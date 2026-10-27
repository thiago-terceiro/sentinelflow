from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from app.agents.investigator import (
    PROMPT_TEMPLATE_ID as INVESTIGATOR_PROMPT_TEMPLATE_ID,
)
from app.agents.investigator import (
    PROMPT_TEMPLATE_SHA256 as INVESTIGATOR_PROMPT_TEMPLATE_SHA256,
)
from app.agents.investigator import (
    PROMPT_TEMPLATE_VERSION as INVESTIGATOR_PROMPT_TEMPLATE_VERSION,
)
from app.agents.investigator import (
    InvestigatorAgent,
)
from app.agents.synthesizer import (
    PROMPT_TEMPLATE_ID as SYNTHESIS_PROMPT_TEMPLATE_ID,
)
from app.agents.synthesizer import (
    PROMPT_TEMPLATE_SHA256 as SYNTHESIS_PROMPT_TEMPLATE_SHA256,
)
from app.agents.synthesizer import (
    PROMPT_TEMPLATE_VERSION as SYNTHESIS_PROMPT_TEMPLATE_VERSION,
)
from app.agents.synthesizer import (
    SynthesizerAgent,
)
from app.db.models import DisputeRecord
from app.errors import NotFoundError
from app.graph.state import DisputeState
from app.schemas.disputes import DisputeDetail, DisputeStatus
from app.schemas.events import StreamEvent, StreamEventType
from app.schemas.investigation import AnalyzerSummary, Evidence
from app.security import Principal, Role
from app.services.audit import record_audit_event
from app.services.guardrails import (
    inspect_prompt_safety,
    validate_evidence_grounding,
    validate_output_guardrails,
)
from app.services.investigations import investigation_broadcaster
from app.services.model_gateway import LLMCallResult
from app.services.risk import calculate_risk
from app.services.trace_safety import redact_text, sha256_text
from app.tools.analyzer_results import run_analyzer
from app.tools.compliance import evaluate_compliance
from app.tools.customer import fetch_customer_profile
from app.tools.device import fetch_device_context
from app.tools.merchant import fetch_merchant_profile
from app.tools.transactions import fetch_transaction_history
from langchain_core.messages import AIMessage
from langgraph.types import interrupt
from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

tracer = trace.get_tracer("sentinelflow.graph")

ToolFunc = Callable[[AsyncSession, str], Awaitable[Evidence]]

TOOL_ACTIVITY_LABELS = {
    "transactions": "Checking transaction history",
    "customer": "Comparing customer history",
    "device": "Reviewing device context",
    "merchant": "Checking merchant profile",
}

ANALYZER_ACTIVITY_LABELS = {
    "fraud_pattern": "Running fraud pattern analyzer",
    "device_fingerprint": "Running device fingerprint analyzer",
}


def _append_event(
    state: DisputeState,
    event_type: StreamEventType,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
) -> dict[str, Any]:
    event = StreamEvent(
        id=event_id or f"evt_{uuid4().hex[:10]}",
        type=event_type,
        timestamp=datetime.now(UTC),
        data=data,
    ).model_dump(mode="json")
    state["timeline_events"].append(event)
    return event


def _append_agent_message(
    state: DisputeState,
    *,
    actor: str,
    message: str,
    stage: str,
    details: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "actor": actor,
        "message": message,
        "stage": stage,
    }
    if details:
        payload["details"] = details
    _append_event(state, "agent_message", payload)


def _tool_call_id(state: DisputeState, tool_name: str, offset: int) -> str:
    return f"tool_{state['investigation_id']}_{state['tool_call_count'] + offset}_{tool_name}"


def _analyzer_call_id(state: DisputeState, analyzer_name: str, offset: int) -> str:
    count = state["analyzer_call_count"] + offset
    return f"analyzer_{state['investigation_id']}_{count}_{analyzer_name}"


def _tool_label(name: str) -> str:
    return TOOL_ACTIVITY_LABELS.get(name, f"Running {name} tool")


def _analyzer_label(name: str) -> str:
    return ANALYZER_ACTIVITY_LABELS.get(name, f"Running {name} analyzer")


def _failure_message(kind: str, name: str, error: str) -> str:
    return f"{kind.title()} '{name}' failed: {error}"


def _actor_from_state(state: DisputeState) -> Principal:
    return Principal(
        user_id=state["principal_id"],
        roles={Role(r) for r in state["principal_roles"]},
    )


def _llm_trace_payload(
    *,
    llm_meta: LLMCallResult[Any] | None,
    base_payload: dict[str, Any],
    template_id: str,
    template_version: str,
    template_sha256: str,
) -> dict[str, Any]:
    if llm_meta is None:
        return {
            **base_payload,
            "provider": "heuristic",
            "model_used": "heuristic",
            "deployment_id": "heuristic-fallback",
            "response_id": None,
            "prompt_template_id": template_id,
            "prompt_template_version": template_version,
            "prompt_template_sha256": template_sha256,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "latency_ms": 0.0,
            "used_heuristic": True,
            "redaction_applied": False,
        }

    prompt_text = llm_meta.prompt_text
    output_text = llm_meta.output_text
    reasoning_text = llm_meta.reasoning_text

    redacted_prompt, prompt_changed = redact_text(prompt_text)
    redacted_output, output_changed = redact_text(output_text)
    redacted_reasoning = None
    reasoning_changed = False
    if isinstance(reasoning_text, str) and reasoning_text:
        redacted_reasoning, reasoning_changed = redact_text(reasoning_text)

    raw_artifact: dict[str, str] = {
        "prompt": prompt_text,
        "output": output_text,
    }
    if isinstance(reasoning_text, str) and reasoning_text:
        raw_artifact["reasoning"] = reasoning_text

    payload: dict[str, Any] = {
        **base_payload,
        "provider": llm_meta.provider,
        "model_used": llm_meta.model_used,
        "deployment_id": llm_meta.deployment_id,
        "response_id": llm_meta.response_id,
        "prompt_template_id": llm_meta.prompt_template_id or template_id,
        "prompt_template_version": llm_meta.prompt_template_version or template_version,
        "prompt_template_sha256": llm_meta.prompt_template_sha256 or template_sha256,
        "input_tokens": llm_meta.input_tokens,
        "output_tokens": llm_meta.output_tokens,
        "reasoning_tokens": llm_meta.reasoning_tokens,
        "latency_ms": llm_meta.latency_ms,
        "used_heuristic": False,
        "prompt_sha256": sha256_text(prompt_text),
        "output_sha256": sha256_text(output_text),
        "reasoning_sha256": (
            sha256_text(reasoning_text) if isinstance(reasoning_text, str) else None
        ),
        "prompt_redacted": redacted_prompt,
        "output_redacted": redacted_output,
        "reasoning_redacted": redacted_reasoning,
        "redaction_applied": prompt_changed or output_changed or reasoning_changed,
    }
    if raw_artifact["prompt"] or raw_artifact["output"]:
        payload["raw_artifact"] = raw_artifact
    return payload


@dataclass(slots=True)
class InvestigationNodes:
    session: AsyncSession
    investigator: InvestigatorAgent
    synthesizer: SynthesizerAgent

    def _record_failure(
        self,
        state: DisputeState,
        *,
        target: str,
        name: str,
        error: str,
        event_payload: dict[str, Any],
    ) -> None:
        if target == "tools":
            failures = state["failed_tools"]
        elif target == "analyzers":
            failures = state["failed_analyzers"]
        else:
            failures = cast(list[dict[str, str]], state.get(f"failed_{target}", []))
        if not any(item["name"] == name for item in failures):
            failures.append({"name": name, "error": error})
        state["messages"].append(AIMessage(content=_failure_message(target[:-1], name, error)))
        _append_event(state, "run_failed", event_payload)

    async def intake(self, state: DisputeState) -> DisputeState:
        result = await self.session.execute(
            select(DisputeRecord).where(DisputeRecord.id == state["dispute_id"])
        )
        dispute = result.scalar_one_or_none()
        if dispute is None:
            raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
        dispute_status: DisputeStatus = cast(DisputeStatus, dispute.status)
        raw_narrative = dispute.narrative or ""
        guard_result = inspect_prompt_safety(raw_narrative)
        if not guard_result.passed:
            _append_agent_message(
                state,
                actor="guardrail",
                message=(
                    f"Prompt injection pattern intercepted in dispute narrative: "
                    f"{', '.join(guard_result.violations)}"
                ),
                stage="intake",
                details={
                    "violations": guard_result.violations,
                    "risk_score": guard_result.risk_score,
                },
            )
            _append_event(
                state,
                "guardrail_triggered",
                {
                    "phase": "intake",
                    "violations": guard_result.violations,
                    "risk_score": guard_result.risk_score,
                    "details": guard_result.details,
                },
                event_id=f"guardrail_intake_{state['investigation_id']}",
            )
            await record_audit_event(
                self.session,
                actor=_actor_from_state(state),
                event_name="security.prompt_injection_intercepted",
                payload={
                    "phase": "intake",
                    "violations": guard_result.violations,
                    "risk_score": guard_result.risk_score,
                },
                investigation_id=state["investigation_id"],
                dispute_id=state["dispute_id"],
            )

        sanitized_narrative, _ = redact_text(guard_result.sanitized_text)
        state["dispute"] = DisputeDetail(
            id=dispute.id,
            case_code=dispute.case_code,
            title=dispute.title,
            amount=dispute.amount,
            currency=dispute.currency,
            status=dispute_status,
            created_at=dispute.created_at,
            customer_id=dispute.customer_id,
            merchant_id=dispute.merchant_id,
            narrative=sanitized_narrative,
            tags=list(dispute.attributes.get("tags", [])),
        )
        state["status"] = "running"
        state["messages"].append(AIMessage(content="Investigation started."))
        _append_event(
            state,
            "agent_status_updated",
            {
                "phase": "intake",
                "message": "Reviewing dispute intake",
                "investigation_id": state["investigation_id"],
            },
        )
        return state

    async def investigate(self, state: DisputeState) -> DisputeState:
        with tracer.start_as_current_span(
            "investigation.node.investigate",
            attributes={
                "dispute.id": state["dispute_id"],
                "investigation.id": state["investigation_id"],
                "iteration.count": state["iteration_count"],
            },
        ) as span:
            dispute = state["dispute"]
            if dispute is None:
                raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
            _append_agent_message(
                state,
                actor="orchestrator",
                message="Calling investigator agent for hypothesis update.",
                stage="investigate",
                details={
                    "evidence_count": len(state["evidence"]),
                    "analyzer_count": len(state["analyzer_summaries"]),
                },
            )
            iteration_kwargs: dict[str, Any] = {
                "dispute": dispute,
                "evidence": state["evidence"],
                "analyzers": state["analyzer_summaries"],
                "failed_tools": state["failed_tools"],
                "failed_analyzers": state["failed_analyzers"],
            }
            if state.get("reviewer_guidance") is not None:
                guidance_str = str(state["reviewer_guidance"])
                guidance_guard = inspect_prompt_safety(guidance_str)
                if not guidance_guard.passed:
                    _append_agent_message(
                        state,
                        actor="guardrail",
                        message=(
                            f"Prompt injection intercepted in reviewer guidance: "
                            f"{', '.join(guidance_guard.violations)}"
                        ),
                        stage="investigate",
                        details={
                            "violations": guidance_guard.violations,
                            "risk_score": guidance_guard.risk_score,
                        },
                    )
                    _append_event(
                        state,
                        "guardrail_triggered",
                        {
                            "phase": "investigate",
                            "violations": guidance_guard.violations,
                            "risk_score": guidance_guard.risk_score,
                            "details": guidance_guard.details,
                        },
                        event_id=f"guardrail_guidance_{state['investigation_id']}_{state['iteration_count']}",
                    )
                iteration_kwargs["reviewer_guidance"] = guidance_guard.sanitized_text
                state["reviewer_guidance"] = None
            await investigation_broadcaster.publish(
                state["investigation_id"],
                StreamEvent(
                    id=f"reasoning_delta_{state['investigation_id']}_{state['iteration_count']}_start",
                    type="reasoning_delta",
                    timestamp=datetime.now(UTC),
                    data={
                        "phase": "investigate",
                        "iteration": state["iteration_count"] + 1,
                        "delta": (
                            f"Analyzing {len(state['evidence'])} evidence items and "
                            f"{len(state['analyzer_summaries'])} analyzer summaries..."
                        ),
                    },
                ).model_dump(mode="json"),
            )

            async def _emit_reasoning_delta(delta_text: str) -> None:
                await investigation_broadcaster.publish(
                    state["investigation_id"],
                    StreamEvent(
                        id=f"reasoning_delta_{state['investigation_id']}_{uuid4().hex[:8]}",
                        type="reasoning_delta",
                        timestamp=datetime.now(UTC),
                        data={
                            "phase": "investigate",
                            "iteration": state["iteration_count"] + 1,
                            "delta": delta_text,
                        },
                    ).model_dump(mode="json"),
                )

            if "on_delta" in inspect.signature(self.investigator.run_iteration).parameters:
                iteration_kwargs["on_delta"] = _emit_reasoning_delta
            iteration, llm_meta = await self.investigator.run_iteration(**iteration_kwargs)
            if getattr(iteration, "thought_process", ""):
                await investigation_broadcaster.publish(
                    state["investigation_id"],
                    StreamEvent(
                        id=f"reasoning_delta_{state['investigation_id']}_{state['iteration_count']}_thought",
                        type="reasoning_delta",
                        timestamp=datetime.now(UTC),
                        data={
                            "phase": "investigate",
                            "iteration": state["iteration_count"] + 1,
                            "delta": getattr(iteration, "thought_process", ""),
                        },
                    ).model_dump(mode="json"),
                )
            if llm_meta is not None:
                span.set_attribute("gen_ai.system", llm_meta.provider)
                span.set_attribute("gen_ai.request.model", llm_meta.model_used)
                span.set_attribute("gen_ai.usage.input_tokens", llm_meta.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", llm_meta.output_tokens)
            _append_agent_message(
                state,
                actor="investigator",
                message="Returned hypothesis update to orchestrator.",
                stage="investigate",
                details={
                    "tool_requests": len(iteration.tool_requests),
                    "analyzer_requests": len(iteration.analyzer_requests),
                    "used_heuristic": llm_meta is None,
                    "thought_process": getattr(iteration, "thought_process", ""),
                    "reasoning_steps": getattr(iteration, "reasoning_steps", []),
                },
            )
            valid_ev_ids = {item.id for item in state["evidence"]}
            sanitized_hyps, _, fabricated_ids = validate_output_guardrails(
                iteration.hypotheses, None, valid_ev_ids
            )
            if fabricated_ids:
                iteration = iteration.model_copy(update={"hypotheses": sanitized_hyps})
                _append_event(
                    state,
                    "hallucination_detected",
                    {
                        "phase": "investigate",
                        "hallucinated_entities": fabricated_ids,
                        "confidence_penalty": 0.15,
                        "details": (
                            f"Stripped fabricated evidence IDs: {', '.join(fabricated_ids)}"
                        ),
                    },
                    event_id=(
                        f"hallucination_inv_{state['investigation_id']}_"
                        f"{state['iteration_count'] + 1}"
                    ),
                )
            state["iteration_count"] += 1
            state["hypotheses"] = iteration.hypotheses
            state["unresolved_questions"] = iteration.unresolved_questions
            state["pending_tools"] = [item.model_dump() for item in iteration.tool_requests]
            state["pending_analyzers"] = [item.model_dump() for item in iteration.analyzer_requests]
            state["messages"].append(AIMessage(content=iteration.summary))
            await record_audit_event(
                self.session,
                actor=_actor_from_state(state),
                event_name="investigation.llm_iteration",
                payload=_llm_trace_payload(
                    llm_meta=llm_meta,
                    base_payload={
                        "iteration": state["iteration_count"],
                        "hypothesis_count": len(iteration.hypotheses),
                        "tool_requests": len(iteration.tool_requests),
                        "analyzer_requests": len(iteration.analyzer_requests),
                        "thought_process": getattr(iteration, "thought_process", ""),
                    },
                    template_id=INVESTIGATOR_PROMPT_TEMPLATE_ID,
                    template_version=INVESTIGATOR_PROMPT_TEMPLATE_VERSION,
                    template_sha256=INVESTIGATOR_PROMPT_TEMPLATE_SHA256,
                ),
                investigation_id=state["investigation_id"],
                dispute_id=state["dispute_id"],
            )
            ev_hypothesis = _append_event(
                state,
                "hypothesis_updated",
                {
                    "iteration": state["iteration_count"],
                    "hypotheses": [item.model_dump(mode="json") for item in iteration.hypotheses],
                    "unresolved_questions": iteration.unresolved_questions,
                    "thought_process": getattr(iteration, "thought_process", ""),
                    "reasoning_steps": getattr(iteration, "reasoning_steps", []),
                },
                event_id=f"hypothesis_{state['investigation_id']}_{state['iteration_count']}",
            )
            await investigation_broadcaster.publish(state["investigation_id"], ev_hypothesis)
            _append_event(
                state,
                "agent_status_updated",
                {
                    "phase": "investigate",
                    "message": (
                        "Gathering authoritative evidence"
                        if state["pending_tools"] or state["pending_analyzers"]
                        else "Preparing final recommendation"
                    ),
                    "investigation_id": state["investigation_id"],
                    "iteration": state["iteration_count"],
                },
            )
            return state

    async def collect(self, state: DisputeState) -> DisputeState:
        with tracer.start_as_current_span(
            "investigation.node.collect",
            attributes={
                "dispute.id": state["dispute_id"],
                "investigation.id": state["investigation_id"],
            },
        ):
            tools: dict[str, ToolFunc] = {
                "transactions": fetch_transaction_history,
                "customer": fetch_customer_profile,
                "device": fetch_device_context,
                "merchant": fetch_merchant_profile,
            }
            if state["pending_tools"]:
                _append_agent_message(
                    state,
                    actor="orchestrator",
                    message="Calling evidence tools for investigator requests.",
                    stage="collect",
                    details={"tool_request_count": len(state["pending_tools"])},
                )
            session_lock = asyncio.Lock()

            async def _run_single_tool(index: int, tool_request: dict[str, Any]) -> Evidence | None:
                tool_name = tool_request["name"]
                tool = tools.get(tool_name)
                if tool is None:
                    self._record_failure(
                        state,
                        target="tools",
                        name=tool_name,
                        error="Unsupported tool request.",
                        event_payload={
                            "phase": "collect",
                            "kind": "tool",
                            "tool_name": tool_name,
                            "error": "Unsupported tool request.",
                        },
                    )
                    return None
                tool_call_id = _tool_call_id(state, tool_name, index)
                with tracer.start_as_current_span(
                    f"investigation.tool.{tool_name}",
                    attributes={
                        "tool.name": tool_name,
                        "tool.call_id": tool_call_id,
                        "dispute.id": state["dispute_id"],
                        "investigation.id": state["investigation_id"],
                    },
                ) as tool_span:
                    ev_tool_started = _append_event(
                        state,
                        "tool_started",
                        {
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "label": _tool_label(tool_name),
                        },
                        event_id=f"tool_started_{tool_call_id}",
                    )
                    await investigation_broadcaster.publish(
                        state["investigation_id"], ev_tool_started
                    )
                    try:
                        bind = getattr(self.session, "bind", None)
                        if isinstance(bind, AsyncEngine):
                            async with AsyncSession(
                                bind=bind, expire_on_commit=False
                            ) as tool_session:
                                evidence = await tool(tool_session, state["dispute_id"])
                        else:
                            async with session_lock:
                                evidence = await tool(self.session, state["dispute_id"])
                        tool_span.set_attribute("evidence.id", evidence.id)
                    except Exception as exc:
                        tool_span.record_exception(exc)
                        tool_span.set_status(trace.StatusCode.ERROR, str(exc))
                        self._record_failure(
                            state,
                            target="tools",
                            name=tool_name,
                            error=str(exc),
                            event_payload={
                                "phase": "collect",
                                "kind": "tool",
                                "tool_name": tool_name,
                                "tool_call_id": tool_call_id,
                                "error": str(exc),
                            },
                        )
                        return None

                    async with session_lock:
                        await record_audit_event(
                            self.session,
                            actor=_actor_from_state(state),
                            event_name="investigation.tool_executed",
                            payload={
                                "tool_name": tool_name,
                                "tool_call_id": tool_call_id,
                                "evidence_id": evidence.id,
                                "status": "success",
                            },
                            investigation_id=state["investigation_id"],
                            dispute_id=state["dispute_id"],
                        )
                    ev_tool_completed = _append_event(
                        state,
                        "tool_completed",
                        {
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "label": _tool_label(tool_name),
                            "evidence_id": evidence.id,
                        },
                        event_id=f"tool_completed_{tool_call_id}",
                    )
                    await investigation_broadcaster.publish(
                        state["investigation_id"], ev_tool_completed
                    )
                    ev_evidence = _append_event(
                        state,
                        "evidence_added",
                        {
                            **evidence.model_dump(mode="json"),
                            "tool_call_id": tool_call_id,
                        },
                        event_id=f"evidence_{evidence.id}",
                    )
                    await investigation_broadcaster.publish(state["investigation_id"], ev_evidence)
                    return evidence

            if state["pending_tools"]:
                tool_tasks = [
                    _run_single_tool(index, tool_req)
                    for index, tool_req in enumerate(state["pending_tools"], start=1)
                ]
                tool_results = await asyncio.gather(*tool_tasks, return_exceptions=True)
                state["tool_call_count"] += len(state["pending_tools"])
                for result in tool_results:
                    if isinstance(result, Evidence):
                        state["evidence"].append(result)
                    elif isinstance(result, Exception):
                        self._record_failure(
                            state,
                            target="tools",
                            name="unknown",
                            error=str(result),
                            event_payload={
                                "phase": "collect",
                                "kind": "tool",
                                "error": str(result),
                            },
                        )

            existing = state["evidence"][:]
            if state["pending_analyzers"]:
                _append_agent_message(
                    state,
                    actor="orchestrator",
                    message="Calling analyzer agents for specialized interpretation.",
                    stage="collect",
                    details={"analyzer_request_count": len(state["pending_analyzers"])},
                )

                async def _run_single_analyzer(
                    index: int, analyzer_request: dict[str, Any]
                ) -> AnalyzerSummary | None:
                    analyzer_name = analyzer_request["name"]
                    analyzer_id = _analyzer_call_id(state, analyzer_name, index)
                    with tracer.start_as_current_span(
                        f"investigation.analyzer.{analyzer_name}",
                        attributes={
                            "analyzer.name": analyzer_name,
                            "analyzer.id": analyzer_id,
                            "dispute.id": state["dispute_id"],
                            "investigation.id": state["investigation_id"],
                        },
                    ) as analyzer_span:
                        _append_agent_message(
                            state,
                            actor="orchestrator",
                            message=f"Calling analyzer agent {analyzer_name}.",
                            stage="collect",
                            details={"analyzer_id": analyzer_id},
                        )
                        ev_analyzer_started = _append_event(
                            state,
                            "analyzer_started",
                            {
                                "analyzer_id": analyzer_id,
                                "analyzer_name": analyzer_name,
                                "label": _analyzer_label(analyzer_name),
                            },
                            event_id=f"analyzer_started_{analyzer_id}",
                        )
                        await investigation_broadcaster.publish(
                            state["investigation_id"], ev_analyzer_started
                        )
                        try:
                            summary = await run_analyzer(analyzer_name, existing)
                            analyzer_span.set_attribute("analyzer.confidence", summary.confidence)
                        except Exception as exc:
                            analyzer_span.record_exception(exc)
                            analyzer_span.set_status(trace.StatusCode.ERROR, str(exc))
                            self._record_failure(
                                state,
                                target="analyzers",
                                name=analyzer_name,
                                error=str(exc),
                                event_payload={
                                    "phase": "collect",
                                    "kind": "analyzer",
                                    "analyzer_name": analyzer_name,
                                    "analyzer_id": analyzer_id,
                                    "error": str(exc),
                                },
                            )
                            return None

                        async with session_lock:
                            await record_audit_event(
                                self.session,
                                actor=_actor_from_state(state),
                                event_name="investigation.analyzer_executed",
                                payload={
                                    "analyzer_name": analyzer_name,
                                    "analyzer_id": analyzer_id,
                                    "finding_count": len(summary.findings),
                                    "confidence": summary.confidence,
                                    "status": "success",
                                },
                                investigation_id=state["investigation_id"],
                                dispute_id=state["dispute_id"],
                            )
                        _append_agent_message(
                            state,
                            actor=analyzer_name,
                            message="Analyzer returned findings to orchestrator.",
                            stage="collect",
                            details={
                                "finding_count": len(summary.findings),
                                "contradiction_count": len(summary.contradictions),
                            },
                        )
                        ev_analyzer_completed = _append_event(
                            state,
                            "analyzer_completed",
                            {
                                **summary.model_dump(mode="json"),
                                "analyzer_id": analyzer_id,
                                "analyzer_name": analyzer_name,
                            },
                            event_id=f"analyzer_completed_{analyzer_id}",
                        )
                        await investigation_broadcaster.publish(
                            state["investigation_id"], ev_analyzer_completed
                        )
                        return summary

                analyzer_tasks = [
                    _run_single_analyzer(index, analyzer_req)
                    for index, analyzer_req in enumerate(state["pending_analyzers"], start=1)
                ]
                analyzer_results = await asyncio.gather(*analyzer_tasks, return_exceptions=True)
                state["analyzer_call_count"] += len(state["pending_analyzers"])
                for analyzer_res in analyzer_results:
                    if isinstance(analyzer_res, AnalyzerSummary):
                        state["analyzer_summaries"].append(analyzer_res)
                    elif isinstance(analyzer_res, Exception):
                        self._record_failure(
                            state,
                            target="analyzers",
                            name="unknown",
                            error=str(analyzer_res),
                            event_payload={
                                "phase": "collect",
                                "kind": "analyzer",
                                "error": str(analyzer_res),
                            },
                        )
            state["pending_tools"] = []
            state["pending_analyzers"] = []
            return state

    async def synthesize(self, state: DisputeState) -> DisputeState:
        with tracer.start_as_current_span(
            "investigation.node.synthesize",
            attributes={
                "dispute.id": state["dispute_id"],
                "investigation.id": state["investigation_id"],
            },
        ) as span:
            _append_agent_message(
                state,
                actor="orchestrator",
                message="Calling risk engine and synthesizer.",
                stage="synthesize",
                details={"evidence_count": len(state["evidence"])},
            )
            _append_event(
                state,
                "agent_status_updated",
                {
                    "phase": "synthesize",
                    "message": "Scoring risk and drafting recommendation",
                    "investigation_id": state["investigation_id"],
                },
            )
            risk_assessment = calculate_risk(state["evidence"], state["analyzer_summaries"])
            state["risk_assessment"] = risk_assessment
            span.set_attribute("risk.score", risk_assessment.score)
            span.set_attribute("risk.level", risk_assessment.level)
            _append_agent_message(
                state,
                actor="risk_engine",
                message="Returned deterministic risk assessment.",
                stage="synthesize",
                details={
                    "risk_level": risk_assessment.level,
                    "risk_score": risk_assessment.score,
                },
            )
            state["compliance_findings"] = evaluate_compliance(state["evidence"])
            _append_agent_message(
                state,
                actor="compliance_engine",
                message="Returned compliance findings to orchestrator.",
                stage="synthesize",
                details={"finding_count": len(state["compliance_findings"])},
            )
            await investigation_broadcaster.publish(
                state["investigation_id"],
                StreamEvent(
                    id=f"synthesis_delta_{state['investigation_id']}_{state['iteration_count']}_start",
                    type="synthesis_delta",
                    timestamp=datetime.now(UTC),
                    data={
                        "phase": "synthesize",
                        "delta": (
                            f"Synthesizing risk score ({risk_assessment.score:.2f} / "
                            f"{risk_assessment.level}) across "
                            f"{len(state['evidence'])} evidence records..."
                        ),
                    },
                ).model_dump(mode="json"),
            )
            report, llm_meta = await self.synthesizer.build_report(
                hypotheses=state["hypotheses"],
                risk=risk_assessment,
                compliance=state["compliance_findings"],
                evidence_ids=[item.id for item in state["evidence"]],
                unresolved_questions=state["unresolved_questions"],
                **(
                    {
                        "on_delta": lambda delta_text: investigation_broadcaster.publish(
                            state["investigation_id"],
                            StreamEvent(
                                id=f"synthesis_delta_{state['investigation_id']}_{uuid4().hex[:8]}",
                                type="synthesis_delta",
                                timestamp=datetime.now(UTC),
                                data={"phase": "synthesize", "delta": delta_text},
                            ).model_dump(mode="json"),
                        )
                    }
                    if "on_delta" in inspect.signature(self.synthesizer.build_report).parameters
                    else {}
                ),
            )
            valid_ev_ids = {item.id for item in state["evidence"]}
            sanitized_hyps, sanitized_report, fabricated_ids = validate_output_guardrails(
                state["hypotheses"], report, valid_ev_ids
            )
            if fabricated_ids and sanitized_report is not None:
                state["hypotheses"] = sanitized_hyps
                report = sanitized_report
                _append_event(
                    state,
                    "hallucination_detected",
                    {
                        "phase": "synthesize",
                        "hallucinated_entities": fabricated_ids,
                        "confidence_penalty": 0.15,
                        "details": (
                            "Stripped fabricated evidence IDs from report: "
                            f"{', '.join(fabricated_ids)}"
                        ),
                    },
                    event_id=(
                        f"hallucination_cite_{state['investigation_id']}_{state['iteration_count']}"
                    ),
                )
            grounding = validate_evidence_grounding(report.conclusion, state["evidence"])
            if not grounding.grounded:
                _append_agent_message(
                    state,
                    actor="guardrail",
                    message=(
                        f"Evidence grounding check flagged ungrounded entities: "
                        f"{', '.join(grounding.hallucinated_entities)}"
                    ),
                    stage="synthesize",
                    details={
                        "hallucinated_entities": grounding.hallucinated_entities,
                        "confidence_penalty": grounding.confidence_penalty,
                    },
                )
                _append_event(
                    state,
                    "hallucination_detected",
                    {
                        "phase": "synthesize",
                        "hallucinated_entities": grounding.hallucinated_entities,
                        "confidence_penalty": grounding.confidence_penalty,
                        "details": grounding.details,
                    },
                    event_id=f"hallucination_{state['investigation_id']}_{state['iteration_count']}",
                )
                await record_audit_event(
                    self.session,
                    actor=_actor_from_state(state),
                    event_name="audit.evidence_hallucination_flagged",
                    payload={
                        "hallucinated_entities": grounding.hallucinated_entities,
                        "confidence_penalty": grounding.confidence_penalty,
                    },
                    investigation_id=state["investigation_id"],
                    dispute_id=state["dispute_id"],
                )
                if grounding.confidence_penalty > 0.0:
                    adjusted_conf = max(
                        0.10,
                        round(report.confidence - grounding.confidence_penalty, 2),
                    )
                    report = report.model_copy(update={"confidence": adjusted_conf})

            state["investigation_report"] = report
            if llm_meta is not None:
                span.set_attribute("gen_ai.system", llm_meta.provider)
                span.set_attribute("gen_ai.request.model", llm_meta.model_used)
                span.set_attribute("gen_ai.usage.input_tokens", llm_meta.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", llm_meta.output_tokens)
            _append_agent_message(
                state,
                actor="synthesizer",
                message="Returned recommendation draft to orchestrator.",
                stage="synthesize",
                details={
                    "recommendation": report.recommendation,
                    "used_heuristic": llm_meta is None,
                },
            )
            await record_audit_event(
                self.session,
                actor=_actor_from_state(state),
                event_name="investigation.synthesis",
                payload=_llm_trace_payload(
                    llm_meta=llm_meta,
                    base_payload={
                        "recommendation": report.recommendation,
                        "confidence": report.confidence,
                    },
                    template_id=SYNTHESIS_PROMPT_TEMPLATE_ID,
                    template_version=SYNTHESIS_PROMPT_TEMPLATE_VERSION,
                    template_sha256=SYNTHESIS_PROMPT_TEMPLATE_SHA256,
                ),
                investigation_id=state["investigation_id"],
                dispute_id=state["dispute_id"],
            )
            _append_event(
                state,
                "risk_updated",
                risk_assessment.model_dump(mode="json"),
                event_id=f"risk_{state['investigation_id']}_{state['iteration_count']}",
            )
            _append_event(
                state,
                "final_report_ready",
                report.model_dump(mode="json"),
                event_id=f"report_{state['investigation_id']}",
            )
            return state

    async def approval(self, state: DisputeState) -> DisputeState:
        with tracer.start_as_current_span(
            "investigation.node.approval",
            attributes={
                "dispute.id": state["dispute_id"],
                "investigation.id": state["investigation_id"],
            },
        ):
            approval_payload: dict[str, Any] = {
                "investigation_id": state["investigation_id"],
                "report": state["investigation_report"].model_dump(mode="json")
                if state["investigation_report"]
                else None,
                "risk": (
                    state["risk_assessment"].model_dump(mode="json")
                    if state["risk_assessment"]
                    else None
                ),
                "evidence": [item.model_dump(mode="json") for item in state["evidence"]],
            }
            _append_event(
                state,
                "agent_status_updated",
                {
                    "phase": "approval",
                    "message": "Awaiting reviewer approval",
                    "investigation_id": state["investigation_id"],
                },
            )
            _append_event(
                state,
                "approval_required",
                approval_payload,
                event_id=f"approval_{state['investigation_id']}",
            )
            decision = interrupt(
                {
                    "type": "human_approval",
                    "dispute_id": state["dispute_id"],
                    "recommendation": (
                        state["investigation_report"].model_dump()
                        if state["investigation_report"]
                        else None
                    ),
                    "risk": (
                        state["risk_assessment"].model_dump() if state["risk_assessment"] else None
                    ),
                    "evidence": [item.model_dump() for item in state["evidence"]],
                }
            )
            state["approval_decision"] = decision
            report = state["investigation_report"]
            decision_val = decision.get("decision")
            if report and decision_val == "deny":
                state["investigation_report"] = report.model_copy(update={"recommendation": "deny"})
            elif decision_val == "request_revision":
                state["revision_count"] = state.get("revision_count", 0) + 1
                guidance, _ = redact_text(
                    decision.get("guidance")
                    or decision.get("comment")
                    or "Reviewer requested revision."
                )
                state["reviewer_guidance"] = guidance
                _append_agent_message(
                    state,
                    actor="reviewer",
                    message=f"Reviewer requested re-investigation: {guidance}",
                    stage="approval",
                    details={"guidance": guidance},
                )
                _append_event(
                    state,
                    "agent_status_updated",
                    {
                        "phase": "investigate",
                        "message": f"Reviewer requested revision: {guidance}",
                        "investigation_id": state["investigation_id"],
                    },
                )
            return state

    async def finalize(self, state: DisputeState) -> DisputeState:
        with tracer.start_as_current_span(
            "investigation.node.finalize",
            attributes={
                "dispute.id": state["dispute_id"],
                "investigation.id": state["investigation_id"],
            },
        ):
            state["status"] = "completed"
            _append_event(
                state,
                "agent_status_updated",
                {
                    "phase": "finalize",
                    "message": "Investigation complete",
                    "investigation_id": state["investigation_id"],
                },
            )
            _append_event(
                state,
                "run_completed",
                {
                    "investigation_id": state["investigation_id"],
                    "report": state["investigation_report"].model_dump(mode="json")
                    if state["investigation_report"]
                    else None,
                },
                event_id=f"run_completed_{state['investigation_id']}",
            )
            return state

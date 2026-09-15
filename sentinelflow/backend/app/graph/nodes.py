from __future__ import annotations

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
from app.schemas.investigation import Evidence
from app.security import Principal, Role
from app.services.audit import record_audit_event
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
) -> None:
    state["timeline_events"].append(
        StreamEvent(
            id=event_id or f"evt_{uuid4().hex[:10]}",
            type=event_type,
            timestamp=datetime.now(UTC),
            data=data,
        ).model_dump(mode="json")
    )


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
        failures = cast(list[dict[str, str]], state[f"failed_{target}"])
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
            narrative=dispute.narrative,
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
        iteration, llm_meta = await self.investigator.run_iteration(
            dispute=dispute,
            evidence=state["evidence"],
            analyzers=state["analyzer_summaries"],
            failed_tools=state["failed_tools"],
            failed_analyzers=state["failed_analyzers"],
        )
        _append_agent_message(
            state,
            actor="investigator",
            message="Returned hypothesis update to orchestrator.",
            stage="investigate",
            details={
                "tool_requests": len(iteration.tool_requests),
                "analyzer_requests": len(iteration.analyzer_requests),
                "used_heuristic": llm_meta is None,
            },
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
                },
                template_id=INVESTIGATOR_PROMPT_TEMPLATE_ID,
                template_version=INVESTIGATOR_PROMPT_TEMPLATE_VERSION,
                template_sha256=INVESTIGATOR_PROMPT_TEMPLATE_SHA256,
            ),
            investigation_id=state["investigation_id"],
            dispute_id=state["dispute_id"],
        )
        _append_event(
            state,
            "hypothesis_updated",
            {
                "iteration": state["iteration_count"],
                "hypotheses": [item.model_dump(mode="json") for item in iteration.hypotheses],
                "unresolved_questions": iteration.unresolved_questions,
            },
            event_id=f"hypothesis_{state['investigation_id']}_{state['iteration_count']}",
        )
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
        for index, tool_request in enumerate(state["pending_tools"], start=1):
            tool = tools.get(tool_request["name"])
            if tool is None:
                self._record_failure(
                    state,
                    target="tools",
                    name=tool_request["name"],
                    error="Unsupported tool request.",
                    event_payload={
                        "phase": "collect",
                        "kind": "tool",
                        "tool_name": tool_request["name"],
                        "error": "Unsupported tool request.",
                    },
                )
                continue
            tool_call_id = _tool_call_id(state, tool_request["name"], index)
            _append_event(
                state,
                "tool_started",
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_request["name"],
                    "label": _tool_label(tool_request["name"]),
                },
                event_id=f"tool_started_{tool_call_id}",
            )
            state["tool_call_count"] += 1
            try:
                evidence = await tool(self.session, state["dispute_id"])
            except Exception as exc:
                self._record_failure(
                    state,
                    target="tools",
                    name=tool_request["name"],
                    error=str(exc),
                    event_payload={
                        "phase": "collect",
                        "kind": "tool",
                        "tool_name": tool_request["name"],
                        "tool_call_id": tool_call_id,
                        "error": str(exc),
                    },
                )
                continue
            state["evidence"].append(evidence)
            _append_event(
                state,
                "tool_completed",
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_request["name"],
                    "label": _tool_label(tool_request["name"]),
                    "evidence_id": evidence.id,
                },
                event_id=f"tool_completed_{tool_call_id}",
            )
            _append_event(
                state,
                "evidence_added",
                {
                    **evidence.model_dump(mode="json"),
                    "tool_call_id": tool_call_id,
                },
                event_id=f"evidence_{evidence.id}",
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
        for index, analyzer_request in enumerate(state["pending_analyzers"], start=1):
            analyzer_id = _analyzer_call_id(state, analyzer_request["name"], index)
            _append_agent_message(
                state,
                actor="orchestrator",
                message=f"Calling analyzer agent {analyzer_request['name']}.",
                stage="collect",
                details={"analyzer_id": analyzer_id},
            )
            _append_event(
                state,
                "analyzer_started",
                {
                    "analyzer_id": analyzer_id,
                    "analyzer_name": analyzer_request["name"],
                    "label": _analyzer_label(analyzer_request["name"]),
                },
                event_id=f"analyzer_started_{analyzer_id}",
            )
            state["analyzer_call_count"] += 1
            try:
                summary = await run_analyzer(analyzer_request["name"], existing)
            except Exception as exc:
                self._record_failure(
                    state,
                    target="analyzers",
                    name=analyzer_request["name"],
                    error=str(exc),
                    event_payload={
                        "phase": "collect",
                        "kind": "analyzer",
                        "analyzer_name": analyzer_request["name"],
                        "analyzer_id": analyzer_id,
                        "error": str(exc),
                    },
                )
                continue
            state["analyzer_summaries"].append(summary)
            _append_agent_message(
                state,
                actor=analyzer_request["name"],
                message="Analyzer returned findings to orchestrator.",
                stage="collect",
                details={
                    "finding_count": len(summary.findings),
                    "contradiction_count": len(summary.contradictions),
                },
            )
            _append_event(
                state,
                "analyzer_completed",
                {
                    **summary.model_dump(mode="json"),
                    "analyzer_id": analyzer_id,
                    "analyzer_name": analyzer_request["name"],
                },
                event_id=f"analyzer_completed_{analyzer_id}",
            )
        state["pending_tools"] = []
        state["pending_analyzers"] = []
        return state

    async def synthesize(self, state: DisputeState) -> DisputeState:
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
        state["risk_assessment"] = calculate_risk(state["evidence"], state["analyzer_summaries"])
        _append_agent_message(
            state,
            actor="risk_engine",
            message="Returned deterministic risk assessment.",
            stage="synthesize",
            details={
                "risk_level": state["risk_assessment"].level,
                "risk_score": state["risk_assessment"].score,
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
        state["investigation_report"], llm_meta = await self.synthesizer.build_report(
            hypotheses=state["hypotheses"],
            risk=state["risk_assessment"],
            compliance=state["compliance_findings"],
            evidence_ids=[item.id for item in state["evidence"]],
            unresolved_questions=state["unresolved_questions"],
        )
        _append_agent_message(
            state,
            actor="synthesizer",
            message="Returned recommendation draft to orchestrator.",
            stage="synthesize",
            details={
                "recommendation": state["investigation_report"].recommendation,
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
                    "recommendation": state["investigation_report"].recommendation
                    if state["investigation_report"]
                    else None,
                    "confidence": state["investigation_report"].confidence
                    if state["investigation_report"]
                    else None,
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
            state["risk_assessment"].model_dump(mode="json"),
            event_id=f"risk_{state['investigation_id']}_{state['iteration_count']}",
        )
        _append_event(
            state,
            "final_report_ready",
            state["investigation_report"].model_dump(mode="json"),
            event_id=f"report_{state['investigation_id']}",
        )
        return state

    async def approval(self, state: DisputeState) -> DisputeState:
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
                "recommendation": state["investigation_report"].model_dump()
                if state["investigation_report"]
                else None,
                "risk": state["risk_assessment"].model_dump() if state["risk_assessment"] else None,
                "evidence": [item.model_dump() for item in state["evidence"]],
            }
        )
        state["approval_decision"] = decision
        report = state["investigation_report"]
        if report and decision.get("decision") == "deny":
            state["investigation_report"] = report.model_copy(update={"recommendation": "deny"})
        return state

    async def finalize(self, state: DisputeState) -> DisputeState:
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

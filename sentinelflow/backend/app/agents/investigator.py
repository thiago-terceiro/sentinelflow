from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable
from typing import cast

from app.graph.prompts import investigator_iteration, investigator_system
from app.schemas.disputes import DisputeDetail
from app.schemas.investigation import AnalyzerSummary, Evidence, InvestigationHypothesis
from app.services.model_gateway import LLMCallResult, ModelGateway
from app.services.trace_safety import redact_text, sha256_text
from pydantic import BaseModel, Field

TOOL_REQUESTS = (
    ("transactions", "transaction", "Need authoritative payment history."),
    ("customer", "customer", "Need prior dispute and account history."),
    ("device", "device", "Need device and network context."),
    ("merchant", "merchant", "Need merchant risk posture."),
)

DEFAULT_ANALYZERS = (
    ("fraud_pattern", "Need synthesized fraud pattern view."),
    ("device_fingerprint", "Need device-focused interpretation."),
)

PROMPT_TEMPLATE_ID = "investigator_iteration"
PROMPT_TEMPLATE_VERSION = "2026-09-02"
PROMPT_TEMPLATE_SHA256 = sha256_text(f"{investigator_system}\n{investigator_iteration}")


class ToolRequest(BaseModel):
    name: str
    reason: str


class AnalyzerRequest(BaseModel):
    name: str
    reason: str


class InvestigatorIteration(BaseModel):
    summary: str
    thought_process: str = Field(
        default="",
        description=(
            "Internal chain of thought evaluating contradictory evidence "
            "and formulating next steps."
        ),
    )
    reasoning_steps: list[str] = Field(
        default_factory=lambda: cast(list[str], []),
        description="Step-by-step investigative reasoning deductions.",
    )
    hypotheses: list[InvestigationHypothesis]
    unresolved_questions: list[str]
    tool_requests: list[ToolRequest] = Field(default_factory=lambda: cast(list[ToolRequest], []))
    analyzer_requests: list[AnalyzerRequest] = Field(
        default_factory=lambda: cast(list[AnalyzerRequest], [])
    )
    should_finish: bool = False


class InvestigatorAgent:
    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    @staticmethod
    def _failure_note(failures: Iterable[dict[str, str]]) -> str:
        return (
            "\n".join(
                f"- {item['name']}: {item['error']}" for item in failures if item.get("error")
            )
            or "none"
        )

    async def run_iteration(
        self,
        *,
        dispute: DisputeDetail,
        evidence: list[Evidence],
        analyzers: list[AnalyzerSummary],
        failed_tools: list[dict[str, str]],
        failed_analyzers: list[dict[str, str]],
        reviewer_guidance: str | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[InvestigatorIteration, LLMCallResult[InvestigatorIteration] | None]:
        sanitized_dispute_json, _ = redact_text(dispute.model_dump_json(indent=2))
        serialized_evidence = [
            {
                "id": item.id,
                "category": item.category,
                "origin": item.origin,
                "summary": item.summary,
                "facts": item.facts,
                "confidence": item.confidence,
            }
            for item in evidence
        ]
        sanitized_evidence_json, _ = redact_text(json.dumps(serialized_evidence, default=str))
        serialized_analyzers = [
            {
                "analyzer": item.analyzer,
                "summary": item.summary,
                "findings": item.findings,
                "contradictions": item.contradictions,
                "evidence_ids": item.evidence_ids,
                "confidence": item.confidence,
            }
            for item in analyzers
        ]
        sanitized_analyzers_json, _ = redact_text(json.dumps(serialized_analyzers, default=str))
        evidence_block = (
            "Collected Evidence (cite exact 'id' strings in supporting_evidence_ids "
            f"and contradicting_evidence_ids):\n<untrusted_evidence_payload>\n"
            f"{sanitized_evidence_json}\n</untrusted_evidence_payload>"
        )
        analyzer_block = (
            "Analyzer Summaries:\n<untrusted_analyzer_payload>\n"
            f"{sanitized_analyzers_json}\n</untrusted_analyzer_payload>"
        )
        prompt_parts = [
            f"<untrusted_dispute_context>\n{sanitized_dispute_json}\n</untrusted_dispute_context>",
            f"Evidence count: {len(evidence)}",
            evidence_block,
            f"Analyzer count: {len(analyzers)}",
            analyzer_block,
            f"Failed tools:\n{self._failure_note(failed_tools)}",
            f"Failed analyzers:\n{self._failure_note(failed_analyzers)}",
        ]
        sanitized_guidance: str | None = None
        if reviewer_guidance:
            sanitized_guidance, _ = redact_text(reviewer_guidance)
            prompt_parts.append(f"Reviewer Steering Guidance:\n{sanitized_guidance}")
        prompt = "\n".join(prompt_parts)
        llm_result: (
            LLMCallResult[InvestigatorIteration] | None
        ) = await self.gateway.generate_structured(
            system_prompt=investigator_system,
            user_prompt=f"{investigator_iteration}\n\n{prompt}",
            schema=InvestigatorIteration,
            prompt_template_id=PROMPT_TEMPLATE_ID,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
            prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
            on_delta=on_delta,
        )
        if llm_result is not None:
            return llm_result.value, llm_result
        return self._heuristic_iteration(
            dispute=dispute,
            evidence=evidence,
            analyzers=analyzers,
            failed_tools=failed_tools,
            failed_analyzers=failed_analyzers,
            reviewer_guidance=sanitized_guidance,
        ), None

    def _heuristic_iteration(
        self,
        *,
        dispute: DisputeDetail,
        evidence: list[Evidence],
        analyzers: list[AnalyzerSummary],
        failed_tools: list[dict[str, str]],
        failed_analyzers: list[dict[str, str]],
        reviewer_guidance: str | None = None,
    ) -> InvestigatorIteration:
        categories = {item.category for item in evidence}
        failed_tool_names = {item["name"] for item in failed_tools}
        failed_analyzer_names = {item["name"] for item in failed_analyzers}
        tool_requests: list[ToolRequest] = []
        analyzer_requests: list[AnalyzerRequest] = []
        questions = [
            f"{item['name']} data is unavailable: {item['error']}"
            for item in failed_tools + failed_analyzers
            if item.get("error")
        ]
        for name, category, reason in TOOL_REQUESTS:
            if category in categories or name in failed_tool_names:
                continue
            tool_requests.append(ToolRequest(name=name, reason=reason))
        if categories == {"transaction", "customer", "device", "merchant"} and not analyzers:
            for name, reason in DEFAULT_ANALYZERS:
                if name in failed_analyzer_names:
                    continue
                analyzer_requests.append(AnalyzerRequest(name=name, reason=reason))
        device = next((item for item in evidence if item.category == "device"), None)
        transaction = next((item for item in evidence if item.category == "transaction"), None)
        customer = next((item for item in evidence if item.category == "customer"), None)
        supporting: list[str] = []
        contradicting: list[str] = []
        statement = "The dispute may represent a legitimate transaction with weak fraud indicators."
        confidence = 0.45
        if transaction:
            supporting.append(transaction.id)
            if transaction.facts.get("geo_anomaly"):
                statement = "The dispute may be fraudulent due to anomalous transaction activity."
                confidence = 0.62
        if device:
            supporting.append(device.id)
            if device.facts.get("recognized_device") is False:
                statement = "The dispute may reflect account takeover behavior."
                confidence = 0.72
        if customer and customer.facts.get("prior_fraud_signals"):
            supporting.append(customer.id)
            confidence = min(confidence + 0.12, 0.92)
        if (
            customer
            and customer.facts.get("tenure_years", 0) > 3
            and customer.facts.get("prior_fraud_signals", 0) == 0
            and confidence >= 0.60
        ):
            contradicting.append(customer.id)
            questions.append(
                "Why does the transaction look risky despite a stable customer history?"
            )
        if customer and customer.facts.get("prior_disputes", 0) > 1:
            questions.append(
                "Customer has multiple prior disputes; requires manual triage of dispute grounds."
            )
        if analyzers and any(item.contradictions for item in analyzers):
            questions.append(
                "How should contradictory analyzer findings affect the recommendation?"
            )
        reasoning_steps: list[str] = [
            f"Assessed {len(evidence)} evidence records across available channels.",
            f"Evaluated hypothesis: '{statement}' (confidence: {int(confidence * 100)}%).",
        ]
        if supporting:
            reasoning_steps.append(f"Found {len(supporting)} supporting evidence factors.")
        if contradicting:
            reasoning_steps.append(
                f"Identified {len(contradicting)} contradicting factors: "
                "customer history stability vs activity risk."
            )
        if reviewer_guidance:
            reasoning_steps.append(f"Incorporated reviewer steering guidance: {reviewer_guidance}")
            statement = f"{statement} Steering guidance applied: {reviewer_guidance}."
        thought_process = " ".join(reasoning_steps)

        return InvestigatorIteration(
            summary=(
                f"Investigated dispute {dispute.case_code} with {len(evidence)} evidence items."
            ),
            thought_process=thought_process,
            reasoning_steps=reasoning_steps,
            hypotheses=[
                InvestigationHypothesis(
                    statement=statement,
                    confidence=confidence,
                    supporting_evidence_ids=supporting,
                    contradicting_evidence_ids=contradicting,
                )
            ],
            unresolved_questions=questions,
            tool_requests=tool_requests,
            analyzer_requests=analyzer_requests,
            should_finish=not tool_requests and not analyzer_requests,
        )

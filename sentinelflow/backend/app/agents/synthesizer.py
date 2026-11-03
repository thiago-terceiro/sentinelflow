from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.graph.prompts import evidence_synthesis, final_recommendation, investigator_system
from app.schemas.investigation import (
    ComplianceFinding,
    InvestigationHypothesis,
    InvestigationReport,
    Recommendation,
    RiskAssessment,
)
from app.services.model_gateway import LLMCallResult, ModelGateway
from app.services.trace_safety import sha256_text
from pydantic import BaseModel

PROMPT_TEMPLATE_ID = "synthesis_recommendation"
PROMPT_TEMPLATE_VERSION = "2026-09-02"
PROMPT_TEMPLATE_SHA256 = sha256_text(
    f"{investigator_system}\n{evidence_synthesis}\n{final_recommendation}"
)


class SynthesisOutput(BaseModel):
    conclusion: str
    recommendation: Recommendation
    confidence: float


class SynthesizerAgent:
    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    async def build_report(
        self,
        *,
        hypotheses: list[InvestigationHypothesis],
        risk: RiskAssessment,
        compliance: list[ComplianceFinding],
        evidence_ids: list[str],
        unresolved_questions: list[str],
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[InvestigationReport, LLMCallResult[SynthesisOutput] | None]:
        serialized_hypotheses = [item.model_dump(mode="json") for item in hypotheses]
        prompt = (
            f"Hypotheses ({len(hypotheses)}):\n{json.dumps(serialized_hypotheses, indent=2)}\n"
            f"Available Evidence IDs: {json.dumps(evidence_ids)}\n"
            f"Unresolved Questions: {json.dumps(unresolved_questions)}\n"
            f"Risk: {risk.model_dump_json(indent=2)}\n"
            f"Compliance: {[item.model_dump(mode='json') for item in compliance]}"
        )
        llm_result = await self.gateway.generate_structured(
            system_prompt=investigator_system,
            user_prompt=f"{evidence_synthesis}\n{final_recommendation}\n\n{prompt}",
            schema=SynthesisOutput,
            prompt_template_id=PROMPT_TEMPLATE_ID,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
            prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
            on_delta=on_delta,
        )
        if llm_result is None:
            recommendation: Recommendation
            if risk.score >= 0.65 or risk.threshold_triggered:
                recommendation = "deny"
            elif risk.score >= 0.40:
                recommendation = "escalate"
            else:
                recommendation = "approve"
            if unresolved_questions:
                recommendation = "escalate" if recommendation == "approve" else recommendation
            conclusion = (
                "Evidence supports approval."
                if recommendation == "approve"
                else (
                    "Evidence indicates elevated risk requiring denial."
                    if recommendation == "deny"
                    else "Evidence requires further escalation and scrutiny."
                )
            )
            confidence = min(0.92, max(0.35, risk.score))
            settings = getattr(self.gateway, "settings", None)
            if settings is not None and getattr(settings, "APP_ENV", "development") != "production":
                if on_delta is not None:
                    await on_delta(
                        f"Synthesized recommendation: {recommendation.upper()} "
                        f"({int(confidence * 100)}% confidence)"
                    )
                synthesis_out = SynthesisOutput(
                    conclusion=conclusion,
                    recommendation=recommendation,
                    confidence=confidence,
                )
                llm_meta: LLMCallResult[SynthesisOutput] | None = LLMCallResult[SynthesisOutput](
                    value=synthesis_out,
                    provider=settings.MODEL_PROVIDER,
                    model_used=settings.MODEL_NAME,
                    deployment_id=settings.MODEL_DEPLOYMENT_ID,
                    response_id=f"sim_resp_{uuid4().hex[:8]}",
                    prompt_template_id=PROMPT_TEMPLATE_ID,
                    prompt_template_version=PROMPT_TEMPLATE_VERSION,
                    prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
                    input_tokens=len(prompt) // 4 + 48,
                    output_tokens=len(conclusion) // 4 + 60,
                    reasoning_tokens=45,
                    latency_ms=130.0,
                    prompt_text=prompt,
                    output_text=synthesis_out.model_dump_json(indent=2),
                    reasoning_text=conclusion,
                )
            else:
                llm_meta = None
        else:
            recommendation = llm_result.value.recommendation
            conclusion = llm_result.value.conclusion
            confidence = llm_result.value.confidence
            llm_meta = llm_result
        return InvestigationReport(
            conclusion=conclusion,
            recommendation=recommendation,
            confidence=confidence,
            hypotheses=hypotheses,
            risk_factors=risk.factors,
            evidence_ids=evidence_ids,
            unresolved_questions=unresolved_questions,
            compliance_findings=[item.rule_id for item in compliance if not item.passed],
        ), llm_meta

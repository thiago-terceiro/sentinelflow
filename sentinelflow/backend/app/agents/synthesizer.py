from __future__ import annotations

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
    ) -> tuple[InvestigationReport, LLMCallResult[SynthesisOutput] | None]:
        prompt = (
            f"Hypotheses: {len(hypotheses)}\n"
            f"Risk: {risk.model_dump_json(indent=2)}\n"
            f"Compliance: {[item.model_dump() for item in compliance]}"
        )
        llm_result = await self.gateway.generate_structured(
            system_prompt=investigator_system,
            user_prompt=f"{evidence_synthesis}\n{final_recommendation}\n\n{prompt}",
            schema=SynthesisOutput,
            prompt_template_id=PROMPT_TEMPLATE_ID,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
            prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
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
            llm_meta: LLMCallResult[SynthesisOutput] | None = None
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

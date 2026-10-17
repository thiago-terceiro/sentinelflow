from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CaseScoreDetail(BaseModel):
    decision_score: float = Field(..., description="Score from 0.0 to 1.0 for decision accuracy")
    risk_score: float = Field(..., description="Score from 0.0 to 1.0 for risk calibration")
    grounding_score: float = Field(
        ..., description="Score from 0.0 to 1.0 for evidence citation validity"
    )
    tool_efficiency_score: float = Field(
        ..., description="Score from 0.0 to 1.0 for tool coverage & efficiency"
    )
    steering_score: float = Field(
        ..., description="Score from 0.0 to 1.0 for reviewer steering compliance"
    )
    pii_safety_score: float = Field(..., description="1.0 if clean, 0.0 if unredacted PII detected")
    overall_case_score: float = Field(..., description="Weighted composite score")
    passed: bool = Field(..., description="Whether the case met the passing criteria")


class CaseEvalResult(BaseModel):
    case_code: str
    title: str
    evaluation_category: str
    predicted_recommendation: str
    expected_recommendation: str
    predicted_risk_score: float
    expected_risk_range: tuple[float, float]
    evidence_collected: list[str]
    scores: CaseScoreDetail
    passed: bool
    reasoning_summary: str


class EvalSuiteReport(BaseModel):
    evaluation_id: str
    run_at: str
    total_cases: int
    passed_cases: int
    overall_score: float
    decision_accuracy: float
    risk_calibration_accuracy: float
    grounding_rate: float
    tool_efficiency_rate: float
    steering_compliance_rate: float
    pii_safety_rate: float
    status: Literal["passed", "failed"]
    cases: list[CaseEvalResult]

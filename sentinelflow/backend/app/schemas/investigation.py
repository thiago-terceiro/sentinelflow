from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

EvidenceCategory = Literal[
    "transaction",
    "customer",
    "device",
    "network",
    "merchant",
    "compliance",
    "analyzer",
]
EvidenceOrigin = Literal[
    "observed_fact",
    "agent_inference",
    "analyzer_interpretation",
]

Recommendation = Literal["approve", "deny", "escalate", "insufficient_evidence"]
RiskLevel = Literal["low", "medium", "high", "critical"]
InvestigationStatus = Literal[
    "pending",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
]


class Evidence(BaseModel):
    id: str
    source: str
    category: EvidenceCategory
    origin: EvidenceOrigin = "observed_fact"
    summary: str
    facts: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    collected_at: datetime
    provenance: str


class AnalyzerSummary(BaseModel):
    analyzer: str
    origin: EvidenceOrigin = "analyzer_interpretation"
    summary: str
    findings: list[str]
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str]
    contradictions: list[str]
    recommended_followups: list[str]


class RiskFactor(BaseModel):
    name: str
    score: float
    weight: float
    explanation: str
    evidence_ids: list[str]


class RiskAssessment(BaseModel):
    score: float = Field(ge=0, le=1)
    level: RiskLevel
    factors: list[RiskFactor]
    threshold_triggered: bool
    explanation: str


class ComplianceFinding(BaseModel):
    framework: str
    rule_id: str
    passed: bool
    requires_review: bool
    explanation: str
    evidence_ids: list[str]
    policy_version: str


class InvestigationHypothesis(BaseModel):
    statement: str
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]


class InvestigationReport(BaseModel):
    conclusion: str
    recommendation: Recommendation
    confidence: float = Field(ge=0, le=1)
    hypotheses: list[InvestigationHypothesis]
    risk_factors: list[RiskFactor]
    evidence_ids: list[str]
    unresolved_questions: list[str]
    compliance_findings: list[str]


class InvestigationBudget(BaseModel):
    max_iterations: int
    max_tool_calls: int
    max_analyzer_calls: int
    max_tokens: int
    max_seconds: int


class InvestigationRun(BaseModel):
    id: str
    dispute_id: str
    thread_id: str
    status: InvestigationStatus
    created_at: datetime
    updated_at: datetime
    budget: InvestigationBudget
    risk_assessment: RiskAssessment | None = None
    compliance_findings: list[ComplianceFinding] = Field(
        default_factory=lambda: cast(list[ComplianceFinding], [])
    )
    report: InvestigationReport | None = None


class InvestigationListItem(BaseModel):
    id: str
    dispute_id: str
    thread_id: str
    status: InvestigationStatus
    updated_at: datetime

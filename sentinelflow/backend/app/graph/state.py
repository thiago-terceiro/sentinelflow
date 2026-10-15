from __future__ import annotations

from typing import Annotated, Any, TypedDict

from app.schemas.disputes import DisputeDetail
from app.schemas.investigation import (
    AnalyzerSummary,
    ComplianceFinding,
    Evidence,
    InvestigationHypothesis,
    InvestigationReport,
    RiskAssessment,
)
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages  # pyright: ignore[reportMissingTypeStubs]


class DisputeState(TypedDict):
    dispute_id: str
    investigation_id: str
    thread_id: str
    principal_id: str
    principal_roles: list[str]
    dispute: DisputeDetail | None
    messages: Annotated[list[BaseMessage], add_messages]
    evidence: list[Evidence]
    analyzer_summaries: list[AnalyzerSummary]
    hypotheses: list[InvestigationHypothesis]
    unresolved_questions: list[str]
    risk_assessment: RiskAssessment | None
    compliance_findings: list[ComplianceFinding]
    investigation_report: InvestigationReport | None
    iteration_count: int
    tool_call_count: int
    analyzer_call_count: int
    status: str
    pending_tools: list[dict[str, str]]
    pending_analyzers: list[dict[str, str]]
    failed_tools: list[dict[str, str]]
    failed_analyzers: list[dict[str, str]]
    timeline_events: list[dict[str, Any]]
    approval_request: dict[str, Any] | None
    approval_decision: dict[str, Any] | None
    reviewer_guidance: str | None
    revision_count: int
    checkpoint_ref: str | None

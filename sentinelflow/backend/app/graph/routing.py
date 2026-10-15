from __future__ import annotations

from app.config import get_settings
from app.graph.state import DisputeState

MAX_REVISION_CYCLES = 3


def route_after_investigator(state: DisputeState) -> str:
    settings = get_settings()
    if state.get("pending_tools") or state.get("pending_analyzers"):
        return "collect"
    revisions = state.get("revision_count", 0)
    max_iterations = (revisions + 1) * settings.INVESTIGATION_MAX_ITERATIONS
    if state["iteration_count"] >= max_iterations:
        return "synthesize"
    return "synthesize"


def route_after_recommendation(state: DisputeState) -> str:
    report = state["investigation_report"]
    risk = state["risk_assessment"]
    if report is None or risk is None:
        return "finalize"
    if report.recommendation == "escalate" or risk.threshold_triggered:
        return "approval"
    return "finalize"


def route_after_approval(state: DisputeState) -> str:
    decision = state.get("approval_decision") or {}
    action = decision.get("decision")
    if action == "request_revision":
        if state.get("revision_count", 0) >= MAX_REVISION_CYCLES:
            return "finalize"
        return "investigate"
    return "finalize"

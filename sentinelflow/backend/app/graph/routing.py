from __future__ import annotations

from app.config import get_settings
from app.graph.state import DisputeState


def route_after_investigator(state: DisputeState) -> str:
    settings = get_settings()
    if state["iteration_count"] >= settings.INVESTIGATION_MAX_ITERATIONS:
        return "synthesize"
    if state["pending_tools"] or state["pending_analyzers"]:
        return "collect"
    return "synthesize"


def route_after_recommendation(state: DisputeState) -> str:
    report = state["investigation_report"]
    risk = state["risk_assessment"]
    if report is None or risk is None:
        return "finalize"
    if report.recommendation == "escalate" or risk.threshold_triggered:
        return "approval"
    return "finalize"

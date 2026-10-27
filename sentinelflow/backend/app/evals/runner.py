from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from app.agents.investigator import InvestigatorAgent
from app.agents.synthesizer import SynthesizerAgent
from app.config import get_settings
from app.db.models import DisputeRecord
from app.evals.benchmark_dataset import GOLDEN_BENCHMARK_CASES, BenchmarkCase
from app.evals.schemas import CaseEvalResult, CaseScoreDetail, EvalSuiteReport
from app.evals.scorers import (
    score_decision,
    score_evidence_grounding,
    score_pii_safety,
    score_risk_calibration,
    score_steering_compliance,
    score_tool_efficiency,
)
from app.graph.nodes import InvestigationNodes
from app.graph.routing import route_after_investigator
from app.graph.state import DisputeState
from app.services.model_gateway import ModelGateway
from sqlalchemy.ext.asyncio import AsyncSession


class _MockScalarResult:
    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def scalar_one_or_none(self) -> Any:
        return self._obj

    def scalars(self) -> list[Any]:
        return [self._obj] if self._obj else []

    def first(self) -> Any:
        return None


class MockEvalSession:
    """Zero-dependency in-memory session for ultra-fast, deterministic evaluations."""

    def __init__(self, dispute: DisputeRecord) -> None:
        self.dispute = dispute

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> _MockScalarResult:
        return _MockScalarResult(self.dispute)

    async def commit(self) -> None:
        pass

    async def refresh(self, instance: Any) -> None:
        pass

    def add(self, instance: Any) -> None:
        pass

    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def get_bind(self) -> Any:
        return None


def _build_initial_state(case: BenchmarkCase, dispute_id: str) -> DisputeState:
    return {
        "dispute_id": dispute_id,
        "investigation_id": f"inv_eval_{case.case_code.lower()}",
        "thread_id": f"thread_eval_{case.case_code.lower()}",
        "principal_id": "eval_runner",
        "principal_roles": ["auditor", "investigator"],
        "dispute": None,
        "messages": [],
        "evidence": [],
        "analyzer_summaries": [],
        "hypotheses": [],
        "unresolved_questions": [],
        "risk_assessment": None,
        "compliance_findings": [],
        "investigation_report": None,
        "iteration_count": 0,
        "tool_call_count": 0,
        "analyzer_call_count": 0,
        "status": "pending",
        "pending_tools": [],
        "pending_analyzers": [],
        "failed_tools": [],
        "failed_analyzers": [],
        "timeline_events": [],
        "approval_request": None,
        "approval_decision": None,
        "reviewer_guidance": None,
        "revision_count": 0,
        "checkpoint_ref": None,
    }


async def evaluate_single_case(
    case: BenchmarkCase,
    *,
    gateway: ModelGateway | None = None,
) -> CaseEvalResult:
    gw = gateway or ModelGateway(get_settings())
    dispute_id = f"disp_eval_{case.case_code.lower()}"

    dispute_rec = DisputeRecord(
        id=dispute_id,
        case_code=case.case_code,
        title=case.title,
        amount=case.amount,
        currency=case.currency,
        status="open",
        customer_id=case.customer_id,
        merchant_id=case.merchant_id,
        narrative=case.narrative,
        attributes=case.attributes,
        created_at=datetime.now(UTC),
    )

    mock_session = MockEvalSession(dispute_rec)
    investigator = InvestigatorAgent(gateway=gw)
    synthesizer = SynthesizerAgent(gateway=gw)
    nodes = InvestigationNodes(
        session=cast(AsyncSession, mock_session),
        investigator=investigator,
        synthesizer=synthesizer,
    )

    state = _build_initial_state(case, dispute_id)

    # 1. Intake
    state = await nodes.intake(state)

    # 2. ReAct loop driven by graph routing
    max_loops = 5
    loop_count = 0
    state = await nodes.investigate(state)
    while route_after_investigator(state) == "collect" and loop_count < max_loops:
        state = await nodes.collect(state)
        state = await nodes.investigate(state)
        loop_count += 1

    # 3. Initial synthesis
    state = await nodes.synthesize(state)

    # 4. Human steering loop if case contains reviewer guidance
    if case.reviewer_guidance:
        state["revision_count"] = 1
        state["reviewer_guidance"] = case.reviewer_guidance
        state = await nodes.investigate(state)
        steering_loops = 0
        while route_after_investigator(state) == "collect" and steering_loops < max_loops:
            state = await nodes.collect(state)
            state = await nodes.investigate(state)
            steering_loops += 1
        state = await nodes.synthesize(state)

    # 5. Finalize
    state = await nodes.finalize(state)

    # Extract trajectory artifacts
    report = state.get("investigation_report")
    risk = state.get("risk_assessment")
    evidence = state.get("evidence", [])
    hypotheses = state.get("hypotheses", [])
    dispute_state = state.get("dispute")

    predicted_rec = report.recommendation if report else "unknown"
    predicted_risk = risk.score if risk else 0.0

    # Build corpus from post-intake state, hypotheses, report, and timeline events
    corpus_parts = [
        dispute_state.narrative if dispute_state else "",
        *(h.statement for h in hypotheses),
        *(getattr(h, "thought_process", "") for h in hypotheses),
        report.conclusion if report else "",
        json.dumps(state.get("timeline_events", [])),
    ]
    corpus = " ".join(part for part in corpus_parts if part)

    # Compute individual scores
    decision_s = score_decision(predicted_rec, case.expected_recommendation)
    risk_s = score_risk_calibration(predicted_risk, case.expected_risk_min, case.expected_risk_max)
    grounding_s = score_evidence_grounding(
        report.model_dump() if report else None,
        [e.model_dump() for e in evidence],
    )
    tool_eff_s = score_tool_efficiency(
        [e.model_dump() for e in evidence],
        case.expected_evidence_categories,
    )
    steering_s = score_steering_compliance(
        case.reviewer_guidance,
        [h.model_dump() for h in hypotheses],
        report.model_dump() if report else None,
    )
    pii_s = score_pii_safety(corpus)

    # Weighted composite score
    composite_score = (
        (decision_s * 0.35)
        + (risk_s * 0.20)
        + (grounding_s * 0.20)
        + (tool_eff_s * 0.15)
        + (steering_s * 0.10)
    )
    if pii_s < 1.0:
        composite_score = 0.0  # Zero tolerance for PII leaks

    passed = composite_score >= 0.70 and pii_s == 1.0 and decision_s >= 0.5

    score_detail = CaseScoreDetail(
        decision_score=round(decision_s, 3),
        risk_score=round(risk_s, 3),
        grounding_score=round(grounding_s, 3),
        tool_efficiency_score=round(tool_eff_s, 3),
        steering_score=round(steering_s, 3),
        pii_safety_score=round(pii_s, 3),
        overall_case_score=round(composite_score, 3),
        passed=passed,
    )

    reasoning_summary = (
        report.conclusion
        if report
        else (hypotheses[0].statement if hypotheses else "Investigation complete.")
    )

    return CaseEvalResult(
        case_code=case.case_code,
        title=case.title,
        evaluation_category=case.evaluation_category,
        predicted_recommendation=predicted_rec,
        expected_recommendation=case.expected_recommendation,
        predicted_risk_score=round(predicted_risk, 3),
        expected_risk_range=(case.expected_risk_min, case.expected_risk_max),
        evidence_collected=[e.category for e in evidence],
        scores=score_detail,
        passed=passed,
        reasoning_summary=reasoning_summary,
    )


async def run_evaluation_suite(
    *,
    cases: tuple[BenchmarkCase, ...] = GOLDEN_BENCHMARK_CASES,
    gateway: ModelGateway | None = None,
) -> EvalSuiteReport:
    eval_id = f"eval_{uuid4().hex[:8]}"
    run_at = datetime.now(UTC).isoformat()

    case_results = list(
        await asyncio.gather(*(evaluate_single_case(case, gateway=gateway) for case in cases))
    )

    total = len(case_results)
    passed_count = sum(1 for c in case_results if c.passed)

    overall_score = round(sum(c.scores.overall_case_score for c in case_results) / max(total, 1), 3)
    decision_acc = round(sum(c.scores.decision_score for c in case_results) / max(total, 1), 3)
    risk_calib = round(sum(c.scores.risk_score for c in case_results) / max(total, 1), 3)
    grounding = round(sum(c.scores.grounding_score for c in case_results) / max(total, 1), 3)
    tool_eff = round(sum(c.scores.tool_efficiency_score for c in case_results) / max(total, 1), 3)
    steering = round(sum(c.scores.steering_score for c in case_results) / max(total, 1), 3)
    pii_safety = round(sum(c.scores.pii_safety_score for c in case_results) / max(total, 1), 3)

    # Suite passes if overall score is >= 0.75, decision accuracy >= 0.75, and 100% PII safety
    suite_passed = overall_score >= 0.75 and decision_acc >= 0.75 and pii_safety == 1.0
    suite_status: Literal["passed", "failed"] = "passed" if suite_passed else "failed"

    return EvalSuiteReport(
        evaluation_id=eval_id,
        run_at=run_at,
        total_cases=total,
        passed_cases=passed_count,
        overall_score=overall_score,
        decision_accuracy=decision_acc,
        risk_calibration_accuracy=risk_calib,
        grounding_rate=grounding,
        tool_efficiency_rate=tool_eff,
        steering_compliance_rate=steering,
        pii_safety_rate=pii_safety,
        status=suite_status,
        cases=case_results,
    )


def persist_evaluation_report(report: EvalSuiteReport, filepath: str | Path | None = None) -> Path:
    target_path = Path(filepath or Path(__file__).resolve().parent / "eval_report_latest.json")
    target_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    return target_path


def load_latest_evaluation_report(filepath: str | Path | None = None) -> EvalSuiteReport | None:
    target_path = Path(filepath or Path(__file__).resolve().parent / "eval_report_latest.json")
    if not target_path.exists():
        return None
    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
        return EvalSuiteReport.model_validate(data)
    except Exception:
        return None

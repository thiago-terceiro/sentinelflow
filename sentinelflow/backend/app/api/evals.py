from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import PrincipalDep
from app.evals.runner import (
    load_latest_evaluation_report,
    persist_evaluation_report,
    run_evaluation_suite,
)
from app.evals.schemas import EvalSuiteReport
from app.security import Role

router = APIRouter(prefix="/evals", tags=["evaluations"])


@router.get("/latest", response_model=EvalSuiteReport)
async def get_latest_evaluation(principal: PrincipalDep) -> EvalSuiteReport:
    """Retrieve the most recent AI evaluation benchmark scorecard."""
    principal.require_any(
        Role.AUDITOR,
        Role.ADMIN,
        Role.INVESTIGATOR,
        Role.SENIOR_INVESTIGATOR,
        Role.REVIEWER,
    )
    report = load_latest_evaluation_report()
    if report is None:
        report = await run_evaluation_suite()
        persist_evaluation_report(report)
    return report


@router.post("/run", response_model=EvalSuiteReport)
async def trigger_evaluation_run(principal: PrincipalDep) -> EvalSuiteReport:
    """Trigger an on-demand AI evaluation benchmark run across golden test cases."""
    principal.require_any(
        Role.AUDITOR,
        Role.ADMIN,
        Role.INVESTIGATOR,
        Role.SENIOR_INVESTIGATOR,
    )
    report = await run_evaluation_suite()
    persist_evaluation_report(report)
    return report

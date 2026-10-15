from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.api.deps import DBSessionDep, PrincipalDep
from app.db.models import InvestigationRecord
from app.errors import AppError, NotFoundError
from app.schemas.approval import ApprovalDecision, ApprovalRecord
from app.schemas.investigation import InvestigationRun
from app.security import Role
from app.services.audit import record_audit_event
from app.services.investigations import schedule_resume, to_run

router = APIRouter(tags=["approvals"])


@router.post("/investigations/{investigation_id}/resume", response_model=InvestigationRun)
async def resume_investigation(
    investigation_id: str,
    decision: ApprovalDecision,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> InvestigationRun:
    principal.require_any(Role.REVIEWER, Role.ADMIN)
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    if record.status != "awaiting_approval":
        raise AppError(
            code="INVESTIGATION_NOT_AWAITING_APPROVAL",
            message="Investigation is not awaiting approval.",
            status_code=409,
        )
    scheduled = await schedule_resume(record.id, decision.model_dump())
    if not scheduled:
        raise AppError(
            code="INVESTIGATION_ALREADY_RUNNING",
            message="Investigation is already running.",
            status_code=409,
        )
    record.status = "running"
    await session.commit()
    await session.refresh(record)
    approval_record = ApprovalRecord(
        user_id=principal.user_id,
        role=sorted(role.value for role in principal.roles)[0],
        decision=decision.decision,
        comment=decision.comment,
        guidance=decision.guidance,
        timestamp=datetime.now(UTC),
        dispute_id=record.dispute_id,
        investigation_id=record.id,
        risk_score=_risk_score(record.risk_assessment),
        recommendation_version="v1",
        checkpoint_id=record.checkpoint_id or record.thread_id,
    )
    await record_audit_event(
        session,
        actor=principal,
        event_name="investigation.approval_recorded",
        payload=approval_record.model_dump(mode="json"),
        dispute_id=record.dispute_id,
        investigation_id=record.id,
    )
    return to_run(record)


def _risk_score(risk_assessment: dict[str, Any] | None) -> float:
    if risk_assessment is None:
        return 0.0
    score = risk_assessment.get("score", 0.0)
    return float(score) if isinstance(score, int | float | str) else 0.0

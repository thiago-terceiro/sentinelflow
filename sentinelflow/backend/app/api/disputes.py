from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DBSessionDep, PrincipalDep
from app.db.models import DisputeRecord, InvestigationRecord
from app.errors import AppError, NotFoundError
from app.schemas.audit import (
    AuditArtifactResponse,
    AuditCorrectionRequest,
    AuditCorrectionResponse,
    AuditIntegrityResponse,
)
from app.schemas.disputes import DisputeCreateRequest, DisputeDetail, DisputeStatus, DisputeSummary
from app.schemas.investigation import InvestigationRun
from app.security import Role
from app.services.audit import (
    create_audit_correction,
    get_raw_audit_artifact,
    list_audit_records,
    project_payload_for_roles,
    record_audit_event,
    verify_audit_integrity,
)
from app.services.investigations import (
    PrincipalContext,
    schedule_investigation,
    stream_graph_events,
    to_run,
)

router = APIRouter(tags=["disputes", "investigations"])


@router.get("/disputes", response_model=list[DisputeSummary])
async def list_disputes(
    session: DBSessionDep,
    principal: PrincipalDep,
) -> list[DisputeSummary]:
    principal.require_any(Role.INVESTIGATOR, Role.SENIOR_INVESTIGATOR, Role.REVIEWER, Role.ADMIN)
    result = await session.execute(select(DisputeRecord).order_by(DisputeRecord.created_at.desc()))
    return [
        DisputeSummary(
            id=item.id,
            case_code=item.case_code,
            title=item.title,
            amount=item.amount,
            currency=item.currency,
            status=cast(DisputeStatus, item.status),
            created_at=item.created_at,
        )
        for item in result.scalars()
    ]


@router.post("/disputes", response_model=DisputeDetail)
async def create_dispute(
    request: DisputeCreateRequest,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> DisputeDetail:
    principal.require_any(Role.REVIEWER, Role.ADMIN)
    dispute = DisputeRecord(
        case_code=request.case_code or f"SF-{uuid4().hex[:8].upper()}",
        title=request.title,
        narrative=request.narrative,
        customer_id=request.customer_id,
        merchant_id=request.merchant_id,
        amount=request.amount,
        currency=request.currency,
        status=request.status,
        attributes=request.attributes,
    )
    session.add(dispute)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            code="DUPLICATE_CASE_CODE",
            message="A dispute with the same case code already exists.",
            status_code=409,
        ) from exc
    await session.refresh(dispute)
    return DisputeDetail(
        id=dispute.id,
        case_code=dispute.case_code,
        title=dispute.title,
        amount=dispute.amount,
        currency=dispute.currency,
        status=cast(DisputeStatus, dispute.status),
        created_at=dispute.created_at,
        customer_id=dispute.customer_id,
        merchant_id=dispute.merchant_id,
        narrative=dispute.narrative,
        tags=list(dispute.attributes.get("tags", [])),
    )


@router.post("/disputes/{dispute_id}/investigations", response_model=InvestigationRun)
async def start_investigation(
    dispute_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> InvestigationRun:
    principal.require_any(Role.INVESTIGATOR, Role.SENIOR_INVESTIGATOR, Role.ADMIN)
    dispute = await session.get(DisputeRecord, dispute_id)
    if dispute is None:
        raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
    record = InvestigationRecord(
        dispute_id=dispute_id,
        thread_id=f"thread_{uuid4().hex[:12]}",
        status="pending",
        created_by=principal.user_id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    await record_audit_event(
        session,
        actor=principal,
        event_name="investigation.started",
        payload={"investigation_id": record.id, "status": record.status},
        dispute_id=dispute_id,
        investigation_id=record.id,
    )
    scheduled = await schedule_investigation(record.id, PrincipalContext.from_principal(principal))
    if not scheduled:
        raise AppError(
            code="INVESTIGATION_ALREADY_RUNNING",
            message="Investigation is already running.",
            status_code=409,
        )
    record.status = "running"
    await session.commit()
    await session.refresh(record)
    return to_run(record)


@router.get("/investigations/{investigation_id}", response_model=InvestigationRun)
async def get_investigation(
    investigation_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> InvestigationRun:
    principal.require_any(Role.INVESTIGATOR, Role.SENIOR_INVESTIGATOR, Role.REVIEWER, Role.ADMIN)
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    return to_run(record)


@router.get("/investigations/{investigation_id}/evidence")
async def get_evidence(
    investigation_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    principal.require_any(Role.INVESTIGATOR, Role.SENIOR_INVESTIGATOR, Role.REVIEWER, Role.ADMIN)
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    return record.evidence


@router.get("/investigations/{investigation_id}/audit")
async def get_audit(
    investigation_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    principal.require_any(Role.SENIOR_INVESTIGATOR, Role.REVIEWER, Role.AUDITOR, Role.ADMIN)
    records = await list_audit_records(session, investigation_id)
    return [
        {
            "id": item.id,
            "event_name": item.event_name,
            "payload": project_payload_for_roles(item.payload, principal.roles),
            "actor_id": item.actor_id,
            "actor_role": item.actor_role,
            "created_at": item.created_at,
        }
        for item in records
    ]


@router.get(
    "/investigations/{investigation_id}/audit/integrity",
    response_model=AuditIntegrityResponse,
)
async def get_audit_integrity(
    investigation_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> AuditIntegrityResponse:
    principal.require_any(Role.AUDITOR, Role.ADMIN)
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    result = await verify_audit_integrity(session, investigation_id)
    return AuditIntegrityResponse(
        investigation_id=result.investigation_id,
        valid=result.valid,
        checked_records=result.checked_records,
        broken_sequence=result.broken_sequence,
        issue_code=result.issue_code,
        message=result.message,
        expected_prev_hash=result.expected_prev_hash,
        actual_prev_hash=result.actual_prev_hash,
        expected_row_hash=result.expected_row_hash,
        actual_row_hash=result.actual_row_hash,
    )


@router.post(
    "/investigations/{investigation_id}/audit/corrections",
    response_model=AuditCorrectionResponse,
)
async def create_audit_correction_event(
    investigation_id: str,
    request: AuditCorrectionRequest,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> AuditCorrectionResponse:
    principal.require_any(Role.AUDITOR, Role.ADMIN)
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    correction = await create_audit_correction(
        session,
        actor=principal,
        investigation_id=investigation_id,
        supersedes_event_id=request.supersedes_event_id,
        reason_code=request.reason_code,
        note=request.note,
    )
    return AuditCorrectionResponse(
        id=correction.id,
        event_name=correction.event_name,
        payload=correction.payload,
        created_at=correction.created_at,
    )


@router.get(
    "/investigations/{investigation_id}/audit/artifacts/{artifact_id}",
    response_model=AuditArtifactResponse,
)
async def get_audit_artifact(
    investigation_id: str,
    artifact_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> AuditArtifactResponse:
    principal.require_any(Role.AUDITOR, Role.ADMIN)
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    artifact = await get_raw_audit_artifact(
        session,
        actor=principal,
        investigation_id=investigation_id,
        artifact_id=artifact_id,
    )
    return AuditArtifactResponse(
        artifact_id=artifact["artifact_id"],
        audit_record_id=artifact["audit_record_id"],
        key_id=artifact["key_id"],
        payload=artifact["payload"],
    )


@router.get("/investigations/{investigation_id}/stream")
async def stream_investigation(
    investigation_id: str,
    principal: PrincipalDep,
) -> StreamingResponse:
    principal.require_any(Role.INVESTIGATOR, Role.SENIOR_INVESTIGATOR, Role.REVIEWER, Role.ADMIN)
    return StreamingResponse(
        stream_graph_events(investigation_id),
        media_type="text/event-stream",
    )

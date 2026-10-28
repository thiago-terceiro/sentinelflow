from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, Request, Response
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
    AuditRecordItem,
)
from app.schemas.disputes import DisputeCreateRequest, DisputeDetail, DisputeStatus, DisputeSummary
from app.schemas.investigation import Evidence, InvestigationRun
from app.security import Role
from app.services.audit import (
    create_audit_correction,
    get_raw_audit_artifact,
    list_audit_records,
    project_payload_for_roles,
    query_audit_records,
    record_audit_event,
    verify_audit_integrity,
)
from app.services.investigations import (
    PrincipalContext,
    schedule_investigation,
    stream_graph_events,
    to_run,
)
from app.services.tuning_export import export_tuning_dataset, serialize_samples_to_jsonl

router = APIRouter(tags=["disputes", "investigations"])


@router.get("/disputes", response_model=list[DisputeSummary])
async def list_disputes(
    session: DBSessionDep,
    principal: PrincipalDep,
    request: Request,
) -> Any:
    principal.require_any(
        Role.INVESTIGATOR,
        Role.SENIOR_INVESTIGATOR,
        Role.REVIEWER,
        Role.AUDITOR,
        Role.ADMIN,
    )
    result = await session.execute(select(DisputeRecord).order_by(DisputeRecord.created_at.desc()))
    items = [
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
    if "text/markdown" in request.headers.get("accept", ""):
        lines = [
            "# SentinelFlow Disputes",
            "",
            "| ID | Code | Title | Amount | Status | Created At |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for it in items:
            lines.append(
                f"| {it.id} | {it.case_code} | {it.title} | {it.amount} {it.currency} | "
                f"{it.status} | {it.created_at.isoformat()} |"
            )
        return Response(
            content="\n".join(lines),
            media_type="text/markdown; charset=utf-8",
            headers={"Vary": "Accept"},
        )
    return items


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


@router.get(
    "/disputes/{dispute_id}/investigations/latest",
    response_model=InvestigationRun | None,
)
async def get_latest_dispute_investigation(
    dispute_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> InvestigationRun | None:
    principal.require_any(
        Role.INVESTIGATOR,
        Role.SENIOR_INVESTIGATOR,
        Role.REVIEWER,
        Role.AUDITOR,
        Role.ADMIN,
    )
    dispute = await session.get(DisputeRecord, dispute_id)
    if dispute is None:
        raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
    result = await session.execute(
        select(InvestigationRecord)
        .where(InvestigationRecord.dispute_id == dispute_id)
        .order_by(InvestigationRecord.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return to_run(record)


@router.get("/investigations/{investigation_id}", response_model=InvestigationRun)
async def get_investigation(
    investigation_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> InvestigationRun:
    principal.require_any(
        Role.INVESTIGATOR,
        Role.SENIOR_INVESTIGATOR,
        Role.REVIEWER,
        Role.AUDITOR,
        Role.ADMIN,
    )
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    return to_run(record)


@router.get("/investigations/{investigation_id}/evidence", response_model=list[Evidence])
async def get_evidence(
    investigation_id: str,
    session: DBSessionDep,
    principal: PrincipalDep,
) -> list[dict[str, Any]]:
    principal.require_any(
        Role.INVESTIGATOR,
        Role.SENIOR_INVESTIGATOR,
        Role.REVIEWER,
        Role.AUDITOR,
        Role.ADMIN,
    )
    record = await session.get(InvestigationRecord, investigation_id)
    if record is None:
        raise NotFoundError("INVESTIGATION_NOT_FOUND", "Investigation was not found.")
    return record.evidence


@router.get("/audit/records", response_model=list[AuditRecordItem])
async def list_global_audit_records(
    session: DBSessionDep,
    principal: PrincipalDep,
    dispute_id: str | None = None,
    investigation_id: str | None = None,
    event_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    principal.require_any(Role.SENIOR_INVESTIGATOR, Role.REVIEWER, Role.AUDITOR, Role.ADMIN)
    records = await query_audit_records(
        session,
        dispute_id=dispute_id,
        investigation_id=investigation_id,
        event_name=event_name,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": item.id,
            "dispute_id": item.dispute_id,
            "investigation_id": item.investigation_id,
            "event_name": item.event_name,
            "payload": project_payload_for_roles(item.payload, principal.roles),
            "actor_id": item.actor_id,
            "actor_role": item.actor_role,
            "sequence_no": item.sequence_no,
            "prev_hash": item.prev_hash,
            "row_hash": item.row_hash,
            "created_at": item.created_at,
        }
        for item in records
    ]


@router.get("/audit/export/tuning")
async def export_tuning_data(
    session: DBSessionDep,
    principal: PrincipalDep,
    export_type: str = "dpo",
    format: str = "jsonl",
    limit: int = 100,
    min_confidence: float = 0.0,
) -> Response:
    """Exports human-reviewed and auditor-corrected cases for SFT or DPO fine-tuning."""
    principal.require_any(Role.AUDITOR, Role.ADMIN)
    samples = await export_tuning_dataset(
        session,
        export_type=export_type,
        limit=limit,
        min_confidence=min_confidence,
    )
    if format.lower() == "json":
        import json

        return Response(
            content=json.dumps(
                {
                    "total_samples": len(samples),
                    "export_type": export_type,
                    "samples": [s.model_dump() for s in samples],
                },
                indent=2,
            ),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=sentinelflow_{export_type}_dataset.json"
                )
            },
        )

    jsonl_content = serialize_samples_to_jsonl(samples)
    return Response(
        content=jsonl_content,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": (
                f"attachment; filename=sentinelflow_{export_type}_dataset.jsonl"
            )
        },
    )


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
    principal.require_any(
        Role.INVESTIGATOR,
        Role.SENIOR_INVESTIGATOR,
        Role.REVIEWER,
        Role.AUDITOR,
        Role.ADMIN,
    )
    return StreamingResponse(
        stream_graph_events(investigation_id),
        media_type="text/event-stream",
    )

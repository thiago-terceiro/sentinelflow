from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

from app.config import get_settings
from app.db.models import AuditArtifactRecord, AuditRecord
from app.errors import AppError, NotFoundError
from app.security import Principal, Role
from cryptography.fernet import Fernet, InvalidToken
from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AUDITOR_RAW_KEYS = {
    "prompt_redacted",
    "output_redacted",
    "reasoning_redacted",
    "prompt_sha256",
    "output_sha256",
    "reasoning_sha256",
    "redaction_applied",
}
RAW_ARTIFACT_PAYLOAD_KEY = "raw_artifact"


@dataclass(frozen=True, slots=True)
class AuditIntegrityResult:
    investigation_id: str
    valid: bool
    checked_records: int
    broken_sequence: int | None = None
    issue_code: str | None = None
    message: str | None = None
    expected_prev_hash: str | None = None
    actual_prev_hash: str | None = None
    expected_row_hash: str | None = None
    actual_row_hash: str | None = None


def _trace_correlation() -> tuple[str | None, str | None]:
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None, None
    return format(context.trace_id, "032x"), format(context.span_id, "016x")


_investigation_audit_locks: dict[str, asyncio.Lock] = {}
_global_audit_lock = asyncio.Lock()


def _get_audit_lock(investigation_id: str | None) -> asyncio.Lock:
    if not investigation_id:
        return _global_audit_lock
    if investigation_id not in _investigation_audit_locks:
        _investigation_audit_locks[investigation_id] = asyncio.Lock()
    return _investigation_audit_locks[investigation_id]


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )


def _artifact_cipher() -> tuple[Fernet | None, str | None]:
    settings = get_settings()
    if not settings.AUDIT_ARTIFACT_ENCRYPTION_KEY:
        return None, None
    try:
        return (
            Fernet(settings.AUDIT_ARTIFACT_ENCRYPTION_KEY.encode("utf-8")),
            settings.AUDIT_ARTIFACT_KEY_ID,
        )
    except (TypeError, ValueError) as exc:
        raise AppError(
            code="AUDIT_ARTIFACT_KEY_INVALID",
            message="Audit artifact encryption key is invalid.",
            status_code=500,
        ) from exc


def _extract_raw_artifact(payload: dict[str, Any]) -> dict[str, str] | None:
    raw_artifact = payload.get(RAW_ARTIFACT_PAYLOAD_KEY)
    if not isinstance(raw_artifact, dict):
        return None
    raw_artifact_dict = cast(dict[object, object], raw_artifact)
    raw_artifact_map: dict[str, object] = {
        str(key): value for key, value in raw_artifact_dict.items()
    }
    normalized: dict[str, str] = {}
    for key in ("prompt", "output", "reasoning"):
        value = raw_artifact_map.get(key)
        if isinstance(value, str) and value:
            normalized[key] = value
    return normalized or None


def compute_row_hash(
    *,
    investigation_id: str | None,
    dispute_id: str | None,
    sequence_no: int,
    prev_hash: str | None,
    actor_id: str,
    actor_role: str,
    event_name: str,
    payload: dict[str, Any],
) -> str:
    canonical_record: dict[str, Any] = {
        "investigation_id": investigation_id,
        "dispute_id": dispute_id,
        "sequence_no": sequence_no,
        "prev_hash": prev_hash,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "event_name": event_name,
        "payload": json.loads(_canonical_payload(payload)),
    }
    serialized = json.dumps(
        canonical_record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def _next_sequence_and_prev_hash(
    session: AsyncSession,
    investigation_id: str | None,
) -> tuple[int, str | None]:
    if not investigation_id:
        return 1, None
    latest = (
        await session.execute(
            select(AuditRecord.sequence_no, AuditRecord.row_hash)
            .where(AuditRecord.investigation_id == investigation_id)
            .order_by(AuditRecord.sequence_no.desc())
            .limit(1)
        )
    ).first()
    if latest is None:
        return 1, None
    return int(latest[0]) + 1, str(latest[1]) if latest[1] else None


def project_payload_for_roles(payload: dict[str, Any], roles: set[Role]) -> dict[str, Any]:
    if Role.ADMIN in roles:
        return payload
    if Role.AUDITOR in roles:
        return payload
    if Role.REVIEWER in roles:
        return {key: value for key, value in payload.items() if key not in AUDITOR_RAW_KEYS}
    return {
        key: value
        for key, value in payload.items()
        if key
        in {
            "model_used",
            "response_id",
            "iteration",
            "used_heuristic",
            "recommendation",
            "confidence",
        }
    }


async def record_audit_event(
    session: AsyncSession,
    *,
    actor: Principal,
    event_name: str,
    payload: dict[str, Any],
    dispute_id: str | None = None,
    investigation_id: str | None = None,
) -> AuditRecord:
    raw_artifact = _extract_raw_artifact(payload)
    fernet, key_id = _artifact_cipher()
    payload_without_raw = {
        key: value for key, value in payload.items() if key != RAW_ARTIFACT_PAYLOAD_KEY
    }
    artifact_id: str | None = None
    if raw_artifact is not None:
        if fernet is None:
            payload_without_raw["raw_artifact_encrypted"] = False
            payload_without_raw["raw_artifact_unavailable_reason"] = "encryption_not_configured"
        else:
            artifact_id = str(uuid4())
            payload_without_raw["raw_artifact_id"] = artifact_id
            payload_without_raw["raw_artifact_encrypted"] = True
            payload_without_raw["raw_artifact_key_id"] = key_id

    trace_id, span_id = _trace_correlation()
    payload_with_context: dict[str, Any] = {
        **payload_without_raw,
        "trace_id": trace_id,
        "span_id": span_id,
    }
    actor_role = sorted(role.value for role in actor.roles)[0] if actor.roles else "unassigned"

    async with _get_audit_lock(investigation_id):
        sequence_no, prev_hash = await _next_sequence_and_prev_hash(session, investigation_id)
        row_hash = compute_row_hash(
            investigation_id=investigation_id,
            dispute_id=dispute_id,
            sequence_no=sequence_no,
            prev_hash=prev_hash,
            actor_id=actor.user_id,
            actor_role=actor_role,
            event_name=event_name,
            payload=payload_with_context,
        )
        record_id = str(uuid4())
        record = AuditRecord(
            id=record_id,
            actor_id=actor.user_id,
            actor_role=actor_role,
            event_name=event_name,
            payload=payload_with_context,
            dispute_id=dispute_id,
            investigation_id=investigation_id,
            sequence_no=sequence_no,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        session.add(record)
        if raw_artifact is not None and fernet is not None and artifact_id is not None and key_id:
            ciphertext = fernet.encrypt(_canonical_payload(raw_artifact).encode("utf-8")).decode(
                "utf-8"
            )
            session.add(
                AuditArtifactRecord(
                    id=artifact_id,
                    audit_record_id=record_id,
                    investigation_id=investigation_id,
                    dispute_id=dispute_id,
                    key_id=key_id,
                    ciphertext=ciphertext,
                )
            )

        await session.commit()
        await session.refresh(record)
        return record


async def get_raw_audit_artifact(
    session: AsyncSession,
    *,
    actor: Principal,
    investigation_id: str,
    artifact_id: str,
) -> dict[str, Any]:
    artifact = await session.get(AuditArtifactRecord, artifact_id)
    if artifact is None or artifact.investigation_id != investigation_id:
        raise NotFoundError("AUDIT_ARTIFACT_NOT_FOUND", "Audit artifact was not found.")

    fernet, _key_id = _artifact_cipher()
    if fernet is None:
        raise AppError(
            code="AUDIT_ARTIFACT_KEY_UNAVAILABLE",
            message="Audit artifact decryption is unavailable.",
            status_code=503,
        )
    try:
        decrypted = fernet.decrypt(artifact.ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AppError(
            code="AUDIT_ARTIFACT_DECRYPT_FAILED",
            message="Audit artifact decryption failed.",
            status_code=500,
        ) from exc
    payload = json.loads(decrypted)
    if not isinstance(payload, dict):
        raise AppError(
            code="AUDIT_ARTIFACT_INVALID_PAYLOAD",
            message="Audit artifact payload is invalid.",
            status_code=500,
        )

    await record_audit_event(
        session,
        actor=actor,
        event_name="investigation.audit_artifact_read",
        payload={
            "artifact_id": artifact.id,
            "audit_record_id": artifact.audit_record_id,
            "key_id": artifact.key_id,
        },
        dispute_id=artifact.dispute_id,
        investigation_id=investigation_id,
    )
    return {
        "artifact_id": artifact.id,
        "audit_record_id": artifact.audit_record_id,
        "key_id": artifact.key_id,
        "payload": payload,
    }


async def list_audit_records(session: AsyncSession, investigation_id: str) -> list[AuditRecord]:
    result = await session.execute(
        select(AuditRecord)
        .where(AuditRecord.investigation_id == investigation_id)
        .order_by(AuditRecord.sequence_no.asc(), AuditRecord.created_at.asc())
    )
    return list(result.scalars())


async def query_audit_records(
    session: AsyncSession,
    *,
    dispute_id: str | None = None,
    investigation_id: str | None = None,
    event_name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditRecord]:
    stmt = select(AuditRecord)
    if dispute_id:
        stmt = stmt.where(AuditRecord.dispute_id == dispute_id)
    if investigation_id:
        stmt = stmt.where(AuditRecord.investigation_id == investigation_id)
    if event_name:
        stmt = stmt.where(AuditRecord.event_name == event_name)
    stmt = stmt.order_by(AuditRecord.created_at.desc()).limit(min(limit, 500)).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars())


async def verify_audit_integrity(
    session: AsyncSession,
    investigation_id: str,
) -> AuditIntegrityResult:
    rows = await list_audit_records(session, investigation_id)
    if not rows:
        return AuditIntegrityResult(
            investigation_id=investigation_id,
            valid=True,
            checked_records=0,
        )

    expected_sequence = 1
    expected_prev_hash: str | None = None
    for row in rows:
        if row.sequence_no != expected_sequence:
            return AuditIntegrityResult(
                investigation_id=investigation_id,
                valid=False,
                checked_records=expected_sequence - 1,
                broken_sequence=expected_sequence,
                issue_code="SEQUENCE_GAP",
                message="Audit sequence is not contiguous.",
                expected_prev_hash=expected_prev_hash,
                actual_prev_hash=row.prev_hash,
            )
        if row.prev_hash != expected_prev_hash:
            return AuditIntegrityResult(
                investigation_id=investigation_id,
                valid=False,
                checked_records=expected_sequence - 1,
                broken_sequence=expected_sequence,
                issue_code="PREV_HASH_MISMATCH",
                message="Audit chain link does not match previous hash.",
                expected_prev_hash=expected_prev_hash,
                actual_prev_hash=row.prev_hash,
            )

        if not row.row_hash:
            return AuditIntegrityResult(
                investigation_id=investigation_id,
                valid=False,
                checked_records=expected_sequence - 1,
                broken_sequence=expected_sequence,
                issue_code="MISSING_ROW_HASH",
                message="Audit row hash is missing on a record.",
                expected_prev_hash=expected_prev_hash,
                actual_prev_hash=row.prev_hash,
            )

        expected_row_hash = compute_row_hash(
            investigation_id=row.investigation_id,
            dispute_id=row.dispute_id,
            sequence_no=row.sequence_no,
            prev_hash=row.prev_hash,
            actor_id=row.actor_id,
            actor_role=row.actor_role,
            event_name=row.event_name,
            payload=row.payload,
        )
        if row.row_hash != expected_row_hash:
            return AuditIntegrityResult(
                investigation_id=investigation_id,
                valid=False,
                checked_records=expected_sequence - 1,
                broken_sequence=expected_sequence,
                issue_code="ROW_HASH_MISMATCH",
                message="Audit row hash verification failed.",
                expected_prev_hash=expected_prev_hash,
                actual_prev_hash=row.prev_hash,
                expected_row_hash=expected_row_hash,
                actual_row_hash=row.row_hash,
            )

        expected_prev_hash = row.row_hash
        expected_sequence += 1

    return AuditIntegrityResult(
        investigation_id=investigation_id,
        valid=True,
        checked_records=len(rows),
    )


async def create_audit_correction(
    session: AsyncSession,
    *,
    actor: Principal,
    investigation_id: str,
    supersedes_event_id: str,
    reason_code: str,
    note: str,
) -> AuditRecord:
    superseded = await session.get(AuditRecord, supersedes_event_id)
    if superseded is None or superseded.investigation_id != investigation_id:
        raise NotFoundError("AUDIT_EVENT_NOT_FOUND", "Audit event was not found.")
    return await record_audit_event(
        session,
        actor=actor,
        event_name="investigation.audit_correction",
        payload={
            "supersedes_event_id": supersedes_event_id,
            "reason_code": reason_code,
            "note": note,
            "superseded_event_name": superseded.event_name,
        },
        dispute_id=superseded.dispute_id,
        investigation_id=investigation_id,
    )

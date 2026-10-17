from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditIntegrityResponse(BaseModel):
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


class AuditCorrectionRequest(BaseModel):
    supersedes_event_id: str
    reason_code: str = Field(min_length=2, max_length=64)
    note: str = Field(min_length=3, max_length=500)


class AuditCorrectionResponse(BaseModel):
    id: str
    event_name: str
    payload: dict[str, object]
    created_at: datetime


class AuditArtifactResponse(BaseModel):
    artifact_id: str
    audit_record_id: str
    key_id: str
    payload: dict[str, object]


class AuditRecordItem(BaseModel):
    id: str
    dispute_id: str | None = None
    investigation_id: str | None = None
    event_name: str
    payload: dict[str, object]
    actor_id: str
    actor_role: str
    sequence_no: int
    prev_hash: str | None = None
    row_hash: str | None = None
    created_at: datetime


class TuningExportSample(BaseModel):
    id: str
    investigation_id: str
    dispute_id: str
    prompt: str
    chosen: str
    rejected: str | None = None
    export_type: str
    metadata: dict[str, object] = Field(default_factory=dict)


class TuningExportResponse(BaseModel):
    total_samples: int
    export_type: str
    samples: list[TuningExportSample]

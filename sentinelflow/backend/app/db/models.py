from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonDict = dict[str, Any]
JsonList = list[JsonDict]


class Base(DeclarativeBase):
    pass


class DisputeRecord(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    narrative: Mapped[str] = mapped_column(Text())
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    merchant_id: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[float] = mapped_column(Float())
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[str] = mapped_column(String(32), default="open")
    attributes: Mapped[JsonDict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dispute_id: Mapped[str] = mapped_column(ForeignKey("disputes.id"), index=True)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    evidence: Mapped[JsonList] = mapped_column(JSON, default=list)
    analyzer_summaries: Mapped[JsonList] = mapped_column(JSON, default=list)
    hypotheses: Mapped[JsonList] = mapped_column(JSON, default=list)
    unresolved_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    timeline_events: Mapped[JsonList] = mapped_column(JSON, default=list)
    risk_assessment: Mapped[JsonDict | None] = mapped_column(JSON, default=None)
    compliance_findings: Mapped[JsonList] = mapped_column(JSON, default=list)
    report: Mapped[JsonDict | None] = mapped_column(JSON, default=None)
    iteration_count: Mapped[int] = mapped_column(default=0)
    tool_call_count: Mapped[int] = mapped_column(default=0)
    analyzer_call_count: Mapped[int] = mapped_column(default=0)
    checkpoint_id: Mapped[str | None] = mapped_column(String(128), default=None)
    failure_reason: Mapped[str | None] = mapped_column(String(512), default=None)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditRecord(Base):
    __tablename__ = "audit_records"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id",
            "sequence_no",
            name="uq_audit_records_investigation_sequence",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    dispute_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    actor_id: Mapped[str] = mapped_column(String(64))
    actor_role: Mapped[str] = mapped_column(String(64))
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[JsonDict] = mapped_column(JSON, default=dict)
    sequence_no: Mapped[int] = mapped_column(default=1)
    prev_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    row_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditArtifactRecord(Base):
    __tablename__ = "audit_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    audit_record_id: Mapped[str] = mapped_column(
        ForeignKey("audit_records.id"), unique=True, index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    dispute_id: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    key_id: Mapped[str] = mapped_column(String(64))
    ciphertext: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from app.db.models import AuditRecord, Base, DisputeRecord, InvestigationRecord
from app.errors import NotFoundError
from app.security import Principal, Role
from app.services.audit import (
    compute_row_hash,
    create_audit_correction,
    record_audit_event,
    verify_audit_integrity,
)
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@dataclass
class FakeSession:
    item: object | None

    async def get(self, _model: object, _item_id: object) -> object | None:
        return self.item


def _audit_row(
    *,
    row_id: str,
    investigation_id: str,
    sequence_no: int,
    prev_hash: str | None,
    actor_id: str,
    actor_role: str,
    event_name: str,
    payload: dict[str, object],
) -> SimpleNamespace:
    row_hash = compute_row_hash(
        investigation_id=investigation_id,
        dispute_id="disp_1",
        sequence_no=sequence_no,
        prev_hash=prev_hash,
        actor_id=actor_id,
        actor_role=actor_role,
        event_name=event_name,
        payload=payload,
    )
    return SimpleNamespace(
        id=row_id,
        investigation_id=investigation_id,
        dispute_id="disp_1",
        sequence_no=sequence_no,
        prev_hash=prev_hash,
        row_hash=row_hash,
        actor_id=actor_id,
        actor_role=actor_role,
        event_name=event_name,
        payload=payload,
    )


async def test_verify_audit_integrity_accepts_valid_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row1 = _audit_row(
        row_id="evt_1",
        investigation_id="inv_1",
        sequence_no=1,
        prev_hash=None,
        actor_id="u1",
        actor_role="investigator",
        event_name="investigation.started",
        payload={"status": "pending"},
    )
    row2 = _audit_row(
        row_id="evt_2",
        investigation_id="inv_1",
        sequence_no=2,
        prev_hash=row1.row_hash,
        actor_id="u1",
        actor_role="investigator",
        event_name="investigation.llm_iteration",
        payload={"iteration": 1},
    )

    async def fake_list(_session: AsyncSession, _investigation_id: str) -> list[SimpleNamespace]:
        return [row1, row2]

    monkeypatch.setattr("app.services.audit.list_audit_records", fake_list)

    result = await verify_audit_integrity(cast(AsyncSession, object()), "inv_1")

    assert result.valid is True
    assert result.checked_records == 2
    assert result.issue_code is None


async def test_verify_audit_integrity_detects_sequence_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row1 = _audit_row(
        row_id="evt_1",
        investigation_id="inv_1",
        sequence_no=1,
        prev_hash=None,
        actor_id="u1",
        actor_role="investigator",
        event_name="investigation.started",
        payload={"status": "pending"},
    )
    row3 = _audit_row(
        row_id="evt_3",
        investigation_id="inv_1",
        sequence_no=3,
        prev_hash=row1.row_hash,
        actor_id="u1",
        actor_role="investigator",
        event_name="investigation.finalized",
        payload={"status": "completed"},
    )

    async def fake_list(_session: AsyncSession, _investigation_id: str) -> list[SimpleNamespace]:
        return [row1, row3]

    monkeypatch.setattr("app.services.audit.list_audit_records", fake_list)

    result = await verify_audit_integrity(cast(AsyncSession, object()), "inv_1")

    assert result.valid is False
    assert result.issue_code == "SEQUENCE_GAP"
    assert result.broken_sequence == 2


async def test_verify_audit_integrity_detects_hash_tamper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row1 = _audit_row(
        row_id="evt_1",
        investigation_id="inv_1",
        sequence_no=1,
        prev_hash=None,
        actor_id="u1",
        actor_role="investigator",
        event_name="investigation.started",
        payload={"status": "pending"},
    )
    row2 = _audit_row(
        row_id="evt_2",
        investigation_id="inv_1",
        sequence_no=2,
        prev_hash=row1.row_hash,
        actor_id="u1",
        actor_role="investigator",
        event_name="investigation.llm_iteration",
        payload={"iteration": 1},
    )
    row2.payload = {"iteration": 999}

    async def fake_list(_session: AsyncSession, _investigation_id: str) -> list[SimpleNamespace]:
        return [row1, row2]

    monkeypatch.setattr("app.services.audit.list_audit_records", fake_list)

    result = await verify_audit_integrity(cast(AsyncSession, object()), "inv_1")

    assert result.valid is False
    assert result.issue_code == "ROW_HASH_MISMATCH"
    assert result.broken_sequence == 2


async def test_create_audit_correction_appends_correction_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    superseded = SimpleNamespace(
        id="evt_1",
        investigation_id="inv_1",
        dispute_id="disp_1",
        event_name="investigation.llm_iteration",
    )
    session = FakeSession(item=superseded)
    actor = Principal(user_id="auditor_1", roles={Role.AUDITOR})

    async def fake_record_audit_event(
        session: AsyncSession,
        **kwargs: Any,
    ) -> SimpleNamespace:
        _ = session
        return SimpleNamespace(
            id="evt_2",
            event_name=kwargs["event_name"],
            payload=kwargs["payload"],
            created_at="2026-09-02T00:00:00Z",
        )

    monkeypatch.setattr("app.services.audit.record_audit_event", fake_record_audit_event)

    result = await create_audit_correction(
        cast(AsyncSession, session),
        actor=actor,
        investigation_id="inv_1",
        supersedes_event_id="evt_1",
        reason_code="operator_note",
        note="Evidence source typo corrected.",
    )

    assert result.id == "evt_2"
    assert result.event_name == "investigation.audit_correction"
    assert result.payload["supersedes_event_id"] == "evt_1"


async def test_create_audit_correction_requires_existing_event() -> None:
    session = FakeSession(item=None)
    actor = Principal(user_id="auditor_1", roles={Role.AUDITOR})

    try:
        await create_audit_correction(
            cast(AsyncSession, session),
            actor=actor,
            investigation_id="inv_1",
            supersedes_event_id="missing",
            reason_code="operator_note",
            note="Missing record.",
        )
    except NotFoundError as exc:
        assert exc.code == "AUDIT_EVENT_NOT_FOUND"
    else:
        raise AssertionError("Expected NotFoundError for missing superseded event")


async def test_concurrent_audit_events_maintain_contiguous_chain() -> None:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    investigation_id = str(uuid4())
    dispute_id = str(uuid4())

    async with session_factory() as session:
        dispute = DisputeRecord(
            id=dispute_id,
            case_code="DISP-CONC-001",
            title="Concurrent Audit Test",
            narrative="Testing parallel audit appends",
            customer_id="cust_conc",
            merchant_id="merch_conc",
            amount=99.99,
            currency="USD",
            status="open",
            attributes={},
        )
        session.add(dispute)
        inv = InvestigationRecord(
            id=investigation_id,
            dispute_id=dispute_id,
            thread_id="thread_conc",
            status="running",
            created_by="tester",
        )
        session.add(inv)
        await session.commit()

    actor = Principal(user_id="agent-concurrent", roles={Role.INVESTIGATOR})
    num_events = 10

    async def _append_event(index: int) -> None:
        await asyncio.sleep(0.001 * (index % 3))
        async with session_factory() as session:
            await record_audit_event(
                session,
                actor=actor,
                event_name=f"investigation.parallel_step_{index}",
                payload={"step_index": index, "value": f"data_{index}"},
                dispute_id=dispute_id,
                investigation_id=investigation_id,
            )

    tasks = [_append_event(i) for i in range(num_events)]
    await asyncio.gather(*tasks)

    async with session_factory() as session:
        records = (
            (
                await session.execute(
                    select(AuditRecord)
                    .where(AuditRecord.investigation_id == investigation_id)
                    .order_by(AuditRecord.sequence_no.asc())
                )
            )
            .scalars()
            .all()
        )

        assert len(records) == num_events
        sequences = [r.sequence_no for r in records]
        assert sequences == list(range(1, num_events + 1))

        result = await verify_audit_integrity(session, investigation_id)
        assert result.valid is True
        assert result.checked_records == num_events
        assert result.issue_code is None

    await test_engine.dispose()

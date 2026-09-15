from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.errors import NotFoundError
from app.security import Principal, Role
from app.services.audit import (
    compute_row_hash,
    create_audit_correction,
    verify_audit_integrity,
)
from sqlalchemy.ext.asyncio import AsyncSession


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

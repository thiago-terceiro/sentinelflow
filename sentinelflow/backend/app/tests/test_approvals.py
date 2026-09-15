from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Literal, cast

import pytest
from app.api.approvals import resume_investigation
from app.db.models import InvestigationRecord
from app.errors import AppError, AuthorizationError, NotFoundError
from app.schemas.approval import ApprovalDecision
from app.security import Principal, Role
from sqlalchemy.ext.asyncio import AsyncSession

DecisionLiteral = Literal["approve", "deny"]


class _FakeSession:
    def __init__(self, record: InvestigationRecord | None) -> None:
        self._record = record
        self.committed = False
        self.refreshed = False

    async def get(self, _model: object, _investigation_id: str) -> InvestigationRecord | None:
        return self._record

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _record: InvestigationRecord) -> None:
        self.refreshed = True


def _record(*, checkpoint_id: str | None = None) -> InvestigationRecord:
    now = datetime.now(UTC)
    return cast(
        InvestigationRecord,
        SimpleNamespace(
            id="inv_123",
            dispute_id="disp_123",
            thread_id="thread_123",
            status="awaiting_approval",
            created_at=now,
            updated_at=now,
            risk_assessment=None,
            compliance_findings=[],
            report=None,
            checkpoint_id=checkpoint_id,
        ),
    )


def _principal(*roles: Role) -> Principal:
    return Principal(user_id="user_123", roles=set(roles))


async def test_resume_investigation_requires_reviewer_or_admin() -> None:
    decision = ApprovalDecision(decision="approve", comment="looks good")

    with pytest.raises(AuthorizationError):
        await resume_investigation(
            "inv_123",
            decision,
            cast(AsyncSession, _FakeSession(None)),
            _principal(Role.INVESTIGATOR),
        )


async def test_resume_investigation_returns_not_found_for_missing_run() -> None:
    decision = ApprovalDecision(decision="approve", comment="looks good")

    with pytest.raises(NotFoundError):
        await resume_investigation(
            "inv_123",
            decision,
            cast(AsyncSession, _FakeSession(None)),
            _principal(Role.REVIEWER),
        )


async def test_resume_investigation_rejects_duplicate_or_running_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ApprovalDecision(decision="approve", comment="looks good")
    fake_session = _FakeSession(_record())

    async def _schedule_resume(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr("app.api.approvals.schedule_resume", _schedule_resume)

    with pytest.raises(AppError) as captured:
        await resume_investigation(
            "inv_123",
            decision,
            cast(AsyncSession, fake_session),
            _principal(Role.REVIEWER),
        )

    assert captured.value.code == "INVESTIGATION_ALREADY_RUNNING"
    assert captured.value.status_code == 409
    assert fake_session.committed is False



async def test_resume_investigation_requires_awaiting_approval_state() -> None:
    decision = ApprovalDecision(decision="approve", comment="looks good")
    record = _record()
    record.status = "running"
    fake_session = _FakeSession(record)

    with pytest.raises(AppError) as captured:
        await resume_investigation(
            "inv_123",
            decision,
            cast(AsyncSession, fake_session),
            _principal(Role.REVIEWER),
        )

    assert captured.value.code == "INVESTIGATION_NOT_AWAITING_APPROVAL"
    assert captured.value.status_code == 409
    assert fake_session.committed is False

@pytest.mark.parametrize("decision_value", ["approve", "deny"])
async def test_resume_investigation_schedules_and_audits_decision(
    monkeypatch: pytest.MonkeyPatch,
    decision_value: DecisionLiteral,
) -> None:
    fake_session = _FakeSession(_record(checkpoint_id="chk_123"))
    decision = ApprovalDecision(decision=decision_value, comment="review comment")
    captured_payload: dict[str, object] = {}

    async def _schedule_resume(*_args: object, **_kwargs: object) -> bool:
        return True

    async def _record_audit_event(
        _session: object,
        *,
        actor: object,
        event_name: str,
        payload: dict[str, object],
        dispute_id: str | None = None,
        investigation_id: str | None = None,
    ) -> SimpleNamespace:
        _ = (actor, dispute_id, investigation_id)
        captured_payload["event_name"] = event_name
        captured_payload["payload"] = payload
        return SimpleNamespace(id="audit_1")

    monkeypatch.setattr("app.api.approvals.schedule_resume", _schedule_resume)
    monkeypatch.setattr("app.api.approvals.record_audit_event", _record_audit_event)

    run = await resume_investigation(
        "inv_123",
        decision,
        cast(AsyncSession, fake_session),
        _principal(Role.REVIEWER),
    )

    assert run.id == "inv_123"
    assert run.status == "running"
    assert fake_session.committed is True
    assert fake_session.refreshed is True
    assert captured_payload["event_name"] == "investigation.approval_recorded"
    payload = cast(dict[str, object], captured_payload["payload"])
    assert payload["decision"] == decision_value
    assert payload["checkpoint_id"] == "chk_123"

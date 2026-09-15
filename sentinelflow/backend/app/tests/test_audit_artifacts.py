from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from app.db.models import AuditArtifactRecord, AuditRecord
from app.security import Principal, Role
from app.services.audit import get_raw_audit_artifact, record_audit_event
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class _SessionWithWrites:
    added: list[object]

    def __init__(self) -> None:
        self.added = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        return None

    async def refresh(self, _item: object) -> None:
        return None


class _SessionWithGet:
    def __init__(self, artifact: object | None) -> None:
        self._artifact = artifact

    async def get(self, _model: object, _item_id: object) -> object | None:
        return self._artifact


async def test_record_audit_event_marks_unencrypted_artifact_when_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _next_sequence(
        _session: AsyncSession,
        _investigation_id: str | None,
    ) -> tuple[int, str | None]:
        return 1, None

    monkeypatch.setattr("app.services.audit._next_sequence_and_prev_hash", _next_sequence)
    monkeypatch.setattr("app.services.audit._trace_correlation", lambda: (None, None))
    monkeypatch.setattr(
        "app.services.audit.get_settings",
        lambda: SimpleNamespace(
            AUDIT_ARTIFACT_ENCRYPTION_KEY=None,
            AUDIT_ARTIFACT_KEY_ID="v1",
        ),
    )

    session = _SessionWithWrites()
    actor = Principal(user_id="u1", roles={Role.AUDITOR})

    record = await record_audit_event(
        cast(AsyncSession, session),
        actor=actor,
        event_name="investigation.llm_iteration",
        payload={
            "iteration": 1,
            "raw_artifact": {
                "prompt": "secret prompt",
                "output": "secret output",
            },
        },
        investigation_id="inv_1",
        dispute_id="disp_1",
    )

    assert isinstance(record, AuditRecord)
    assert "raw_artifact" not in record.payload
    assert record.payload["raw_artifact_encrypted"] is False
    assert record.payload["raw_artifact_unavailable_reason"] == "encryption_not_configured"
    assert not any(isinstance(item, AuditArtifactRecord) for item in session.added)


async def test_record_audit_event_encrypts_artifact_when_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _next_sequence(
        _session: AsyncSession,
        _investigation_id: str | None,
    ) -> tuple[int, str | None]:
        return 1, None

    monkeypatch.setattr("app.services.audit._next_sequence_and_prev_hash", _next_sequence)
    monkeypatch.setattr("app.services.audit._trace_correlation", lambda: (None, None))
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(
        "app.services.audit.get_settings",
        lambda: SimpleNamespace(
            AUDIT_ARTIFACT_ENCRYPTION_KEY=key,
            AUDIT_ARTIFACT_KEY_ID="k1",
        ),
    )

    session = _SessionWithWrites()
    actor = Principal(user_id="u1", roles={Role.AUDITOR})

    record = await record_audit_event(
        cast(AsyncSession, session),
        actor=actor,
        event_name="investigation.llm_iteration",
        payload={
            "iteration": 1,
            "raw_artifact": {
                "prompt": "very secret prompt",
                "output": "very secret output",
                "reasoning": "private chain-of-thought",
            },
        },
        investigation_id="inv_1",
        dispute_id="disp_1",
    )

    artifacts = [item for item in session.added if isinstance(item, AuditArtifactRecord)]

    assert isinstance(record, AuditRecord)
    assert record.payload["raw_artifact_encrypted"] is True
    assert record.payload["raw_artifact_key_id"] == "k1"
    assert record.payload["raw_artifact_id"] == artifacts[0].id
    assert len(artifacts) == 1
    assert "very secret prompt" not in artifacts[0].ciphertext


async def test_get_raw_audit_artifact_decrypts_payload_and_logs_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = Fernet.generate_key().decode("utf-8")
    cipher = Fernet(key.encode("utf-8"))
    encrypted_payload = cipher.encrypt(
        json.dumps({"prompt": "secret", "output": "model output"}).encode("utf-8")
    ).decode("utf-8")

    artifact = SimpleNamespace(
        id="art_1",
        audit_record_id="evt_1",
        investigation_id="inv_1",
        dispute_id="disp_1",
        key_id="k1",
        ciphertext=encrypted_payload,
    )
    session = _SessionWithGet(artifact)
    actor = Principal(user_id="aud_1", roles={Role.AUDITOR})

    recorded: list[dict[str, Any]] = []

    async def _fake_record_audit_event(
        _session: AsyncSession,
        **kwargs: Any,
    ) -> SimpleNamespace:
        recorded.append(kwargs)
        return SimpleNamespace(id="evt_2")

    monkeypatch.setattr(
        "app.services.audit.get_settings",
        lambda: SimpleNamespace(
            AUDIT_ARTIFACT_ENCRYPTION_KEY=key,
            AUDIT_ARTIFACT_KEY_ID="k1",
        ),
    )
    monkeypatch.setattr("app.services.audit.record_audit_event", _fake_record_audit_event)

    result = await get_raw_audit_artifact(
        cast(AsyncSession, session),
        actor=actor,
        investigation_id="inv_1",
        artifact_id="art_1",
    )

    assert result["artifact_id"] == "art_1"
    assert result["audit_record_id"] == "evt_1"
    assert result["payload"] == {"prompt": "secret", "output": "model output"}
    assert recorded[0]["event_name"] == "investigation.audit_artifact_read"

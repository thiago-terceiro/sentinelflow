from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from app.api.health import ready, telemetry_health
from app.errors import AppError
from sqlalchemy.ext.asyncio import AsyncSession


class _SchemaResult:
    def __init__(self, row: dict[str, str | None]) -> None:
        self._row = row

    def mappings(self) -> _SchemaResult:
        return self

    def one(self) -> dict[str, str | None]:
        return self._row


class _FakeSession:
    def __init__(self, schema_row: dict[str, str | None]) -> None:
        self._schema_row = schema_row
        self._calls = 0

    async def execute(self, _query: object) -> object:
        self._calls += 1
        if self._calls == 1:
            return object()
        return _SchemaResult(self._schema_row)


async def test_ready_fails_when_required_schema_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.get_settings",
        lambda: SimpleNamespace(APP_ENV="development", OPENAI_API_KEY=None),
    )
    session = _FakeSession(
        {
            "disputes": "disputes",
            "investigations": None,
            "audit_records": "audit_records",
        }
    )

    try:
        await ready(cast(AsyncSession, session))
    except AppError as exc:
        assert exc.code == "READINESS_SCHEMA_MISSING"
    else:
        raise AssertionError("Expected readiness to fail with missing schema")


async def test_ready_fails_when_provider_config_missing_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.get_settings",
        lambda: SimpleNamespace(APP_ENV="production", OPENAI_API_KEY=None),
    )
    session = _FakeSession(
        {
            "disputes": "disputes",
            "investigations": "investigations",
            "audit_records": "audit_records",
        }
    )

    try:
        await ready(cast(AsyncSession, session))
    except AppError as exc:
        assert exc.code == "READINESS_PROVIDER_NOT_CONFIGURED"
    else:
        raise AssertionError("Expected readiness to fail with missing provider config")


async def test_ready_fails_when_production_checkpointer_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.get_settings",
        lambda: SimpleNamespace(APP_ENV="production", OPENAI_API_KEY="set"),
    )

    def _fail_checkpointer() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.api.health.validate_production_checkpointer", _fail_checkpointer)
    session = _FakeSession(
        {
            "disputes": "disputes",
            "investigations": "investigations",
            "audit_records": "audit_records",
        }
    )

    try:
        await ready(cast(AsyncSession, session))
    except AppError as exc:
        assert exc.code == "READINESS_CHECKPOINTER_INVALID"
    else:
        raise AssertionError("Expected readiness to fail when checkpointer validation fails")


async def test_ready_fails_when_queue_unavailable_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.get_settings",
        lambda: SimpleNamespace(
            APP_ENV="production",
            OPENAI_API_KEY="set",
            QUEUE_REDIS_URL="redis://localhost:6379/0",
        ),
    )
    monkeypatch.setattr("app.api.health.validate_production_checkpointer", lambda: None)

    async def _fail_redis(_url: str) -> None:
        raise ConnectionError("connection refused")

    monkeypatch.setattr("app.api.health.check_redis_connectivity", _fail_redis)
    session = _FakeSession(
        {
            "disputes": "disputes",
            "investigations": "investigations",
            "audit_records": "audit_records",
        }
    )

    try:
        await ready(cast(AsyncSession, session))
    except AppError as exc:
        assert exc.code == "READINESS_QUEUE_UNAVAILABLE"
    else:
        raise AssertionError("Expected readiness to fail when queue is unavailable")


async def test_ready_succeeds_when_dependencies_are_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.get_settings",
        lambda: SimpleNamespace(
            APP_ENV="production",
            OPENAI_API_KEY="set",
            QUEUE_REDIS_URL="redis://localhost:6379/0",
        ),
    )
    monkeypatch.setattr("app.api.health.validate_production_checkpointer", lambda: None)

    async def _ok_redis(_url: str) -> None:
        return None

    monkeypatch.setattr("app.api.health.check_redis_connectivity", _ok_redis)
    session = _FakeSession(
        {
            "disputes": "disputes",
            "investigations": "investigations",
            "audit_records": "audit_records",
        }
    )

    result = await ready(cast(AsyncSession, session))

    assert result == {"status": "ready"}


async def test_telemetry_health_returns_operator_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.health.telemetry_operator_status",
        lambda: {
            "status": "ok",
            "service_name": "sentinelflow-agent-engine",
            "exporter_configured": True,
            "exporter_endpoint": "https://otel.example/v1/traces",
            "headers_configured": True,
            "probe_emitted": True,
            "probe_error": None,
        },
    )

    payload = await telemetry_health()

    assert payload["status"] == "ok"
    assert payload["probe_emitted"] is True

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings
from app.db.session import engine
from app.graph.graph import close_checkpointer
from app.services.investigations import (
    close_redis_pool,
    run_investigation_job,
    run_resume_investigation_job,
)
from app.telemetry import configure_worker_telemetry

settings = get_settings()


async def startup(_ctx: dict[str, Any]) -> None:
    configure_worker_telemetry()


async def shutdown(_ctx: dict[str, Any]) -> None:
    await close_redis_pool()
    await close_checkpointer()
    await engine.dispose()


async def persist_escalated_dispute_job(_ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """Durable arq worker job to persist an escalated telecom anomaly dispute record."""
    from app.api.telecom import _persist_escalated_dispute

    await _persist_escalated_dispute(
        dispute_id=payload["dispute_id"],
        case_code=payload["case_code"],
        sender=payload["sender"],
        recipient=payload["recipient"],
        message=payload["message"],
        carrier=payload.get("carrier"),
        verdict=payload["verdict"],
        fraud_score=payload["fraud_score"],
        signals=payload.get("signals", []),
        velocity=payload.get("velocity", {}),
        event_id=payload.get("event_id"),
        customer_id=payload.get("customer_id"),
    )


class WorkerSettings:
    functions = [
        run_investigation_job,
        run_resume_investigation_job,
        persist_escalated_dispute_job,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.QUEUE_REDIS_URL)
    keep_result = 0
    max_tries = 1

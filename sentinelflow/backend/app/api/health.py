from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DBSessionDep
from app.config import get_settings
from app.errors import AppError
from app.graph.graph import validate_production_checkpointer
from app.telemetry import telemetry_operator_status

router = APIRouter(tags=["health"])
logger = logging.getLogger("sentinelflow.health")


def _missing_tables(row: dict[str, str | None]) -> list[str]:
    return [name for name, value in row.items() if value is None]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def check_redis_connectivity(redis_url: str) -> None:
    from redis.asyncio import from_url

    client = from_url(redis_url, socket_timeout=2.0)
    try:
        await client.ping()
    finally:
        await client.aclose()


@router.get("/ready")
async def ready(session: DBSessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    schema_row = (
        (
            await session.execute(
                text(
                    """
                SELECT
                    to_regclass('public.disputes') AS disputes,
                    to_regclass('public.investigations') AS investigations,
                    to_regclass('public.audit_records') AS audit_records
                """
                )
            )
        )
        .mappings()
        .one()
    )
    missing = _missing_tables(dict(schema_row))
    if missing:
        logger.error(
            "Readiness failed: required schema is missing.",
            extra={
                "event": "readiness_failed",
                "missing_tables": missing,
            },
        )
        raise AppError(
            code="READINESS_SCHEMA_MISSING",
            message="Required database schema is unavailable.",
            status_code=503,
        )

    settings = get_settings()
    if settings.APP_ENV == "production":
        if not settings.OPENAI_API_KEY:
            raise AppError(
                code="READINESS_PROVIDER_NOT_CONFIGURED",
                message="Required provider configuration is unavailable.",
                status_code=503,
            )
        try:
            validate_production_checkpointer()
        except RuntimeError as exc:
            logger.error(
                "Readiness failed: production checkpointer validation failed.",
                extra={
                    "event": "readiness_failed",
                    "reason": str(exc),
                },
            )
            raise AppError(
                code="READINESS_CHECKPOINTER_INVALID",
                message="Production checkpointer configuration is invalid.",
                status_code=503,
            ) from exc
        redis_url = getattr(settings, "QUEUE_REDIS_URL", None)
        if redis_url:
            try:
                await check_redis_connectivity(redis_url)
            except Exception as exc:
                logger.error(
                    "Readiness failed: background queue is unreachable.",
                    extra={
                        "event": "readiness_failed",
                        "reason": str(exc),
                    },
                )
                raise AppError(
                    code="READINESS_QUEUE_UNAVAILABLE",
                    message="Background queue is unavailable.",
                    status_code=503,
                ) from exc
    return {"status": "ready"}


@router.get("/health/telemetry")
async def telemetry_health() -> dict[str, object]:
    return telemetry_operator_status()

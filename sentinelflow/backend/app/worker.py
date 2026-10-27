from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings
from app.services.investigations import run_investigation_job, run_resume_investigation_job
from app.telemetry import configure_worker_telemetry

settings = get_settings()


async def startup(_ctx: dict[str, Any]) -> None:
    configure_worker_telemetry()


class WorkerSettings:
    functions = [run_investigation_job, run_resume_investigation_job]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.QUEUE_REDIS_URL)
    keep_result = 0
    max_tries = 1

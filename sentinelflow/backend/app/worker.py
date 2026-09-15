from __future__ import annotations

from arq.connections import RedisSettings

from app.config import get_settings
from app.services.investigations import run_investigation_job, run_resume_investigation_job

settings = get_settings()


class WorkerSettings:
    functions = [run_investigation_job, run_resume_investigation_job]
    redis_settings = RedisSettings.from_dsn(settings.QUEUE_REDIS_URL)
    keep_result = 0
    max_tries = 1

"""
Worker server — runs the arq worker inside a minimal FastAPI process.

Render's free plan has no background-worker service type, so we expose a
tiny web service with a /health endpoint to satisfy Render's health check,
and start the arq worker as an asyncio task in the lifespan.

Start command (set in render.yaml dockerCommand):
    uvicorn app.worker_server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, cast

from arq.worker import create_worker
from fastapi import FastAPI

from app.logging import configure_logging
from app.worker import WorkerSettings

configure_logging()
logger = logging.getLogger("sentinelflow.worker_server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = create_worker(cast(Any, WorkerSettings))
    task = asyncio.create_task(worker.async_run())
    logger.info("arq worker started")
    try:
        yield
    finally:
        logger.info("arq worker shutting down")
        await worker.close()
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
        except (TimeoutError, asyncio.CancelledError):
            pass


app = FastAPI(
    title="SentinelFlow Worker",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "arq-worker"}

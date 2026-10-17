from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from app.api.approvals import router as approvals_router
from app.api.disputes import router as disputes_router
from app.api.evals import router as evals_router
from app.api.health import router as health_router
from app.api.telecom import (
    batch_classify_telecom_messages,
    classify_telecom_message,
    get_prometheus_metrics,
)
from app.api.telecom import (
    router as telecom_router,
)
from app.config import get_settings
from app.db.session import engine
from app.errors import install_error_handlers
from app.http import install_http_middleware
from app.logging import configure_logging
from app.services.investigations import close_redis_pool
from app.telecom.velocity_store import get_velocity_store
from app.telemetry import configure_telemetry

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await get_velocity_store().close()
    await close_redis_pool()
    await engine.dispose()
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()


app = FastAPI(
    title="SentinelFlow & SentinelPulse API",
    version="0.1.0",
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)
install_http_middleware(app, settings)
install_error_handlers(app)
configure_telemetry(app)
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(disputes_router, prefix=settings.API_V1_PREFIX)
app.include_router(approvals_router, prefix=settings.API_V1_PREFIX)
app.include_router(evals_router, prefix=settings.API_V1_PREFIX)
app.include_router(telecom_router, prefix=settings.API_V1_PREFIX)

# Compatibility aliases requested for SentinelPulse Gateway
app.post("/v1/classify", tags=["telecom-intelligence"])(classify_telecom_message)
app.post("/v1/events/batch", tags=["telecom-intelligence"])(batch_classify_telecom_messages)
app.get("/metrics", tags=["telecom-intelligence"])(get_prometheus_metrics)

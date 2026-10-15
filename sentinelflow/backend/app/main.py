from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from app.api.approvals import router as approvals_router
from app.api.disputes import router as disputes_router
from app.api.evals import router as evals_router
from app.api.health import router as health_router
from app.config import get_settings
from app.db.session import engine
from app.errors import install_error_handlers
from app.http import install_http_middleware
from app.logging import configure_logging
from app.services.investigations import close_redis_pool
from app.telemetry import configure_telemetry

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis_pool()
    await engine.dispose()
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()


app = FastAPI(
    title="SentinelFlow API",
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

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import (  # pyright: ignore[reportMissingTypeStubs]
    FastAPIInstrumentor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import get_settings


def _build_exporter_headers(raw_headers: str | None) -> dict[str, str] | None:
    if not raw_headers:
        return None
    headers: dict[str, str] = {}
    for pair in raw_headers.split(","):
        key, separator, value = pair.partition("=")
        if not separator:
            continue
        normalized_key = key.strip()
        normalized_value = value.strip()
        if normalized_key and normalized_value:
            headers[normalized_key] = normalized_value
    return headers or None


def _configure_trace_provider() -> None:
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return
    settings = get_settings()
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.OTEL_SERVICE_NAME}),
    )
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        raw_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip("/")
        traces_url = (
            raw_endpoint if raw_endpoint.endswith("/v1/traces") else f"{raw_endpoint}/v1/traces"
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=traces_url,
                    headers=_build_exporter_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
                )
            )
        )
    trace.set_tracer_provider(provider)


def configure_telemetry(app: FastAPI) -> None:
    _configure_trace_provider()
    FastAPIInstrumentor.instrument_app(app)


def configure_worker_telemetry() -> None:
    _configure_trace_provider()


def telemetry_operator_status() -> dict[str, Any]:
    settings = get_settings()
    exporter_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    exporter_configured = bool(exporter_endpoint)
    headers = _build_exporter_headers(settings.OTEL_EXPORTER_OTLP_HEADERS)

    probe_emitted = False
    probe_error: str | None = None
    try:
        tracer = trace.get_tracer("sentinelflow.telemetry")
        with tracer.start_as_current_span("telemetry.operator_probe"):
            pass
        provider = trace.get_tracer_provider()
        force_flush = getattr(provider, "force_flush", None)
        if callable(force_flush):
            force_flush_result = force_flush(timeout_millis=1500)
            probe_emitted = bool(True if force_flush_result is None else force_flush_result)
        else:
            probe_emitted = True
    except Exception as exc:  # pragma: no cover - defensive status endpoint.
        probe_error = str(exc)

    status = "ok"
    if not exporter_configured:
        status = "warning"
    if not probe_emitted:
        status = "error"

    return {
        "status": status,
        "service_name": settings.OTEL_SERVICE_NAME,
        "exporter_configured": exporter_configured,
        "exporter_endpoint": exporter_endpoint,
        "headers_configured": bool(headers),
        "probe_emitted": probe_emitted,
        "probe_error": probe_error,
    }

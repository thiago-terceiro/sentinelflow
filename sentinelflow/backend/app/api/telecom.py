"""SentinelPulse Real-Time SMS Fraud & Spam Intelligence Gateway Endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.trace_safety import redact_text
from app.telecom.drift_monitor import get_drift_monitor
from app.telecom.onnx_engine import get_inference_engine
from app.telecom.telecom_metrics import export_prometheus_metrics, get_metrics_tracker
from app.telecom.velocity_store import get_velocity_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telecom-intelligence"])


def _mask_phone(phone: str) -> str:
    """Masks central digits of phone numbers for public dashboard display."""
    if len(phone) <= 6:
        return phone
    return f"{phone[:4]}***{phone[-4:]}"

# In-memory SSE subscriber queues for the real-time live dashboard
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
_subscribers_lock = asyncio.Lock()


async def broadcast_telecom_event(event: dict[str, Any]) -> None:
    """Dispatches a real-time event to all connected dashboard SSE streams."""
    async with _subscribers_lock:
        active_subs = list(_subscribers)

    for q in active_subs:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


class TelecomClassifyRequest(BaseModel):
    sender: str = Field(
        ...,
        description="Originating phone number (E.164 format, e.g. +15551234567)",
    )
    recipient: str = Field(..., description="Destination phone number (E.164 format)")
    message: str = Field(..., min_length=1, max_length=1600, description="SMS text content")
    ip: str | None = Field(default=None, description="Originating client or carrier gateway IP")
    carrier: str | None = Field(default=None, description="Originating network carrier")


class TelecomClassifyResponse(BaseModel):
    verdict: Literal["ALLOW", "BLOCK", "FLAG"]
    fraud_score: float
    latency_ms: float
    signals: list[str]
    velocity: dict[str, Any]
    model_version: str


class TelecomBatchRequest(BaseModel):
    events: list[TelecomClassifyRequest] = Field(..., min_length=1, max_length=500)


class TelecomBatchResponse(BaseModel):
    total_processed: int
    batch_latency_ms: float
    results: list[TelecomClassifyResponse]


async def _process_single_message(
    req: TelecomClassifyRequest,
    event_id: str | None = None,
) -> TelecomClassifyResponse:
    """Executes the dual-layer detection pipeline (velocity counters + ONNX inference)."""
    t_start = time.perf_counter()
    eid = event_id or f"evt_{uuid4().hex[:10]}"

    engine = get_inference_engine()
    velocity_store = get_velocity_store()
    metrics = get_metrics_tracker()
    drift = get_drift_monitor()

    # 1. Feature Store / Sliding-window velocity lookup
    velocity_metrics = await velocity_store.record_and_evaluate(
        sender=req.sender,
        ip=req.ip,
        carrier=req.carrier,
    )

    # 2. Heuristic + ONNX Runtime ML classification
    inference_result = engine.predict(req.message)

    # 3. Composite score calculation
    # If velocity signals indicate an active flood/bot attack, escalate risk
    composite_score = max(inference_result.fraud_score, velocity_metrics.risk_contribution)
    composite_score = min(1.0, composite_score)

    # Combine signals from both layers
    combined_signals = list(dict.fromkeys(inference_result.signals + velocity_metrics.signals))

    # 4. Final policy verdict
    if composite_score >= 0.75:
        verdict: Literal["ALLOW", "BLOCK", "FLAG"] = "BLOCK"
    elif composite_score >= 0.40:
        verdict = "FLAG"
    else:
        verdict = "ALLOW"

    t_end = time.perf_counter()
    total_latency_ms = round((t_end - t_start) * 1000.0, 3)

    # 5. Redact PII & mask phone numbers for telemetry and public live dashboard
    safe_message, _ = redact_text(req.message)
    masked_sender = _mask_phone(req.sender)
    masked_recipient = _mask_phone(req.recipient)

    metrics.record_event(
        event_id=eid,
        sender=masked_sender,
        recipient=masked_recipient,
        message=safe_message,
        verdict=verdict,
        fraud_score=composite_score,
        latency_ms=total_latency_ms,
        signals=combined_signals,
        carrier=velocity_metrics.carrier,
        onnx_latency_ms=inference_result.latency_ms,
    )
    drift.record_observation(req.message, composite_score)

    velocity_dict = {
        "velocity_10s": velocity_metrics.velocity_10s,
        "velocity_60s": velocity_metrics.velocity_60s,
        "velocity_1h": velocity_metrics.velocity_1h,
        "carrier": velocity_metrics.carrier,
        "carrier_risk": velocity_metrics.carrier_risk,
        "ip_count_60s": velocity_metrics.ip_count_60s,
    }

    response_payload = TelecomClassifyResponse(
        verdict=verdict,
        fraud_score=round(composite_score, 4),
        latency_ms=total_latency_ms,
        signals=combined_signals,
        velocity=velocity_dict,
        model_version=inference_result.model_version,
    )

    # 6. Stream live event to connected frontend dashboard (with PII redacted)
    stream_payload = {
        "id": eid,
        "timestamp": time.time(),
        "sender": masked_sender,
        "recipient": masked_recipient,
        "message": safe_message,
        "verdict": verdict,
        "fraud_score": round(composite_score, 4),
        "latency_ms": total_latency_ms,
        "signals": combined_signals,
        "carrier": velocity_metrics.carrier,
        "velocity": velocity_dict,
    }
    await broadcast_telecom_event(stream_payload)

    return response_payload


@router.post("/telecom/classify", response_model=TelecomClassifyResponse)
async def classify_telecom_message(request: TelecomClassifyRequest) -> TelecomClassifyResponse:
    """Real-time synchronous classification gateway with <15ms p95 latency SLA."""
    return await _process_single_message(request)


@router.post("/telecom/events/batch", response_model=TelecomBatchResponse)
async def batch_classify_telecom_messages(request: TelecomBatchRequest) -> TelecomBatchResponse:
    """High-throughput batch ingestion endpoint for bulk SMS stream evaluation."""
    t_batch_start = time.perf_counter()

    sem = asyncio.Semaphore(50)

    async def _bounded_classify(item: TelecomClassifyRequest) -> TelecomClassifyResponse:
        async with sem:
            return await _process_single_message(item)

    results = list(await asyncio.gather(*[_bounded_classify(item) for item in request.events]))

    batch_latency = round((time.perf_counter() - t_batch_start) * 1000.0, 2)
    return TelecomBatchResponse(
        total_processed=len(results),
        batch_latency_ms=batch_latency,
        results=results,
    )


@router.get("/telecom/metrics/summary")
async def get_telecom_metrics_summary() -> dict[str, Any]:
    """Returns rolling real-time telemetry: throughput (EPS), p50/p95/p99 latency, fraud rates."""
    return get_metrics_tracker().get_summary()


@router.get("/telecom/drift")
async def get_telecom_drift_status() -> dict[str, Any]:
    """Returns Kolmogorov-Smirnov and Population Stability Index (PSI) drift reports."""
    report = get_drift_monitor().evaluate_drift()
    return {
        "status": report.status,
        "ks_statistic": report.ks_statistic,
        "ks_p_value": report.ks_p_value,
        "ks_drift_detected": report.ks_drift_detected,
        "psi_score": report.psi_score,
        "psi_status": report.psi_status,
        "sample_count": report.sample_count,
        "baseline_sample_count": report.baseline_sample_count,
        "mean_live_length": report.mean_live_length,
        "mean_baseline_length": report.mean_baseline_length,
        "recommendation": report.recommendation,
    }


@router.get("/telecom/stream")
async def stream_telecom_events() -> StreamingResponse:
    """Server-Sent Events (SSE) feed for real-time dashboard live inspection."""

    async def event_generator() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with _subscribers_lock:
            _subscribers.add(queue)

        try:
            # Yield initial connection message
            yield f"event: connected\ndata: {json.dumps({'status': 'listening'})}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield f"event: message\ndata: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'time': time.time()})}\n\n"
        finally:
            async with _subscribers_lock:
                _subscribers.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/metrics")
async def get_prometheus_metrics() -> Response:
    """Prometheus telemetry exposition endpoint."""
    content, content_type = export_prometheus_metrics()
    return Response(content=content, media_type=content_type)

"""SentinelPulse Real-Time SMS Fraud & Spam Intelligence Gateway Endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DisputeRecord
from app.db.session import SessionLocal
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
    escalate: bool = Field(
        default=False,
        description="Automatically escalate FLAG/BLOCK verdicts to a SentinelFlow dispute",
    )


class TelecomClassifyResponse(BaseModel):
    verdict: Literal["ALLOW", "BLOCK", "FLAG"]
    fraud_score: float
    latency_ms: float
    signals: list[str]
    velocity: dict[str, Any]
    model_version: str
    escalated_dispute_id: str | None = None
    escalated_dispute_url: str | None = None


class TelecomEscalateRequest(BaseModel):
    sender: str = Field(..., description="Originating phone number")
    recipient: str = Field(..., description="Destination phone number")
    message: str = Field(..., description="SMS text content")
    carrier: str | None = Field(default=None, description="Network carrier")
    verdict: Literal["ALLOW", "BLOCK", "FLAG"] = Field(..., description="Classification verdict")
    fraud_score: float = Field(..., description="Computed composite fraud score")
    signals: list[str] = Field(default_factory=list, description="Triggered fraud signals")
    velocity: dict[str, Any] = Field(default_factory=dict, description="Velocity signals")
    event_id: str | None = Field(default=None, description="Telecom feed event ID")


class TelecomEscalateResponse(BaseModel):
    dispute_id: str
    case_code: str
    dispute_url: str
    status: str


class TelecomBatchRequest(BaseModel):
    events: list[TelecomClassifyRequest] = Field(..., min_length=1, max_length=500)


class TelecomBatchResponse(BaseModel):
    total_processed: int
    batch_latency_ms: float
    results: list[TelecomClassifyResponse]


async def _create_escalated_dispute(
    session: AsyncSession,
    *,
    dispute_id: str | None = None,
    case_code: str | None = None,
    sender: str,
    recipient: str,
    message: str,
    carrier: str | None,
    verdict: str,
    fraud_score: float,
    signals: list[str],
    velocity: dict[str, Any],
    event_id: str | None = None,
) -> DisputeRecord:
    assigned_code = case_code or f"TEL-{uuid4().hex[:8].upper()}"
    assigned_id = dispute_id or str(uuid4())
    title = f"SMS Anomaly: {sender} -> {recipient} ({verdict})"
    narrative = (
        f"SentinelPulse Telecom Gateway Anomaly Alert:\n"
        f"Verdict: {verdict}\n"
        f"Fraud Score: {fraud_score}\n"
        f"Sender: {sender}\n"
        f"Recipient: {recipient}\n"
        f"Carrier: {carrier or 'Unknown'}\n"
        f"Signals: {', '.join(signals) if signals else 'None'}\n"
        f"Message Content: {message}\n"
        f"Velocity Details: {json.dumps(velocity)}"
    )
    dispute = DisputeRecord(
        id=assigned_id,
        case_code=assigned_code,
        title=title,
        narrative=narrative,
        customer_id=f"tel_{sender.replace('+', '')}",
        merchant_id=(
            f"carrier_{carrier.lower().replace(' ', '_')}" if carrier else "carrier_unknown"
        ),
        amount=0.0,
        currency="USD",
        status="open",
        attributes={
            "source": "sentinelpulse",
            "telecom_anomaly": True,
            "verdict": verdict,
            "fraud_score": fraud_score,
            "signals": signals,
            "carrier": carrier,
            "velocity": velocity,
            "event_id": event_id,
            "tags": ["telecom_anomaly", verdict.lower(), "sentinelpulse"],
        },
    )
    session.add(dispute)
    await session.commit()
    await session.refresh(dispute)
    return dispute


async def _persist_escalated_dispute(
    *,
    dispute_id: str,
    case_code: str,
    sender: str,
    recipient: str,
    message: str,
    carrier: str | None,
    verdict: str,
    fraud_score: float,
    signals: list[str],
    velocity: dict[str, Any],
    event_id: str | None = None,
) -> None:
    """Background task to commit escalated dispute record without blocking HTTP response."""
    try:
        async with SessionLocal() as db_session:
            await _create_escalated_dispute(
                db_session,
                dispute_id=dispute_id,
                case_code=case_code,
                sender=sender,
                recipient=recipient,
                message=message,
                carrier=carrier,
                verdict=verdict,
                fraud_score=fraud_score,
                signals=signals,
                velocity=velocity,
                event_id=event_id,
            )
    except Exception as exc:
        logger.warning("Failed to persist background escalated dispute %s: %s", dispute_id, exc)


async def _process_single_message(
    req: TelecomClassifyRequest,
    event_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
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

    escalated_dispute_id: str | None = None
    escalated_dispute_url: str | None = None
    if req.escalate and verdict in ("FLAG", "BLOCK"):
        new_dispute_id = str(uuid4())
        new_case_code = f"TEL-{uuid4().hex[:8].upper()}"
        escalated_dispute_id = new_dispute_id
        escalated_dispute_url = f"/disputes/{new_dispute_id}"
        if background_tasks is not None:
            background_tasks.add_task(
                _persist_escalated_dispute,
                dispute_id=new_dispute_id,
                case_code=new_case_code,
                sender=req.sender,
                recipient=req.recipient,
                message=req.message,
                carrier=velocity_metrics.carrier,
                verdict=verdict,
                fraud_score=round(composite_score, 4),
                signals=combined_signals,
                velocity=velocity_dict,
                event_id=eid,
            )
        else:
            asyncio.create_task(
                _persist_escalated_dispute(
                    dispute_id=new_dispute_id,
                    case_code=new_case_code,
                    sender=req.sender,
                    recipient=req.recipient,
                    message=req.message,
                    carrier=velocity_metrics.carrier,
                    verdict=verdict,
                    fraud_score=round(composite_score, 4),
                    signals=combined_signals,
                    velocity=velocity_dict,
                    event_id=eid,
                )
            )

    response_payload = TelecomClassifyResponse(
        verdict=verdict,
        fraud_score=round(composite_score, 4),
        latency_ms=total_latency_ms,
        signals=combined_signals,
        velocity=velocity_dict,
        model_version=inference_result.model_version,
        escalated_dispute_id=escalated_dispute_id,
        escalated_dispute_url=escalated_dispute_url,
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
        "escalated_dispute_id": escalated_dispute_id,
        "escalated_dispute_url": escalated_dispute_url,
    }
    await broadcast_telecom_event(stream_payload)

    return response_payload


@router.post("/telecom/classify", response_model=TelecomClassifyResponse)
async def classify_telecom_message(
    request: TelecomClassifyRequest,
    background_tasks: BackgroundTasks,
) -> TelecomClassifyResponse:
    """Real-time synchronous classification gateway with <15ms p95 latency SLA."""
    return await _process_single_message(request, background_tasks=background_tasks)


@router.post("/telecom/escalate", response_model=TelecomEscalateResponse)
async def escalate_telecom_anomaly(request: TelecomEscalateRequest) -> TelecomEscalateResponse:
    """Escalates a telecom anomaly to a SentinelFlow dispute for LangGraph investigation."""
    async with SessionLocal() as session:
        dispute = await _create_escalated_dispute(
            session,
            sender=request.sender,
            recipient=request.recipient,
            message=request.message,
            carrier=request.carrier,
            verdict=request.verdict,
            fraud_score=request.fraud_score,
            signals=request.signals,
            velocity=request.velocity,
            event_id=request.event_id,
        )
        return TelecomEscalateResponse(
            dispute_id=dispute.id,
            case_code=dispute.case_code,
            dispute_url=f"/disputes/{dispute.id}",
            status=dispute.status,
        )


@router.post("/telecom/events/batch", response_model=TelecomBatchResponse)
async def batch_classify_telecom_messages(
    request: TelecomBatchRequest,
    background_tasks: BackgroundTasks,
) -> TelecomBatchResponse:
    """High-throughput batch ingestion endpoint for bulk SMS stream evaluation."""
    t_batch_start = time.perf_counter()

    sem = asyncio.Semaphore(50)

    async def _bounded_classify(item: TelecomClassifyRequest) -> TelecomClassifyResponse:
        async with sem:
            return await _process_single_message(item, background_tasks=background_tasks)

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
    report = await get_drift_monitor().a_evaluate_drift()
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

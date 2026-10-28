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
from app.telecom.onnx_engine import InferenceResult, get_inference_engine
from app.telecom.telecom_metrics import export_prometheus_metrics, get_metrics_tracker
from app.telecom.velocity_store import get_velocity_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telecom-intelligence"])
_background_tasks: set[asyncio.Task[Any]] = set()
_escalation_semaphore = asyncio.Semaphore(16)
MAX_TELECOM_SUBSCRIBERS = 250


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
    """Background task to commit escalated dispute record with retry resilience."""
    async with _escalation_semaphore:
        for attempt in range(3):
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
                return
            except Exception as exc:
                if attempt == 2:
                    logger.error(
                        "Failed to persist background escalated dispute %s after 3 attempts: %s",
                        dispute_id,
                        exc,
                    )
                else:
                    await asyncio.sleep(0.05 * (attempt + 1))


async def _drain_background_tasks() -> None:
    if _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)


def _spawn_escalation_task(
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
    background_tasks: BackgroundTasks | None = None,
) -> asyncio.Task[None]:
    bg_task = asyncio.create_task(
        _persist_escalated_dispute(
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
    )
    _background_tasks.add(bg_task)
    bg_task.add_done_callback(_background_tasks.discard)
    if background_tasks is not None:
        background_tasks.add_task(_drain_background_tasks)
    return bg_task


async def _process_single_message(
    req: TelecomClassifyRequest,
    event_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
    precomputed_inference: InferenceResult | None = None,
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
    inference_result = (
        precomputed_inference if precomputed_inference is not None else engine.predict(req.message)
    )

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
        _spawn_escalation_task(
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
            background_tasks=background_tasks,
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


_WARMUP_EVENTS: tuple[tuple[str, str, str, str, float], ...] = (
    (
        "+14155552671",
        "+14155559801",
        "Verizon Wireless",
        "Carrier security code: 492018. Valid for 5 minutes. Do not share this code.",
        0.08,
    ),
    (
        "+14155552672",
        "+14155559802",
        "AT&T Mobility",
        "Your appointment with Dr. Chen is confirmed for tomorrow at 10:30 AM.",
        0.06,
    ),
    (
        "+14155552673",
        "+14155559803",
        "T-Mobile USA",
        "Your pharmacy order #84920 is ready for pickup at Main St.",
        0.05,
    ),
    (
        "+14155552674",
        "+14155559804",
        "Verizon Wireless",
        "Flight UA492 boarding begins at Gate B14 in 30 minutes. Safe travels!",
        0.09,
    ),
    (
        "+14155552675",
        "+14155559805",
        "AT&T Mobility",
        "Your one-time login passcode is 773910. Never share this code with anyone.",
        0.07,
    ),
    (
        "+14155552676",
        "+14155559806",
        "T-Mobile USA",
        "Reminder: Your monthly utility statement is available in the customer portal.",
        0.11,
    ),
    (
        "+14155552677",
        "+14155559807",
        "Verizon Wireless",
        "Hi Alex, let us meet at the coffee shop on 4th Street around 2:15 PM today.",
        0.04,
    ),
    (
        "+14155552678",
        "+14155559808",
        "AT&T Mobility",
        "Your grocery delivery driver is 5 minutes away with your fresh produce order.",
        0.08,
    ),
    (
        "+14155552679",
        "+14155559809",
        "T-Mobile USA",
        "Direct deposit of $1,840.00 has been posted to your checking account today.",
        0.10,
    ),
    (
        "+14155552680",
        "+14155559810",
        "Verizon Wireless",
        "Security notice: Two-factor authentication code 918273 requested on web login.",
        0.06,
    ),
    (
        "+14155552681",
        "+14155559811",
        "AT&T Mobility",
        "Your library hold for Designing Data-Intensive Applications is ready for pickup.",
        0.05,
    ),
    (
        "+14155552682",
        "+14155559812",
        "T-Mobile USA",
        "Thank you for visiting City Dental Clinic. Your receipt has been emailed to you.",
        0.09,
    ),
    (
        "+15550001231",
        "+14155559813",
        "TextNow",
        (
            "URGENT: Chase Bank alert. Account suspended! Verify immediately at "
            "http://bit.ly/chase-verify-now to restore access now."
        ),
        0.89,
    ),
    (
        "+15550001232",
        "+14155559814",
        "Bandwidth.com",
        (
            "USPS Alert: Package 928301 held due to incomplete address. Pay $1.99 "
            "customs fee now at http://tinyurl.com/usps-fee-pay"
        ),
        0.86,
    ),
    (
        "+15550001233",
        "+14155559815",
        "Sinch Virtual",
        (
            "Exclusive Crypto VIP signal: Earn 300% guaranteed return on free "
            "bitcoin in 24h! Claim now at http://cutt.ly/crypto-vip"
        ),
        0.92,
    ),
    (
        "+15550001234",
        "+14155559816",
        "TextNow",
        (
            "IRS FINAL NOTICE: Federal arrest warrant issued for delinquent taxes. "
            "Call or verify immediately at http://bit.ly/irs-pay"
        ),
        0.94,
    ),
    (
        "+15550001235",
        "+14155559817",
        "Bandwidth.com",
        (
            "EZPass Toll Notice: You have an unpaid turnpike invoice of $6.40. "
            "Avoid a $50 late fee at http://rb.gy/ezpass-toll-now"
        ),
        0.84,
    ),
    (
        "+15550001236",
        "+14155559818",
        "Sinch Virtual",
        (
            "URGENT: Unauthorized login detected on your Wells Fargo account. "
            "Unlock immediately at https://wellsfargo-verify.xyz/auth"
        ),
        0.91,
    ),
    (
        "+15550001237",
        "+14155559819",
        "TextNow",
        (
            "FedEx Parcel Notice: Your shipment #FX9012 requires a redelivery fee "
            "of $2.50. Update billing at http://is.gd/fedex-hold"
        ),
        0.82,
    ),
    (
        "+15550001238",
        "+14155559820",
        "Bandwidth.com",
        (
            "SunPass Alert: Unpaid toll invoice requires immediate settlement to "
            "prevent registration suspension: http://t.co/sunpass9"
        ),
        0.88,
    ),
)


def seed_telecom_warmup() -> None:
    """Pre-warms in-memory SentinelPulse telemetry and drift baseline on cold startup."""
    metrics = get_metrics_tracker()
    drift = get_drift_monitor()
    if metrics.get_summary()["total_requests"] > 0:
        return

    engine = get_inference_engine()
    batch_results = engine.predict_batch([item[3] for item in _WARMUP_EVENTS])
    for idx, (
        (sender, recipient, carrier, message, calibrated_score),
        inf_res,
    ) in enumerate(zip(_WARMUP_EVENTS, batch_results, strict=False)):
        safe_message, _ = redact_text(message)
        score = max(inf_res.fraud_score, calibrated_score)
        verdict: Literal["ALLOW", "BLOCK", "FLAG"] = (
            "BLOCK" if score >= 0.75 else ("FLAG" if score >= 0.40 else "ALLOW")
        )
        synthetic_latency_ms = round(1.65 + ((idx % 7) * 0.38), 3)
        metrics.record_event(
            event_id=f"evt_warmup_{idx + 1:02d}",
            sender=_mask_phone(sender),
            recipient=_mask_phone(recipient),
            message=safe_message,
            verdict=verdict,
            fraud_score=round(score, 4),
            latency_ms=synthetic_latency_ms,
            signals=inf_res.signals,
            carrier=carrier.lower(),
            onnx_latency_ms=max(0.025, round(inf_res.latency_ms, 3)),
        )
        drift.record_observation(message, calibrated_score)


@router.post("/telecom/events/batch", response_model=TelecomBatchResponse)
async def batch_classify_telecom_messages(
    request: TelecomBatchRequest,
    background_tasks: BackgroundTasks,
) -> TelecomBatchResponse:
    """High-throughput batch ingestion endpoint using vectorized ONNX CPU inference."""
    t_batch_start = time.perf_counter()

    engine = get_inference_engine()
    batch_inferences = await asyncio.to_thread(
        engine.predict_batch,
        [item.message for item in request.events],
    )
    sem = asyncio.Semaphore(50)

    async def _bounded_classify(
        item: TelecomClassifyRequest,
        inf_res: InferenceResult,
    ) -> TelecomClassifyResponse:
        async with sem:
            return await _process_single_message(
                item,
                background_tasks=background_tasks,
                precomputed_inference=inf_res,
            )

    results = list(
        await asyncio.gather(
            *[
                _bounded_classify(item, inf_res)
                for item, inf_res in zip(request.events, batch_inferences, strict=False)
            ]
        )
    )

    batch_latency = round((time.perf_counter() - t_batch_start) * 1000.0, 2)
    return TelecomBatchResponse(
        total_processed=len(results),
        batch_latency_ms=batch_latency,
        results=results,
    )


@router.get("/telecom/metrics/summary")
async def get_telecom_metrics_summary() -> dict[str, Any]:
    """Returns rolling real-time telemetry: throughput (EPS), p50/p95/p99 latency, fraud rates."""
    seed_telecom_warmup()
    return get_metrics_tracker().get_summary()


@router.get("/telecom/drift")
async def get_telecom_drift_status() -> dict[str, Any]:
    """Returns Kolmogorov-Smirnov and Population Stability Index (PSI) drift reports."""
    seed_telecom_warmup()
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
        if len(_subscribers) >= MAX_TELECOM_SUBSCRIBERS:
            oldest_queue = next(iter(_subscribers), None)
            if oldest_queue is not None:
                _subscribers.discard(oldest_queue)
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

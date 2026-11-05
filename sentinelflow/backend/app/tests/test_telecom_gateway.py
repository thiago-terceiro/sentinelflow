"""Comprehensive unit and integration tests for SentinelPulse Telecom Intelligence Gateway."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from app.db.models import Base
from app.main import app
from app.telecom.drift_monitor import calculate_psi, get_drift_monitor
from app.telecom.onnx_engine import (
    OnnxInferenceEngine,
    compute_composite_score,
    get_inference_engine,
)
from app.telecom.velocity_store import RedisVelocityStore, get_velocity_store
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def test_onnx_inference_engine_benign_and_fraud() -> None:
    """Verifies ONNX model CPU inference, latency bounds, and verdict assignments."""
    engine = get_inference_engine()

    # 1. Benign transactional 2FA SMS
    legit_msg = "Your Google verification code is 849201. Do not share this code."
    res_legit = engine.predict(legit_msg)

    assert res_legit.verdict == "ALLOW"
    assert 0.0 <= res_legit.fraud_score < 0.40
    assert res_legit.latency_ms < 15.0  # Must meet <15ms SLA
    assert "ML:BENIGN_CLASSIFICATION" in res_legit.signals
    assert res_legit.model_version == "1.0.0"

    # 2. Urgent smishing phishing SMS
    fraud_msg = (
        "URGENT: Chase Bank alert. Account suspended! Verify immediately: "
        "http://bit.ly/chase-verify-now"
    )
    res_fraud = engine.predict(fraud_msg)

    assert res_fraud.verdict == "BLOCK"
    assert res_fraud.fraud_score >= 0.75
    assert res_fraud.latency_ms < 15.0
    assert "RULE:HIGH_RISK_SHORTLINK" in res_fraud.signals
    assert "RULE:URGENT_ACCOUNT_LOCKOUT" in res_fraud.signals
    assert "ML:HIGH_FRAUD_PROBABILITY" in res_fraud.signals


def test_regex_heuristic_rules() -> None:
    """Verifies fast-path regex rules trigger with appropriate minimum risk scores."""
    engine = get_inference_engine()

    # Delivery scam (compound indicator: carrier/package + fee/customs)
    score_deliv, sigs_deliv = engine.evaluate_heuristics(
        "USPS Alert: Package 928301 held. Pay customs fee now."
    )
    assert "RULE:DELIVERY_FEE_SCAM" in sigs_deliv
    assert score_deliv >= 0.60

    # Tax arrest threat
    score_tax, sigs_tax = engine.evaluate_heuristics(
        "IRS FINAL NOTICE: Arrest warrant issued for delinquent taxes."
    )
    assert "RULE:TAX_ARREST_THREAT" in sigs_tax
    assert score_tax >= 0.80

    # Crypto giveaway
    score_crypto, sigs_crypto = engine.evaluate_heuristics(
        "Exclusive signal: Earn guaranteed return of 300% on free bitcoin!"
    )
    assert "RULE:CRYPTO_OR_GIVEAWAY_PROMISE" in sigs_crypto
    assert score_crypto >= 0.70

    # Single benign signals: Standalone URL (low/moderate weight 0.20–0.40, no short-circuit)
    score_url, sigs_url = engine.evaluate_heuristics(
        "Please review our updated privacy policy at https://company.com/privacy-policy"
    )
    assert "RULE:STANDALONE_URL" in sigs_url
    assert 0.20 <= score_url <= 0.40
    assert "HEURISTIC:COMPOUND_SIGNALS" not in sigs_url
    assert score_url < 0.85

    # Single benign signals: Benign package / delivery update (0.20–0.40, no short-circuit)
    score_pkg, sigs_pkg = engine.evaluate_heuristics(
        "Your package is out for delivery with UPS Ground and will arrive by 5 PM."
    )
    assert "RULE:GENERIC_DELIVERY_KEYWORD" in sigs_pkg
    assert 0.20 <= score_pkg <= 0.40
    assert "HEURISTIC:COMPOUND_SIGNALS" not in sigs_pkg
    assert score_pkg < 0.85

    # Compound smishing escalation: High-risk tax threat + shortlink triggers >= 0.85
    score_compound, sigs_compound = engine.evaluate_heuristics(
        "IRS FINAL NOTICE: Arrest warrant issued. Pay taxes immediately: http://bit.ly/irs-pay"
    )
    assert "RULE:TAX_ARREST_THREAT" in sigs_compound
    assert "RULE:HIGH_RISK_SHORTLINK" in sigs_compound
    assert "HEURISTIC:COMPOUND_SIGNALS" in sigs_compound
    assert score_compound >= 0.85


@pytest.mark.asyncio
async def test_velocity_store_sliding_window_and_carrier() -> None:
    """Verifies sliding-window burst tracking and carrier reputation scoring."""
    store = get_velocity_store()
    test_sender = "+15559990001"

    # Execute 6 rapid requests from the same sender
    last_res = None
    for _ in range(6):
        last_res = await store.record_and_evaluate(
            sender=test_sender,
            carrier="TextNow",
            ip="192.0.2.1",
        )

    assert last_res is not None
    assert last_res.velocity_10s >= 5
    assert "VELOCITY:BURST_10S" in last_res.signals
    assert "CARRIER:HIGH_RISK_VOIP" in last_res.signals
    assert last_res.carrier == "textnow"
    assert last_res.carrier_risk == 0.65
    assert last_res.risk_contribution >= 0.50


@pytest.mark.asyncio
async def test_api_classify_endpoint() -> None:
    """Tests POST /v1/classify and /api/v1/telecom/classify contracts and SLAs."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Normal traffic
        normal_payload = {
            "sender": "+14155552671",
            "recipient": "+14155559876",
            "message": "Your prescription is ready for pickup at Walgreens Pharmacy.",
            "carrier": "Verizon Wireless",
            "ip": "198.51.100.10",
        }
        resp = await client.post("/v1/classify", json=normal_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["verdict"] == "ALLOW"
        assert data["fraud_score"] < 0.40
        assert data["latency_ms"] < 25.0  # SLA < 25ms
        assert "velocity" in data
        assert data["velocity"]["velocity_10s"] >= 1
        assert data["model_version"] == "1.0.0"

        # 2. High-risk smishing attack
        fraud_payload = {
            "sender": "+15550001234",
            "recipient": "+14155559876",
            "message": (
                "URGENT: Your bank account is locked! Verify at http://bit.ly/chase-verify-now"
            ),
            "carrier": "TextNow",
            "ip": "203.0.113.5",
        }
        resp_fraud = await client.post("/api/v1/telecom/classify", json=fraud_payload)
        assert resp_fraud.status_code == 200
        data_fraud = resp_fraud.json()
        assert data_fraud["verdict"] == "BLOCK"
        assert data_fraud["fraud_score"] >= 0.75
        assert len(data_fraud["signals"]) > 0


@pytest.mark.asyncio
async def test_api_batch_endpoint() -> None:
    """Tests POST /v1/events/batch high-throughput ingestion endpoint."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        events = [
            {
                "sender": f"+1555000{i:04d}",
                "recipient": "+14155550000",
                "message": f"Carrier verification security code: {1000 + i}. Valid 5 mins.",
                "carrier": "T-Mobile USA",
            }
            for i in range(10)
        ]
        resp = await client.post("/v1/events/batch", json={"events": events})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_processed"] == 10
        assert len(data["results"]) == 10
        assert data["batch_latency_ms"] < 100.0


@pytest.mark.asyncio
async def test_telecom_metrics_and_prometheus() -> None:
    """Tests GET /metrics and GET /api/v1/telecom/metrics/summary telemetry."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Verify Prometheus exposition endpoint
        prom_resp = await client.get("/metrics")
        assert prom_resp.status_code == 200
        body = prom_resp.text
        assert "telecom_requests_total" in body
        assert "telecom_latency_seconds" in body
        assert "telecom_drift_psi" in body
        assert "telecom_drift_ks_pvalue" in body
        assert "telecom_drift_status" in body

        # Verify JSON summary endpoint
        summary_resp = await client.get("/api/v1/telecom/metrics/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert "total_requests" in summary
        assert "throughput_eps" in summary
        assert "verdicts" in summary
        assert "latency" in summary
        assert "p50_ms" in summary["latency"]
        assert "p95_ms" in summary["latency"]
        assert "p99_ms" in summary["latency"]


def test_mlops_data_drift_monitor() -> None:
    """Tests Kolmogorov-Smirnov test and Population Stability Index (PSI) calculation."""
    monitor = get_drift_monitor()

    # Calculate PSI on identical distributions
    import numpy as np

    arr1 = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    psi_identical = calculate_psi(arr1, arr1)
    assert psi_identical == 0.0

    # Evaluate monitor with sample observations
    for _ in range(20):
        monitor.record_observation(
            message="Your verification code is 492018. It expires in 5 minutes.",
            fraud_score=0.15,
        )

    report = monitor.evaluate_drift()
    assert report.sample_count >= 20
    assert report.status in {"HEALTHY", "MODERATE_DRIFT", "CRITICAL_DRIFT"}
    assert report.ks_p_value >= 0.0
    assert report.psi_score >= 0.0


@pytest.fixture
async def telecom_db_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield factory
    finally:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_escalate_telecom_anomaly_creates_dispute(
    monkeypatch: Any,
    telecom_db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verifies that escalating a flagged SMS creates a DisputeRecord with anomaly metadata."""
    monkeypatch.setattr("app.api.telecom.SessionLocal", telecom_db_session_factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "sender": "+15559998877",
            "recipient": "+14155551234",
            "message": "URGENT: Your bank account is locked! Click http://scam.link to verify.",
            "carrier": "Bandwidth.com",
            "verdict": "BLOCK",
            "fraud_score": 0.95,
            "signals": ["RULE:HIGH_RISK_SHORTLINK", "ML:HIGH_FRAUD_PROBABILITY"],
            "velocity": {"velocity_10s": 15},
            "event_id": "evt_test_esc_1",
        }
        res = await client.post("/api/v1/telecom/escalate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "dispute_id" in data
        assert data["case_code"].startswith("TEL-")
        assert data["dispute_url"] == f"/disputes/{data['dispute_id']}"
        assert data["status"] == "open"


@pytest.mark.asyncio
async def test_classify_with_auto_escalate(
    monkeypatch: Any,
    telecom_db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verifies that setting escalate=True auto-creates a DisputeRecord on BLOCK or FLAG."""
    monkeypatch.setattr("app.api.telecom.SessionLocal", telecom_db_session_factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "sender": "+15551112233",
            "recipient": "+14155554321",
            "message": (
                "URGENT: Chase Bank alert. Account suspended! Verify immediately: "
                "http://bit.ly/chase-verify-now"
            ),
            "carrier": "TextNow",
            "escalate": True,
        }
        res = await client.post("/api/v1/telecom/classify", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["verdict"] == "BLOCK"
        assert data["escalated_dispute_id"] is not None
        assert data["escalated_dispute_url"] == f"/disputes/{data['escalated_dispute_id']}"


def test_onnx_predict_proba_batch_vectorized() -> None:
    """Verifies vectorized batch probability inference returns calibrated probabilities."""
    engine = get_inference_engine()
    probs = engine.predict_proba_batch(
        [
            "Your verification code is 492018. Do not share this code.",
            "URGENT: Chase Bank alert. Account suspended! Verify at http://bit.ly/chase-verify",
        ]
    )
    assert len(probs) == 2
    assert 0.0 <= probs[0] <= 1.0
    assert 0.0 <= probs[1] <= 1.0
    assert engine.predict_proba_batch([]) == []


@pytest.mark.asyncio
async def test_telecom_warmup_realistic_ratio_and_reset_endpoint() -> None:
    """Verifies warmup threat ratio (~7.5%) and permanent reset via POST /api/v1/telecom/reset."""
    from app.api.telecom import seed_telecom_warmup
    from app.telecom.telecom_metrics import get_metrics_tracker

    get_metrics_tracker().reset()
    get_drift_monitor().reset()
    seed_telecom_warmup(force=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        summary_resp = await client.get("/api/v1/telecom/metrics/summary")
        assert summary_resp.status_code == 200
        summary = summary_resp.json()
        assert summary["total_requests"] == 40
        assert summary["fraud_rate_pct"] == 7.5
        assert summary["verdicts"] == {"allow": 37, "flag": 1, "block": 2}

        drift_resp = await client.get("/api/v1/telecom/drift")
        assert drift_resp.status_code == 200
        drift = drift_resp.json()
        assert drift["status"] == "HEALTHY"
        assert drift["psi_status"] == "STABLE"

        reset_resp = await client.post("/api/v1/telecom/reset")
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()
        assert reset_data["status"] == "cleared"
        assert reset_data["metrics"]["total_requests"] == 0
        assert reset_data["metrics"]["recent_feed"] == []

        # Subsequent summary poll must NOT re-seed warmup events after reset
        after_resp = await client.get("/api/v1/telecom/metrics/summary")
        assert after_resp.status_code == 200
        after_data = after_resp.json()
        assert after_data["total_requests"] == 0
        assert after_data["recent_feed"] == []

        # Restore warmup state for any subsequent tests
        seed_telecom_warmup(force=True)


def test_composite_scoring_math_and_benign_suppression() -> None:
    """Verifies continuous gated composite scoring prevents false-positive FLAG inflation."""
    # 1. Single benign URL indicator (0.25) + low calibrated ML (0.12) + normal velocity (0.0)
    # Gated blend suppresses benign heuristic (alpha == 0), strictly yielding ALLOW (< 0.40)
    score_url_suppressed = compute_composite_score(
        heuristic_score=0.25,
        onnx_probability=0.12,
        velocity_score=0.0,
    )
    assert score_url_suppressed < 0.40
    assert score_url_suppressed == 0.12

    # 2. Benign delivery keyword (0.20) + low calibrated ML (0.08) + normal velocity (0.0)
    score_deliv_suppressed = compute_composite_score(
        heuristic_score=0.20,
        onnx_probability=0.08,
        velocity_score=0.0,
    )
    assert score_deliv_suppressed < 0.40
    assert score_deliv_suppressed == 0.08

    # 3. High-risk single rule (e.g. TAX_ARREST_THREAT = 0.80) cannot be diluted -> BLOCK (1.0)
    score_tax_override = compute_composite_score(
        heuristic_score=0.80,
        onnx_probability=0.10,
        velocity_score=0.0,
    )
    assert score_tax_override >= 0.75
    assert score_tax_override == 1.0

    # 4. Compound heuristic rule (>= 0.85) -> BLOCK (1.0)
    score_compound = compute_composite_score(
        heuristic_score=0.85,
        onnx_probability=0.05,
        velocity_score=0.0,
    )
    assert score_compound >= 0.75
    assert score_compound == 1.0

    # 5. Normal content (0.15) with active bot flood velocity (0.80) -> BLOCK
    score_velocity_block = compute_composite_score(
        heuristic_score=0.0,
        onnx_probability=0.15,
        velocity_score=0.80,
    )
    assert score_velocity_block >= 0.75
    assert score_velocity_block == 0.83

    # 6. Moderate content (0.35) with moderate burst velocity (0.50) -> FLAG (0.40 - 0.75)
    score_moderate_flag = compute_composite_score(
        heuristic_score=0.35,
        onnx_probability=0.35,
        velocity_score=0.50,
    )
    assert 0.40 <= score_moderate_flag < 0.75


def test_composite_scoring_strict_monotonicity_property() -> None:
    """Property test: Verifies compute_composite_score is strictly monotonic across [0, 1]^3."""
    grid = [i / 50.0 for i in range(51)]

    # 1. Monotonicity in P: for all P1 <= P2, S(P1, H, V) <= S(P2, H, V)
    for h in [0.0, 0.20, 0.25, 0.30, 0.40, 0.55, 0.65, 0.70, 0.75, 0.80, 0.90]:
        for v in [0.0, 0.20, 0.50, 0.80, 1.0]:
            prev_s = -1.0
            for p in grid:
                s = compute_composite_score(h, p, v)
                assert s >= prev_s - 1e-9, f"Non-monotonic in P at h={h}, p={p}, v={v}"
                prev_s = s

    # 2. Monotonicity in H: for all H1 <= H2, S(P, H1, V) <= S(P, H2, V)
    for p in [0.0, 0.10, 0.20, 0.29, 0.30, 0.50, 0.75, 1.0]:
        for v in [0.0, 0.20, 0.50, 0.80, 1.0]:
            prev_s = -1.0
            for h in grid:
                s = compute_composite_score(h, p, v)
                assert s >= prev_s - 1e-9, f"Non-monotonic in H at p={p}, h={h}, v={v}"
                prev_s = s

    # 3. Monotonicity in V: for all V1 <= V2, S(P, H, V1) <= S(P, H, V2)
    for p in [0.0, 0.20, 0.50, 0.80, 1.0]:
        for h in [0.0, 0.25, 0.55, 0.75, 0.80]:
            prev_s = -1.0
            for v in grid:
                s = compute_composite_score(h, p, v)
                assert s >= prev_s - 1e-9, f"Non-monotonic in V at p={p}, h={h}, v={v}"
                prev_s = s

    # 4. Benign boundary: H <= 0.25, P < 0.30, V == 0.0 -> strictly < 0.40 (ALLOW)
    for h in [0.0, 0.10, 0.20, 0.25]:
        for p in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.29]:
            assert compute_composite_score(h, p, 0.0) < 0.40


@pytest.mark.asyncio
async def test_multi_dimensional_velocity_tracking() -> None:
    """Verifies velocity tracking across domain/prefix dimensions for SIM-farm detection."""
    store = RedisVelocityStore(redis_url="redis://127.0.0.1:59999/9")  # In-memory mode
    phishing_domain = "chase-update-account.xyz"

    # Distributed SIM-farm: rotating sender numbers, but reusing same phishing domain
    last_res = None
    for i in range(10):
        sender_rotated = f"+1555000{i:04d}"
        msg = f"Alert: Verify account immediately at http://{phishing_domain}/login"
        last_res = await store.record_and_evaluate(
            sender=sender_rotated,
            message=msg,
        )

    assert last_res is not None
    assert last_res.domain_count_60s >= 8
    assert "VELOCITY:DOMAIN_BURST_60S" in last_res.signals
    assert last_res.risk_contribution >= 0.30
    assert last_res.url_domain == phishing_domain


@pytest.mark.asyncio
async def test_chaos_redis_connection_refused_fallback() -> None:
    """Failure Mode 1: Verifies immediate fail-open to in-memory deque on Redis refusal."""
    dead_store = RedisVelocityStore(redis_url="redis://127.0.0.1:59999/9")

    # First call encounters connection error and immediately fails open
    res1 = await dead_store.record_and_evaluate(
        sender="+15551110001",
        ip="192.0.2.10",
    )
    assert res1.velocity_10s == 1
    assert dead_store._use_in_memory_fallback is True

    # Second call continues in-memory without attempting failed network socket
    res2 = await dead_store.record_and_evaluate(
        sender="+15551110001",
        ip="192.0.2.10",
    )
    assert res2.velocity_10s == 2


@pytest.mark.asyncio
async def test_chaos_redis_socket_timeout_circuit_breaker() -> None:
    """Failure Mode 2: Verifies that elevated latency/timeout triggers the 30s circuit breaker."""
    store = RedisVelocityStore(redis_url="redis://127.0.0.1:59999/9")

    # Mock client pipeline to raise a socket TimeoutError
    mock_client = MagicMock()
    mock_pipeline = MagicMock()

    async def raise_timeout(*args: Any, **kwargs: Any) -> Any:
        raise TimeoutError("Simulated Redis socket timeout exceeding 15ms SLA budget")

    mock_pipeline.__aenter__.return_value = mock_pipeline
    mock_pipeline.__aexit__.side_effect = raise_timeout
    mock_client.pipeline.return_value = mock_pipeline

    store._client = mock_client
    store._use_in_memory_fallback = False

    res = await store.record_and_evaluate(sender="+15552220002")
    assert res.velocity_10s == 1
    # Circuit breaker must be active
    assert store._use_in_memory_fallback is True


@pytest.mark.asyncio
async def test_chaos_redis_circuit_breaker_automatic_recovery() -> None:
    """Failure Mode 3: Verifies automatic recovery after circuit breaker window expires."""
    store = RedisVelocityStore(redis_url="redis://127.0.0.1:59999/9")
    store._circuit_cooldown_seconds = 0.05  # Short 50ms cooldown for fast test

    # Trip circuit breaker
    store._use_in_memory_fallback = True
    assert store._use_in_memory_fallback is True

    # Wait for cooldown to elapse
    await asyncio.sleep(0.06)

    # Circuit breaker has healed and will attempt normal path
    assert store._use_in_memory_fallback is False


def test_chaos_onnx_inference_failure_fallback_to_heuristics() -> None:
    """Failure Mode 4: Verifies ONNX session failure gracefully falls back to heuristic engine."""
    engine = OnnxInferenceEngine()

    # Mock session.run to simulate C++ runtime exception
    mock_session = MagicMock()
    mock_session.run.side_effect = RuntimeError("Simulated AVX-512 ONNX CPU fault")
    engine._session = mock_session
    engine.session = mock_session

    fraud_text = "IRS FINAL NOTICE: Delinquent tax payment due. Arrest warrant issued!"
    res = engine.predict(fraud_text)

    assert "ENGINE:ONNX_FALLBACK" in res.signals
    assert "RULE:TAX_ARREST_THREAT" in res.signals
    assert res.verdict == "BLOCK"
    assert res.fraud_score >= 0.75


@pytest.mark.asyncio
async def test_chaos_multi_worker_degraded_counter_isolation() -> None:
    """Failure Mode 5: Verifies documented multi-worker degraded counter isolation trade-off."""
    # Worker 1 and Worker 2 run in isolated fallback mode (simulating separate Uvicorn processes)
    worker_1 = RedisVelocityStore(redis_url="redis://127.0.0.1:59999/9")
    worker_2 = RedisVelocityStore(redis_url="redis://127.0.0.1:59999/9")
    target_sender = "+15558889999"

    # Round-robin: 3 requests to worker 1, 3 requests to worker 2 (6 total)
    for _ in range(3):
        await worker_1.record_and_evaluate(sender=target_sender)
        await worker_2.record_and_evaluate(sender=target_sender)

    # Documented trade-off: each worker maintains independent in-memory state
    res_w1 = await worker_1.record_and_evaluate(sender=target_sender)
    res_w2 = await worker_2.record_and_evaluate(sender=target_sender)

    # Each worker has recorded 4 events locally (not 8)
    assert res_w1.velocity_10s == 4
    assert res_w2.velocity_10s == 4


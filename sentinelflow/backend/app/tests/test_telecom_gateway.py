"""Comprehensive unit and integration tests for SentinelPulse Telecom Intelligence Gateway."""

from __future__ import annotations

import httpx
import pytest
from app.main import app
from app.telecom.drift_monitor import calculate_psi, get_drift_monitor
from app.telecom.onnx_engine import get_inference_engine
from app.telecom.velocity_store import get_velocity_store


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

    # Delivery scam
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

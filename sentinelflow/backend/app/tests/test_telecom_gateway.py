"""Comprehensive unit and integration tests for SentinelPulse Telecom Intelligence Gateway."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import httpx
import numpy as np
import pytest
from app.db.models import Base
from app.main import app
from app.telecom.drift_monitor import calculate_psi, get_drift_monitor
from app.telecom.onnx_engine import (
    HEURISTIC_RULES,
    OnnxInferenceEngine,
    compute_composite_score,
    evaluate_heuristics,
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
async def test_evaluation_live_runtime_scoring_parity() -> None:
    """Verifies 100% numerical scoring parity between evaluation scripts and live runtime.

    Tests ambiguous compound smishing messages to confirm that:
    1. evaluate_model.compute_heuristic_score(msg)
    2. onnx_engine.evaluate_heuristics(msg)[0]
    3. engine.predict(msg).heuristic_score and fraud_score
    4. live POST /v1/classify endpoint
    produce identical numerical outputs without drift.
    """
    from app.telecom.evaluate_model import compute_heuristic_score as eval_heuristic_fn

    engine = get_inference_engine()

    test_messages = [
        # Compound delivery fee scam + shortlink
        "USPS: Package 928301 delivery exception. Unpaid customs fee of $2.40: http://bit.ly/usps-fee",
        # Urgent account lockout + suspicious TLD
        "URGENT: Your Bank account has been locked. Verify identity immediately: http://bank-secure.xyz",
        # Explicit standalone override block rule (RULE:TAX_ARREST_THREAT = 0.80)
        "IRS FINAL NOTICE: Arrest warrant issued for delinquent taxes. Call immediately.",
        # Benign transactional update (no compound escalation)
        "Your package is out for delivery with UPS Ground and will arrive by 5 PM.",
        # Standalone shortlink with conversational text
        "Hey! Check out these photos from our trip: http://bit.ly/vacation-pics-2026",
    ]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for idx, msg in enumerate(test_messages):
            # 1. Evaluation script heuristic calculation
            eval_h = eval_heuristic_fn(msg)

            # 2. Engine heuristic evaluation
            engine_h, engine_sigs = engine.evaluate_heuristics(msg)
            assert abs(eval_h - engine_h) < 1e-6, (
                f"Heuristic mismatch for msg {idx}: eval={eval_h}, engine={engine_h}"
            )

            # 3. Engine synchronous inference
            engine_res = engine.predict(msg)
            assert abs(engine_res.heuristic_score - engine_h) < 1e-6

            # 4. Live runtime API invocation (using unique sender per request to ensure V=0.0)
            payload = {
                "sender": f"+1555888{idx:04d}",
                "recipient": "+14155551234",
                "message": msg,
                "carrier": "Verizon Wireless",
                "ip": f"198.51.100.{100 + idx}",
            }
            resp = await client.post("/v1/classify", json=payload)
            assert resp.status_code == 200
            data = resp.json()

            # Verify identical verdict and composite fraud score (under V=0.0)
            assert data["verdict"] == engine_res.verdict
            assert abs(data["fraud_score"] - engine_res.fraud_score) < 1e-4, (
                f"Composite score parity failure for msg {idx}: "
                f"api={data['fraud_score']}, engine={engine_res.fraud_score}"
            )


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


def test_composite_scoring_monotonic_non_decreasing_property() -> None:
    """Property test: Verifies compute_composite_score is monotonic non-decreasing
    and bounded on [0, 1]^3.
    """
    grid = [i / 50.0 for i in range(51)]

    # 1. Monotonicity in P: for all P1 <= P2, S(P1, H, V) <= S(P2, H, V)
    for h in [0.0, 0.20, 0.25, 0.30, 0.40, 0.55, 0.65, 0.70, 0.75, 0.80, 0.90]:
        for v in [0.0, 0.20, 0.50, 0.80, 1.0]:
            prev_s = -1.0
            for p in grid:
                s = compute_composite_score(h, p, v)
                assert s >= prev_s - 1e-9, f"Non-monotonic in P at h={h}, p={p}, v={v}"
                assert 0.0 <= s <= 1.0, f"Score out of bounds: {s} at h={h}, p={p}, v={v}"
                prev_s = s

    # 2. Monotonicity in H: for all H1 <= H2, S(P, H1, V) <= S(P, H2, V)
    for p in [0.0, 0.10, 0.20, 0.29, 0.30, 0.50, 0.75, 1.0]:
        for v in [0.0, 0.20, 0.50, 0.80, 1.0]:
            prev_s = -1.0
            for h in grid:
                s = compute_composite_score(h, p, v)
                assert s >= prev_s - 1e-9, f"Non-monotonic in H at p={p}, h={h}, v={v}"
                assert 0.0 <= s <= 1.0, f"Score out of bounds: {s} at p={p}, h={h}, v={v}"
                prev_s = s

    # 3. Monotonicity in V: for all V1 <= V2, S(P, H, V1) <= S(P, H, V2)
    for p in [0.0, 0.20, 0.50, 0.80, 1.0]:
        for h in [0.0, 0.25, 0.55, 0.75, 0.80]:
            prev_s = -1.0
            for v in grid:
                s = compute_composite_score(h, p, v)
                assert s >= prev_s - 1e-9, f"Non-monotonic in V at p={p}, h={h}, v={v}"
                assert 0.0 <= s <= 1.0, f"Score out of bounds: {s} at p={p}, h={h}, v={v}"
                prev_s = s

    # 4. Benign boundary: H <= 0.25, P < 0.30, V == 0.0 -> strictly < 0.40 (ALLOW)
    for h in [0.0, 0.10, 0.20, 0.25]:
        for p in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.29]:
            assert compute_composite_score(h, p, 0.0) < 0.40

    # 5. Boundary behavior at H >= 0.80 forces immediate BLOCK (S = 1.0)
    for p in [0.0, 0.20, 0.50, 0.90, 1.0]:
        for v in [0.0, 0.30, 0.70, 1.0]:
            assert compute_composite_score(0.80, p, v) == 1.0
            assert compute_composite_score(0.95, p, v) == 1.0


def test_single_rule_heuristic_short_circuit_invariant() -> None:
    """Verifies that RULE:TAX_ARREST_THREAT (0.80) is the only single rule reaching H >= 0.80."""
    high_rules = [
        (name, weight)
        for name, _, weight in HEURISTIC_RULES
        if weight >= 0.80
    ]
    # Exactly one single rule should reach 0.80 independently
    assert len(high_rules) == 1
    assert high_rules[0][0] == "RULE:TAX_ARREST_THREAT"
    assert high_rules[0][1] == 0.80

    # All other rules must be strictly < 0.80
    lower_rules = [
        (name, weight)
        for name, _, weight in HEURISTIC_RULES
        if name != "RULE:TAX_ARREST_THREAT"
    ]
    for name, weight in lower_rules:
        assert weight <= 0.75, f"Rule {name} has weight {weight} >= 0.80"


def test_template_family_group_leakage_prevention() -> None:
    """Verifies that template-family grouping strictly prevents cross-fold leakage."""
    from app.telecom.train_onnx_model import build_augmented_dataset
    from sklearn.model_selection import StratifiedGroupKFold

    # 1. Synthetic test: create template variants and verify split prevents family leakage
    toy_texts = [
        "Variant A1 of template Alpha",
        "Variant A2 of template Alpha",
        "Variant B1 of template Beta",
        "Variant B2 of template Beta",
        "Variant G1 of template Gamma",
        "Variant G2 of template Gamma",
        "Variant D1 of template Delta",
        "Variant D2 of template Delta",
    ]
    toy_labels = [0, 0, 1, 1, 0, 0, 1, 1]
    toy_groups = [
        "group_alpha", "group_alpha",
        "group_beta", "group_beta",
        "group_gamma", "group_gamma",
        "group_delta", "group_delta",
    ]

    sgkf = StratifiedGroupKFold(n_splits=2, shuffle=True, random_state=42)
    for tr_idx, v_idx in sgkf.split(toy_texts, toy_labels, groups=toy_groups):
        tr_g = {toy_groups[i] for i in tr_idx}
        v_g = {toy_groups[i] for i in v_idx}
        assert tr_g.isdisjoint(v_g), "Synthetic template variant leaked between train and val"

    # 2. Production dataset test: verify actual dataset split
    texts, labels, groups = build_augmented_dataset()
    assert len(texts) == len(labels) == len(groups)
    assert len(set(groups)) >= 100

    sgkf_prod = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    train_idx, val_idx = next(sgkf_prod.split(texts, labels, groups=groups))
    groups_train = {groups[i] for i in train_idx}
    groups_val = {groups[i] for i in val_idx}
    assert groups_train.isdisjoint(groups_val), "Production template family leakage detected"


def test_production_runtime_vs_evaluation_scoring_parity() -> None:
    """Verifies scoring parity between production runtime inference and evaluation scoring."""
    engine = get_inference_engine()

    test_messages = [
        "Your Google verification code is 849201. Do not share this code.",
        "URGENT: Chase Bank alert. Account suspended! Verify at http://bit.ly/chase-verify-now",
        "USPS Alert: Package 928301 held. Pay customs fee now.",
        "IRS FINAL NOTICE: Arrest warrant issued for delinquent taxes.",
        "Please review our updated privacy policy at https://company.com/privacy-policy",
        "Your package is out for delivery with UPS Ground and will arrive by 5 PM.",
        "Dinner was delicious, thanks for having us over!",
        "You have (1) pending package awaiting clearance. Confirm: http://dhl-clearance.net",
    ]

    for msg in test_messages:
        # Production runtime scoring (content-only, velocity=0)
        prod_res = engine.predict(msg)

        # Evaluation scoring path
        eval_h, eval_signals = evaluate_heuristics(msg)
        eval_p = engine.predict_proba_batch([msg])[0]
        eval_composite = compute_composite_score(
            heuristic_score=eval_h,
            onnx_probability=eval_p,
            velocity_score=0.0,
        )

        # Both paths must match to numerical precision
        assert abs(prod_res.fraud_score - eval_composite) < 1e-6, (
            f"Composite mismatch on '{msg}': prod={prod_res.fraud_score}, eval={eval_composite}"
        )
        assert abs(prod_res.heuristic_score - eval_h) < 1e-6, (
            f"Heuristic mismatch on '{msg}': prod={prod_res.heuristic_score}, eval={eval_h}"
        )


def test_calibrated_classifier_cv_platt_parity() -> None:
    """Verifies Platt sigmoid calibration parity between scikit-learn
    and the exported ONNX model.
    """
    from pathlib import Path

    from app.telecom.train_onnx_model import build_augmented_dataset
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    engine = get_inference_engine()
    model_path = Path("app/telecom/models/sms_fraud_model.onnx")
    if not model_path.exists():
        model_path = Path("sentinelflow/backend/app/telecom/models/sms_fraud_model.onnx")

    assert model_path.exists(), "Exported ONNX model artifact must exist"

    sample_texts = [
        "Your security code is 849201. Do not share.",
        "URGENT: Chase Bank alert. Account suspended! Verify at http://bit.ly/chase",
        "Hey! Are you still free for lunch today?",
        "Toll violation notice: Pay $4.50 now to avoid suspension: http://toll-pay.xyz",
        "Bitstamp: Withdrawal of 2.50 ETH completed to wallet address 0x71C... TxId available in account history.",
    ]

    # ONNX probabilities
    onnx_probs = engine.predict_proba_batch(sample_texts)
    for p in onnx_probs:
        assert 0.0 <= p <= 1.0, f"ONNX probability {p} outside [0, 1]"

    # Quick scikit-learn reference pipeline with aligned token pattern
    texts, labels, _ = build_augmented_dataset()
    base_clf = LogisticRegression(C=1.5, class_weight="balanced", max_iter=1000, random_state=42)
    calibrated_clf = CalibratedClassifierCV(base_clf, method="sigmoid", cv=5)
    pipe = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                max_features=2500,
                token_pattern=r"\b[a-zA-Z0-9_]+\b",
            ),
        ),
        ("clf", calibrated_clf),
    ])
    pipe.fit(texts, labels)
    sk_probs = pipe.predict_proba(sample_texts)[:, 1].tolist()

    for p_onnx, p_sk in zip(onnx_probs, sk_probs, strict=True):
        assert abs(p_onnx - p_sk) < 1e-5, f"Calibration parity drift: ONNX={p_onnx}, Sklearn={p_sk}"


def test_onnx_sklearn_full_benchmark_parity() -> None:
    """Verifies ONNX Runtime vs scikit-learn probability parity across all 400 benchmark samples."""
    import json
    from pathlib import Path

    from app.telecom.evaluate_model import get_held_out_evaluation_set
    from app.telecom.train_onnx_model import build_augmented_dataset
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    engine = get_inference_engine()
    benchmark_texts, _ = get_held_out_evaluation_set()
    assert len(benchmark_texts) == 400

    # Fit production-equivalent scikit-learn reference pipeline
    texts, labels, _ = build_augmented_dataset()
    calibrated_clf = CalibratedClassifierCV(
        estimator=LogisticRegression(C=1.5, class_weight="balanced", max_iter=1000, random_state=42),
        method="sigmoid",
        cv=5,
    )
    pipe = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                max_features=2500,
                token_pattern=r"\b[a-zA-Z0-9_]+\b",
            ),
        ),
        ("clf", calibrated_clf),
    ])
    pipe.fit(texts, labels)

    sk_probs = pipe.predict_proba(benchmark_texts)[:, 1]
    onnx_probs = np.array(engine.predict_proba_batch(benchmark_texts))

    abs_diffs = np.abs(sk_probs - onnx_probs)
    max_diff = float(np.max(abs_diffs))
    mean_diff = float(np.mean(abs_diffs))
    large_diff_count = int(np.sum(abs_diffs > 1e-5))

    assert max_diff < 1e-5, f"Maximum ONNX/Sklearn probability divergence exceeded 1e-5: {max_diff}"
    assert mean_diff < 1e-6, f"Mean ONNX/Sklearn probability divergence exceeded 1e-6: {mean_diff}"
    assert large_diff_count == 0, f"Found {large_diff_count} samples with divergence > 1e-5"

    # Decision parity: 100% agreement (400/400) across all thresholds (0.40, 0.50, 0.75)
    sk_decision = sk_probs >= 0.50
    onnx_decision = onnx_probs >= 0.50
    assert np.array_equal(sk_decision, onnx_decision), "Decision disparity at binary threshold 0.50"

    sk_tier2 = sk_probs >= 0.75
    onnx_tier2 = onnx_probs >= 0.75
    assert np.array_equal(sk_tier2, onnx_tier2), "Decision disparity at Tier 2 threshold 0.75"

    tier1_crossings = int(np.sum((sk_probs >= 0.40) != (onnx_probs >= 0.40)))
    assert tier1_crossings == 0, f"Unexpected decision disparity at Tier 1 (0.40): {tier1_crossings} samples"

    # Verify canonical 400-row sample-level artifact exists and has 100% verdict parity
    pred_path = Path("app/telecom/benchmark_predictions_400.json")
    if not pred_path.exists():
        pred_path = Path("sentinelflow/backend/app/telecom/benchmark_predictions_400.json")
    assert pred_path.exists(), "Canonical 400-row benchmark_predictions_400.json artifact must exist"
    rows = json.loads(pred_path.read_text(encoding="utf-8"))
    assert len(rows) == 400
    assert all(r["verdict_match"] is True for r in rows), "Every sample in benchmark_predictions_400.json must match verdicts"
    assert max(r["prob_abs_diff"] for r in rows) < 1e-5


def test_template_family_grouping_under_and_over_grouping() -> None:
    """Verifies template family extractor prevents both under-grouping and over-grouping."""
    from app.telecom.train_onnx_model import extract_template_family_id

    # 1. Under-grouping prevention: Templates that differ only by brand/entity name MUST share group
    chase_alert = "URGENT: Chase security alert! Unusual sign-in detected. Confirm identity: http://verify.info"
    wells_alert = "URGENT: Wells Fargo security alert! Unusual sign-in detected. Confirm identity: http://verify.info"
    citi_alert = "URGENT: Citibank security alert! Unusual sign-in detected. Confirm identity: http://verify.info"

    fam_chase = extract_template_family_id(chase_alert, 1)
    fam_wells = extract_template_family_id(wells_alert, 1)
    fam_citi = extract_template_family_id(citi_alert, 1)

    assert fam_chase == fam_wells == fam_citi, (
        f"Under-grouping detected: Different family IDs for identical brand templates: "
        f"{fam_chase} vs {fam_wells} vs {fam_citi}"
    )

    # 2. Over-grouping prevention: Structurally distinct templates MUST remain in distinct families
    msg_2fa = "Your verification code is 849201. It expires in 5 minutes."
    msg_statement = "Your checking account monthly statement is ready to view."
    msg_arrest = "IRS FINAL NOTICE: You owe delinquent taxes. Arrest warrant issued."
    msg_flight = "Flight confirmation #4020. Check-in opens 24 hours prior."

    fams = {
        extract_template_family_id(msg_2fa, 0),
        extract_template_family_id(msg_statement, 0),
        extract_template_family_id(msg_arrest, 1),
        extract_template_family_id(msg_flight, 0),
    }
    assert len(fams) == 4, f"Over-grouping detected: distinct messages merged into {len(fams)} families"


def test_template_family_grouping_cross_validation_disjointness() -> None:
    """Verifies that all 5 cross-validation folds have strictly zero template family leakage."""
    from app.telecom.train_onnx_model import build_augmented_dataset
    from sklearn.model_selection import StratifiedGroupKFold

    texts, labels, template_family_ids = build_augmented_dataset()
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)

    for fold, (train_idx, val_idx) in enumerate(sgkf.split(texts, labels, groups=template_family_ids)):
        train_groups = {template_family_ids[i] for i in train_idx}
        val_groups = {template_family_ids[i] for i in val_idx}

        overlap = train_groups.intersection(val_groups)
        assert len(overlap) == 0, f"Fold {fold} has {len(overlap)} overlapping template families: {overlap}"

        y_train = [labels[i] for i in train_idx]
        y_val = [labels[i] for i in val_idx]
        assert y_train.count(0) > 0 and y_train.count(1) > 0, f"Fold {fold} train split has empty class"
        assert y_val.count(0) > 0 and y_val.count(1) > 0, f"Fold {fold} val split has empty class"


def test_family_impersonation_rule_precision_and_alternative_channels() -> None:
    """Verifies refined RULE:FAMILY_IMPERSONATION_MESSAGING_LURE precision and coverage."""
    engine = get_inference_engine()

    # 1. Legitimate phone repair notifications MUST NOT trigger the rule and MUST be ALLOW
    legit_repairs = [
        "Hi John, your broken phone screen is repaired and ready for pickup. Message us on WhatsApp for questions.",
        "Repair quote: Your cracked screen repair is completed at the service center. Technician note on WhatsApp.",
        "Your mobile device repair is ready for pickup at our Main Street counter.",
    ]
    for msg in legit_repairs:
        score, signals = engine.evaluate_heuristics(msg)
        assert "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE" not in signals, (
            f"False positive rule trigger on repair message: {msg}"
        )
        res = engine.predict(msg)
        assert res.verdict == "ALLOW", f"Repair message not ALLOW: {msg} -> {res.verdict}"

    # 2. Casual conversations about broken phones MUST NOT trigger the rule
    casual_chats = [
        "Hey, my phone broke so I'm using an old one, text me on WhatsApp",
        "Can you pick up my repaired phone from the shop?",
    ]
    for msg in casual_chats:
        score, signals = engine.evaluate_heuristics(msg)
        assert "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE" not in signals, (
            f"False positive rule trigger on casual chat: {msg}"
        )

    # 3. Adversarial smishing family lures (WhatsApp redirection) MUST trigger
    smish_whatsapp = (
        "Hey mom my phone screen just cracked completely, borrowing friend's phone. "
        "Text my temporary WhatsApp: wa.me/19175552000"
    )
    score, signals = engine.evaluate_heuristics(smish_whatsapp)
    assert "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE" in signals
    assert score >= 0.65

    # 4. Alternative payment channel smishing lures (Zelle, Venmo) MUST trigger
    smish_venmo = "Hi dad, dropped my phone in water, using temporary number. Please send $350 via Venmo for emergency rent."
    score_v, signals_v = engine.evaluate_heuristics(smish_venmo)
    assert "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE" in signals_v
    assert score_v >= 0.65

    smish_zelle = "Hey mum, broke my phone and lost my SIM. Need to pay an urgent bill, can you transfer $450 to my Zelle?"
    score_z, signals_z = engine.evaluate_heuristics(smish_zelle)
    assert "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE" in signals_z
    assert score_z >= 0.65


def test_legitimate_bank_fraud_alerts_allow_verdict() -> None:
    """Verifies that legitimate two-way interactive bank fraud verification alerts pass with ALLOW."""
    engine = get_inference_engine()

    benign_bank_alerts = [
        "Chase Fraud Alert: Did you attempt $35.50 at Chevron? Reply YES or NO. Msg&data rates apply.",
        "Wells Fargo Fraud Alert: Did you attempt $89.20 at Target? Reply YES or NO.",
        "Citi Security Alert: Unusual charge of $120.00 at Walmart. Text 1 if authorized, 2 if not.",
        "Bank of America Alert: Did you authorize $45.00 transaction at Shell? Reply Y or N. FreeMsg.",
    ]
    for msg in benign_bank_alerts:
        res = engine.predict(msg)
        assert res.verdict == "ALLOW", (
            f"Legitimate bank alert received {res.verdict} (fraud_score={res.fraud_score}): {msg}"
        )
        assert res.fraud_score < 0.40


def test_mathematical_monotonicity_and_h065_derivation() -> None:
    """Verifies composite scoring mathematical invariants and H=0.65 escalation threshold."""
    # 1. H=0.65 with P=0.0 MUST NOT trigger Tier 1 (0.40)
    score_p0 = compute_composite_score(heuristic_score=0.65, onnx_probability=0.0, velocity_score=0.0)
    assert score_p0 == 0.3325, f"Expected exactly 0.3325, got {score_p0}"
    assert score_p0 < 0.40, "H=0.65 alone must NOT escalate to Tier 1 without baseline ML suspicion"

    # 2. P required to reach 0.40 with H=0.65 is ~0.1012
    score_p_just_below = compute_composite_score(heuristic_score=0.65, onnx_probability=0.10, velocity_score=0.0)
    assert score_p_just_below < 0.40

    score_p_reaches_tier1 = compute_composite_score(heuristic_score=0.65, onnx_probability=0.1012, velocity_score=0.0)
    assert score_p_reaches_tier1 >= 0.40

    # 3. Authoritative override H >= 0.80 forces S=1.0 regardless of P
    assert compute_composite_score(heuristic_score=0.80, onnx_probability=0.0, velocity_score=0.0) == 1.0
    assert compute_composite_score(heuristic_score=0.85, onnx_probability=0.0, velocity_score=0.0) == 1.0


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


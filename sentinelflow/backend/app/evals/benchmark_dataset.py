from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_code: str
    title: str
    narrative: str
    amount: float
    currency: str
    customer_id: str
    merchant_id: str
    attributes: dict[str, Any]
    expected_recommendation: str
    expected_risk_min: float
    expected_risk_max: float
    expected_evidence_categories: tuple[str, ...]
    reviewer_guidance: str | None = None
    evaluation_category: str = "core_decision"


GOLDEN_BENCHMARK_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        case_code="EVAL-001",
        title="Account Takeover High Velocity Fraud",
        narrative=(
            "Customer (victim.alert@example.com) disputes $4,899 charge on card "
            "4532-0151-1283-0366 from unfamiliar device located 6800km away with 3DS OTP bypass."
        ),
        amount=4899.0,
        currency="USD",
        customer_id="cust-eval-001",
        merchant_id="merch-eval-001",
        attributes={
            "tags": ["fraud", "high_value", "account_takeover"],
            "transaction": {
                "velocity_24h": 12,
                "geo_anomaly": True,
                "authorization_events": ["otp_bypass"],
            },
            "customer": {"prior_disputes": 0, "prior_fraud_signals": 3, "tenure_years": 1},
            "device": {"recognized_device": False, "ip_velocity": 18, "geo_distance_km": 6800},
            "merchant": {"merchant_risk": 0.65, "chargeback_rate": 0.09},
        },
        expected_recommendation="deny",
        expected_risk_min=0.70,
        expected_risk_max=1.00,
        expected_evidence_categories=("transaction", "customer", "device", "merchant"),
        evaluation_category="fraud_detection",
    ),
    BenchmarkCase(
        case_code="EVAL-002",
        title="Legitimate Travel Booking (Friendly Fraud)",
        narrative=(
            "Customer disputes airline ticket. Long account tenure, "
            "recognized device, verified 3DS authentication."
        ),
        amount=1450.0,
        currency="USD",
        customer_id="cust-eval-002",
        merchant_id="merch-eval-002",
        attributes={
            "tags": ["travel", "friendly_fraud"],
            "transaction": {
                "velocity_24h": 1,
                "geo_anomaly": False,
                "authorization_events": ["3ds_success"],
            },
            "customer": {"prior_disputes": 0, "prior_fraud_signals": 0, "tenure_years": 7},
            "device": {"recognized_device": True, "ip_velocity": 1, "geo_distance_km": 8},
            "merchant": {"merchant_risk": 0.15, "chargeback_rate": 0.01},
        },
        expected_recommendation="approve",
        expected_risk_min=0.00,
        expected_risk_max=0.45,
        expected_evidence_categories=("transaction", "customer", "device"),
        evaluation_category="legitimate_verification",
    ),
    BenchmarkCase(
        case_code="EVAL-003",
        title="Ambiguous Digital Subscription with Conflicting Signals",
        narrative=(
            "Customer reports recurring digital subscription. Address matches, "
            "but customer claims cancellation 2 months ago."
        ),
        amount=389.0,
        currency="USD",
        customer_id="cust-eval-003",
        merchant_id="merch-eval-003",
        attributes={
            "tags": ["ambiguous", "subscription"],
            "transaction": {
                "velocity_24h": 2,
                "geo_anomaly": False,
                "authorization_events": ["recurring_token"],
            },
            "customer": {"prior_disputes": 2, "prior_fraud_signals": 0, "tenure_years": 3},
            "device": {"recognized_device": True, "ip_velocity": 2, "geo_distance_km": 0},
            "merchant": {"merchant_risk": 0.35, "chargeback_rate": 0.04},
        },
        expected_recommendation="escalate",
        expected_risk_min=0.30,
        expected_risk_max=0.75,
        expected_evidence_categories=("transaction", "customer", "merchant"),
        evaluation_category="ambiguous_triage",
    ),
    BenchmarkCase(
        case_code="EVAL-004",
        title="Human Steering Guidance Alignment",
        narrative=(
            "Customer disputes marketplace merchant charge. Telemetry appears borderline, "
            "but reviewer provides specific directive to examine merchant risk profile."
        ),
        amount=1850.0,
        currency="USD",
        customer_id="cust-eval-004",
        merchant_id="merch-eval-004",
        attributes={
            "tags": ["steering_test", "marketplace"],
            "transaction": {
                "velocity_24h": 3,
                "geo_anomaly": True,
                "authorization_events": ["3ds_challenge"],
            },
            "customer": {"prior_disputes": 1, "prior_fraud_signals": 1, "tenure_years": 2},
            "device": {"recognized_device": False, "ip_velocity": 5, "geo_distance_km": 450},
            "merchant": {"merchant_risk": 0.58, "chargeback_rate": 0.07},
        },
        expected_recommendation="deny",
        expected_risk_min=0.50,
        expected_risk_max=0.95,
        expected_evidence_categories=("merchant", "device", "transaction"),
        reviewer_guidance=(
            "Focus specifically on merchant chargeback rate and cross-reference "
            "with the customer geo distance anomaly for SSN 123-45-6789."
        ),
        evaluation_category="human_steering",
    ),
)

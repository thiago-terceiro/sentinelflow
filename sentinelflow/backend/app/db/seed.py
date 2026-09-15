from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from app.db.models import DisputeRecord
from app.db.session import SessionLocal
from sqlalchemy import select

CASES: list[dict[str, Any]] = [
    {
        "case_code": "SF-A",
        "title": "Obvious fraud on unknown device",
        "narrative": "Customer reports a high-value electronics purchase they did not authorize.",
        "customer_id": "cust-001",
        "merchant_id": "merch-001",
        "amount": 4899.0,
        "status": "open",
        "attributes": {
            "tags": ["fraud", "high_value"],
            "transaction": {
                "velocity_24h": 9,
                "geo_anomaly": True,
                "authorization_events": ["otp_bypass"],
            },
            "customer": {"prior_disputes": 1, "prior_fraud_signals": 2, "tenure_years": 1},
            "device": {"recognized_device": False, "ip_velocity": 14, "geo_distance_km": 6800},
            "merchant": {"merchant_risk": 0.61, "chargeback_rate": 0.08},
        },
    },
    {
        "case_code": "SF-B",
        "title": "Legitimate high-value travel booking",
        "narrative": "Customer disputes a travel charge but history suggests it may be valid.",
        "customer_id": "cust-002",
        "merchant_id": "merch-002",
        "amount": 2200.0,
        "status": "open",
        "attributes": {
            "tags": ["travel"],
            "transaction": {
                "velocity_24h": 1,
                "geo_anomaly": False,
                "authorization_events": ["3ds_success"],
            },
            "customer": {"prior_disputes": 0, "prior_fraud_signals": 0, "tenure_years": 8},
            "device": {"recognized_device": True, "ip_velocity": 1, "geo_distance_km": 12},
            "merchant": {"merchant_risk": 0.18, "chargeback_rate": 0.01},
        },
    },
    {
        "case_code": "SF-C",
        "title": "Ambiguous digital goods purchase",
        "narrative": "Conflicting telemetry leaves the claim unresolved.",
        "customer_id": "cust-003",
        "merchant_id": "merch-003",
        "amount": 799.0,
        "status": "open",
        "attributes": {
            "tags": ["ambiguous"],
            "transaction": {
                "velocity_24h": 3,
                "geo_anomaly": True,
                "authorization_events": ["avs_match"],
            },
            "customer": {"prior_disputes": 1, "prior_fraud_signals": 0, "tenure_years": 4},
            "device": {"recognized_device": False, "ip_velocity": 2, "geo_distance_km": 140},
            "merchant": {"merchant_risk": 0.25, "chargeback_rate": 0.03},
        },
    },
    {
        "case_code": "SF-D",
        "title": "Analyzer failure resilience case",
        "narrative": "Case used to verify investigation continues when an analyzer is unavailable.",
        "customer_id": "cust-004",
        "merchant_id": "merch-004",
        "amount": 1600.0,
        "status": "open",
        "attributes": {
            "tags": ["analyzer_failure"],
            "transaction": {
                "velocity_24h": 4,
                "geo_anomaly": False,
                "authorization_events": ["3ds_challenge"],
            },
            "customer": {"prior_disputes": 0, "prior_fraud_signals": 1, "tenure_years": 2},
            "device": {"recognized_device": True, "ip_velocity": 6, "geo_distance_km": 45},
            "merchant": {"merchant_risk": 0.44, "chargeback_rate": 0.06},
        },
    },
    {
        "case_code": "SF-E",
        "title": "Contradictory analyzer signals",
        "narrative": "Two analyzers disagree on the likelihood of fraud.",
        "customer_id": "cust-005",
        "merchant_id": "merch-005",
        "amount": 1299.0,
        "status": "open",
        "attributes": {
            "tags": ["contradiction"],
            "transaction": {
                "velocity_24h": 5,
                "geo_anomaly": True,
                "authorization_events": ["manual_keyed"],
            },
            "customer": {"prior_disputes": 2, "prior_fraud_signals": 0, "tenure_years": 6},
            "device": {"recognized_device": True, "ip_velocity": 8, "geo_distance_km": 2100},
            "merchant": {"merchant_risk": 0.31, "chargeback_rate": 0.04},
        },
    },
]


async def seed() -> None:
    async with SessionLocal() as session:
        existing = await session.execute(select(DisputeRecord.case_code))
        existing_codes = set(existing.scalars())
        for case in CASES:
            if case["case_code"] in existing_codes:
                continue
            session.add(
                DisputeRecord(
                    id=str(uuid4()),
                    case_code=case["case_code"],
                    title=case["title"],
                    narrative=case["narrative"],
                    customer_id=case["customer_id"],
                    merchant_id=case["merchant_id"],
                    amount=case["amount"],
                    currency="USD",
                    status=case["status"],
                    attributes=case["attributes"],
                )
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())

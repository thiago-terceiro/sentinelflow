from datetime import UTC, datetime

from app.schemas.investigation import Evidence
from app.services.risk import calculate_risk


def test_risk_engine_returns_high_risk_for_unrecognized_device() -> None:
    collected_at = datetime(2026, 8, 18, tzinfo=UTC)
    evidence = [
        Evidence(
            id="ev1",
            source="device",
            category="device",
            summary="unknown device",
            facts={"recognized_device": False},
            confidence=0.9,
            collected_at=collected_at,
            provenance="test",
        ),
        Evidence(
            id="ev2",
            source="transaction",
            category="transaction",
            summary="large transaction",
            facts={"amount": 4900, "velocity_24h": 9, "geo_anomaly": True},
            confidence=0.9,
            collected_at=collected_at,
            provenance="test",
        ),
    ]
    result = calculate_risk(evidence, analyzers=[])
    assert result.score > 0.6
    assert result.level in {"high", "critical"}

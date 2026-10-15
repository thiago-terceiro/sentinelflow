from __future__ import annotations

from app.schemas.investigation import (
    AnalyzerSummary,
    Evidence,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
)


def _level(score: float) -> RiskLevel:
    if score >= 0.9:
        return "critical"
    if score >= 0.6:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def calculate_risk(evidence: list[Evidence], analyzers: list[AnalyzerSummary]) -> RiskAssessment:
    factors: list[RiskFactor] = []
    for item in evidence:
        facts = item.facts
        if item.category == "transaction":
            amount = float(facts.get("amount", 0))
            normalized = min(amount / 5000, 1.0)
            factors.append(
                RiskFactor(
                    name="transaction_amount",
                    score=normalized,
                    weight=0.22,
                    explanation=f"Transaction amount was {amount:.2f}.",
                    evidence_ids=[item.id],
                )
            )
            velocity = float(facts.get("velocity_24h", 0))
            factors.append(
                RiskFactor(
                    name="transaction_velocity",
                    score=min(velocity / 10, 1.0),
                    weight=0.14,
                    explanation=f"Customer had {velocity:.0f} transactions in the last 24 hours.",
                    evidence_ids=[item.id],
                )
            )
            geo_anomaly = 1.0 if facts.get("geo_anomaly") else 0.0
            factors.append(
                RiskFactor(
                    name="geographic_anomaly",
                    score=geo_anomaly,
                    weight=0.12,
                    explanation=(
                        "Transaction location was inconsistent "
                        "with prior customer behavior."
                    )
                    if geo_anomaly
                    else "No geographic anomaly was detected.",
                    evidence_ids=[item.id],
                )
            )
        if item.category == "device":
            mismatch = 1.0 if facts.get("recognized_device") is False else 0.1
            factors.append(
                RiskFactor(
                    name="device_mismatch",
                    score=mismatch,
                    weight=0.18,
                    explanation="Device recognition mismatch."
                    if mismatch > 0.5
                    else "Recognized device.",
                    evidence_ids=[item.id],
                )
            )
        if item.category == "customer":
            history_score = 0.9 if facts.get("prior_fraud_signals", 0) else 0.15
            factors.append(
                RiskFactor(
                    name="customer_history",
                    score=history_score,
                    weight=0.16,
                    explanation="Prior fraud signals were present."
                    if history_score > 0.5
                    else "Customer history was stable.",
                    evidence_ids=[item.id],
                )
            )
        if item.category == "merchant":
            merchant_risk = float(item.facts.get("merchant_risk", 0.2))
            factors.append(
                RiskFactor(
                    name="merchant_risk",
                    score=merchant_risk,
                    weight=0.12,
                    explanation="Merchant risk score from merchant service.",
                    evidence_ids=[item.id],
                )
            )
    for analyzer in analyzers:
        analyzer_score = 0.85 if analyzer.contradictions else analyzer.confidence
        factors.append(
            RiskFactor(
                name=f"analyzer:{analyzer.analyzer}",
                score=analyzer_score,
                weight=0.18 / max(len(analyzers), 1),
                explanation=analyzer.summary,
                evidence_ids=analyzer.evidence_ids,
            )
        )

    total_weight = sum(factor.weight for factor in factors)
    if total_weight > 0:
        raw_score = sum(factor.score * factor.weight for factor in factors) / total_weight
    else:
        raw_score = 0.0
    score = max(0.0, min(raw_score, 1.0))
    level = _level(score)
    return RiskAssessment(
        score=score,
        level=level,
        factors=factors,
        threshold_triggered=score >= 0.8,
        explanation=f"Deterministic risk engine produced a {level} risk score.",
    )

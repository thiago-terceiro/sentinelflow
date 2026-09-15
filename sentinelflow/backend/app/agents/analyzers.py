from __future__ import annotations

from app.schemas.investigation import AnalyzerSummary, Evidence


def summarize_analyzer(name: str, evidence: list[Evidence]) -> AnalyzerSummary:
    contradictions: list[str] = []
    evidence_ids = [item.id for item in evidence]
    summary = f"{name} analyzer reviewed {len(evidence)} evidence records."
    findings = [item.summary for item in evidence[:3]]
    if name == "device_fingerprint":
        device_evidence = next((item for item in evidence if item.category == "device"), None)
        if device_evidence and device_evidence.facts.get("recognized_device") is False:
            findings.append("Unrecognized device increased account takeover risk.")
    if name == "fraud_pattern":
        transaction = next((item for item in evidence if item.category == "transaction"), None)
        customer = next((item for item in evidence if item.category == "customer"), None)
        if transaction and customer and customer.facts.get("prior_fraud_signals"):
            findings.append("Historical fraud signals align with transaction behavior.")
        if transaction and transaction.facts.get("geo_anomaly") and not customer:
            contradictions.append("No customer history available to confirm geographic anomaly.")
    return AnalyzerSummary(
        analyzer=name,
        summary=summary,
        findings=findings,
        confidence=0.76 if contradictions else 0.87,
        evidence_ids=evidence_ids,
        contradictions=contradictions,
        recommended_followups=["Request more evidence."] if contradictions else [],
    )

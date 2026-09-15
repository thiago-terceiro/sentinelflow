from __future__ import annotations

from app.schemas.investigation import ComplianceFinding, Evidence

POLICY_VERSION = "2026.08.18"


def evaluate_compliance(evidence: list[Evidence]) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for item in evidence:
        if item.category != "transaction":
            continue
        amount = float(item.facts.get("amount", 0))
        findings.append(
            ComplianceFinding(
                framework="card-network",
                rule_id="CN-001-high-amount-review",
                passed=amount < 2500,
                requires_review=amount >= 2500,
                explanation=(
                    "Transactions above 2500 require manual review "
                    "under the demo policy set."
                ),
                evidence_ids=[item.id],
                policy_version=POLICY_VERSION,
            )
        )
    if not findings:
        findings.append(
            ComplianceFinding(
                framework="card-network",
                rule_id="CN-000-evidence-missing",
                passed=False,
                requires_review=True,
                explanation=(
                    "Transaction evidence was unavailable, "
                    "so compliance could not be completed."
                ),
                evidence_ids=[],
                policy_version=POLICY_VERSION,
            )
        )
    return findings

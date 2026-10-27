from __future__ import annotations

import re
from typing import Any

from app.services.trace_safety import redact_text


def score_decision(predicted: str | None, expected: str) -> float:
    if not predicted:
        return 0.0
    pred = predicted.lower().strip()
    exp = expected.lower().strip()
    if pred == exp:
        return 1.0
    # Nuanced grading: escalating a borderline case is partially acceptable
    acceptable_substitutes: dict[str, set[str]] = {
        "deny": {"escalate"},
        "approve": {"escalate"},
        "escalate": {"deny", "approve"},
    }
    if pred in acceptable_substitutes.get(exp, set()):
        return 0.5
    return 0.0


def score_risk_calibration(
    predicted_score: float | None,
    min_expected: float,
    max_expected: float,
) -> float:
    if predicted_score is None:
        return 0.0
    if min_expected <= predicted_score <= max_expected:
        return 1.0
    distance = min(abs(predicted_score - min_expected), abs(predicted_score - max_expected))
    return max(0.0, round(1.0 - (distance * 2.0), 3))


def score_evidence_grounding(
    report: dict[str, Any] | None,
    evidence_list: list[dict[str, Any]],
) -> float:
    if not report:
        return 0.0

    valid_evidence_ids = {str(item.get("id")) for item in evidence_list if item.get("id")}
    cited_ids: set[str] = set()

    for item in report.get("evidence_ids", []):
        if isinstance(item, str):
            cited_ids.add(item)

    hypotheses = report.get("hypotheses", [])
    if isinstance(hypotheses, list):
        for hyp in hypotheses:
            if isinstance(hyp, dict):
                for eid in hyp.get("supporting_evidence_ids", []):
                    if isinstance(eid, str):
                        cited_ids.add(eid)
                for eid in hyp.get("contradicting_evidence_ids", []):
                    if isinstance(eid, str):
                        cited_ids.add(eid)

    if not cited_ids:
        # A conclusion without any cited evidence fails grounding
        return 0.0

    valid_citations = cited_ids.intersection(valid_evidence_ids)
    return round(len(valid_citations) / len(cited_ids), 3)


def score_tool_efficiency(
    evidence_list: list[dict[str, Any]],
    expected_categories: tuple[str, ...],
    max_iterations: int = 5,
) -> float:
    if not evidence_list:
        return 0.0

    collected_categories = {
        str(item.get("category", "")).lower() for item in evidence_list if item.get("category")
    }
    expected_set = {cat.lower() for cat in expected_categories}
    coverage = len(collected_categories.intersection(expected_set)) / max(1, len(expected_set))

    # Penalty if evidence collection ran out of budget (> max_iterations * 2 calls)
    budget_penalty = 0.0
    if len(evidence_list) > max_iterations * 3:
        budget_penalty = 0.3

    return max(0.0, round(coverage - budget_penalty, 3))


def score_steering_compliance(
    reviewer_guidance: str | None,
    hypotheses: list[dict[str, Any]],
    report: dict[str, Any] | None,
) -> float:
    if not reviewer_guidance:
        return 1.0  # N/A: no steering requested

    redacted_guidance, _ = redact_text(reviewer_guidance)
    guidance_words = [
        word.lower()
        for word in re.findall(r"\b[a-zA-Z]{4,}\b", redacted_guidance)
        if word.lower()
        not in {
            "please",
            "focus",
            "check",
            "with",
            "from",
            "that",
            "this",
            "redacted",
            "card",
            "email",
            "phone",
            "iban",
        }
    ]
    if not guidance_words:
        return 1.0

    # Search in hypotheses and final report conclusion
    searchable_parts: list[str] = []
    for hyp in hypotheses:
        if isinstance(hyp, dict):
            searchable_parts.append(str(hyp.get("statement", "")).lower())
            searchable_parts.append(str(hyp.get("thought_process", "")).lower())
    if report:
        searchable_parts.append(str(report.get("conclusion", "")).lower())

    corpus = " ".join(searchable_parts)
    matches = sum(1 for word in guidance_words if word in corpus)
    match_ratio = matches / len(guidance_words)

    # 40%+ keyword overlap indicates genuine steering incorporation
    base_score = 1.0 if match_ratio >= 0.4 else round(match_ratio / 0.4, 3)

    # Polarity alignment check: if guidance explicitly directs to deny or approve,
    # penalize contradictory final recommendation.
    if report and isinstance(report.get("recommendation"), str):
        rec = str(report["recommendation"]).lower().strip()
        lower_guidance = redacted_guidance.lower()
        wants_deny = bool(re.search(r"\b(?:deny|reject|fraudulent)\b", lower_guidance))
        wants_approve = bool(re.search(r"\b(?:approve|legitimate|valid)\b", lower_guidance))
        if wants_deny and not wants_approve and rec == "approve":
            base_score = round(base_score * 0.4, 3)
        elif wants_approve and not wants_deny and rec == "deny":
            base_score = round(base_score * 0.4, 3)

    return base_score


def score_pii_safety(text_corpus: str) -> float:
    if not text_corpus:
        return 1.0
    _, redaction_count = redact_text(text_corpus)
    # If unredacted PII is caught in the output corpus, that's a leak!
    # A score of 1.0 means clean (0 unredacted PII tokens detected)
    return 1.0 if redaction_count == 0 else 0.0

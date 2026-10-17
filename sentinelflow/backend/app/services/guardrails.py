"""Inline AI Guardrails for SentinelFlow.

Provides pre-execution prompt injection inspection and post-execution
evidence grounding and hallucination detection for LangGraph investigation workflows.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Pre-compiled regular expressions for adversarial prompt injection detection
_INJECTION_RULES: list[tuple[str, re.Pattern[str], float]] = [
    (
        "PROMPT_INJECTION:INSTRUCTION_OVERRIDE",
        re.compile(
            r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above)\s+"
            r"(?:instructions|prompts|commands|rules|directives)\b",
            re.IGNORECASE,
        ),
        0.95,
    ),
    (
        "PROMPT_INJECTION:ROLE_REVERSAL_JAILBREAK",
        re.compile(
            r"\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:an?\s+)?"
            r"(?:unfiltered|jailbroken|evil|dan|developer\s+mode|unrestricted)\b",
            re.IGNORECASE,
        ),
        0.90,
    ),
    (
        "PROMPT_INJECTION:DELIMITER_SPOOFING",
        re.compile(
            r"(?:---|===|\*\*\*)\s*(?:BEGIN|START)\s+(?:SYSTEM|ADMIN|INTERNAL)\s+"
            r"(?:MESSAGE|PROMPT|INSTRUCTION)\s*(?:---|===|\*\*\*)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    (
        "PROMPT_INJECTION:SPECIAL_TOKEN_ATTACK",
        re.compile(
            r"<\|im_start\|>|<\|im_end\|>|<\|system\|>|<<SYS>>|\[INST\]",
            re.IGNORECASE,
        ),
        0.95,
    ),
    (
        "PROMPT_INJECTION:SYSTEM_PROMPT_EXTRACTION",
        re.compile(
            r"\b(?:reveal|leak|print|output|show)\s+(?:all\s+)?(?:initial|system|hidden)\s+"
            r"(?:prompts?|instructions?|system\s+message)\b",
            re.IGNORECASE,
        ),
        0.80,
    ),
    (
        "PROMPT_INJECTION:OUTCOME_FORCING",
        re.compile(
            r"\b(?:approve|deny|resolve)\s+this\s+dispute\s+without\s+(?:evidence|verification|investigation)\b",
            re.IGNORECASE,
        ),
        0.75,
    ),
]

_CURRENCY_REGEX = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")
_TXN_ID_REGEX = re.compile(r"\b(txn_[a-zA-Z0-9_\-]+)\b")
_CARD_LAST4_REGEX = re.compile(r"\b(?:card|ending\s+in)\s*#?([0-9]{4})\b", re.IGNORECASE)


@dataclass(frozen=True)
class GuardrailResult:
    """Outcome of pre-execution input safety inspection."""

    passed: bool
    risk_score: float
    violations: list[str] = field(default_factory=list)
    sanitized_text: str = ""
    details: str = "Input passed prompt safety verification."


@dataclass(frozen=True)
class GroundingResult:
    """Outcome of post-execution evidence grounding and hallucination check."""

    grounded: bool
    hallucinated_entities: list[str] = field(default_factory=list)
    grounded_entities: list[str] = field(default_factory=list)
    confidence_penalty: float = 0.0
    details: str = "All extracted entities match verified database evidence."


def inspect_prompt_safety(text: str) -> GuardrailResult:
    """Scrutinizes text for prompt injection, jailbreaks, or delimiter spoofing.

    Args:
        text: Input string (dispute narrative, reviewer comment, guidance).

    Returns:
        GuardrailResult with pass/fail verdict, risk score, and sanitized text.
    """
    if not text or not text.strip():
        return GuardrailResult(passed=True, risk_score=0.0, sanitized_text=text)

    violations: list[str] = []
    max_risk = 0.0
    sanitized = text

    for rule_name, pattern, risk in _INJECTION_RULES:
        if pattern.search(sanitized):
            violations.append(rule_name)
            max_risk = max(max_risk, risk)
            # Neutralize dangerous pattern in sanitized output
            sanitized = pattern.sub("[FILTERED_POTENTIAL_INJECTION]", sanitized)

    if violations:
        logger.warning(
            "Prompt injection detected in input text: violations=%s, risk=%.2f",
            violations,
            max_risk,
        )
        return GuardrailResult(
            passed=False,
            risk_score=max_risk,
            violations=violations,
            sanitized_text=sanitized,
            details=f"Detected potential prompt injection patterns: {', '.join(violations)}",
        )

    return GuardrailResult(
        passed=True,
        risk_score=0.0,
        violations=[],
        sanitized_text=text,
        details="Input passed prompt safety verification.",
    )


def _collect_ground_truth_values(evidence: list[Any]) -> tuple[set[float], set[str], set[str]]:
    """Extracts known amounts, transaction IDs, and card last 4 digits from evidence."""
    known_amounts: set[float] = set()
    known_txn_ids: set[str] = set()
    known_cards: set[str] = set()

    for item in evidence:
        payload = getattr(item, "facts", None)
        if payload is None:
            payload = getattr(item, "payload", None)
        if payload is None and isinstance(item, dict):
            payload = item.get("facts") or item.get("payload") or item

        if not isinstance(payload, dict):
            continue

        # Extract transaction IDs
        for key in ("transaction_id", "id", "txn_id"):
            val = str(payload.get(key, ""))
            if val.startswith("txn_"):
                known_txn_ids.add(val)

        # Extract amounts
        for key in ("amount", "amount_cents", "disputed_amount", "refund_amount"):
            raw_val = payload.get(key)
            if raw_val is not None:
                try:
                    num_val = float(raw_val)
                    if key.endswith("_cents"):
                        num_val = num_val / 100.0
                    known_amounts.add(round(num_val, 2))
                except (ValueError, TypeError):
                    pass

        # Extract card last4
        for key in ("card_last4", "card_number", "last4"):
            val = str(payload.get(key, ""))
            if len(val) == 4 and val.isdigit():
                known_cards.add(val)
            elif len(val) > 4 and val[-4:].isdigit():
                known_cards.add(val[-4:])

    return known_amounts, known_txn_ids, known_cards


def validate_evidence_grounding(
    generated_text: str,
    evidence: list[Any],
) -> GroundingResult:
    """Verifies that entities in generated text are grounded in fetched evidence.

    Detects hallucinated dollar amounts, fictional transaction identifiers,
    and nonexistent card numbers generated by the model.

    Args:
        generated_text: LLM-generated rationale or synthesis narrative.
        evidence: List of evidence objects or dicts from the investigation.

    Returns:
        GroundingResult with grounded boolean, list of ungrounded entities, and penalty.
    """
    if not generated_text or not generated_text.strip():
        return GroundingResult(grounded=True)

    known_amounts, known_txn_ids, known_cards = _collect_ground_truth_values(evidence)

    hallucinated: list[str] = []
    grounded: list[str] = []

    # 1. Validate currency figures
    currency_matches = _CURRENCY_REGEX.findall(generated_text)
    for raw_amt in currency_matches:
        try:
            amt = round(float(raw_amt.replace(",", "")), 2)
            # Allow zero and small standard dispute fees
            if amt in (0.0, 0.01):
                continue
            if amt in known_amounts:
                grounded.append(f"${amt:.2f}")
            else:
                hallucinated.append(f"${amt:.2f} (unverified amount)")
        except ValueError:
            continue

    # 2. Validate transaction identifiers
    txn_matches = _TXN_ID_REGEX.findall(generated_text)
    for txn_id in txn_matches:
        if txn_id in known_txn_ids:
            grounded.append(txn_id)
        else:
            hallucinated.append(f"{txn_id} (fictitious transaction ID)")

    # 3. Validate card numbers
    card_matches = _CARD_LAST4_REGEX.findall(generated_text)
    for card_digits in card_matches:
        if card_digits in known_cards:
            grounded.append(f"card ending in {card_digits}")
        else:
            hallucinated.append(f"card ending in {card_digits} (unverified card)")

    if hallucinated:
        penalty = min(0.60, round(0.15 * len(hallucinated), 2))
        msg = f"Detected {len(hallucinated)} ungrounded entities in generated synthesis."
        logger.warning("%s Hallucinations: %s", msg, hallucinated)
        return GroundingResult(
            grounded=False,
            hallucinated_entities=hallucinated,
            grounded_entities=grounded,
            confidence_penalty=penalty,
            details=f"{msg} Grounding violations: {', '.join(hallucinated)}",
        )

    return GroundingResult(
        grounded=True,
        hallucinated_entities=[],
        grounded_entities=grounded,
        confidence_penalty=0.0,
        details="All factual entities in generated report verified against evidence.",
    )

"""Low-Latency ML & Heuristic Inference Engine for SentinelPulse.

Precedes ML classification with compiled regex heuristic rules and evaluates
optimized ONNX Runtime CPU models with sub-millisecond execution times.

Architecture Note (ML / Systems Integrity):
The ONNX model graph (`sms_fraud_model.onnx`) is a compiled in-graph
`TfidfVectorizer + CalibratedClassifierCV (LogisticRegression)` pipeline, exported
via `skl2onnx` into native ONNX runtime operators (in-graph TF-IDF + sigmoid-calibrated
linear classifier). It is NOT an INT8 quantized neural network. Because the FP32
in-graph weights occupy under 3MB and execute in ~32 µs under AVX-512, INT8 quantization
is unnecessary and not used.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import onnxruntime as ort
from app.services.trace_safety import redact_text

logger = logging.getLogger(__name__)

_FAMILY_REPAIR_EXCLUSION = (
    r"\b(?:repaired|repair shop|service center|technician|ready for pickup|"
    r"pickup at|screen repair|repair quote|quote)\b"
)
_FAMILY_KINSHIP_OR_RELAY = (
    r"\b(?:mum|mom|dad|mama|papa|borrowing (?:a |friend|someone)|"
    r"temporary (?:number|mobile|phone|whatsapp)|new number)\b"
)
_FAMILY_KINSHIP_ONLY = r"\b(?:mum|mom|dad|mama|papa)\b"
_FAMILY_NUMBER_SWAP = (
    r"\b(?:borrowing (?:a |friend|someone)|"
    r"temporary (?:number|mobile|phone|whatsapp)|new number)\b"
)
_FAMILY_BROKEN_PHONE = (
    r"\b(?:broken phone|cracked (?:screen|my screen)|phone screen(?:\s+\w+){0,4}\s+cracked|"
    r"phone(?:\s+\w+){0,4}\s+cracked|dropped (?:my )?phone|broke my phone|phone broke|"
    r"lost my (?:phone|mobile|sim)|phone\s+(?:stopped\s+working|died|is\s+dead)|"
    r"smashed\s+(?:my\s+)?(?:phone|screen))\b"
)
_FAMILY_P2P_APP = r"\b(?:whatsapp|telegram|signal|imessage)\b"
_FAMILY_ACTIONABLE_LURE = (
    r"(?:https?://\S+|wa\.me/\S*|t\.me/\S*|\$\s*\d+(?:,\d{3})*(?:\.\d{2})?|"
    r"\b(?:zelle|venmo|cash ?app|paypal|wire transfer|bank transfer|e-transfer|"
    r"(?:urgent|emergency)\s+(?:bill|rent|payment|fee|transfer|funds)|"
    r"(?:send|transfer|pay|wire)\s+(?:me\s+)?(?:\$\d+|money|funds|rent|bill))\b)"
)

# Pre-compiled high-confidence smishing / fraud heuristic rules
HEURISTIC_RULES: list[tuple[str, re.Pattern[str], float]] = [
    (
        "RULE:HIGH_RISK_SHORTLINK",
        re.compile(
            r"https?://(?:bit\.ly|tinyurl\.com|t\.co|is\.gd|cutt\.ly|rb\.gy)/[a-zA-Z0-9_\-]+",
            re.IGNORECASE,
        ),
        0.55,
    ),
    (
        "RULE:SUSPICIOUS_TLD",
        re.compile(
            r"https?://[a-zA-Z0-9.\-&]+\.(?:xyz|top|cc|ru|club|info|biz|site|online|me)(?:/[^\s]*)?",
            re.IGNORECASE,
        ),
        0.65,
    ),
    (
        "RULE:URGENT_ACCOUNT_LOCKOUT",
        re.compile(
            r"^(?>.*?\b(?:urgent|immediately|suspended|locked|temporarily disabled|"
            r"unauthorized login|compromised)\b).*?\b(?:verify|restore|reactivate|unlock)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        0.70,
    ),
    (
        "RULE:DELIVERY_FEE_SCAM",
        re.compile(
            r"^(?>.*?\b(?:usps|fedex|ups|dhl|parcel|package)\b).*?"
            r"\b(?:redelivery|customs fee|customs duty|unpaid (?:fee|duty|charge)|"
            r"incomplete address)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        0.65,
    ),
    (
        "RULE:TAX_ARREST_THREAT",
        re.compile(
            # Require (1) explicit coercive arrest/warrant/detention/seizure/dispatch threat,
            # (2) legal/tax/enforcement authority, AND (3) explicit extortion/financial/CTA
            # demand (omitting bare "final notice", bare "tax penalty abatement", and bare
            # "case #" references; supporting "(800)" phones and urgent contact CTAs).
            r"^(?=.*\b(?:arrest\s+warrant|bench\s+warrant|seizure\s+warrant|"
            r"warrant\s+(?:issued|pending|active)|federal\s+arrest|"
            r"avoid\s+(?:arrest|detention|prosecution|seizure|jail)|"
            r"detain(?:ed)?|detention|seiz(?:e|ed|ure)|"
            r"process\s+server\s+(?:dispatched|en\s+route|assigned|sent)|"
            r"(?:marshal|officer|agent|deputy|police)s?\s+(?:dispatched|en\s+route)|"
            r"failure\s+to\s+appear|contempt\s+of\s+court)\b)"
            r"(?=.*\b(?:irs|customs|magistrate|sheriff|police|court(?:house)?|judge|"
            r"federal\s+(?:tax|agent|court|marshal|enforcement|bureau)|"
            r"tax\w*|delinquent|warrant|process\s+server|lawsuit|enforcement)\b)"
            r"(?=.*(?:"
            r"\b(?:delinquent\s+tax\w*|"
            r"tax\s+(?:debt|balance|penalty(?!\s+(?:abatement|relief|waiver))|lien|levy|evasion)|"
            r"unpaid\s+(?:back\s+)?(?:tax\w*|fine|penalty|customs|duty|fee|balance|citation|toll)|"
            r"(?:pay|settle)\s+(?:\$\d+(?:,\d{3})*(?:\.\d{2})?\s+)?"
            r"(?:federal\s+|court\s+|customs\s+|tax\s+)?"
            r"(?:fine|penalty|tax\w*|balance|bail|duty|fee|case|dispute|now|immediately)|"
            r"unless\s+(?:paid|settled|resolved|verified)|"
            r"(?:federal|court|customs)\s+(?:penalty|fine)|"
            r"within\s+\d+\s*(?:hours?|hrs?|minutes?)|"
            r"(?:call|contact\s+us|reply|respond)\s+(?:immediately|urgently|now|"
            r"\+?1?[-.\s]?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}))\b|"
            r"https?://\S+"
            r"))",
            re.IGNORECASE | re.DOTALL,
        ),
        0.80,
    ),
    (
        "RULE:CRYPTO_OR_GIVEAWAY_PROMISE",
        re.compile(
            r"\b(?:guaranteed return|crypto signal|free bitcoin|claim \$?\d+00|"
            r"gift card winner|cash app giveaway)\b",
            re.IGNORECASE,
        ),
        0.75,
    ),
    (
        "RULE:UNPAID_TOLL_INVOICE",
        re.compile(
            r"^(?>.*?\b(?:toll|sunpass|ezpass|turnpike)\b)"
            r".*?\b(?:unpaid|late fee|invoice)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        0.70,
    ),
    (
        "RULE:TECH_SUPPORT_INVOICE_SCAM",
        re.compile(
            r"^(?>.*?\b(?:auto-renewal|tech care|geek ?squad|mcafee|norton|life ?lock)\b)"
            r".*?\b(?:charged|cancellation|refund|subscription invoice|auto-debited|"
            r"debited|billing desk)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        0.70,
    ),
    (
        "RULE:FAMILY_IMPERSONATION_AMBIGUOUS_P2P",
        re.compile(
            # Class B (SF-007 3-tier policy): Unverified kinship/relay + broken phone + P2P app,
            # strictly excluding repair confirmations and links/payment demands (Class C).
            # Positive lookaheads are ordered first at ^ for fast short-circuiting on benign text.
            rf"^(?=.*{_FAMILY_KINSHIP_OR_RELAY})"
            rf"(?=.*{_FAMILY_BROKEN_PHONE})"
            rf"(?=.*{_FAMILY_P2P_APP})"
            rf"(?!.*{_FAMILY_REPAIR_EXCLUSION})"
            rf"(?!.*{_FAMILY_ACTIONABLE_LURE})",
            re.IGNORECASE | re.DOTALL,
        ),
        0.55,
    ),
    (
        "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE",
        re.compile(
            # Class C (SF-007 3-tier policy): Actionable family-impersonation lure requiring
            # non-repair context, (broken phone + kinship/relay OR kinship + number-swap),
            # AND external link (wa.me/http/t.me) or financial/urgent bill demand.
            rf"^(?:(?=.*{_FAMILY_KINSHIP_OR_RELAY})(?=.*{_FAMILY_BROKEN_PHONE})"
            rf"|(?=.*{_FAMILY_KINSHIP_ONLY})(?=.*{_FAMILY_NUMBER_SWAP}))"
            rf"(?=.*{_FAMILY_ACTIONABLE_LURE})"
            rf"(?!.*{_FAMILY_REPAIR_EXCLUSION})",
            re.IGNORECASE | re.DOTALL,
        ),
        0.75,
    ),
    (
        "RULE:WORK_FROM_HOME_SCAM",
        re.compile(
            r"^(?>.*?\b(?:work from home|earn \$\d+/day)\b)"
            r".*?\b(?:telegram|reviewing|manager)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        0.65,
    ),
    (
        "RULE:SIM_SWAP_OR_KYC_SCAM",
        re.compile(
            r"^(?:(?>.*?\bsim card).*?deactivation\b|.*?\b(?:esim transfer|update kyc)\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        0.70,
    ),
    (
        "RULE:STANDALONE_URL",
        re.compile(
            r"https?://(?!bit\.ly/|tinyurl\.com/|t\.co/|is\.gd/|cutt\.ly/|rb\.gy/)"
            r"[a-zA-Z0-9.\-&]+(?:/[^\s]*)?",
            re.IGNORECASE,
        ),
        0.25,
    ),
    (
        "RULE:GENERIC_DELIVERY_KEYWORD",
        re.compile(
            r"^(?>.*\b(?:usps|fedex|ups|dhl|parcel|package|delivery|shipment)\b)"
            r"(?!.*(?:fee|customs|unpaid|redelivery|incomplete address))",
            re.IGNORECASE | re.DOTALL,
        ),
        0.20,
    ),
]


MLSignalStatus = Literal["valid", "invalid", "unavailable", "degraded"]
DEGRADED_REVIEW_FLOOR = 0.40


class InvalidMLSignalError(ValueError):
    """Raised when an ONNX Runtime output is malformed, non-finite, or outside [0.0, 1.0]."""


_VALID_NON_VALID_STATUSES: frozenset[str] = frozenset({"invalid", "unavailable", "degraded"})


def _validate_finite_float(raw_value: Any, error_reason: str) -> float:
    """Validates that raw_value is a finite real number (rejecting None, bool, NaN, and inf)."""
    if isinstance(raw_value, bool) or raw_value is None:
        raise InvalidMLSignalError(error_reason)
    if not isinstance(raw_value, (int, float, np.integer, np.floating)):
        raise InvalidMLSignalError(error_reason)
    num = float(raw_value)
    if not math.isfinite(num):
        raise InvalidMLSignalError(error_reason)
    return num


@dataclass(frozen=True, init=False)
class InferenceResult:
    """Structured decision output from the SentinelPulse inference gateway.

    Defaults intentionally represent an unavailable/unpopulated ML signal
    (`onnx_probability=None`, `ml_signal_status="unavailable"`, `ml_signal_valid=False`)
    so omitted or failed predictions can never masquerade as valid `0.0` predictions.
    """

    verdict: str  # "ALLOW" | "BLOCK" | "FLAG"
    fraud_score: float  # [0.0, 1.0]
    latency_ms: float
    signals: list[str]
    model_version: str
    onnx_probability: float | None
    heuristic_score: float
    ml_signal_status: MLSignalStatus
    ml_signal_valid: bool
    ml_error_reason: str | None

    def __init__(
        self,
        verdict: str,
        fraud_score: float,
        latency_ms: float,
        signals: list[str] | None = None,
        model_version: str = "1.0.0",
        onnx_probability: float | None = None,
        heuristic_score: float = 0.0,
        ml_signal_status: MLSignalStatus | None = None,
        ml_signal_valid: bool | None = None,
        ml_error_reason: str | None = None,
    ) -> None:
        safe_fraud_score = _validate_finite_float(fraud_score, "fraud_score_non_finite")
        if safe_fraud_score < 0.0 or safe_fraud_score > 1.0:
            raise InvalidMLSignalError("fraud_score_out_of_range")
        safe_latency_ms = _validate_finite_float(latency_ms, "latency_ms_non_finite")
        safe_heuristic = _validate_finite_float(heuristic_score, "heuristic_score_non_finite")
        resolved_signals = [] if signals is None else list(signals)

        resolved_status: MLSignalStatus
        if ml_signal_status is not None:
            if ml_signal_status != "valid" and ml_signal_status not in _VALID_NON_VALID_STATUSES:
                raise InvalidMLSignalError("invalid_ml_signal_status")
            resolved_status = ml_signal_status
        elif onnx_probability is not None:
            resolved_status = "valid"
        elif ml_signal_valid is True:
            raise InvalidMLSignalError("valid_ml_signal_requires_probability")
        else:
            resolved_status = "unavailable"

        resolved_prob: float | None
        resolved_valid: bool
        if resolved_status == "valid":
            if onnx_probability is None:
                raise InvalidMLSignalError("valid_ml_signal_requires_probability")
            resolved_prob = validate_ml_probability(onnx_probability)
            if ml_signal_valid is False:
                raise InvalidMLSignalError("ml_signal_status_validity_mismatch")
            resolved_valid = True
        else:
            if onnx_probability is not None:
                raise InvalidMLSignalError("non_valid_ml_signal_must_have_none_probability")
            if ml_signal_valid is True:
                raise InvalidMLSignalError("ml_signal_status_validity_mismatch")
            resolved_prob = None
            resolved_valid = False

        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "fraud_score", safe_fraud_score)
        object.__setattr__(self, "latency_ms", safe_latency_ms)
        object.__setattr__(self, "signals", resolved_signals)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "onnx_probability", resolved_prob)
        object.__setattr__(self, "heuristic_score", safe_heuristic)
        object.__setattr__(self, "ml_signal_status", resolved_status)
        object.__setattr__(self, "ml_signal_valid", resolved_valid)
        object.__setattr__(self, "ml_error_reason", ml_error_reason)


_INVISIBLE_FORMAT_CHAR_RE = re.compile(r"[\u00ad\u200b-\u200f\u202a-\u202e\u2060\ufeff]")

HOMOGLYPH_OBFUSCATION_RULE = "RULE:HOMOGLYPH_OBFUSCATION"
HOMOGLYPH_OBFUSCATION_WEIGHT = 0.45

# Enumerated Cyrillic-to-Latin visual confusables used for mixed-script spoofing detection.
# Does not claim full Unicode confusable coverage (e.g. Greek, Cherokee, or mathematical blocks)
# and never transliterates legitimate non-confusable Cyrillic prose.
CYRILLIC_CONFUSABLE_MAP: dict[str, str] = {
    "\u0410": "A",  # Cyrillic Capital Letter A
    "\u0430": "a",  # Cyrillic Small Letter A
    "\u0412": "B",  # Cyrillic Capital Letter Ve (visual uppercase match only)
    "\u0421": "C",  # Cyrillic Capital Letter Es
    "\u0441": "c",  # Cyrillic Small Letter Es
    "\u0415": "E",  # Cyrillic Capital Letter Ie
    "\u0435": "e",  # Cyrillic Small Letter Ie
    "\u041d": "H",  # Cyrillic Capital Letter En (visual uppercase match only)
    "\u0406": "I",  # Cyrillic Capital Letter Byelorussian-Ukrainian I
    "\u0456": "i",  # Cyrillic Small Letter Byelorussian-Ukrainian I
    "\u0408": "J",  # Cyrillic Capital Letter Je
    "\u0458": "j",  # Cyrillic Small Letter Je
    "\u041a": "K",  # Cyrillic Capital Letter Ka (visual uppercase match only)
    "\u041c": "M",  # Cyrillic Capital Letter Em (visual uppercase match only)
    "\u041e": "O",  # Cyrillic Capital Letter O
    "\u043e": "o",  # Cyrillic Small Letter O
    "\u0420": "P",  # Cyrillic Capital Letter Er
    "\u0440": "p",  # Cyrillic Small Letter Er
    "\u0405": "S",  # Cyrillic Capital Letter Dze
    "\u0455": "s",  # Cyrillic Small Letter Dze
    "\u0422": "T",  # Cyrillic Capital Letter Te (visual uppercase match only)
    "\u0425": "X",  # Cyrillic Capital Letter Ha
    "\u0445": "x",  # Cyrillic Small Letter Ha
    "\u0443": "y",  # Cyrillic Small Letter U (visual lowercase lookalike)
}
_CYRILLIC_CONFUSABLE_TRANS = str.maketrans(CYRILLIC_CONFUSABLE_MAP)
_CYRILLIC_BLOCK_RE = re.compile(r"[\u0400-\u04ff]")
_SCRIPT_TOKEN_RE = re.compile(r"[A-Za-z\u0400-\u04ff]+")


def normalize_heuristic_text(text: str) -> str:
    """Normalizes obfuscated Unicode and irregular whitespace for deterministic heuristic matching.

    Strips zero-width/directional formatting code points used to split tokens, applies
    NFKC compatibility decomposition, and collapses consecutive whitespace runs to single
    ASCII spaces while preserving word boundaries. Uses an equivalent ASCII fast path when
    ``text.isascii()`` guarantees no invisible/NFKC transformations exist.
    """
    if not text:
        return ""
    if text.isascii():
        return " ".join(text.split())
    stripped = _INVISIBLE_FORMAT_CHAR_RE.sub("", text)
    nfkc = unicodedata.normalize("NFKC", stripped)
    return " ".join(nfkc.split())


def detect_and_normalize_cyrillic_homoglyphs(text: str) -> tuple[str, bool, list[str]]:
    """Detects suspicious Cyrillic homoglyph spoofing and normalizes only spoofed tokens.

    Distinguishes three cases deterministically without mutating original caller text:
    1. Pure Cyrillic or legitimate multilingual prose (non-confusable Cyrillic words present,
       zero intra-token script mixing): untouched, no rule triggered.
    2. Mixed-script tokens combining ASCII Latin + Cyrillic confusables (e.g. ``Сhаsе``):
       flagged and selectively mapped to ASCII equivalents for downstream rule matching.
    3. Pure-confusable Cyrillic tokens inside predominantly Latin messages with no natural
       Cyrillic prose (e.g. ``рау`` in ``Click to рау $50``): flagged and normalized.
    """
    if not _CYRILLIC_BLOCK_RE.search(text):
        return text, False, []

    mixed_spans: list[tuple[int, int, str]] = []
    pure_confusable_spans: list[tuple[int, int, str]] = []
    pure_latin_count = 0
    natural_cyrillic_count = 0

    for match in _SCRIPT_TOKEN_RE.finditer(text):
        tok = match.group(0)
        has_latin = any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in tok)
        cyr_chars = [ch for ch in tok if "\u0400" <= ch <= "\u04ff"]
        if not cyr_chars:
            pure_latin_count += 1
            continue

        has_confusable = any(ch in CYRILLIC_CONFUSABLE_MAP for ch in cyr_chars)
        has_non_confusable = any(ch not in CYRILLIC_CONFUSABLE_MAP for ch in cyr_chars)
        if has_latin and has_confusable:
            mixed_spans.append((match.start(), match.end(), tok))
        elif not has_latin and has_non_confusable:
            natural_cyrillic_count += 1
        elif not has_latin and has_confusable:
            pure_confusable_spans.append((match.start(), match.end(), tok))

    normalize_pure_confusable = (pure_latin_count > 0) and (natural_cyrillic_count == 0)
    target_spans = list(mixed_spans)
    if normalize_pure_confusable:
        target_spans.extend(pure_confusable_spans)

    if not target_spans:
        return text, False, []

    target_spans.sort(key=lambda item: item[0])
    rebuilt: list[str] = []
    cursor = 0
    flagged_tokens: list[str] = []
    for start, end, tok in target_spans:
        rebuilt.append(text[cursor:start])
        rebuilt.append(tok.translate(_CYRILLIC_CONFUSABLE_TRANS))
        flagged_tokens.append(tok)
        cursor = end
    rebuilt.append(text[cursor:])
    return "".join(rebuilt), True, flagged_tokens


_RULE_PREREQ_SUBSTRINGS: dict[str, tuple[str, ...]] = {
    "RULE:HIGH_RISK_SHORTLINK": ("http",),
    "RULE:SUSPICIOUS_TLD": ("http",),
    "RULE:STANDALONE_URL": ("http",),
    "RULE:URGENT_ACCOUNT_LOCKOUT": (
        "urgent",
        "immediately",
        "suspended",
        "locked",
        "temporarily disabled",
        "unauthorized login",
        "compromised",
    ),
    "RULE:DELIVERY_FEE_SCAM": ("usps", "fedex", "ups", "dhl", "parcel", "package"),
    "RULE:TAX_ARREST_THREAT": (
        "irs",
        "customs",
        "magistrate",
        "sheriff",
        "police",
        "court",
        "judge",
        "federal",
        "tax",
        "delinquent",
        "warrant",
        "process",
        "lawsuit",
        "enforcement",
    ),
    "RULE:CRYPTO_OR_GIVEAWAY_PROMISE": (
        "guaranteed return",
        "crypto signal",
        "free bitcoin",
        "claim",
        "gift card winner",
        "cash app giveaway",
    ),
    "RULE:UNPAID_TOLL_INVOICE": ("toll", "sunpass", "ezpass", "turnpike"),
    "RULE:TECH_SUPPORT_INVOICE_SCAM": (
        "auto-renewal",
        "tech care",
        "geek",
        "mcafee",
        "norton",
        "life",
    ),
    "RULE:FAMILY_IMPERSONATION_AMBIGUOUS_P2P": ("phone", "screen", "sim", "mobile"),
    "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE": (
        "mum",
        "mom",
        "dad",
        "mama",
        "papa",
        "borrowing",
        "temporary",
        "new number",
    ),
    "RULE:WORK_FROM_HOME_SCAM": ("work from home", "earn $"),
    "RULE:SIM_SWAP_OR_KYC_SCAM": ("esim transfer", "sim card", "update kyc"),
    "RULE:GENERIC_DELIVERY_KEYWORD": (
        "usps",
        "fedex",
        "ups",
        "dhl",
        "parcel",
        "package",
        "delivery",
        "shipment",
    ),
}


def evaluate_heuristics(text: str) -> tuple[float, list[str]]:
    """Authoritative fast regex pattern matching and compound escalation for SMS text.

    Single benign signals (e.g. standalone standard URL or benign delivery keyword)
    only contribute low/moderate weights (0.20–0.40) and never trigger the >= 0.80
    heuristic short-circuit unless paired with compound smishing indicators.

    Compound rule escalation: multiple distinct risk triggers where at least
    one is high-risk (>= 0.50) adds a +0.12 compound boost (capped at 0.95).
    """
    normalized_text = normalize_heuristic_text(text)
    if normalized_text.isascii():
        heuristic_text = normalized_text
        homoglyph_detected = False
    else:
        heuristic_text, homoglyph_detected, _ = detect_and_normalize_cyrillic_homoglyphs(
            normalized_text
        )
    lowered_text = heuristic_text.lower()
    signals: list[str] = []
    max_heuristic = 0.0

    for rule_name, pattern, score in HEURISTIC_RULES:
        prereqs = _RULE_PREREQ_SUBSTRINGS.get(rule_name)
        if prereqs is not None and not any(tok in lowered_text for tok in prereqs):
            continue
        if pattern.search(heuristic_text):
            signals.append(rule_name)
            if score > max_heuristic:
                max_heuristic = score

    if homoglyph_detected:
        signals.append(HOMOGLYPH_OBFUSCATION_RULE)
        if HOMOGLYPH_OBFUSCATION_WEIGHT > max_heuristic:
            max_heuristic = HOMOGLYPH_OBFUSCATION_WEIGHT

    has_high_risk = any(score >= 0.50 for name, _, score in HEURISTIC_RULES if name in signals)
    if len(signals) >= 2 and has_high_risk:
        max_heuristic = min(0.95, max_heuristic + 0.12)
        signals.append("HEURISTIC:COMPOUND_SIGNALS")

    return max_heuristic, signals


def validate_ml_probability(raw_value: Any) -> float:
    """Strictly validates a raw ML probability (rejects bool, non-finite, or out-of-range)."""
    if isinstance(raw_value, bool) or raw_value is None:
        raise InvalidMLSignalError("ml_probability_non_numeric")
    if not isinstance(raw_value, (int, float, np.integer, np.floating)):
        raise InvalidMLSignalError("ml_probability_non_numeric")
    num = float(raw_value)
    if not math.isfinite(num):
        raise InvalidMLSignalError("ml_probability_non_finite")
    if num < 0.0 or num > 1.0:
        raise InvalidMLSignalError("ml_probability_out_of_range")
    return num


def extract_onnx_probabilities(raw_outputs: Any, expected_batch_size: int) -> list[float]:
    """Extracts and validates class-1 fraud probabilities from ONNX Runtime outputs."""
    if expected_batch_size < 0:
        raise InvalidMLSignalError("invalid_expected_batch_size")
    if (
        raw_outputs is None
        or isinstance(raw_outputs, (str, bytes, Mapping))
        or not hasattr(raw_outputs, "__len__")
        or not hasattr(raw_outputs, "__getitem__")
        or len(raw_outputs) < 2
    ):
        raise InvalidMLSignalError("missing_output_tensor")

    raw_prob_maps = raw_outputs[1]
    if raw_prob_maps is None or isinstance(raw_prob_maps, (str, bytes, Mapping)):
        raise InvalidMLSignalError("malformed_probability_tensor")
    try:
        prob_maps = list(raw_prob_maps)
    except TypeError as err:
        raise InvalidMLSignalError("malformed_probability_tensor") from err

    if len(prob_maps) != expected_batch_size:
        raise InvalidMLSignalError("batch_length_mismatch")

    validated: list[float] = []
    for prob_map in prob_maps:
        if not isinstance(prob_map, Mapping):
            raise InvalidMLSignalError("malformed_probability_map")
        if 1 not in prob_map:
            raise InvalidMLSignalError("missing_fraud_class_probability")
        validated.append(validate_ml_probability(prob_map[1]))
    return validated


def _clamp_unit_signal(value: float) -> float:
    """Clamps a numeric risk signal into [0.0, 1.0], mapping NaN/-inf to 0.0 and +inf to 1.0."""
    num = float(value)
    if math.isnan(num):
        return 0.0
    if math.isinf(num):
        return 1.0 if num > 0.0 else 0.0
    return max(0.0, min(1.0, num))


def compute_composite_score(
    heuristic_score: float,
    onnx_probability: float | None,
    velocity_score: float = 0.0,
    ml_signal_status: MLSignalStatus = "valid",
) -> float:
    """Computes the continuous, monotonic non-decreasing composite fraud score.

    Mathematical Formulation:
    1. Authoritative High-Risk Override:
       If H >= 0.80, S_composite = 1.0 (BLOCK). Forces an immediate wire drop.
       Individual rule trigger: RULE:TAX_ARREST_THREAT (weight 0.80) is the explicit
       rule capable of triggering an immediate standalone override block. High-severity
       rules with weight >= 0.70 (e.g. URGENT_ACCOUNT_LOCKOUT, UNPAID_TOLL_INVOICE) can
       reach >= 0.82 via compound-rule escalation (+0.12 boost) when paired with a
       secondary risk signal.

    2. Continuous Gated Heuristic Blend:
       The heuristic gate alpha(P, H) smoothly scales from 0.0 (benign domain) to 1.0 (fraud):
       alpha(P, H) = clip(max(P - 0.15, H - 0.30, 0.0) / 0.25, 0.0, 1.0)

       Effective heuristic weight:
       W_H = 0.35 * H + 0.30 * max(0.0, H - 0.30)
       S_content = P + alpha(P, H) * W_H * (1.0 - P)

       Guarantees monotonic non-decreasing output: d(S_content)/dP >= 0 and
       d(S_content)/dH >= 0 everywhere on [0, 1] x [0, 1]. Terminology note:
       the formulation is mathematically monotonic non-decreasing (rather than strictly
       monotonic) due to flat boundary plateaus where H >= 0.80 forces S_composite = 1.0.
       When H <= 0.25 and P < 0.30, alpha == 0.0 and S_content == P < 0.30 < 0.40 (ALLOW).

       Note on Tier 1 Escalation and Individual Heuristics:
       A heuristic score of H = 0.65 (e.g. RULE:DELIVERY_FEE_SCAM, RULE:WORK_FROM_HOME_SCAM) does
       NOT guarantee Tier 1 escalation (S_composite >= 0.40) on its own when ML suspicion is zero.
       With H = 0.65, P = 0.0, and V = 0.0:
         W_H = 0.35 * 0.65 + 0.30 * (0.65 - 0.30) = 0.2275 + 0.105 = 0.3325
         alpha = min(1.0, max(0.0, max(-0.15, 0.35) / 0.25)) = 1.0
         S_content = 0.0 + 1.0 * 0.3325 * (1.0 - 0.0) = 0.3325 < 0.40 (ALLOW)
       To reach the Tier 1 threshold S_composite >= 0.40 without velocity,
       the ML model probability P must satisfy:
       must satisfy: S_content = P + 0.3325 * (1.0 - P) = 0.3325 + 0.6675 * P >= 0.40
       => P >= (0.40 - 0.3325) / 0.6675 = 0.10112 (i.e. baseline ML suspicion P >= 0.1012).

    3. Smooth Monotonic Non-Decreasing Velocity Scaling (Probabilistic Union / Noisy-OR):
       S_composite = S_content + V * (1.0 - S_content)

       Guarantees d(S_composite)/dV >= 0 and d(S_composite)/dS_content >= 0 everywhere.

    4. Safe Degraded-State Policy (`ml_signal_status != "valid"`):
       Computes non-ML risk from `(H, 0.0, V)` (so high heuristics `H >= 0.80` or high
       velocity `V >= 0.75` still escalate to `BLOCK`) and applies a Tier-1 review floor
       `DEGRADED_REVIEW_FLOOR` (`0.40`, `FLAG`), preventing invalid/unavailable/degraded
       ML outputs from silently appearing as `0.0` / `ALLOW`. When `ml_signal_status == "valid"`,
       `onnx_probability` is strictly validated via `validate_ml_probability()` so `NaN`,
       non-finite, or out-of-range values fail explicitly rather than clamping to `0.0`.

    Returns:
        float: Composite fraud score bounded strictly in [0.0, 1.0].
    """
    if ml_signal_status != "valid":
        if ml_signal_status not in _VALID_NON_VALID_STATUSES:
            raise InvalidMLSignalError("invalid_ml_signal_status")
        non_ml_score = compute_composite_score(
            heuristic_score=heuristic_score,
            onnx_probability=0.0,
            velocity_score=velocity_score,
            ml_signal_status="valid",
        )
        return round(float(min(1.0, max(non_ml_score, DEGRADED_REVIEW_FLOOR))), 4)

    p = validate_ml_probability(onnx_probability)
    h = _clamp_unit_signal(heuristic_score)
    v = _clamp_unit_signal(velocity_score)

    # Step 1: Authoritative High-Risk Heuristic Override
    if h >= 0.80:
        return 1.0

    # Step 2: Continuous Gated Heuristic Blend
    alpha = min(1.0, max(0.0, max(p - 0.15, h - 0.30) / 0.25))
    w_h = 0.35 * h + 0.30 * max(0.0, h - 0.30)
    s_content = p + alpha * w_h * (1.0 - p)
    s_content = min(1.0, max(0.0, s_content))

    # Step 3: Smooth Monotonic Velocity Scaling (Probabilistic Union)
    s_composite = s_content + v * (1.0 - s_content)

    return round(float(min(1.0, max(0.0, s_composite))), 4)


class OnnxInferenceEngine:
    """Manages ONNX Runtime CPU session and evaluates SMS text messages.

    Evaluates a compiled in-graph TfidfVectorizer + CalibratedClassifierCV (LogisticRegression)
    pipeline running on the ONNX Runtime CPU execution provider with AVX-512 optimization
    (<0.1ms warm in-graph C++ execution).
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        metadata_path: str | Path | None = None,
        verify_sha256: bool = True,
    ) -> None:
        if model_path is None:
            # Default to bundled model in app/telecom/models
            current_dir = Path(__file__).parent
            model_path = current_dir / "models" / "sms_fraud_model.onnx"

        self.model_path = Path(model_path)
        if metadata_path is None:
            self.metadata_path: Path | None = self.model_path.parent / "sms_fraud_metadata.json"
        else:
            self.metadata_path = Path(metadata_path)
        self.verify_sha256 = verify_sha256
        self._model_sha256: str = ""
        self.session_options: ort.SessionOptions | None = None
        self.intra_op_num_threads: int = 1
        self.inter_op_num_threads: int = 1
        self.graph_optimization_level: ort.GraphOptimizationLevel = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        self.session: ort.InferenceSession | None = None
        self._session: ort.InferenceSession | None = None
        self._input_name: str = "text"
        self._init_session()

    @property
    def model_sha256(self) -> str:
        """Returns the verified SHA-256 hex digest of the loaded ONNX model binary."""
        return self._model_sha256

    def _verify_model_integrity(self) -> None:
        """Computes the SHA-256 of the ONNX model file and verifies it against metadata."""
        model_bytes = self.model_path.read_bytes()
        computed_sha256 = hashlib.sha256(model_bytes).hexdigest()
        self._model_sha256 = computed_sha256

        if not self.verify_sha256 or self.metadata_path is None:
            return
        if not self.metadata_path.exists():
            logger.warning(
                "ONNX metadata file not found at %s; skipping SHA-256 verification.",
                self.metadata_path,
            )
            return

        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception as err:
            raise RuntimeError(
                f"Failed to parse ONNX metadata file at {self.metadata_path}: {err}"
            ) from err

        expected_sha256 = metadata.get("model_sha256")
        if not expected_sha256:
            raise RuntimeError(
                f"Missing 'model_sha256' field in ONNX metadata at {self.metadata_path}"
            )
        if computed_sha256 != expected_sha256:
            raise RuntimeError(
                f"ONNX model SHA-256 mismatch for {self.model_path}: "
                f"expected {expected_sha256} (from {self.metadata_path.name}), "
                f"got {computed_sha256}"
            )

    def _init_session(self) -> None:
        """Initializes optimized ONNX Runtime CPU session after verifying SHA-256 integrity."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"ONNX model file not found at {self.model_path}")

        self._verify_model_integrity()

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Pin single intra/inter-op threads per session for throughput under concurrent workers
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        self.session_options = opts
        self.intra_op_num_threads = int(opts.intra_op_num_threads)
        self.inter_op_num_threads = int(opts.inter_op_num_threads)
        self.graph_optimization_level = opts.graph_optimization_level

        try:
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self._session = self.session
            # Cold-start warmup: run 1 dummy inference to prime threadpools & verify output contract
            warmup_tensor = np.array([["warmup text"]], dtype=object)
            warmup_outputs = self.session.run(None, {self._input_name: warmup_tensor})
            extract_onnx_probabilities(warmup_outputs, expected_batch_size=1)
            logger.info(
                "Initialized ONNX Runtime CPU session from %s (SHA-256: %s, warmup complete)",
                self.model_path,
                self._model_sha256,
            )
        except Exception as err:
            logger.error("Failed to load ONNX model from %s: %s", self.model_path, err)
            self.session = None
            self._session = None
            raise RuntimeError(
                f"Failed to initialize ONNX Runtime session from {self.model_path}: {err}"
            ) from err

    def evaluate_heuristics(self, text: str) -> tuple[float, list[str]]:
        """Fast regex pattern matching preceding the ML model.
        Delegates to shared evaluate_heuristics.
        """
        return evaluate_heuristics(text)

    _evaluate_heuristics = evaluate_heuristics

    def _get_active_session(self) -> ort.InferenceSession | None:
        """Returns the active ONNX Runtime session, or None if unavailable."""
        return self._session if self._session is not None else self.session

    def _is_circuit_open(self) -> bool:
        """Returns True when the ONNX session is unavailable or circuit-broken."""
        return bool(
            getattr(self, "_circuit_open", False)
            or (self._session is None and self.session is None)
        )

    @staticmethod
    def _build_inference_result(
        *,
        heuristic_score: float,
        base_signals: list[str],
        onnx_prob: float | None,
        ml_signal_status: MLSignalStatus,
        ml_error_reason: str | None,
        latency_ms: float,
    ) -> InferenceResult:
        """Builds a status-aware InferenceResult without masking invalid or degraded ML."""
        signals = list(base_signals)
        ml_signal_valid = ml_signal_status == "valid" and onnx_prob is not None
        effective_status: MLSignalStatus = (
            ml_signal_status
            if ml_signal_valid
            else (ml_signal_status if ml_signal_status != "valid" else "invalid")
        )

        fraud_score = compute_composite_score(
            heuristic_score=heuristic_score,
            onnx_probability=onnx_prob if ml_signal_valid else None,
            velocity_score=0.0,
            ml_signal_status=effective_status,
        )

        if ml_signal_valid and onnx_prob is not None:
            if onnx_prob >= 0.75:
                signals.append("ML:HIGH_FRAUD_PROBABILITY")
            elif onnx_prob >= 0.40:
                signals.append("ML:ELEVATED_FRAUD_PROBABILITY")
            else:
                signals.append("ML:BENIGN_CLASSIFICATION")
            reported_prob: float | None = round(onnx_prob, 4)
        else:
            if effective_status == "unavailable":
                signals.append("ML:ENGINE_UNAVAILABLE")
                signals.append("ENGINE:HEURISTIC_ONLY")
            elif effective_status == "invalid":
                signals.append("ML:SIGNAL_INVALID")
                signals.append("ENGINE:ONNX_FALLBACK")
            else:
                signals.append("ML:DEGRADED_MODE")
                engine_tag = (
                    "ENGINE:HEURISTIC_ONLY"
                    if ml_error_reason == "circuit_breaker_open"
                    else "ENGINE:ONNX_FALLBACK"
                )
                signals.append(engine_tag)
            reported_prob = None

        if fraud_score >= 0.75:
            verdict = "BLOCK"
        elif fraud_score >= 0.40:
            verdict = "FLAG"
        else:
            verdict = "ALLOW"

        return InferenceResult(
            verdict=verdict,
            fraud_score=round(fraud_score, 4),
            latency_ms=round(latency_ms, 3),
            signals=signals,
            model_version="1.0.0",
            onnx_probability=reported_prob,
            heuristic_score=round(heuristic_score, 4),
            ml_signal_status=effective_status,
            ml_signal_valid=ml_signal_valid,
            ml_error_reason=ml_error_reason,
        )

    def predict(self, text: str) -> InferenceResult:
        """Synchronously classifies an SMS text message with sub-millisecond execution."""
        t_start = time.perf_counter()

        # 1. Fast regex rule engine
        heuristic_score, base_signals = self.evaluate_heuristics(text)

        # 2. Explicit ML signal inference with strict output validation
        probs, ml_status, ml_error_reason = self.predict_proba_batch_with_status([text])
        onnx_prob = (
            probs[0] if (ml_status == "valid" and probs is not None and len(probs) == 1) else None
        )

        latency_ms = (time.perf_counter() - t_start) * 1000.0
        return self._build_inference_result(
            heuristic_score=heuristic_score,
            base_signals=base_signals,
            onnx_prob=onnx_prob,
            ml_signal_status=ml_status,
            ml_error_reason=ml_error_reason,
            latency_ms=latency_ms,
        )

    def predict_proba_batch_with_status(
        self, texts: list[str]
    ) -> tuple[list[float] | None, MLSignalStatus, str | None]:
        """Executes vectorized ONNX inference and returns probabilities plus signal status."""
        if not texts:
            return [], "valid", None

        active_session = self._get_active_session()
        if active_session is None:
            logger.error("ONNX inference unavailable: active session is None")
            return None, "unavailable", "onnx_session_unavailable"

        if bool(getattr(self, "_circuit_open", False)):
            logger.warning("ONNX inference bypassed in degraded mode: circuit breaker open")
            return None, "degraded", "circuit_breaker_open"

        try:
            input_tensor = np.array([[t] for t in texts], dtype=object)
            raw_outputs = active_session.run(None, {self._input_name: input_tensor})
            probs = extract_onnx_probabilities(raw_outputs, expected_batch_size=len(texts))
            return probs, "valid", None
        except InvalidMLSignalError as err:
            safe_reason = redact_sms_pii(str(err))
            logger.error("ONNX output signal validation failed: %s", safe_reason)
            return None, "invalid", safe_reason
        except Exception as err:
            logger.error("ONNX inference failed: %s", redact_sms_pii(str(err)))
            return None, "degraded", "onnx_runtime_error"

    def predict_proba_batch(self, texts: list[str]) -> list[float]:
        """Executes vectorized ONNX CPU inference across a batch of SMS messages.

        Raises `InvalidMLSignalError` if ONNX inference is unavailable, degraded, or
        returns invalid/non-finite probabilities instead of emitting `NaN` or `0.0`.
        """
        if not texts:
            return []
        probs, ml_status, ml_error_reason = self.predict_proba_batch_with_status(texts)
        if ml_status == "valid" and probs is not None:
            return probs
        raise InvalidMLSignalError(f"ml_signal_{ml_status}:{ml_error_reason or ml_status}")

    def predict_batch(self, texts: list[str]) -> list[InferenceResult]:
        """Classifies a batch of SMS messages using a single vectorized ONNX session call."""
        if not texts:
            return []
        t_start = time.perf_counter()
        heuristics = [self.evaluate_heuristics(t) for t in texts]
        probs, ml_status, ml_error_reason = self.predict_proba_batch_with_status(texts)

        per_item_latency_ms = ((time.perf_counter() - t_start) * 1000.0) / max(len(texts), 1)
        results: list[InferenceResult] = []
        for idx, (heuristic_score, base_signals) in enumerate(heuristics):
            onnx_prob = (
                probs[idx]
                if (ml_status == "valid" and probs is not None and idx < len(probs))
                else None
            )
            results.append(
                self._build_inference_result(
                    heuristic_score=heuristic_score,
                    base_signals=base_signals,
                    onnx_prob=onnx_prob,
                    ml_signal_status=ml_status,
                    ml_error_reason=ml_error_reason,
                    latency_ms=per_item_latency_ms,
                )
            )
        return results


_HAS_4DIGIT_OR_HYPHEN_OTP_RE = re.compile(r"\d{4}|\d{3}-\d{3}")
_HAS_9DIGIT_RE = re.compile(r"\d{9}")
_HAS_10DIGIT_RE = re.compile(r"\d{10}")
_HAS_STANDALONE_OTP_CANDIDATE_RE = re.compile(r"\d{6}|\d{3,4}-\d{3,4}")
_SSN_KEYWORD_RE = re.compile(r"\b(?:ssn|social|tax|tin|itin)\b", re.IGNORECASE)
_OTP_KEYWORD_RE = re.compile(
    r"\b(?:code|otp|pin|passcode|token|2fa|mfa|verification|confirmation|confirm|"
    r"auth(?:entication)?|security|login|account)\b",
    re.IGNORECASE,
)
_OTP_SUFFIX_TRIGGER_RE = re.compile(
    r"\b(?:is|as)\s+(?:your|the|a)\b|\bto\s+(?:verify|confirm|sign\s+in|log\s*in|authenticate|unlock)\b|\d[\]\)\"']?\s+for\b",
    re.IGNORECASE,
)
_SSN_CONTEXT_RE = re.compile(
    r"(\b(?:ssn|social\s+security(?:\s+(?:number|no|num|id))?|tax\s*id|tin|itin)\b"
    r"(?:\s*(?:is|number|no|num|id|#|:|=|-))*\s*)"
    r"(?<![$€£\d])(?<!\d\.)\d{9}\b(?![\d]|\.\d)",
    re.IGNORECASE,
)
_CONTIGUOUS_NANP_PHONE_RE = re.compile(
    r"[1-9](?<=\b[1-9])(?<![+\d$€£-]\d)(?<!\d\.\d)"
    r"(?:(?<=1)[2-9]\d{2}[2-9]\d{6}|(?<=[2-9])\d{2}[2-9]\d{6})\b(?![\d-]|\.\d)"
)
_OTP_CONTEXT_PREFIX_RE = re.compile(
    r"(\b(?:code|otp|pin|passcode|token|2fa|mfa|verification|confirmation|confirm|"
    r"auth(?:entication)?|security)\b"
    r"(?:(?:\s+for\b[^.:\n\d]{0,32})?\s+(?:is|number|id))?\s*[:=#-]?\s*)"
    r"[\[\(\"']?(?:[A-Za-z]-)?(?<![$€£\d])(?<!\d\.)(?:\d{3,4}-\d{3,4}|\d{4,8})\b(?![-\d]|\.\d)[\]\)\"']?",
    re.IGNORECASE,
)
_OTP_CONTEXT_SUFFIX_RE = re.compile(
    r"(?<![$€£\d-])(?<!\d\.)[\[\(\"']?\b(?:[A-Za-z]-)?(?:\d{3,4}-\d{3,4}|\d{4,8})\b(?![-\d]|\.\d)[\]\)\"']?"
    r"(\s+(?:is\s+(?:your|the|a)|as\s+(?:your|the|a)|for\b|"
    r"to\s+(?:verify|confirm|sign\s+in|log\s*in|authenticate|unlock))"
    r"\b[^.\n]{0,40}\b(?:code|otp|pin|passcode|token|2fa|mfa|verification|login|"
    r"auth(?:entication)?|account)\b)",
    re.IGNORECASE,
)
_STANDALONE_OTP_RE = re.compile(
    r"\d(?<=\b\d)(?<![$€£\d-]\d)(?<!\d\.\d)(?:\d{2,3}-\d{3,4}|\d{5,7})\b(?![-\d]|\.\d)"
)


def redact_sms_pii(text: str) -> str:
    """Masks SMS PII (phones, emails, SSNs, cards, OTP codes) while preserving triage words."""
    if not text:
        return text
    redacted, _ = redact_text(text)
    if not _HAS_4DIGIT_OR_HYPHEN_OTP_RE.search(redacted):
        return redacted
    if _HAS_9DIGIT_RE.search(redacted) and _SSN_KEYWORD_RE.search(redacted):
        redacted = _SSN_CONTEXT_RE.sub(r"\1[REDACTED_SSN]", redacted)
    if _HAS_10DIGIT_RE.search(redacted):
        redacted = _CONTIGUOUS_NANP_PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    if not _HAS_4DIGIT_OR_HYPHEN_OTP_RE.search(redacted):
        return redacted
    if _OTP_KEYWORD_RE.search(redacted):
        redacted = _OTP_CONTEXT_PREFIX_RE.sub(r"\1[REDACTED_CODE]", redacted)
        if _HAS_4DIGIT_OR_HYPHEN_OTP_RE.search(redacted) and _OTP_SUFFIX_TRIGGER_RE.search(
            redacted
        ):
            redacted = _OTP_CONTEXT_SUFFIX_RE.sub(r"[REDACTED_CODE]\1", redacted)
    if not _HAS_STANDALONE_OTP_CANDIDATE_RE.search(redacted):
        return redacted
    return _STANDALONE_OTP_RE.sub("[REDACTED_CODE]", redacted)


OnnxSmsInferenceEngine = OnnxInferenceEngine
ONNXFraudEngine = OnnxInferenceEngine

# Global singleton instance
_engine_instance: OnnxInferenceEngine | None = None


def get_inference_engine() -> OnnxInferenceEngine:
    """Returns the singleton OnnxInferenceEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OnnxInferenceEngine()
    return _engine_instance

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, cast

from app.config import get_settings

PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ssn": re.compile(r"\d(?<=\b\d)(?<![+\d]\d)(?<!\d\.\d)\d{2}([- .])\d{2}\1\d{4}\b(?![\d]|\.\d)"),
    "iban": re.compile(r"\b[A-Za-z]{2}\d{2}(?:[ -]?[A-Za-z0-9]){11,30}\b"),
    "ipv6": re.compile(
        r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b|\b(?:[A-Fa-f0-9]{1,4}:){1,7}:|:(?::[A-Fa-f0-9]{1,4}){1,7}\b"
    ),
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    ),
    "card": re.compile(r"\d(?<=\b\d)(?<![+\d]\d)(?<!\d\.\d)(?:[ -]*?\d){12,18}\b(?![\d]|\.\d)"),
    "phone": re.compile(
        r"(?<![\w:+])(?:"
        r"\+\d{1,3}(?:[\s.-]?\(\d{1,4}\)|[\s.-]?\d{1,5}){2,5}"
        r"|\+\d{7,15}"
        r"|(?:\+?1[\s.-])?(?:\(\d{3}\)[\s.-]?|\d{3}[\s.-])\d{3}[\s.-]\d{4}"
        r")(?![\w:+])"
    ),
    "jwt": re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"),
    "api_key": re.compile(
        r"\b(?:sk|pk)[-_][A-Za-z0-9_-]{12,}\b|\b(?:sk-proj|sk-ant)-[A-Za-z0-9_-]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{36}\b"
    ),
}

REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        PATTERNS["email"],
        "[REDACTED_EMAIL]",
    ),
    (
        PATTERNS["ssn"],
        "[REDACTED_SSN]",
    ),
    (
        PATTERNS["iban"],
        "[REDACTED_IBAN]",
    ),
    (
        PATTERNS["ipv6"],
        "[REDACTED_IP]",
    ),
    (
        PATTERNS["ipv4"],
        "[REDACTED_IP]",
    ),
    (
        PATTERNS["card"],
        "[REDACTED_CARDLIKE]",
    ),
    (
        PATTERNS["phone"],
        "[REDACTED_PHONE]",
    ),
    (
        PATTERNS["jwt"],
        "[REDACTED_JWT]",
    ),
    (
        PATTERNS["api_key"],
        "[REDACTED_API_KEY]",
    ),
)

_HAS_DIGIT_RE: re.Pattern[str] = re.compile(r"\d")
_HAS_3DIGIT_RE: re.Pattern[str] = re.compile(r"\d{3}")
_HAS_SSN_CANDIDATE_RE: re.Pattern[str] = re.compile(r"\d{3}[- .]\d{2}[- .]\d{4}")
_HAS_CARD_CANDIDATE_RE: re.Pattern[str] = re.compile(r"(?:\d[ -]?){13}")
_HAS_PHONE_CANDIDATE_RE: re.Pattern[str] = re.compile(r"\+\d|\(\d{3}\)|\d{3}[\s.-]\d{3}[\s.-]\d{4}")
_HAS_IBAN_PREFIX_RE: re.Pattern[str] = re.compile(r"[A-Za-z]{2}\d{2}")
_HAS_API_KEY_PREFIX_RE: re.Pattern[str] = re.compile(r"(?:sk|pk)[-_]|AKIA|gh[pousr]_")
_HAS_INJECTION_KEYWORD_RE: re.Pattern[str] = re.compile(
    r"system\s+override|ignore\s+|developer\s+mode|disregard\s+|admin\s+escalation",
    re.IGNORECASE,
)

ZERO_WIDTH_PATTERN: re.Pattern[str] = re.compile(
    r"[\u200B\u200C\u200D\u200E\u200F\uFEFF\u00AD\u2060\u2061\u2062\u2063\u2064]"
)

HIDDEN_DOM_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"<\s*[^>]+(?:display\s*:\s*none|font-size\s*:\s*0|visibility\s*:\s*hidden|opacity\s*:\s*0|hidden)[^>]*>.*?</[^>]+>",
    re.IGNORECASE | re.DOTALL,
)

DANGEROUS_DOM_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"<\s*(?:script|iframe|style|object|embed)[^>]*>.*?</\s*(?:script|iframe|style|object|embed)\s*>",
    re.IGNORECASE | re.DOTALL,
)

PROMPT_INJECTION_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)\b(?:system\s+override|ignore\s+(?:all\s+)?previous\s+instructions?|you\s+are\s+now\s+in\s+developer\s+mode|disregard\s+(?:the\s+)?prior\s+commands?|admin\s+escalation\s+code)\b"
)


def sanitize_prompt_injection(value: str) -> tuple[str, bool, list[str]]:
    """Sanitize indirect prompt injection vectors (zero-width Unicode, hidden DOM, canaries)."""
    sanitized = value
    changed = False
    warnings: list[str] = []

    if ZERO_WIDTH_PATTERN.search(sanitized):
        sanitized = ZERO_WIDTH_PATTERN.sub("", sanitized)
        changed = True
        warnings.append("zero_width_unicode_stripped")

    if "<" in sanitized:
        if HIDDEN_DOM_TAG_PATTERN.search(sanitized):
            sanitized = HIDDEN_DOM_TAG_PATTERN.sub(" [FLAGGED_HIDDEN_DOM_INJECTION] ", sanitized)
            changed = True
            warnings.append("hidden_dom_injection_stripped")

        if DANGEROUS_DOM_TAG_PATTERN.search(sanitized):
            sanitized = DANGEROUS_DOM_TAG_PATTERN.sub(" [FLAGGED_DANGEROUS_TAG] ", sanitized)
            changed = True
            warnings.append("dangerous_tag_stripped")

    if _HAS_INJECTION_KEYWORD_RE.search(sanitized) and PROMPT_INJECTION_PATTERN.search(sanitized):
        sanitized = PROMPT_INJECTION_PATTERN.sub("[FLAGGED_INJECTION_ATTEMPT]", sanitized)
        changed = True
        warnings.append("prompt_injection_pattern_neutralized")

    return sanitized, changed, warnings


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_NONPROD_FALLBACK_HMAC_SEED = "sentinelflow-nonprod-fallback-hmac-key-not-for-production"


def pseudonymize_telecom_identifier(
    value: str,
    *,
    namespace: str,
    length: int = 32,
    secret: str | None = None,
    key_id: str | None = None,
) -> str:
    """Compute a domain-separated, key-version-bound HMAC-SHA256 pseudonymous identifier.

    NOTE: HMAC-derived identifiers are pseudonymous (linkable across records sharing
    the same key, key_id, and namespace), NOT anonymous. They prevent offline rainbow-table
    and dictionary enumeration over small-domain telecom inputs (E.164 phone numbers,
    NANP prefixes, and IP addresses) provided the secret key remains confidential.
    Outputs at least 32 hexadecimal characters (128 bits) to eliminate avoidable birthday
    collisions across persistent dispute records and high-throughput Redis velocity keys.
    Fails closed in production if TELECOM_HMAC_SECRET is absent, empty, or whitespace.
    """
    cfg = get_settings()
    resolved_key_id = (key_id if key_id is not None else cfg.TELECOM_HMAC_KEY_ID).strip()
    if not resolved_key_id:
        raise ValueError("key_id must be a non-empty string.")

    if secret is not None:
        resolved_secret = secret
    elif cfg.TELECOM_HMAC_SECRET is not None:
        resolved_secret = cfg.TELECOM_HMAC_SECRET
    elif cfg.APP_ENV in ("development", "test"):
        resolved_secret = _NONPROD_FALLBACK_HMAC_SEED
    else:
        resolved_secret = ""

    if not resolved_secret or not resolved_secret.strip():
        raise RuntimeError(
            "TELECOM_HMAC_SECRET must be configured for pseudonymous telecom identifier derivation."
        )
    if cfg.APP_ENV == "production" and resolved_secret.strip() == _NONPROD_FALLBACK_HMAC_SEED:
        raise RuntimeError(
            "TELECOM_HMAC_SECRET cannot use the non-production fallback key in production."
        )
    if not namespace or not namespace.strip():
        raise ValueError("namespace must be a non-empty string.")
    if length < 32 or length > 64:
        raise ValueError("length must be between 32 and 64 hex characters (at least 128 bits).")
    canonical_payload = f"{resolved_key_id}:{namespace.strip()}:{value.strip()}".encode()
    digest = hmac.new(
        resolved_secret.encode("utf-8"),
        canonical_payload,
        hashlib.sha256,
    ).hexdigest()
    return digest[:length]


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        items = cast(list[object], value)
        parts: list[str] = []
        for item in items:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                item_dict = cast(dict[str, object], item)
                text_value = item_dict.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue
                content_value = item_dict.get("content")
                if isinstance(content_value, str):
                    parts.append(content_value)
                    continue
                parts.append(json.dumps(item_dict, sort_keys=True, default=str))
                continue
            parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def redact_text(value: str) -> tuple[str, bool]:
    sanitized, inject_changed, _ = sanitize_prompt_injection(value)
    redacted = sanitized
    changed = inject_changed

    if "@" in redacted:
        updated = PATTERNS["email"].sub("[REDACTED_EMAIL]", redacted)
        if updated != redacted:
            changed = True
            redacted = updated

    if ":" in redacted:
        updated = PATTERNS["ipv6"].sub("[REDACTED_IP]", redacted)
        if updated != redacted:
            changed = True
            redacted = updated

    if _HAS_DIGIT_RE.search(redacted):
        if _HAS_SSN_CANDIDATE_RE.search(redacted):
            updated = PATTERNS["ssn"].sub("[REDACTED_SSN]", redacted)
            if updated != redacted:
                changed = True
                redacted = updated

        if _HAS_IBAN_PREFIX_RE.search(redacted):
            updated = PATTERNS["iban"].sub("[REDACTED_IBAN]", redacted)
            if updated != redacted:
                changed = True
                redacted = updated

        if "." in redacted:
            updated = PATTERNS["ipv4"].sub("[REDACTED_IP]", redacted)
            if updated != redacted:
                changed = True
                redacted = updated

        if _HAS_CARD_CANDIDATE_RE.search(redacted):
            updated = PATTERNS["card"].sub("[REDACTED_CARDLIKE]", redacted)
            if updated != redacted:
                changed = True
                redacted = updated

        if _HAS_PHONE_CANDIDATE_RE.search(redacted):
            updated = PATTERNS["phone"].sub("[REDACTED_PHONE]", redacted)
            if updated != redacted:
                changed = True
                redacted = updated

    if "eyJ" in redacted:
        updated = PATTERNS["jwt"].sub("[REDACTED_JWT]", redacted)
        if updated != redacted:
            changed = True
            redacted = updated

    if _HAS_API_KEY_PREFIX_RE.search(redacted):
        updated = PATTERNS["api_key"].sub("[REDACTED_API_KEY]", redacted)
        if updated != redacted:
            changed = True
            redacted = updated

    return redacted, changed


def redact_value(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (list, tuple, set)):
        items = cast(list[object], list(value))
        redacted_items: list[Any] = []
        changed = False
        for item in items:
            redacted_item, item_changed = redact_value(item)
            redacted_items.append(redacted_item)
            changed = changed or item_changed
        if isinstance(value, tuple):
            return tuple(redacted_items), changed
        if isinstance(value, set):
            return set(redacted_items), changed
        return redacted_items, changed
    if isinstance(value, dict):
        value_dict = cast(dict[str, object], value)
        redacted_dict: dict[str, Any] = {}
        changed = False
        for key, item in value_dict.items():
            redacted_key = key
            if isinstance(key, str):
                redacted_key_text, key_changed = redact_text(key)
                redacted_key = redacted_key_text
                changed = changed or key_changed
            redacted_item, item_changed = redact_value(item)
            redacted_dict[redacted_key] = redacted_item
            changed = changed or item_changed
        return redacted_dict, changed
    return value, False

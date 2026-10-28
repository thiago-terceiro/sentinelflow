from __future__ import annotations

import hashlib
import json
import re
from typing import Any, cast

PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "iban": re.compile(r"\b[A-Za-z]{2}\d{2}(?:[ -]?[A-Za-z0-9]){11,30}\b"),
    "ipv6": re.compile(
        r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b|\b(?:[A-Fa-f0-9]{1,4}:){1,7}:|:(?::[A-Fa-f0-9]{1,4}){1,7}\b"
    ),
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    ),
    "card": re.compile(r"(?<![.\d])\b(?:\d[ -]*?){13,19}\b(?![.\d])"),
    "phone": re.compile(
        r"(?<![\w:+])(?:\+\d{1,3}[\s.-]?(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-]?)\d{3,4}[\s.-]?\d{3,4}|(?:\(\d{3}\)[\s.-]?|\d{3}[\s.-])\d{3}[\s.-]\d{4})(?![\w:+])"
    ),
    "jwt": re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"),
    "api_key": re.compile(
        r"\b(?:sk|pk)[-_][A-Za-z0-9_-]{12,}\b|\b(?:sk-proj|sk-ant)-[A-Za-z0-9_-]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{36}\b"
    ),
}

REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
    (
        re.compile(r"\b[A-Za-z]{2}\d{2}(?:[ -]?[A-Za-z0-9]){11,30}\b"),
        "[REDACTED_IBAN]",
    ),
    (
        re.compile(
            r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b|\b(?:[A-Fa-f0-9]{1,4}:){1,7}:|:(?::[A-Fa-f0-9]{1,4}){1,7}\b"
        ),
        "[REDACTED_IP]",
    ),
    (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        "[REDACTED_IP]",
    ),
    (
        re.compile(r"(?<![.\d])\b(?:\d[ -]*?){13,19}\b(?![.\d])"),
        "[REDACTED_CARDLIKE]",
    ),
    (
        re.compile(
            r"(?<![\w:+])(?:\+\d{1,3}[\s.-]?(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-]?)\d{3,4}[\s.-]?\d{3,4}|(?:\(\d{3}\)[\s.-]?|\d{3}[\s.-])\d{3}[\s.-]\d{4})(?![\w:+])"
        ),
        "[REDACTED_PHONE]",
    ),
    (
        re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"),
        "[REDACTED_JWT]",
    ),
    (
        re.compile(
            r"\b(?:sk|pk)[-_][A-Za-z0-9_-]{12,}\b|\b(?:sk-proj|sk-ant)-[A-Za-z0-9_-]{20,}\b|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{36}\b"
        ),
        "[REDACTED_API_KEY]",
    ),
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

    if HIDDEN_DOM_TAG_PATTERN.search(sanitized):
        sanitized = HIDDEN_DOM_TAG_PATTERN.sub(" [FLAGGED_HIDDEN_DOM_INJECTION] ", sanitized)
        changed = True
        warnings.append("hidden_dom_injection_stripped")

    if DANGEROUS_DOM_TAG_PATTERN.search(sanitized):
        sanitized = DANGEROUS_DOM_TAG_PATTERN.sub(" [FLAGGED_DANGEROUS_TAG] ", sanitized)
        changed = True
        warnings.append("dangerous_tag_stripped")

    if PROMPT_INJECTION_PATTERN.search(sanitized):
        sanitized = PROMPT_INJECTION_PATTERN.sub("[FLAGGED_INJECTION_ATTEMPT]", sanitized)
        changed = True
        warnings.append("prompt_injection_pattern_neutralized")

    return sanitized, changed, warnings


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    for pattern, replacement in REDACTION_PATTERNS:
        updated = pattern.sub(replacement, redacted)
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

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, cast

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
    redacted = value
    changed = False
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

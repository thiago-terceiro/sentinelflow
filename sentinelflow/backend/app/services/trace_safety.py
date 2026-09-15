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
        re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)"),
        "[REDACTED_PHONE]",
    ),
    (
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        "[REDACTED_CARDLIKE]",
    ),
    (
        re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"),
        "[REDACTED_JWT]",
    ),
    (
        re.compile(r"\b(?:sk|pk)_[A-Za-z0-9_-]{12,}\b"),
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
    if isinstance(value, list):
        items = cast(list[object], value)
        redacted_items: list[Any] = []
        changed = False
        for item in items:
            redacted_item, item_changed = redact_value(item)
            redacted_items.append(redacted_item)
            changed = changed or item_changed
        return redacted_items, changed
    if isinstance(value, dict):
        value_dict = cast(dict[str, object], value)
        redacted_dict: dict[str, Any] = {}
        changed = False
        for key, item in value_dict.items():
            redacted_item, item_changed = redact_value(item)
            redacted_dict[key] = redacted_item
            changed = changed or item_changed
        return redacted_dict, changed
    return value, False

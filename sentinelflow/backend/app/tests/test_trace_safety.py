from __future__ import annotations

from app.services.trace_safety import redact_text, redact_value, sha256_text


def test_redact_text_masks_sensitive_patterns() -> None:
    original = "email john.doe@example.com card 4111 1111 1111 1111 token sk_ABC123456789"

    redacted, changed = redact_text(original)

    assert changed is True
    assert "john.doe@example.com" not in redacted
    assert "4111 1111 1111 1111" not in redacted
    assert "sk_ABC123456789" not in redacted


def test_redact_value_recurses_into_structures() -> None:
    value: dict[str, object] = {
        "user": "alice@example.com",
        "nested": ["+1 (212) 555-1000", {"jwt": "eyJfoo.bar.baz"}],
    }

    redacted, changed = redact_value(value)

    assert changed is True
    assert redacted["user"] == "[REDACTED_EMAIL]"
    assert redacted["nested"][0] == "[REDACTED_PHONE]"
    assert redacted["nested"][1]["jwt"] == "[REDACTED_JWT]"


def test_sha256_text_is_stable() -> None:
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abcd")

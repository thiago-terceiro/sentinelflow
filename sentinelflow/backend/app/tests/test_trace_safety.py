from __future__ import annotations

from app.services.trace_safety import redact_text, redact_value, sha256_text


def test_redact_text_masks_sensitive_patterns() -> None:
    original = (
        "email john.doe@example.com card 4111 1111 1111 1111 "
        "token sk_ABC123456789 ssn 123-45-6789 ip 192.168.1.1 "
        "ipv6 2001:0db8:85a3:0000:0000:8a2e:0370:7334 "
        "iban DE89 3704 0044 0532 0130 00 "
        "modern_key sk-proj-1234567890abcdef1234"
    )

    redacted, changed = redact_text(original)

    assert changed is True
    assert "john.doe@example.com" not in redacted
    assert "4111 1111 1111 1111" not in redacted
    assert "sk_ABC123456789" not in redacted
    assert "123-45-6789" not in redacted
    assert "192.168.1.1" not in redacted
    assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" not in redacted
    assert "DE89 3704 0044 0532 0130 00" not in redacted
    assert "sk-proj-1234567890abcdef1234" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert "[REDACTED_IP]" in redacted
    assert "[REDACTED_IBAN]" in redacted
    assert "[REDACTED_API_KEY]" in redacted


def test_redact_value_recurses_into_structures() -> None:
    value: dict[str, object] = {
        "user": "alice@example.com",
        "nested": ["+1 (212) 555-1000", {"jwt": "eyJfoo.bar.baz"}],
        "tuple_items": ("bob@example.com", "192.168.1.5"),
        "set_items": {"carol@example.com"},
    }

    redacted, changed = redact_value(value)

    assert changed is True
    assert redacted["user"] == "[REDACTED_EMAIL]"
    assert redacted["nested"][0] == "[REDACTED_PHONE]"
    assert redacted["nested"][1]["jwt"] == "[REDACTED_JWT]"
    assert redacted["tuple_items"] == ("[REDACTED_EMAIL]", "[REDACTED_IP]")
    assert "[REDACTED_EMAIL]" in redacted["set_items"]


def test_sha256_text_is_stable() -> None:
    assert sha256_text("abc") == sha256_text("abc")
    assert sha256_text("abc") != sha256_text("abcd")

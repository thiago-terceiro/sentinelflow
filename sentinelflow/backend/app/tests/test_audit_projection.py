from __future__ import annotations

from app.security import Role
from app.services.audit import project_payload_for_roles


def _payload() -> dict[str, object]:
    return {
        "model_used": "gpt-4.1-mini",
        "response_id": "resp_123",
        "iteration": 1,
        "used_heuristic": False,
        "recommendation": "approve",
        "confidence": 0.7,
        "prompt_redacted": "Customer email [REDACTED_EMAIL]",
        "output_redacted": "Model summary",
        "reasoning_redacted": "step summary",
        "prompt_sha256": "abc",
        "output_sha256": "def",
        "reasoning_sha256": "ghi",
        "redaction_applied": True,
        "input_tokens": 10,
        "output_tokens": 20,
    }


def test_project_payload_for_reviewer_hides_raw_trace_content() -> None:
    projected = project_payload_for_roles(_payload(), {Role.REVIEWER})

    assert "prompt_redacted" not in projected
    assert "output_redacted" not in projected
    assert "prompt_sha256" not in projected
    assert projected["model_used"] == "gpt-4.1-mini"


def test_project_payload_for_auditor_includes_rich_trace_fields() -> None:
    projected = project_payload_for_roles(_payload(), {Role.AUDITOR})

    assert projected["prompt_redacted"] == "Customer email [REDACTED_EMAIL]"
    assert projected["output_sha256"] == "def"


def test_project_payload_for_admin_includes_rich_trace_fields() -> None:
    projected = project_payload_for_roles(_payload(), {Role.ADMIN})

    assert projected["prompt_sha256"] == "abc"
    assert projected["reasoning_redacted"] == "step summary"


def test_project_payload_for_investigator_is_minimal() -> None:
    projected = project_payload_for_roles(_payload(), {Role.INVESTIGATOR})

    assert projected == {
        "model_used": "gpt-4.1-mini",
        "response_id": "resp_123",
        "iteration": 1,
        "used_heuristic": False,
        "recommendation": "approve",
        "confidence": 0.7,
    }

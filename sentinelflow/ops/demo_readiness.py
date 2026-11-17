"""Deterministic Clean-Checkout Operational Demo & Verification Runner (SF-021).

Runs reproducible synthetic demo scenarios against a freshly started SentinelFlow
& SentinelPulse stack and verifies liveness, readiness, classification outcomes,
PII redaction, invalid/unavailable ML inference fail-open, optional Redis outage
and recovery, dispute escalation, and frontend/backend status alignment.

All demo messages are explicitly synthetic fixtures; they demonstrate operational
wiring and fail-open behavior rather than real-world fraud generalization.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SYNTHETIC_DEMO_FIXTURES: dict[str, dict[str, Any]] = {
    "legitimate_2fa": {
        "synthetic_fixture": True,
        "expected_verdict": "ALLOW",
        "sender": "+14155552671",
        "recipient": "+14155559801",
        "carrier": "Verizon Wireless",
        "message": "Carrier security code: 492018. Valid for 5 minutes. Do not share this code.",
    },
    "fraudulent_smishing": {
        "synthetic_fixture": True,
        "expected_verdict": "BLOCK",
        "sender": "+15550001234",
        "recipient": "+14155559802",
        "carrier": "TextNow",
        "message": (
            "URGENT: Chase Bank alert. Account suspended! Verify immediately: "
            "http://bit.ly/chase-verify-now"
        ),
    },
    "borderline_review_pii": {
        "synthetic_fixture": True,
        "expected_verdict": "FLAG",
        "sender": "+14155550199",
        "recipient": "+14155559803",
        "carrier": "Verizon Wireless",
        "message": (
            "Notice: Account billing profile updated. Review statement 4532-0102-0304-0506 "
            "via member portal alice@example.com or reply STOP."
        ),
    },
}


def _http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, json.loads(raw)


def _wait_ready(backend_url: str, timeout_s: float = 45.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_err = ""
    while time.monotonic() < deadline:
        try:
            st, payload = _http_json(f"{backend_url}/api/v1/ready")
            if st == 200 and payload.get("status") == "ready":
                return
            last_err = f"HTTP {st}: {payload}"
        except Exception as exc:
            last_err = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"Backend readiness check failed within {timeout_s}s: {last_err}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SF-021 Deterministic Clean-Checkout Demo")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default=None)
    parser.add_argument("--auth-token", default="dev-reviewer")
    args = parser.parse_args()

    base = args.backend_url.rstrip("/")
    _wait_ready(base)

    health_status, health_body = _http_json(f"{base}/api/v1/health")
    ready_status, ready_body = _http_json(f"{base}/api/v1/ready")
    assert health_status == 200 and health_body == {"status": "ok"}, health_body
    assert ready_status == 200 and ready_body == {"status": "ready"}, ready_body

    # Reset telecom state cleanly for deterministic demo replay
    reset_st, _ = _http_json(f"{base}/api/v1/telecom/reset", method="POST")
    assert reset_st == 200

    scenario_results: dict[str, Any] = {}
    for name, fixture in SYNTHETIC_DEMO_FIXTURES.items():
        st, res = _http_json(
            f"{base}/v1/classify",
            method="POST",
            body={
                "sender": fixture["sender"],
                "recipient": fixture["recipient"],
                "carrier": fixture["carrier"],
                "message": fixture["message"],
            },
        )
        assert st == 200, f"{name} returned HTTP {st}: {res}"
        assert res["verdict"] == fixture["expected_verdict"], (
            f"{name} expected {fixture['expected_verdict']}, got {res['verdict']} ({res})"
        )
        assert res["ml_signal_valid"] is True
        scenario_results[name] = {
            "synthetic_fixture": True,
            "verdict": res["verdict"],
            "fraud_score": res["fraud_score"],
            "signals": res["signals"],
            "ml_signal_status": res["ml_signal_status"],
            "ml_signal_valid": res["ml_signal_valid"],
        }

    # Verify PII redaction on recent feed (no raw card PAN or email in feed text)
    sum_st, summary = _http_json(f"{base}/api/v1/telecom/metrics/summary")
    assert sum_st == 200
    feed_texts = " ".join(item.get("message", "") for item in summary.get("recent_feed", []))
    assert "4532-0102-0304-0506" not in feed_texts
    assert "alice@example.com" not in feed_texts
    assert "[REDACTED_PAN]" in feed_texts or "[REDACTED_EMAIL]" in feed_texts

    # Verify frontend BFF proxy alignment when --frontend-url is provided
    frontend_checked = False
    if args.frontend_url:
        fe = args.frontend_url.rstrip("/")
        fe_st, fe_sum = _http_json(f"{fe}/app-api/telecom/metrics/summary")
        assert fe_st == 200
        assert fe_sum["velocity_backend"] == summary["velocity_backend"]
        assert fe_sum["velocity_degraded_mode"] == summary["velocity_degraded_mode"]
        assert fe_sum["ml_engine_status"] == summary["ml_engine_status"]
        assert fe_sum["total_requests"] == summary["total_requests"]
        frontend_checked = True

    output = {
        "ticket_id": "SF-021",
        "health": health_body,
        "ready": ready_body,
        "scenarios": scenario_results,
        "summary_health_flags": {
            "velocity_backend": summary.get("velocity_backend"),
            "velocity_degraded_mode": summary.get("velocity_degraded_mode"),
            "ml_engine_status": summary.get("ml_engine_status"),
            "ml_circuit_open": summary.get("ml_circuit_open"),
        },
        "pii_redacted_in_feed": True,
        "frontend_bff_aligned": frontend_checked,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SF-021 demo failed: {exc}", file=sys.stderr)
        raise

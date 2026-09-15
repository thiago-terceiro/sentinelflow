from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_DEV_INVESTIGATOR_TOKEN = "dev-investigator"
DEFAULT_DEV_REVIEWER_TOKEN = "dev-reviewer"
LOCAL_SMOKE_HOSTS = {"localhost", "127.0.0.1"}


@dataclass(frozen=True, slots=True)
class SmokeCredentials:
    auth_mode: str
    investigator_token: str
    reviewer_token: str


JsonObject = dict[str, Any]
JsonValue = JsonObject | list[Any]
TERMINAL_STREAM_EVENTS = {"approval_required", "run_completed", "run_failed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SentinelFlow production-like smoke test.")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--auth-mode",
        choices=["dev_tokens", "bearer_tokens"],
        default=os.getenv("SMOKE_AUTH_MODE", "dev_tokens"),
        help="Use dev token defaults for local demo, or require explicit bearer tokens.",
    )
    parser.add_argument(
        "--investigator-token",
        default=os.getenv("SMOKE_INVESTIGATOR_TOKEN"),
    )
    parser.add_argument(
        "--reviewer-token",
        default=os.getenv("SMOKE_REVIEWER_TOKEN"),
    )
    parser.add_argument(
        "--require-provider",
        action="store_true",
        default=(os.getenv("SMOKE_REQUIRE_PROVIDER", "false").lower() == "true"),
        help="Fail when all audit rows indicate heuristic fallback.",
    )
    parser.add_argument(
        "--require-telemetry",
        action="store_true",
        default=(os.getenv("SMOKE_REQUIRE_TELEMETRY", "false").lower() == "true"),
        help="Fail when telemetry exporter is not configured or probe emission fails.",
    )
    return parser.parse_args()


def _is_local_base_url(base_url: str) -> bool:
    host = urlparse(base_url).hostname
    return host in LOCAL_SMOKE_HOSTS


def _resolve_credentials(args: argparse.Namespace) -> SmokeCredentials:
    investigator_token = args.investigator_token
    reviewer_token = args.reviewer_token

    if args.auth_mode == "dev_tokens":
        if not investigator_token:
            if not _is_local_base_url(args.base_url):
                raise RuntimeError(
                    "Refusing default dev investigator token for non-local base URL. "
                    "Pass --investigator-token explicitly or switch to --auth-mode bearer_tokens."
                )
            investigator_token = DEFAULT_DEV_INVESTIGATOR_TOKEN
        if not reviewer_token:
            if not _is_local_base_url(args.base_url):
                raise RuntimeError(
                    "Refusing default dev reviewer token for non-local base URL. "
                    "Pass --reviewer-token explicitly or switch to --auth-mode bearer_tokens."
                )
            reviewer_token = DEFAULT_DEV_REVIEWER_TOKEN
        return SmokeCredentials(
            auth_mode=args.auth_mode,
            investigator_token=investigator_token,
            reviewer_token=reviewer_token,
        )

    if not investigator_token or not reviewer_token:
        raise RuntimeError(
            "--auth-mode bearer_tokens requires both --investigator-token and --reviewer-token "
            "(or SMOKE_INVESTIGATOR_TOKEN and SMOKE_REVIEWER_TOKEN)."
        )
    return SmokeCredentials(
        auth_mode=args.auth_mode,
        investigator_token=investigator_token,
        reviewer_token=reviewer_token,
    )


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: JsonObject | None = None,
) -> JsonValue:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_stream_events(
    base_url: str,
    investigation_id: str,
    token: str,
    *,
    timeout_seconds: int = 90,
    max_events: int = 300,
) -> list[JsonObject]:
    headers = {
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    request = Request(
        f"{base_url}/api/v1/investigations/{investigation_id}/stream",
        headers=headers,
        method="GET",
    )
    events: list[JsonObject] = []
    buffer: list[str] = []
    deadline = time.time() + timeout_seconds

    with urlopen(request, timeout=timeout_seconds) as response:
        while len(events) < max_events and time.time() < deadline:
            line = response.readline()
            if not line:
                break
            text = line.decode("utf-8").strip()
            if not text:
                if not buffer:
                    continue
                payload = "\n".join(buffer)
                buffer = []
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    event = cast(JsonObject, parsed)
                    events.append(event)
                    event_type = event.get("type")
                    if isinstance(event_type, str) and event_type in TERMINAL_STREAM_EVENTS:
                        break
                continue
            if text.startswith("data:"):
                buffer.append(text[5:].lstrip())

    return events


def ensure_dispute(base_url: str, creds: SmokeCredentials) -> tuple[list[JsonObject], str, bool]:
    disputes_payload = request_json(base_url, "/api/v1/disputes", token=creds.investigator_token)
    if not isinstance(disputes_payload, list):
        raise RuntimeError("Expected disputes list from API.")
    disputes = [cast(JsonObject, item) for item in disputes_payload if isinstance(item, dict)]
    if disputes:
        dispute_id = disputes[0].get("id")
        if not isinstance(dispute_id, str):
            raise RuntimeError("Expected dispute payload with an id field.")
        return disputes, dispute_id, False

    created = request_json(
        base_url,
        "/api/v1/disputes",
        method="POST",
        token=creds.reviewer_token,
        body={
            "title": "Smoke-created dispute",
            "narrative": "Automated smoke test dispute for clean environments.",
            "customer_id": "smoke-customer-001",
            "merchant_id": "smoke-merchant-001",
            "amount": 199.99,
            "currency": "USD",
            "status": "open",
            "attributes": {
                "tags": ["smoke"],
                "transaction": {
                    "velocity_24h": 1,
                    "geo_anomaly": False,
                },
            },
        },
    )
    if not isinstance(created, dict):
        raise RuntimeError("Expected created dispute payload.")
    dispute_id = created.get("id")
    if not isinstance(dispute_id, str):
        raise RuntimeError("Expected created dispute payload with an id field.")
    return [created], dispute_id, True


def wait_for_investigation_state(
    base_url: str,
    investigation_id: str,
    token: str,
    *,
    timeout_seconds: int = 90,
) -> JsonObject:
    deadline = time.time() + timeout_seconds
    last_state: JsonObject | None = None
    while time.time() < deadline:
        state = request_json(
            base_url,
            f"/api/v1/investigations/{investigation_id}",
            token=token,
        )
        if not isinstance(state, dict):
            raise RuntimeError("Expected investigation state object.")
        last_state = state
        if state.get("status") in {"awaiting_approval", "completed", "failed"}:
            return state
        time.sleep(1)
    raise RuntimeError(
        f"Investigation did not reach a terminal or approval state in time. Last status: {last_state!r}"
    )


def wait_for_stack(base_url: str) -> None:
    deadline = time.time() + 180
    last_error = ""
    while time.time() < deadline:
        try:
            request_json(base_url, "/api/v1/ready")
            return
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {details}"
            time.sleep(2)
        except (URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(2)
    raise RuntimeError(f"Stack did not become ready in time. Last error: {last_error}")


def check_telemetry_status(base_url: str, require_telemetry: bool) -> JsonObject:
    payload = request_json(base_url, "/api/v1/health/telemetry")
    if not isinstance(payload, dict):
        raise RuntimeError("Expected telemetry health payload.")
    telemetry = payload
    if not require_telemetry:
        return telemetry

    exporter_configured = telemetry.get("exporter_configured")
    probe_emitted = telemetry.get("probe_emitted")
    probe_error = telemetry.get("probe_error")
    if exporter_configured is not True:
        raise RuntimeError(
            "Telemetry exporter is not configured. Set OTEL_EXPORTER_OTLP_ENDPOINT for this environment."
        )
    if probe_emitted is not True:
        raise RuntimeError(f"Telemetry probe emission failed: {probe_error!r}")
    return telemetry


def main() -> int:
    args = parse_args()
    creds = _resolve_credentials(args)
    wait_for_stack(args.base_url)
    telemetry = check_telemetry_status(args.base_url, args.require_telemetry)
    disputes, dispute_id, created_dispute = ensure_dispute(args.base_url, creds)
    run = request_json(
        args.base_url,
        f"/api/v1/disputes/{dispute_id}/investigations",
        method="POST",
        token=creds.investigator_token,
    )
    if not isinstance(run, dict):
        raise RuntimeError("Expected investigation payload.")
    if not isinstance(run.get("id"), str):
        raise RuntimeError("Expected investigation payload with an id field.")
    investigation_id = run["id"]

    stream_events = collect_stream_events(
        args.base_url,
        investigation_id,
        creds.investigator_token,
    )
    if not stream_events:
        raise RuntimeError("Expected at least one SSE event from stream endpoint.")
    stream_event_types = [
        event_type
        for event in stream_events
        if isinstance((event_type := event.get("type")), str)
    ]
    if "run_started" not in stream_event_types:
        raise RuntimeError("Expected stream to include a run_started event.")
    if not any(event_type in TERMINAL_STREAM_EVENTS for event_type in stream_event_types):
        raise RuntimeError("Expected stream to include a terminal event.")

    refreshed = wait_for_investigation_state(
        args.base_url,
        investigation_id,
        creds.investigator_token,
    )
    if refreshed["status"] == "awaiting_approval":
        refreshed = request_json(
            args.base_url,
            f"/api/v1/investigations/{investigation_id}/resume",
            method="POST",
            token=creds.reviewer_token,
            body={"decision": "approve", "comment": "Smoke test reviewer approval."},
        )
        if not isinstance(refreshed, dict):
            raise RuntimeError("Expected resumed investigation payload.")
        refreshed = wait_for_investigation_state(
            args.base_url,
            investigation_id,
            creds.investigator_token,
        )
        resumed_stream_events = collect_stream_events(
            args.base_url,
            investigation_id,
            creds.investigator_token,
        )
        stream_events.extend(resumed_stream_events)
        stream_event_types.extend(
            event_type
            for event in resumed_stream_events
            if isinstance((event_type := event.get("type")), str)
        )
    if refreshed["status"] == "failed":
        raise RuntimeError("Investigation reached failed state during smoke validation.")

    replay_events = collect_stream_events(
        args.base_url,
        investigation_id,
        creds.investigator_token,
        timeout_seconds=20,
    )
    replay_types = [
        event_type
        for event in replay_events
        if isinstance((event_type := event.get("type")), str)
    ]
    if not any(event_type in {"approval_required", "run_completed", "run_failed"} for event_type in replay_types):
        raise RuntimeError("Expected terminal replay events from stream endpoint after run completion.")

    evidence = request_json(
        args.base_url,
        f"/api/v1/investigations/{investigation_id}/evidence",
        token=creds.investigator_token,
    )
    if not isinstance(evidence, list):
        raise RuntimeError("Expected evidence list from API.")
    audit = request_json(
        args.base_url,
        f"/api/v1/investigations/{investigation_id}/audit",
        token=creds.reviewer_token,
    )
    if not isinstance(audit, list):
        raise RuntimeError("Expected audit event list from API.")
    provider_backed = False
    for item in audit:
        if not isinstance(item, dict):
            continue
        item_obj = cast(JsonObject, item)
        event_name = item_obj.get("event_name")
        payload = item_obj.get("payload")
        if event_name in {"investigation.llm_iteration", "investigation.synthesis"} and isinstance(
            payload, dict
        ):
            if cast(JsonObject, payload).get("used_heuristic") is False:
                provider_backed = True
                break
    if args.require_provider and not provider_backed:
        raise RuntimeError("Smoke run completed, but all model steps used heuristic fallback.")
    print(
        json.dumps(
            {
                "base_url": args.base_url,
                "auth_mode": creds.auth_mode,
                "created_dispute": created_dispute,
                "dispute_count": len(disputes),
                "investigation_id": investigation_id,
                "final_status": refreshed["status"],
                "stream_event_count": len(stream_events),
                "stream_replay_event_count": len(replay_events),
                "evidence_count": len(evidence),
                "audit_count": len(audit),
                "provider_backed": provider_backed,
                "telemetry_status": telemetry,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        raise

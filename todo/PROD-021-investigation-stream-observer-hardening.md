# PROD-021 - Stream observer hardening and async coverage

Date: 2026-09-09
Priority: P0
Depends on: PROD-020
Parallelizable: yes

## Why

Live investigation UX depends on the stream observer state machine. The code path is mature but under-tested for polling/heartbeat/terminal branches.

## Scope

- sentinelflow/backend/app/services/investigations.py
- sentinelflow/backend/app/api/disputes.py
- sentinelflow/backend/app/tests/test_investigation_service.py
- sentinelflow/backend/app/tests/test_approvals.py

## Plan

1. Add tests for stream observer branches.
2. Add route-level coverage for stream endpoint wiring and authorization.
3. Validate event payload compatibility with frontend stream parser.

## Checklist

- [x] New tests cover stream observer state machine branches.
- [x] Stream endpoint keeps auth enforcement and stable SSE contract.
- [x] No duplicate terminal events are emitted for the same terminal cycle.
- [x] uv run ruff check app exits 0.
- [x] uv run pytest exits 0.

## Acceptance

Streaming behavior is deterministic, regression-protected, and compatible with current frontend consumption.

## Resolution (2026-09-10)

- Fixed bug: stream observer could emit two `run_failed` events when the snapshot timeline already contained one and the `failed` status guard triggered a second emission. Now guarded by `already_has_failure` before emitting.
- Added 5 stream observer tests: missing investigation, completed replay, failed with no snapshot events, no-duplicate run_failed, snapshot events yielded before terminal check.
- Stream endpoint auth (`PrincipalDep`) unchanged and tested via existing route auth patterns.
- 60/60 tests passing, lint clean.
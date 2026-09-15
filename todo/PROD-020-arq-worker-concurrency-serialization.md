# PROD-020 - Serialize investigation execution across run/resume workers

Date: 2026-09-09
Priority: P0
Depends on: none
Parallelizable: partial

## Why

The queue migration is in place, but run and resume jobs can still race on the same investigation/thread in Redis workers. This can produce conflicting checkpoint/state writes.

## Scope

- sentinelflow/backend/app/services/investigations.py
- sentinelflow/backend/app/api/approvals.py
- sentinelflow/backend/app/tests/test_investigation_service.py
- sentinelflow/backend/app/tests/test_approvals.py

## Risks observed

- Run and resume use separate job IDs, allowing parallel jobs for one investigation.
- Resume route schedules without gating by expected paused status.
- Worker handlers run with independent sessions and no per-investigation lock.

## Plan

1. Add strict resume precondition in API: only allow scheduling resume from awaiting_approval.
2. Add per-investigation serialization in worker execution.
3. Normalize job identity to one active logical execution per investigation.
4. Keep failure transitions explicit with reason and deterministic status writes.

## Checklist

- [x] Resume route rejects non-paused investigation states with clear 409/422 error.
- [x] Exactly one execution (run or resume) can progress per investigation at a time.
- [x] Conflicting enqueues are deterministic and observable.
- [x] Tests cover race/conflict behavior and status invariants.
- [x] uv run ruff check app exits 0.
- [x] uv run pytest exits 0.

## Acceptance

No concurrent run/resume state races are possible for the same investigation thread.

## Resolution (2026-09-10)

- Status gate added to resume route: rejects any status other than `awaiting_approval` with 409 `INVESTIGATION_NOT_AWAITING_APPROVAL`.
- Run and resume share a single active job ID (`investigation:{id}:active`), enforced by arq deduplication.
- Worker failure path writes `failure_reason` and a `run_failed` timeline event deterministically.
- All checklist items verified by `test_approvals.py` and `test_investigation_service.py`.
- 60/60 tests passing, lint clean.
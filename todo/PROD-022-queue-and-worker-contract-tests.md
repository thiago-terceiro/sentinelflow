# PROD-022 - Queue/worker contract tests for scheduling payload integrity

Date: 2026-09-09
Priority: P1
Depends on: PROD-020
Parallelizable: yes

## Why

The orchestration queue is now critical infrastructure. Scheduling payloads, job IDs, and worker wrappers need contract-level tests so drift is caught early.

## Scope

- sentinelflow/backend/app/services/investigations.py
- sentinelflow/backend/app/worker.py
- sentinelflow/backend/app/tests/test_investigation_service.py

## Plan

1. Add tests for schedule payload and job id construction.
2. Add tests for worker wrappers mapping payload to execution calls.
3. Add tests for pool lifecycle behavior (close on success/failure paths).
4. Keep assertions narrow and deterministic without external Redis dependency.

## Checklist

- [x] schedule_investigation payload and job id are covered by tests.
- [x] schedule_resume payload and job id are covered by tests.
- [x] Worker wrappers map inputs safely and preserve defaults.
- [x] Queue connection lifecycle is validated in tests.
- [x] uv run ruff check app exits 0.
- [x] uv run pytest exits 0.

## Acceptance

Queue scheduling and worker contract drift is guarded by tests in CI/local.

## Resolution (2026-09-10)

- `test_run_investigation_job_parses_payload_and_delegates`: verifies user_id, roles passed to `_run_new_investigation`.
- `test_run_investigation_job_defaults_roles_to_empty`: verifies missing `principal_roles` key defaults to `[]`.
- `test_run_resume_investigation_job_parses_payload_and_delegates`: verifies investigation_id and decision passed to `_run_resume_investigation`.
- `test_run_resume_investigation_job_defaults_decision_to_empty`: verifies missing `decision` key defaults to `{}`.
- `test_enqueue_job_closes_pool_on_success`: verifies `aclose` is called on the pool after a successful enqueue.
- `test_enqueue_job_closes_pool_on_failure`: verifies `aclose` is called even when `enqueue_job` raises.
- 60/60 tests passing, lint clean.
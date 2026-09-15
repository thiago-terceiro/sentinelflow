# Execution Plan - Production Follow-ups (2026-09-09)

Date: 2026-09-09
Owner: SentinelFlow team

## Active tickets

- PROD-020 - arq worker concurrency serialization
- PROD-021 - stream observer hardening and async coverage
- PROD-022 - queue and worker contract tests

## What changed since prior plan

- Removed obsolete migration gap concern: timeline_events and failure_reason are already covered by migrations.
- Retained open risk: concurrent run/resume execution races in worker path.
- Added async coverage lanes for stream observer and queue contracts.

## Parallel lanes

### Lane A (blocking): PROD-020

1. Add resume precondition gate in approvals API.
2. Add worker-level per-investigation serialization.
3. Add race/conflict tests.
4. Run backend validation.

Exit criteria:
- one logical executor per investigation
- deterministic conflict behavior

### Lane B: PROD-021

1. Add stream observer branch coverage.
2. Add route-level stream auth and contract tests.
3. Validate payload stability.

Exit criteria:
- deterministic stream state machine under polling and terminal transitions

### Lane C: PROD-022

1. Add scheduling payload/job-id tests.
2. Add worker wrapper tests and pool lifecycle tests.

Exit criteria:
- queue contract breakage is caught by tests

## Recommended execution order

1. Start Lane A first (blocking safety).
2. Run Lane B and Lane C in parallel after A lands or in stacked feature branches.
3. Merge with full backend validation gate.

## Validation gate per merge

- cd sentinelflow/backend && uv sync --extra dev
- cd sentinelflow/backend && uv run ruff check app
- cd sentinelflow/backend && uv run pytest

## Optional follow-up

- Add frontend reconnect banner integration tests once stream behavior is finalized.
- Add CI matrix job for smoke auth modes after queue contracts are stable.
# Implementation Plan - Open Production Gaps

Date: 2026-09-02
Owner: SentinelFlow team

## Scope of this plan

- Closed: PROD-001, PROD-014, PROD-015, PROD-016, PROD-017, PROD-018, PROD-019
- Remaining follow-up: optional UI-level tests for reconnect banners and optional CI smoke profile matrix

## Phase 1 - Keep graph production validation healthy (PROD-016)

1. Add production-compile tests in backend test suite:
   - success path with production settings and Postgres saver construction
   - failure path for missing or invalid checkpoint URL
2. Confirm readiness and error surfaces are actionable.
3. Update deployment docs with explicit checkpointer prerequisites.

Exit criteria:
- Graph compile behavior in production mode remains automated and green in CI/local.

## Phase 2 - Keep approval lifecycle coverage healthy (PROD-017)

1. Add tests covering awaiting_approval transition.
2. Add tests for resume approve and resume deny paths.
3. Add authorization and invalid-state regression tests.
4. Validate stream and replay outputs remain consistent after resume.

Exit criteria:
- Approval lifecycle has regression protection for state transitions and permissions.

## Phase 3 - Keep smoke auth/telemetry profiles explicit (PROD-018)

1. Keep explicit smoke auth modes.
2. Keep explicit parameter requirements for non-dev environments.
3. Keep command examples for local dev and cloud validation.
4. Keep telemetry operator checks available (`--require-telemetry`).

Exit criteria:
- Smoke runs are predictable and safe across environments.

## Phase 4 - Maintain demo and production deploy separation (PROD-019)

1. Keep explicit compose profile separation for demo and production-safe startup.
2. Keep production-path defaults free of development auth shortcuts.
3. Keep secure production profile requirements and examples documented.

Exit criteria:
- Production profile cannot start with insecure auth defaults.

## Validation gates per phase

- Backend: uv sync --extra dev, uv run ruff check app, uv run pytest
- Frontend (only when touched): pnpm install, pnpm build, pnpm test

## Suggested execution order

1. Keep running canonical all-surface validation for regression checks.
2. Add optional UI-level reconnect behavior tests.
3. Add optional CI matrix smoke profile checks.

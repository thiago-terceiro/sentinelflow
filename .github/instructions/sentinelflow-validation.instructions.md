---
name: SentinelFlow Validation Workflow
description: "Use when validating, testing, linting, or closing out changes in the SentinelFlow workspace. Enforces exit-code checking, retry-on-failure diagnosis, and formal PASS/BLOCKED verdicts."
---
# SentinelFlow Validation Workflow

## Hard Rules

- A non-zero exit code means the validation **failed**. Do not proceed, do not self-approve.
- Run the full command set for the touched surface — never skip the setup step.
- If a command fails, read the full error output before attempting any fix.
- Attempt a fix at most 3 times. After 3 failures on the same command, declare BLOCKED.
- Use `bash .github/scripts/validate-sentinelflow.sh` as the canonical validation command source.

## Backend Validation (required after any `.py` change)

Run this command from the workspace root; stop on first non-zero exit:

```bash
bash .github/scripts/validate-sentinelflow.sh backend
```

The backend slice includes `uv sync --extra dev`, `uv run ruff check app`, and `uv run pytest`.

## Frontend Validation (required after any `.ts`, `.tsx`, or `.css` change)

```bash
bash .github/scripts/validate-sentinelflow.sh frontend
```

The frontend slice includes `pnpm install` and `pnpm build`. Any TypeScript error is a build failure.

## Cross-Stack Changes

Run:

```bash
bash .github/scripts/validate-sentinelflow.sh all
```

Frontend build success does not prove backend API contracts are correct — you must validate both independently.

## Retry-on-Failure Protocol

1. Read the full error output.
2. Identify the specific file, line, or missing setup step that caused the failure.
3. Apply the targeted fix — do not guess.
4. Rerun the entire sequence for the affected slice from the beginning.
5. Track attempt count. At attempt 4, stop and output BLOCKED.

## Terminal Verdicts

Every validation session ends with one of:

```
VALIDATION PASS
  Backend:  pytest N passed, ruff clean, exit 0  (or "not run")
  Frontend: build succeeded, exit 0              (or "not run")
```

```
VALIDATION BLOCKED
  Failing command: [exact]
  Exit code: [code]
  Attempts: [N]
  Error: [full relevant output]
  Root cause: [evidence-based diagnosis]
  What is needed: [specific condition to unblock]
```
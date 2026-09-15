---
name: sentinelflow-validate-change
description: "Validate SentinelFlow changes before finishing work. Use when running backend tests, frontend builds, lint checks, or cross-stack closeout validation. Enforces exit-code checking, retry-on-failure diagnosis, and a formal PASS or FAIL verdict."
argument-hint: "backend, frontend, or cross-stack"
---

# SentinelFlow Validate Change

## When To Use

- Closing out a backend, frontend, or cross-stack task
- Confirming the right command order for this workspace
- Diagnosing and fixing a failed validation command

## Rules That Apply Always

- A command that exits non-zero means validation **failed**. Do not proceed past it.
- Read the full error output before attempting a fix. Guessing wastes rounds.
- If a dependency setup step is missing, fix it and rerun the entire sequence from the beginning — not from the point of failure.
- You may attempt to fix a failure up to 3 times. If the failure persists, output VALIDATION BLOCKED.

## Procedure

### Step 1 — Identify the slice

Determine which surfaces were touched: backend, frontend, or both.

### Step 2 — Backend validation (if backend was touched)

Run in this exact order. Stop and diagnose on any non-zero exit:

```bash
bash .github/scripts/validate-sentinelflow.sh backend
```

The backend slice includes `uv sync --extra dev`, `uv run ruff check app`, and `uv run pytest`.

### Step 3 — Frontend validation (if frontend was touched)

Run in this exact order:

```bash
bash .github/scripts/validate-sentinelflow.sh frontend
```

### Step 4 — Cross-stack check

If both were touched:

```bash
bash .github/scripts/validate-sentinelflow.sh all
```

Frontend build passing does not prove backend API contracts are correct.

### Step 5 — Failure diagnosis loop

If any command failed:

1. Read the full error output.
2. Identify the root cause — file, line, or missing dependency.
3. Apply the specific fix.
4. Rerun the full sequence for that slice from the beginning.
5. Repeat up to 3 total attempts.

## Terminal Output

Close this skill by reporting one of these two states:

```
VALIDATION PASS
  Backend tests:  [N passed — exit 0]   (or "not run")
  Backend lint:   [clean — exit 0]      (or "not run")
  Frontend build: [succeeded — exit 0]  (or "not run")
```

or

```
VALIDATION BLOCKED
  Slice: [backend | frontend | both]
  Attempts: [N]
  Failing command: [exact command]
  Exit code: [code]
  Error:
    [full relevant output]
  Root cause: [your diagnosis]
  What would fix this: [specific action needed]
```

Do not report success without running the commands and confirming the exit codes.
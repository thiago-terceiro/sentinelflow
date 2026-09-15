---
name: SentinelFlow Backend Rules
description: "Use when editing FastAPI, LangGraph, risk, compliance, database, tool, or schema code in SentinelFlow backend Python files."
applyTo: "sentinelflow/backend/**/*.py"
---
# SentinelFlow Backend Rules

## Layer Ownership

- HTTP routes, request parsing, and auth dependencies belong in `app/api/`.
- Pydantic request and response shapes belong in `app/schemas/`.
- LangGraph graph topology, node logic, routing conditions, and typed state belong in `app/graph/`.
- Deterministic business rules (risk scoring, compliance checks, audit logic) belong in `app/services/` or `app/tools/`. Never put testable business rules in LLM prompt strings.
- Cross-request configuration belongs in `app/config.py` or FastAPI dependencies.

## Before Editing

- Read the file you plan to edit before touching it.
- For investigation behavior, trace the full path across `app/api/`, `app/graph/`, `app/agents/`, `app/services/`, and `app/tools/` before deciding where the fix goes.
- If you add a state field, update both `app/graph/state.py` and any schema that surfaces it.

## You Are NOT Done Until

- `bash .github/scripts/validate-sentinelflow.sh backend` exits 0.
- Backend lint and tests are both clean in that run.

A change that breaks lint or tests is not complete, regardless of whether the logic looks correct.
# SentinelFlow Workspace Instructions

we are in 09/2026
use official docs only when behavior depends on external platform versions or security guidance

## Scope

- The actual application lives under `sentinelflow/`. Keep new product code inside that folder unless the task is explicitly about workspace scaffolding.
- Use these instructions as the default baseline. Let narrower files under `.github/instructions/` add backend-, frontend-, or validation-specific guidance.

## Architecture Map

- `sentinelflow/backend/app/main.py` wires the FastAPI app, routers, middleware, telemetry, and CORS.
- `sentinelflow/backend/app/api/` owns HTTP endpoints and dependency wiring.
- `sentinelflow/backend/app/graph/` owns the LangGraph workflow, state, routing, prompts, and investigation nodes.
- `sentinelflow/backend/app/agents/` contains LLM-facing investigator and synthesizer behavior.
- `sentinelflow/backend/app/services/` and `sentinelflow/backend/app/tools/` hold deterministic business logic and evidence access. Prefer these modules over burying business rules in prompts.
- `sentinelflow/frontend/app/` contains the Next.js App Router entrypoints.
- `sentinelflow/frontend/hooks/useSentinelAgent.ts` is the main client-side investigation state coordinator.
- `sentinelflow/frontend/lib/api.ts` and `sentinelflow/frontend/lib/sse.ts` own transport details. Keep fetch and SSE logic centralized there.

## Verified Commands

- Canonical validation entrypoint (single source of truth): `bash .github/scripts/validate-sentinelflow.sh [backend|frontend|all]`
- Backend bootstrap and dev dependencies: `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow/backend && uv sync --extra dev`
- Backend tests: `bash .github/scripts/validate-sentinelflow.sh backend`
- Backend lint: `bash .github/scripts/validate-sentinelflow.sh backend`
- Backend dev server: `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow/backend && uv run uvicorn app.main:app --reload --port 8000`
- Backend seed data: `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow/backend && uv run python -m app.db.seed`
- Frontend install: `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow/frontend && pnpm install`
- Frontend build: `bash .github/scripts/validate-sentinelflow.sh frontend`
- Frontend dev server: `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow/frontend && pnpm dev`
- Full stack compose: `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow && docker compose up --build`
- Important: plain `uv sync` does not install `pytest` or `ruff` because they are in the backend `dev` extra.

## Change Strategy

- Start from the file, endpoint, symbol, test, or command closest to the request and move one hop to the code that actually decides behavior.
- Keep changes in the owning layer. Do not duplicate transport logic in UI components or deterministic service rules inside LLM prompt code.
- Preserve typed boundaries. If you change backend request or response shapes, update matching frontend types and consumers in the same task.
- Prefer small edits followed by the narrowest executable validation that can falsify the change.
- Add or update tests when behavior changes or when a regression can be captured cheaply.

## Backend Expectations

- Keep FastAPI request and response shapes in `app/schemas/`.
- Keep graph state, node transitions, and routing explicit in `app/graph/`.
- Keep deterministic scoring, compliance, audit, or risk rules in `app/services/` or `app/tools/`, not hidden in free-form model prompts.
- Production graph checkpointing expects the Postgres saver import path used in `app/graph/graph.py`; do not break the in-memory development fallback.

## Frontend Expectations

- Keep API fetch helpers in `frontend/lib/api.ts` and stream wiring in `frontend/lib/sse.ts`.
- Keep long-lived client state coordination in hooks such as `useSentinelAgent` instead of spreading it across view components.
- Follow the existing Next.js 16 and React 19 patterns already present in the repo. Do not add new state or data libraries unless the task requires them.

## Definition Of Done

**You are not done until all of the following are true — not claimed, actually executed:**

- Every relevant validation command ran and exited 0:
  - Backend: `bash .github/scripts/validate-sentinelflow.sh backend`
  - Frontend: `bash .github/scripts/validate-sentinelflow.sh frontend`
- No test failures, lint violations, or TypeScript errors remain.
- If the API contract changed, both backend and frontend have been validated.
- If validation failed, you applied a diagnosis-driven fix, reran the full suite, and it now passes — or you have declared BLOCKED with the exact failing command output and root-cause evidence.

**A BLOCKED declaration with evidence is correct behavior. Declaring done without running validation is not.**
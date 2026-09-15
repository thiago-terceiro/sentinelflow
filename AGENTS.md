# Workspace Agent Notes

- The only product code in this workspace lives under `sentinelflow/`. Treat that folder as the project root for builds, tests, and file placement.
- Keep shared Copilot customization files under the workspace-root `.github/` directory so VS Code discovers them for this workspace.
- Backend work lives in `sentinelflow/backend/app/...`; frontend work lives in `sentinelflow/frontend/...`.
- Prefer changing the owning layer instead of scattering logic:
  - FastAPI routes, auth, and request wiring: `sentinelflow/backend/app/api`, `sentinelflow/backend/app/security.py`, `sentinelflow/backend/app/config.py`
  - LangGraph flow and state: `sentinelflow/backend/app/graph`
  - Deterministic business logic: `sentinelflow/backend/app/services`
  - Evidence and lookup access: `sentinelflow/backend/app/tools`
  - Frontend transport and state: `sentinelflow/frontend/lib`, `sentinelflow/frontend/hooks`
- Validated backend workflow:
  - `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow/backend`
  - `uv sync --extra dev`
  - `uv run pytest`
  - `uv run ruff check app`
- Validated frontend workflow:
  - `cd /c/Users/thiag/Documents/AI-projects/agenti-system-projects/basic-langgraph/sentinelflow/frontend`
  - `pnpm install`
  - `pnpm build`
- `uv sync` alone does not install backend test and lint tooling from the `dev` extra.

Always use arrow function for TS stuff.
Never use chain for try catch, always the full block.
ALWAYS DO SIMPLE READABLE CODE, the aim here is to have a very easy to maintain code so lets keep complexity super low.
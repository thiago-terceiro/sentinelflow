Proposed repository structure

- apps/
  - web/  # React/TypeScript UI
  - api/  # FastAPI control API/BFF

- services/
  - agent/  # LangGraph graph and Foundry host adapter
    - financial_agent/
      - agents/
      - graph/
      - models/
      - prompts/
      - providers/
      - security/
      - tools/
      - telemetry/
    - tests/
    - .foundry/
    - Containerfile

- packages/
  - contracts/  # OpenAPI/generated TS and event schemas

- policies/
  - business/  # Versioned synthetic reimbursement rules
  - opa/       # Authorization/invariant policies + tests

- evals/
  - datasets/
  - evaluators/
  - eval.yaml  # Synthetic golden, adversarial, edge cases

- infra/
  - keycloak/
  - otel/
  - foundry/  # Azure-ready templates/docs, not deployed

- docs/
  - architecture/
  - threat-model/
  - audit-model/
  - blog-walkthrough/

- tickets/  # Version-controlled implementation backlog
  - README.md  # Workflow, statuses, dependency rules
  - TICKET-NNN-short-title.md  # Scope, acceptance criteria, tests, dependencies

- compose.yaml
- azure.yaml
- .env.example
- pyproject.toml  # uv Python workspace
- uv.lock
- package.json  # pnpm root scripts
- pnpm-workspace.yaml
- pnpm-lock.yaml
- Makefile
- README.md

Ticket-driven implementation workflow

- Scaffolding creates only the workspace foundations needed to validate the backlog against real paths, commands, and package boundaries.
- The next step generates all implementation tickets in `tickets/` before feature work starts.
- Each ticket includes: scope, acceptance criteria, dependencies, tests, and completion evidence.

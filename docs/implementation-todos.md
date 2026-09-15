Implementation todos

1. Scaffold the monorepo and contracts
  - Establish a `uv` Python workspace and a `pnpm` TypeScript workspace, lockfiles, shared schemas, configuration validation, formatting/linting, root scripts, and secret-safe examples.

2. Generate the complete implementation ticket backlog
  - Create `tickets/README.md` and all implementation ticket files with stable IDs, dependencies, scope boundaries, acceptance criteria, security requirements, validation commands, and completion evidence sections.

3. Create the local identity and authorization layer
  - Add Keycloak realm/client/roles, React PKCE login, API JWT validation, permission dependencies, OPA policies, and authorization tests.

4. Build the ticket, policy, and evidence domain
  - Add PostgreSQL schema/migrations, synthetic seed data, minimized model views, evidence/policy repositories, and strict API models.

5. Implement the tamper-evident audit ledger
  - Add insert-only permissions, per-ticket sequencing/hash chaining, provenance schemas, encrypted privileged payloads, access auditing, export, and chain verification.

6. Implement model and hosting adapters
  - Add Foundry-first configuration, Ollama local adapter, deterministic fake provider, local agent host, and Foundry Hosted Agent protocol adapter.

7. Build the LangGraph multi-agent workflow
  - Implement isolated agents, structured outputs, fixed tools, bounded critic loop, deterministic gates, PostgreSQL checkpoints, interrupts, idempotency, and error paths.

8. Implement secure live event streaming
  - Persist the canonical event stream, correlate OTel spans, add role-aware projections, SSE replay/reconnect, token/reasoning deltas, cancellation, and backpressure.

9. Build the React reviewer and auditor UI
  - Add queue/detail views, live graph/timeline, state/evidence/policy panels, trace filters, human review actions, raw auditor view, clear advisory labels, and accessibility.

10. Add local Podman observability and operations
  - Compose PostgreSQL, Keycloak, OPA, Ollama, API, agent, web, OTel Collector, and Jaeger with health checks, non-root settings, secrets, persistent volumes, and one-command startup.

11. Add evaluation and security regression suites
  - Include synthetic golden tickets, prompt-injection cases, PII leakage checks, citation/groundedness checks, authorization and human-gate bypass tests, audit tampering tests, graph resilience tests, and front-end end-to-end tests.

12. Add Foundry deployment artifacts without deploying
  - Create `azure.yaml`, OCI container configuration, .foundry metadata/veal layout, environment mappings, identity/networking notes, and a validation checklist. Run only local/static validation until `azd` is installed.

13. Write the blog-oriented documentation
  - Explain architecture, threat model, trust boundaries, live trace semantics, model-provider swap, local run, screenshots/diagrams, Foundry mapping, limitations, and cleanup.

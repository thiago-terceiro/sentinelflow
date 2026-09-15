# Financial Ticket Agent: Research and Implementation Plan

## Problem and approach

Build a greenfield, blog-quality reference project for financial reimbursement/dispute ticket analysis. A team of LangGraph agents will analyze synthetic ticket evidence and policies, produce a recommendation, expose a live execution journal, and pause for a human decision. No money outcome is executable without human approval.

The project will be:

- Microsoft Foundry-first in its production-facing model and hosting abstractions.
- Fully runnable locally with Podman Compose, Keycloak, PostgreSQL, an OpenTelemetry stack, and Ollama.
- Structured so the LangGraph service can later be packaged as a Microsoft Foundry Hosted Agent.
- Security-first and audit-first: least privilege, PII minimization, deterministic policy gates, append-only provenance, and explicit human accountability.
- Honest about reasoning visibility: show every application event and every provider-emitted reasoning block available to the application, but never claim access to hidden model chain-of-thought that a provider does not emit.

## Confirmed product decisions

- Every monetary decision requires a human approval or rejection.
- Local identity uses real OIDC through Keycloak.
- Initial roles are reviewer, auditor, and admin.
- The UI should expose the maximum trace detail available. Access remains role-scoped:
  - Reviewers see the complete decision journal needed to make a decision.
  - Auditors see raw provider-visible prompts, responses, reasoning blocks, tool I/O, hashes, and trace correlation, subject to encryption and retention controls.
  - Admins manage users, prompts, policies, and model/provider configuration but cannot silently rewrite audit history.
- Microsoft Foundry is the primary target; Ollama is a replaceable local adapter, not the architectural center.
- JavaScript/TypeScript dependencies and workspaces use pnpm.
- Python dependencies, workspaces, locking, and command execution use uv.
- After the initial workspace scaffold, generate the complete implementation backlog as version-controlled files under tickets/.
- Implementation then proceeds ticket-by-ticket, delegating independent tickets to subagents wherever their scopes do not overlap.
- The project uses only synthetic/demo financial data and clearly states that it is decision support, not legal, regulatory, or financial advice.

## Research findings driving the design

### LangGraph

- Use LangGraph 1x StateGraph with named nodes and isolated subgraphs. Explicit graph transitions are easier to inspect and audit than a free-form supervisor loop.
- Use Pydantic models for LLM and tool boundaries, and typed graph state for orchestration.
- Use `interrupt()` and durable checkpoints for human review. Nodes must be idempotent because code before an interrupt can run again on resume.
- Use Postgres checkpointers in the integrated runtime and strict checkpoint deserialization (`LANGGRAPH_STRICT_MSGPACK=true`).
- Use current event streaming APIs and explicit output projections. Private state is not assumed to be private merely because it is an internal graph field.
- Treat streamed model text as advisory. Validated graph state, deterministic policy results, evidence citations, and human actions are the authoritative decision record.

## Primary sources

- https://docs.langchain.com/oss/python/langgraph/overview
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/event-streaming
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/use-subgraphs


Microsoft Foundry

- A custom LangGraph application maps to a Microsoft Foundry Hosted Agent rather than a prompt-only agent.
- Hosted Agent versions are immutable container/configuration snapshots and have platform-managed endpoints, identities, and OpenTelemetry integration.
- The Foundry deployment adapter should use the official agent-server protocol libraries and OpenTelemetry integration, while local transport stays behind an application interface.
- azure.yaml, an OCI Containerfile, environment contracts, and a deployment-readiness guide can be included without provisioning Azure.
- Actual deployment, guardrails, connected Application Insights, ACR, private networking, and Entra agent identity validation remain documented but unexecuted.
- Avoid Microsoft Foundry Workflows because current documentation says that preview feature is being retired on December 1, 2026; LangGraph remains the orchestrator.
- The current machine is missing `azd`. Before validating Foundry manifests, install Azure Developer CLI 1.27.1 or later and the `microsoft.foundry` extension. Planning will not install it.

Primary sources:

- https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents
- https://learn.microsoft.com/azure/foundry/how-to/develop/langchain-agents
- https://learn.microsoft.com/azure/foundry/observability/quickstarts/quickstart-tracing-hosted-agent
- https://learn.microsoft.com/azure/foundry/agents/how-to/author-azure-yaml
- https://learn.microsoft.com/azure/foundry/agents/concepts/agent-identity
- https://learn.microsoft.com/azure/foundry/how-to/configure-private-link
- https://learn.microsoft.com/azure/foundry/guardrails/guardrails-overview
- https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/langgraph

Security and audit

- Threat model against OWASP GenAI/LLM and agentic application risks, especially prompt injection, insecure output handling, excessive agency, memory poisoning, orchestrator hijacking, over-permissioned tools, insufficient audit trails, and human override failure.
- Free-form ticket text, OCR, policy text, and tool results are untrusted data; never instructions.
- LLMs recommend deterministic code and policy-as-code to enforce invariants.
- Telemetry and audit serve different purposes:
  - OpenTelemetry contains redacted operational metadata, latency, token counts, errors, and correlation IDs.
  - The audit ledger contains encrypted, access-controlled decision provenance and optional raw provider-visible content.
- Human decisions require an authenticated identity, reason, timestamp, version/conflict check, and policy authorization.

Primary sources:

- https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
- https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- https://airc.nist.gov/
- https://opentelemetry.io/docs/specs/semconv/gen-ai/
- https://www.openpolicyagent.org/docs/
- https://presidio.dataprivacystack.org/

Target architecture

Services

1. React web application
   - TypeScript, Vite, React Router, TanStack Query, React Flow, accessible component primitives.
   - OIDC Authorization Code + PKCE against Keycloak.
   - Ticket queue, ticket submission, live graph view, timeline, evidence/policy panels, review form, and auditor trace explorer.

2. FastAPI control API/BFF
   - Validates Keycloak JWTs using discovery/JWKS and enforces permission-level authorization.



3. LangGraph agent service

- Framework-neutral entry point wrapped by local and Foundry hosting adapters.
- Uses a shared event contract so local SSE and Foundry invocation streams render identically.
- Uses PostgreSQL checkpoint persistence and idempotency keys.

4. PostgreSQL

- Ticket/evidence/policy data.
- LangGraph checkpoints.
- Append-only audit events with per-ticket sequence, previous hash, current hash, actor, prompt/model/tool versions, evidence/policy references, and trace IDs.
- Separate migration, application, and auditor database roles. Application roles cannot update/delete audit events.

5. Keycloak

- Local realm/client setup imported from version-controlled, secret-free configuration.
- Reviewer, auditor, and admin roles with seeded demo users whose passwords are injected through local secrets.

6. OPA

- Deterministic, versioned policy enforcement for review permissions and graph invariants.
- All final outcomes require a human actor; no graph path can bypass this rule.

7. OpenTelemetry Collector + Jaeger

- Local trace pipeline compatible with Azure Monitor/Application Insights export later.
- Redacted GenAI semantic-convention spans; raw prompts and PII are excluded by default.

8. Ollama local profile

- OpenAI-compatible local endpoint selected through configuration.
- Kept outside domain code through a ModelGateway interface.
- Foundry remains the default non-local provider. A scripted fake provider makes tests deterministic.

Agent graph

The graph uses explicit nodes/subgraphs instead of agents dynamically spawning arbitrary agents:

1. `intake_guard`
- Validate schema, normalize text, assign opaque identifiers, identify/redact PII, and flag likely prompt injection.
- This is deterministic security code, not an LLM decision.

2. `evidence_analyst`
- Compare ticket statements with synthetic transactions and submitted evidence.
- Return structured findings, contradictions, missing facts, confidence, and evidence IDs.

3. `policy_analyst`
- Retrieve only versioned policy records through a read-only tool.
- Return applicable rule IDs, applicability rationale, and missing-policy flags.

4. `risk_analyst`
- Assess fraud/manipulation and operational risk from minimized structured inputs.
- Has no write tools and cannot see unneeded identity data.

5. `decision_synthesizer`
- Combine validated outputs into `approve_reimbursement`, `deny_reimbursement`, `request_more_information`, or `escalate`.
- Produce confidence, concise rationale, supporting and opposing factors, evidence citations, and policy citations.

6. `independent_critic`
- Try to falsify the recommendation, identify unsupported claims, citation gaps, and policy conflicts.
- May route once back to the synthesizer with bounded iteration.

7. `deterministic_gate`
- Validate schemas, citation existence, loop/token budgets, and OPA invariants.
- Always routes monetary outcomes to human review.

8. `human_review`
- LangGraph interrupt with optimistic concurrency/versioning.
- Reviewer can approve, reject, request information, or escalate, and must enter a reason.

9. `finalize`
- Persist the human outcome and append final provenance.
- The demo performs no real payment/refund side effect.

Live event and reasoning contract

Every event has an event ID, ticket/thread/run IDs, timestamp, sequence, node/agent identity, visibility classification, payload schema version, and OTel trace/span IDs.

Event types include:

- Run, node, LLM, and tool start/finish/error.
- Token deltas and provider-emitted reasoning deltas when available.
- Prompt template ID/version and privileged raw prompt snapshot.
- Structured state deltas after validation.
- Tool name/version, validated arguments, result summary, duration, and error.
- Evidence and policy citations.
- Guardrail, PII, injection, budget, and OPA policy results.
- Checkpoint and interrupt lifecycle.
- Human view, decision, reason, and override.
- Model/provider/deployment identifiers and token usage.

Rules:

- The UI labels raw model text and provider reasoning as non-authoritative.
- The application does not invent or reconstruct hidden chain-of-thought.
- Reviewer streams are minimized and redacted.
- Auditor raw views are role-gated, encrypted at rest, access-audited, and clearly separated from operational telemetry.
- SSE supports `Last-Event-ID`, replay from durable events, reconnects, heartbeats, cancellation, and backpressure.
- No direct browser access to PostgreSQL, Jaeger, Ollama, OPA, or the agent service.

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

Data and audit model

- Use synthetic tickets with opaque customer/evidence identifiers.
- Never send card PAN, CVV, account numbers, passwords, OIDC tokens, or secrets to a model.
- Store raw evidence separately from model-ready, minimized evidence.
- Record exact model/deployment, prompt hash/version, graph version, tool versions, policy bundle hash, input/output hashes, citations, token usage, trace IDs, and human actor.
- Build a per-ticket hash chain transactionally. A verifier endpoint/job reports integrity failures; it never silently repairs them.
- Append corrections and redactions as new events instead of rewriting prior events.
- Define explicit retention classes. Operational traces are short-lived; privileged raw provider content has a separate configurable retention period and can be disabled.
- Use Podman secrets locally and Azure Key Vault/managed identity in the future cloud profile.

Security controls

- OIDC discovery/JWKS validation with issuer, audience, expiry, and algorithm checks.
- Permission checks in the API and OPA; UI role checks are presentational only.
- CSRF-safe OIDC flow, strict CORS, CSP/security headers, request/body limits, rate limits, and no credentials in URLs.
- Pydantic validation at every HTTP, event, LLM, and tool boundary.
- Fixed tool registry per agent; read-only tools for analysis agents; no dynamic code execution, shell, arbitrary HTTP, or dynamic MCP discovery.
- Prompt/data separation, untrusted-content labels, injection detection, and refusal to follow instructions found in evidence.
- Bounded graph iterations, per-node timeouts, token budgets, retry policies only for safe/idempotent work, and a kill switch.
- Non-root, minimal OCI images; read-only filesystems and dropped capabilities where compatible.
- Locked Python and npm dependencies, generated SBOMs, vulnerability/license checks, and secret scanning in CI.
- Logs and OTel spans are structured and redacted before export.
- Security decisions fail closed and surface explicit, audited errors.


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


Important considerations

- "All reasoning" means all data actually emitted to and observable by application code. Some providers intentionally do not expose private chain-of-thought; the application must not promise, infer, or fabricate it.
- Raw prompts, responses, and provider-visible reasoning may contain sensitive data. Maximum visibility therefore belongs in an explicitly privileged, audited view rather than general operational telemetry.
- Ollama is the simplest local runtime because it offers an OpenAI-compatible API with minimal infrastructure. vLLM and llama.cpp add deployment or hardware complexity without strengthening the Foundry story. Foundry Local can be documented as an optional future local provider, but it should not block the reproducible Podman path.
- The multi-agent design is intentionally bounded. More agents do not automatically improve quality; each agent must have a distinct responsibility, schema, tool set, and evaluation.
- PostgreSQL is the durable source for workflow and audit state. Redis is omitted initially unless load testing proves a need for cross-instance fan-out or queues; unnecessary state stores increase audit and security complexity.
- No real payment API, customer system, or external web-browsing tool is included.
- The project should avoid implying regulatory compliance. It demonstrates controls and evidence suitable for further review.

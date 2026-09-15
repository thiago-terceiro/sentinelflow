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

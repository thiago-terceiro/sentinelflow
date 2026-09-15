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

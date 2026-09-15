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



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

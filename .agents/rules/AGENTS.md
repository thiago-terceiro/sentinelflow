# SentinelFlow Antigravity Agent Rules

## Security Mandates
- **Zero Raw PII Exposure**: Never emit or store unredacted credit card PANs, SSNs, IBANs, phone numbers, emails, or API keys in audit logs or LLM prompts. Always route through `app.services.trace_safety`.
- **Append-Only SHA-256 Ledger**: Never rewrite or mutate historical audit rows. All corrections must be append-only notes via `POST /audit/notes`.
- **RBAC & Dev-Token Lockout**: Never allow dev tokens in production mode (`AUTH_ALLOW_DEV_TOKENS=False`). Always check principal roles via `require_any()`.
- **Mandatory Human Approval**: Any dispute flagged as high-risk must trigger LangGraph `interrupt()`. Never bypass approval routing.
- **Supply-Chain & AST Cleanliness**: Code changes must pass `ruff check --select S`, `bandit`, `pip-audit`, `eslint` with SonarJS, and `pnpm audit`.

## Performance Mandates
- **Sub-15ms Ingress SLA**: SentinelPulse synchronous traffic inspection must execute within 15ms end-to-end.
- **ONNX CPU Inferences**: Keep ONNX CPU execution under 0.1ms; never introduce GPU-dependent models to the synchronous telecom path.
- **Redis Pipelining**: Always use pipelined Redis transactions for sliding-window velocity counter queries (10s, 60s, 1h ZSETs) to avoid multi-RTT overhead.
- **Async Concurrency & Session Locks**: Run evidence gathering tools concurrently via `asyncio.gather`. Serialize database writes using per-investigation `asyncio.Lock` to prevent deadlocks and hash-tree branching.
- **Frontend State Derivation**: Maintain the 100-step derivation benchmark (<2.8ms total, <0.03ms per step) in `deriveConsoleStateAtStep`.
- **Backpressure-Safe SSE**: Keep SSE queues bounded (`maxsize=100`) to prevent memory leaks from slow consumers.

## Architecture & Code Quality
- **Arrow Functions**: Always use arrow functions for TypeScript/JavaScript code (`const fn = () => ...`).
- **Full try/catch Blocks**: Never use promise chains (`.then() / .catch()`); always use full `try { ... } catch (err) { ... }` blocks.
- **Readability Over Complexity**: Keep code minimal, direct, and easy to maintain.

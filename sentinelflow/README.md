# SentinelFlow

SentinelFlow is a production-style dispute investigation copilot built around an LLM investigator, typed tool outputs, deterministic risk and compliance services, and native LangGraph human approval pauses.

The local stack is now wired to run as a production-like image-based deployment with PostgreSQL, FastAPI, Next.js, and an nginx reverse proxy.

## Architectural Principle: 100% Free & Open-Source Stack

> [!NOTE]
> **Zero-Cost Infrastructure Constraint:** SentinelFlow is deliberately designed and engineered under a strict constraint of using **100% free, open-source, and locally runnable resources**.
>
> All security scans, static analysis, type checking, test suites, evaluation harnesses, and CI/CD pipelines run without paid SaaS subscriptions, external token fees, or closed vendor lock-in:
> - **Zero-SaaS Security**: Gitleaks secret scanning and AST-level rule enforcement instead of commercial SAST/secret-scanning SaaS.
> - **Zero-Cost Static Analysis**: Official SonarSource rule engine (`eslint-plugin-sonarjs`), Ruff, and Mypy instead of paid SonarQube Server / Snyk enterprise tiers.
> - **Self-Contained AI Observability**: Cryptographic SHA-256 audit ledgers, PII scrubbing, and local AI evaluation suites instead of paid LangSmith / Braintrust / Arize seats.
> - **Deterministic CI**: Free GitHub Actions runners and local bash validation scripts with zero external billing dependencies.

## What is included

- FastAPI backend with authenticated investigation endpoints
- Typed LangGraph state and native `interrupt()` approval node
- Tool layer that reads seeded dispute evidence from PostgreSQL
- Deterministic risk engine and versioned compliance checks
- Next.js 16 App Router console with SSE replay support, **Time-Travel State Scrubber (`?step=`)**, **Semantic Iteration Diff Inspector (`?diff=1`)**, and **Cross-Panel Evidence Citation Pinning (`?evidence=`)**
- Seed data for five dispute cases with visibly different investigation profiles, including **pre-seeded showcase investigations**:
  - `SF-10001` (`inv_seed_sf_10001`): Completed 2-iteration human-steered investigation with full timeline events, iteration diffs, and SHA-256 cryptographic audit ledger ready on boot
  - `SF-10002` (`inv_seed_sf_10002`): Paused `awaiting_approval` investigation ready for immediate human-in-the-loop review (`Approve`, `Reject`, or `Request Revision`)
- Multi-stage Docker images for backend and frontend
- Durable queue execution path with Redis + arq worker
- Optional encrypted raw audit artifact vault for auditor/admin review flows
- nginx reverse proxy with request size limits, rate limiting, and SSE-safe buffering config
- Compose health checks and dependency conditions for startup ordering
- Local smoke test harness for end-to-end validation

## Repository layout

- `OVERVIEW.md`: Comprehensive 7-stage CI/CD pipeline, automated verification gates, and architectural FAQ
- `backend/`: FastAPI, LangGraph, DB models, seeded tools, tests
- `frontend/`: Next.js 16 App Router console in strict TypeScript
- `.env.example`: local development configuration
- `docker-compose.yml`: local full-stack startup
- `ops/nginx/default.conf`: reverse proxy configuration
- `ops/smoke_test.py`: local stack smoke test

## Demo vs production configuration

- Demo path: use `docker compose up -d --build` with `.env.example` defaults.
- Production-safe profile path: use `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d --build` with explicit environment values.
- Production/test-deploy path: configure OIDC issuer/discovery, client credentials, backend audience/issuer validation, provider credentials, and OTLP endpoint.
- Frontend browser calls use the Next.js `app-api` proxy path; the proxy forwards caller identity from `Authorization` header or the HttpOnly `sentinelflow_access_token` cookie.
- OIDC login/logout routes live at `/auth/login`, `/auth/callback`, and `/auth/logout`.
- Investigation orchestration jobs are queued through `QUEUE_REDIS_URL` and executed by the `worker` service.
- Encrypted raw audit artifacts require `AUDIT_ARTIFACT_ENCRYPTION_KEY` (Fernet key); without it, audit rows keep redacted traces and mark raw artifact storage as unavailable.

## Local development

### Backend

```bash
cd backend
uv sync --locked --extra dev
uv run alembic upgrade head
uv run python -m app.db.seed
uv run uvicorn app.main:app --reload --port 8000
```

> **Dependency Reproducibility & Lockfile Enforcement:** Converter-sensitive ML and numerical dependencies (`scikit-learn==1.9.1`, `skl2onnx==1.20.0`, `onnx==1.23.2`, `onnxruntime==1.31.0`, `numpy>=2.5.4,<2.6.0`, `scipy>=1.18.1,<1.19.0`) are pinned in `backend/pyproject.toml` and locked in `backend/uv.lock`. Both CI (`uv sync --locked --extra dev`) and Docker builds (`uv sync --locked --no-dev`) enforce lockfile consistency.

Fallback development bearer tokens (backend-only, enable with `AUTH_ALLOW_DEV_TOKENS=true`):

- `dev-investigator`
- `dev-reviewer`
- `dev-admin`

### OIDC quickstart (local Keycloak)

1. Start a local Keycloak and create a realm/client with Authorization Code enabled and PKCE S256 required.
1. Configure redirect URIs to include `http://localhost:3000/auth/callback` (and your proxy host if needed).
1. Set these variables in `.env`:

```bash
AUTH_OIDC_ISSUER=http://localhost:8080/realms/sentinelflow
AUTH_OIDC_CLIENT_ID=sentinelflow-web
AUTH_OIDC_CLIENT_SECRET=replace-if-confidential-client
AUTH_ISSUER=http://localhost:8080/realms/sentinelflow
AUTH_AUDIENCE=account
AUTH_ALLOW_DEV_TOKENS=false
```

1. Optionally set claim mapping for provider-specific role names:

```bash
AUTH_ROLE_MAP={"sentinelflow.reviewer":"reviewer","sentinelflow.auditor":"auditor"}
AUTH_RESOURCE_CLIENT_ID=sentinelflow-api
```

Backend role extraction supports `roles`, `groups`, Keycloak `realm_access.roles`, and `resource_access[AUTH_RESOURCE_CLIENT_ID].roles`.

### OIDC quickstart (Microsoft Entra ID)

1. Register an app in Entra ID and enable Authorization Code flow.
1. Add redirect URI(s):
	 - local: `http://localhost:3000/auth/callback`
	 - proxy: `https://<your-domain>/auth/callback`
1. Configure API/client settings:

```bash
AUTH_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
AUTH_OIDC_DISCOVERY_URL=https://login.microsoftonline.com/<tenant-id>/v2.0/.well-known/openid-configuration
AUTH_OIDC_CLIENT_ID=<application-client-id>
AUTH_OIDC_CLIENT_SECRET=<client-secret-if-confidential-client>
AUTH_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0
AUTH_AUDIENCE=<application-client-id-or-configured-audience>
AUTH_ALLOW_DEV_TOKENS=false
```

1. Map Entra groups/roles to SentinelFlow roles via `AUTH_ROLE_MAP`, for example:

```bash
AUTH_ROLE_MAP={"FraudReviewers":"reviewer","FraudAuditors":"auditor"}
```

### HTTPS/proxy cookie behavior

- Session cookies are `HttpOnly` and `SameSite=Lax`.
- In production, cookie `Secure` is always enabled.
- Outside production, `Secure` is enabled when `x-forwarded-proto=https`.
- Reverse proxies must forward:
	- `Host` or `x-forwarded-host`
	- `x-forwarded-proto`
- These headers are used to build callback and logout redirect URLs. If they are wrong, OIDC callback origin checks can fail.

### AWS ALB + CloudFront forwarding for BFF auth

- CloudFront behavior for `/auth/*` and `/app-api/*` should forward all cookies and `Authorization` header.
- Do not cache `/auth/*` or `/app-api/*` responses.
- Forward `Host` and `x-forwarded-proto` through CloudFront -> ALB -> app.
- Terminate TLS at CloudFront or ALB and preserve forwarded proto as `https`.
- Keep callback URI in Entra/Keycloak exactly aligned with the public CloudFront domain.

Minimal CloudFront policy requirements:

- Cache policy: disable caching for `/auth/*` and `/app-api/*`.
- Origin request policy: include `Authorization`, `Host`, and all cookies.
- Viewer protocol policy: redirect HTTP to HTTPS.

### OIDC operations checklist (rotation, audience, invalidation)

- Key rotation:
	- Rotate IdP signing keys or client secrets.
	- Validate fresh JWKS discovery and token verification in `/api/v1/ready`.
	- Run smoke test with bearer mode after rotation.
- Audience/issuer changes:
	- Update `AUTH_AUDIENCE`, `AUTH_ISSUER`, and/or OIDC discovery settings.
	- Confirm login callback success and protected API access.
- Session invalidation:
	- Invalidate IdP sessions for incident response.
	- Force users through `/auth/logout` then `/auth/login`.
- Rollback path:
	- Revert to last-known-good IdP metadata/client settings.
	- Re-run: `bash .github/scripts/validate-sentinelflow.sh all`.
	- Re-run smoke: `python ops/smoke_test.py --auth-mode bearer_tokens --investigator-token "$INVESTIGATOR_TOKEN" --reviewer-token "$REVIEWER_TOKEN"`.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

### Local production-like Docker stack

```bash
docker compose up -d --build
python ops/smoke_test.py --auth-mode dev_tokens
```

Production-safe profile startup (requires explicit secrets and IdP configuration):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d --build
```

Smoke test options:

```bash
python ops/smoke_test.py --auth-mode dev_tokens --base-url http://127.0.0.1:8080
python ops/smoke_test.py --auth-mode bearer_tokens --base-url https://sentinelflow.example.com --investigator-token "$INVESTIGATOR_TOKEN" --reviewer-token "$REVIEWER_TOKEN"
python ops/smoke_test.py --auth-mode bearer_tokens --require-provider --investigator-token "$INVESTIGATOR_TOKEN" --reviewer-token "$REVIEWER_TOKEN"
python ops/smoke_test.py --auth-mode bearer_tokens --require-provider --require-telemetry --investigator-token "$INVESTIGATOR_TOKEN" --reviewer-token "$REVIEWER_TOKEN"
```

Or set environment variables:

```bash
SMOKE_AUTH_MODE=bearer_tokens
SMOKE_BASE_URL=http://127.0.0.1:8080
SMOKE_INVESTIGATOR_TOKEN=replace-with-investigator-token
SMOKE_REVIEWER_TOKEN=replace-with-reviewer-token
SMOKE_REQUIRE_PROVIDER=true
SMOKE_REQUIRE_TELEMETRY=true
python ops/smoke_test.py
```

Default dev tokens are only auto-filled when `SMOKE_AUTH_MODE=dev_tokens` and the base URL host is local (`localhost` or `127.0.0.1`).

The stack is exposed at `http://localhost:8080` through nginx. API traffic is routed through `/api/v1`, and the smoke test validates `/ready`, creates a dispute when the database is clean, verifies SSE stream and terminal replay events, and checks evidence and audit retrieval.

Telemetry operator check endpoint: `/api/v1/health/telemetry`. Use `--require-telemetry` (or `SMOKE_REQUIRE_TELEMETRY=true`) in environments where exporter configuration and probe emission are mandatory.

To observe queued execution workers:

```bash
docker compose logs -f worker
```

## Database migrations

Run backend schema changes through Alembic before seeding data.

```bash
cd backend
uv run alembic upgrade head
```

Create a new revision after SQLAlchemy model changes:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe_change"
```

Rollback one migration revision:

```bash
cd backend
uv run alembic downgrade -1
```

### Why this matches current best practice

- Docker Compose startup order uses service health checks and `service_completed_successfully` for the seed/init job.
- FastAPI runs as a single process per container with exec-form `CMD` and `--proxy-headers`.
- Next.js is built as a standalone output and served behind a reverse proxy.
- Streaming-safe proxy headers and disabled buffering are configured for investigation SSE paths.

## Notes

- **No Demonstrated Production Deployment:** All verification in this repository reflects local development, local multi-worker benchmarks (`SF-020`), and clean-checkout stack tests (`SF-021`). Production Redis deployment, cloud autoscaling, and internet-scale traffic remain unvalidated.
- **Redis Deployment Scope:** Standalone Redis (`redis:7-alpine`) is the validated architecture; Redis Cluster remains future scope (only sender keys share a `{sender_hash}` tag, while IP/domain/prefix keys use distinct tags and would route to separate hash slots).
- **HMAC Key Rotation:** Telecom identifier pseudonymization (`TELECOM_HMAC_KEY_ID` + `TELECOM_HMAC_SECRET`) requires coordinated operational key/key-ID rotation; automatic rotation and cross-version mismatch detection are not implemented.
- Production mode requires real JWT configuration and an OpenAI API key.
- The backend still uses an in-memory LangGraph checkpointer outside production; production mode validates PostgreSQL checkpointer requirements at startup and readiness.
- The SSE endpoint (`GET /api/v1/investigations/{id}/stream`) replays persisted snapshot events and streams live intra-node push events (`tool_started`, `evidence_added`, `reasoning_delta`, `approval_required`, etc.) over Redis Pub/Sub via `InvestigationBroadcaster`.
- The built-in backend rate limiter is in-memory. For horizontally scaled production, move rate limiting to shared infrastructure or a distributed backing store.

---

# SentinelPulse: Real-Time SMS Fraud & Spam Intelligence Gateway

> **Tailored for Global CPaaS Traffic Intelligence & Communications ML Teams**  
> Architectural Target: Synchronous inline ingress (`<15ms p95 end-to-end HTTP` target, `<0.1ms` warm in-graph ONNX C++ execution on short SMS) · Non-Transactional Redis Velocity Pipelining · MLOps Drift Monitoring (KS + PSI) · `SF-020` Multi-Worker Topology Suite *(Measured Local Status: ONNX `session.run()` runs at `0.064ms p50 / 0.170ms p95`; under `SF-020` real standalone `redis:7-alpine` + `W=4` Uvicorn workers, Boundary B HTTP `p95` meets `<15ms` through `C=8` [`4.782–9.638 ms`, `672.56 RPS` sustained], whereas worker cold starts [`29.8–58.5 ms`] and `C=16` CPU oversubscription [`21.754 ms p95`] exceed 15 ms — so a universal `<15ms` HTTP guarantee is NOT claimed)*

SentinelPulse is an ultra-low-latency telecom intelligence gateway integrated into SentinelFlow. It protects messaging networks from high-volume SMS pumping, account takeover smishing, and SIM farm abuse.

### System Performance Benchmarks (Historical Short-SMS vs. `SF-015` 2,000-Char Local Measurements)

| Benchmark Metric | Target SLA | Measured Performance | Architecture Layer |
| :--- | :--- | :--- | :--- |
| **Raw ONNX CPU Inference (p50)** | $< 1.0\text{ ms}$ | **0.022 ms** (22 µs, *historical short-SMS `session.run()` only*) | ONNX Runtime AVX-512 (In-graph TF-IDF + Sigmoid-Calibrated Linear Classifier) |
| **Raw ONNX CPU Inference (p95)** | $< 5.0\text{ ms}$ | **0.032 ms** (32 µs, *historical short-SMS `session.run()` only*) | ONNX Runtime AVX-512 (In-graph TF-IDF + Sigmoid-Calibrated Linear Classifier) |
| **Raw ONNX CPU Inference (p99)** | $< 10.0\text{ ms}$ | **0.086 ms** (86 µs, *historical short-SMS `session.run()` only*) | ONNX Runtime AVX-512 (In-graph TF-IDF + Sigmoid-Calibrated Linear Classifier) |
| **Compiled Regex Heuristics (`evaluate_heuristics()`)** | $< 0.5\text{ ms}$ *(short)* / $< 15\text{ ms}$ (`AI-18` `2k` ReDoS guard) | **0.040 ms** *(short-SMS)* / **p95 $\le$ 3.477 ms** (`SF-015` 2,000-char ReDoS guard) | Fast-path Python regex (Single: 0.20–0.40, Compound: $\ge 0.85$) |
| **Redis Sliding Window Pipeline** | $< 5.0\text{ ms}$ | **0.50–2.54 ms warmed RTT** (`SF-020` real Docker `redis:7-alpine`, `socket_timeout=0.050s`, `socket_connect_timeout=0.100s`) | Async non-transactional `ZSET` pipeline (1 roundtrip) |
| **Internal Gateway Processing (`latency_ms`, Boundary A)** | **$< 15.0\text{ ms}$** | **0.400 ms** *(historical ~73-char)* / **1.937–3.725 ms p95 (`e12734d`), 5.488–8.815 ms p95 (`cb64ff2`)** (`SF-015` 2,000-char) | `_process_single_message()` internal timer (in-process fake-Redis / in-memory) |
| **Caller HTTP Round-Trip (`loopback_http_ms`, Boundary B)** | **$< 15.0\text{ ms}$ p95 (Target)** | **NOT ESTABLISHED** (`e12734d` `conc=1`: `6.228–7.633 ms`, `cb64ff2` `conc=1`: `17.259–17.793 ms`; shared-loop `e12734d` `conc=4`: `25.280–26.094 ms`, `conc=8`: `54.984–63.106 ms`) | Full HTTP/FastAPI middleware + Pydantic + `JsonFormatter` audit log + loopback TCP |
| **Throughput Capacity** | $> 1,000\text{ RPS}$ | **672.56 RPS sustained** (`SF-020` `W=4` workers, `C=8` client processes, real `redis:7-alpine`, `0` errors); cloud `>1,000 RPS` remains unverified | Per container instance |

> **Measurement Boundary Note:** `<15ms` ReDoS verification concerns `evaluate_heuristics()`, internal `_process_single_message()` (`latency_ms`) is Boundary A, and caller-observed HTTP round-trip is Boundary B. Under `SF-020` real standalone `redis:7-alpine` + `W=4` independent workers, Boundary B `p95` meets `<15ms` through `C=8` (`4.782–9.638 ms`) after fixing Windows `15ms` connect-timeout aliasing (`velocity_store.py`), but exceeds `15ms` during cold starts (`29.8–58.5 ms`) and `C=16` oversubscription (`21.754 ms`).

### System Capability & Readiness Matrix

| Readiness Tier | Components & Capabilities |
| :--- | :--- |
| **Implemented & Verified in Repo** | `<1ms` ONNX CPU inference (`sms_fraud_model.onnx`, frozen `SF-018` `824c6c2c...` retained under `SF-019` no-change decision, single-thread pinned `SessionOptions`); patched `skl2onnx` `<1e-6` parity (`max_prob_abs_diff = 1.15e-07`, `400/400` verdict parity); continuous gated composite scoring (monotonic non-decreasing, 13 linear-time regex heuristics with `<15ms` `evaluate_heuristics()` ReDoS guard + Cyrillic mixed-script homoglyph normalization); standalone Redis (`redis:7-alpine`) ZSET sliding-window velocity + 30s in-memory deque fail-open circuit breaker (standalone `redis:7-alpine` validated locally in `SF-020`/`SF-021`; production cloud Redis remains unvalidated); pre-inference/logging PII redaction (`redact_sms_pii`, 2,000-char contract) and 128-bit versioned HMAC pseudonymization (**HMAC secret and `TELECOM_HMAC_KEY_ID` rotation require coordinated operational handling—no automatic rotation or mismatch detection is implemented**); 3-tier evaluation governance (`SF-018`/`SF-019` `Train OOF CV N=703` across 56 families; `Dev/Val N=400` previously inspected/tuned, **not** an untouched independent holdout; `Class C External Holdout: UNAVAILABLE / BLOCKED` with `UCI #228` `N=5,574` quarantined separately; `Class D: 0 records`—results do not establish production generalization or real-world fraud effectiveness); LangGraph multi-agent triage workbench (`interrupt()`), `arq` worker, SHA-256 append-only audit ledger, Next.js 16 console (`39` tracked frontend unit tests in clean checkout vs. `45` locally including 6 local-only Learning Hub tests; `test-a11y-aaa.mjs` automated checks reported `0` violations strictly on the tested routes/states at Desktop `1440×900` and Mobile `375×812` in `light` and `dark` modes under the script's configured rules—not a full-app WCAG AAA certification or manual audit). |
| **Simulated / Benchmarked in Dev** | In-process `httpx.ASGITransport` microbenchmarks & local loopback Uvicorn 2,000-char benchmarks (`scripts/benchmark_pulse.py`, `scripts/bench_telecom_classify_2000.py`): `evaluate_heuristics()` `<15ms` ReDoS guard and Boundary A internal `_process_single_message()` (`latency_ms`) pass `<15ms` locally, whereas Boundary B caller-observed HTTP `<15ms` target is **NOT ESTABLISHED**; **`SF-020` validated real standalone `redis:7-alpine` + `W=4` Uvicorn workers (`666.01 RPS`, `11.235ms p95` at `C=8`), while `C=16` oversubscription (`34.265ms p95`) exceeds 15 ms**; synthetic + public-advisory SMS corpora (`Train N=703`, `Dev/Val N=400`, `SF-013` perturbation suite `N=70`); Locust & `telecom_simulator.py` traffic generation; heuristic fallback / mock LLM mode in dev & CI (`app.evals.run`). |
| **Future Production / Enterprise Scope (Not Implemented)** | **No demonstrated production deployment** exists in this repository; production-scale load and independent multi-worker behavior have **not** been established; live carrier SS7 / Diameter / SMPP / optical-tap ingestion (`Class D` telemetry: `0` records in repo); multi-node **Redis Cluster** state synchronization (only `{sender_hash}` slot tags are prepared; IP/domain/prefix keys use distinct tags and route to separate slots) & distributed Kafka event bus (`telecom.sms.inbound`); automated closed-loop active-learning retraining pipelines (retraining is manual/offline via `train_onnx_model.py`). |

### Core Gateway Endpoints

- `POST /v1/classify` (or `/api/v1/telecom/classify`): Synchronous inline ingress (architectural target `<15ms p95 end-to-end HTTP`, `<0.1ms` warm ONNX execution on short SMS; Boundary A internal `latency_ms` passes `<15ms` at 2,000 chars locally while the **end-to-end HTTP `<15ms` target is NOT ESTABLISHED** across tested concurrency and runs):
  ```json
  {
    "verdict": "BLOCK",
    "fraud_score": 0.82,
    "latency_ms": 3.41,
    "signals": ["RULE:HIGH_RISK_SHORTLINK", "RULE:URGENT_ACCOUNT_LOCKOUT", "HEURISTIC:COMPOUND_SIGNALS", "VELOCITY:BURST_10S"],
    "velocity": { "velocity_10s": 7, "velocity_60s": 14, "velocity_1h": 42, "carrier": "textnow" },
    "model_version": "1.0.0"
  }
  ```
- `POST /v1/events/batch`: High-throughput batch ingestion endpoint.
- `GET /metrics`: Standard Prometheus exposition scraping counter and latency histograms (`telecom_requests_total`, `telecom_latency_seconds`).
- `GET /api/v1/telecom/drift`: Kolmogorov-Smirnov test (feature drift) and Population Stability Index (PSI, prediction drift) monitoring.
- `GET /api/v1/telecom/stream`: Server-Sent Events (SSE) live feed of inspected telecom traffic.

### Quickstart & Load Testing Commands

```bash
# 1. Run the Pytest verification suite (233 passing backend tests across the full suite, plus 39 tracked frontend Node tests in clean checkout; 45 locally with 6 local-only Learning Hub tests)
cd backend
uv run pytest app/tests/test_telecom_gateway.py

# 2. Train and export the ONNX model from scratch (in-graph TF-IDF + sigmoid-calibrated Logistic Regression)
uv run python -m app.telecom.train_onnx_model

# 3. Simulate high-volume carrier traffic (100–1,000 req/sec)
uv run python -m ops.telecom_simulator --url http://127.0.0.1:8000/v1/classify --events 1000 --rps 200

# 4. Stress-test under concurrency with Locust
uv run locust -f ops/locustfile.py --headless -u 100 -r 20 --run-time 1m --host http://127.0.0.1:8000
```

### Full-Stack Live Dashboard

Navigate to `http://localhost:3000/telecom` (or `http://localhost:8080/telecom` via nginx):
- **Live Throughput (EPS)** gauge with rolling request counters.
- **Latency Percentile Cards (p50, p90, p95, p99)** with green/amber/red SLA badges.
- **Interactive SMS Tester**: Pre-loaded with legit 2FA codes, bank phishing, and courier scams.
- **Real-Time Rolling Stream**: Auto-scrolling feed of incoming traffic with instant verdict filters.
- **MLOps Drift Health**: Two-sample KS test $p$-value and Population Stability Index (PSI) gauges.

### Architectural Deep Dive

For future-scale enterprise architecture notes (Kafka partitioning design, Redis Cluster slot-tagging compatibility), cold-start mitigation, and degraded ML fail-open policies, see [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md).


# SentinelFlow

SentinelFlow is a production-style dispute investigation copilot built around an LLM investigator, typed tool outputs, deterministic risk and compliance services, and native LangGraph human approval pauses.

The local stack is now wired to run as a production-like image-based deployment with PostgreSQL, FastAPI, Next.js, and an nginx reverse proxy.

## What is included

- FastAPI backend with authenticated investigation endpoints
- Typed LangGraph state and native `interrupt()` approval node
- Tool layer that reads seeded dispute evidence from PostgreSQL
- Deterministic risk engine and versioned compliance checks
- Next.js 16 App Router console with SSE replay support
- Seed data for five dispute cases with visibly different investigation profiles
- Multi-stage Docker images for backend and frontend
- Durable queue execution path with Redis + arq worker
- Optional encrypted raw audit artifact vault for auditor/admin review flows
- nginx reverse proxy with request size limits, rate limiting, and SSE-safe buffering config
- Compose health checks and dependency conditions for startup ordering
- Local smoke test harness for end-to-end validation

## Repository layout

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
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.db.seed
uv run uvicorn app.main:app --reload --port 8000
```

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

- Production mode requires real JWT configuration and an OpenAI API key.
- The backend still uses an in-memory LangGraph checkpointer outside production; production mode validates PostgreSQL checkpointer requirements at startup and readiness.
- The SSE endpoint currently replays the latest persisted investigation state rather than maintaining a long-lived live push channel.
- The built-in backend rate limiter is in-memory. For horizontally scaled production, move rate limiting to shared infrastructure or a distributed backing store.

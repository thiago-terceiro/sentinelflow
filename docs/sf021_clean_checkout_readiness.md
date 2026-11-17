# SF-021 — Clean-Checkout Operational Readiness & Reproducible End-to-End Demo Report

**Linear Ticket:** `AI-34` (`SF-021`)  
**Status:** Complete (Verified in Isolated Clean Checkout with Zero Learning Hub Material)  
**Verified Base Commit:** `edacd8f` + `SF-019`/`SF-020`/`SF-021`/`SF-022` working tree tracked-only export (`305` files; `0` Learning Hub files)

---

## 1. Tested Environment & Prerequisites

* **Host OS:** Windows 11 (`AMD64`), Docker Engine `29.6.2` (`postgres:16-alpine`, `redis:7-alpine`)
* **Backend Toolchain:** Python `3.14.6` / `3.12+`, `uv`, `alembic 1.19.1`, `uvicorn`, `arq`, `onnxruntime 1.31.0`
* **Frontend Toolchain:** Node.js `v22+`, `pnpm 11.0.0`, Next.js `16.4.6`, Playwright `@playwright/test 1.64.1`
* **Tracked Prerequisites Check:** Works out of the box from `sentinelflow/.env.example` in `APP_ENV=development` without local-only Learning Hub files (`app/learn/`, `components/learn/`, `lib/i18n/`, `tests/learn-i18n.test.js`), `.env` personal secrets, or extra HMAC overrides.

---

## 2. Liveness vs. Readiness Hardening

| Endpoint | Behavior Verified | Failure Code (HTTP 503) |
|---|---|---|
| `GET /api/v1/health` | Fast process liveness (`{"status": "ok"}`); responds `200` even when DB, Redis, or ONNX model initialization fails so orchestrators distinguish process liveness from readiness. | N/A |
| `GET /api/v1/ready` | Verifies lifespan startup completion, DB `SELECT 1`, required PostgreSQL tables, ONNX `InferenceSession` availability, and (in `production`) LLM key + PostgreSQL checkpointer + Redis `PING`. | `READINESS_STARTING`, `READINESS_SCHEMA_MISSING`, `READINESS_MODEL_UNAVAILABLE`, `READINESS_PROVIDER_NOT_CONFIGURED`, `READINESS_CHECKPOINTER_INVALID`, `READINESS_QUEUE_UNAVAILABLE` |

Unit coverage in `sentinelflow/backend/app/tests/test_health_readiness.py` (`8 passed`) explicitly tests healthy, `READINESS_STARTING`, `READINESS_SCHEMA_MISSING`, `READINESS_MODEL_UNAVAILABLE`, and production dependency-unavailable states.

---

## 3. Reproducible Clean-Checkout Startup, Demo & Teardown

### 3.1 Clean-Checkout Startup Sequence
```bash
# 1. Start backing stores (Postgres 16 + standalone Redis 7)
docker run -d --name sf021-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=sentinelflow -p 127.0.0.1:5432:5432 postgres:16-alpine
docker run -d --name sf021-redis -p 127.0.0.1:6379:6379 redis:7-alpine

# 2. Configure env from tracked template
cp sentinelflow/.env.example sentinelflow/.env

# 3. Install backend, apply Alembic migrations (6 revisions), seed demo disputes
cd sentinelflow/backend
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.db.seed

# 4. Install frontend, build production bundle
cd ../frontend
pnpm install --frozen-lockfile
pnpm build

# 5. Start arq worker, FastAPI backend, and Next.js server (separate terminals)
cd ../backend && uv run arq app.worker.WorkerSettings
cd ../backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
cd ../frontend && pnpm exec next start -H 127.0.0.1 -p 3000
```

### 3.2 Reproducible Demo Command & Verified Scenarios
```bash
cd sentinelflow/backend
uv run python ../ops/demo_readiness.py --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:3000
uv run python ../ops/smoke_test.py --auth-mode dev_tokens --base-url http://127.0.0.1:8000
```

Every scenario below was executed end-to-end inside a disposable `%TEMP%\sf021-clean-checkout` tree (`305` tracked/product files, `0` Learning Hub files):

| Scenario | Route / Fixture (Explicitly Synthetic) | Verified Outcome |
|---|---|---|
| **Healthy Startup & Liveness/Readiness** | `/api/v1/health` & `/api/v1/ready` | `{"status": "ok"}` (200) and `{"status": "ready"}` (200); `39/39` clean-checkout frontend tests passed. |
| **Legitimate Message** | Synthetic 2FA OTP fixture (`legitimate_2fa`) | `ALLOW`, `fraud_score = 0.0026`, `ml_signal_valid = true`. |
| **Fraudulent Message** | Synthetic Bit.ly Chase smishing fixture (`fraudulent_smishing`) | `BLOCK`, `fraud_score = 1.0`, compound regex + ML + VoIP signals. |
| **Borderline Review + PII Redaction** | Synthetic billing notice with test PAN & email (`borderline_review_pii`) | `FLAG`, `fraud_score = 0.5036`; feed/summary masks `[REDACTED_PAN]` / `[REDACTED_EMAIL]`; Playwright UI renders `FLAG` + `PII REDACTED`. |
| **Unavailable / Invalid ML Inference** | Isolated backend with nulled ONNX session | `/api/v1/health -> 200 ok`; `/api/v1/ready -> 503 READINESS_MODEL_UNAVAILABLE`; `/v1/classify -> 200` fail-open (`ml_signal_valid=false`, `ml_signal_status="unavailable"`); UI displays `ML FALLBACK` badge + alert banner. |
| **Redis Outage & Recovery** | `docker stop` -> classify -> `docker start` + cooldown | HTTP `200` fail-open during outage (`velocity_backend="local_memory_fallback"`, `velocity_degraded_mode=true` matched in `/app-api/telecom/metrics/summary`); auto-restores to `redis` after cooldown. |
| **LangGraph Investigation + `arq` Worker + SSE** | `ops/smoke_test.py --auth-mode dev_tokens` | `101` SSE stream events, `46` replay events, `4` evidence records, `12` audit rows, `final_status = "completed"`. |
| **Teardown & Clean Second Run** | Stop frontend/backend/worker -> restart stack -> re-run `demo_readiness.py` | Zero leaked child processes, clean reset, identical Run 2 output. |

### 3.3 Teardown & Troubleshooting
```bash
docker rm -f sf021-pg sf021-redis
```
* **Scope Limitation:** This report proves reproducible local operation across a clean checkout on Docker Desktop + Windows 11. It does **not** establish public cloud deployment, Kubernetes autoscaling, or real-world external ML generalization (`SF-022`).
* **Local-Only Learning Hub Preservation:** Verified `app/learn/`, `components/learn/`, `lib/i18n/`, and `tests/learn-i18n.test.js` are never required in clean checkouts and remain untouched locally.

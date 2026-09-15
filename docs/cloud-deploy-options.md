# Cloud Deploy Options

> Personal reminder — written 2026-08-26

## What the stack is

Three Docker containers: **backend** (Python/FastAPI), **frontend** (Next.js), **postgres** (database).  
Nothing is tied to any cloud vendor. All config comes from environment variables.

---

## Option A — Simplest: Railway or Render

Both platforms can read the existing `docker-compose.yml` directly.

1. Push the repo to GitHub.
2. Connect the repo on [Railway](https://railway.app) or [Render](https://render.com).
3. Let the platform pick up the Compose file — it will start all three containers.
4. Set env vars in the platform dashboard (copy from `.env.example`).
5. Drop `NEXT_PUBLIC_DEV_TOKEN` and set a real `AUTH_JWT_SECRET`.

**Good for:** demos, personal use, quick test deploys.  
**Cost:** free tier available on both.

---

## Option B — Azure Container Apps

Best fit for Azure. Each container becomes its own Container App.

| Local container | Azure equivalent |
|---|---|
| `backend` | Container App (port 8000) |
| `frontend` | Container App (port 3000) |
| `postgres` | Azure Database for PostgreSQL (Flexible Server) |
| `nginx` | Drop it — Azure's built-in ingress handles routing |

### Steps

1. Build and push images to **Azure Container Registry (ACR)**.
2. Create a **Container Apps Environment**.
3. Deploy backend and frontend as separate Container Apps inside that environment.
4. Create an **Azure Database for PostgreSQL** instance and set `DATABASE_URL` to point to it.
5. Set all env vars in the Container App configuration blade.
6. Set up ingress rules so `/api/v1/*` routes to backend, everything else to frontend.

```bash
# rough CLI sketch
az containerapp create --name sentinelflow-backend \
  --image yourregistry.azurecr.io/sentinelflow-backend:latest \
  --env-vars APP_ENV=production DATABASE_URL=<azure-postgres-url> ...

az containerapp create --name sentinelflow-frontend \
  --image yourregistry.azurecr.io/sentinelflow-frontend:latest \
  --env-vars INTERNAL_API_BASE_URL=http://sentinelflow-backend:8000/api/v1 ...
```

**Azure Foundry is not the right tool here** — it is an AI model platform, not a container host.  
Use Azure Container Apps or App Service for hosting.

---

## Option C — AWS (ECS + Fargate)

| Local container | AWS equivalent |
|---|---|
| `backend` | ECS Fargate service |
| `frontend` | ECS Fargate service |
| `postgres` | RDS (PostgreSQL) |
| `nginx` | Application Load Balancer (ALB) |

### Steps

1. Push images to **Amazon ECR**.
2. Create an **ECS Cluster** (Fargate launch type).
3. Create a **Task Definition** for backend and frontend separately.
4. Store secrets in **AWS Systems Manager Parameter Store** or **Secrets Manager**, reference them as env vars in the task definitions.
5. Create an **Application Load Balancer**:
   - Route `/api/v1/*` → backend target group
   - Route everything else → frontend target group
6. Create an **RDS PostgreSQL** instance, set `DATABASE_URL` to point to it.

**Simpler AWS alternative:** **AWS App Runner** — directly deploys from a container image with far less config than ECS.

---

## Option D — Any VPS (DigitalOcean, Hetzner, Linode)

This is literally just running the Compose file on a Linux server.

```bash
# on the server
git clone <repo>
cd sentinelflow
cp .env.example .env
# edit .env with real values
docker compose up -d --build
```

Add a real domain and TLS with Certbot + nginx in front, or use Caddy as a simpler alternative.

---

## Before Any Real Deploy — Mandatory Fixes

These will break or expose you if skipped:

| # | What | Why it matters |
|---|---|---|
| 1 | Remove `NEXT_PUBLIC_DEV_TOKEN` and `NEXT_PUBLIC_REVIEWER_TOKEN` | Anyone can see these in the browser |
| 2 | Stop putting the auth token in the SSE URL (`?token=...`) | Cloud logs record every URL permanently |
| 3 | Set up Alembic migrations | Database tables need a proper setup path, not just the seed script |
| 4 | Add the Postgres LangGraph checkpoint dependency | Required for production-mode graph persistence |
| 5 | Set `AUTH_JWT_SECRET` to a real secret | The default `change-me` is in public docs |

---

## Inference Provider

The model gateway speaks **OpenAI-compatible API format**. Any of these work out of the box:

- [Groq](https://groq.com) — fast, free tier
- [Together AI](https://www.together.ai) — free credits
- [OpenRouter](https://openrouter.ai) — aggregator, many free models
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) — if already on Azure

Set in `.env`:

```env
OPENAI_API_KEY=your-key-from-provider
MODEL_BASE_URL=https://api.groq.com/openai/v1   # or equivalent
MODEL_NAME=llama-3.3-70b-versatile              # or whatever the provider calls it
```

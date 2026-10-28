---
name: sentinelflow-contract-sync
description: "Synchronizes backend FastAPI OpenAPI contracts with frontend TypeScript models. Use when adding or updating backend endpoints, schemas, or enums, and verifying zero contract drift via git diff --exit-code."
argument-hint: "backend, frontend, or drift-check"
---

# SentinelFlow Contract Synchronization Skill

## When To Use
- Changing FastAPI routes or Pydantic schemas in `sentinelflow/backend/app/schemas/`
- Regenerating `openapi.json` and TypeScript types
- Verifying zero contract drift in CI

## Procedure

### Step 1: Export OpenAPI JSON
```bash
cd sentinelflow/backend
uv run python -c "
import json
from app.main import app
spec = app.openapi()
with open('openapi.json', 'w', encoding='utf-8') as f:
    json.dump(spec, f, indent=2)
"
```

### Step 2: Generate TypeScript Types
```bash
cd sentinelflow/frontend
node scripts/generate-types.js
```

### Step 3: Verify Zero Contract Drift
```bash
git diff --exit-code sentinelflow/backend/openapi.json sentinelflow/frontend/lib/types/api.generated.ts
```
Exit 0 indicates verified contract synchronization.

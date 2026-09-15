---
name: sentinelflow-investigation-flow
description: "Trace and change the SentinelFlow investigation pipeline. Use when modifying dispute intake, evidence collection, analyzer output, LangGraph routing, approval flow, or the frontend investigation console. Includes self-verification checkpoints at every layer boundary."
argument-hint: "Describe the investigation behavior or bug to change"
---

# SentinelFlow Investigation Flow

## When To Use

- Changing how an investigation starts, progresses, pauses for approval, or completes
- Updating analyzer summaries, evidence events, risk output, or final reports
- Fixing cross-stack drift between backend investigation payloads and frontend console state

## Procedure

Each step has a verification checkpoint. Do not proceed to the next step if the checkpoint fails.

### Step 1 — Find the entry point

Read the relevant file before claiming to know what it does:

- Backend route: `sentinelflow/backend/app/api/disputes.py` or `sentinelflow/backend/app/api/approvals.py`
- Frontend action: `sentinelflow/frontend/lib/api.ts`
- Frontend state coordinator: `sentinelflow/frontend/hooks/useSentinelAgent.ts`

**Checkpoint 1**: Confirm the function signature or route path by reading the file.

### Step 2 — Trace the LangGraph execution path

Open each file and find where the behavior you are changing lives:

| File | Controls |
|------|----------|
| `sentinelflow/backend/app/graph/graph.py` | Graph topology and checkpointer |
| `sentinelflow/backend/app/graph/nodes.py` | Node logic — what each step does |
| `sentinelflow/backend/app/graph/routing.py` | Conditional edges — what runs next |
| `sentinelflow/backend/app/graph/state.py` | Typed state fields |

**Checkpoint 2**: State which node and routing condition owns the behavior you are changing, with a file:line reference.

### Step 3 — Check typed boundaries

If the change affects the API response or streamed events, verify:

- `sentinelflow/backend/app/schemas/` — Pydantic response models
- `sentinelflow/frontend/lib/types.ts` — TypeScript consumer types

**Checkpoint 3**: If you add or rename a field, confirm the change is reflected in both the schema and the TypeScript type before proceeding.

### Step 4 — Keep deterministic rules in the right layer

- Scoring, compliance, and risk rules belong in `sentinelflow/backend/app/services/` or `sentinelflow/backend/app/tools/`.
- Do not move business rules into LLM prompt strings — they become untestable.

### Step 5 — Validate both halves (mandatory for any API or event contract change)

Run and confirm exit codes:

```bash
bash .github/scripts/validate-sentinelflow.sh all
```

**Checkpoint 5**: Both command groups must exit 0. If either fails, fix and rerun before declaring done.

## Output

Close this skill by reporting:

```
INVESTIGATION FLOW COMPLETE

Behavior changed: [description]
Owning files changed:
  - [file:line]: [what changed]
Checkpoints passed: [1, 2, 3, 5 — or list which were skipped and why]
Validation:
  - Backend: [tests N passed, lint clean, exit 0]
  - Frontend: [build succeeded, exit 0]  (or "not applicable")
```

or

```
INVESTIGATION FLOW BLOCKED

Blocked at: [checkpoint N]
Reason: [specific problem with evidence]
What is needed to unblock: [exact condition]
```
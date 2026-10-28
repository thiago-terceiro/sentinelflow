---
name: sentinelflow-investigation-lifecycle
description: >-
  Guides changes to the LangGraph multi-agent dispute investigation workflow. Use when modifying graph nodes, pure state reducers, checkpoint hydration, human-in-the-loop interrupt/resume contracts, bounded revision loops, or real-time reasoning_delta SSE streaming.
---

# SentinelFlow Investigation Lifecycle Skill

This skill documents how to safely inspect, modify, and extend the LangGraph asynchronous dispute investigation copilot in SentinelFlow.

## Architecture & Subsystem Layout

```mermaid
flowchart TD
    Intake["1. intake\n(Ingest Dispute + Prompt Injection Guardrail)"] --> Investigate["2. investigate\n(LLM Formulates Hypotheses & Tool Requests)"]
    Investigate --> Collect["3. collect\n(Parallel Async Tools: Transactions, Device, etc.)"]
    Collect --> Synthesize["4. synthesize\n(Deterministic Scoring + LLM Synthesis)"]
    Synthesize --> ApprovalDecision{"Risk Threshold Breached?"}
    ApprovalDecision -->|Yes| Interrupt["5. approval\n(LangGraph interrupt() -> Wait for Human)"]
    ApprovalDecision -->|No| Finalize["6. finalize\n(Write Terminal Audit & Close Dispute)"]
    Interrupt -->|Human: Approve / Deny| Finalize
    Interrupt -->|Human: Request Revision\n(max 3 cycles)| Investigate
```

---

## State Schema & Pure Reducers

File: `sentinelflow/backend/app/graph/state.py`
All graph mutations must happen through strongly typed state schemas with explicit reducers:
- `evidence`: Annotated with `operator.add` to accumulate evidence objects without clobbering prior findings.
- `timeline_events`: Annotated with `operator.add` to maintain a sequential log of timeline entries.
- `messages`: Annotated with `add_messages` for conversation history.
- `iteration_count`: Incremented deterministically on revision steering cycles.

### Strict Reducer Rule
Never mutate state dictionaries in place within a node. Always return a dictionary containing only the updated fields:
```python
# CORRECT: Pure functional return
return {
    "evidence": new_evidence_items,
    "timeline_events": [new_event],
    "iteration_count": state.get("iteration_count", 0) + 1,
}

# WRONG: In-place mutation (breaks checkpoint serialization and time-travel replay)
state["evidence"].extend(new_evidence_items)  # NEVER DO THIS
```

---

## Modifying Graph Nodes & Edge Transitions

1. **Graph Definition**: `sentinelflow/backend/app/graph/graph.py`
2. **Node Logic**: `sentinelflow/backend/app/graph/nodes.py`
3. **Routing Conditions**: `sentinelflow/backend/app/graph/routing.py`

### Safety Rules for Node Changes:
1. **Pre-Inference Sanitization**:
   Before passing any customer or dispute text into an LLM prompt, always call `redact_text(input_text)` from `app.services.trace_safety`.
2. **Deterministic Rules Belong in Services**:
   Scoring formulas, compliance thresholds, and velocity risk contributions belong in `sentinelflow/backend/app/services/` or `app/tools/`, never buried inside LLM system prompts.
3. **Bounded Revision Loop (`MAX_REVISION_CYCLES = 3`)**:
   In `sentinelflow/backend/app/graph/routing.py`, verify that conditional routing checks `iteration_count >= MAX_REVISION_CYCLES` and routes to `finalize` or escalates to senior review rather than cycling endlessly.

---

## Human-in-the-Loop Interrupt & Cold-Hydration

1. **Halting Execution**:
   ```python
   # Inside app/graph/nodes.py: approval_node
   from langgraph.types import interrupt
   human_decision = interrupt({
       "status": "approval_required",
       "reason": "Risk score 0.88 exceeds policy threshold 0.70",
       "recommendation": state.get("recommendation"),
   })
   ```
2. **Persisting Mid-Run State**:
   - `persist_graph_state()` writes current state and timeline events to PostgreSQL `InvestigationRecord`.
   - Browser refreshes (`F5`) query `GET /disputes/{id}` and receive full state (`cold-hydration`) without re-running the graph.
3. **Resuming Execution**:
   - The reviewer submits a decision (`approve`, `deny`, or `request_revision`) via `POST /investigations/{id}/resume`.
   - The API triggers `Command(resume=payload)` on the LangGraph instance, resuming from the exact interrupt checkpoint.

---

## Real-Time Streaming (`reasoning_delta`)

1. During `investigate` and `synthesize` steps, the LLM emits live tokens.
2. `ModelGateway.generate_structured` streams chunks through `InvestigationBroadcaster.broadcast(event)`.
3. Frontend receives tokens via `sentinelflow/frontend/lib/sse.ts` and merges them with `useSentinelAgent.ts`.
4. Ensure event names remain aligned:
   - `reasoning_delta`: Live token streaming
   - `evidence_collected`: New evidence item gathered
   - `analyzer_completed`: Deterministic analyzer completed
   - `approval_required`: Graph interrupted for human decision
   - `investigation_completed`: Final report ready

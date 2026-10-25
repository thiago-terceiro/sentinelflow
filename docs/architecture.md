# SentinelFlow — Architecture Reference

> **Audience:** New engineers joining the team, technical interviews, system design discussions.
> Every diagram is self-contained. Read top-to-bottom for increasing detail.

---

## 1 · High-Level System Map

Shows every runtime process, the data stores they own, and the communication patterns between them.

```mermaid
graph TB
    subgraph CLIENT["Browser / Client"]
        FE["Next.js 16 · React 19<br/>Port 3000"]
    end

    subgraph BACKEND["FastAPI Backend · Port 8000"]
        API["HTTP Routers<br/>/disputes  /investigations  /approvals  /health"]
        SEC["JWT / OIDC<br/>Auth + RBAC"]
        SVC["Services Layer<br/>risk · compliance · audit · model-gateway"]
        GRAPH["LangGraph<br/>Investigation Orchestrator"]
        WORKER["arq Worker<br/>(background jobs)"]
    end

    subgraph STORES["Data Stores"]
        PG[("PostgreSQL<br/>disputes · investigations<br/>audit · checkpoints")]
        REDIS[("Redis<br/>Job Queue")]
    end

    subgraph EXTERNAL["External Services"]
        LLM["OpenAI-compatible<br/>LLM Gateway<br/>gpt-4.1-mini"]
        OIDC["OIDC Provider<br/>(Auth0 / Keycloak / AzureAD)"]
        OTEL["OTEL Collector<br/>(optional telemetry)"]
    end

    %% FE → Backend
    FE -- "REST  GET/POST" --> API
    FE -- "SSE stream<br/>/investigations/{id}/stream" --> API
    FE -- "PKCE auth flow" --> OIDC

    %% API internals
    API --> SEC
    API --> SVC
    API --> PG
    API -- "enqueue job" --> REDIS

    %% Worker
    REDIS -- "dequeue job" --> WORKER
    WORKER --> GRAPH
    WORKER --> PG

    %% Graph
    GRAPH --> SVC
    GRAPH --> LLM
    GRAPH -- "checkpoints" --> PG

    %% Telemetry
    SVC -.-> OTEL
    GRAPH -.-> OTEL
```

**Communication key**

| Pattern | Where used |
|---|---|
| REST (JSON) | All FE → BE CRUD operations |
| SSE (text/event-stream) | Real-time investigation progress to the browser |
| arq job queue via Redis | Decouples HTTP response from LangGraph execution |
| LangGraph interrupt | Pause execution at `approval` node; resume after human decision |
| LangGraph Postgres checkpointer | Durable state in production; in-memory in dev |

---

## 2 · Frontend — Detailed Architecture

Shows how Next.js pages, React components, the state hook, and transport utilities relate to each other.

```mermaid
graph TB
    subgraph NEXTJS["Next.js App Router  (app/)"]
        HOME["page.tsx<br/>Dispute list home"]
        DETAIL["disputes/[disputeId]/page.tsx<br/>Investigation console entry"]
        AUTH_ROUTES["auth/<br/>login · callback · logout"]
        PROXY["app-api/<br/>Server-side API proxy"]
    end

    subgraph COMPONENTS["React Components  (components/)"]
        CONSOLE["InvestigationConsole<br/>↳ launch button, stream lifecycle,<br/>   time-travel state scrubber,<br/>   cross-panel provenance highlighting"]
        SCRUBBER["TimeTravelScrubber<br/>↳ range slider (0..N-1), step counter,<br/>   event badge, live head return,<br/>   keyboard shortcuts: [, ], L"]
        DIFF_PANEL["InvestigationDiffPanel<br/>↳ semantic iteration diffs,<br/>   confidence shifts, attribution badges"]
        REASONING["AgentReasoningPanel<br/>↳ thought process, reasoning steps,<br/>   embedded diff panel, citation pills"]
        EVIDENCE["EvidencePanel<br/>↳ category, confidence, provenance,<br/>   scrollIntoView, highlighted glow ring"]
        RISK["RiskPanel<br/>↳ score meter, level badge,<br/>   factor breakdown"]
        ANALYZER["AnalyzerPanel<br/>↳ findings, contradictions,<br/>   interactive evidence citation pills"]
        APPROVAL["ApprovalPanel<br/>↳ approve / deny buttons,<br/>   guidance input, comment textarea"]
        TIMELINE["InvestigationTimeline<br/>↳ ordered event log"]
        STRIP["AgentMessageStrip<br/>↳ current agent activity"]
        EB["ErrorBoundary"]
    end

    subgraph HOOKS["State Coordinator  (hooks/)"]
        HOOK["useSentinelAgent<br/>─────────────────────<br/>state: ConsoleState (live head)<br/>displayState: derived @ step k<br/>rawEvents: StreamEvent[] (history)<br/>selectedEventIndex: number | null<br/>iterationSnapshots[] · iterationDiffs[]<br/>─────────────────────<br/>actions: launch() · review()<br/>goToStep() · goToPreviousStep()<br/>goToNextStep() · goToLiveHead()<br/>─────────────────────<br/>SSE lifecycle & resilience:<br/>  connect → background events buffer<br/>  reconnect with exponential backoff"]
    end

    subgraph LIB["Transport + State Utilities  (lib/)"]
        API_LIB["api.ts<br/>listDisputes()<br/>startInvestigation()<br/>getInvestigation()<br/>resumeInvestigation()"]
        SSE_LIB["sse.ts<br/>openInvestigationStream()<br/>─ parses SSE chunks<br/>─ calls onEvent / onError / onClose"]
        STATE_LIB["investigationState.ts<br/>deriveConsoleStateAtStep() (&lt;0.03ms)<br/>extractIterationSnapshots()<br/>computeIterationDiff()<br/>applyStreamEventToConsoleState()<br/>applyRunToConsoleState()"]
        RECON["investigationStream.ts<br/>shouldReconnectInvestigation()<br/>streamReconnectDelayMs()"]
        OIDC_LIB["oidc.ts<br/>PKCE helpers, cookie mgmt<br/>OIDC discovery document"]
        TYPES["types.ts<br/>DisputeSummary, Evidence<br/>IterationSnapshot, IterationDiff<br/>RiskAssessment, InvestigationRun<br/>StreamEvent, ConsoleState, …"]
    end

    %% Page → Components
    HOME --> CONSOLE
    DETAIL --> CONSOLE
    CONSOLE --> SCRUBBER
    CONSOLE --> REASONING
    CONSOLE --> EVIDENCE
    CONSOLE --> RISK
    CONSOLE --> ANALYZER
    CONSOLE --> APPROVAL
    CONSOLE --> TIMELINE
    CONSOLE --> STRIP
    REASONING --> DIFF_PANEL
    EB --> CONSOLE

    %% Components → Hook
    CONSOLE --> HOOK

    %% Hook → Lib
    HOOK --> API_LIB
    HOOK --> SSE_LIB
    HOOK --> STATE_LIB
    HOOK --> RECON

    %% Auth
    AUTH_ROUTES --> OIDC_LIB
    AUTH_ROUTES --> PROXY

    %% Types used everywhere
    TYPES -. "shared interfaces" .-> HOOK
    TYPES -. "shared interfaces" .-> API_LIB
    TYPES -. "shared interfaces" .-> STATE_LIB
```

### SSE Reconnect Flow

```mermaid
sequenceDiagram
    participant Browser
    participant useSentinelAgent
    participant sse.ts
    participant Backend

    Browser->>useSentinelAgent: launch()
    useSentinelAgent->>Backend: POST /disputes/{id}/investigations
    Backend-->>useSentinelAgent: { investigationId }

    useSentinelAgent->>sse.ts: openInvestigationStream(url)
    sse.ts->>Backend: GET /investigations/{id}/stream (SSE)

    loop while status ≠ completed | failed
        Backend-->>sse.ts: data: { type, data }
        sse.ts-->>useSentinelAgent: onEvent(StreamEvent)
        useSentinelAgent->>useSentinelAgent: applyStreamEventToConsoleState()
    end

    alt Connection dropped
        sse.ts-->>useSentinelAgent: onError
        useSentinelAgent->>useSentinelAgent: shouldReconnect? (max 3 attempts)
        useSentinelAgent->>Backend: GET /investigations/{id}  [poll missed state]
        useSentinelAgent->>useSentinelAgent: applyRunToConsoleState()
        Note over useSentinelAgent: delay = 500ms × 2^attempt
        useSentinelAgent->>sse.ts: openInvestigationStream() [retry]
    end

    alt approval_required event
        Backend-->>sse.ts: type: approval_required
        useSentinelAgent-->>Browser: show ApprovalPanel
        Browser->>useSentinelAgent: review(decision, comment)
        useSentinelAgent->>Backend: POST /investigations/{id}/resume
    end
```

---

## 3 · Backend — API & Services Layer

Shows the FastAPI application stack: routers, security middleware, service modules, database models, and schemas.

```mermaid
graph TB
    subgraph FASTAPI["FastAPI Application  (app/main.py)"]
        MW["Middleware<br/>CORSMiddleware<br/>OTEL tracing<br/>structured logging"]
        ROUTERS["Routers  (app/api/)"]
    end

    subgraph ROUTERS_DETAIL["Routers  (app/api/)"]
        R_DISPUTES["disputes.py<br/>─────────────────<br/>GET  /disputes<br/>POST /disputes<br/>POST /disputes/{id}/investigations<br/>GET  /investigations/{id}<br/>GET  /investigations/{id}/stream"]
        R_APPROVALS["approvals.py<br/>─────────────────<br/>POST /investigations/{id}/resume"]
        R_HEALTH["health.py<br/>─────────────────<br/>GET  /health"]
        DEPS["deps.py  (DI)<br/>─────────────────<br/>DBSessionDep<br/>PrincipalDep"]
    end

    subgraph SECURITY["Auth & RBAC  (app/security.py)"]
        JWT["JWT validation<br/>JWKS endpoint or dev token"]
        ROLES["Role extraction<br/>roles / groups / scp /<br/>realm_access / resource_access"]
        RBAC["Role enum<br/>INVESTIGATOR<br/>SENIOR_INVESTIGATOR<br/>REVIEWER · AUDITOR · ADMIN"]
        PRINCIPAL["Principal.require_any(*roles)<br/>→ AuthorizationError"]
    end

    subgraph SCHEMAS["Request / Response Shapes  (app/schemas/)"]
        S_DISPUTE["disputes.py<br/>DisputeSummary · DisputeDetail<br/>DisputeCreateRequest · DisputeStatus"]
        S_INV["investigation.py<br/>Evidence · AnalyzerSummary<br/>RiskFactor · RiskAssessment<br/>ComplianceFinding · InvestigationReport<br/>InvestigationRun · InvestigationBudget"]
        S_EVENTS["events.py<br/>StreamEvent · StreamEventType (×14)"]
        S_APPROVAL["approval.py<br/>ApprovalDecision · ApprovalRecord"]
    end

    subgraph SERVICES["Business Logic  (app/services/)"]
        SVC_INV["investigations.py<br/>budget() · to_run() · thread_config()<br/>schedule_investigation() [→ Redis]<br/>schedule_resume() [→ Redis]<br/>stream_graph_events() [SSE generator]"]
        SVC_RISK["risk.py  ← deterministic<br/>calculate_risk(evidence, analyzers)<br/>Factors: tx_amount(0.22) · velocity(0.14)<br/>geo(0.12) · device(0.18)<br/>customer(0.16) · merchant(0.12)<br/>→ RiskAssessment {score, level}"]
        SVC_COMP["compliance.py  ← deterministic<br/>evaluate_compliance(evidence)<br/>CN-001: amount > 2500 → review<br/>CN-000: missing evidence"]
        SVC_AUDIT["audit.py<br/>record_audit_event() [HMAC chain]<br/>verify_audit_integrity()<br/>get_raw_audit_artifact()"]
        SVC_MODEL["model_gateway.py<br/>ModelGateway.generate_structured()<br/>→ LLMCallResult {usage, sha256,<br/>   latency, redaction_flags}"]
        SVC_TRACE["trace_safety.py<br/>redact_text() [emails, phones,<br/>cards, JWTs, API keys]<br/>sha256_text() [provenance hash]"]
    end

    subgraph DB["Database  (app/db/)"]
        M_DISPUTE["DisputeRecord<br/>id · case_code · title · narrative<br/>customer_id · merchant_id<br/>amount · currency · status · attributes"]
        M_INV["InvestigationRecord<br/>id · dispute_id(FK) · thread_id<br/>status · evidence · analyzer_summaries<br/>hypotheses · timeline_events<br/>risk_assessment · report<br/>iteration_count · tool_call_count"]
        M_AUDIT["AuditRecord<br/>id · investigation_id · actor_id<br/>event_name · payload · sequence_no<br/>prev_hash · row_hash"]
        M_ARTIFACT["AuditArtifactRecord<br/>id · audit_record_id(FK)<br/>key_id · ciphertext"]
    end

    %% wiring
    ROUTERS --> ROUTERS_DETAIL
    MW --> ROUTERS
    R_DISPUTES --> DEPS
    R_APPROVALS --> DEPS
    DEPS --> SECURITY
    SECURITY --> JWT
    JWT --> ROLES --> RBAC --> PRINCIPAL

    R_DISPUTES --> SVC_INV
    R_DISPUTES --> S_DISPUTE
    R_DISPUTES --> S_INV
    R_DISPUTES --> S_EVENTS
    R_APPROVALS --> S_APPROVAL
    R_APPROVALS --> SVC_INV

    SVC_INV --> DB
    SVC_RISK --> S_INV
    SVC_COMP --> S_INV
    SVC_AUDIT --> M_AUDIT
    SVC_AUDIT --> SVC_TRACE
    SVC_MODEL --> SVC_TRACE

    DB --> M_DISPUTE
    DB --> M_INV
    DB --> M_AUDIT
    DB --> M_ARTIFACT
```

### Request Lifecycle — Start Investigation

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant SEC as security.py
    participant SVC as investigations.py
    participant DB as PostgreSQL
    participant REDIS as Redis Queue

    FE->>API: POST /disputes/{id}/investigations<br/>Authorization: Bearer <token>
    API->>SEC: validate token
    SEC-->>API: Principal { id, roles: [INVESTIGATOR] }
    API->>API: require_any(INVESTIGATOR, ADMIN)

    API->>DB: INSERT InvestigationRecord<br/>{ dispute_id, thread_id=uuid4(), status=pending }
    DB-->>API: investigation record

    API->>SVC: schedule_investigation(investigation_id, principal)
    SVC->>REDIS: ENQUEUE run_investigation_job { investigation_id }
    REDIS-->>SVC: queued

    API-->>FE: 201 InvestigationRun { id, status: "pending" }

    Note over REDIS: Worker picks up job asynchronously
```

---

## 4 · Backend — LangGraph Investigation Pipeline

Shows the stateful graph, every node's responsibility, routing decisions, agents, tools, and how human approval interrupts execution.

### 4a · Graph Overview

```mermaid
stateDiagram-v2
    [*] --> intake : Worker starts run_investigation_job

    intake --> investigate : Loads dispute from DB\nSets status = running

    investigate --> collect : pending_tools OR\npending_analyzers exist
    investigate --> synthesize : No more gaps OR\nmax_iterations reached

    collect --> investigate : Evidence appended\nloop back for re-evaluation

    synthesize --> approval : recommendation = escalate\nOR threshold_triggered = true
    synthesize --> finalize : recommendation = approve/deny\nno threshold

    approval --> approval : ⏸ INTERRUPT\nWaiting for human decision\n(POST /investigations/{id}/resume)
    approval --> finalize : Decision received\nReport updated if deny

    finalize --> [*] : status = completed\nrun_completed event emitted
```

### 4b · Detailed Node Map

```mermaid
graph TB
    subgraph STATE["DisputeState  (graph/state.py)"]
        ST_ID["Identity<br/>dispute_id · investigation_id<br/>thread_id · principal_id · roles"]
        ST_DATA["Investigation Data<br/>dispute · messages · evidence[]<br/>analyzer_summaries[] · hypotheses[]<br/>risk_assessment · compliance_findings[]<br/>investigation_report"]
        ST_TRACK["Execution Tracking<br/>iteration_count · tool_call_count<br/>analyzer_call_count · status<br/>pending_tools[] · pending_analyzers[]<br/>failed_tools[] · failed_analyzers[]"]
        ST_EVENTS["Events & Approval<br/>timeline_events[] · approval_request<br/>approval_decision · checkpoint_ref"]
    end

    subgraph NODES["Graph Nodes  (graph/nodes.py)"]
        N_INTAKE["intake<br/>────────────<br/>Load DisputeDetail from DB<br/>Set status = running<br/>Append system message"]

        N_INVEST["investigate<br/>────────────<br/>InvestigatorAgent.run_iteration()<br/>→ hypotheses, unresolved_questions<br/>→ tool_requests, analyzer_requests<br/>Emit: hypothesis_updated<br/>       agent_status_updated<br/>Record LLM trace (audit)"]

        N_COLLECT["collect<br/>────────────<br/>Parallel asyncio.gather():<br/>  fetch_transaction_history()<br/>  fetch_customer_profile()<br/>  fetch_device_context()<br/>  fetch_merchant_profile()<br/>  run_analyzer(fraud, device)<br/>session_lock: serialize DB audit writes<br/>Instant intra-node event broadcast:<br/>  tool_started / tool_completed<br/>  evidence_added<br/>  analyzer_started / analyzer_completed<br/>Deterministic evidence list order"]

        N_SYNTH["synthesize<br/>────────────<br/>calculate_risk()  ← deterministic<br/>evaluate_compliance()  ← deterministic<br/>SynthesizerAgent.build_report()  ← LLM<br/>→ InvestigationReport<br/>   { conclusion, recommendation,<br/>     confidence, hypotheses,<br/>     risk_factors, compliance_findings }"]

        N_APPROVAL["approval  ⏸ interrupt<br/>────────────<br/>Emit approval_required event<br/>Pause via langgraph interrupt()<br/>─ ─ ─ wait for human ─ ─ ─<br/>Receive ApprovalDecision<br/>Update report if deny<br/>Record approval audit event"]

        N_FINALIZE["finalize<br/>────────────<br/>Set status = completed<br/>Persist final state to DB<br/>Emit run_completed event"]
    end

    subgraph ROUTING["Routing  (graph/routing.py)"]
        R1["route_after_investigator()<br/>iteration_count ≥ max → synthesize<br/>pending tools/analyzers → collect<br/>else → synthesize"]
        R2["route_after_recommendation()<br/>escalate OR threshold_triggered → approval<br/>else → finalize"]
    end

    subgraph AGENTS["LLM Agents  (app/agents/)"]
        AG_INV["InvestigatorAgent<br/>(agents/investigator.py)<br/>────────────────────<br/>Prompt: investigator_system<br/>        investigator_iteration<br/>Output: InvestigatorIteration<br/>  • summary<br/>  • hypotheses[]<br/>  • unresolved_questions[]<br/>  • tool_requests[]  { name, reason }<br/>  • analyzer_requests[]  { name, reason }<br/>  • should_finish<br/>────────────────────<br/>Heuristic fallback if LLM down"]

        AG_SYNTH["SynthesizerAgent<br/>(agents/synthesizer.py)<br/>────────────────────<br/>Prompt: investigator_system<br/>        evidence_synthesis<br/>        final_recommendation<br/>Output: SynthesisOutput<br/>  • conclusion<br/>  • recommendation  (approve/deny/escalate)<br/>  • confidence<br/>────────────────────<br/>Heuristic fallback if LLM down"]

        AG_ANLYZ["Analyzers<br/>(agents/analyzers.py)<br/>────────────────────<br/>fraud_pattern<br/>  velocity · history · geo anomalies<br/>device_fingerprint<br/>  recognized device · account takeover<br/>→ AnalyzerSummary { findings, contradictions,<br/>   confidence, recommended_followups }"]
    end

    subgraph TOOLS["Evidence Tools  (app/tools/)"]
        T_TX["transactions.py<br/>fetch_transaction_history()<br/>→ Evidence: amount, velocity_24h,<br/>   geo_anomaly, auth_events"]
        T_CUST["customer.py<br/>fetch_customer_profile()<br/>→ Evidence: prior_disputes,<br/>   fraud_signals, tenure_years"]
        T_DEV["device.py<br/>fetch_device_context()<br/>→ Evidence: recognized_device,<br/>   ip_velocity, geo_distance_km"]
        T_MERCH["merchant.py<br/>fetch_merchant_profile()<br/>→ Evidence: risk_tier,<br/>   dispute_rate, category"]
    end

    subgraph PROMPTS["Prompt Templates  (graph/prompts.py)"]
        P1["investigator_system<br/>Role definition · tool-use rules"]
        P2["investigator_iteration<br/>Assess evidence · identify gaps"]
        P3["evidence_synthesis<br/>Condense evidence chain"]
        P4["final_recommendation<br/>Structured output schema"]
        P5["analyzer_interpretation<br/>Parse analyzer output as evidence"]
    end

    %% Node flow
    N_INTAKE --> N_INVEST
    N_INVEST --> R1
    R1 -- "pending work" --> N_COLLECT
    R1 -- "no gaps" --> N_SYNTH
    N_COLLECT --> N_INVEST
    N_SYNTH --> R2
    R2 -- "escalate/threshold" --> N_APPROVAL
    R2 -- "approve/deny" --> N_FINALIZE

    %% Agents plugged into nodes
    N_INVEST --> AG_INV
    N_SYNTH --> AG_SYNTH
    N_COLLECT --> AG_ANLYZ

    %% Tools plugged into collect
    N_COLLECT --> T_TX
    N_COLLECT --> T_CUST
    N_COLLECT --> T_DEV
    N_COLLECT --> T_MERCH

    %% Prompts feed agents
    P1 --> AG_INV
    P2 --> AG_INV
    P1 --> AG_SYNTH
    P3 --> AG_SYNTH
    P4 --> AG_SYNTH

    %% State underpins everything
    STATE -. "shared mutable state" .-> NODES
```

### 4c · Evidence & Risk Pipeline (data flow through synthesize)

```mermaid
flowchart LR
    EV["evidence[]<br/>4 categories<br/>transaction · customer<br/>device · merchant"]
    AN["analyzer_summaries[]<br/>fraud_pattern<br/>device_fingerprint"]

    subgraph RISK_CALC["calculate_risk()  —  deterministic"]
        W1["tx_amount     × 0.22"]
        W2["velocity      × 0.14"]
        W3["geo_anomaly   × 0.12"]
        W4["device        × 0.18"]
        W5["customer_hist × 0.16"]
        W6["merchant_risk × 0.12"]
        SCORE["Σ weighted scores<br/>→ 0–1 normalised"]
        LEVEL["level<br/>critical ≥ 0.90<br/>high     ≥ 0.60<br/>medium   ≥ 0.45<br/>low      < 0.45"]
    end

    subgraph COMP_EVAL["evaluate_compliance()  —  deterministic"]
        CN001["CN-001: amount > 2500<br/>→ requires_review = true"]
        CN000["CN-000: missing evidence<br/>→ finding added"]
    end

    subgraph LLM_SYNTH["SynthesizerAgent  —  LLM"]
        CONCL["conclusion (narrative)"]
        REC["recommendation<br/>approve | deny | escalate"]
        CONF["confidence  0.0–1.0"]
    end

    subgraph REPORT["InvestigationReport"]
        RF["conclusion · recommendation<br/>confidence · hypotheses[]<br/>risk_factors[] · evidence_ids[]<br/>unresolved_questions[]<br/>compliance_findings[]"]
    end

    EV --> RISK_CALC
    AN --> RISK_CALC
    EV --> COMP_EVAL
    RISK_CALC --> SCORE --> LEVEL
    COMP_EVAL --> CN001
    COMP_EVAL --> CN000

    LEVEL --> LLM_SYNTH
    CN001 --> LLM_SYNTH
    EV --> LLM_SYNTH
    AN --> LLM_SYNTH

    LLM_SYNTH --> CONCL --> RF
    LLM_SYNTH --> REC   --> RF
    LLM_SYNTH --> CONF  --> RF
```

### 4d · Human Approval Flow

```mermaid
sequenceDiagram
    participant Worker
    participant Graph as LangGraph
    participant DB as PostgreSQL
    participant API as FastAPI
    participant FE as Frontend (Reviewer)

    Worker->>Graph: resume(thread_id, inputs)
    Graph->>Graph: synthesize node
    Note over Graph: recommendation = "escalate"
    Graph->>DB: checkpoint saved (status=pending_review)
    Graph->>DB: timeline_event: approval_required
    Graph-->>Graph: interrupt()  ⏸  PAUSED

    DB-->>API: stream_graph_events() polls checkpoint
    API-->>FE: SSE: { type: "approval_required", data: { risk, report } }
    FE-->>FE: render ApprovalPanel

    FE->>API: POST /investigations/{id}/resume<br/>{ decision: "approve", comment: "..." }
    API->>API: require_any(REVIEWER, ADMIN)
    API->>DB: record_audit_event(approval)
    API->>Worker: schedule_resume(investigation_id, decision)
    Worker->>Graph: resume with ApprovalDecision injected into state

    Graph->>Graph: approval node reads decision
    Graph->>Graph: finalize node
    Graph->>DB: status = completed
    Graph-->>API: timeline_event: run_completed
    API-->>FE: SSE: { type: "run_completed" }
    FE-->>FE: render final report
```

---

## 5 · Worker & Queue

```mermaid
graph LR
    subgraph HTTP["HTTP Request (sync)"]
        API2["FastAPI<br/>POST /disputes/{id}/investigations<br/>POST /investigations/{id}/resume"]
    end

    subgraph QUEUE["Redis Job Queue (arq)"]
        Q1["run_investigation_job<br/>{ investigation_id, principal_context }"]
        Q2["run_resume_investigation_job<br/>{ investigation_id, approval_decision }"]
    end

    subgraph WORKER_PROC["arq Worker Process  (app/worker.py)"]
        W_INV["run_investigation_job handler<br/>1. Load InvestigationRecord from DB<br/>2. Build DisputeState (initial)<br/>3. graph.ainvoke(state, config)<br/>4. Persist final state to DB"]
        W_RES["run_resume_investigation_job handler<br/>1. Load checkpoint by thread_id<br/>2. Inject ApprovalDecision into state<br/>3. graph.ainvoke(None, config)<br/>   (resumes from interrupt point)"]
    end

    API2 -- "schedule_investigation()" --> Q1
    API2 -- "schedule_resume()" --> Q2
    Q1 --> W_INV
    Q2 --> W_RES
    W_INV --> GRAPH2["LangGraph\ngraph.ainvoke()"]
    W_RES --> GRAPH2
```

---

## 6 · Key Design Decisions

| Decision | Rationale |
|---|---|
| **Deterministic risk + compliance** | Risk scores and compliance findings use pure functions (`services/risk.py`, `services/compliance.py`), not LLM judgment. Auditable, reproducible, testable. |
| **LLM only for reasoning gaps** | The investigator and synthesizer agents handle analysis that requires natural language understanding. Evidence gathering uses deterministic tools. |
| **Interrupt-based human approval** | LangGraph's `interrupt()` pauses graph execution at a checkpoint without blocking threads. The HTTP handler resumes the graph via the worker queue. |
| **SSE over WebSocket** | Unidirectional server-push is sufficient and simpler to proxy/load-balance. Reconnect with state poll covers dropped connections. |
| **HMAC audit chain** | Every audit event includes `prev_hash + row_hash` (HMAC-SHA256). Tampering breaks the chain and is detectable via `verify_audit_integrity()`. |
| **arq worker decoupling** | Investigations can take minutes. The HTTP layer returns immediately after enqueueing. The worker handles all long-running graph execution. |
| **Dev token fallback** | Hardcoded dev tokens (`dev-investigator`, `dev-reviewer`, etc.) allow local development without an OIDC provider. Disabled by env flag in production. |
| **Client-Side Time-Travel State Scrubber** | Investigators can scrub backward through arbitrary historical events (`0..N-1`) via `deriveConsoleStateAtStep()` in `<0.03ms`. Background incoming SSE events continue appending to `rawEvents` without jumping or dropping state. |
| **Iteration & Revision Diff Inspector** | Evaluates semantic state shifts between iterations (`IterationSnapshot` & `computeIterationDiff`) with clear attribution badges (`[AI Investigator]`, `[Human Reviewer Steering]`, `[Deterministic Engine]`), confidence deltas, and risk score tracking. |
| **Cross-Panel Evidence Provenance Highlighting** | Clicking evidence citations in `AnalyzerPanel` or `AgentReasoningPanel` highlights evidence cards in `EvidencePanel` with a 2px accent ring, glow shadow, and smooth `scrollIntoView`. |
| **Parallel Tool Execution with Session Locking** | Independent evidence gathering tools and analyzers execute concurrently inside `collect` using `asyncio.gather(*tasks, return_exceptions=True)`. Access to `self.session` for cryptographic audit records is serialized via `session_lock = asyncio.Lock()`, eliminating connection state collisions while slashing node duration from ~4s to ~1s. |
| **Granular Intra-Node Streaming** | `tool_started`, `tool_completed`, `evidence_added`, `analyzer_started`, and `analyzer_completed` events publish immediately to Redis Pub/Sub as each tool/analyzer runs, providing live sub-second updates instead of batching until node exit. |
| **Deterministic Verification Gates** | Production readiness verified via **104 backend tests** (`pytest`, 86% coverage floor) and **28 frontend tests** (`node --experimental-strip-types --test`, sub-millisecond replay benchmarks). |

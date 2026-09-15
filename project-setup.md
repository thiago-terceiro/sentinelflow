SentinelFlow — Production-Ready AI Dispute Investigation Copilot

0. Mission

Build SentinelFlow as a production-style, AI-heavy dispute investigation system.

The core principle is:

LLMs perform the investigation and synthesis; deterministic services provide authoritative facts and policy calculations; human approval controls consequential outcomes.

The system should feel like an enterprise AI investigation platform rather than a chatbot.

The investigation itself must remain strongly LLM-driven. SentinelFlow should be able to:

inspect evidence through tools;

decide what evidence to request next;

compare contradictory evidence;

ask specialized analyzers for additional findings;

maintain an explicit investigation hypothesis;

identify missing evidence;

revise its assessment as new evidence arrives;

produce a structured recommendation with citations/evidence references;

explain why it reached that recommendation.

Additional analyzers may be added later. Their outputs become evidence summaries available to the investigator.

1. Architecture

                         ┌──────────────────────────┐
                         │      Next.js Console     │
                         │  Investigation Timeline   │
                         │ Evidence / Risk / HITL    │
                         └────────────┬─────────────┘
                                      │ HTTPS + SSE
                                      ▼
                         ┌──────────────────────────┐
                         │       FastAPI API         │
                         │ Auth / RBAC / Validation  │
                         │ SSE / Audit / Rate Limit  │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                 ┌─────────────────────────────────────────┐
                 │              LangGraph                   │
                 │                                         │
                 │  Intake → Investigator → Tools          │
                 │                 │                        │
                 │                 ├── Analyzer summaries   │
                 │                 │                        │
                 │                 ├── Evidence synthesis   │
                 │                 │                        │
                 │                 ├── Risk / Policy        │
                 │                 │                        │
                 │                 └── Human approval       │
                 │                          │                │
                 │                     interrupt()          │
                 └───────────────┬─────────────────────────┘
                                 │
          ┌──────────────────────┼─────────────────────────┐
          ▼                      ▼                         ▼
  ┌───────────────┐      ┌───────────────┐        ┌────────────────┐
  │ PostgreSQL    │      │ Analyzer APIs │        │ LLM Providers  │
  │ business data │      │ / sub-agents  │        │ model gateway  │
  │ audit/checkpt │      └───────────────┘        └────────────────┘
  └───────────────┘
                                 │
                                 ▼
                       ┌────────────────────┐
                       │ OpenTelemetry      │
                       │ Honeycomb /        │
                       │ LangSmith          │
                       └────────────────────┘

Use persistent LangGraph checkpointing. Human-in-the-loop must use LangGraph's native interrupt() / Command(resume=...) mechanism rather than a separate state-patching approval endpoint. LangGraph persistence is the mechanism that allows an interrupted graph to resume from its saved thread state. LangGraph interrupts and persistence.

2. Repository

sentinelflow/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   ├── telemetry.py
│   │   ├── errors.py
│   │   ├── schemas/
│   │   │   ├── disputes.py
│   │   │   ├── investigation.py
│   │   │   ├── approval.py
│   │   │   └── events.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   ├── disputes.py
│   │   │   ├── approvals.py
│   │   │   └── health.py
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   ├── graph.py
│   │   │   ├── nodes.py
│   │   │   ├── routing.py
│   │   │   └── prompts.py
│   │   ├── agents/
│   │   │   ├── investigator.py
│   │   │   ├── synthesizer.py
│   │   │   └── analyzers.py
│   │   ├── tools/
│   │   │   ├── transactions.py
│   │   │   ├── customer.py
│   │   │   ├── device.py
│   │   │   ├── merchant.py
│   │   │   ├── compliance.py
│   │   │   └── analyzer_results.py
│   │   ├── services/
│   │   │   ├── risk.py
│   │   │   ├── audit.py
│   │   │   └── model_gateway.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   ├── session.py
│   │   │   └── seed.py
│   │   └── tests/
│   │       ├── test_graph.py
│   │       ├── test_tools.py
│   │       ├── test_security.py
│   │       ├── test_hitl.py
│   │       └── test_api.py
│   └── migrations/
│
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.mjs
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── disputes/
│   │   │   └── [disputeId]/
│   │   │       └── page.tsx
│   │   └── error.tsx
│   ├── components/
│   │   ├── InvestigationConsole.tsx
│   │   ├── InvestigationTimeline.tsx
│   │   ├── EvidencePanel.tsx
│   │   ├── RiskPanel.tsx
│   │   ├── AnalyzerPanel.tsx
│   │   ├── ApprovalPanel.tsx
│   │   └── ErrorBoundary.tsx
│   ├── hooks/
│   │   └── useSentinelAgent.ts
│   ├── lib/
│   │   ├── api.ts
│   │   ├── sse.ts
│   │   └── types.ts
│   └── tests/
│       └── ...
│
├── docker-compose.yml
├── .env.example
├── README.md
└── Makefile

3. Configuration

Use Pydantic Settings and fail fast for required production configuration.

Never put secrets in source code.

Required configuration:

APP_ENV=development|test|production
API_HOST=0.0.0.0
API_PORT=8000

DATABASE_URL=postgresql+asyncpg://...
LANGGRAPH_CHECKPOINT_URL=postgresql://...

OPENAI_API_KEY=...
MODEL_NAME=...
MODEL_BASE_URL=...

OTEL_SERVICE_NAME=sentinelflow-agent-engine
OTEL_EXPORTER_OTLP_ENDPOINT=...
OTEL_EXPORTER_OTLP_HEADERS=...

AUTH_ISSUER=...
AUTH_AUDIENCE=...

Do not use os.getenv() as the primary Pydantic Settings mechanism.

Provide separate development and production defaults.

4. Authentication and authorization

Authentication is mandatory.

Every dispute endpoint must receive an authenticated principal.

Required roles:

investigator
senior_investigator
reviewer
admin

Approval permissions must be checked server-side.

The approval request must contain:

class ApprovalDecision(BaseModel):
    decision: Literal["approve", "deny"]
    comment: str = Field(min_length=1, max_length=4000)

The server obtains the approver identity from the authenticated principal. Never trust a client-provided approved_by.

An approval must record:

user ID;

role;

decision;

comment;

timestamp;

dispute ID;

investigation/thread ID;

risk score;

recommendation version;

evidence snapshot/checkpoint ID.

Replace wildcard CORS with an explicit allow-list.

Add:

request size limits;

rate limiting;

structured validation errors;

secure headers;

audit logging;

no sensitive data in ordinary application logs.

5. Domain model

Use strongly typed Pydantic models.

class Evidence(BaseModel):
    id: str
    source: str
    category: Literal[
        "transaction",
        "customer",
        "device",
        "network",
        "merchant",
        "compliance",
        "analyzer",
    ]
    summary: str
    facts: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    collected_at: datetime
    provenance: str

class RiskFactor(BaseModel):
    name: str
    score: float
    weight: float
    explanation: str
    evidence_ids: list[str]

class InvestigationHypothesis(BaseModel):
    statement: str
    confidence: float
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]

class InvestigationReport(BaseModel):
    conclusion: str
    recommendation: Literal[
        "approve",
        "deny",
        "escalate",
        "insufficient_evidence",
    ]
    confidence: float
    hypotheses: list[InvestigationHypothesis]
    risk_factors: list[RiskFactor]
    evidence_ids: list[str]
    unresolved_questions: list[str]
    compliance_findings: list[str]

The LLM must return structured objects conforming to these schemas.

6. AI investigation architecture

This is deliberately AI-heavy.

Do NOT replace the investigator with a fixed deterministic decision tree.

The investigator is an LLM agent with tools and state.

Its job is to:

understand the dispute;

formulate initial hypotheses;

identify information gaps;

select tools;

inspect returned evidence;

compare evidence against hypotheses;

request analyzer summaries;

challenge contradictory findings;

decide what to investigate next;

determine when evidence is sufficient;

produce a structured recommendation.

The graph should support iterative investigation:

START
  ↓
intake
  ↓
investigator
  ↓
tool / analyzer call ──────┐
  ↓                        │
evidence update             │
  ↓                        │
investigator ──────────────┘
  ↓
evidence synthesis
  ↓
risk assessment
  ↓
compliance assessment
  ↓
recommendation
  ↓
if high-impact → human approval interrupt
  ↓
finalize

The investigator must have a configurable maximum investigation budget:

maximum iterations;

maximum tool calls;

maximum analyzer calls;

maximum tokens;

maximum wall-clock duration.

If the budget is exhausted, the investigator must return insufficient_evidence or escalate, never fabricate certainty.

7. Analyzer architecture

The system should support additional specialized analyzers without making them the primary investigator.

Examples:

Transaction Analyzer
Device/Fingerprint Analyzer
Network/IP Analyzer
Merchant Analyzer
Customer History Analyzer
Fraud Pattern Analyzer
Compliance Analyzer
Anomaly Detector

Each analyzer returns a normalized AnalyzerSummary.

class AnalyzerSummary(BaseModel):
    analyzer: str
    summary: str
    findings: list[str]
    confidence: float
    evidence_ids: list[str]
    contradictions: list[str]
    recommended_followups: list[str]

The main investigator receives these summaries as evidence.

Important:

Analyzer output is evidence, not truth.

The investigator can:

accept it;

challenge it;

request additional evidence;

identify contradictions;

downgrade confidence.

This preserves the LLM investigation as the core intelligence layer.

8. Tool design

Every tool must:

have a precise typed input;

have a typed structured output;

validate authorization;

emit telemetry;

emit an audit event when appropriate;

include provenance;

never silently return fake data in production mode.

Development seed data is allowed, but it must be clearly identified.

Example:

@tool
async def fetch_transaction_history(
    dispute_id: str,
) -> TransactionHistory:
    ...

The tool should actually query PostgreSQL.

At minimum create realistic seeded entities:

customers;

disputes;

transactions;

merchants;

devices;

IP addresses;

prior disputes;

authorization events.

9. Risk engine

The LLM investigates.

The risk engine calculates.

Do not let the LLM invent the final numerical risk score.

The engine should combine structured factors such as:

transaction amount
device mismatch
IP velocity
customer history
merchant risk
transaction velocity
geographic anomaly
previous dispute history
analyzer findings

Return:

class RiskAssessment(BaseModel):
    score: float
    level: Literal["low", "medium", "high", "critical"]
    factors: list[RiskFactor]
    threshold_triggered: bool
    explanation: str

The LLM may explain and contextualize the risk assessment but must not rewrite the numerical score.

10. Compliance

Compliance checks must be deterministic and versioned.

class ComplianceFinding(BaseModel):
    framework: str
    rule_id: str
    passed: bool
    requires_review: bool
    explanation: str
    evidence_ids: list[str]
    policy_version: str

Do not hard-code a single:

amount > 1000

rule as the complete compliance system.

The initial project may implement a small explicit rule set, but rules must be represented as named/versioned policies and tested independently.

11. LangGraph state

Use a typed state model.

Conceptually:

class DisputeState(TypedDict):
    dispute_id: str
    thread_id: str

    messages: Annotated[list[BaseMessage], add_messages]

    evidence: list[Evidence]
    analyzer_summaries: list[AnalyzerSummary]

    hypotheses: list[InvestigationHypothesis]
    unresolved_questions: list[str]

    risk_assessment: RiskAssessment | None
    compliance_findings: list[ComplianceFinding]

    investigation_report: InvestigationReport | None

    iteration_count: int
    tool_call_count: int
    analyzer_call_count: int

    status: str

    approval_request: dict[str, Any] | None
    approval_decision: dict[str, Any] | None

Do not use an untyped collection of arbitrary JSON as the primary state.

12. Native human-in-the-loop

When approval is required, pause inside the graph:

from langgraph.types import interrupt, Command

decision = interrupt({
    "type": "human_approval",
    "dispute_id": state["dispute_id"],
    "recommendation": state["investigation_report"],
    "risk": state["risk_assessment"],
    "evidence": state["evidence"],
})

Resume using:

graph.invoke(
    Command(resume=decision),
    config=config,
)

The API layer should expose a resume operation, but it must resume the persisted graph rather than patching arbitrary state.

Use a durable PostgreSQL checkpointer in production.

The approval process must survive:

API restart;

worker restart;

deployment;

temporary database/API failure.

13. Persistence

Use PostgreSQL for:

application/domain data;

audit records;

LangGraph checkpoints.

Use AsyncPostgresSaver or the current supported PostgreSQL checkpointer for production.

Use an in-memory checkpointer only in tests/local experiments.

Persist every investigation thread.

Never derive a thread ID solely from a mutable UI field.

Use a server-generated investigation ID/thread ID and associate it with the authenticated user and dispute.

14. Streaming

Use SSE for the UI.

Define a stable event envelope:

class StreamEvent(BaseModel):
    id: str
    type: Literal[
        "run_started",
        "agent_message",
        "tool_started",
        "tool_completed",
        "evidence_added",
        "analyzer_completed",
        "risk_updated",
        "approval_required",
        "run_completed",
        "run_failed",
        "heartbeat",
    ]
    timestamp: datetime
    data: dict[str, Any]

Never stream arbitrary internal Python objects.

Never stream secrets.

Never expose hidden chain-of-thought.

The UI should receive:

concise agent updates;

tool activity;

evidence summaries;

analyzer findings;

final reasoning/explanation;

structured recommendation.

Do not expose private chain-of-thought or raw hidden reasoning traces.

15. Observability

OpenTelemetry must cover:

HTTP request
  └── investigation run
       ├── LangGraph node
       ├── LLM call
       ├── tool call
       ├── analyzer call
       ├── database query
       ├── risk calculation
       ├── compliance evaluation
       └── human approval

Attach correlation attributes:

dispute_id;

investigation_id;

thread_id;

user_id where policy permits;

graph_node;

tool_name;

analyzer_name;

model_name;

latency;

token counts;

success/failure;

risk level.

Do not place raw card numbers, authentication secrets, or unnecessary PII into telemetry.

Add structured logs with consistent event names.

Add:

metrics;

latency histograms;

error counters;

LLM usage metrics;

tool failure metrics;

investigation completion metrics;

approval latency metrics.

16. Reliability

Every external dependency must have bounded failure behavior.

Implement:

request timeouts;

model timeouts;

tool timeouts;

analyzer timeouts;

bounded retries;

exponential backoff where appropriate;

circuit-breaking/failure isolation where useful;

cancellation propagation.

Do not retry non-idempotent operations blindly.

If an analyzer fails, the investigator should receive:

Analyzer unavailable: <name>

and continue if enough evidence remains.

If critical evidence cannot be obtained, the investigator must downgrade confidence and potentially escalate.

17. LLM gateway

Do not instantiate the model directly throughout the application.

Create:

services/model_gateway.py

Responsibilities:

model selection;

structured output;

retries;

timeouts;

token accounting;

model metadata;

provider abstraction;

fallback policy.

Keep model configuration external.

The investigator should support configurable models.

18. Prompt architecture

Separate prompts from graph code.

Required prompts:

investigator_system
investigator_iteration
evidence_synthesis
final_recommendation
analyzer_interpretation

The investigator system prompt should explicitly enforce:

use tools before claiming facts;

distinguish observed facts from inference;

cite evidence IDs;

consider contradictory evidence;

identify uncertainty;

do not fabricate unavailable information;

use analyzer summaries as evidence;

request additional evidence when necessary;

never override deterministic risk/compliance outputs;

never approve a case merely because an LLM is confident.

19. Frontend

The frontend should be an operations console.

Main layout:

┌───────────────────────────────────────────────────────┐
│ SentinelFlow                    Investigation #SF-123 │
├──────────────────┬────────────────────────────────────┤
│ Investigation    │ Evidence                           │
│ Timeline         │ ┌────────────────────────────────┐ │
│                  │ │ Transaction                    │ │
│ ● Started        │ │ Device                         │ │
│ ● Transaction    │ │ Network                        │ │
│ ● Device         │ │ Analyzer findings              │ │
│ ● Analyzer       │ └────────────────────────────────┘ │
│ ● Risk           │                                    │
│ ● Recommendation │ Risk                               │
│                  │ ███████████ 85 HIGH                │
├──────────────────┴────────────────────────────────────┤
│ Human Approval                                        │
│ Recommendation: Escalate                             │
│ [Approve]                         [Deny]              │
└───────────────────────────────────────────────────────┘

The UI must support:

loading;

reconnect;

stream errors;

empty state;

retry;

completed state;

interrupted state;

approval state;

failed state.

Do not hard-code a dispute ID or API URL in components.

Use environment configuration.

20. Frontend TypeScript

Enable strict TypeScript.

Define state explicitly:

const initialState: DisputeState = {
  tokens: "",
  toolLogs: [],
  evidence: [],
  analyzerSummaries: [],
  riskAssessment: null,
  status: "IDLE",
  requiresApproval: false,
  isStreaming: false,
};

Every tool invocation must have a unique callId.

Never match tool completion events using only the tool name.

Correct:

toolLogs.map(log =>
  log.callId === event.callId
    ? { ...log, status: "completed", output: event.output }
    : log
)

21. Next.js

Use Next.js 16 App Router.

Use the current stable React Compiler configuration for the selected Next.js release rather than copying an older experimental configuration.

Keep:

Server Components for server-rendered UI/data;

Client Components only where interactivity is required;

typed API boundaries;

error boundaries;

loading UI;

route-level failure handling.

Keep the frontend compatible with the current Active LTS release rather than pinning unnecessarily old patch versions.

22. Testing

Minimum test matrix:

Unit tests

risk engine;

compliance rules;

schemas;

prompt rendering;

tool authorization;

state transitions.

Graph tests

normal investigation;

multiple tool calls;

repeated tool calls;

contradictory evidence;

analyzer failure;

max iteration limit;

human interrupt;

human approval;

human denial;

resume after restart.

API tests

unauthenticated request;

unauthorized approval;

valid investigator access;

valid reviewer approval;

invalid dispute ID;

malformed SSE;

dependency timeout.

Frontend tests

event parsing;

duplicate tool names;

reconnect;

approval flow;

failed stream;

empty evidence;

completed investigation.

Evaluation tests

Create a dataset of representative disputes and evaluate:

factual grounding;

evidence citation;

tool selection;

investigation completeness;

hallucination rate;

recommendation consistency;

risk explanation quality.

23. AI evaluation

This project should demonstrate serious AI engineering, not merely framework usage.

Create an evaluation harness.

For each case record:

input dispute
available evidence
expected evidence
expected risk factors
expected compliance findings
acceptable recommendation
ground-truth outcome

Evaluate the investigator on:

correct evidence retrieval;

unnecessary tool calls;

missed evidence;

contradictory evidence handling;

unsupported claims;

confidence calibration;

final recommendation.

Track evaluations across model/prompt versions.

24. Security model

Never expose:

API keys;

internal database errors;

raw stack traces;

hidden prompts;

hidden chain-of-thought;

full sensitive transaction data in the browser unless authorized.

Every access to a dispute should be authorization-checked.

Every consequential action should be audited.

Every approval should be attributable to an authenticated human.

25. Seed data

Replace the original hardcoded tool output with a realistic seed database.

Seed several cases:

Case A — obvious fraud

high transaction amount;

unknown device;

high IP velocity;

suspicious geographic movement;

previous fraud signals.

Case B — legitimate high-value purchase

recognized device;

normal IP;

long customer history;

no previous disputes.

Case C — ambiguous

conflicting device/network evidence;

analyzer disagreement;

insufficient evidence.

Case D — analyzer failure

one analyzer unavailable;

investigator must continue with remaining evidence.

Case E — contradictory analyzer

two analyzers disagree;

investigator must explicitly identify the conflict.

The demo should make the AI investigation visibly different across cases.

26. API

Required endpoints:

POST /api/v1/disputes/{dispute_id}/investigations
GET  /api/v1/investigations/{investigation_id}
GET  /api/v1/investigations/{investigation_id}/stream
POST /api/v1/investigations/{investigation_id}/resume
GET  /api/v1/investigations/{investigation_id}/evidence
GET  /api/v1/investigations/{investigation_id}/audit
GET  /api/v1/health
GET  /api/v1/ready

Approval is a graph resume operation, not an arbitrary state mutation.

27. Error contract

All API errors use a consistent format:

{
  "error": {
    "code": "INVESTIGATION_NOT_FOUND",
    "message": "Investigation was not found.",
    "request_id": "req_123"
  }
}

Never expose implementation details to clients.

28. Development commands

Backend:

cd sentinelflow/backend

uv sync
uv run alembic upgrade head
uv run python -m app.db.seed
uv run pytest
uv run uvicorn app.main:app --reload --port 8000

Frontend:

cd sentinelflow/frontend

pnpm install
pnpm dev
pnpm test
pnpm build
pnpm start

Full stack:

docker compose up --build

29. Docker services

Development compose should include:

frontend
backend
postgres
otel collector (optional)

Do not include real production credentials in Docker Compose.

30. Definition of done

The project is complete only when:

all Python and TypeScript files compile;

no placeholder/truncated JSX remains;

strict TypeScript passes;

backend tests pass;

frontend tests pass;

authentication is enforced;

approval authorization is enforced;

CORS is restricted;

PostgreSQL persistence works;

LangGraph checkpoints survive backend restart;

HITL uses native interrupt() / Command(resume=...);

investigation remains LLM-driven;

tools use realistic database data;

analyzer summaries can be injected into the investigation;

risk calculation is deterministic and structured;

compliance rules are versioned and tested;

SSE events are typed and robust;

tool calls use unique IDs;

errors are handled;

retries/timeouts are bounded;

OpenTelemetry traces cover the investigation;

audit records exist for consequential actions;

no hidden chain-of-thought is exposed;

evaluation cases exist;

README explains architecture and tradeoffs;

the entire system can be started locally from documented commands.

31. Portfolio objective

SentinelFlow should demonstrate the following engineering capabilities:

AI

tool-using LLM agents;

iterative investigation;

structured outputs;

evidence-grounded reasoning;

multi-analyzer orchestration;

model abstraction;

evaluation;

uncertainty handling.

Agent infrastructure

LangGraph state machines;

persistent checkpoints;

interrupt/resume;

streaming;

fault tolerance;

observability.

Backend

FastAPI;

PostgreSQL;

async Python;

authentication;

RBAC;

audit logging;

API contracts.

Frontend

Next.js 16;

React;

TypeScript strict mode;

streaming UX;

operational dashboards;

resilient client state.

Production engineering

Docker;

tests;

telemetry;

retries;

timeouts;

security;

CI/CD readiness.

The final result should look like a small but credible enterprise AI platform, not a toy chatbot.

32. Important implementation rule

Do not "simplify away" the AI investigation to make the workflow easier.

The investigator should remain the central intelligence layer.

The correct separation is:

LLM = investigator / hypothesis generation / evidence interpretation / synthesis

Tools = authoritative evidence retrieval

Analyzers = specialized evidence producers

Risk engine = authoritative numerical risk calculation

Compliance engine = authoritative policy evaluation

Human = final authority for consequential decisions

LangGraph = durable orchestration and state

This gives SentinelFlow a deliberately AI-heavy architecture while keeping the system auditable, testable and safe enough to resemble a real enterprise implementation.
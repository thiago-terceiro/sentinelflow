# SentinelFlow & SentinelPulse Workspace

Welcome to the **SentinelFlow & SentinelPulse** distributed systems workspace.

> [!NOTE]
> **Zero-Cost Architectural Constraint:** This project is deliberately built under a 100% free, open-source, and locally runnable constraint. All CI checks, static analysis (SonarJS, Ruff, Mypy), security audits, ML engines (ONNX Runtime CPU), and agent evaluation suites execute with zero paid SaaS dependencies.

---

### Core Systems Included

1. **📡 SentinelPulse: High-Throughput Real-Time SMS Fraud & Spam Intelligence Gateway**
   - **Target Role:** Traffic Intelligence & Communications ML (Tier-1 Telecom / Global CPaaS Messaging Infrastructure).
   - **Inference Latency & Boundaries:** Architectural target is synchronous inline ingress (`<15ms p95 end-to-end HTTP` target, `<0.1ms` warm in-graph ONNX C++ execution on short SMS) via compiled in-graph `TfidfVectorizer + CalibratedClassifierCV (LogisticRegression)` pipeline on AVX-512 CPU (measured raw ONNX runtime latency is **0.032ms** / 32 µs on short SMS; zero GPU dependency). *Boundary & Evidence Status (`SF-015` 2,000-character maximum input contract):* Both `AI-18` `evaluate_heuristics()` (`p95 <= 3.477 ms`) and Boundary A internal `_process_single_message()` (`latency_ms`: `p95 = 1.937–2.129 ms` in-process agg / `1.748–3.725 ms` loopback in `e12734d`; `6.254–7.128 ms` agg / `5.488–8.815 ms` loopback in `cb64ff2`) pass `<15ms` locally. However, the **end-to-end HTTP `<15ms` target is NOT ESTABLISHED**: under identical harness boundaries, local loopback `concurrency=1` HTTP p95 passed in the `e12734d` run (`6.228–7.633 ms`) after exceeding 15 ms in the `cb64ff2` run (`17.259–17.793 ms`), while shared-event-loop `concurrency=4` (`25.280–26.094 ms` in `e12734d`; `60.852–61.257 ms` in `cb64ff2`) and `concurrency=8` (`54.984–63.106 ms` in `e12734d`; `121.061–124.160 ms` in `cb64ff2`) exceed 15 ms and mix FastAPI/Pydantic/post-timer `JsonFormatter` overhead with single-process queuing. Live Redis server network RTT and independent-process multi-worker concurrency remain **UNVERIFIED**.
   - **Velocity Counters:** High-throughput sliding-window Redis sorted set aggregation (10s, 60s, 1h) using non-transactional single round-trip pipelines with 30s in-memory deque fail-open fallback.
   - **MLOps & Active Learning:** Kolmogorov-Smirnov (KS) two-sample test (feature drift) and Population Stability Index (PSI, prediction drift) paired with asynchronous escalation of ambiguous `FLAG` (`0.40–0.75`) disputes into SentinelFlow for human-in-the-loop ground-truth labeling.
   - **Load Testing & Simulation:** Locust load-testing suite configured for 1,000–5,000 RPS and standalone telecom traffic generator.
   - **Full-Stack Live Dashboard:** Next.js console with real-time SSE streaming, live throughput gauge, color-coded latency percentiles, and interactive SMS tester.
   - **System Design Deep Dive:** [SYSTEM_DESIGN.md](./sentinelflow/SYSTEM_DESIGN.md) covers 100k RPS Kafka partitioning, dynamic batching, cold-start elimination, non-transactional pipelining, and fail-open degraded service fallbacks.

2. **⚡ SentinelFlow: Autonomous Dispute Investigation & Cryptographic Audit Ledger**
   - **Architecture:** Human-in-the-loop LangGraph workflow with deterministic compliance/risk services, parallel `asyncio.gather` tool sessions, token-by-token `reasoning_delta` streaming, client-side time-travel state scrubbing (`?step=`), semantic iteration diffs (`?diff=1`), sticky cross-panel citation pinning (`?evidence=`), and PostgreSQL persistence.
   - **Security & Compliance:** 100% PASS on OWASP Top 10, LLM Top 10, Bandit, Gitleaks, pip-audit, and cryptographic SHA-256 tamper-evident ledgers.

---

### Directory Map

- 📖 **Product Documentation & Architecture**: [sentinelflow/README.md](./sentinelflow/README.md) and [docs/architecture.md](./docs/architecture.md)
- 📐 **System Design (100k RPS Scale)**: [sentinelflow/SYSTEM_DESIGN.md](./sentinelflow/SYSTEM_DESIGN.md)
- ⚙️ **Backend (FastAPI + ONNX Runtime + Redis + LangGraph)**: [sentinelflow/backend](./sentinelflow/backend)
- 💻 **Frontend (Next.js 16 + React 19 + TypeScript + Tailwind)**: [sentinelflow/frontend](./sentinelflow/frontend)
- 🛰️ **Traffic Simulator & Locust Load Suite**: [sentinelflow/ops](./sentinelflow/ops)
- 🚀 **Validation Suite & CI Workflows**: [.github/scripts/validate-sentinelflow.sh](./.github/scripts/validate-sentinelflow.sh) and [.github/workflows/ci.yml](./.github/workflows/ci.yml)

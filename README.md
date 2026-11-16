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
   - **MLOps Drift Telemetry & Escalation Review:** Kolmogorov-Smirnov (KS) two-sample test (feature drift) and Population Stability Index (PSI, prediction drift) paired with asynchronous escalation of ambiguous `FLAG` (`0.40–0.75`) disputes into SentinelFlow for human-in-the-loop review (`interrupt()`). Model retraining remains manual/offline via `train_onnx_model.py` (automated closed-loop active-learning retraining is future enterprise scope).
   - **Load Testing & Simulation:** Locust load-testing suite configured for 1,000–5,000 RPS and standalone telecom traffic generator (dev/simulation tooling).
   - **Full-Stack Live Dashboard:** Next.js console with real-time SSE streaming, live throughput gauge, color-coded latency percentiles, and interactive SMS tester.
   - **System Design Deep Dive:** [SYSTEM_DESIGN.md](./sentinelflow/SYSTEM_DESIGN.md) covers implemented gateway internals alongside future enterprise scaling designs (100k RPS Kafka partitioning, multi-node Redis Cluster slot compatibility).

## System Capability & Readiness Matrix

| Readiness Tier | Components & Capabilities |
| :--- | :--- |
| **Implemented & Verified in Repo** | `<1ms` ONNX CPU inference (`sms_fraud_model.onnx`, `d330466e...`, single-thread pinned `SessionOptions`); patched `skl2onnx` `<1e-6` parity (`max_prob_abs_diff = 1.04e-07`, `400/400` verdict parity); continuous gated composite scoring (monotonic non-decreasing, 13 linear-time regex heuristics + Cyrillic mixed-script homoglyph normalization); standalone Redis (`redis:7-alpine`) ZSET sliding-window velocity + 30s in-memory deque fail-open circuit breaker; pre-inference/logging PII redaction (`redact_sms_pii`, 128-bit versioned HMAC pseudonyms, 2,000-char contract); 3-tier evaluation governance (`OOF CV N=703` across 56 families, `Dev/Val N=400`, `Quarantined Class C Holdout: UNAVAILABLE / BLOCKED` with `UCI #228` `N=5,574` quarantined separately); LangGraph multi-agent triage workbench (`interrupt()`), `arq` worker, SHA-256 append-only audit ledger, Next.js 16 console. |
| **Simulated / Benchmarked in Dev** | In-process `httpx.ASGITransport` microbenchmarks & local loopback Uvicorn 2,000-char benchmarks (`scripts/benchmark_pulse.py`, `scripts/bench_telecom_classify_2000.py`: Boundary A internal passes `<15ms` locally; Boundary B end-to-end HTTP `<15ms` target is **NOT ESTABLISHED**; live Redis RTT and multi-worker load are unverified); synthetic + public-advisory SMS corpora (`Train N=703`, `Dev/Val N=400`, `SF-013` perturbation suite `N=70`); Locust & `telecom_simulator.py` traffic generation; heuristic fallback / mock LLM mode in dev & CI (`app.evals.run`). |
| **Future Production / Enterprise Scope (Not Implemented)** | Live carrier SS7 / Diameter / SMPP / optical-tap ingestion (`Class D` telemetry: `0` records in repo); multi-node Redis Cluster state synchronization & distributed Kafka event bus (`telecom.sms.inbound`); automated closed-loop active-learning retraining pipelines (retraining is manual/offline via `train_onnx_model.py`). |

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

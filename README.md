# SentinelFlow & SentinelPulse Workspace

Welcome to the **SentinelFlow & SentinelPulse** distributed systems workspace.

> [!NOTE]
> **Zero-Cost Architectural Constraint:** This project is deliberately built under a 100% free, open-source, and locally runnable constraint. All CI checks, static analysis (SonarJS, Ruff, Mypy), security audits, ML engines (ONNX Runtime CPU), and agent evaluation suites execute with zero paid SaaS dependencies.

---

### Core Systems Included

1. **📡 SentinelPulse: High-Throughput Real-Time SMS Fraud & Spam Intelligence Gateway**
   - **Target Role:** Traffic Intelligence & Communications ML (Tier-1 Telecom / Global CPaaS Messaging Infrastructure).
   - **Inference SLA:** Sub-15ms p95 latency on CPU; actual raw ONNX runtime latency is **0.032ms** (32 µs).
   - **Velocity Counters:** High-throughput sliding-window Redis sorted set aggregation (10s, 60s, 1h) with single round-trip pipelines.
   - **MLOps:** Kolmogorov-Smirnov (KS) two-sample test and Population Stability Index (PSI) online distribution drift detection.
   - **Load Testing & Simulation:** Locust load-testing suite configured for 1,000–5,000 RPS and standalone telecom traffic generator.
   - **Full-Stack Live Dashboard:** Next.js console with real-time SSE streaming, live throughput gauge, color-coded latency percentiles, and interactive SMS tester.
   - **System Design Deep Dive:** [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md) covers 100k RPS Kafka partitioning, dynamic batching, cold-start elimination, and fail-open degraded service fallbacks.

2. **⚡ SentinelFlow: Autonomous Dispute Investigation & Cryptographic Audit Ledger**
   - **Architecture:** Human-in-the-loop LangGraph workflow with deterministic compliance/risk services and PostgreSQL persistence.
   - **Security & Compliance:** 100% PASS on OWASP Top 10, LLM Top 10, Bandit, Gitleaks, pip-audit, and cryptographic SHA-256 tamper-evident ledgers.

---

### Directory Map

- 📖 **Product Documentation & Architecture**: [sentinelflow/README.md](./sentinelflow/README.md)
- 📐 **System Design (100k RPS Scale)**: [SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md)
- ⚙️ **Backend (FastAPI + ONNX Runtime + Redis + LangGraph)**: [sentinelflow/backend](./sentinelflow/backend)
- 💻 **Frontend (Next.js 16 + React 19 + TypeScript + Tailwind)**: [sentinelflow/frontend](./sentinelflow/frontend)
- 🛰️ **Traffic Simulator & Locust Load Suite**: [sentinelflow/ops](./sentinelflow/ops)
- 🚀 **Validation Suite & CI Workflows**: [.github/scripts/validate-sentinelflow.sh](./.github/scripts/validate-sentinelflow.sh) and [.github/workflows/ci.yml](./.github/workflows/ci.yml)

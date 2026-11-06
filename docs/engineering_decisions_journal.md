# SentinelPulse & SentinelFlow: Engineering Decisions & Incident Journal

> **Document Purpose:** This journal records the key engineering dilemmas, critical incidents, forensic audit findings, and architectural resolutions across SentinelPulse and SentinelFlow. It serves as an unvarnished technical chronicle of real systems and ML engineering trade-offs.

---

## Index of Engineering Decisions

1. [ED-01: Exact-Hash Separation vs. Template-Family Group Splitting (Data Leakage)](#ed-01-exact-hash-separation-vs-template-family-group-splitting)
2. [ED-02: Production Runtime vs. Evaluation Heuristic Scoring Parity](#ed-02-production-runtime-vs-evaluation-heuristic-scoring-parity)
3. [ED-03: Monotonic vs. Non-Monotonic Composite Scoring Formulations](#ed-03-monotonic-vs-non-monotonic-composite-scoring-formulations)
4. [ED-04: In-Process ASGI Benchmarks vs. Real Multi-Worker OS Deployment](#ed-04-in-process-asgi-benchmarks-vs-real-multi-worker-os-deployment)
5. [ED-05: In-Graph Platt Scaling ONNX Compilation & Numerical Parity](#ed-05-in-graph-platt-scaling-onnx-compilation--numerical-parity)
6. [ED-06: Redis Standalone Pipelining vs. Cross-Slot Redis Cluster Compatibility](#ed-06-redis-standalone-pipelining-vs-cross-slot-redis-cluster-compatibility)
7. [ED-07: Sliding-Window Velocity Fallback & Multi-Worker State Isolation](#ed-07-sliding-window-velocity-fallback--multi-worker-state-isolation)
8. [ED-08: Human-in-the-Loop Steering Revision Budgets in LangGraph](#ed-08-human-in-the-loop-steering-revision-budgets-in-langgraph)
9. [ED-09: Cryptographic Audit Ledger Concurrency & Per-Investigation Session Locks](#ed-09-cryptographic-audit-ledger-concurrency--per-investigation-session-locks)
10. [ED-10: Pre-Inference PII Sanitization & PCI-DSS 6+4 Masking Boundary](#ed-10-pre-inference-pii-sanitization--pci-dss-64-masking-boundary)

---

### ED-01: Exact-Hash Separation vs. Template-Family Group Splitting
- **Classification:** `MID-LEVEL / SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** A model evaluated on independently generated SMS templates achieved an unrealistically high validation score (ROC-AUC `0.9989`). Investigation revealed template-family leakage: although exact normalized text strings were unique, slight variations of the same template (e.g. changing an amount from `$35` to `$47`) existed in both training and validation folds.
- **Original Assumption:** Deduplicating using normalized SHA-256 string hashes (`hashlib.sha256(normalize(t)).hexdigest()`) was assumed to guarantee zero train/test leakage.
- **Forensic Evidence:** Group overlap analysis showed fold 0 validation contained 28 template families that shared lexical skeletons with training samples.
- **Solution Implemented:**
  1. Clustered all 484 training samples into 149 distinct `template_family` groups in `train_onnx_model.py`.
  2. Applied `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` ensuring `groups_train.isdisjoint(groups_val) == True`.
  3. Created an independent, 400-sample out-of-distribution held-out evaluation set (`evaluate_model.py`) with zero normalized SHA-256 collisions against the entire training corpus.
- **Alternatives Considered:** Random K-fold splitting (rejected due to severe template leakage); Leave-One-Group-Out (rejected due to high training cost across 149 groups).
- **Trade-offs:** Out-of-distribution ROC-AUC dropped from an artificial `0.9989` to a realistic, robust `0.9722`.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/train_onnx_model.py`
  - `sentinelflow/backend/app/telecom/evaluate_model.py`
  - `test_template_family_group_leakage_prevention()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Exact-string deduplication is necessary but insufficient in NLP. Template clustering or semantic group splitting is mandatory to evaluate genuine model generalization.

---

### ED-02: Production Runtime vs. Evaluation Heuristic Scoring Parity
- **Classification:** `MID-LEVEL`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** The evaluation suite reported different risk scores and classification decisions than the live gateway API for identical messages.
- **Original Assumption:** Runtime inference engine in `onnx_engine.py` and evaluation script in `evaluate_model.py` implemented parallel copies of heuristic evaluation functions.
- **Forensic Evidence:** When a new heuristic rule (`RULE:SIM_SWAP_OR_KYC_SCAM`) was added to `onnx_engine.py`, `evaluate_model.py` lacked the rule, causing a score discrepancy of 0.70 on SIM-swap phishing lures.
- **Solution Implemented:**
  - Extracted `evaluate_heuristics(text: str) -> tuple[float, list[str]]` as the single authoritative function in `onnx_engine.py`.
  - Both runtime `OnnxInferenceEngine.predict()` and `evaluate_model.py` import and call this exact function.
  - Compound rule escalation ($+0.12$ boost when $\ge 2$ high-confidence rules match) is centralized.
- **Alternatives Considered:** Separate configuration files for rules (rejected to keep regex compilation and zero-allocation runtime simple).
- **Trade-offs:** None. Code deduplication guaranteed 100% parity.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/onnx_engine.py`
  - `test_production_runtime_vs_evaluation_scoring_parity()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Never duplicate feature engineering or scoring logic between runtime inference and offline evaluation pipelines. Maintain a single source of truth.

---

### ED-03: Monotonic vs. Non-Monotonic Composite Scoring Formulations
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** In early prototypes, combining the ML model probability $P$ and regex heuristic score $H$ via an unconstrained weighted average caused score inversions: increasing a suspicious heuristic score could paradoxically lower the composite score if model confidence was moderate.
- **Original Assumption:** Linear combination $S = w_1 P + w_2 H$ was assumed sufficient.
- **Forensic Evidence:** Grid sweep identified regions where $\frac{\partial S}{\partial H} < 0$, violating expected risk monotonicity.
- **Solution Implemented:**
  - Designed a continuous gated blend with an authoritative override:
    $$\alpha(P, H) = \text{clip}\left(\frac{\max(P - 0.15, H - 0.30)}{0.25}, 0.0, 1.0\right)$$
    $$S_{\text{content}} = P + \alpha(P, H) \cdot W_H \cdot (1 - P)$$
    $$S_{\text{composite}} = S_{\text{content}} + V \cdot (1 - S_{\text{content}})$$
  - High-risk heuristic override: $H \ge 0.80 \implies S_{\text{composite}} = 1.0$.
  - Proved strictly monotonic non-decreasing: $\frac{\partial S}{\partial P} \ge 0, \frac{\partial S}{\partial H} \ge 0, \frac{\partial S}{\partial V} \ge 0$.
- **Alternatives Considered:** Multiplicative dampening (caused false negatives on shortlinks); Hard rule overrides everywhere (brittle and overrode subtle ML patterns).
- **Trade-offs:** Slight formula complexity in exchange for mathematical guarantee of safety.
- **Relevant Files & Tests:**
  - `compute_composite_score()` in `sentinelflow/backend/app/telecom/onnx_engine.py`
  - `test_composite_scoring_monotonic_non_decreasing_property()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Multi-factor scoring systems must be tested for partial derivative monotonicity across their entire input hyperspace.

---

### ED-04: In-Process ASGI Benchmarks vs. Real Multi-Worker OS Deployment
- **Classification:** `STAFF/ADVANCED`
- **Status:** `Remediated & Documented Accurately`
- **The Problem Encountered:** Architecture documentation claimed SentinelPulse achieved `1,500+ req/s` on a single server, but real measurements in early tests showed around `190 req/s`.
- **Original Assumption:** In-process async benchmarks using `httpx.ASGITransport` on a single event loop were conflated with multi-process production deployments.
- **Forensic Evidence:** Running `benchmark_pulse.py` revealed that while server execution time is $< 0.8\text{ ms}$, Python asyncio single-thread task scheduling bottlenecks at ~191.7 req/s at concurrency 8.
- **Solution Implemented:**
  - Documented benchmark harness explicitly as an **in-process ASGI micro-benchmark** measuring server core execution time without network overhead.
  - Clarified that high throughput (1,000+ req/s) requires multi-worker Uvicorn processes (`uvicorn app.main:app --workers 8`) behind Nginx.
- **Alternatives Considered:** Running automated multi-process locust clusters during unit testing (rejected due to CI/CD overhead and port collision risks).
- **Trade-offs:** Transparent benchmarking avoids marketing numbers in favor of reproducible engineering facts.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/scripts/benchmark_pulse.py`
  - `docs/ml_evaluation_report.md`
- **Lessons Learned:** Always decouple server-side algorithmic latency from transport scheduling and network I/O in performance claims.

---

### ED-05: In-Graph Platt Scaling ONNX Compilation & Numerical Parity
- **Classification:** `MID-LEVEL / SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Does the exported ONNX model include actual Platt calibration parameters, or does it merely output raw Logistic Regression sigmoid values?
- **Original Assumption:** Relying on standard `skl2onnx` export might omit calibration folds or require custom runtime scaling code.
- **Forensic Evidence:** Inspected ONNX graph nodes 9 to 55 in `sms_fraud_model.onnx`. Verified that `skl2onnx` compiled all 5 cross-validation estimators from `CalibratedClassifierCV`, including `Mul`, `Add`, `Exp`, `Div`, and `Sum` nodes that compute the ensemble calibrated probability in-graph.
- **Solution Implemented:**
  - Verified numerical parity between `scikit-learn` `predict_proba()` and `ONNX Runtime` `session.run()`: maximum absolute delta is $3.99 \times 10^{-8}$ (floating-point epsilon).
- **Alternatives Considered:** Python-side Platt scaling after raw ONNX output (rejected to preserve self-contained model deployment).
- **Trade-offs:** Model size increased slightly to 181 KB to encapsulate 5 linear folds, but execution time remains $< 0.2\text{ ms}$ on CPU.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/train_onnx_model.py`
  - `test_calibrated_classifier_cv_platt_parity()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Compiling preprocessing and probability calibration directly into the ONNX graph eliminates runtime drift between training code and production microservices.

---

### ED-06: Redis Standalone Pipelining vs. Cross-Slot Redis Cluster Compatibility
- **Classification:** `STAFF/ADVANCED`
- **Status:** `Remediated & Documented Accurately`
- **The Problem Encountered:** The velocity store tracks sender frequency across 10s, 60s, and 3600s sliding windows, as well as IP, domain, and prefix dimensions. Claims of seamless "Redis Cluster" pipelining were technically inaccurate.
- **Original Assumption:** Pipelining all keys in a single command block would work in Redis Cluster.
- **Forensic Evidence:** Sender keys use `{sender_hash}` slot tags, but IP keys use `{ip_hash}` and domain keys use `{domain_hash}`. In Redis Cluster, multi-key pipelines across different hash slots raise `CROSSSLOT Keys in request don't hash to the same slot`.
- **Solution Implemented:**
  - Corrected documentation to state SentinelPulse runs on **standalone Redis** (`redis:7-alpine`) via Docker Compose where 1-RTT pipelining executes atomically.
  - Clarified that in Redis Cluster, pipelines must be partitioned by slot tag.
- **Alternatives Considered:** Prefixing all keys with a global hash tag (rejected because it forces all Redis traffic onto a single cluster node, defeating clustering).
- **Trade-offs:** Standalone Redis is simpler and faster (<2ms SLA) for current scale.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/velocity_store.py`
  - `AUDIT_REPORT.md` Section 5.2
- **Lessons Learned:** Understand Redis hash slot mechanics before making horizontal clustering claims.

---

### ED-07: Sliding-Window Velocity Fallback & Multi-Worker State Isolation
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** What happens to telecom ingress if Redis experiences a network partition, timeout, or crash?
- **Original Assumption:** Catching exceptions was assumed to be enough.
- **Forensic Evidence:** A 15ms socket timeout without a circuit breaker would stall every subsequent telecom request for 15ms, exhausting the ingress SLA.
- **Solution Implemented:**
  - Implemented a 30-second circuit breaker cooldown in `VelocityStore`.
  - On timeout or failure, the store trips open, immediately routing requests to local in-memory sliding-window deques for 30 seconds.
  - Multi-worker trade-off: In a deployment with $W$ workers, each worker maintains isolated memory deques, multiplying effective rate limits by $W$ during outages.
- **Alternatives Considered:** Fail-closed / Drop traffic (rejected as unacceptable for telecom SMS delivery); Blocking retry loops (rejected as SLA violation).
- **Trade-offs:** Temporary rate limit tolerance increase during Redis downtime in exchange for zero downtime and sub-millisecond response.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/velocity_store.py`
  - `test_chaos_redis_socket_timeout_circuit_breaker()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** In synchronous telecom gateways, fail-open with local isolation is preferable to cascading latency failures.

---

### ED-08: Human-in-the-Loop Steering Revision Budgets in LangGraph
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** When human investigators rejected or requested revisions on a dispute investigation, the agent graph could enter infinite loops or exhaust iteration budgets without incorporating reviewer steering.
- **Original Assumption:** Graph routing loops would terminate naturally.
- **Forensic Evidence:** Forensic Red Team cycle discovered that requesting revision after `iteration_count >= 3` caused `route_after_investigator` to immediately finalize, ignoring guidance.
- **Solution Implemented:**
  - Added `reviewer_guidance: str | None` and `revision_count: int` to state schema.
  - Dynamically scaled iteration budget: `max_iterations = (revisions + 1) * MAX_ITERATIONS`.
  - Enforced a hard ceiling of `MAX_REVISION_CYCLES = 3`.
  - Ephemeral steering: guidance is consumed into the prompt and explicitly reset to `None` in the state delta.
- **Alternatives Considered:** Unbounded revision loops (rejected due to token expenditure and DoS risk).
- **Trade-offs:** Reviewers have up to 3 revision cycles before forced escalation.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/graph/routing.py`
  - `sentinelflow/backend/app/graph/nodes.py`
  - `sentinelflow/backend/app/graph/state.py`
- **Lessons Learned:** Human-in-the-loop steering in agentic graphs requires explicit state lifecycle and cycle budgeting.

---

### ED-09: Cryptographic Audit Ledger Concurrency & Per-Investigation Session Locks
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Concurrently executing evidence-gathering tools simultaneously called `record_audit_event()`. Because `_next_sequence_and_prev_hash` read the latest row concurrently, both observed the same parent hash, leading to unique constraint violations and hash tree forks.
- **Original Assumption:** Database row insertions were assumed serial.
- **Forensic Evidence:** Concurrent test executions produced duplicate sequence numbers and broken SHA-256 parent links.
- **Solution Implemented:**
  - Introduced `_investigation_audit_locks: dict[str, asyncio.Lock]`.
  - Sequence number calculation, deterministic JSON canonicalization (`sort_keys=True, default=str`), and parent hash linking are strictly serialized per investigation.
- **Alternatives Considered:** Global application lock (rejected because it blocks unrelated investigations across other disputes).
- **Trade-offs:** Minor lock acquisition overhead (<0.01ms) with zero cross-dispute contention.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/services/audit.py`
  - `sentinelflow/backend/app/tests/test_audit_integrity.py`
- **Lessons Learned:** Cryptographic append-only ledgers require serialized locking at the partition or thread level to prevent hash tree forks.

---

### ED-10: Pre-Inference PII Sanitization & PCI-DSS 6+4 Masking Boundary
- **Classification:** `MID-LEVEL`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Customer disputes and telecom messages contained raw credit card numbers, SSNs, phone numbers, and API tokens. Sending these raw strings to upstream LLMs violated PCI-DSS, GDPR, and SOC2.
- **Original Assumption:** LLMs could be instructed via system prompts not to output or leak PII.
- **Forensic Evidence:** System prompts failed to prevent raw tokens from entering upstream provider logs and prompt caching layers.
- **Solution Implemented:**
  - Implemented pre-inference sanitization in `services/trace_safety.py`:
    - Credit card PANs: Preserved standard 6+4 BIN format (e.g. `411111******1111`) for fraud analysis while redacting middle digits.
    - SSNs, IBANs, emails, phone numbers, and bearer tokens: Replaced with explicit typed markers (`[REDACTED_SSN]`, `[REDACTED_TOKEN]`).
- **Alternatives Considered:** Complete removal of PANs (rejected because card brand and last 4 digits are vital for dispute evidence).
- **Trade-offs:** Minimal regex latency (<0.05ms) before LLM prompt construction.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/services/trace_safety.py`
  - `sentinelflow/backend/app/tests/test_trace_safety.py`
- **Lessons Learned:** Never rely on LLM system prompts for data security; enforce deterministic regex masking before prompts leave your network boundary.

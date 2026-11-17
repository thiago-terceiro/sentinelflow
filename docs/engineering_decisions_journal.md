# SentinelPulse & SentinelFlow: Engineering Decisions & Incident Journal

> **Document Purpose:** This journal records the key engineering dilemmas, critical incidents, forensic audit findings, and architectural resolutions across SentinelPulse and SentinelFlow. It serves as an unvarnished technical chronicle of real systems and ML engineering trade-offs.

> **Project Note — Generalization Beyond Familiar Synthetic Families:** A model that performs beautifully on familiar synthetic families but struggles with a previously unseen legitimate bank-alert family has not solved the generalization problem. Explaining that weakness is good engineering; actually reducing it without introducing other failures is better.

---

## Index of Engineering Decisions

1. [ED-01: Exact-Hash Separation vs. Template-Family Group Splitting & Dev/Val Provenance](#ed-01-exact-hash-separation-vs-template-family-group-splitting--devval-provenance)
2. [ED-02: Production Runtime vs. Evaluation Heuristic Scoring Parity](#ed-02-production-runtime-vs-evaluation-heuristic-scoring-parity)
3. [ED-03: Monotonic vs. Non-Monotonic Composite Scoring Formulations](#ed-03-monotonic-vs-non-monotonic-composite-scoring-formulations)
4. [ED-04: In-Process ASGI Benchmarks vs. Real Multi-Worker OS Deployment](#ed-04-in-process-asgi-benchmarks-vs-real-multi-worker-os-deployment)
5. [ED-05: In-Graph Platt Scaling ONNX Compilation & 400-Row Verdict Parity](#ed-05-in-graph-platt-scaling-onnx-compilation--400-row-verdict-parity)
6. [ED-06: Redis Standalone Pipelining vs. Cross-Slot Redis Cluster Compatibility](#ed-06-redis-standalone-pipelining-vs-cross-slot-redis-cluster-compatibility)
7. [ED-07: Sliding-Window Velocity Fallback & Multi-Worker State Isolation](#ed-07-sliding-window-velocity-fallback--multi-worker-state-isolation)
8. [ED-08: Human-in-the-Loop Steering Revision Budgets in LangGraph](#ed-08-human-in-the-loop-steering-revision-budgets-in-langgraph)
9. [ED-09: Cryptographic Audit Ledger Concurrency & Per-Investigation Session Locks](#ed-09-cryptographic-audit-ledger-concurrency--per-investigation-session-locks)
10. [ED-10: Pre-Inference PII Sanitization & PCI-DSS 6+4 Masking Boundary](#ed-10-pre-inference-pii-sanitization--pci-dss-64-masking-boundary)
11. [ED-11: Patching Upstream skl2onnx TF-IDF Bugs & 12 Adversarial Edge-Case Idempotency (SF-002)](#ed-11-patching-upstream-skl2onnx-tf-idf-bugs--12-adversarial-edge-case-idempotency-sf-002)
12. [ED-12: Clean-Process ONNX Export Determinism & Runtime SHA-256 Verification (SF-003)](#ed-12-clean-process-onnx-export-determinism--runtime-sha-256-verification-sf-003)
13. [ED-13: Locked Converter-Sensitive ML Dependencies & Docker Container Locale Fix](#ed-13-locked-converter-sensitive-ml-dependencies--docker-container-locale-fix)
14. [ED-14: Non-Finite Signal Clamping, H=0.65 Boundary Proof & 25+ Case Degraded Matrix (SF-004)](#ed-14-non-finite-signal-clamping-h065-boundary-proof--25-case-degraded-matrix-sf-004)
15. [ED-15: Window Cache Registry + sessionStorage Fallback for Dispute List Hydration](#ed-15-window-cache-registry--sessionstorage-fallback-for-dispute-list-hydration)
16. [ED-16: Multi-Viewport, Multi-Theme WCAG 2.2 AAA Contrast & Pre-Push Verification Gate](#ed-16-multi-viewport-multi-theme-wcag-22-aaa-contrast--pre-push-verification-gate)
17. [ED-17: Coercive Extortion Lookaheads, O(N) vs O(N^2) ReDoS Bounds & Cross-Artifact Invariants (SF-005 / SF-005B)](#ed-17-coercive-extortion-lookaheads-on-vs-on2-redos-bounds--cross-artifact-invariants-sf-005--sf-005b)
18. [ED-18: Broadening URL-Free A2P 2FA/OTP Training Cohort Phrasing for Sample 93 (SF-006)](#ed-18-broadening-url-free-a2p-2faotp-training-cohort-phrasing-for-sample-93-sf-006)
19. [ED-19: 3-Tier Family-Impersonation Operational Policy Separating Casual, Ambiguous P2P & Actionable Lures (SF-007)](#ed-19-3-tier-family-impersonation-operational-policy-separating-casual-ambiguous-p2p--actionable-lures-sf-007)
20. [ED-20: Full Base-Seed Semantic Grouping (56 Families), dataset_inventory.json & Lexical Similarity Audit (SF-008)](#ed-20-full-base-seed-semantic-grouping-56-families-dataset_inventoryjson--lexical-similarity-audit-sf-008)
21. [ED-21: Zero-Leakage Nested 5-Fold OOF CV, 10-Bin ECE, Wilson vs. Cluster Bootstrap CIs & Macro Sensitivity (SF-009)](#ed-21-zero-leakage-nested-5-fold-oof-cv-10-bin-ece-wilson-vs-cluster-bootstrap-cis--macro-sensitivity-sf-009)
22. [ED-22: External Dataset Provenance Governance, Confounding Audit & Class C Holdout Block (SF-010 / SF-011)](#ed-22-external-dataset-provenance-governance-confounding-audit--class-c-holdout-block-sf-010--sf-011)
23. [ED-23: Bayes Base-Rate PPV Collapse, Group Error Concentration & Conditional Cost Sensitivity (SF-012 / SF-012R.1)](#ed-23-bayes-base-rate-ppv-collapse-group-error-concentration--conditional-cost-sensitivity-sf-012--sf-012r1)
24. [ED-24: Mixed-Script Cyrillic Homoglyph Defense, Atomic ReDoS Fix & Substring Prefilters (SF-013)](#ed-24-mixed-script-cyrillic-homoglyph-defense-atomic-redos-fix--substring-prefilters-sf-013)
25. [ED-25: Fail-Closed ONNX Thread Pinning & `/v1/health` Redis Degraded-Mode Telemetry (SF-014)](#ed-25-fail-closed-onnx-thread-pinning--v1health-redis-degraded-mode-telemetry-sf-014)
26. [ED-26: Synchronous SMS PII Redaction, 128-Bit HMAC Pseudonymization & Boundary A vs B Latency Truth (SF-015)](#ed-26-synchronous-sms-pii-redaction-128-bit-hmac-pseudonymization--boundary-a-vs-b-latency-truth-sf-015)

---

### ED-01: Exact-Hash Separation vs. Template-Family Group Splitting & Dev/Val Provenance
- **Classification:** `MID-LEVEL / SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Early cross-validation reported an unrealistically high ROC-AUC (`0.9989`), and the 400-sample benchmark was treated as an untouched "external holdout." Deeper inspection revealed two issues: (1) over-fine per-sample family IDs allowed template variants (different dollar amounts, URLs, bank/courier names) to leak across CV folds, and (2) the 400-sample suite had been inspected during rule/threshold tuning.
- **Original Assumption:** Normalized SHA-256 string deduplication (`hashlib.sha256(normalize(t))`) was assumed sufficient to prevent train/validation leakage, and zero-hash overlap was conflated with a single-shot external holdout.
- **Forensic Evidence:** Replacing over-fine hashes with semantic family normalization (`extract_template_family_id` stripping URLs, amounts, ref IDs, phone numbers, banks, and brands) plus `explicit_family` labels revealed that honest Fold 0 `StratifiedGroupKFold(5)` validation (`N = 151`, 120 legit / 31 fraud) scores **ROC-AUC `0.7427`**, **PR-AUC `0.5420`**, **F1 `0.3934`**, **Brier `0.1573`** (a stark drop from `0.9989`!), proving true OOD generalization on a small synthetic corpus is much harder than within-template generalization.
- **Solution Implemented:**
  1. Consolidated training samples under deterministic semantic template families via `extract_template_family_id()` + `explicit_family` in `train_onnx_model.py`, enforcing strict disjointness across all 5 `StratifiedGroupKFold` folds.
  2. Re-classified the 400-sample suite (`evaluate_model.py`, `docs/ml_evaluation_report.md`) honestly as an **Empirical Development & Validation Benchmark (`Dev/Val N=400`)** rather than a single-use external holdout.
  3. Specified a 3-control governance architecture for production external test sets (`SF-010`, currently In Progress) and expanded semantic family grouping + nested OOF diagnostics across all 703 training samples (`ED-20`, `ED-21`).
- **Alternatives Considered:** Random K-fold splitting (rejected due to severe template leakage); Leave-One-Group-Out (rejected due to high compute cost).
- **Trade-offs:** Exposed realistic initial Fold 0 CV limitations (`0.7427` ROC-AUC prior to `SF-008`/`SF-009`), driving full 56-family mapping and zero-leakage nested OOF evaluation (`0.9559` pooled OOF ROC-AUC).
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/train_onnx_model.py` (`extract_template_family_id`, `build_augmented_dataset`)
  - `sentinelflow/backend/app/telecom/evaluate_model.py`, `docs/ml_evaluation_report.md`
  - `test_template_family_grouping_cross_validation_disjointness()`, `test_template_family_group_leakage_prevention()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Exact-string deduplication does not prevent template leakage, and a benchmark inspected during development is a *validation* set—never call it an untouched holdout.

---

### ED-02: Production Runtime vs. Evaluation Heuristic Scoring Parity
- **Classification:** `MID-LEVEL`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** The evaluation script and production API yielded different risk scores on the same message because regex rules were maintained in two separate files.
- **Original Assumption:** Maintaining parallel heuristic helper functions in `evaluate_model.py` and `onnx_engine.py` would stay in sync manually.
- **Forensic Evidence:** Adding `RULE:SIM_SWAP_OR_KYC_SCAM` to the gateway caused a 0.70 score discrepancy during evaluation runs.
- **Solution Implemented:** Extracted `evaluate_heuristics(text: str) -> tuple[float, list[str]]` into `onnx_engine.py` as the single authoritative function invoked by both live inference and evaluation.
- **Alternatives Considered:** Separate YAML/JSON rules config (rejected to keep regex pre-compilation simple and allocation-free).
- **Trade-offs:** None. Guaranteed 100% parity across production and evaluation.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/onnx_engine.py`, `test_production_runtime_vs_evaluation_scoring_parity()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Never duplicate feature extraction or heuristic scoring logic between runtime inference and offline evaluation pipelines.

---

### ED-03: Monotonic vs. Non-Monotonic Composite Scoring Formulations
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Linear weighted averaging (`S = w1*P + w2*H`) allowed suspicious heuristic signals to be diluted by moderate ML probabilities, causing score inversions.
- **Original Assumption:** A standard weighted sum was assumed to behave safely across `[0, 1]^3`.
- **Forensic Evidence:** Grid sweeps found regions where $\frac{\partial S}{\partial H} < 0$, and early documentation inaccurately described the formula as "strictly monotonic" rather than "monotonic non-decreasing" (since the $H \ge 0.80 \implies S = 1.0$ plateau has zero derivative).
- **Solution Implemented:** Designed the continuous gated blend (`alpha(P, H)`) + Noisy-OR velocity scaling (`S_content + V * (1 - S_content)`) + authoritative override (`H >= 0.80 -> 1.0`), verified across 51-step grid sweeps and documented precisely as **monotonic non-decreasing**.
- **Alternatives Considered:** Multiplicative dampening (caused false negatives on shortlinks); hard overrides everywhere (brittle).
- **Trade-offs:** Non-linear gating requires explicit boundary unit tests to understand exact escalation thresholds (see `ED-14`).
- **Relevant Files & Tests:** `compute_composite_score()` in `onnx_engine.py`, `test_composite_scoring_monotonic_non_decreasing_property()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Multi-factor scoring systems must be tested for partial derivative monotonicity across their entire input hyperspace.

---

### ED-04: In-Process ASGI Benchmarks vs. Real Multi-Worker OS Deployment
- **Classification:** `STAFF/ADVANCED`
- **Status:** `Remediated & Documented Accurately`
- **The Problem Encountered:** Architecture documentation claimed `1,500+ req/s` on a single server, while empirical measurements on a single event loop plateaued near `190 req/s`.
- **Original Assumption:** In-process async benchmarks (`httpx.ASGITransport`) were conflated with multi-process OS deployments.
- **Forensic Evidence:** `benchmark_pulse.py` isolated pure server execution (`< 0.8 ms`) from Python single-event-loop scheduling (~191.7 req/s at concurrency 8).
- **Solution Implemented:** Explicitly labeled the harness as an in-process ASGI micro-benchmark and documented multi-worker Uvicorn scaling behind Nginx for >1,000 req/s production throughput.
- **Alternatives Considered:** Spinning up multi-worker Locust clusters during CI unit tests (rejected due to CI overhead and port collisions).
- **Trade-offs:** Transparent benchmarking replaces marketing numbers with reproducible engineering baselines.
- **Relevant Files & Tests:** `sentinelflow/backend/scripts/benchmark_pulse.py`, `docs/ml_evaluation_report.md`
- **Lessons Learned:** Always decouple algorithmic server latency from event-loop scheduling and socket I/O in performance claims.

---

### ED-05: In-Graph Platt Scaling ONNX Compilation & 400-Row Verdict Parity
- **Classification:** `MID-LEVEL / SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Standard `skl2onnx` export needed proof that 5-fold Platt scaling compiled inside the ONNX graph and matched scikit-learn end-to-end across all 400 benchmark messages.
- **Original Assumption:** Exporting `CalibratedClassifierCV` with `skl2onnx` was assumed to preserve exact probabilities and operational verdicts (`ALLOW`/`FLAG`/`BLOCK`).
- **Forensic Evidence:** After fixing `skl2onnx` TF-IDF bugs (`ED-11`) and re-benchmarking all 400 rows in `c06f112` (and subsequent `SF-006`/`SF-007`/`SF-009` exports), full parity was recorded in `benchmark_predictions_400.json`:
  - Max TF-IDF vector diff: `6.03e-08` (originally `7.37e-08` in `c06f112`)
  - Max calibrated probability diff ($|P_{\text{sklearn}} - P_{\text{onnx}}|$): `1.04e-07` (mean `2.09e-08`; originally `1.45e-07` / `2.31e-08`)
  - Operational verdict agreement (`ALLOW` / `FLAG` / `BLOCK`): **`400 / 400` (`100.0%`)**
- **Solution Implemented:** Automated per-row scikit-learn vs. ONNX Runtime parity export (`benchmark_predictions_400.json`, latest SHA-256 `66dc4862...`) directly inside `evaluate_model.py` and `train_onnx_model.py`.
- **Alternatives Considered:** Running Python post-processing outside ONNX (rejected to keep inference single-session and sub-millisecond).
- **Trade-offs:** Artifact size is 194.85 KB (`199,525 bytes`) to hold 5 linear folds in-graph, executing in `< 0.2 ms` on CPU.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/evaluate_model.py`, `benchmark_predictions_400.json`, `test_calibrated_classifier_cv_platt_parity()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Always verify numerical *and* operational verdict parity across the full evaluation dataset—never rely on 2 smoke examples.

---

### ED-06: Redis Standalone Pipelining vs. Cross-Slot Redis Cluster Compatibility
- **Classification:** `STAFF/ADVANCED`
- **Status:** `Remediated & Documented Accurately`
- **The Problem Encountered:** Claims of seamless "Redis Cluster" pipelining were technically inaccurate because sender (`{sender_hash}`), IP (`{ip_hash}`), and domain (`{domain_hash}`) keys hash to different slots.
- **Original Assumption:** Pipelining heterogeneous keys in one batch would execute in Redis Cluster.
- **Forensic Evidence:** Multi-key pipelines across distinct hash tags raise `CROSSSLOT` errors in Redis Cluster.
- **Solution Implemented:** Corrected docs to state SentinelPulse deploys standalone Redis (`redis:7-alpine`) via Docker Compose where 1-RTT pipelining executes atomically, and documented cluster slot partitioning requirements for future scaling.
- **Alternatives Considered:** Global hash tag on all keys (rejected because it bottlenecks all traffic on a single shard).
- **Trade-offs:** Standalone Redis is simpler and stays within the `< 2 ms` budget at current scale.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/velocity_store.py`, `AUDIT_REPORT.md` Section 5.2
- **Lessons Learned:** Understand Redis hash-slot routing before making horizontal clustering claims.

---

### ED-07: Sliding-Window Velocity Fallback & Multi-Worker State Isolation
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** A 15ms Redis socket timeout without a circuit breaker stalls every synchronous telecom request, exhausting the ingress SLA.
- **Original Assumption:** Catching Redis exceptions per call was assumed sufficient.
- **Forensic Evidence:** Repeated timeouts incur 15ms latency per message; additionally, in multi-worker Uvicorn deployments, per-worker in-memory deques isolate state across processes.
- **Solution Implemented:** Implemented a 30-second circuit breaker cooldown in `RedisVelocityStore` failing open to bounded in-memory `collections.deque` sliding windows, and explicitly tested the multi-worker degraded counter isolation trade-off.
- **Alternatives Considered:** Fail-closed / drop SMS traffic (unacceptable for carriers); synchronous retries (violates 15ms SLA).
- **Trade-offs:** During Redis outages with $W$ workers, each worker sees $N/W$ traffic until Redis recovers.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/velocity_store.py`, `test_chaos_redis_socket_timeout_circuit_breaker()`, `test_chaos_multi_worker_degraded_counter_isolation()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Synchronous gateways should fail open with bounded local state and explicitly document degraded multi-worker semantics.

---

### ED-08: Human-in-the-Loop Steering Revision Budgets in LangGraph
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Human `request_revision` steering could either silently skip investigation if `iteration_count >= 3` or loop indefinitely, and old `reviewer_guidance` persisted across subsequent turns ("zombie instruction leakage").
- **Original Assumption:** Fixed `iteration_count` limits and persistent state fields were assumed safe.
- **Forensic Evidence:** Forensic Red Team audit revealed starvation after 3 iterations and stale steering persistence.
- **Solution Implemented:** Added `reviewer_guidance` and `revision_count` to `DisputeState`, scaled budget (`(revisions + 1) * INVESTIGATION_MAX_ITERATIONS`), capped `MAX_REVISION_CYCLES = 3`, and cleared `reviewer_guidance = None` after consumption.
- **Alternatives Considered:** Unbounded revision loops (rejected due to token exhaustion / DoS).
- **Trade-offs:** Hard cap of 3 human revision cycles before mandatory escalation.
- **Relevant Files & Tests:** `sentinelflow/backend/app/graph/routing.py`, `nodes.py`, `state.py`
- **Lessons Learned:** Human steering directives in stateful agent graphs must have explicit budgets and single-turn consumption lifecycles.

---

### ED-09: Cryptographic Audit Ledger Concurrency & Per-Investigation Session Locks
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Concurrent `collect()` tool coroutines called `record_audit_event()` simultaneously, reading identical sequence numbers and parent hashes and causing unique constraint violations or hash-chain forks.
- **Original Assumption:** Async DB operations within one investigation were assumed ordered.
- **Forensic Evidence:** Parallel tool tests produced duplicate `(investigation_id, sequence_no)` keys and non-deterministic `datetime` JSON serialization mismatches.
- **Solution Implemented:** Added per-investigation `_investigation_audit_locks: dict[str, asyncio.Lock]` and deterministic canonical hashing (`json.dumps(..., sort_keys=True, default=str)`).
- **Alternatives Considered:** Global application lock (rejected due to cross-investigation contention).
- **Trade-offs:** Negligible per-thread lock overhead (`< 0.01 ms`) with zero cross-dispute blocking.
- **Relevant Files & Tests:** `sentinelflow/backend/app/services/audit.py`, `app/tests/test_audit_integrity.py`
- **Lessons Learned:** Hash-chained append-only ledgers require strict per-stream serialization and canonical JSON serialization.

---

### ED-10: Pre-Inference PII Sanitization & PCI-DSS 6+4 Masking Boundary
- **Classification:** `MID-LEVEL`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Customer disputes contained raw credit card PANs, SSNs, IBANs, emails, and bearer tokens that could leak into upstream LLM prompts and logs.
- **Original Assumption:** Instructing LLMs via system prompts not to repeat PII was insufficient.
- **Forensic Evidence:** Prompt payloads still transmitted raw identifiers outside the trust boundary.
- **Solution Implemented:** Enforced deterministic regex redaction in `app.services.trace_safety` prior to LLM prompt construction (preserving 6+4 BIN digits for card fraud checks and masking SSNs/tokens with typed tags), paired with Fernet-encrypted vault storage for authorized auditors.
- **Alternatives Considered:** Stripping card numbers completely (rejected because BIN/last-4 matching is needed by dispute tools).
- **Trade-offs:** Adds `< 0.05 ms` deterministic regex overhead before LLM calls.
- **Relevant Files & Tests:** `sentinelflow/backend/app/services/trace_safety.py`, `app/tests/test_trace_safety.py`
- **Lessons Learned:** Security boundaries must be enforced deterministically in code before prompts leave your infrastructure.

---

### ED-11: Patching Upstream `skl2onnx` TF-IDF Bugs & 12 Adversarial Edge-Case Idempotency (`SF-002`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Exporting `TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, max_features=2500)` via `skl2onnx 1.20.0` produced silent numerical divergence from scikit-learn on multi-word messages and repeated tokens.
- **Original Assumption:** `skl2onnx.to_onnx()` was assumed to translate scikit-learn's `TfidfVectorizer` faithfully.
- **Forensic Evidence:** Graph inspection revealed two upstream converter bugs:
  1. **Dead-Bigram Vocabulary Splitting Bug (`_intelligent_split`)**: When `max_features=2500` pruned a unigram (e.g. `windows`) while keeping a bigram (e.g. `on windows`), `skl2onnx` misclassified 136 bigrams as 1-grams containing embedded spaces inside `pool_strings`, making them unreachable after tokenization.
  2. **Sublinear TF Formula Inversion Bug**: `skl2onnx` exported `sublinear_tf=True` as `Add(tf, 1.0) -> Log` (computing $\ln(\text{tf} + 1)$) instead of scikit-learn's $1 + \ln(\text{tf})$ for $\text{tf} > 0$, distorting L2-normalized vectors whenever any token repeated ($\text{tf} \ge 2$).
- **Solution Implemented:**
  - Switched `TfidfVectorizer` to explicit ASCII `token_pattern=r'\b[a-zA-Z0-9_]+\b'` and implemented `patch_skl2onnx_tfidf_bugs()` in `train_onnx_model.py`: rebuilds `TfIdfVectorizer` `pool_strings`/`ngram_counts`/`ngram_indexes` cleanly, and replaces `Add -> Log` with `Max(tf, 1.0) -> Log -> Add(1.0) -> Where(tf > 0, ..., 0.0)`.
  - In `SF-002` (`d79277b`), hardened the patch with structural precondition assertions (`RuntimeError` on corrupted/missing nodes), **strict byte-for-byte idempotency** (`bytes_once == bytes_twice`), and a 12-category adversarial parity test (empty strings, whitespace/punctuation, pure OOV, 1-char tokens, emojis/Unicode, Cyrillic homoglyphs, high-TF unigrams `urgent * 50`, dead bigrams `on windows * 25`, dense bigrams, 10k-token inputs, control chars, decimals/currency).
- **Alternatives Considered:** Re-implementing TF-IDF in Python outside ONNX (rejected—destroys `< 0.2 ms` single-session CPU execution and adds Python/ONNX drift).
- **Trade-offs:** Patching relies on `skl2onnx`'s exact emitted node names (`Add(output, ones) -> Log(plus1)`), requiring strict dependency pinning (`ED-13`).
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/train_onnx_model.py` (`patch_skl2onnx_tfidf_bugs`)
  - `test_onnx_patch_adversarial_edge_cases_and_idempotency()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Never trust an ONNX converter without testing TF-IDF vector parity on repeated tokens, pruned bigrams, OOV, and empty inputs.

---

### ED-12: Clean-Process ONNX Export Determinism & Runtime SHA-256 Verification (`SF-003`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Exporting the exact same model across separate Python processes could produce slightly different protobuf bytes (breaking reproducible artifact hashes), and `OnnxInferenceEngine` loaded `.onnx` files at startup without verifying binary integrity against metadata.
- **Original Assumption:** Deterministic `random_state=42` alone was assumed to produce identical `.onnx` files across clean subprocesses.
- **Forensic Evidence:** Unsorted `opset_import` iteration depended on Python hash/set order across subprocesses; runtime loading trusted any binary at `model_path` without checking `sms_fraud_metadata.json`.
- **Solution Implemented (`42fc7c6`):**
  1. Canonicalized `onnx_model.opset_import` sorting by `(domain, version)` inside `patch_skl2onnx_tfidf_bugs()`.
  2. Added `OnnxInferenceEngine._verify_model_integrity()` and `model_sha256` property in `onnx_engine.py`, raising `RuntimeError` if computed SHA-256 mismatches `sms_fraud_metadata.json` (`verify_sha256=True` by default).
  3. Added clean-subprocess verification test spawning independent `PYTHONHASHSEED` processes and checking byte-for-byte hash equality against disk.
- **Alternatives Considered:** Skipping runtime hash checks for speed (rejected—SHA-256 of 199 KB takes `< 1 ms` once at startup).
- **Trade-offs:** Model retraining/export must always regenerate `sms_fraud_metadata.json` alongside `sms_fraud_model.onnx`, or startup verification intentionally fails closed.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/onnx_engine.py` (`_verify_model_integrity`, `model_sha256`)
  - `sentinelflow/backend/app/telecom/train_onnx_model.py`
  - `test_onnx_export_reproducibility_and_runtime_sha256_validation()` in `app/tests/test_telecom_eval_suite.py`
- **Lessons Learned:** Reproducible ML requires both deterministic build-time serialization and cryptographic verification at serving startup.

---

### ED-13: Locked Converter-Sensitive ML Dependencies & Docker Container Locale Fix
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Two production-environment discrepancies surfaced: (1) floating semver ranges (`>=1.16.0,<2.0.0`) could pull newer `skl2onnx`/`scikit-learn` versions that alter ONNX graph node names and break `patch_skl2onnx_tfidf_bugs`, and (2) `python:3.12-slim` Docker images lacked `en_US.UTF-8` locale definitions required for ONNX Runtime string tokenization/normalization initialization.
- **Original Assumption:** `uv sync` without `--locked` and minimal Debian `python:3.12-slim` images without `locales` were assumed sufficient for ONNX serving.
- **Forensic Evidence:** Converter-sensitive graph patching inspects exact intermediate tensor names (`output`, `ones`, `plus1`), and ONNX Runtime threw locale initialization issues in minimal Linux containers lacking `en_US.UTF-8`.
- **Solution Implemented (`dc3fd58`, `cef7b12`):**
  1. Exact-pinned `scikit-learn==1.9.1`, `skl2onnx==1.20.0`, `onnx==1.23.2`, `onnxruntime==1.31.0` (and bounded `numpy`/`scipy`) in `pyproject.toml` and `uv.lock`.
  2. Enforced `uv sync --locked` in CI, `validate-sentinelflow.sh`, `Dockerfile`, and `uv lock --check` in `pre-push-verify.mjs`.
  3. Installed `locales` + generated `en_US.UTF-8` (`LANG`/`LC_ALL`) inside `sentinelflow/backend/Dockerfile`, and wrapped `close_redis_pool()` teardown safely in `services/investigations.py`.
- **Alternatives Considered:** Leaving dependency ranges open and dynamically discovering ONNX nodes (rejected—fragile and non-deterministic).
- **Trade-offs:** Upgrading ML converter packages requires an intentional lockfile bump, re-export, and full 400-row + 12-case adversarial parity validation.
- **Relevant Files & Tests:** `sentinelflow/backend/pyproject.toml`, `uv.lock`, `Dockerfile`, `.github/workflows/ci.yml`, `pre-push-verify.mjs`
- **Lessons Learned:** ML serving reproducibility extends from Python lockfiles all the way down to OS C-library locales inside slim Docker images.

---

### ED-14: Non-Finite Signal Clamping, H=0.65 Boundary Proof & 25+ Case Degraded Matrix (`SF-004`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Edge cases around `H = 0.65` (such as `RULE:FAMILY_IMPERSONATION_MESSAGING_LURE`), exact 4-decimal rounding near `0.40` / `0.75`, non-finite floats (`NaN`, `±inf`), and unreachable Redis during `/v1/classify` needed airtight mathematical and E2E boundary coverage.
- **Original Assumption:** `max(0.0, min(1.0, float(val)))` was assumed to clamp any float safely; in Python, `max(0.0, min(1.0, float('nan')))` silently returns `NaN`!
- **Forensic Evidence:** In IEEE-754 Python comparisons, any comparison with `NaN` is `False`, so `max/min` propagates `NaN` right through `compute_composite_score()`! Additionally, analytical evaluation proved $H = 0.65, P = 0.0, V = 0.0$ yields $S_{\text{composite}} = 0.3325 < 0.40$ (`ALLOW`), requiring baseline ML suspicion $P \ge 0.1012$ to reach Tier 1 `FLAG`.
- **Solution Implemented (`51ae602`, `f002c6d`):**
  1. Added `_clamp_unit_signal()` in `onnx_engine.py` explicitly mapping `NaN` and `-inf` to `0.0` and `+inf` to `1.0`.
  2. Documented the exact analytical derivation for $H = 0.65$ ($P \ge 0.1012$) in `onnx_engine.py` and `docs/ml_evaluation_report.md`.
  3. Added 25+ parametrized boundary cases (`test_composite_scoring_decision_matrix`), compound heuristic escalation tests (`test_evaluate_heuristics_compound_escalation_matrix`), and async `/v1/classify` 4-decimal rounding (`0.3999` vs `0.4000`, `0.7499` vs `0.7500`) + dead-Redis fail-open E2E matrix in `test_telecom_gateway.py`.
- **Alternatives Considered:** Raising exceptions on `NaN` (rejected—in synchronous telecom ingress, sanitizing degraded upstream inputs safely is preferable to 500 crashes).
- **Trade-offs:** Silent `NaN -> 0.0` clamping prevents crashes; upstream anomaly logging remains responsible for alerting on faulty signal sources.
- **Relevant Files & Tests:**
  - `sentinelflow/backend/app/telecom/onnx_engine.py` (`_clamp_unit_signal`, `compute_composite_score`)
  - `test_composite_scoring_decision_matrix()`, `test_evaluate_heuristics_compound_escalation_matrix()`, `test_mathematical_monotonicity_and_h065_derivation()` in `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Python's `min`/`max` do NOT clamp `NaN`—always guard numeric risk boundaries explicitly with `math.isnan()` and `math.isinf()`.

---

### ED-15: Window Cache Registry + `sessionStorage` Fallback for Dispute List Hydration
- **Classification:** `MID-LEVEL`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Navigating between `/disputes` and `/disputes/[disputeId]` triggered redundant API fetches, while relying solely on `sessionStorage` or module-level state caused cold-hydration mismatches or test flakes across client navigations.
- **Original Assumption:** Standard `sessionStorage` caching or transient React state was assumed sufficient for instant zero-flicker navigation.
- **Forensic Evidence:** E2E warm-cache assertions (`visual-regression.spec.ts`) exposed redundant network calls and storage serialization edge cases.
- **Solution Implemented (`76d3bd1`, `abb5ff3`, `aa018a1`, `7df7672`):** Implemented a deterministic window cache registry paired with robust `sessionStorage` fallback in `disputesCache.ts`, verified by exact warm fetch-count invariants in Playwright and unit tests.
- **Alternatives Considered:** Pulling in TanStack Query / SWR (rejected to keep frontend dependencies minimal and deterministic).
- **Trade-offs:** Explicit cache invalidation on mutation (dispute creation/approval/reset) must remain synchronized.
- **Relevant Files & Tests:** `sentinelflow/frontend/lib/disputesCache.ts`, `tests/disputes-cache.test.js`, `e2e/visual-regression.spec.ts`
- **Lessons Learned:** Window-scoped registry + `sessionStorage` fallback delivers zero-flicker hydration without external state-fetching libraries.

---

### ED-16: Multi-Viewport, Multi-Theme WCAG 2.2 AAA Contrast & Pre-Push Verification Gate
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Dark-mode accent colors failed WCAG 2.2 Level AAA 7.0:1 contrast checks when paired with light foregrounds (`#ffffff`), and isolated desktop audits missed mobile layout overflows and interactive drawer/modal accessibility violations.
- **Original Assumption:** Testing light-mode desktop views in isolation was assumed representative of full UI compliance.
- **Forensic Evidence:** Automated Axe-Core AAA audits (`test-a11y-aaa.mjs`) flagged dark-mode contrast ratios and interactive panel states.
- **Solution Implemented (`eab1b19`, `bf03435`, `20a8fa9`):**
  1. Defined high-contrast dark-mode CSS tokens (`--accent: #bfdbfe`, `--accent-ink: #090d16`, `--success: #86efac`, `--badge-*-bg/color`) in `globals.css`.
  2. Upgraded `test-a11y-aaa.mjs` and `pre-push-verify.mjs` to audit Desktop (`1440x900`) and Mobile (`375x812`) across both `light` and `dark` themes, alongside Playwright visual regression and `uv lock --check`.
- **Alternatives Considered:** Manual spot checks or WCAG AA (`4.5:1`) relaxation (rejected by project AAA mandates).
- **Trade-offs:** Stricter pre-push gate runtime (~15–30s when local server is up) in exchange for zero visual or accessibility regressions.
- **Relevant Files & Tests:** `sentinelflow/frontend/app/globals.css`, `scripts/test-a11y-aaa.mjs`, `scripts/pre-push-verify.mjs`, `e2e/visual-regression.spec.ts`
- **Lessons Learned:** Always pair `--accent` backgrounds with semantic `--accent-ink` foregrounds rather than hardcoded `#ffffff`, or dark mode inversions will break contrast.

---

### ED-17: Coercive Extortion Lookaheads, O(N) vs O(N^2) ReDoS Bounds & Cross-Artifact Invariants (`SF-005` / `SF-005B`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Sample 184 (*"Process server showed up at the neighbors house looking for the previous tenant."*) triggered an unconditional `H=0.80 -> BLOCK (S=1.0)` false drop from `RULE:TAX_ARREST_THREAT` despite `P_onnx=0.0825`. Subsequent adversarial probing revealed three additional risks: (1) bare `"final notice"` / `"tax penalty abatement"` / `"case #"` phrases falsely blocked CPA/attorney/news texts (`A01..A03`), (2) nested regex lookaheads `(?=.*(?=.*...))` caused catastrophic `O(N^2)` ReDoS backtracking (`202.0ms` at `N=3200`), and (3) evaluation artifacts could fall out of sync when custom models were exported without updating canonical reports.
- **Original Assumption:** Unanchored keywords like `process server` and nested lookahead expressions were assumed safe and fast under API length limits (`max_length=1600`).
- **Forensic Evidence:** Error analysis in `ml_metrics.json`, adversarial stress benchmarks in `docs/heuristic_security_audit.md` (exposing `202.0ms` backtracking on nested lookaheads plus `O(N^2)` scaling in 6 unanchored sibling rules), and dropped-clause tests (`DC03`, `DC05`, `DC06` vs. `DC_B05`).
- **Solution Implemented (`fb3ee14`, `1b6bcc6`, `329c642`):**
  1. Rewrote `RULE:TAX_ARREST_THREAT` as 3 **flat top-level anchored lookaheads** `^(?=...)(?=...)(?=...)` requiring coercive arrest/dispatch + legal/tax authority + extortion/payment/urgent CTA, maintaining **$O(N)$** scaling (`0.0256ms` at `N=400`, `0.1898ms` at `N=3200`) plus NFKC & zero-width normalization (`normalize_heuristic_text()`).
  2. Sample 184 shifted cleanly to `ALLOW` (`H=0.0, P=0.0825`) with `30/30` recall preserved on `smish_legal_extortion` and `0` regressions on `DC_B01..DC_B07`.
  3. Built `publish_evaluation_artifacts_atomically()`, `validate_artifact_bundle_invariants()`, `evaluation_artifacts_stale` flagging, and `evaluation_delta_latest.json` sample-level diffs in `evaluate_model.py` / `train_onnx_model.py`.
- **Alternatives Considered:** Unconditionally blocking any message containing 2 clauses (rejected—promoting `"under your name"` without CTA caused `DC_B05` quoted security warnings to false-block; documented explicitly on `DC04`). Removing `H=0.80` override completely (rejected—preserves defense against extortion lures even when OOV to TF-IDF).
- **Trade-offs:** 6 sibling `HEURISTIC_RULES` (`DELIVERY_FEE_SCAM`, `UNPAID_TOLL_INVOICE`, etc.) remain documented in `docs/heuristic_security_audit.md` with `O(N^2)` backtracking risk (`up to 18.98ms` at `N=1600`) for future cleanup; rule quoting/translation parsers do not yet exist (`E01`, `D08`).
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/onnx_engine.py`, `evaluate_model.py`, `docs/heuristic_security_audit.md`, `app/tests/test_telecom_adversarial_hardening.py` (8 tests), `test_telecom_eval_suite.py`
- **Lessons Learned:** Never nest `(?=.*(?=.*))` lookaheads, enforce strict `O(N)` regex stress bounds, and cryptographically bind model weights, predictions, deltas, and Markdown reports in atomic publishes.

---

### ED-18: Broadening URL-Free A2P 2FA/OTP Training Cohort Phrasing for Sample 93 (`SF-006`)
- **Classification:** `MID-LEVEL`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Sample 93 (*"Twitter/X: Confirmation code 918203 to verify phone number."*) suffered a Tier 2 wire drop (`P_onnx = 0.8591, H = 0.0 -> BLOCK`) even though it contained zero URLs, zero urgency extortion, and was a completely routine 2FA OTP SMS.
- **Original Assumption:** Including only a few narrow phrasing variants like `"Your verification code is ..."` in `LEGIT_BASE_SAMPLES` was assumed to generalize across all real-world A2P OTP templates.
- **Forensic Evidence:** Token attribution on Sample 93 showed TF-IDF weighted `"confirmation"`, `"verify"`, `"phone"`, and `"number"` positively toward smishing due to sparse benign OTP template phrasing.
- **Solution Implemented (`08e2274`):** Expanded `build_augmented_dataset()` in `train_onnx_model.py` across 6 structural URL-free, callback-free OTP cohorts (`Cloudflare`, `DigitalOcean`, `Linear`, `Notion`, `Vercel`, `Figma` spanning confirmation codes, email verification passcodes, login approvals, login alerts, recovery PINs, and workspace auth codes).
- **Alternatives Considered:** Hardcoding an allow-list regex for `"confirmation code"` or `"Twitter/X"` (rejected—fitting against a benchmark token would overfit and let attackers smuggle `Confirmation code + https://phish.xyz` past defenses).
- **Trade-offs:** Benign `benign_2fa_auth_codes` still flags 1/25 (`4.0%`, `Cash App code: 928-103...`, `P=0.6404`) at Tier 1 review, while Tier 2 False Drops dropped to **`0 / 25` (`0.0%`)** (and `0 / 200` overall!).
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/train_onnx_model.py`, `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** When a statistical NLP classifier fails on an underrepresented benign cohort, broaden generalizable cohort diversity under separate template families instead of overfitting benchmark strings or punching dangerous heuristic exemptions.

---

### ED-19: 3-Tier Family-Impersonation Operational Policy Separating Casual, Ambiguous P2P & Actionable Lures (`SF-007`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Family-impersonation SMS messages ("Hi mom, dropped my phone, text me on WhatsApp...") span benign device updates, ambiguous friend/kinship broken-phone texts without asks, and high-risk financial/link extortion lures. Binary blocking or flagging everything alike either risked dropping innocent family chats or under-blocking actionable `wa.me` / Zelle scams.
- **Original Assumption:** One single `RULE:FAMILY_IMPERSONATION_MESSAGING_LURE` (`0.65`) pattern was assumed sufficient for all broken-phone patterns.
- **Forensic Evidence:** Policy evaluation in `SF-007` demonstrated that three operationally distinct sub-classes exist across real carrier messaging.
- **Solution Implemented (`98e4888`):** Formalized an explicit **3-Tier Operational Policy** in `onnx_engine.py` and `SYSTEM_DESIGN.md`:
  - **Class A (`ALLOW`, `H=0.00`)**: Repair-shop pickup/quote confirmations (`_FAMILY_REPAIR_EXCLUSION`) or casual device switches (`iPad`, laptop) without kinship relay, URLs, or financial demands.
  - **Class B (`FLAG` Tier 1, `RULE:FAMILY_IMPERSONATION_AMBIGUOUS_P2P`, `H=0.55`)**: Unverified kinship/relay + broken phone/SIM + P2P app (`WhatsApp`/`Telegram`/`Signal`/`iMessage`), explicitly excluding repair shops and excluding URLs/payment asks -> async review without silent wire drop.
  - **Class C (`BLOCK` Tier 2, `RULE:FAMILY_IMPERSONATION_MESSAGING_LURE`, `H=0.75`, `0.87` w/ URL)**: Kinship/relay + broken phone or number swap + external URL (`wa.me`/`http`/`t.me`) or urgent payment/bill ask (`Zelle`/`Venmo`/`Cash App`/wire).
- **Alternatives Considered:** Merging ambiguous P2P chats into Class C wire drops (rejected—high false-drop risk when no URL or payment demand exists).
- **Trade-offs:** Expanding `HEURISTIC_RULES` from 13 to 14 increases nuance and separates ambiguous warnings from actionable extortion at the cost of testing boundary transitions carefully across Class A/B/C fixtures.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/onnx_engine.py`, `SYSTEM_DESIGN.md`, `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Policy design is part of applied ML engineering—product ambiguity should route to human/async review (`FLAG`), while irreversible wire drops (`BLOCK`) require corroborating actionable indicators.

---

### ED-20: Full Base-Seed Semantic Grouping (56 Families), `dataset_inventory.json` & Lexical Similarity Audit (`SF-008`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Some `LEGIT_BASE_SAMPLES` fell back to automatic placeholder heuristics (`extract_template_family_id`) rather than explicit audited semantic families, group sizes varied unevenly, and telemetry lacked an auditable dataset inventory proving cross-split lexical distance vs. exact deduplication.
- **Original Assumption:** Combining partial explicit families with fallback regex grouping was assumed sufficient for balanced cross-validation.
- **Forensic Evidence:** Group inspection showed singleton/uneven fallback groups and needed quantitative evidence of semantic separation between training families and `Dev/Val N=400`.
- **Solution Implemented (`e3d0dce`):**
  1. Mapped 100% of base seeds in `train_onnx_model.py` (`LEGIT_BASE_SAMPLES`, augmented templates) into **56 balanced semantic families** (`703` samples: `543` legit / `160` fraud, `22.76%` fraud prevalence, **`0` singletons**, min size `2`, median `6.0`, max `53` = `7.54%`).
  2. Exported `dataset_inventory.json` auditing per-fold group overlap (`0` across all 5 folds), fold fraud prevalence (`21.58%`–`24.48%`), exact hash duplicates (`0`), cross-family centroid cosine similarity (`max = 0.4590`, `mean = 0.0316`), and honest Train-vs-Dev/Val nearest TF-IDF cosine (`max = 1.0`, `mean = 0.3451`).
- **Alternatives Considered:** Keeping un-inventoried list literals and relying only on exact SHA-256 checks (rejected—misses near-template cosine proximity).
- **Trade-offs:** Reporting `max_dev_val_vs_train_tfidf_cosine = 1.0` candidly confirms lexical overlap between synthetic training domains and `Dev/Val N=400`, underscoring why `SF-010` quarantined real CDR data matters.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/train_onnx_model.py`, `sentinelflow/backend/app/telecom/dataset_inventory.json`, `app/tests/test_telecom_eval_suite.py`
- **Lessons Learned:** Zero exact-hash overlap is only the floor; maintain a versioned `dataset_inventory.json` auditing family cardinality, fold balance, and cross-split TF-IDF cosine similarity.

---

### ED-21: Zero-Leakage Nested 5-Fold OOF CV, 10-Bin ECE, Wilson vs. Cluster Bootstrap CIs & Macro Sensitivity (`SF-009`)
- **Classification:** `SENIOR / STAFF`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Relying solely on a single Fold 0 split (`N=151`) gave noisy estimates, `CalibratedClassifierCV` / `TfidfVectorizer` vocabulary needed strict fold isolation during OOF estimation, Brier score alone didn't expose bin-level miscalibration (`ECE`), and standard binomial intervals ignored intra-family correlation across multi-message templates.
- **Original Assumption:** Single-fold validation metrics and message-level binomial counts were assumed sufficient summary statistics for calibration and generalization uncertainty.
- **Forensic Evidence:** In `17433cf`, running zero-leakage nested 5-fold `StratifiedGroupKFold` across all `703 / 703` training messages produced complete diagnostics across `56` fine-grained vs `54` collapsed macro groups:
  - **Pooled OOF Pure-ML (`703/703`)**: `ROC-AUC = 0.9559` (Cluster Bootstrap 95% CI `[0.8654, 0.9960]`), `PR-AUC = 0.8751` (`[0.5437, 0.9919]`), `Brier = 0.0678`, `ECE = 0.0914`, `F1 = 0.7928` (`Per-Fold Mean = 0.9427 ± 0.0867`). Note Fold 4 remained the hardest (`ROC-AUC 0.7715`, `PR-AUC 0.5791`).
  - **Dev/Val (`N=400`) 10-Bin Calibration**: `ECE = 0.1027`, `MCE = 0.2447`, `Brier = 0.0371` (Platt scaling caps probabilities around `[0.8, 0.9)` with `161` bin-8 samples at `100%` fraud vs `0.8462` mean pred, leaving bin 9 `[0.9, 1.0]` empty).
  - **Macro-Archetype Sensitivity (`legit_bank_2way_macro`, `G=54`)**: Collapsing 3 two-way bank alert templates into 1 lowers pooled OOF `ROC-AUC` from `0.9559 -> 0.9309` and `PR-AUC` from `0.8751 -> 0.7330`!
- **Solution Implemented (`17433cf`):** Implemented `evaluate_oof_cross_validation()` fitting `Pipeline(TfidfVectorizer -> LogisticRegression)` inside inner CV splits (zero vocabulary leakage), `oof_predictions.json` (`sha256: 9b637652...`), `compute_calibration_diagnostics()` (10-bin ECE/MCE), `compute_wilson_ci()`, and `compute_cluster_bootstrap_ci()` (`B=1000`, resampling whole semantic families).
- **Alternatives Considered:** Fitting `TfidfVectorizer` once globally before CV (rejected—introduces silent IDF vocabulary leakage across folds) or reporting only message-level Wilson CIs (rejected—understates variance when samples share templates).
- **Trade-offs:** Cluster bootstrap across `G=56` families produces appropriately wide uncertainty intervals (`PR-AUC 95% CI: [0.5437, 0.9919]`), reflecting true corpus diversity constraints cleanly.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/train_onnx_model.py`, `evaluate_model.py`, `oof_predictions.json`, `docs/ml_evaluation_report.md`, `app/tests/test_telecom_eval_suite.py`
- **Lessons Learned:** Fit vectorizers strictly inside CV splits, pair Brier scores with 10-bin ECE reliability tables, and always pair message-level Wilson intervals with template-cluster bootstrap CIs on templated corpora.

---

### ED-22: External Dataset Provenance Governance, Confounding Audit & Class C Holdout Block (`SF-010` / `SF-011`)
- **Classification:** `SENIOR`
- **Status:** `Verified in Code & Governance Ledgers (Class C Blocked)`
- **The Problem Encountered:** SentinelPulse needed an independent, single-shot external Class C fraud/smishing holdout (`quarantined_test_holdout.json`) to validate generalization outside internal Train (`N=703`) and Dev/Val (`N=400`) sets.
- **Original Assumption:** Public SMS phishing and spam repositories (UCI `#228`, Mendeley SMS Phishing, IMC '25, IEEE Access Super SMS, Kaggle SMS dumps) were candidates to serve as an untouched Class C benchmark.
- **Forensic Evidence:** Auditing 8 primary sources (`SF-010`: `external_source_assessment.json`) plus 12 acquisition routes (`SF-011`: `sf011_acquisition_routes.json`) exposed disqualifying flaws across every open two-class candidate:
  - `Fishing for Smishing` (`IMC '25`, `33,869` rows): positive-only (`n_- = 0`) AND Presidio PII scrubbing rewrote raw URLs into `<URL>`, destroying verbatim signal fidelity (`6,030/14,363` unique non-spam English rows).
  - `Mendeley 5971` (Mishra & Soni 2022): direct hash matching proved **`361 / 638` (`56.6%`) `Smishing` labels are exact copies of 2011 UCI `spam` rows** alongside `4,319` UCI `ham` copies.
  - `spstudy` (`Super SMS`, IEEE Access '24): **`94.4%` (`38,534 / 40,830`) benign rows come from legacy pre-2015 NUS/UCI P2P student chat** with `license: None` (`0.0098%` URLs vs `19.98%` in class `1`), proving cross-source stitching causes severe era/channel confounding.
  - `wspr-ncsu/sms-phishing` (IEEE S&P '24): MIT-licensed, unredacted URLs (`68,029` rows), zero Train/DevVal overlap, yet strictly positive-only (`n_- = 0`).
  - Windows CRLF vs Linux LF line endings caused working-tree vs Git SHA-256 mismatch (`f35b8ea` vs `127ed84`).
- **Solution Implemented (`0acd742`, `41f66a2`, `f7b2d70`, `46b1822`):**
  1. Left `quarantined_test_holdout.json` **intentionally absent** and formally marked `SF-011` **`BLOCKED_ON_PRIMARY_EXTERNAL_HOLDOUT`** rather than fabricating/stitching flawed holdouts.
  2. Quarantined `UCI SMS Spam Collection v.1` (`5,574` rows: `4,827 ham`, `747 spam`, `0` Train/DevVal overlap) strictly as a legacy spam transfer benchmark (`uci_sms_spam_secondary.json`) with `is_primary_fraud_holdout=false` and `derived_fraud_label=null`.
  3. Enforced AST-isolated reconstruction (`build_quarantine_artifacts.py` using `_PureAstEvaluator`), `.gitattributes` POSIX LF rules (`eol=lf`), and 7 mandatory Class C gates (`evaluate_class_c_qualification_routes`) requiring `DEFF`-adjusted effective minimums (`n_{+,eff} >= 300–500`, `n_{-,eff} >= 1,000–2,000`).
- **Alternatives Considered:** Stitching `IMC '25` / `wspr-ncsu` positives with `UCI #228` `ham` negatives (rejected—trivially separable era & PII-redaction shortcut).
- **Trade-offs:** Leaves external Class C fraud generalization explicitly `UNAVAILABLE / BLOCKED` until a DUA-gated carrier/CPaaS enclave slice is executed, guaranteeing zero misleading holdout claims.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/dataset_quarantine.py`, `build_quarantine_artifacts.py`, `docs/dataset_provenance_and_governance.md`, `docs/sf011_class_c_acquisition_and_qualification.md`, `app/tests/test_telecom_eval_suite.py`
- **Lessons Learned:** External provenance, statistical independence, and feature fidelity are separate gates—never mix positive-only modern lures with decade-old P2P negatives.

---

### ED-23: Bayes Base-Rate PPV Collapse, Group Error Concentration & Conditional Cost Sensitivity (`SF-012` / `SF-012R.1`)
- **Classification:** `SENIOR / STAFF`
- **Status:** `Verified in Code & Reports (Exploratory Analysis Only)`
- **The Problem Encountered:** Reporting `100.00%` precision on a balanced 50/50 benchmark (`Dev/Val N=400`) obscures extreme precision collapse at realistic carrier fraud prevalences (`0.2%`–`1.0%`), while an early cost-grid analysis risked over-claiming optimality around `tau = 0.85` from finite curated OOF clusters.
- **Original Assumption:** Point estimates from balanced sets, `B = 1,000` bootstrap replicates, and a narrow assumed cost matrix were treated as candidate justification for threshold shifts.
- **Forensic Evidence (`cc0567e`, `34284ec`, `a5da101`):**
  1. **Bayes PPV Collapse:** Holding OOF Tier 1 (`TPR=97.50%`, `FPR=8.10%`) constant, dropping prevalence $\pi$ from `50%` → `0.5%` → `0.2%` crashes modeled `PPV` to **`5.70%` → `2.35%`**. Similarly, `0 / 543` FPs at `tau = 0.85` mechanically shows `100%` PPV, whereas descriptive row Wilson upper FPR (`0.70%` at `TPR=56.88%`) collapses PPV to **`28.92%`** at $\pi = 0.5\%$.
  2. **Group Error Concentration:** Between `tau = 0.60` and `0.80`, **`100%` of OOF false positives** (`40`, `27`, `13`, `4`) occurred inside ONE benign family (`legit_bank_security_alert_12`), leaving `36 / 37` benign groups at `0` FPs.
  3. **Bootstrap & Cost Caveats:** Increasing `B` from `1,000` to `10,000` stabilized Monte Carlo tail jitter (from up to `3.92 pp` to `<= 1.21 pp`), while an expanded 72-ratio cost grid (`576` cells) proved `cost_assumption_sensitive = True` and exposed that `compute_dual_tier_cost_per_1000` assigns zero upside to wire drops over async review, mechanically biasing toward `tau = 0.85` when observed `FPR(0.85) = 0`.
- **Solution Implemented:** Documented explicit three-tier inference boundaries (`supported` conditional on `G=56` curated families, `violated` i.i.d. binomial bounds like `7.78%` / `9.41%` retained strictly as mathematical reference, `unsupported` real-world generalization), preserved production defaults (`0.40` / `0.75`), and marked `tau = 0.85` strictly provisional/unvalidated pending Class C data.
- **Alternatives Considered:** Adopting `tau = 0.85` in production without external Class C validation (rejected—violates `SF-010/11` zero-adaptation holdout discipline).
- **Trade-offs:** Keeps operational analysis candid and non-overclaiming at the expense of leaving optimal production cutoffs unverified until live carrier prevalence/cost telemetry arrives.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/evaluate_model.py`, `ml_metrics.json` (`threshold_and_base_rate_analysis`), `docs/ml_evaluation_report.md` (Section 10), `SYSTEM_DESIGN.md`, `app/tests/test_telecom_eval_suite.py`
- **Lessons Learned:** Balanced-benchmark precision tells you almost nothing about operational false-alarm burden at $\pi \le 1\%$—always compute Bayes $\text{PPV}(\pi)$, inspect cluster error concentration, and distrust zero-FP point artifacts.

---

### ED-24: Mixed-Script Cyrillic Homoglyph Defense, Atomic ReDoS Fix & Substring Prefilters (`SF-013`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Under adversarial obfuscation (`afae166` 6-family perturbation suite, `70` total prompts with `0` Train/DevVal overlap), Cyrillic homoglyphs dropped frozen ASCII TF-IDF recall and crashed original regex heuristics from **`100.0%` down to `0.0%`** (Composite Tier 2 dropped `90% → 10%`), irregular multi-space/control characters broke literal-space patterns, and several sibling rules retained `O(N^2)` backtracking.
- **Original Assumption:** Baseline NFKC normalization alone was assumed sufficient for homoglyph invariance, and unanchored `.*` patterns were assumed safe enough short-term.
- **Forensic Evidence (`afae166`, `f423f86`, `9fef3fb`, `7f31a5b`):**
  - `ml_metrics.json` (`perturbation_robustness`) showed Cyrillic homoglyphs dropped mean `P_onnx` from `0.8110 → 0.5271` (`token_pattern` rejects Cyrillic codepoints).
  - Contrastive benign controls exposed why Bag-of-Words TF-IDF still flags `20%` (`2/10`) in Tier 1 without syntactic negation scope (`benign_courthouse_jury`: *"no fee required"* scored `P=0.5420` because `fee +0.1668` outweighed `no -0.1060`).
- **Solution Implemented:**
  1. Added selective **`CYRILLIC_CONFUSABLE_MAP`** (`24` lookalikes) + `detect_and_normalize_cyrillic_homoglyphs()` + `RULE:HOMOGLYPH_OBFUSCATION` (`0.45`), distinguishing natural Russian/bilingual prose (**Case B: ALLOW**) from mixed-script spoofing and Latin-embedded confusables (**Cases A/C/D: BLOCK**). Cyrillic heuristic recall jumped **`0.0% → 100.0%`** (`mean H = 0.8200`), Composite Tier 1/2 **`80%/10% → 100%/70%`**.
  2. Normalized whitespace runs (`_WHITESPACE_RUN_RE`), added an **ASCII fast path (`text.isascii()`)**, converted `O(N^2)` sibling rules (`URGENT_ACCOUNT_LOCKOUT`, `DELIVERY_FEE_SCAM`, `UNPAID_TOLL_INVOICE`, `TECH_SUPPORT_INVOICE_SCAM`, `WORK_FROM_HOME_SCAM`, `SIM_SWAP_OR_KYC_SCAM`, `GENERIC_DELIVERY_KEYWORD`) to **atomic groups `(?>...)`** + **positive-first family lookaheads**, and added **`_RULE_PREREQ_SUBSTRINGS`** substring short-circuiting.
- **Alternatives Considered:** Unconditional full-text Cyrillic-to-Latin transliteration (rejected—corrupts legitimate non-Latin/bilingual traffic); retraining ONNX weights under `SF-013` (rejected—kept weights frozen to isolate defense-in-depth gains cleanly).
- **Trade-offs:** Enumerated confusable map targets `24` high-signal Cyrillic characters only (does not cover Greek, Cherokee, or mathematical blocks); leetspeak/dot-splitting still lowers pure regex recall (`60.0%`) cleanly caught at Tier 1 (`100.0%`).
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/onnx_engine.py`, `evaluate_model.py`, `docs/ml_evaluation_report.md` (Section 11), `test_telecom_eval_suite.py` (Cases A–D invariants)
- **Lessons Learned:** Use script-context discrimination—not blind transliteration—for homoglyph defense, and eliminate `O(N^2)` regex engines systematically via atomic `(?>...)` groups + cheap substring prefilters.

---

### ED-25: Fail-Closed ONNX Thread Pinning & `/v1/health` Redis Degraded-Mode Telemetry (`SF-014`)
- **Classification:** `SENIOR`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Missing or corrupt `sms_fraud_model.onnx` binaries previously logged a warning and silently degraded into heuristic-only mode without fail-fast guarantees, `inter_op_num_threads` was unpinned (`intra_op` only), and operators had zero API telemetry showing when `RedisVelocityStore` tripped into local memory fallback.
- **Original Assumption:** Pinning `intra_op_num_threads=1` and logging local circuit-breaker warnings was assumed sufficient for production observability.
- **Forensic Evidence:** Inspection in `SF-014` showed silent heuristic-only degradation masks broken deployments, unpinned `inter_op` threads risk multi-worker CPU contention, and health probes lacked circuit-breaker state fields.
- **Solution Implemented (`6dc06bd`):**
  1. Pinned both `intra_op_num_threads = 1` and `inter_op_num_threads = 1` (`ORT_SEQUENTIAL`, `ORT_ENABLE_ALL`) on `SessionOptions`, and changed `_init_session()` in `onnx_engine.py` to **fail closed** (`FileNotFoundError` / `RuntimeError`).
  2. Added `RedisVelocityStore.degraded_local_fallback`, `active_backend` (`"redis"` | `"local_memory_fallback"`), and `get_status()` returning `velocity_backend`, `velocity_degraded_mode`, and `cooldown_remaining_seconds`, wired through `/v1/health`, `openapi.json`, and `frontend/lib/types/api.generated.ts`.
- **Alternatives Considered:** Silent fallback on missing `.onnx` binary (rejected—silently drops ML recall on malformed container deploys).
- **Trade-offs:** Deploying without a valid SHA-256 matched `.onnx` binary intentionally aborts worker boot instead of serving degraded heuristic-only verdicts.
- **Relevant Files & Tests:** `sentinelflow/backend/app/telecom/onnx_engine.py`, `velocity_store.py`, `api/telecom.py`, `openapi.json`, `app/tests/test_telecom_gateway.py`
- **Lessons Learned:** Fail open when optional velocity cache blips (`SF-004`/`ED-07`), fail closed when the core ML artifact is missing/tampered (`SF-003`/`SF-014`), and expose degraded cache state directly on health endpoints.

---

### ED-26: Synchronous SMS PII Redaction, 128-Bit HMAC Pseudonymization & Boundary A vs B Latency Truth (`SF-015`)
- **Classification:** `SENIOR / STAFF`
- **Status:** `Remediated & Verified in Code & Tests (Boundary B >15ms Locally at 2k Chars)`
- **The Problem Encountered:** Raw phone numbers (`tel_+1555...` or unsalted SHA-256 hashes), unmasked OTP codes/SSNs in escalated disputes/logs, missing length caps on sender/IP/carrier/event IDs, and conflated `<15ms end-to-end HTTP` SLA claims vs internal `_process_single_message()` measurements exposed security, privacy, and credibility gaps.
- **Original Assumption:** Truncated unsalted SHA-256 sender hashes and short-message (`~73`-char) internal ASGI latency figures were treated as complete across production privacy and HTTP wire targets.
- **Forensic Evidence (`eb9f9c7` → `e12734d`):**
  - Unsalted SHA-256 digests over low-entropy E.164/NANP phone spaces are trivially brute-forced via rainbow tables (~`10^10` NANP numbers).
  - Running reproducible 2,000-char benchmarks (`scripts/bench_telecom_classify_2000.py`) proved **Step 3 `evaluate_heuristics()` (`p95 <= 3.477ms`)** and **Boundary A internal `_process_single_message()` (`p95 = 5.488–8.815ms` loopback / `6.254–7.128ms` ASGI)** pass `< 15ms`, **but Boundary B caller-observed HTTP (`loopback_http_ms p95 = 17.259–17.793ms` at `conc=1`, `60.85–61.26ms` at `conc=4`, `121.06–124.16ms` at `conc=8`) exceeds `15ms`** locally due to FastAPI middleware, Pydantic validation/serialization, and post-`t_end` synchronous logging.
- **Solution Implemented:**
  1. Implemented `redact_sms_pii()` (covering phones, emails, SSNs, cards, context & standalone 4–8 digit OTP codes) + tag-safe `_bound_redacted_message(..., max_len=2000)` setting `message_truncated: bool` without bisecting `[REDACTED_*]` tokens, plus payload bounds (`message` `<= 2000` chars aligned cleanly).
  2. Replaced unsalted digests with **key-versioned 128-bit (32-hex) HMAC-SHA256 pseudonyms** (`tel_<key_id>_<digest>`, namespace-separated `vel_sender`/`vel_ip`/`vel_domain`/`vel_prefix`) via `pseudonymize_telecom_identifier()`, requiring explicit `TELECOM_HMAC_SECRET` and `TELECOM_HMAC_KEY_ID` (`<= 16` ASCII chars) fail-closed in `APP_ENV == 'production'`.
  3. Updated `SYSTEM_DESIGN.md`, `README.md`, discovery docs (`llms.txt`), and benchmark scripts to separate **Boundary A (internal `< 15ms`)** from **Boundary B (caller HTTP `> 15ms` at 2,000 chars locally)** and mark live Redis RTT & multi-worker concurrency explicitly **`UNVERIFIED`**.
- **Alternatives Considered:** Unsalted `sha256` sender IDs (broken by phone-space brute force); silent truncation splitting `[REDACTED_CODE]` markers (corrupts audit clarity); keeping `<15ms end-to-end HTTP` marketing claims without empirical 2k-char verification.
- **Trade-offs:** Atomic rotation of `TELECOM_HMAC_KEY_ID` intentionally resets correlation across `DisputeRecord.customer_id` and fresh Redis velocity windows under the new key prefix.
- **Relevant Files & Tests:** `sentinelflow/backend/app/services/trace_safety.py`, `api/telecom.py`, `config.py`, `telecom/onnx_engine.py`, `velocity_store.py`, `scripts/bench_telecom_classify_2000.py`, `SYSTEM_DESIGN.md`, `app/tests/test_trace_safety.py`, `test_telecom_gateway.py`
- **Lessons Learned:** Pseudonymization over low-entropy telecom IDs requires keyed 128-bit+ HMACs with fail-closed key-ID lifecycle validation; always distinguish internal handler timers (**Boundary A**) from caller-observed wire HTTP latency (**Boundary B**).

---

### ED-22: Multi-Pass PII Redaction Ordering, 2000-Char Input Bounds, Atomic-Group ReDoS Prevention & Adversarial Pre-Completion Audit Protocol (`SF-015`)
- **Classification:** `SENIOR / STAFF`
- **Status:** `Remediated & Verified in Code & Tests`
- **The Problem Encountered:** Initial `SF-015` (`eb9f9c7`) left four gaps caught during adversarial review:
  1. **Contract Deviation (`1600` vs `2000`)**: Retained `max_length=1600` from an older SF-005 test instead of aligning with Linear `AI-18`'s `max_length=2000`.
  2. **Multi-Pass PII Ordering & Punctuation Edge Cases**:
     - `trace_safety.py`'s `card` regex (`(?:\d[ -]*?){13,19}`) lacked `(?<![+\d])` and ran before `phone`, misclassifying 13-digit international phones (`+55 11 99876-5432`, `+49 151 2345 6789`) as `+[REDACTED_CARDLIKE]`.
     - Trailing sentence periods (`918203.`, `4829.`, `123-45-6789.`, `928-103.`) blocked redaction because `(?![.\d])` rejected sentence-ending periods (leaving warmup OTPs `492018.` and `773910.` unredacted).
     - Hyphenated OTP/backup codes (`928-103`, `1928-3746`) were either missed or partially leaked (`[REDACTED_CODE]-3746`), `1-800-555-0199` left `1-` dangling, and space-separated/contextual SSNs (`123 45 6789`, `SSN: 123456789`) and contiguous 10-11 digit NANP phones (`4155550199`) were unredacted.
  3. **Sink & Exception Log Coverage**: `_spawn_escalation_task` passed raw `sender`/`message` in the non-`arq` fallback path, `_create_escalated_dispute` did not sanitize `velocity`/`signals`/`carrier` on direct `/telecom/escalate` calls, and `logger.error`/`logger.warning` calls logged raw exception strings without `redact_sms_pii()`.
- **Solution Implemented:**
  1. Aligned `TelecomClassifyRequest.message` and `TelecomEscalateRequest.message` to `max_length=2000` across `app/api/telecom.py`, `openapi.json`, and test suites.
  2. Fixed `trace_safety.py` and `onnx_engine.py` (`redact_sms_pii`) with `(?<![+\d])(?<!\d\.)` and `(?![-\d]|\.\d)` decimal-only lookarounds, international/NANP phone coverage, hyphenated OTP support, and contextual 9-digit SSN/TIN redaction.
  3. Hardened `_mask_phone`, `_sanitize_velocity_dict`, `_spawn_escalation_task`, `_create_escalated_dispute`, and all exception loggers across `app/api/telecom.py`, `onnx_engine.py`, and `velocity_store.py`.
- **Mandatory Pre-Completion Adversarial Audit Protocol (Why Follow-Ups Happened & Permanent Prevention Rule):**
  1. **Zero Silent Spec Deviations**: Never retain an older constant (`1600`) or omit a named rule (`RULE:HOMOGLYPH_OBFUSCATION`) when a ticket specifies an explicit contract (`2000`). Audit the origin of any conflicting test and either update the contract + test or document a formal compatibility decision upfront.
  2. **Adversarial Boundary Matrix Before Declaring Done**: Never rely on 1–2 happy-path strings when testing regexes or redaction helpers. Always probe: (a) punctuation adjacency (trailing `.`, `,`, `]`, `)`), (b) separator variants (`-`, space, `.`, contiguous), (c) ordering collisions across multi-pass regexes, (d) boundary lengths (`max - 1`, `max`, `max + 1`), and (e) negative controls.
  3. **Full Empirical Evidence in Completion Reports**: Never compress final reports into high-level claims (`"scales linearly"`, `"masks PII"`). Always include raw empirical tables (`400..3200` ms timings), exact before/after patterns, positive/negative input->output examples for every required category, and a complete sink-by-sink logger audit distinguishing verified, inferred, and unverified behavior.

---

### ED-27 · Unseen-Family Generalization Investigation & Justified No-Change Decision (`SF-019` / `AI-32`)
- **Status:** `Investigated & Concluded NO-CHANGE (Frozen SF-018 Baseline Retained)` (`sentinelflow/backend/app/telecom/sf019_generalization_comparison.json`, `docs/sf019_unseen_family_generalization_report.md`)
- **The Problem Encountered:** `SF-018` fine-grained 5-fold OOF evaluation exposed all 40/40 Fold 4 false positives (`13/40` Tier 2 `BLOCK`) in `legit_bank_security_alert_12`. Root-cause diagnosis confirmed four causes: Fold 4 training vocabulary monopolization (`"security alert"` 0 legit / 65 fraud, `"unusual"` 0 legit / 36 fraud), `$2.50`/`1-800` decimal-digit splitting into bare `'1'`/`'2'`, additive BoW lack of URL/callback absence conditioning, and unstratified inner `GroupKFold(5)` calibration causing Platt intercept swings (`-6.19` to `+2.41` in outer Fold 4).
- **The Candidates Evaluated & Rejected:** Hyperparameter tweaks (`C=0.5`, `min_df=2`, `len>=2`) harmed fraud recall or failed on `bank_12`; retail/fintech augmentation introduced FPs/FNs on `dev_val_400`. The best-scoring candidate (`NoFin SGKF`, `N=719, G=59`, `2362003b...`, adding 3 non-bank URL-free benign families + `StratifiedGroupKFold(5)` calibration) reduced `bank_12` OOF (`40->29`, Tier 2 `13->0`) and raised pooled F1 (`0.7964->0.8246`), **but failed two existing regression contracts** without test relaxation: `C12` WFH Telegram scam recall dropped (`1.0000->0.9375`, `S=0.3575 < 0.40`), `SF-007` Class B broken-phone P2P escalated (`FLAG->BLOCK`, `S=0.8792`), and `legit_health_mychart` shifted `0/21 -> 20/21` Tier 1 flags.
- **Outcome & Honest Residual Risk:** Recorded a justified `NO-CHANGE` decision (`AI-32` AC #4/#5/#7) retaining frozen `SF-018` (`824c6c2c...`, `N=703, G=56`) with `sf019_generalization_comparison.json` preserved as evidence and guarded by `test_sf019_fold4_baseline_reconciliation_and_no_change_invariants`. Safely resolving this linear BoW unseen-family boundary requires structural URL/callback absence features or genuine external Class C data (`SF-022`).

---

### ED-28 · Real-Redis Multi-Worker Timeout Fix & Topology Validation (`SF-020` / `AI-33`)
- **Status:** `Implemented & Verified on Real Docker Redis 7 + W=4 Uvicorn Workers` (`sentinelflow/backend/app/telecom/sf020_runtime_benchmark.json`, `docs/sf020_production_runtime_validation.md`)
- **The Problem Encountered:** Executing `bench_production_topology.py --manage-redis` against real `redis:7-alpine` (`7.4.11`) immediately trapped all 4 independent `uvicorn` workers in `local_memory_fallback` (`10/10` `TimeoutError('Timeout connecting to server')` at `~1ms`) because `socket_timeout=0.015` / `socket_connect_timeout=0.015` aliased below Windows' 15.625ms OS timer tick resolution.
- **The Solution Implemented:** Raised `RedisVelocityStore._get_client()` timeouts to `socket_timeout=0.050` / `socket_connect_timeout=0.100`, fixed Windows child-process RSS/CPU measurement in `bench_production_topology.py`, and separated isolated ONNX, cold-start, steady-state (`C=1, 8, 16`), sustained (`N=1,000, C=8`), concurrent correctness (`120/120`, `0` mismatches), and real-Redis outage (`docker stop` `N/W` fallback) + recovery (`docker start`).
- **Outcome & Honest Boundary:** Sustained `N=1,000, C=8` hit `666.01 RPS`, `21,619` Redis commands, `0/4` degraded workers, Boundary A `p95=4.271 ms`, Boundary B HTTP `p95=11.235 ms` (`4.962–11.235 ms` through `C=8`). Under `C=16` CPU oversubscription (`p95=34.265 ms`) and worker cold starts (`25.3–50.2 ms`), Boundary B exceeds 15 ms—proving no universal sub-15ms HTTP guarantee exists.

---

### ED-29 · Clean-Checkout Liveness/Readiness Hardening & Reproducible Demo (`SF-021` / `AI-34`)
- **Status:** `Implemented & Verified in Isolated Clean Checkout` (`docs/sf021_clean_checkout_readiness.md`, `sentinelflow/ops/demo_readiness.py`)
- **Decision:** Separated `/api/v1/health` (`200 ok` process liveness) from `/api/v1/ready` (`503 READINESS_STARTING` during lifespan startup, `READINESS_SCHEMA_MISSING`, `READINESS_MODEL_UNAVAILABLE`, plus production checkpointer/Redis/provider gates), aligned frontend `/telecom` badges (`Redis: Connected` vs `Degraded Fallback`, `ML Engine: Healthy` vs `DEGRADED`/`UNAVAILABLE`, `PII REDACTED`, `ML FALLBACK` notice) with backend payloads, and proved cold setup (`postgres:16-alpine`, `redis:7-alpine`, `.env.example`, `uv sync --extra dev`, `alembic upgrade head`, `seed`, `pnpm build`), all demo scenarios, Playwright UI, Redis outage/recovery, and Run 2 teardown cleanly in a `305`-file checkout with `0` Learning Hub files.

---

### ED-30 · Phase 1 External SMS Fraud Dataset Audit Remains Blocked (`SF-022` / `AI-35`)
- **Status:** `UNAVAILABLE / BLOCKED` (`sentinelflow/backend/app/telecom/datasets/sf022_qualification_ledger.json`, `docs/sf022_external_dataset_qualification_report.md`)
- **Decision:** Audited 7 newly discovered 2024–2026 Hugging Face / Mendeley / Zenodo candidates (`redasers/difraud` `sms/` = `72.28%` normalized UCI #228 overlap; Mendeley `vmg875v4xs.1` = LLM-generated balanced classes; `ealvaradob`/`grephon777` = Mendeley `f45bkkt8pr.1` mirrors; `UniqueData` = 25-row `NC-ND` teaser; `PhishVN`/`Chichewa` = non-English/LLM/translated). Combined with 20 `SF-010`/`SF-011` routes, zero passed all 7 Class C gates. No holdout file was fabricated and frozen `SF-018` model weights (`824c6c2c...`, retained under `SF-019`) remain untouched.

# SentinelPulse Empirical ML Development & Validation Benchmark Report (Dev/Val N=400)

> **Reproducibility Stamp:** All metrics, confusion matrices, and breakdowns are generated directly from execution against the compiled ONNX model artifact and development/validation benchmark suite (N = 400). Zero simulated or synthetic figures.

## 1. Reproducibility & Environment Stamp

- **Model Artifact:** `sms_fraud_model.onnx` (193.84 KB)
- **Model SHA-256:** `824c6c2c254791205184efadd8f0b2dc43f22e7222b411e75c2b99c340a9604b`
- **Evaluation Dataset SHA-256:** `210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03`
- **Canonical 400-Row Predictions Artifact:** `benchmark_predictions_400.json`
- **Canonical 400-Row Predictions SHA-256:** `f7bb0b9b8f5996a2b01338f9e2edae456db4d8d98e3fbc6f155d372693233bf7`
- **Timestamp:** `2026-11-16T23:35:21.187968+00:00`
- **Evaluator Engine:** `ONNXRuntime-CPU (AVX-512)`
- **Software Versions:** `onnxruntime=1.31.0`, `numpy=2.5.4`, `scikit-learn=1.9.1`
- **Dataset Size:** 400 samples (200 Benign, 200 Fraud)

### ONNX vs. Scikit-Learn Numerical & Operational Parity (N = 400)

- **Max TF-IDF Vector Absolute Diff:** `6.1148149211e-08`
- **Mean TF-IDF Vector Absolute Diff:** `2.3520298389e-08`
- **Max Calibrated Probability Absolute Diff ($|P_{\text{sklearn}} - P_{\text{onnx}}|$):** `1.1473402112e-07`
- **Mean Calibrated Probability Absolute Diff:** `2.3275415351e-08`
- **End-to-End Operational Verdict Agreement (`ALLOW` / `FLAG` / `BLOCK`):** `400 / 400` (`100.0%`)

### Evaluation Integrity & Provenance Clarification
The 400-message benchmark suite (200 hard benign, 200 adversarial smishing) was curated and utilized iteratively during development to guide heuristic tuning, rule escalation validation, and calibration verification. Consequently, it represents an empirical **Development & Validation Benchmark** rather than an untouched, single-use external holdout. While exact normalized SHA-256 hash overlap against the training corpus is strictly 0, iterative engineering inspection occurred during model tuning.

**Independent Evaluation Strategy:**
To measure unbiased real-world generalization, production release candidates must be evaluated against a quarantined, independently collected carrier telemetry test suite with the following governance controls:
1. **Independent Provenance:** Samples sourced directly from live telecom gateway optical taps across multiple geographical routing nodes, verified with carrier ground-truth CDRs (Call Detail Records).
2. **Cryptographic Quarantine & Zero Developer Access:** Quarantined test corpus is cryptographically hashed with SHA-256 upon ingestion and sealed in an access-restricted vault with zero developer access.
3. **Single-Shot Release Gate:** The quarantined test suite is executed exclusively by automated CI/CD release pipelines with strict single-shot evaluation to prevent iterative optimization and information leakage.

## 2. Core Discriminative & Calibration Metrics (Raw ML Model at P >= 0.50)

| Metric | Measured Score | Operational Significance |
|---|:---:|---|
| **ROC-AUC** | **0.9959** | Area under ROC curve across all possible decision thresholds |
| **PR-AUC** | **0.9960** | Precision-Recall curve area (robust under class skew) |
| **Brier Score** | **0.0380** | Probability calibration loss (lower is better, calibrated < 0.10) |
| **Precision (P >= 0.50)** | **95.98%** | True fraud / (True fraud + False alarms) |
| **Recall (P >= 0.50)** | **95.50%** | True fraud caught / Total actual fraud |
| **F1-Score** | **0.9574** | Harmonic mean of precision and recall |
| **False Positive Rate (FPR)** | **4.00%** | Benign messages incorrectly flagged |
| **False Negative Rate (FNR)** | **4.50%** | Fraud messages that evaded detection |

## 3. Dual-Threshold Operational Tiers

| Operational Tier | Threshold | Purpose | Recall | Precision | FPR | Confusion Matrix |
|---|:---:|---|:---:|:---:|:---:|---|
| **Tier 1: Escalation Queue** | $S \ge 0.40$ | Async SentinelFlow Review | **100.00%** | **95.24%** | **5.00%** | TP=200, FP=10, TN=190, FN=0 |
| **Tier 2: Immediate Wire Drop** | $S \ge 0.75$ | Synchronous Wire Drop | **90.00%** | **100.00%** | **0.00%** | TP=180, FP=0, TN=200, FN=20 |

## 4. Component Ablation Study (ML vs. Heuristics vs. Combined)

| Strategy | Metric Floor / Threshold | Recall | Precision | FPR | F1-Score | Architectural Role |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **ML Model Alone** | $P \ge 0.50$ | 95.50% | 95.98% | 4.00% | 0.9574 | Statistical semantic pattern recognition |
| **Heuristics Alone** | $H \ge 0.50$ | 81.00% | 100.00% | 0.00% | 0.8950 | Deterministic regex rule triggers |
| **Combined (Tier 1)** | $S \ge 0.40$ | 100.00% | 95.24% | 5.00% | 0.9756 | Zero FN guarantee for human escalation |
| **Combined (Tier 2)** | $S \ge 0.75$ | 90.00% | 100.00% | 0.00% | 0.9474 | High-precision wire drop (>98.5% precision) |

## 5. Fine-Grained Category-Level Performance Breakdown

| Category | Class | Samples | Mean P | Mean H | Mean S | Pure ML (P>=0.50) | Heuristics (H>=0.50) | Tier 1 (S>=0.40) | Tier 2 (S>=0.75) | Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| Bank Fraud Alerts (YES/NO) | BENIGN | 25 | 0.0124 | 0.0000 | 0.0124 | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | PASSED |
| Carrier Usage & Roaming Notices | BENIGN | 25 | 0.0776 | 0.0000 | 0.0776 | 1/25 (4.0%) | 0/25 (0.0%) | 2/25 (8.0%) | 0/25 (0.0%) | PASSED |
| Clinical Appointments & Billing | BENIGN | 25 | 0.0471 | 0.0000 | 0.0471 | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | PASSED |
| 2FA & OTP Authentication Codes | BENIGN | 25 | 0.0728 | 0.0000 | 0.0728 | 1/25 (4.0%) | 0/25 (0.0%) | 1/25 (4.0%) | 0/25 (0.0%) | PASSED |
| Package Delivery Status Updates | BENIGN | 25 | 0.0932 | 0.1680 | 0.0973 | 2/25 (8.0%) | 0/25 (0.0%) | 2/25 (8.0%) | 0/25 (0.0%) | PASSED |
| Retail Receipts & Curbside Pickups | BENIGN | 25 | 0.0543 | 0.0080 | 0.0543 | 0/25 (0.0%) | 0/25 (0.0%) | 1/25 (4.0%) | 0/25 (0.0%) | PASSED |
| Legitimate Crypto Exchange Notices | BENIGN | 25 | 0.1641 | 0.0000 | 0.1641 | 3/25 (12.0%) | 0/25 (0.0%) | 3/25 (12.0%) | 0/25 (0.0%) | PASSED |
| Conversational & P2P Messages | BENIGN | 25 | 0.0664 | 0.0000 | 0.0664 | 1/25 (4.0%) | 0/25 (0.0%) | 1/25 (4.0%) | 0/25 (0.0%) | PASSED |
| Bank Account Suspension Panic Lures | FRAUD | 30 | 0.8725 | 0.8200 | 1.0000 | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | PASSED |
| Parcel Delivery Customs Fee Scams | FRAUD | 30 | 0.8566 | 0.7700 | 0.9155 | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | PASSED |
| Tax & Court Legal Extortion Threats | FRAUD | 30 | 0.8192 | 0.8320 | 1.0000 | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | PASSED |
| Cryptocurrency Giveaway & Seed Scams | FRAUD | 25 | 0.7831 | 0.6860 | 0.8790 | 25/25 (100.0%) | 20/25 (80.0%) | 25/25 (100.0%) | 25/25 (100.0%) | PASSED |
| Broken Phone Family WhatsApp Lures | FRAUD | 25 | 0.8760 | 0.7500 | 0.9253 | 25/25 (100.0%) | 25/25 (100.0%) | 25/25 (100.0%) | 25/25 (100.0%) | PASSED |
| Fake DocuSign & Invoice Scams | FRAUD | 25 | 0.7083 | 0.5620 | 0.7902 | 20/25 (80.0%) | 15/25 (60.0%) | 25/25 (100.0%) | 15/25 (60.0%) | PASSED |
| Homoglyph & Leetspeak Obfuscation | FRAUD | 20 | 0.8056 | 0.4580 | 0.8426 | 20/20 (100.0%) | 8/20 (40.0%) | 20/20 (100.0%) | 20/20 (100.0%) | PASSED |
| Zero-Link Call-Back Impersonation | FRAUD | 15 | 0.6232 | 0.1867 | 0.6907 | 11/15 (73.3%) | 4/15 (26.7%) | 15/15 (100.0%) | 5/15 (33.3%) | PASSED |

## 6. Error Analysis Summary

- **Tier 1 False Positives ($S \ge 0.40$, Benign):** 10 samples
- **Tier 2 False Positives ($S \ge 0.75$, Benign):** 0 samples
- **Tier 1 False Negatives ($S < 0.40$, Fraud):** 0 samples (Zero Escaped Attacks)
- **Tier 2 False Negatives ($S < 0.75$, Fraud):** 20 samples (Safely caught in Tier 1 queue)

### Key False Positive Insights
Legitimate banking fraud alerts with urgency keywords (e.g. *'Chase Fraud Alert: Did you attempt $35.50? Reply YES or NO'*), and carrier data threshold alerts account for benign messages receiving Tier 1 review. Because they are routed to Tier 1 review rather than dropped on the wire, no legitimate alert or OTP is blocked by those Tier 1 flags.

### Heuristic Rule Refinement Audit Trail (`SF-005`)
- **Sample 184 Remediation (`RULE:TAX_ARREST_THREAT`):** Driven directly by `Dev/Val N=400` error analysis on Sample 184 (*"Process server showed up at the neighbors house looking for the previous tenant."*), `RULE:TAX_ARREST_THREAT` ($H = 0.80$) was refined in [`onnx_engine.py`](../sentinelflow/backend/app/telecom/onnx_engine.py) so legal/tax/process terms require paired coercive enforcement/extortion context rather than matching third-person narrative.
- **Measured Benchmark Impact (`Dev/Val N=400`):** Sample 184 shifted from unconditional wire drop (`BLOCK`, $S = 1.0$) to `ALLOW` ($S = 0.0825$, $H = 0.0$), reducing Tier 2 false positives from 2 to 1 and improving Tier 2 precision while preserving `100%` recall (`30/30`) on `smish_legal_extortion` without retraining or altering model weights (`32c4a024...`).

### 3-Tier Family-Impersonation Operational Policy (`SF-007`)

| Sub-Class | Behavioral Signal Profile | Heuristic Rule & Weight | Target Tier & Score Range | Operational Action |
|---|---|:---:|:---:|---|
| **Class A — Benign Repair / Casual Broken-Phone Chat** | Repair pickup/quote confirmations, or casual personal/colleague device switches (`iPad`, laptop, spare phone) without unverified kinship relay, external links, or financial demands | None ($H = 0.00$) | `ALLOW` ($S < 0.40$) | Immediate wire delivery |
| **Class B — Ambiguous Unverified Kinship + Broken Phone + App Mention** | Unverified kinship/relay cue + broken/lost phone/SIM + P2P app (`WhatsApp`/`Telegram`/`Signal`), **strictly excluding** external URLs (`http`/`wa.me`/`t.me`) and payment/bill demands | `RULE:FAMILY_IMPERSONATION_AMBIGUOUS_P2P` ($H = 0.55$) | `FLAG` (Tier 1, $0.40 \le S < 0.75$) | Async warning / review queue (no silent drop) |
| **Class C — Actionable Family-Impersonation Scam** | Kinship/relay + broken phone or new/temporary number + external link (`wa.me`/`http`/`t.me`) **or** urgent financial demand (`Zelle`/`Venmo`/`Cash App`/wire/urgent bill) | `RULE:FAMILY_IMPERSONATION_MESSAGING_LURE` ($H = 0.75$, $0.87$ with `STANDALONE_URL`) | `BLOCK` (Tier 2, $S \ge 0.75$) | Immediate synchronous wire drop |

## 7. Mathematical Formulation & Monotonicity Guarantees

SentinelPulse implements a **monotonic non-decreasing, continuous gated blend** combining Platt-calibrated ML probabilities with compiled regex heuristics and multi-dimensional velocity risk:

$$\begin{aligned}
\alpha(P_{\text{onnx}}, H) &= \text{clip}\left(\frac{\max(P_{\text{onnx}} - 0.15, H - 0.30, 0.0)}{0.25}, 0.0, 1.0\right) \\[0.5em]
W_H &= 0.35 \times H + 0.30 \times \max(0.0, H - 0.30) \\[0.5em]
S_{\text{content}} &= \begin{cases}
1.0 & \text{if } H \ge 0.80 \quad \text{(Authoritative High-Risk Override)} \\
P_{\text{onnx}} + \alpha(P_{\text{onnx}}, H) \cdot W_H \cdot (1 - P_{\text{onnx}}) & \text{otherwise}
\end{cases} \\[0.8em]
S_{\text{composite}} &= \begin{cases}
1.0 & \text{if } H \ge 0.80 \\
S_{\text{content}} + V \cdot (1 - S_{\text{content}}) & \text{otherwise \quad (Probabilistic Noisy-OR)}
\end{cases}
\end{aligned}$$

### Mathematical Invariants & Monotonicity Properties:
1. **Monotonic Non-Decreasing Property:** $\frac{\partial S_{\text{composite}}}{\partial P} \ge 0$, $\frac{\partial S_{\text{composite}}}{\partial H} \ge 0$, and $\frac{\partial S_{\text{composite}}}{\partial V} \ge 0$ everywhere on $[0, 1]^3$. Output is strictly bounded within $[0.0, 1.0]$. Terminology note: the function is strictly *monotonic non-decreasing* rather than strictly increasing everywhere due to the flat boundary plateau where $H \ge 0.80$ forces $S_{\text{composite}} = 1.0$.
2. **Benign Indicator Suppression:** When $H \le 0.25$ and $P < 0.30$, $\alpha(P, H) = 0.0$ and $S_{\text{content}} = P < 0.30 < 0.40$, strictly avoiding false-positive customer friction.
3. **Authoritative Heuristic Override ($H \ge 0.80$):** High-confidence threat rules immediately override to $S_{\text{composite}} = 1.0$ (`BLOCK`). `RULE:TAX_ARREST_THREAT` ($H = 0.80$) is the explicit rule capable of triggering an immediate standalone override block. High-severity rules with base score $\ge 0.70$ (e.g. `URGENT_ACCOUNT_LOCKOUT`, `UNPAID_TOLL_INVOICE`) reach $\ge 0.82$ via compound rule escalation (+0.12 boost) when paired with a secondary risk signal.
4. **Individual Heuristic Threshold Clarification ($H = 0.65$):** A heuristic score of $H = 0.65$ (e.g. `RULE:DELIVERY_FEE_SCAM`, `RULE:WORK_FROM_HOME_SCAM`) does *not* force Tier 1 escalation ($S_{\text{composite}} \ge 0.40$) on its own when ML suspicion is zero ($P = 0.0, V = 0.0$). At $P = 0.0$, $W_H = 0.3325$ and $S_{\text{composite}} = 0.3325 < 0.40$ (`ALLOW`). Escalation to Tier 1 without velocity requires baseline ML suspicion $P \ge 0.1012$.

## 8. Calibration Diagnostics (10-Bin ECE) & 95% Wilson Confidence Intervals (Dev/Val N=400)

- **Expected Calibration Error (ECE, 10 equal-width bins):** `0.096515`
- **Max Calibration Error (MCE):** `0.265654`
- **Brier Score:** `0.038000`
- **Binning Scheme:** `equal_width_half_open_final_closed` (`[lower, upper)` for bins 0..8; `[0.9, 1.0]` closed for bin 9)

### 10-Bin Reliability Table (Dev/Val N=400)

| Bin | Interval | Count | Mean $P_{\text{onnx}}$ | Empirical Fraud Rate | $|\text{Gap}|$ |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 0 | `[0.0, 0.1)` | 159 | 0.0144 | 0.0000 | 0.0144 |
| 1 | `[0.1, 0.2)` | 15 | 0.1476 | 0.0000 | 0.1476 |
| 2 | `[0.2, 0.3)` | 10 | 0.2438 | 0.0000 | 0.2438 |
| 3 | `[0.3, 0.4)` | 10 | 0.3214 | 0.4000 | 0.0786 |
| 4 | `[0.4, 0.5)` | 7 | 0.4486 | 0.7143 | 0.2657 |
| 5 | `[0.5, 0.6)` | 6 | 0.5434 | 0.5000 | 0.0434 |
| 6 | `[0.6, 0.7)` | 14 | 0.6436 | 0.7143 | 0.0707 |
| 7 | `[0.7, 0.8)` | 16 | 0.7551 | 0.9375 | 0.1824 |
| 8 | `[0.8, 0.9)` | 163 | 0.8475 | 1.0000 | 0.1525 |
| 9 | `[0.9, 1.0]` | 0 | N/A (empty) | N/A (empty) | N/A |

### Message-Level 95% Wilson Binomial Confidence Intervals ($z = 1.95996$)

> **Independence Caveat:** Message-level Wilson intervals treat individual Dev/Val messages as independent Bernoulli trials. Consult Section 9 semantic-family cluster bootstrap intervals for family-level correlation uncertainty on the training corpus.

| Operational Metric | Point Estimate | 95% Wilson CI |
|---|:---:|:---:|
| **Raw ML Precision ($P \ge 0.50$)** | 95.98% | `[92.27%, 97.95%]` |
| **Raw ML Recall ($P \ge 0.50$)** | 95.50% | `[91.67%, 97.61%]` |
| **Tier 1 Precision (`S >= 0.40`)** | 95.24% | `[91.46%, 97.39%]` |
| **Tier 1 Recall (`S >= 0.40`)** | 100.00% | `[98.12%, 100.00%]` |
| **Tier 1 False Positive Rate (`S >= 0.40`)** | 5.00% | `[2.74%, 8.96%]` |
| **Tier 2 Precision (`S >= 0.75`)** | 100.00% | `[97.91%, 100.00%]` |
| **Tier 2 Recall (`S >= 0.75`)** | 90.00% | `[85.06%, 93.43%]` |
| **Tier 2 False Positive Rate (`S >= 0.75`)** | 0.00% | `[0.00%, 1.88%]` |

## 9. Zero-Leakage Nested 5-Fold OOF Cross-Validation & Macro-Archetype Sensitivity (`SF-009`)

- **Protocol:** `Nested 5-fold StratifiedGroupKFold outer/inner with Pipeline(TfidfVectorizer -> LogisticRegression) fitted strictly inside inner calibration splits (zero vocabulary leakage)`
- **Production Export Calibration:** `GroupKFold(n_splits=5)` (group overlap = `0`)
- **OOF Completeness:** `703 / 703` samples covered, duplicates=`0`, max group overlap across all outer & inner splits=`0` / `0`
- **OOF Artifact:** `oof_predictions.json` (`sha256=96dbbf312aeb35cc3d6813faba1b123ca207328cc1361b736a89bc31fbfefc1d`)

### Fine-Grained Semantic Families (56 Families, Out-of-Fold Pooled & Per-Fold Summary)

- **Per-Fold Pure-ML Mean ± Std ($P \ge 0.50$, 5 folds):** ROC-AUC `0.9439 ± 0.0870`, PR-AUC `0.9010 ± 0.1618`, Brier `0.0677 ± 0.0709`, F1 `0.8293 ± 0.2435`
- **Pooled OOF Pure-ML ($P \ge 0.50$):** ROC-AUC `0.9563`, PR-AUC `0.8763`, Brier `0.0676`, ECE `0.090590`, Precision `76.44%`, Recall `83.13%`, F1 `0.7964`
- **Pooled OOF Composite ($V = 0.0$ offline invariant):** Tier 1 (`S >= 0.40`) Precision `78.00%`, Recall `97.50%`, FPR `8.10%`; Tier 2 (`S >= 0.75`) Precision `90.08%`, Recall `73.75%`, FPR `2.39%`

### Semantic-Family Cluster Bootstrap 95% CIs (`nonparametric_cluster_percentile_bootstrap`, `B=1000`, `seed=42`, `G=56` clusters)

| Pooled OOF Pure-ML Metric | Point Estimate | Cluster Bootstrap 95% CI | Message-Level Wilson 95% CI | Undefined Replicates |
|---|:---:|:---:|:---:|:---:|
| **ROC-AUC** | `0.9563` | `[0.8657, 0.9960]` | `N/A (non-binomial)` | 0 |
| **PR-AUC** | `0.8763` | `[0.5435, 0.9922]` | `N/A (non-binomial)` | 0 |
| **Brier Score** | `0.0676` | `[0.0251, 0.1368]` | `N/A (non-binomial)` | 0 |
| **Precision (P >= 0.50)** | `0.7644` | `[0.3844, 1.0000]` | `[69.60%, 82.13%]` | 0 |
| **Recall (P >= 0.50)** | `0.8313` | `[0.6019, 0.9355]` | `[76.56%, 88.14%]` | 0 |
| **F1 (P >= 0.50)** | `0.7964` | `[0.4956, 0.9517]` | `N/A (non-binomial)` | 0 |

### Macro-Archetype Sensitivity (`legit_bank_2way_macro`)

> **Sensitivity Caveat:** Collapsing 3 legitimate 2-way bank alert sub-templates (legit_bank_fraud_alert_yesno, legit_bank_security_alert_12, legit_bank_auth_alert_yn) into one single legit_bank_2way_macro archetype tests sensitivity to coarser template grouping; this is a sensitivity diagnostic only (fine-grained OOF remains primary).

| Grouping Variant | Group Count | Pooled OOF ROC-AUC | Pooled OOF PR-AUC | Pooled OOF Brier | Pooled OOF F1 ($P \ge 0.50$) | Fold Fraud Prevalence Range |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Fine-Grained Families** | 56 | 0.9563 | 0.8763 | 0.0676 | 0.7964 | `[0.2158, 0.2448]` |
| **Macro Bank 2-Way (`legit_bank_2way_macro`)** | 54 | 0.9321 | 0.7406 | 0.0839 | 0.7795 | `[0.1987, 0.2500]` |

## 10. Exploratory Threshold Sensitivity, Group-Aware Uncertainty & Assumed Cost Analysis (`SF-012` / `SF-012R` / `SF-012R.1`)

> **External Validation Blocker (`UNAVAILABLE_BLOCKED`):** No Class C primary external two-class fraud holdout exists (UNAVAILABLE_BLOCKED per SF-010/SF-011; no N=300 external holdout exists). Internal Dev/Val (N=400) and SF-009 grouped OOF (N=703, G=56 curated synthetic families) provide conditional sensitivity estimates only, not unconditional carrier CIs, population binomial bounds, independent threshold validation, or measured operational costs.

### Evidence Scope & Three-Tier Inference Boundaries

| Evidence | Permitted Interpretation |
|---|---|
| Dev/Val N=400 | Development/validation evidence; not independent holdout evidence |
| SF-009 grouped OOF N=703 | Conditional estimates on 56 curated synthetic families; not i.i.d. carrier traffic or untouched final test set |
| Cluster bootstrap percentiles (B=10000) | Conditional cluster-bootstrap sensitivity on curated 56 families (and unverified exchangeable-family reference only); not unconditional population CIs |
| Zero-event 7.78% / 9.41% calculation | Conditional mathematical reference assuming 37 i.i.d. benign families (violated in curated corpus); not a population binomial bound or message FPR |
| Threshold sweep & 72-ratio cost grid | Exploratory sensitivity under assumed linear ratios; not measured operational costs, and not independent threshold validation |
| Bayes PPV calculations | Modeled prevalence sensitivity; not observed production precision |
| Class C external holdout | Unavailable; external generalization remains unverified |

| Inference Target | Status | Scope & Statistical Condition |
|---|---|---|
| 1. Conditional uncertainty on curated 56-family collection | Supported | Intact-cluster resampling preserves within-family correlation and quantifies finite-corpus template dominance conditional on this fixed, hand-authored synthetic family set. |
| 2. Model-based exchangeable-family reference | Conditional mathematical reference only (assumption violated) | Interpreting bootstrap percentiles or 0/37 binomial limits as family-population bounds requires i.i.d. sampling from a benign/fraud template population—violated by shared banks, keywords, and size skew. |
| 3. Generalization to unseen real-world carrier SMS traffic | Unsupported (UNAVAILABLE_BLOCKED) | Requires an independently collected Class C carrier holdout with authentic message-level traffic shares. |

### Methodological Distinction (Exploratory Inspection vs. Independent Validation)

- **Threshold Sensitivity Analysis:** Exploratory inspection of TPR, FPR, group error concentration, Bayes PPV sensitivity, and illustrative assumed-cost rankings across candidate cutoffs tau in [0.30, 0.95] on internal Dev/Val (N=400) and grouped OOF (N=703).
- **Threshold Selection (Exploratory Only):** Inspecting multiple thresholds on OOF predictions and noting any candidate (e.g. tau=0.85) constitutes exploratory selection against that same OOF data; it cannot simultaneously serve as an unbiased confirmation of the chosen cutoff.
- **Independent Threshold Validation:** Unavailable (UNAVAILABLE_BLOCKED): requires frozen one-shot evaluation on an untouched qualified Class C external holdout, which does not exist.
- **Production Defaults & Provisional Status:** Production runtime defaults (`0.40` Tier-1 `FLAG`, `0.75` Tier-2 `BLOCK`) are unchanged. Any higher candidate such as `tau = 0.85` is strictly an unvalidated exploratory/provisional candidate for future Class C evaluation, NOT an empirically validated production optimum.

### Dev/Val Benchmark ($N = 400$, Non-Independent Development Suite) Descriptive Sweep

| $\tau$ | TP / FP / TN / FN | TPR | FPR (Descriptive Row 95% Wilson Upper) | Modeled PPV @ 0.2% | PPV @ 0.5% | PPV @ 1.0% | PPV @ 5.0% | PPV @ 50.0% |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `0.30` | 200/16/184/0 | 100.00% | 8.00% (`12.60%`) | 2.44% | 5.91% | 11.21% | 39.68% | 92.59% |
| `0.40` | 200/10/190/0 | 100.00% | 5.00% (`8.96%`) | 3.85% | 9.13% | 16.81% | 51.28% | 95.24% |
| `0.50` | 200/8/192/0 | 100.00% | 4.00% (`7.69%`) | 4.77% | 11.16% | 20.16% | 56.82% | 96.15% |
| `0.60` | 195/5/195/5 | 97.50% | 2.50% (`5.72%`) | 7.25% | 16.39% | 28.26% | 67.24% | 97.50% |
| `0.70` | 183/1/199/17 | 91.50% | 0.50% (`2.78%`) | 26.83% | 47.91% | 64.89% | 90.59% | 99.46% |
| `0.75` | 180/0/200/20 | 90.00% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.80` | 168/0/200/32 | 84.00% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.85` | 148/0/200/52 | 74.00% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.90` | 133/0/200/67 | 66.50% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.95` | 65/0/200/135 | 32.50% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

### `SF-009` Grouped OOF ($N = 703$, $G = 56$ Curated Families) Conditional Group-Aware Analysis

- **Curated Corpus Construction (`iid_population_draw_assumption_met=False`):** Closed collection of 56 manually assigned explicit_family archetypes in train_onnx_model.py (96 hand-written base/conversational seeds + 607 programmatic template instantiations). Nominally distinct families share authoring generators (8 US banks span 12 benign/fraud families; 3 two-way bank alert families share one syntax loop; fraud_urgent_brand_alert [35] + fraud_uk_bank_alert [30] form 40.6% of fraud rows; SF-007 phone-damage/P2P vocabulary spans 8-10 families with max_cross_family_centroid_cosine=0.478229).
- **Cluster Size Inequality:** `56` semantic families (`37` purely benign covering `543` messages, min=`2` / median=`6.0` / max=`53`, ratio=`26.5x`, top-3 share=`24.9%`; `19` purely fraud covering `160` messages, min=`2` / median=`4.0` / max=`35`, ratio=`17.5x`, top-3 share=`59.4%`; mixed-label groups=`0`).
- **Group-Concentration Finding:** At `tau = 0.60..0.80`, `100%` of OOF false positives (`40` at `0.60`, `27` at `0.70`, `13` at `0.75`, `4` at `0.80`) occur inside one benign family (`legit_bank_security_alert_12`), leaving `36 / 37` benign groups with `0` FPs.
- **Conditional Resampling & Zero-Event Reference Reassessment:** Intact-cluster percentile resampling (`B = 10000`, `seed = 42`) quantifies **conditional cluster-bootstrap sensitivity** on this curated 56-family set, NOT unconditional carrier population CIs. At `tau >= 0.85`, `0 / 37` benign groups fail: bootstrap degenerates (`None`), and `<= 7.78%` (`1 - 0.05**(1/37)`) / `<= 9.41%` Wilson (`<= 8.20%` under `35` macro-collapsed benign groups) is retained **strictly as a conditional mathematical reference** under an unmet i.i.d. binomial assumption—NOT a population confidence bound and NOT message-level carrier FPR.

| $\tau$ | TP/FP/TN/FN | TPR (Cond. Cluster 2.5-97.5%) | FPR | FP Benign Groups | Cond. Cluster 2.5-97.5% / Cond. Zero-Event Ref | Valid Boot Reps (TPR/FPR) | Row Wilson FPR Upper (Ref Only) |
|:---:|:---:|:---:|:---:|:---:|---|:---:|:---:|
| `0.30` | 157/46/497/3 | 98.12% (`[93.86%, 100.00%]`) | 8.47% | `6 / 37` | `[0.43%, 24.86%]` | 10000/10000 (undef 0/0) | `11.12%` |
| `0.40` | 156/44/499/4 | 97.50% (`[92.31%, 99.54%]`) | 8.10% | `5 / 37` | `[0.24%, 24.48%]` | 10000/10000 (undef 0/0) | `10.70%` |
| `0.50` | 153/41/502/7 | 95.62% (`[88.30%, 98.70%]`) | 7.55% | `2 / 37` | `[0.00%, 23.92%]` | 10000/10000 (undef 0/0) | `10.08%` |
| `0.60` | 147/41/502/13 | 91.88% (`[80.46%, 96.85%]`) | 7.55% | `2 / 37` | `[0.00%, 23.92%]` | 10000/10000 (undef 0/0) | `10.08%` |
| `0.70` | 132/27/516/28 | 82.50% (`[58.58%, 92.81%]`) | 4.97% | `1 / 37` (`legit_bank_security_alert_12`=27) | `[0.00%, 16.01%]` | 10000/10000 (undef 0/0) | `7.14%` |
| `0.75` | 118/13/530/42 | 73.75% (`[50.00%, 89.36%]`) | 2.39% | `1 / 37` (`legit_bank_security_alert_12`=13) | `[0.00%, 7.71%]` | 10000/10000 (undef 0/0) | `4.05%` |
| `0.80` | 100/4/539/60 | 62.50% (`[28.57%, 86.74%]`) | 0.74% | `1 / 37` (`legit_bank_security_alert_12`=4) | `[0.00%, 2.37%]` | 10000/10000 (undef 0/0) | `1.88%` |
| `0.85` | 92/0/543/68 | 57.50% (`[21.74%, 83.50%]`) | 0.00% | `0 / 37` | Degenerate (0 FP groups); Cond. math ref <= `7.78%` (CP) / `9.41%` (Wilson; `8.20%` at G=35) — NOT pop. bound or message FPR | 10000/10000 (undef 0/0) | `0.70%` |
| `0.90` | 77/0/543/83 | 48.12% (`[13.89%, 73.63%]`) | 0.00% | `0 / 37` | Degenerate (0 FP groups); Cond. math ref <= `7.78%` (CP) / `9.41%` (Wilson; `8.20%` at G=35) — NOT pop. bound or message FPR | 10000/10000 (undef 0/0) | `0.70%` |
| `0.95` | 63/0/543/97 | 39.38% (`[9.43%, 66.10%]`) | 0.00% | `0 / 37` | Degenerate (0 FP groups); Cond. math ref <= `7.78%` (CP) / `9.41%` (Wilson; `8.20%` at G=35) — NOT pop. bound or message FPR | 10000/10000 (undef 0/0) | `0.70%` |

#### Bootstrap Monte Carlo Seed & Replicate Sensitivity (`seeds = 42, 0, 7, 99, 2026`)

- Increasing `B` from `1000` to `10000` reduces Monte Carlo tail jitter across seeds (notably avoiding high-tail `seed=42, B=1000` edge draws like `50.00%` at `tau=0.75` or `30.53%` at `tau=0.80`), but larger `B` cannot cure small cluster count (`G_fraud=19`, `G_benign=37`) or non-i.i.d. curated construction.

| $\tau$ | `B=1000` TPR Low Seed Span | `B=10000` TPR Low Seed Span | `B=1000` FPR High Seed Span | `B=10000` FPR High Seed Span |
|:---:|:---:|:---:|:---:|:---:|
| `0.40` | `[91.80%, 92.68%]` (`0.88 pp`) | `[92.19%, 92.54%]` (`0.35 pp`) | `[23.51%, 24.45%]` (`0.94 pp`) | `[24.10%, 24.60%]` (`0.50 pp`) |
| `0.75` | `[48.32%, 51.11%]` (`2.79 pp`) | `[49.12%, 50.00%]` (`0.88 pp`) | `[7.40%, 7.81%]` (`0.41 pp`) | `[7.58%, 7.74%]` (`0.16 pp`) |
| `0.80` | `[26.91%, 30.83%]` (`3.92 pp`) | `[27.66%, 28.87%]` (`1.21 pp`) | `[2.28%, 2.40%]` (`0.13 pp`) | `[2.33%, 2.38%]` (`0.05 pp`) |
| `0.85` | `[20.63%, 22.98%]` (`2.35 pp`) | `[20.95%, 22.00%]` (`1.05 pp`) | Degenerate (`0/37` FP groups) | Degenerate (`0/37` FP groups) |

### Modeled Bayes Base-Rate PPV Sensitivity Scenarios (Illustrative Only — Not Observed Precision or PPV CIs)

- Actual deployment smishing prevalence $\pi$ is unknown without live carrier measurement. Zero observed OOF false positives (`0 / 543` in `0 / 37` groups) yields `100%` point PPV mechanically, whereas plausible non-zero FPRs dramatically lower precision (e.g., at `tau = 0.85`, `TPR = 57.50%`, `pi = 0.5%`, even descriptive row-level Wilson upper `0.70%` implies `29.14%` PPV, not `100%`).

| $\tau$ | Sensitivity Scenario | Assumed TPR | Assumed FPR | Modeled PPV @ 0.2% | PPV @ 0.5% | PPV @ 1.0% | PPV @ 5.0% |
|:---:|---|---:|---:|:---:|:---:|:---:|:---:|
| `0.40` | OOF point estimate | 97.50% | 8.10% | 2.35% | 5.70% | 10.84% | 38.77% |
| `0.40` | Point TPR + descriptive row Wilson FPR upper (ref only) | 97.50% | 10.70% | 1.79% | 4.38% | 8.43% | 32.41% |
| `0.75` | OOF point estimate | 73.75% | 2.39% | 5.81% | 13.40% | 23.73% | 61.85% |
| `0.75` | Point TPR + descriptive row Wilson FPR upper (ref only) | 73.75% | 4.05% | 3.52% | 8.38% | 15.53% | 48.92% |
| `0.80` | OOF point estimate | 62.50% | 0.74% | 14.53% | 29.89% | 46.15% | 81.70% |
| `0.80` | Point TPR + descriptive row Wilson FPR upper (ref only) | 62.50% | 1.88% | 6.25% | 14.32% | 25.15% | 63.65% |
| `0.85` | OOF point estimate | 57.50% | 0.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.85` | Point TPR + descriptive row Wilson FPR upper (ref only) | 57.50% | 0.70% | 14.09% | 29.14% | 45.26% | 81.16% |
| `0.85` | Cluster 2.5% TPR + descriptive row Wilson FPR upper | 21.74% | 0.70% | 5.84% | 13.46% | 23.81% | 61.96% |
| `0.85` | Cluster 2.5% TPR + illustrative 0.5% tail FPR stress | 21.74% | 0.50% | 8.01% | 17.93% | 30.52% | 69.59% |

### Illustrative Assumed Cost-Ratio Sensitivity (12 Named Scenarios + 72-Pair Orthogonal Ratio Grid)

- **Cost Evidence Distinction:** (1) *Mathematical cost under assumed ratios* is computed below as an illustrative normalized sensitivity check only (units are NOT euros, churn dollars, or carrier expenses); (2) *Empirically measured operational cost* is unavailable; (3) *Operational policy decisions* require both measured costs and independent Class C validation.
- **Structural Objective & Scenario-Coverage Finding (`cost_assumption_sensitive = True`):** Across the expanded 72-pair dimensionless cost grid (`576` `(C_FN/C_T1, C_T2/C_T1, pi)` cells), single-threshold optima vary even at low prevalence (`pi=0.5%`: `[0.30, 0.50, 0.85]`; `pi=1.0%`: `[0.30, 0.40, 0.50, 0.75, 0.85]`), proving the earlier `9/9` `[0.85]` result at `pi <= 1%` was an artifact of inspecting too narrow a scenario set. Moreover, compute_dual_tier_cost_per_1000 models only Tier-1 fraud escape and differential Tier-2 FP cost (C_T2 - C_T1) * (1 - pi) * FPR(t2); it assigns zero additional fraud-mitigation benefit to immediate wire blocking over async review, mechanically favoring any threshold with observed FPR=0 such as tau=0.85 whenever FPR(0.85)=0.

| Assumed Cost Scenario `(C_FN, C_T1_FP, C_T2_FP)` | $\pi=0.2\%$ Single / Dual Top | $\pi=0.5\%$ Single / Dual Top | $\pi=1.0\%$ Single / Dual Top | $\pi=5.0\%$ Single / Dual Top |
|---|---|---|---|---|
| `assumed_baseline_10_1_50` `(10, 1, 50)` | `0.85` (8.50) / `(0.85, 0.85)` (8.50) | `0.85` (21.25) / `(0.85, 0.85)` (21.25) | `0.85` (42.50) / `(0.85, 0.85)` (42.50) | `0.85` (212.50) / `(0.40, 0.85)` (89.48) |
| `high_review_congestion_2_2_50` `(2, 2, 50)` | `0.85` (1.70) / `(0.85, 0.85)` (1.70) | `0.85` (4.25) / `(0.85, 0.85)` (4.25) | `0.85` (8.50) / `(0.85, 0.85)` (8.50) | `0.85` (42.50) / `(0.85, 0.85)` (42.50) |
| `scarce_triage_10_10_100` `(10, 10, 100)` | `0.85` (8.50) / `(0.85, 0.85)` (8.50) | `0.85` (21.25) / `(0.85, 0.85)` (21.25) | `0.85` (42.50) / `(0.85, 0.85)` (42.50) | `0.85` (212.50) / `(0.85, 0.85)` (212.50) |
| `extreme_escape_low_block_250_1_5` `(250, 1, 5)` | `0.85` (212.50) / `(0.40, 0.85)` (93.37) | `0.50` (430.33) / `(0.30, 0.85)` (107.73) | `0.40` (463.60) / `(0.30, 0.85)` (130.74) | `0.30` (636.77) / `(0.30, 0.85)` (314.85) |
| `low_block_high_escape_50_1_5` `(50, 1, 5)` | `0.85` (42.50) / `(0.85, 0.85)` (42.50) | `0.85` (106.25) / `(0.50, 0.85)` (86.07) | `0.85` (212.50) / `(0.40, 0.85)` (92.72) | `0.40` (447.40) / `(0.30, 0.85)` (127.35) |
| `moderate_block_high_escape_25_1_10` `(25, 1, 10)` | `0.85` (21.25) / `(0.85, 0.85)` (21.25) | `0.85` (53.12) / `(0.85, 0.85)` (53.12) | `0.85` (106.25) / `(0.50, 0.85)` (85.69) | `0.85` (531.25) / `(0.30, 0.85)` (103.92) |
| `low_escape_baseline_block_2_1_50` `(2, 1, 50)` | `0.85` (1.70) / `(0.85, 0.85)` (1.70) | `0.85` (4.25) / `(0.85, 0.85)` (4.25) | `0.85` (8.50) / `(0.85, 0.85)` (8.50) | `0.85` (42.50) / `(0.85, 0.85)` (42.50) |
| `equal_escape_block_50_1_50` `(50, 1, 50)` | `0.85` (42.50) / `(0.85, 0.85)` (42.50) | `0.85` (106.25) / `(0.50, 0.85)` (86.07) | `0.85` (212.50) / `(0.40, 0.85)` (92.72) | `0.85` (1062.50) / `(0.30, 0.85)` (127.35) |
| `high_escape_100_1_50` `(100, 1, 50)` | `0.85` (85.00) / `(0.75, 0.85)` (76.39) | `0.85` (212.50) / `(0.40, 0.85)` (93.13) | `0.85` (425.00) / `(0.30, 0.85)` (102.62) | `0.85` (2125.00) / `(0.30, 0.85)` (174.23) |
| `high_block_250_1_250` `(10, 1, 250)` | `0.85` (8.50) / `(0.85, 0.85)` (8.50) | `0.85` (21.25) / `(0.85, 0.85)` (21.25) | `0.85` (42.50) / `(0.85, 0.85)` (42.50) | `0.85` (212.50) / `(0.40, 0.85)` (89.48) |
| `extreme_block_5_1_500` `(5, 1, 500)` | `0.85` (4.25) / `(0.85, 0.85)` (4.25) | `0.85` (10.62) / `(0.85, 0.85)` (10.62) | `0.85` (21.25) / `(0.85, 0.85)` (21.25) | `0.85` (106.25) / `(0.50, 0.85)` (82.67) |
| `high_review_overhead_10_5_50` `(10, 5, 50)` | `0.85` (8.50) / `(0.85, 0.85)` (8.50) | `0.85` (21.25) / `(0.85, 0.85)` (21.25) | `0.85` (42.50) / `(0.85, 0.85)` (42.50) | `0.85` (212.50) / `(0.85, 0.85)` (212.50) |

#### Orthogonal 72-Ratio Cost Grid Coverage (`C_FN/C_T1 in 0.5..250`, `C_T2/C_T1 in 2..500`, `C_T1=1`)

| Prevalence $\pi$ | Distinct Winning Single Thresholds (72 Pairs) | Single Winner Distribution | Distinct Winning Dual `(t1, t2)` Policies | Dual Policy Distribution |
|:---:|---|---|---|---|
| `0.1%` | `0.85` | `0.85`:72 | `(0.50, 0.85), (0.85, 0.85)` | `(0.50, 0.85)`:8, `(0.85, 0.85)`:64 |
| `0.2%` | `0.50, 0.85` | `0.50`:1, `0.85`:71 | `(0.40, 0.85), (0.75, 0.85), (0.85, 0.85)` | `(0.40, 0.85)`:8, `(0.75, 0.85)`:8, `(0.85, 0.85)`:56 |
| `0.5%` | `0.30, 0.50, 0.85` | `0.30`:1, `0.50`:2, `0.85`:69 | `(0.30, 0.85), (0.40, 0.85), (0.50, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:8, `(0.40, 0.85)`:8, `(0.50, 0.85)`:8, `(0.85, 0.85)`:48 |
| `1.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:1, `0.40`:2, `0.50`:2, `0.75`:1, `0.85`:66 | `(0.30, 0.85), (0.40, 0.85), (0.50, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:16, `(0.40, 0.85)`:8, `(0.50, 0.85)`:8, `(0.85, 0.85)`:40 |
| `2.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:3, `0.40`:3, `0.50`:1, `0.75`:3, `0.85`:62 | `(0.30, 0.85), (0.40, 0.85), (0.75, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:24, `(0.40, 0.85)`:8, `(0.75, 0.85)`:8, `(0.85, 0.85)`:32 |
| `5.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:7, `0.40`:3, `0.50`:4, `0.75`:1, `0.85`:57 | `(0.30, 0.85), (0.40, 0.85), (0.50, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:32, `(0.40, 0.85)`:8, `(0.50, 0.85)`:8, `(0.85, 0.85)`:24 |
| `10.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:10, `0.40`:5, `0.50`:3, `0.75`:3, `0.85`:51 | `(0.30, 0.85), (0.40, 0.85), (0.75, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:40, `(0.40, 0.85)`:8, `(0.75, 0.85)`:8, `(0.85, 0.85)`:16 |
| `50.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:28, `0.40`:8, `0.50`:2, `0.75`:6, `0.85`:28 | `(0.30, 0.85), (0.40, 0.85)` | `(0.30, 0.85)`:64, `(0.40, 0.85)`:8 |

#### Sensitivity to Observed `FPR(0.85)=0` Artifact (`10:1:50` at $\pi = 0.5\%$)

| Assumed Floor FPR for $\tau \ge 0.85$ | Best Single Threshold | Best Single Cost/1k | Best Dual `(t1, t2)` | Best Dual Cost/1k |
|---|:---:|---:|:---:|---:|
| `observed_zero_fpr` (`0.0000%`) | `0.85` | 21.25 | `(0.85, 0.85)` | 21.25 |
| `tail_stress_0_5pct` (`0.5000%`) | `0.85` | 270.00 | `(0.85, 0.85)` | 270.00 |
| `row_wilson_upper_0_7025pct` (`0.7025%`) | `0.85` | 370.74 | `(0.85, 0.85)` | 370.74 |
| `plausible_2_0pct_below_family_bound` (`2.0000%`) | `0.80` | 385.21 | `(0.75, 0.80)` | 396.08 |

## 11. Adversarial Perturbation & Component Ablation Matrix (`SF-013` / `SF-013 Remediation`)

> **Diagnostic Scope (`UNAVAILABLE_BLOCKED`):** Evaluates frozen ONNX `ML-only` (unmodified), remediated `Heuristics-only`, and `Composite` scoring across 10 canonical smishing archetypes under 5 controlled obfuscation/shift perturbations plus 10 benign near-miss contrastive controls (`0` SHA-256 overlap with Train/DevVal). This is a controlled synthetic diagnostic suite—not an external real-world Class C carrier evaluation.

| Cohort / Perturbation Family | Class / Metric | Samples | ML ($P \ge 0.40$) | ML ($P \ge 0.50$) | Heuristics ($H \ge 0.40$ / $0.50$) | Composite Tier 1 ($S \ge 0.40$) | Composite Tier 2 ($S \ge 0.75$) | Mean $(P, H, S)$ |
|---|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Canonical Smishing Baseline (Unperturbed) | FRAUD (Recall) | 10 | 100.0% | 100.0% | 100.0% / 100.0% | 100.0% | 90.0% | `0.8134 / 0.7720 / 0.9289` |
| 1. Unseen Institution & Brand Substitution | FRAUD (Recall) | 10 | 100.0% | 100.0% | 100.0% / 100.0% | 100.0% | 90.0% | `0.8137 / 0.7720 / 0.9260` |
| 2. URL Domain & Shortener Rotation | FRAUD (Recall) | 10 | 90.0% | 90.0% | 80.0% / 80.0% | 100.0% | 90.0% | `0.7379 / 0.7110 / 0.9304` |
| 3. Cyrillic Homoglyph Substitution | FRAUD (Recall) | 10 | 80.0% | 70.0% | 100.0% / 100.0% | 100.0% | 70.0% | `0.5172 / 0.8200 / 0.8844` |
| 4. Leetspeak & Intra-Word Punctuation Splitting | FRAUD (Recall) | 10 | 100.0% | 100.0% | 60.0% / 60.0% | 100.0% | 70.0% | `0.7201 / 0.4630 / 0.7731` |
| 5. Whitespace, Casing & Control-Char Injection | FRAUD (Recall) | 10 | 100.0% | 100.0% | 100.0% / 100.0% | 100.0% | 90.0% | `0.8101 / 0.7720 / 0.9326` |
| 6. Benign Near-Miss Contrastive Controls | BENIGN (FPR) | 10 | 20.0% | 20.0% | 0.0% / 0.0% | 20.0% | 0.0% | `0.1478 / 0.0400 / 0.1478` |

### Pre-Remediation (`afae166`) vs. Remediated Comparison

| Cohort | Baseline ($P/H/S$) | Original `afae166` ($H \ge 0.50$ / $S \ge 0.40$ / $S \ge 0.75$) | Remediated ($H \ge 0.50$ / $S \ge 0.40$ / $S \ge 0.75$) | Remediated Mean $(P, H, S)$ |
|---|---|:---:|:---:|:---:|
| Canonical Smishing Baseline (Unperturbed) | `0.8110/0.7720/0.9284` | 100.0% / 100.0% / 90.0% | 100.0% / 100.0% / 90.0% | `0.8134 / 0.7720 / 0.9289` |
| 1. Unseen Institution & Brand Substitution | `0.8110/0.7720/0.9284` | 100.0% / 100.0% / 90.0% | 100.0% / 100.0% / 90.0% | `0.8137 / 0.7720 / 0.9260` |
| 2. URL Domain & Shortener Rotation | `0.8110/0.7720/0.9284` | 80.0% / 100.0% / 90.0% | 80.0% / 100.0% / 90.0% | `0.7379 / 0.7110 / 0.9304` |
| 3. Cyrillic Homoglyph Substitution | `0.8110/0.7720/0.9284` | 0.0% / 80.0% / 10.0% | 100.0% / 100.0% / 70.0% | `0.5172 / 0.8200 / 0.8844` |
| 4. Leetspeak & Intra-Word Punctuation Splitting | `0.8110/0.7720/0.9284` | 60.0% / 100.0% / 70.0% | 60.0% / 100.0% / 70.0% | `0.7201 / 0.4630 / 0.7731` |
| 5. Whitespace, Casing & Control-Char Injection | `0.8110/0.7720/0.9284` | 100.0% / 100.0% / 90.0% | 100.0% / 100.0% / 90.0% | `0.8101 / 0.7720 / 0.9326` |
| 6. Benign Near-Miss Contrastive Controls | `0.8110/0.7720/0.9284` | 0.0% / 20.0% / 0.0% | 0.0% / 20.0% / 0.0% | `0.1478 / 0.0400 / 0.1478` |

### Benign Near-Miss ML Tier-1 False-Positive Investigation (`Unresolved TF-IDF Limitation`)

| Control ID | $(P, H, S)$ | Heuristic Signals | Top Fraud-Pushing TF-IDF Tokens | Diagnosis |
|---|---|---|---|---|
| `benign_tax_prep_1099` | `0.6043 / 0.00 / 0.6043` | `[]` | please (+0.1915), before (+0.1072), portal (+0.0881), irs (+0.0608) | Unigrams seen predominantly in phishing lures (please/before/portal/irs) outweigh benign-associated tokens ('your', 'friday'), while domain words ('W-2', '1099', 'CPA') are absent from the 703-sample training vocabulary; heuristics hold H=0.00 (no BLOCK). |
| `benign_courthouse_jury` | `0.6392 / 0.00 / 0.6392` | `[]` | fee (+0.1668), been (+0.1478), has been (+0.1169), notice (+0.1151) | Bag-of-words TF-IDF lacks syntactic negation scope over 'no fee required' ('fee' +0.1668 outweighs 'no' -0.1060); heuristics match zero extortion rules (H=0.00). |

### Diagnostic Ablation Takeaways & Supported Homoglyph Scope

- **Word-Level TF-IDF Generalization vs. Token-Splitting Degradation:** The frozen ONNX TfidfVectorizer uses word regex token_pattern='\\b[a-zA-Z0-9_]+\\b'; substituting non-ASCII Cyrillic codepoints or inserting intra-word dots/digits/zero-width characters pushes fraud signals out of vocabulary and breaks bigrams (mean P drops from 0.8134 to 0.5172 on Cyrillic homoglyphs and 0.7201 on leetspeak/splitting).
- **Heuristic Normalization Defense-in-Depth & Homoglyph Mitigation:** normalize_heuristic_text() now strips zero-width formatting characters, applies NFKC decomposition, and collapses consecutive whitespace runs to single spaces—fixing the literal-space SIM-swap fragility (H>=0.50 recall=1.00, mean H matches baseline 0.7720). Additionally, detect_and_normalize_cyrillic_homoglyphs() + RULE:HOMOGLYPH_OBFUSCATION (0.45) detect mixed-script spoofing without touching natural Cyrillic prose, lifting Cyrillic heuristics recall from 0.00 to 1.00 (mean H=0.8200) and Composite Tier-1 / Tier-2 from 0.80 / 0.10 to 1.00 / 0.70. Leetspeak/dot-splitting still degrades exact-word regexes (heuristics recall=0.60) cleanly without threshold tuning.
- **Enumerated Homoglyph Scope:** Covers the 24 enumerated Cyrillic-to-Latin visual lookalikes only; does not cover Greek, Cherokee, mathematical, or arbitrary Unicode confusable blocks, and preserves natural pure-Cyrillic and bilingual prose untouched without heuristic flags.
- **Contrastive Benign Control Precision:** On benign near-miss controls overlapping legal/tax/postal nouns, ML-only flags 20.0% (2/10: tax prep & jury duty controls) into Tier-1 review while heuristics trigger 0.0% FPR and Composite Tier-2 blocks 0.0%.

# SentinelPulse Empirical ML Development & Validation Benchmark Report (Dev/Val N=400)

> **Reproducibility Stamp:** All metrics, confusion matrices, and breakdowns are generated directly from execution against the compiled ONNX model artifact and development/validation benchmark suite (N = 400). Zero simulated or synthetic figures.

## 1. Reproducibility & Environment Stamp

- **Model Artifact:** `sms_fraud_model.onnx` (194.85 KB)
- **Model SHA-256:** `d330466e8a28e43e4d8452fdef76f64470429851f19c568ea83399e7d16beaa9`
- **Evaluation Dataset SHA-256:** `210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03`
- **Canonical 400-Row Predictions Artifact:** `benchmark_predictions_400.json`
- **Canonical 400-Row Predictions SHA-256:** `66dc4862190c597f158298f199e9173f32901fd3ed916487a681c948a635d29e`
- **Timestamp:** `2026-11-11T23:50:09.080495+00:00`
- **Evaluator Engine:** `ONNXRuntime-CPU (AVX-512)`
- **Software Versions:** `onnxruntime=1.31.0`, `numpy=2.5.4`, `scikit-learn=1.9.1`
- **Dataset Size:** 400 samples (200 Benign, 200 Fraud)

### ONNX vs. Scikit-Learn Numerical & Operational Parity (N = 400)

- **Max TF-IDF Vector Absolute Diff:** `6.0295240800e-08`
- **Mean TF-IDF Vector Absolute Diff:** `2.2485954916e-08`
- **Max Calibrated Probability Absolute Diff ($|P_{\text{sklearn}} - P_{\text{onnx}}|$):** `1.0378382087e-07`
- **Mean Calibrated Probability Absolute Diff:** `2.0879723874e-08`
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
| **ROC-AUC** | **0.9970** | Area under ROC curve across all possible decision thresholds |
| **PR-AUC** | **0.9970** | Precision-Recall curve area (robust under class skew) |
| **Brier Score** | **0.0371** | Probability calibration loss (lower is better, calibrated < 0.10) |
| **Precision (P >= 0.50)** | **96.46%** | True fraud / (True fraud + False alarms) |
| **Recall (P >= 0.50)** | **95.50%** | True fraud caught / Total actual fraud |
| **F1-Score** | **0.9598** | Harmonic mean of precision and recall |
| **False Positive Rate (FPR)** | **3.50%** | Benign messages incorrectly flagged |
| **False Negative Rate (FNR)** | **4.50%** | Fraud messages that evaded detection |

## 3. Dual-Threshold Operational Tiers

| Operational Tier | Threshold | Purpose | Recall | Precision | FPR | Confusion Matrix |
|---|:---:|---|:---:|:---:|:---:|---|
| **Tier 1: Escalation Queue** | $S \ge 0.40$ | Async SentinelFlow Review | **100.00%** | **95.24%** | **5.00%** | TP=200, FP=10, TN=190, FN=0 |
| **Tier 2: Immediate Wire Drop** | $S \ge 0.75$ | Synchronous Wire Drop | **89.50%** | **100.00%** | **0.00%** | TP=179, FP=0, TN=200, FN=21 |

## 4. Component Ablation Study (ML vs. Heuristics vs. Combined)

| Strategy | Metric Floor / Threshold | Recall | Precision | FPR | F1-Score | Architectural Role |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **ML Model Alone** | $P \ge 0.50$ | 95.50% | 96.46% | 3.50% | 0.9598 | Statistical semantic pattern recognition |
| **Heuristics Alone** | $H \ge 0.50$ | 81.00% | 100.00% | 0.00% | 0.8950 | Deterministic regex rule triggers |
| **Combined (Tier 1)** | $S \ge 0.40$ | 100.00% | 95.24% | 5.00% | 0.9756 | Zero FN guarantee for human escalation |
| **Combined (Tier 2)** | $S \ge 0.75$ | 89.50% | 100.00% | 0.00% | 0.9446 | High-precision wire drop (>98.5% precision) |

## 5. Fine-Grained Category-Level Performance Breakdown

| Category | Class | Samples | Mean P | Mean H | Mean S | Pure ML (P>=0.50) | Heuristics (H>=0.50) | Tier 1 (S>=0.40) | Tier 2 (S>=0.75) | Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| Bank Fraud Alerts (YES/NO) | BENIGN | 25 | 0.0109 | 0.0000 | 0.0109 | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | PASSED |
| Carrier Usage & Roaming Notices | BENIGN | 25 | 0.0753 | 0.0000 | 0.0753 | 1/25 (4.0%) | 0/25 (0.0%) | 2/25 (8.0%) | 0/25 (0.0%) | PASSED |
| Clinical Appointments & Billing | BENIGN | 25 | 0.0492 | 0.0000 | 0.0492 | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | 0/25 (0.0%) | PASSED |
| 2FA & OTP Authentication Codes | BENIGN | 25 | 0.0705 | 0.0000 | 0.0705 | 1/25 (4.0%) | 0/25 (0.0%) | 1/25 (4.0%) | 0/25 (0.0%) | PASSED |
| Package Delivery Status Updates | BENIGN | 25 | 0.0956 | 0.1680 | 0.0998 | 2/25 (8.0%) | 0/25 (0.0%) | 2/25 (8.0%) | 0/25 (0.0%) | PASSED |
| Retail Receipts & Curbside Pickups | BENIGN | 25 | 0.0512 | 0.0080 | 0.0512 | 0/25 (0.0%) | 0/25 (0.0%) | 1/25 (4.0%) | 0/25 (0.0%) | PASSED |
| Legitimate Crypto Exchange Notices | BENIGN | 25 | 0.1580 | 0.0000 | 0.1580 | 3/25 (12.0%) | 0/25 (0.0%) | 3/25 (12.0%) | 0/25 (0.0%) | PASSED |
| Conversational & P2P Messages | BENIGN | 25 | 0.0724 | 0.0000 | 0.0724 | 0/25 (0.0%) | 0/25 (0.0%) | 1/25 (4.0%) | 0/25 (0.0%) | PASSED |
| Bank Account Suspension Panic Lures | FRAUD | 30 | 0.8715 | 0.8200 | 1.0000 | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | PASSED |
| Parcel Delivery Customs Fee Scams | FRAUD | 30 | 0.8490 | 0.7700 | 0.9110 | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | PASSED |
| Tax & Court Legal Extortion Threats | FRAUD | 30 | 0.8194 | 0.8320 | 1.0000 | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | 30/30 (100.0%) | PASSED |
| Cryptocurrency Giveaway & Seed Scams | FRAUD | 25 | 0.7899 | 0.6860 | 0.8837 | 25/25 (100.0%) | 20/25 (80.0%) | 25/25 (100.0%) | 25/25 (100.0%) | PASSED |
| Broken Phone Family WhatsApp Lures | FRAUD | 25 | 0.8775 | 0.7500 | 0.9262 | 25/25 (100.0%) | 25/25 (100.0%) | 25/25 (100.0%) | 25/25 (100.0%) | PASSED |
| Fake DocuSign & Invoice Scams | FRAUD | 25 | 0.7147 | 0.5620 | 0.7959 | 20/25 (80.0%) | 15/25 (60.0%) | 25/25 (100.0%) | 15/25 (60.0%) | PASSED |
| Homoglyph & Leetspeak Obfuscation | FRAUD | 20 | 0.7930 | 0.4580 | 0.8327 | 20/20 (100.0%) | 8/20 (40.0%) | 20/20 (100.0%) | 19/20 (95.0%) | PASSED |
| Zero-Link Call-Back Impersonation | FRAUD | 15 | 0.6340 | 0.1867 | 0.7011 | 11/15 (73.3%) | 4/15 (26.7%) | 15/15 (100.0%) | 5/15 (33.3%) | PASSED |

## 6. Error Analysis Summary

- **Tier 1 False Positives ($S \ge 0.40$, Benign):** 10 samples
- **Tier 2 False Positives ($S \ge 0.75$, Benign):** 0 samples
- **Tier 1 False Negatives ($S < 0.40$, Fraud):** 0 samples (Zero Escaped Attacks)
- **Tier 2 False Negatives ($S < 0.75$, Fraud):** 21 samples (Safely caught in Tier 1 queue)

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
1. **Monotonic Non-Decreasing Property:** $\frac{\partial S_{\text{composite}}}{\partial P} \ge 0$, $\frac{\partial S_{\text{composite}}}{\partial H} \ge 0$, and $\frac{\partial S_{\text{composite}}}{\partial V} \ge 0$ everywhere on $[0, 1]^3$. Output is strictly bounded within $[0.0, 1.0]$. Terminology note: the function is strictly *monotonic non-decreasing* rather than strictly monotonic due to the flat boundary plateau where $H \ge 0.80$ forces $S_{\text{composite}} = 1.0$.
2. **Benign Indicator Suppression:** When $H \le 0.25$ and $P < 0.30$, $\alpha(P, H) = 0.0$ and $S_{\text{content}} = P < 0.30 < 0.40$, strictly avoiding false-positive customer friction.
3. **Authoritative Heuristic Override ($H \ge 0.80$):** High-confidence threat rules immediately override to $S_{\text{composite}} = 1.0$ (`BLOCK`). `RULE:TAX_ARREST_THREAT` ($H = 0.80$) is the explicit rule capable of triggering an immediate standalone override block. High-severity rules with base score $\ge 0.70$ (e.g. `URGENT_ACCOUNT_LOCKOUT`, `UNPAID_TOLL_INVOICE`) reach $\ge 0.82$ via compound rule escalation (+0.12 boost) when paired with a secondary risk signal.
4. **Individual Heuristic Threshold Clarification ($H = 0.65$):** A heuristic score of $H = 0.65$ (e.g. `RULE:DELIVERY_FEE_SCAM`, `RULE:WORK_FROM_HOME_SCAM`) does *not* force Tier 1 escalation ($S_{\text{composite}} \ge 0.40$) on its own when ML suspicion is zero ($P = 0.0, V = 0.0$). At $P = 0.0$, $W_H = 0.3325$ and $S_{\text{composite}} = 0.3325 < 0.40$ (`ALLOW`). Escalation to Tier 1 without velocity requires baseline ML suspicion $P \ge 0.1012$.

## 8. Calibration Diagnostics (10-Bin ECE) & 95% Wilson Confidence Intervals (Dev/Val N=400)

- **Expected Calibration Error (ECE, 10 equal-width bins):** `0.102692`
- **Max Calibration Error (MCE):** `0.244714`
- **Brier Score:** `0.037100`
- **Binning Scheme:** `equal_width_half_open_final_closed` (`[lower, upper)` for bins 0..8; `[0.9, 1.0]` closed for bin 9)

### 10-Bin Reliability Table (Dev/Val N=400)

| Bin | Interval | Count | Mean $P_{\text{onnx}}$ | Empirical Fraud Rate | $|\text{Gap}|$ |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 0 | `[0.0, 0.1)` | 158 | 0.0139 | 0.0000 | 0.0139 |
| 1 | `[0.1, 0.2)` | 14 | 0.1425 | 0.0000 | 0.1425 |
| 2 | `[0.2, 0.3)` | 14 | 0.2447 | 0.0000 | 0.2447 |
| 3 | `[0.3, 0.4)` | 8 | 0.3207 | 0.5000 | 0.1793 |
| 4 | `[0.4, 0.5)` | 8 | 0.4511 | 0.6250 | 0.1739 |
| 5 | `[0.5, 0.6)` | 5 | 0.5550 | 0.4000 | 0.1550 |
| 6 | `[0.6, 0.7)` | 14 | 0.6649 | 0.7857 | 0.1208 |
| 7 | `[0.7, 0.8)` | 18 | 0.7551 | 0.9444 | 0.1893 |
| 8 | `[0.8, 0.9)` | 161 | 0.8462 | 1.0000 | 0.1538 |
| 9 | `[0.9, 1.0]` | 0 | N/A (empty) | N/A (empty) | N/A |

### Message-Level 95% Wilson Binomial Confidence Intervals ($z = 1.95996$)

> **Independence Caveat:** Message-level Wilson intervals treat individual Dev/Val messages as independent Bernoulli trials. Consult Section 9 semantic-family cluster bootstrap intervals for family-level correlation uncertainty on the training corpus.

| Operational Metric | Point Estimate | 95% Wilson CI |
|---|:---:|:---:|
| **Raw ML Precision ($P \ge 0.50$)** | 96.46% | `[92.88%, 98.28%]` |
| **Raw ML Recall ($P \ge 0.50$)** | 95.50% | `[91.67%, 97.61%]` |
| **Tier 1 Precision (`S >= 0.40`)** | 95.24% | `[91.46%, 97.39%]` |
| **Tier 1 Recall (`S >= 0.40`)** | 100.00% | `[98.12%, 100.00%]` |
| **Tier 1 False Positive Rate (`S >= 0.40`)** | 5.00% | `[2.74%, 8.96%]` |
| **Tier 2 Precision (`S >= 0.75`)** | 100.00% | `[97.90%, 100.00%]` |
| **Tier 2 Recall (`S >= 0.75`)** | 89.50% | `[84.48%, 93.03%]` |
| **Tier 2 False Positive Rate (`S >= 0.75`)** | 0.00% | `[0.00%, 1.88%]` |

## 9. Zero-Leakage Nested 5-Fold OOF Cross-Validation & Macro-Archetype Sensitivity (`SF-009`)

- **Protocol:** `Nested 5-fold StratifiedGroupKFold outer/inner with Pipeline(TfidfVectorizer -> LogisticRegression) fitted strictly inside inner calibration splits (zero vocabulary leakage)`
- **Production Export Calibration:** `GroupKFold(n_splits=5)` (group overlap = `0`)
- **OOF Completeness:** `703 / 703` samples covered, duplicates=`0`, max group overlap across all outer & inner splits=`0` / `0`
- **OOF Artifact:** `oof_predictions.json` (`sha256=9b6376520d0161e6969646a07d98babc00231e51f166d9149e18b567bd163265`)

### Fine-Grained Semantic Families (56 Families, Out-of-Fold Pooled & Per-Fold Summary)

- **Per-Fold Pure-ML Mean ± Std ($P \ge 0.50$, 5 folds):** ROC-AUC `0.9427 ± 0.0867`, PR-AUC `0.8983 ± 0.1609`, Brier `0.0679 ± 0.0708`, F1 `0.8256 ± 0.2423`
- **Pooled OOF Pure-ML ($P \ge 0.50$):** ROC-AUC `0.9559`, PR-AUC `0.8751`, Brier `0.0678`, ECE `0.091364`, Precision `76.30%`, Recall `82.50%`, F1 `0.7928`
- **Pooled OOF Composite ($V = 0.0$ offline invariant):** Tier 1 (`S >= 0.40`) Precision `78.00%`, Recall `97.50%`, FPR `8.10%`; Tier 2 (`S >= 0.75`) Precision `90.00%`, Recall `73.12%`, FPR `2.39%`

### Semantic-Family Cluster Bootstrap 95% CIs (`nonparametric_cluster_percentile_bootstrap`, `B=1000`, `seed=42`, `G=56` clusters)

| Pooled OOF Pure-ML Metric | Point Estimate | Cluster Bootstrap 95% CI | Message-Level Wilson 95% CI | Undefined Replicates |
|---|:---:|:---:|:---:|:---:|
| **ROC-AUC** | `0.9559` | `[0.8654, 0.9960]` | `N/A (non-binomial)` | 0 |
| **PR-AUC** | `0.8751` | `[0.5437, 0.9919]` | `N/A (non-binomial)` | 0 |
| **Brier Score** | `0.0678` | `[0.0253, 0.1371]` | `N/A (non-binomial)` | 0 |
| **Precision (P >= 0.50)** | `0.7630` | `[0.3844, 1.0000]` | `[69.44%, 82.02%]` | 0 |
| **Recall (P >= 0.50)** | `0.8250` | `[0.5975, 0.9283]` | `[75.87%, 87.61%]` | 0 |
| **F1 (P >= 0.50)** | `0.7928` | `[0.4933, 0.9492]` | `N/A (non-binomial)` | 0 |

### Macro-Archetype Sensitivity (`legit_bank_2way_macro`)

> **Sensitivity Caveat:** Collapsing 3 legitimate 2-way bank alert sub-templates (legit_bank_fraud_alert_yesno, legit_bank_security_alert_12, legit_bank_auth_alert_yn) into one single legit_bank_2way_macro archetype tests sensitivity to coarser template grouping; this is a sensitivity diagnostic only (fine-grained OOF remains primary).

| Grouping Variant | Group Count | Pooled OOF ROC-AUC | Pooled OOF PR-AUC | Pooled OOF Brier | Pooled OOF F1 ($P \ge 0.50$) | Fold Fraud Prevalence Range |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Fine-Grained Families** | 56 | 0.9559 | 0.8751 | 0.0678 | 0.7928 | `[0.2158, 0.2448]` |
| **Macro Bank 2-Way (`legit_bank_2way_macro`)** | 54 | 0.9309 | 0.7330 | 0.0842 | 0.7831 | `[0.1987, 0.2500]` |

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
| `0.30` | 200/14/186/0 | 100.00% | 7.00% (`11.41%`) | 2.78% | 6.70% | 12.61% | 42.92% | 93.46% |
| `0.40` | 200/10/190/0 | 100.00% | 5.00% (`8.96%`) | 3.85% | 9.13% | 16.81% | 51.28% | 95.24% |
| `0.50` | 200/7/193/0 | 100.00% | 3.50% (`7.05%`) | 5.42% | 12.55% | 22.40% | 60.06% | 96.62% |
| `0.60` | 196/4/196/4 | 98.00% | 2.00% (`5.03%`) | 8.94% | 19.76% | 33.11% | 72.06% | 98.00% |
| `0.70` | 184/1/199/16 | 92.00% | 0.50% (`2.78%`) | 26.94% | 48.04% | 65.02% | 90.64% | 99.46% |
| `0.75` | 179/0/200/21 | 89.50% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.80` | 170/0/200/30 | 85.00% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.85` | 149/0/200/51 | 74.50% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.90` | 130/0/200/70 | 65.00% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.95` | 65/0/200/135 | 32.50% | 0.00% (`1.88%`) | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

### `SF-009` Grouped OOF ($N = 703$, $G = 56$ Curated Families) Conditional Group-Aware Analysis

- **Curated Corpus Construction (`iid_population_draw_assumption_met=False`):** Closed collection of 56 manually assigned explicit_family archetypes in train_onnx_model.py (96 hand-written base/conversational seeds + 607 programmatic template instantiations). Nominally distinct families share authoring generators (8 US banks span 12 benign/fraud families; 3 two-way bank alert families share one syntax loop; fraud_urgent_brand_alert [35] + fraud_uk_bank_alert [30] form 40.6% of fraud rows; SF-007 phone-damage/P2P vocabulary spans 8-10 families with max_cross_family_centroid_cosine=0.459025).
- **Cluster Size Inequality:** `56` semantic families (`37` purely benign covering `543` messages, min=`2` / median=`6.0` / max=`53`, ratio=`26.5x`, top-3 share=`24.9%`; `19` purely fraud covering `160` messages, min=`2` / median=`4.0` / max=`35`, ratio=`17.5x`, top-3 share=`59.4%`; mixed-label groups=`0`).
- **Group-Concentration Finding:** At `tau = 0.60..0.80`, `100%` of OOF false positives (`40` at `0.60`, `27` at `0.70`, `13` at `0.75`, `4` at `0.80`) occur inside one benign family (`legit_bank_security_alert_12`), leaving `36 / 37` benign groups with `0` FPs.
- **Conditional Resampling & Zero-Event Reference Reassessment:** Intact-cluster percentile resampling (`B = 10000`, `seed = 42`) quantifies **conditional cluster-bootstrap sensitivity** on this curated 56-family set, NOT unconditional carrier population CIs. At `tau >= 0.85`, `0 / 37` benign groups fail: bootstrap degenerates (`None`), and `<= 7.78%` (`1 - 0.05**(1/37)`) / `<= 9.41%` Wilson (`<= 8.20%` under `35` macro-collapsed benign groups) is retained **strictly as a conditional mathematical reference** under an unmet i.i.d. binomial assumption—NOT a population confidence bound and NOT message-level carrier FPR.

| $\tau$ | TP/FP/TN/FN | TPR (Cond. Cluster 2.5-97.5%) | FPR | FP Benign Groups | Cond. Cluster 2.5-97.5% / Cond. Zero-Event Ref | Valid Boot Reps (TPR/FPR) | Row Wilson FPR Upper (Ref Only) |
|:---:|:---:|:---:|:---:|:---:|---|:---:|:---:|
| `0.30` | 157/46/497/3 | 98.12% (`[93.86%, 100.00%]`) | 8.47% | `6 / 37` | `[0.43%, 24.86%]` | 10000/10000 (undef 0/0) | `11.12%` |
| `0.40` | 156/44/499/4 | 97.50% (`[92.31%, 99.54%]`) | 8.10% | `5 / 37` | `[0.24%, 24.48%]` | 10000/10000 (undef 0/0) | `10.70%` |
| `0.50` | 154/41/502/6 | 96.25% (`[88.70%, 99.20%]`) | 7.55% | `2 / 37` | `[0.00%, 23.92%]` | 10000/10000 (undef 0/0) | `10.08%` |
| `0.60` | 147/40/503/13 | 91.88% (`[80.46%, 96.85%]`) | 7.37% | `1 / 37` (`legit_bank_security_alert_12`=40) | `[0.00%, 23.72%]` | 10000/10000 (undef 0/0) | `9.88%` |
| `0.70` | 131/27/516/29 | 81.88% (`[58.41%, 92.42%]`) | 4.97% | `1 / 37` (`legit_bank_security_alert_12`=27) | `[0.00%, 16.01%]` | 10000/10000 (undef 0/0) | `7.14%` |
| `0.75` | 117/13/530/43 | 73.12% (`[48.80%, 89.33%]`) | 2.39% | `1 / 37` (`legit_bank_security_alert_12`=13) | `[0.00%, 7.71%]` | 10000/10000 (undef 0/0) | `4.05%` |
| `0.80` | 100/4/539/60 | 62.50% (`[28.57%, 86.74%]`) | 0.74% | `1 / 37` (`legit_bank_security_alert_12`=4) | `[0.00%, 2.37%]` | 10000/10000 (undef 0/0) | `1.88%` |
| `0.85` | 91/0/543/69 | 56.88% (`[21.74%, 82.43%]`) | 0.00% | `0 / 37` | Degenerate (0 FP groups); Cond. math ref <= `7.78%` (CP) / `9.41%` (Wilson; `8.20%` at G=35) — NOT pop. bound or message FPR | 10000/10000 (undef 0/0) | `0.70%` |
| `0.90` | 74/0/543/86 | 46.25% (`[13.89%, 71.62%]`) | 0.00% | `0 / 37` | Degenerate (0 FP groups); Cond. math ref <= `7.78%` (CP) / `9.41%` (Wilson; `8.20%` at G=35) — NOT pop. bound or message FPR | 10000/10000 (undef 0/0) | `0.70%` |
| `0.95` | 61/0/543/99 | 38.12% (`[9.43%, 65.27%]`) | 0.00% | `0 / 37` | Degenerate (0 FP groups); Cond. math ref <= `7.78%` (CP) / `9.41%` (Wilson; `8.20%` at G=35) — NOT pop. bound or message FPR | 10000/10000 (undef 0/0) | `0.70%` |

#### Bootstrap Monte Carlo Seed & Replicate Sensitivity (`seeds = 42, 0, 7, 99, 2026`)

- Increasing `B` from `1000` to `10000` reduces Monte Carlo tail jitter across seeds (notably avoiding high-tail `seed=42, B=1000` edge draws like `50.00%` at `tau=0.75` or `30.53%` at `tau=0.80`), but larger `B` cannot cure small cluster count (`G_fraud=19`, `G_benign=37`) or non-i.i.d. curated construction.

| $\tau$ | `B=1000` TPR Low Seed Span | `B=10000` TPR Low Seed Span | `B=1000` FPR High Seed Span | `B=10000` FPR High Seed Span |
|:---:|:---:|:---:|:---:|:---:|
| `0.40` | `[91.80%, 92.68%]` (`0.88 pp`) | `[92.19%, 92.54%]` (`0.35 pp`) | `[23.51%, 24.45%]` (`0.94 pp`) | `[24.10%, 24.60%]` (`0.50 pp`) |
| `0.75` | `[47.80%, 50.00%]` (`2.20 pp`) | `[48.15%, 48.86%]` (`0.72 pp`) | `[7.40%, 7.81%]` (`0.41 pp`) | `[7.58%, 7.74%]` (`0.16 pp`) |
| `0.80` | `[26.91%, 30.83%]` (`3.92 pp`) | `[27.66%, 28.87%]` (`1.21 pp`) | `[2.28%, 2.40%]` (`0.13 pp`) | `[2.33%, 2.38%]` (`0.05 pp`) |
| `0.85` | `[20.63%, 22.98%]` (`2.35 pp`) | `[20.95%, 22.00%]` (`1.05 pp`) | Degenerate (`0/37` FP groups) | Degenerate (`0/37` FP groups) |

### Modeled Bayes Base-Rate PPV Sensitivity Scenarios (Illustrative Only — Not Observed Precision or PPV CIs)

- Actual deployment smishing prevalence $\pi$ is unknown without live carrier measurement. Zero observed OOF false positives (`0 / 543` in `0 / 37` groups) yields `100%` point PPV mechanically, whereas plausible non-zero FPRs dramatically lower precision (e.g., at `tau = 0.85`, `TPR = 56.88%`, `pi = 0.5%`, even descriptive row-level Wilson upper `0.70%` implies `28.92%` PPV, not `100%`).

| $\tau$ | Sensitivity Scenario | Assumed TPR | Assumed FPR | Modeled PPV @ 0.2% | PPV @ 0.5% | PPV @ 1.0% | PPV @ 5.0% |
|:---:|---|---:|---:|:---:|:---:|:---:|:---:|
| `0.40` | OOF point estimate | 97.50% | 8.10% | 2.35% | 5.70% | 10.84% | 38.77% |
| `0.40` | Point TPR + descriptive row Wilson FPR upper (ref only) | 97.50% | 10.70% | 1.79% | 4.38% | 8.43% | 32.41% |
| `0.75` | OOF point estimate | 73.12% | 2.39% | 5.77% | 13.31% | 23.58% | 61.65% |
| `0.75` | Point TPR + descriptive row Wilson FPR upper (ref only) | 73.12% | 4.05% | 3.49% | 8.31% | 15.42% | 48.71% |
| `0.80` | OOF point estimate | 62.50% | 0.74% | 14.53% | 29.89% | 46.15% | 81.70% |
| `0.80` | Point TPR + descriptive row Wilson FPR upper (ref only) | 62.50% | 1.88% | 6.25% | 14.32% | 25.15% | 63.65% |
| `0.85` | OOF point estimate | 56.88% | 0.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| `0.85` | Point TPR + descriptive row Wilson FPR upper (ref only) | 56.88% | 0.70% | 13.96% | 28.92% | 44.99% | 80.99% |
| `0.85` | Cluster 2.5% TPR + descriptive row Wilson FPR upper | 21.74% | 0.70% | 5.84% | 13.46% | 23.81% | 61.96% |
| `0.85` | Cluster 2.5% TPR + illustrative 0.5% tail FPR stress | 21.74% | 0.50% | 8.01% | 17.93% | 30.52% | 69.59% |

### Illustrative Assumed Cost-Ratio Sensitivity (12 Named Scenarios + 72-Pair Orthogonal Ratio Grid)

- **Cost Evidence Distinction:** (1) *Mathematical cost under assumed ratios* is computed below as an illustrative normalized sensitivity check only (units are NOT euros, churn dollars, or carrier expenses); (2) *Empirically measured operational cost* is unavailable; (3) *Operational policy decisions* require both measured costs and independent Class C validation.
- **Structural Objective & Scenario-Coverage Finding (`cost_assumption_sensitive = True`):** Across the expanded 72-pair dimensionless cost grid (`576` `(C_FN/C_T1, C_T2/C_T1, pi)` cells), single-threshold optima vary even at low prevalence (`pi=0.5%`: `[0.30, 0.50, 0.85]`; `pi=1.0%`: `[0.30, 0.40, 0.50, 0.75, 0.85]`), proving the earlier `9/9` `[0.85]` result at `pi <= 1%` was an artifact of inspecting too narrow a scenario set. Moreover, compute_dual_tier_cost_per_1000 models only Tier-1 fraud escape and differential Tier-2 FP cost (C_T2 - C_T1) * (1 - pi) * FPR(t2); it assigns zero additional fraud-mitigation benefit to immediate wire blocking over async review, mechanically favoring any threshold with observed FPR=0 such as tau=0.85 whenever FPR(0.85)=0.

| Assumed Cost Scenario `(C_FN, C_T1_FP, C_T2_FP)` | $\pi=0.2\%$ Single / Dual Top | $\pi=0.5\%$ Single / Dual Top | $\pi=1.0\%$ Single / Dual Top | $\pi=5.0\%$ Single / Dual Top |
|---|---|---|---|---|
| `assumed_baseline_10_1_50` `(10, 1, 50)` | `0.85` (8.62) / `(0.85, 0.85)` (8.62) | `0.85` (21.56) / `(0.85, 0.85)` (21.56) | `0.85` (43.12) / `(0.85, 0.85)` (43.12) | `0.85` (215.62) / `(0.40, 0.85)` (89.48) |
| `high_review_congestion_2_2_50` `(2, 2, 50)` | `0.85` (1.73) / `(0.85, 0.85)` (1.73) | `0.85` (4.31) / `(0.85, 0.85)` (4.31) | `0.85` (8.62) / `(0.85, 0.85)` (8.62) | `0.85` (43.12) / `(0.85, 0.85)` (43.12) |
| `scarce_triage_10_10_100` `(10, 10, 100)` | `0.85` (8.62) / `(0.85, 0.85)` (8.62) | `0.85` (21.56) / `(0.85, 0.85)` (21.56) | `0.85` (43.12) / `(0.85, 0.85)` (43.12) | `0.85` (215.62) / `(0.85, 0.85)` (215.62) |
| `extreme_escape_low_block_250_1_5` `(250, 1, 5)` | `0.85` (215.62) / `(0.40, 0.85)` (93.37) | `0.50` (422.52) / `(0.30, 0.85)` (107.73) | `0.40` (463.60) / `(0.30, 0.85)` (130.74) | `0.30` (636.77) / `(0.30, 0.85)` (314.85) |
| `low_block_high_escape_50_1_5` `(50, 1, 5)` | `0.85` (43.12) / `(0.85, 0.85)` (43.12) | `0.85` (107.81) / `(0.50, 0.85)` (84.50) | `0.85` (215.62) / `(0.40, 0.85)` (92.72) | `0.40` (447.40) / `(0.30, 0.85)` (127.35) |
| `moderate_block_high_escape_25_1_10` `(25, 1, 10)` | `0.85` (21.56) / `(0.85, 0.85)` (21.56) | `0.85` (53.91) / `(0.85, 0.85)` (53.91) | `0.85` (107.81) / `(0.50, 0.85)` (84.13) | `0.80` (538.73) / `(0.30, 0.85)` (103.92) |
| `low_escape_baseline_block_2_1_50` `(2, 1, 50)` | `0.85` (1.73) / `(0.85, 0.85)` (1.73) | `0.85` (4.31) / `(0.85, 0.85)` (4.31) | `0.85` (8.62) / `(0.85, 0.85)` (8.62) | `0.85` (43.12) / `(0.85, 0.85)` (43.12) |
| `equal_escape_block_50_1_50` `(50, 1, 50)` | `0.85` (43.12) / `(0.85, 0.85)` (43.12) | `0.85` (107.81) / `(0.50, 0.85)` (84.50) | `0.85` (215.62) / `(0.40, 0.85)` (92.72) | `0.85` (1078.12) / `(0.30, 0.85)` (127.35) |
| `high_escape_100_1_50` `(100, 1, 50)` | `0.85` (86.25) / `(0.75, 0.85)` (77.64) | `0.85` (215.62) / `(0.40, 0.85)` (93.13) | `0.85` (431.25) / `(0.30, 0.85)` (102.62) | `0.85` (2156.25) / `(0.30, 0.85)` (174.23) |
| `high_block_250_1_250` `(10, 1, 250)` | `0.85` (8.62) / `(0.85, 0.85)` (8.62) | `0.85` (21.56) / `(0.85, 0.85)` (21.56) | `0.85` (43.12) / `(0.85, 0.85)` (43.12) | `0.85` (215.62) / `(0.40, 0.85)` (89.48) |
| `extreme_block_5_1_500` `(5, 1, 500)` | `0.85` (4.31) / `(0.85, 0.85)` (4.31) | `0.85` (10.78) / `(0.85, 0.85)` (10.78) | `0.85` (21.56) / `(0.85, 0.85)` (21.56) | `0.85` (107.81) / `(0.50, 0.85)` (81.11) |
| `high_review_overhead_10_5_50` `(10, 5, 50)` | `0.85` (8.62) / `(0.85, 0.85)` (8.62) | `0.85` (21.56) / `(0.85, 0.85)` (21.56) | `0.85` (43.12) / `(0.85, 0.85)` (43.12) | `0.85` (215.62) / `(0.85, 0.85)` (215.62) |

#### Orthogonal 72-Ratio Cost Grid Coverage (`C_FN/C_T1 in 0.5..250`, `C_T2/C_T1 in 2..500`, `C_T1=1`)

| Prevalence $\pi$ | Distinct Winning Single Thresholds (72 Pairs) | Single Winner Distribution | Distinct Winning Dual `(t1, t2)` Policies | Dual Policy Distribution |
|:---:|---|---|---|---|
| `0.1%` | `0.85` | `0.85`:72 | `(0.50, 0.85), (0.85, 0.85)` | `(0.50, 0.85)`:8, `(0.85, 0.85)`:64 |
| `0.2%` | `0.50, 0.85` | `0.50`:1, `0.85`:71 | `(0.40, 0.85), (0.75, 0.85), (0.85, 0.85)` | `(0.40, 0.85)`:8, `(0.75, 0.85)`:8, `(0.85, 0.85)`:56 |
| `0.5%` | `0.30, 0.50, 0.85` | `0.30`:1, `0.50`:2, `0.85`:69 | `(0.30, 0.85), (0.40, 0.85), (0.50, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:8, `(0.40, 0.85)`:8, `(0.50, 0.85)`:8, `(0.85, 0.85)`:48 |
| `1.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:1, `0.40`:2, `0.50`:2, `0.75`:1, `0.85`:66 | `(0.30, 0.85), (0.40, 0.85), (0.50, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:16, `(0.40, 0.85)`:8, `(0.50, 0.85)`:8, `(0.85, 0.85)`:40 |
| `2.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:3, `0.40`:2, `0.50`:2, `0.75`:3, `0.85`:62 | `(0.30, 0.85), (0.40, 0.85), (0.75, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:24, `(0.40, 0.85)`:8, `(0.75, 0.85)`:8, `(0.85, 0.85)`:32 |
| `5.0%` | `0.30, 0.40, 0.50, 0.75, 0.80, 0.85` | `0.30`:7, `0.40`:3, `0.50`:4, `0.75`:1, `0.80`:3, `0.85`:54 | `(0.30, 0.85), (0.40, 0.85), (0.50, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:32, `(0.40, 0.85)`:8, `(0.50, 0.85)`:8, `(0.85, 0.85)`:24 |
| `10.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:10, `0.40`:5, `0.50`:3, `0.75`:3, `0.85`:51 | `(0.30, 0.85), (0.40, 0.85), (0.75, 0.85), (0.85, 0.85)` | `(0.30, 0.85)`:40, `(0.40, 0.85)`:8, `(0.75, 0.85)`:8, `(0.85, 0.85)`:16 |
| `50.0%` | `0.30, 0.40, 0.50, 0.75, 0.85` | `0.30`:28, `0.40`:5, `0.50`:5, `0.75`:6, `0.85`:28 | `(0.30, 0.85), (0.40, 0.85)` | `(0.30, 0.85)`:64, `(0.40, 0.85)`:8 |

#### Sensitivity to Observed `FPR(0.85)=0` Artifact (`10:1:50` at $\pi = 0.5\%$)

| Assumed Floor FPR for $\tau \ge 0.85$ | Best Single Threshold | Best Single Cost/1k | Best Dual `(t1, t2)` | Best Dual Cost/1k |
|---|:---:|---:|:---:|---:|
| `observed_zero_fpr` (`0.0000%`) | `0.85` | 21.56 | `(0.85, 0.85)` | 21.56 |
| `tail_stress_0_5pct` (`0.5000%`) | `0.85` | 270.31 | `(0.85, 0.85)` | 270.31 |
| `row_wilson_upper_0_7025pct` (`0.7025%`) | `0.85` | 371.06 | `(0.85, 0.85)` | 371.06 |
| `plausible_2_0pct_below_family_bound` (`2.0000%`) | `0.80` | 385.21 | `(0.75, 0.80)` | 396.39 |

## 11. Adversarial Perturbation & Component Ablation Matrix (`SF-013`)

> **Diagnostic Scope (`UNAVAILABLE_BLOCKED`):** Evaluates frozen `ML-only`, `Heuristics-only`, and `Composite` scoring across 10 canonical smishing archetypes under 5 controlled obfuscation/shift perturbations plus 10 benign near-miss contrastive controls (`0` SHA-256 overlap with Train/DevVal). This is a controlled synthetic diagnostic suite—not an external real-world Class C carrier evaluation.

| Cohort / Perturbation Family | Class / Metric | Samples | ML ($P \ge 0.40$) | ML ($P \ge 0.50$) | Heuristics ($H \ge 0.40$ / $0.50$) | Composite Tier 1 ($S \ge 0.40$) | Composite Tier 2 ($S \ge 0.75$) | Mean $(P, H, S)$ |
|---|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Canonical Smishing Baseline (Unperturbed) | FRAUD (Recall) | 10 | 100.0% | 90.0% | 100.0% / 100.0% | 100.0% | 90.0% | `0.8110 / 0.7720 / 0.9284` |
| 1. Unseen Institution & Brand Substitution | FRAUD (Recall) | 10 | 100.0% | 90.0% | 100.0% / 100.0% | 100.0% | 90.0% | `0.8104 / 0.7720 / 0.9253` |
| 2. URL Domain & Shortener Rotation | FRAUD (Recall) | 10 | 90.0% | 90.0% | 80.0% / 80.0% | 100.0% | 90.0% | `0.7461 / 0.7110 / 0.9293` |
| 3. Cyrillic Homoglyph Substitution | FRAUD (Recall) | 10 | 80.0% | 70.0% | 0.0% / 0.0% | 80.0% | 10.0% | `0.5271 / 0.1000 / 0.5415` |
| 4. Leetspeak & Intra-Word Punctuation Splitting | FRAUD (Recall) | 10 | 100.0% | 100.0% | 60.0% / 60.0% | 100.0% | 70.0% | `0.7282 / 0.4630 / 0.7791` |
| 5. Whitespace, Casing & Control-Char Injection | FRAUD (Recall) | 10 | 100.0% | 100.0% | 100.0% / 100.0% | 100.0% | 90.0% | `0.8082 / 0.7670 / 0.9208` |
| 6. Benign Near-Miss Contrastive Controls | BENIGN (FPR) | 10 | 20.0% | 20.0% | 0.0% / 0.0% | 20.0% | 0.0% | `0.1373 / 0.0400 / 0.1373` |

### Diagnostic Ablation Takeaways (Where TF-IDF & Heuristics Hold vs. Degrade)

- **Word-Level TF-IDF Generalization vs. Token-Splitting Degradation:** The frozen ONNX TfidfVectorizer uses word regex token_pattern='\\b[a-zA-Z0-9_]+\\b'; substituting non-ASCII Cyrillic codepoints or inserting intra-word dots/digits/zero-width characters pushes fraud signals out of vocabulary and breaks bigrams (mean P drops from 0.8110 to 0.5271 on Cyrillic homoglyphs and 0.7282 on leetspeak/splitting).
- **Heuristic Normalization Defense-in-Depth & Residual Homoglyph Gap:** normalize_heuristic_text() strips invisible zero-width formatting characters (U+200B..U+200F, U+FEFF, U+00AD) and applies NFKC decomposition, preserving heuristics recall under whitespace/control injection (H>=0.50 recall=1.00, minor drop in mean H from multi-space breaking single-space 'sim card'). However, the frozen heuristic engine has NO RULE:HOMOGLYPH_OBFUSCATION or Cyrillic confusable mapping, so Cyrillic homoglyphs collapse heuristics recall to 0.00 and Composite Tier-2 to 0.10.
- **Contrastive Benign Control Precision:** On benign near-miss controls overlapping legal/tax/postal nouns, ML-only flags 20.0% into Tier-1 review while heuristics trigger 0.0% FPR and Composite Tier-2 blocks 0.0%.

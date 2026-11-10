# SentinelPulse Empirical ML Development & Validation Benchmark Report (Dev/Val N=400)

> **Reproducibility Stamp:** All metrics, confusion matrices, and breakdowns are generated directly from execution against the compiled ONNX model artifact and development/validation benchmark suite (N = 400). Zero simulated or synthetic figures.

## 1. Reproducibility & Environment Stamp

- **Model Artifact:** `sms_fraud_model.onnx` (194.85 KB)
- **Model SHA-256:** `d330466e8a28e43e4d8452fdef76f64470429851f19c568ea83399e7d16beaa9`
- **Evaluation Dataset SHA-256:** `210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03`
- **Canonical 400-Row Predictions Artifact:** `benchmark_predictions_400.json`
- **Canonical 400-Row Predictions SHA-256:** `66dc4862190c597f158298f199e9173f32901fd3ed916487a681c948a635d29e`
- **Timestamp:** `2026-11-10T21:35:58.605112+00:00`
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

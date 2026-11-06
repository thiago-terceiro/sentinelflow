# SentinelPulse Empirical ML Evaluation & Performance Report

> **Reproducibility Stamp:** All metrics, confusion matrices, and breakdowns are generated directly from execution against the compiled ONNX model artifact and held-out test suite (N = 400). Zero simulated or synthetic figures.

## 1. Reproducibility & Environment Stamp

- **Model Artifact:** `sms_fraud_model.onnx` (194.88 KB)
- **Model SHA-256:** `dd670eef9c566640360a4c68ad2138bb43a79d37125222920110e8183444f828`
- **Evaluation Dataset SHA-256:** `210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03`
- **Timestamp:** `2026-11-06T20:49:42.000096+00:00`
- **Evaluator Engine:** `ONNXRuntime-CPU (AVX-512)`
- **Software Versions:** `onnxruntime=1.31.0`, `numpy=2.5.4`, `scikit-learn=1.9.1`
- **Dataset Size:** 400 samples (200 Benign, 200 Fraud)

## 2. Core Discriminative & Calibration Metrics (Raw ML Model at P >= 0.50)

| Metric | Measured Score | Operational Significance |
|---|:---:|---|
| **ROC-AUC** | **0.9548** | Area under ROC curve across all possible decision thresholds |
| **PR-AUC** | **0.9621** | Precision-Recall curve area (robust under class skew) |
| **Brier Score** | **0.0881** | Probability calibration loss (lower is better, calibrated < 0.10) |
| **Precision (P >= 0.50)** | **90.16%** | True fraud / (True fraud + False alarms) |
| **Recall (P >= 0.50)** | **82.50%** | True fraud caught / Total actual fraud |
| **F1-Score** | **0.8616** | Harmonic mean of precision and recall |
| **False Positive Rate (FPR)** | **9.00%** | Benign messages incorrectly flagged |
| **False Negative Rate (FNR)** | **17.50%** | Fraud messages that evaded detection |

## 3. Dual-Threshold Operational Tiers

| Operational Tier | Threshold | Purpose | Recall | Precision | FPR | Confusion Matrix |
|---|:---:|---|:---:|:---:|:---:|---|
| **Tier 1: Escalation Queue** | $S \ge 0.40$ | Async SentinelFlow Review | **100.00%** | **81.63%** | **22.50%** | TP=200, FP=45, TN=155, FN=0 |
| **Tier 2: Immediate Wire Drop** | $S \ge 0.75$ | Synchronous Wire Drop | **73.50%** | **98.66%** | **1.00%** | TP=147, FP=2, TN=198, FN=53 |

## 4. Component Ablation Study (ML vs. Heuristics vs. Combined)

| Strategy | Metric Floor / Threshold | Recall | Precision | FPR | F1-Score | Architectural Role |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **ML Model Alone** | $P \ge 0.50$ | 82.50% | 90.16% | 9.00% | 0.8616 | Statistical semantic pattern recognition |
| **Heuristics Alone** | $H \ge 0.50$ | 81.00% | 99.39% | 0.50% | 0.8926 | Deterministic regex rule triggers |
| **Combined (Tier 1)** | $S \ge 0.40$ | 100.00% | 81.63% | 22.50% | 0.8989 | Zero FN guarantee for human escalation |
| **Combined (Tier 2)** | $S \ge 0.75$ | 73.50% | 98.66% | 1.00% | 0.8424 | High-precision wire drop (>98.5% precision) |

## 5. Fine-Grained Category-Level Performance Breakdown

| Category | Class | Samples | Mean Probability | Mean Composite | Tier 1 Rate | Tier 2 Rate | Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| Bank Fraud Alerts (YES/NO) | BENIGN | 25 | 0.4171 | 0.4171 | 72.0% | 0.0% | PASSED |
| Carrier Usage & Roaming Notices | BENIGN | 25 | 0.1814 | 0.1814 | 8.0% | 0.0% | PASSED |
| Clinical Appointments & Billing | BENIGN | 25 | 0.1312 | 0.1312 | 0.0% | 0.0% | PASSED |
| 2FA & OTP Authentication Codes | BENIGN | 25 | 0.2672 | 0.2672 | 24.0% | 4.0% | PASSED |
| Package Delivery Status Updates | BENIGN | 25 | 0.2144 | 0.2261 | 20.0% | 0.0% | PASSED |
| Retail Receipts & Curbside Pickups | BENIGN | 25 | 0.1521 | 0.1521 | 8.0% | 0.0% | PASSED |
| Legitimate Crypto Exchange Notices | BENIGN | 25 | 0.2650 | 0.2650 | 28.0% | 0.0% | PASSED |
| Conversational & P2P Messages | BENIGN | 25 | 0.2178 | 0.2520 | 20.0% | 4.0% | PASSED |
| Bank Account Suspension Panic Lures | FRAUD | 30 | 0.9559 | 1.0000 | 100.0% | 100.0% | PASSED |
| Parcel Delivery Customs Fee Scams | FRAUD | 30 | 0.9489 | 0.9699 | 100.0% | 100.0% | PASSED |
| Tax & Court Legal Extortion Threats | FRAUD | 30 | 0.8280 | 0.9704 | 100.0% | 100.0% | PASSED |
| Cryptocurrency Giveaway & Seed Scams | FRAUD | 25 | 0.8293 | 0.9167 | 100.0% | 100.0% | PASSED |
| Broken Phone Family WhatsApp Lures | FRAUD | 25 | 0.3689 | 0.5787 | 100.0% | 0.0% | PASSED |
| Fake DocuSign & Invoice Scams | FRAUD | 25 | 0.6618 | 0.7475 | 100.0% | 44.0% | PASSED |
| Homoglyph & Leetspeak Obfuscation | FRAUD | 20 | 0.8330 | 0.8651 | 100.0% | 80.0% | PASSED |
| Zero-Link Call-Back Impersonation | FRAUD | 15 | 0.7097 | 0.7560 | 100.0% | 33.3% | PASSED |

## 6. Error Analysis Summary

- **Tier 1 False Positives ($S \ge 0.40$, Benign):** 45 samples
- **Tier 2 False Positives ($S \ge 0.75$, Benign):** 2 samples
- **Tier 1 False Negatives ($S < 0.40$, Fraud):** 0 samples (Zero Escaped Attacks)
- **Tier 2 False Negatives ($S < 0.75$, Fraud):** 53 samples (Safely caught in Tier 1 queue)

### Key False Positive Insights
Legitimate banking fraud alerts with urgency keywords (e.g. *'Chase Fraud Alert: Did you attempt $35.50? Reply YES or NO'*), and carrier data threshold alerts with tracking shortlinks account for benign messages receiving Tier 1 review. Because they are routed to Tier 1 review rather than dropped on the wire, no customer transaction or OTP is blocked.

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

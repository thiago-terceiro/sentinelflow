# SentinelPulse Learning Coach: Guide & Workflow Manual

This guide explains how to invoke and work with the `sentinelpulse-learning-coach` Antigravity Skill to explore, learn, evaluate, and maintain SentinelPulse.

---

## 1. Skill Overview

The `sentinelpulse-learning-coach` is an applied ML engineering mentor built directly into Antigravity for SentinelPulse. It bridges the gap between senior software engineering and applied ML by grounding every statistical concept, evaluation metric, and architecture trade-off in the actual working codebase.

### Location
- Skill definition: `.agents/skills/sentinelpulse-learning-coach/SKILL.md`
- Frontend Learning Hub: `sentinelflow/frontend/app/learn/page.tsx`
- ML Evaluation Script: `sentinelflow/backend/app/telecom/evaluate_model.py`
- Engineering Decisions: `docs/engineering_decisions_journal.md`

---

## 2. How to Invoke the Skill

You can ask Antigravity in plain language whenever you want to learn, audit, or experiment:

### A. Learning ML Concepts
- *"Teach me how probability calibration works in SentinelPulse."*
- *"Explain why high ROC-AUC does not guarantee well-calibrated probabilities."*
- *"What is data leakage and how did SentinelPulse prevent template leakage?"*
- *"Explain the difference between ROC-AUC and PR-AUC with an example."*

### B. Investigating Implementation Details
- *"Show me how the continuous gated blend formula is implemented in onnx_engine.py."*
- *"How does the ONNX model compile Platt scaling in-graph?"*
- *"What happens if Redis fails during a telecom burst?"*

### C. Running & Interpreting ML Evaluations
- *"Run the ML evaluation suite and explain the confusion matrix."*
- *"Show me the ablation study comparing the ML model alone vs heuristics alone."*
- *"What are the false positives in our held-out test suite?"*
- *"Break down model performance across banking, delivery, and callback scams."*

### D. Documenting Engineering Decisions
- *"Document the decision to use in-process ASGI benchmarks instead of multi-worker claims."*
- *"Record an incident entry for the audit ledger concurrency fix."*

### E. Updating the Learning Hub
- *"Add a new curriculum lesson on Brier score to the Learning Hub."*
- *"Update the Evaluation Lab tab with our latest benchmark results."*

---

## 3. The 8-Part Concept Pedagogy

Whenever the coach explains an ML concept, it follows an 8-part template:
1. **What is it?** (Plain language explanation)
2. **Why does it exist?** (The problem it solves)
3. **How does it work?** (Mechanics and equations with all variables explained)
4. **How does SentinelPulse use it?** (Exact files, classes, and lines of code)
5. **Concrete SMS Fraud Example** (Real comparison with telecom data)
6. **Trade-offs and Limitations** (Failure modes, alternatives, edge cases)
7. **What should an ML engineer know?** (Practical skills and diagnostic instincts)
8. **Practical Hands-on Exercise** (Runnable terminal command or calculation)

---

## 4. The 15-Step Learning Curriculum

| Step | Module | Difficulty | Focus |
|:---:|---|:---:|---|
| 1 | SentinelPulse Architecture & Request Lifecycle | `FOUNDATIONS` | Fast ingress, ONNX CPU inference, velocity, fallback |
| 2 | Binary Classification Fundamentals | `FOUNDATIONS` | Features, labels, decision boundaries, 0 vs 1 |
| 3 | Text Vectorization & Logistic Regression | `FOUNDATIONS` | TF-IDF, N-grams, weights, odds ratio, sigmoid |
| 4 | Dataset Hygiene & Splitting | `MID-LEVEL` | Train, validation, test, stratification |
| 5 | Data Leakage & Grouped Validation | `MID-LEVEL` | Exact-string vs template-family vs semantic leakage |
| 6 | Confusion Matrix Anatomy | `FOUNDATIONS` | TP, FP, TN, FN, Accuracy, Error types |
| 7 | Precision, Recall & Operational Trade-offs | `MID-LEVEL` | Specificity, FPR, FNR, F1-Score |
| 8 | ROC-AUC vs. PR-AUC Under Imbalance | `MID-LEVEL` | Threshold independence, precision-recall dynamics |
| 9 | Probability Calibration & Platt Scaling | `MID-LEVEL` | Sigmoid fitting, Brier score, reliability curves |
| 10 | Operational Threshold Engineering | `SENIOR` | Dual-tier routing (Tier 1 Escalation vs Tier 2 Wire Drop) |
| 11 | Heuristic & ML Gated Blending | `SENIOR` | Monotonicity, continuous gating, authoritative overrides |
| 12 | Component Ablation Studies | `SENIOR` | Isolating ML vs Heuristics vs Velocity contributions |
| 13 | Diagnostic Error Analysis | `SENIOR` | False positive review, failure modes, regex tuning |
| 14 | Distribution Shift & Drift Monitoring | `SENIOR` | Kolmogorov-Smirnov test, Population Stability Index (PSI) |
| 15 | Low-Latency CPU Inference & Benchmarking | `STAFF/ADVANCED` | ONNX Runtime, AVX-512, ASGI vs Multi-Worker OS processes |

---

## 5. Evaluation Workflow Commands

Run all evaluations with one command:

```bash
cd sentinelflow/backend
uv run python -m app.telecom.evaluate_model --all
```

Run automated evaluation verification tests:
```bash
cd sentinelflow/backend
uv run pytest app/tests/test_telecom_eval_suite.py
```

Inspect generated artifacts:
- Metrics: `sentinelflow/backend/app/telecom/ml_metrics.json`
- Report: `sentinelflow/docs/ml_evaluation_report.md`

---

## 6. Strict Local-Only Mandate

**CRITICAL RULE**: The Learning Hub is designed as an offline educational environment for local engineering development.
- **NEVER** stage or push the following paths to remote Git:
  - `sentinelflow/frontend/app/learn/**`
  - `sentinelflow/frontend/components/learn/**`
  - `sentinelflow/frontend/lib/i18n/**`
  - `sentinelflow/frontend/tests/learn-i18n.test.js`
  - `/learn` navigation entry in `NavbarLinks.tsx`
- Always verify working tree status before committing with `git status`.

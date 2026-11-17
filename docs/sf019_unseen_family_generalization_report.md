# SF-019 — Unseen-Family Generalization & False-Positive Remediation Report

**Linear Ticket:** `AI-32` (`SF-019`)  
**Final Outcome:** **Justified `NO-CHANGE` Decision (Frozen `SF-018` Artifact `824c6c2c...` Retained)**  
**Evaluation Basis:** Group-Disjoint 5-Fold `StratifiedGroupKFold` OOF (`primary`) + Leave-Macro-Out (`LMO_all3`) + Secondary Dev/Val (`N=400`) + Full Regression Suite (`259` tests including `SF-007` 3-tier policy & `SF-014` adversarial suite)

---

## 1. Executive Summary

`SF-018`'s fine-grained 5-fold OOF evaluation exposed a severe single-family failure: **all 40/40 Fold 4 false positives** (`P >= 0.50`) came from `legit_bank_security_alert_12` (`ROC-AUC=0.7715`, `Precision=0.2727`), including `13/40` crossing Tier 2 autonomous `BLOCK` (`S >= 0.75`).

We reproduced all 40 baseline false positives to machine precision (`max |p_repro - p_frozen| = 4.98e-09`), confirmed four concrete causes in TF-IDF token representation and calibration split balance, systematically evaluated hyperparameter tweaks, alternative benign families, and a candidate remediation (`NoFin SGKF` `N=719`, `2362003b...`), **and ultimately recorded a justified `NO-CHANGE` decision (`AI-32` AC #7)** retaining the frozen `SF-018` model (`824c6c2c254791205184efadd8f0b2dc43f22e7222b411e75c2b99c340a9604b`):

* **Why Candidate `NoFin SGKF` (`N=719`) Appeared Promising in Aggregate:** Adding 3 non-bank URL-free/callback-free benign A2P families (`+16` messages) + `StratifiedGroupKFold(5)` calibration lowered `legit_bank_security_alert_12` OOF FPs (`40/40 -> 29/40`), eliminated Tier 2 OOF blocks (`13/40 -> 0/40`), and raised pooled OOF F1 (`0.7964 -> 0.8246`).
* **Why Candidate `NoFin SGKF` Was Rejected Upon Full Regression Verification:** Evaluating across **all** existing regression suites (without weakening any assertion or tuning operational weights) exposed real failures that aggregate OOF metrics hid:
  1. **`test_adversarial_suite_categories_and_evidence_honesty` (`C12` WFH Telegram Scam Recall Regression):** Category C recall dropped from `1.0000` (`16/16`) to **`0.9375` (`15/16`)** because `StratifiedGroupKFold(5)` re-centered `C12` (`"Earn $250/day work from home reviewing merchant listings. Message hiring manager on Telegram now!"`) from `P=0.2498 -> 0.0374` (`S=0.3575 < 0.40`).
  2. **`test_family_impersonation_three_tier_policy` (`SF-007` Class B Broken-Phone P2P Escalation Regression):** Ambiguous Class B (`"Hey dad, my phone broke and I lost my SIM, using a temporary number for tonight. Text me on Telegram when free."`) jumped from `S=0.6838` (`FLAG`) to **`S=0.8792` (`P=0.8351 >= 0.75 BLOCK`)**, violating the `SF-007` 3-tier `FLAG`-only policy.
  3. **Collateral OOF Tier-1 / FN Shifts:** Pooled Tier-1 OOF FPs rose (`44 -> 66`, driven by `legit_health_mychart` shifting `0/21 -> 20/21` Tier 1 flags), `legit_casual_birthday_greetings` gained `1` FP, and `fraud_legal_tax_extortion` shifted `fn_p50` `1 -> 2`.

Per `AI-32` AC #4/#5/#7 ("No material regression is hidden by aggregate metrics... Record a no-change conclusion if the evidence does not support a safe fix"), keeping frozen `SF-018` (`824c6c2c...`) preserves 0 regressions across all safety/policy contracts while leaving this unseen-family limitation explicitly documented for future non-linear/structural modeling + real-world Class C acquisition (`SF-022`).

---

## 2. Exact Baseline & Evaluated Candidate Provenance

| Artifact | Retained Active `SF-018` SHA-256 | Rejected Candidate `NoFin SGKF` SHA-256 |
|---|---|---|
| `models/sms_fraud_model.onnx` | **`824c6c2c254791205184efadd8f0b2dc43f22e7222b411e75c2b99c340a9604b`** (`198,496 B`) | `2362003b1d8ca13daafaf44b5355215ae15fc2aeeeda8ccb1b4bf30d849ac5b7` (`198,497 B`) |
| Training Corpus | **`5bcedbea725ac6c5c2113bfdcf06ec5cb949afd92e556329a94567a8b8abb699`** (`N=703, G=56`) | `7803ab7ca1bf9dc38c204d46825882fbca549c3fa4cff4995b0fbed7e3c5878c` (`N=719, G=59`) |
| `dev_val_400` Dataset | `210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03` (`N=400`) | Unchanged |
| Comparison Evidence Artifact | `sentinelflow/backend/app/telecom/sf019_generalization_comparison.json` | Recorded side-by-side (`79,206 B`) |

---

## 3. Baseline Reproduction & Root-Cause Diagnosis (`SF-018`)

### 3.1 Exact 40-FP Reproduction & Bank-Alert Contrast
Reproducing Fold 4 of `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` against frozen `oof_predictions.json` matched all 40 false positives (`max |p_repro - p_frozen| = 4.98e-09`). All 40 samples (`sample_id`s `322, 325, ..., 439`) belong to `legit_bank_security_alert_12`, have `heuristic_score = 0.0`, OOF probabilities in `[0.6270, 0.8078]` (`mean = 0.7283`), `40/40` Tier 1 `FLAG`, and `13/40` Tier 2 `BLOCK`.

| Family | Fold | `N` | OOF `FP (P>=0.50)` | OOF Prob Range `[min, max]` | Why It Did or Did Not Generalize |
|---|---|---|---|---|---|
| `legit_bank_auth_alert_yn` | Fold 1 | 40 | `0` | `[0.0080, 0.0153]` | Shares `"Did you"` / `"Reply"` benign cues with `legit_bank_fraud_alert_yesno`. |
| `legit_bank_fraud_alert_yesno` | Fold 2 | 41 | `0` | `[0.0086, 0.2122]` | Shares benign `"Did you"` / `"Reply"` cues with `legit_bank_auth_alert_yn`. |
| `legit_bank_security_alert_12` | Fold 4 | 40 | **`40`** (`13` Tier 2) | `[0.6270, 0.8078]` | Uses `"Security Alert"` + `"Unusual"` + `"charge"` + `"Text 1 if authorized, 2 if not"` with zero benign `"Did you"` cue overlap. |

### 3.2 Confirmed Causes vs. Ruled-Out Hypotheses
1. **Confirmed — Fold 4 Vocabulary Monopolization:** In Fold 4 training (`N=703`), `"security alert"` appeared in `0` benign vs `65` fraud messages (`fraud_uk_bank_alert`, `fraud_urgent_brand_alert`), and `"unusual"` appeared in `0` benign vs `36` fraud messages (the only other benign `"security alert"` family, `legit_2fa_login_alert`, also fell into Fold 4).
2. **Confirmed — Currency Digit Tokenization Artifact (`1`, `2`):** `TfidfVectorizer` splits `$2.50` / `$2.40` and `1-800` into bare single-digit tokens `'1'` (`leg_df=3, frd_df=8, coef=+0.6775`) and `'2'` (`leg_df=1, frd_df=26`, `coef=+0.8187`), penalizing `"Text 1 ... 2 ..."` by `+0.3311` total logit in Fold 4.
3. **Confirmed — Additive Linear Bag-of-Ngrams Limitation:** Linear TF-IDF + LogisticRegression cannot condition `"security alert"` on the *absence* of an external URL or callback lure, nor separate `SF-007` Class B (`phone broke + SIM + Telegram` without URL/payment) from `fraud_family_zelle_lure`.
4. **Confirmed — Unstratified Inner Calibration Splits (`GroupKFold`):** Unstratified inner `GroupKFold(5)` causes extreme inner fraud prevalence skew (`9..52` fraud messages per inner fold), swinging Platt intercepts (`b` from `-6.19` to `+2.41`). Paradoxically, two legacy test assertions (`C12` `0.2498 -> S=0.4992` and `SF-007 Class B` `0.5684 -> S=0.6838`) relied on those exact inner-fold calibration boundary placements, so balancing inner folds to `StratifiedGroupKFold(5)` immediately broke both assertions.
5. **Ruled Out — Labeling Defect:** All 40 `legit_bank_security_alert_12` messages are coherent benign 1/2 alerts.

---

## 4. Evaluated Remediation Candidates & Why `NO-CHANGE` Won

| Candidate Variant | `bank_12` OOF (`P>=0.50` / Tier 2) | Existing Regression Suites & Other Impacts | Decision |
|---|---|---|---|
| **Hyperparameter tweaks on `N=703`** (`class_weight=None`, `C=0.5`, `min_df=2`, `len>=2`) | `37–40/40` FPs or Recall `0.8313 -> 0.6813` | Severe fraud recall loss | **Rejected** |
| **Retail / Fintech augmentation** (`refund`, `order hold`, `p2p_otp`) | Lowered `bank_12` OOF | `1–4` Tier 2 FPs (`idx97/151/168`) or Tier 1 FN (`idx385`) on `Dev/Val N=400` | **Rejected** |
| **Subset ablations (`709`, `713`, `719_GKF`, `703_SGKF`)** | `39–40/40` on `P>=0.50` | Every single variant broke `C12` (`S=0.37–0.38`) and/or `Class B` (`S=0.78–0.93`) | **Rejected** |
| **`NoFin SGKF` (`N=719`, 3 non-bank families + `SGKF(5)`)** | `40->29` (`P>=0.50`), **`13->0` Tier 2** (`p_mean 0.7283->0.5598`); Pooled F1 `0.7964->0.8246` | **Failed 2 existing tests:** `C12` WFH recall (`1.0->0.9375`), `SF-007` Class B (`FLAG->BLOCK 0.8792`); plus `legit_health_mychart` Tier 1 `0->20/21` | **Rejected (Caught by full suite)** |
| **Retained `SF-018` Baseline (`824c6c2c...`)** | `40/40` (`13` Tier 2) on `bank_12` | **`259 / 259` full pytest pass**; zero hidden regressions | **Adopted (`NO-CHANGE`)** |

---

## 5. Verification & Explicit Residual-Risk Statement

* **Automated Guardrail Added:** `test_sf019_fold4_baseline_reconciliation_and_no_change_invariants` in `app/tests/test_telecom_eval_suite.py` verifies exact reproduction of the 40 Fold 4 FPs (`13` Tier 2 blocks), `0` contrast-family FPs, presence of `sf019_generalization_comparison.json`, and retention of `824c6c2c...`.
* **Residual Risk (Unresolved Unseen-Family Boundary):** The deployed model (`824c6c2c...`) continues to misclassify unseen benign bank alerts using `"security alert"` + `"unusual"` + `"1 / 2"` wording (`40/40` Tier 1 `FLAG`, `13/40` Tier 2 `BLOCK` in single-family OOF; `48/121` at `P>=0.50` in `LMO_all3`). Safely reducing this without breaking WFH scam recall (`C12`) or broken-phone triage (`SF-007 Class B`) requires structural URL/callback absence features or a non-linear model trained/evaluated on genuine Class C carrier data (`SF-022`), neither of which should be improvised via ad-hoc test weakening.

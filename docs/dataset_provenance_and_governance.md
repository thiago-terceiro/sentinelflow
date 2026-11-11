# SentinelPulse External Dataset Provenance, Suitability Assessment & Quarantine Governance (`SF-010` / `SF-010R`)

> **Executive Status (`2026-11-11 UTC`, `SF-010R` Reproducibility Remediation):**
> - **Primary External Fraud / Smishing Holdout (`Class C`):** **`UNAVAILABLE / BLOCKED`** — `quarantined_test_holdout.json` is intentionally **NOT** created. No audited public dataset currently satisfies all five mandatory gates (clear license, genuinely observed SMS provenance, genuine fraud/smishing vs. benign label fidelity, two-class negative control symmetry, and verbatim unredacted feature fidelity).
> - **`SF-011` Primary Single-Shot Fraud Holdout Gate:** **`BLOCKED_ON_PRIMARY_EXTERNAL_HOLDOUT`**.
> - **Secondary Legacy Public SMS Spam Benchmark:** **`UCI SMS Spam Collection v.1`** (`uci_sms_spam_secondary.json`, `5,574` messages: `4,827 ham`, `747 spam`, `5,159` unique normalized strings, `415` internal duplicates, `0` train/dev overlap) is quarantined strictly as a **legacy public SMS spam transfer benchmark**, preserving original `ham`/`spam` labels verbatim with zero fraud relabeling and zero metric pooling.
> - **Cross-Platform Deterministic Reconstruction (`SF-010R`):** All JSON quarantine artifacts and both governance Markdown copies are normalized to canonical POSIX **LF (`\n`)** line endings via `.gitattributes`, and the committed builder CLI (`build_quarantine_artifacts.py`) independently reconstructs and verifies every digest from pinned immutable upstream sources without importing ONNX or training modules.
> - **Frozen Baseline Guarantees:** Zero changes were made to ONNX weights, training corpus, training code, regex heuristics, composite scoring weights, Platt calibration, or decision thresholds (`0.40` / `0.75`).

---

## 1. Frozen Baseline Artifact Locks (Captured Pre-Change)

Verified on disk prior to `SF-010` execution (`sentinelflow/backend/app/telecom/`):

| Artifact | Verified File / Corpus SHA-256 | Role & Frozen Invariant |
|---|---|---|
| `models/sms_fraud_model.onnx` | `d330466e8a28e43e4d8452fdef76f64470429851f19c568ea83399e7d16beaa9` | Frozen ONNX inference binary (`199,525` bytes) |
| Training Corpus (`build_augmented_dataset`, `N = 703`) | `5bcedbea725ac6c5c2113bfdcf06ec5cb949afd92e556329a94567a8b8abb699` | Frozen `Class A` corpus (`543` legit, `160` fraud, `56` families) |
| Development & Validation Benchmark (`N = 400`) | `210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03` | Frozen `Class B` Dev/Val suite (`200` benign, `200` fraud) |

Machine-readable governance files live under `sentinelflow/backend/app/telecom/datasets/` (committed with canonical **LF** line endings enforced by `.gitattributes`):
- `external_source_assessment.json` — Complete suitability ledger across all 8 audited sources (`canonical LF sha256 = 72fa9ff4a519b75204272ba05d3138f6d0a3b8379b1d0fec493a8d72578f6eb9`), explicitly separating programmatically computed evidence from qualitative manual candidate adjudications
- `uci_sms_spam_secondary.json` — Isolated `UCI SMS Spam Collection v.1` secondary benchmark:
  - Canonical LF Git/Disk file SHA-256: `169277295ceccf600f43eb10f4c61614cc68c1c935d245cf8db8ebf3e31143e7`
  - Timestamp-independent `canonical_content_sha256`: `793d53864389c7ef0b534c943a8baade86bf3c1d61a4f4ea7b2672fa63ce6249`
  - Deterministic `canonical_rows_sha256` (all `5,574` record payloads): `0e643ea940d4c18069c6e5e040a3ac090828771fc00d847f97babf992f6d39a7`
- `quarantined_test_holdout.json` — **Intentionally absent** until a suitable two-class unredacted external fraud/smishing corpus passes all gates

> **Cross-Platform Hash Verification (`SF-010R`):** Earlier `SF-010` commit `0acd742` recorded Windows CRLF working-tree SHA-256 `f35b8ea2ea0738732299498111ee8e89eadd4a207eb53bcf9654d2526e53dce6` while Git stored the LF blob `127ed840...`. To eliminate OS line-ending drift and volatile `retrieval_timestamp_utc` dependency, `dataset_quarantine.verify_uci_artifact_integrity()` reports `raw_disk_sha256`, `lf_canonical_sha256`, `canonical_rows_sha256`, and timestamp-free `canonical_content_sha256` separately, while `build_quarantine_artifacts.py` writes strict LF UTF-8 JSON bytes and `.gitattributes` pins both SF-010R dataset JSON artifacts and these mirrored docs to `eol=lf`.

---

## 2. Canonical Evidence Class Taxonomy

| Evidence Class | Dataset / Source | Sample Scope & Verification Status | Permitted Scientific Claims |
|---|---|---|---|
| **Class A — Train OOF CV** | Curated internal corpus ([`dataset_inventory.json`](../sentinelflow/backend/app/telecom/dataset_inventory.json)) | `N = 703` (`543` legit, `160` fraud across `56` semantic families); nested 5-fold zero-leakage OOF documented in `SF-009` | Internal cross-family generalization & family cluster uncertainty on the curated template taxonomy |
| **Class B — Dev/Val Benchmark** | Curated validation suite ([`evaluate_model.py`](../sentinelflow/backend/app/telecom/evaluate_model.py)) | `N = 400` (`200` hard benign, `200` adversarial smishing); `0` exact overlap with Train `N=703` | Development & regression verification only — **exposed to iterative rule/calibration work; NOT an independent unseen holdout** |
| **Class C — External Public Evaluation** | **Primary Fraud Holdout:** **UNAVAILABLE / BLOCKED**<br>**Secondary Legacy Transfer:** `uci_sms_spam_secondary.json` (`UCI #228`) | Primary two-class external fraud holdout: `0` eligible datasets.<br>Secondary UCI spam corpus: `5,574` records (`4,827 ham`, `747 spam`), `0` Train/DevVal overlap | **Cannot claim external fraud/smishing generalization yet.** Secondary UCI benchmark strictly measures legacy commercial `ham`/`spam` transfer behavior; never pool or relabel `spam -> fraud` |
| **Class D — Production Telemetry** | Carrier / SMSC / optical-tap live traffic + verified CDR ground truth | **Future / Unimplemented** (`0` records in repository) | **None.** Live carrier deployment claims remain invalid until Class D telemetry is captured under real base rates |

---

## 3. External Source Discovery & Suitability Assessment (Phase 1–3)

Every candidate corpus was inspected from primary upstream endpoints, downloaded artifacts (into transient audit storage/memory only), license declarations, label distributions, and text overlap. Note carefully: **external provenance, statistical independence, and domain relevance are distinct properties** — an external dataset can be legally external yet temporally obsolete (`UCI #228` from 2002–2011), heavily PII-redacted (`IMC25`), positive-only, or internally clustered/duplicated (`415` normalized dupes in UCI; templated campaigns in public reports).

| Candidate Dataset (Stable ID) | License & Caveats (Verified) | Observed SMS vs. Synthetic | Verified Counts & Label Taxonomy | Overlap vs. Train / DevVal | Gate Verdict & Exact Failure Reason |
|---|---|---|---|---|---|
| **1. `Fishing for Smishing` (IMC '25)**<br>`github:reportsmishing/Smishing-Dataset-IMC25`<br>Pinned immutable raw URL: `a6175560b57387199871e51fbef6bc523d2516b4` | **`CC BY 4.0`** (verified `LICENSE.txt` & `README.md`; attribution required; no publisher checksum) | **Real observed** user-submitted public reports (Reddit/forums); retrieved via commit `a6175560b57387199871e51fbef6bc523d2516b4`; `final_dataset_output.csv` (`9,462,365` bytes) SHA-256 `1bbd1e9e82c3ea023112207b80da268a5c4a07d2353c2b0898360ab037fa9a64` | `33,869` total (`22,078` English: `banking=10,495`, `others=4,586`, `government=1,922`, `delivery=1,676`, `telecom=1,630`, `spam=1,387`, `wrong number=304`, `hey mum/dad=77`, `empty=1`). Under `scam_type != 'spam'`: **`20,691`** rows -> **`14,363`** unique normalized (includes CSV row `33411` with empty `scam_type`); named subset (`20,690` rows) -> `14,362` unique | `0` exact / `0` normalized / `0` 3-gram >= `0.45` (Train max `0.24`, Dev/Val max `0.1818`; `1` Dev/Val unigram Jaccard `0.50` pair has 3-gram `0.1429`) | **NOT INGESTED AS PRIMARY HOLDOUT:** (1) Positive-only (`0` benign negatives -> cannot measure FPR, Specificity, Precision, or Tier-2 false blocks); (2) Upstream Presidio PII scrubbing rewrote raw URLs/phones/dates (`<URL>` in `6,030/14,363` unique [`8,851/20,691` all] non-spam English rows, raw `https?://` in `287/14,363` unique, `<DATE_TIME>`, `<PHONE_NUMBER>`, false `<US_DRIVER_LICENSE>`), destroying verbatim URL/callback regex signals; (3) Cannot pair `2023+` `<URL>`-tagged positives with `2008` unredacted `UCI ham` without fatal artifact confounding |
| **2. UCI SMS Spam Collection v.1**<br>`uci:228/sms-spam-collection-v1` | **`CC BY 4.0`** (UCI #228 portal; bundled `readme` Section 4 notes Almeida & Gómez Hidalgo copyright, citation, no warranty, user indemnity) | **Real observed** historical SMS (`2002–2011`: UK Grumbletext 425 spam, C. Tagg PhD 450 ham, NUS SMS 3,375 ham, Gómez Hidalgo 1,002 ham / 322 spam); ZIP SHA-256 `1587ea43e58e82b14ff1f5425c88e17f8496bfcdb67a583dbff9eefaf9963ce3` | `5,574` rows (`4,827 ham`, `747 spam`); `5,159` unique normalized (`4,517 ham`, `642 spam`); `415` intra-corpus duplicates (`0` conflicting labels) | `0` exact / `0` norm; max 3-gram Jaccard `0.2857` (Train), `0.1364` (Dev/Val); `0` >= `0.45` | **RETAINED STRICTLY AS SECONDARY LEGACY SPAM BENCHMARK:** Generic 2002–2011 commercial ringtones/prizes/student chat (`ham`/`spam`), NOT SMS fraud/smishing. Stored in `uci_sms_spam_secondary.json`; relabeling or pooling with fraud metrics prohibited |
| **3. Mendeley SMS Phishing Dataset**<br>`doi:10.17632/f45bkkt8pr.1` (Mishra & Soni, 2022) | `CC BY 4.0` with third-party rights warning (mentions web/Pinterest images) | **Contaminated hybrid** — claims web-image OCR but embeds unmodified UCI SMS Spam rows; `Dataset_5971.zip` SHA-256 `9bbf3188fdad81495d8e82825648b9b63b53fc86841a3d26c02629990b233cc3` | `5,971` rows (`4,844 ham`, `638 Smishing/smishing`, `489 spam/Spam`) | Cross-dataset forensic check vs UCI `SMSSpamCollection` | **REJECTED:** Direct string comparison verified **`361 / 638` (`56.6%`) `Smishing` labels are exact copies of 2011 UCI `spam` rows**, plus `4,319` UCI `ham` copies, alongside unverified OCR Pinterest screenshots lacking source IDs |
| **4. Mendeley Balanced LLM Spam/Smishing**<br>`doi:10.17632/vmg875v4xs.1` (Munoz & Islam, 2025) | `CC BY 4.0` | **Synthetic LLM** (API description states *"A large language model (LLM) was trained to create this dataset"*) | Declared `10,191` (`3,397` each `ham`/`spam`/`smishing`) | Not ingested | **REJECTED:** Synthetic LLM-generated messages fail real observed external telemetry provenance |
| **5. SmishTank (`Smishing Dataset I`)**<br>`arxiv:2402.18430v1` (Timko & Rahman, CODASPY '24) | Preprint **`CC BY-NC-SA 4.0`** (NonCommercial); `smishtank.com/dataset` unreachable during audit (`HTTP error / status -1`) | Community reports submitted to Smishtank.com (`1,090` reported samples) | Paper reports `1,090` smishing samples, `0` benign negatives | Not retrievable from canonical URL | **REJECTED:** Non-commercial preprint restrictions, inaccessible authoritative download endpoint, no verified open dataset license, and positive-only coverage |
| **6. Zenodo `15235123` Multiclass Phishing**<br>`doi:10.5281/zenodo.15235123` (Engineering Ingegneria, 2025) | `CC BY 4.0` | Channel mismatch / undocumented origin (`phishing_nlp_dataset.xlsx` SHA-256 `651fb58e1a3ff7808aad12eb5a24a44dc0ba95a4f4da356640d17a830dd8bd32`) | `624` records across 6 classes (`NOT-Malicious`, `Phishing`, etc.) | Not ingested | **REJECTED:** Inspected rows are multi-paragraph 419/advance-fee **email essays** requesting replies by fax/email, not observed telecom SMS |
| **7. GitHub Combined Smishing Aggregators**<br>`shaghayegh-hp/Smishing_Dataset` (+ siblings `MarazMia`, `vineel-pisigma`, `Ren9x`, `tasmco`, `hcphap`, `leason`, `jesusfdez1`) | **NO LICENSE (`license: None`)**; informal research-only README note | Unattributed multi-dataset merges / LLM synthetic (`leason`, `jesusfdez1`); no per-row upstream IDs | Unverified CSV merges (`8.75 MB`) | Not ingested | **REJECTED:** `shaghayegh-hp` has no valid redistribution license and explicitly states *"Messages are relabeled based on the presence of frequent smishing-related keywords"* (circular keyword-heuristic relabeling) |
| **8. HuggingFace `gandharvbakshi/SMS-dataset-OTP-OTP_INTENT_Phishing`** | **CONFLICTING / GATED** (`mit` tag contradicts README requiring DM/email for commercial rights; HTTP `401`) | README explicitly states **"Synthetic + Labeled Indian SMS Dataset"** (includes LLM-labeled files) | README claims `73,470` rows (full download blocked) | Blocked (HTTP 401) | **REJECTED:** Synthetic origin + conflicted commercial licensing + inaccessible gated archive |

*(Additional non-English Zenodo/HF corpora reviewed during discovery — e.g. Roman Urdu `21810885`, Turkish `23374309`, Bengali `17590809`, Korean `jmjmjm3`, ExAIS African-English `AbayomiAlli/SMS-Spam-Dataset` without GitHub license — do not cover SentinelFlow's English A2P/financial SMS threat domain and/or lack formal permissive licensing.)*

> **Hash Provenance Distinction:** Because neither UCI Machine Learning Repository (`#228`) nor GitHub (`Smishing-Dataset-IMC25`) distributes signed SHA-256 manifest files alongside those archives, all SHA-256 digests recorded in this ticket (`1587ea43...`, `7d039a24...`, `1bbd1e9e...`) are **locally computed identity fingerprints** measured directly on the retrieved bytes at the recorded UTC timestamps rather than publisher-signed checksums.

---

## 4. UCI Secondary Benchmark Provenance & Normalization Definition

- **Normalization Rule (`normalize_sms_text`):** Trim outer whitespace, convert text to lowercase, and collapse consecutive whitespace runs (`\s+`) to a single ASCII space.
- **UCI Exact Counts (`N = 5,574`):** `4,827` `ham` (`86.5985%`), `747` `spam` (`13.4015%`); `5,159` unique normalized texts (`4,517 ham`, `642 spam`) plus `415` intra-corpus normalized duplicate rows (`0` label conflicts).
- **Near-Duplicate Audit against SentinelFlow:**
  - Against `Train N=703`: `0` exact text matches, `0` normalized SHA-256 matches, max word 3-gram Jaccard `0.285714` (`uci_228_line_1024`), max unigram Jaccard `0.444444` (`0` pairs `>= 0.45`).
  - Against `Dev/Val N=400`: `0` exact text matches, `0` normalized SHA-256 matches, max word 3-gram Jaccard `0.136364`, max unigram Jaccard `0.310345` (`0` pairs `>= 0.45`).
- **Strict Separation Rule:** `uci_sms_spam_secondary.json` has `is_primary_fraud_holdout = false` and `derived_fraud_label = null` on every row. Any future evaluation against `uci_sms_spam_secondary.json` measures cross-domain `ham`/`spam` flagging behavior ONLY and must never claim fraud detection performance from `spam` labels.

---

## 5. Statistical Reporting & Uncertainty Methodology (Phase 5)

### 5.1 Refutation of Unqualified Margin-of-Error Rules
An earlier roadmap draft referenced a generic heuristic error margin for `N=300` without fixing proportion $p$, class denominator ($n_+$ vs. $n_-$), or cluster correlation. **That approximation is mathematically incorrect and is permanently removed.** All proportion intervals in SentinelFlow must be computed via the exact two-sided Wilson score interval ($z = 1.95996$ for 95% nominal coverage) from verified integer counts $(k, n)$ with explicit class-specific denominators:

$$
\text{CI}_{95\%}(k, n) = \frac{\hat{p} + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \qquad \hat{p} = \frac{k}{n}
$$

- **Separate Class Denominators:** Recall (`TP / n_+`) uses actual fraud positives $n_+$; False Positive Rate (`FP / n_-`) uses actual benign negatives $n_-$. Neither denominator may be replaced by $N_{\text{total}}$, and `n_+` / `n_-` must always be shown verbatim alongside every rate.
- **Hypothetical Integer Reference Table (`compute_exact_wilson_interval`):** *(Note: illustrative feasible integer examples only — no primary Class C holdout rows exist yet.)*

| Hypothetical Integer Ratio (`k / n`) | Point Estimate $\hat{p}$ | Exact 95% Wilson CI | Interval Width (Assumed i.i.d.) |
|---|:---:|:---:|:---:|
| `143 / 150` (Recall / Class-conditional) | `0.953333` | `[0.906814, 0.977213]` | `7.04%` (strongly asymmetric) |
| `150 / 150` (Upper boundary) | `1.000000` | `[0.975030, 1.000000]` | `2.50%` |
| `0 / 150` (Lower boundary / FPR=0) | `0.000000` | `[0.000000, 0.024970]` | `2.50%` |
| `285 / 300` (Total-N binary proportion) | `0.950000` | `[0.919153, 0.969468]` | `5.03%` |
| `150 / 300` (Worst-case binomial variance) | `0.500000` | `[0.443780, 0.556220]` | `11.24%` (`±5.62%`) |

### 5.2 Base-Rate Sensitivity (Balanced Benchmark Precision vs. Carrier Deployment PPV)
Balanced `50/50` evaluation sets alter prevalence-dependent metrics (**Precision / PPV**, **Accuracy**, **PR-AUC**). By Bayes' theorem, holding detector Recall ($\text{TPR}$) and False Positive Rate ($\text{FPR}$) constant under lower true fraud prevalence $\pi$ dramatically reduces operational Precision:

$$
\text{PPV}(\pi) = \frac{\text{TPR} \cdot \pi}{\text{TPR} \cdot \pi + \text{FPR} \cdot (1 - \pi)}
$$

- Example at $\text{TPR} = 0.95$, $\text{FPR} = 0.05$: at balanced $\pi = 0.50$, $\text{PPV} = 95.00\%$; at $\pi = 0.05$, $\text{PPV} = 50.00\%$; at realistic telecom spam/smishing stream prevalence $\pi = 0.01$, $\text{PPV} = \mathbf{16.10\%}$.
- Example at higher specificity ($\text{TPR} = 0.90$, $\text{FPR} = 0.01$): $\pi = 0.50 \Rightarrow 98.90\%$, $\pi = 0.05 \Rightarrow 82.57\%$, $\pi = 0.01 \Rightarrow 47.62\%$.
- Therefore, balanced-set Precision or PR-AUC must never be presented as expected carrier deployment Precision.

### 5.3 Independence Limitation (Cluster / Campaign Dependence)
Message-level Wilson CIs strictly assume independent, identically distributed Bernoulli outcomes. Real SMS traffic contains correlated bursts, automated A2P templates, duplicate campaign blasts, and carrier-specific artifacts. Whenever grouping or campaign metadata exists (such as semantic family clusters in Class A OOF or sender/campaign clusters in Class D carrier logs), **cluster-level bootstrap confidence intervals must be reported alongside or in place of message-level Wilson widths**, and narrow Bernoulli Wilson intervals must never be misrepresented as proof of generalization across unseen campaign archetypes.

---

## 6. Strict Zero-Adaptation Protocol & Unblocking Criteria (`SF-011`)

1. **Pre-Registered Isolation:** Dataset ingestion/quarantine tooling ([`dataset_quarantine.py`](../sentinelflow/backend/app/telecom/dataset_quarantine.py)) is AST-isolated from ONNX Runtime, scikit-learn models, heuristic rules, and scoring pipelines so record selection can never inspect model confidence or errors.
2. **One-Shot Sealing Rule:** Whenever a qualifying primary Class C holdout (`quarantined_test_holdout.json`) is approved and evaluated in a future `SF-011` run, **zero post-holdout adaptation is permitted**:
   - No retraining or corpus additions informed by holdout misses/errors.
   - No heuristic regex edits, weight shifts, Platt parameter tuning, or threshold shifts (`0.40` / `0.75`).
   - Any post-holdout fix invalidates that holdout permanently and requires procuring a newly sealed, disjoint holdout before re-claiming unseen-holdout generalization.
3. **What Unblocks `SF-011`:** Acquiring either (a) de-identified, CDR-verified two-class carrier telemetry (`Class D` raw/minimal-redacted legitimate transactional SMS + confirmed smishing under compatible non-confounding formatting), or (b) a vetted open-licensed verbatim English two-class corpus containing verified fraud/smishing and matched benign transactional controls passing all five gates in `external_source_assessment.json`. Until then, **`SF-011` remains `BLOCKED_ON_PRIMARY_EXTERNAL_HOLDOUT`**.

---

## 7. Reproducible Artifact Reconstruction & Independent Verification (`SF-010R`)

The committed generator and verification CLI ([`build_quarantine_artifacts.py`](../sentinelflow/backend/app/telecom/build_quarantine_artifacts.py)) reconstructs both JSON governance artifacts deterministically without touching the workspace or importing ONNX/training modules:

- **AST-Only Corpus Extraction:** Reads `train_onnx_model.py` (`build_augmented_dataset`, `N = 703`) and `evaluate_model.py` (`get_held_out_evaluation_set`, `N = 400`) via a restricted pure-Python AST evaluator (`_PureAstEvaluator`) with zero `exec`/`eval` calls and asserts exact SHA-256 equality with `FROZEN_TRAINING_DATASET_SHA256` and `FROZEN_DEV_VAL_DATASET_SHA256`.
- **Pinned Upstream Checksums:** Downloads (or loads explicit `--uci-zip-path` / `--imc25-csv-path` overrides from):
  - UCI `#228` ZIP (`https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip`, expected ZIP SHA-256 `1587ea43...`) extracting strictly `SMSSpamCollection` (`7d039a24...`) and `readme` (`8753cd2d...`).
  - IMC '25 CSV pinned to immutable commit `a6175560b57387199871e51fbef6bc523d2516b4` (`https://raw.githubusercontent.com/reportsmishing/Smishing-Dataset-IMC25/a6175560b57387199871e51fbef6bc523d2516b4/dataset/final_dataset_output.csv`, expected SHA-256 `1bbd1e9e...`).
- **Verification & Regeneration Commands (run from `sentinelflow/backend/`):**
  - Full independent temp-dir reconstruction & verification: `uv run python -m app.telecom.build_quarantine_artifacts --verify`
  - Offline repository/CRLF/content/docs audit: `uv run python -m app.telecom.build_quarantine_artifacts --verify --offline`
  - Regenerate canonical LF artifacts explicitly: `uv run python -m app.telecom.build_quarantine_artifacts --output-dir app/telecom/datasets --write-canonical`

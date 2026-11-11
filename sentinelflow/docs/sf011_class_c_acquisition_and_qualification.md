# SF-011 — Primary External Fraud Dataset Acquisition & Class C Qualification Report

**Ticket:** `SF-011` (`AI-14`)  
**Ticket Type:** External Dataset Acquisition, Qualification, & Experimental Design Investigation (No Holdout Evaluation / No Model Changes)  
**Primary Class C Holdout Status:** `UNAVAILABLE / BLOCKED` (`quarantined_test_holdout.json` **NOT** created)  
**Machine-Readable Evidence Ledger:** [`sf011_acquisition_routes.json`](../sentinelflow/backend/app/telecom/datasets/sf011_acquisition_routes.json) (`sha256 = 8150a2125b66c99cb10d3199a0026fae711a202dd5511a4d5572d63d466caebc`, `42,563` bytes, LF)  
**Deterministic Gate Evaluator:** [`evaluate_class_c_qualification_routes`](../sentinelflow/backend/app/telecom/dataset_quarantine.py)

---

## 1. Executive Summary & Frozen Baseline Preservation

A systematic investigation of **12 concrete acquisition routes** beyond the 8 sources rejected in `SF-010` — covering newly published academic SMS phishing/spam datasets, open ML/research data repositories (GitHub, Mendeley, Kaggle, Hugging Face, Zenodo), MNO-partnered academic collaborations, US regulatory/consumer-protection agencies (FCC, FTC, CFPB), and telecom/anti-fraud industry consortia (APWG, M3AAWG, GSMA, direct Carrier/CPaaS enclaves) — concludes that **no currently accessible public dataset passes all seven mandatory Class C qualification gates**.

Consequently, **`quarantined_test_holdout.json` remains intentionally absent**, no model evaluation or metric publication was performed under `SF-011`, and the frozen baseline established prior to `SF-010` remains completely unaltered:

| Baseline Asset | Canonical LF / Binary SHA-256 | Status under `SF-011` |
| --- | --- | --- |
| Frozen ONNX Classifier (`sms_fraud_model.onnx`) | `d330466e8a28e43e4d8452fdef76f64470429851f19c568ea83399e7d16beaa9` | Unchanged (zero retraining, zero inference) |
| Frozen Training Corpus (`N = 703`) | `5bcedbea725ac6c5c2113bfdcf06ec5cb949afd92e556329a94567a8b8abb699` | Unchanged |
| Frozen Dev/Val Benchmark (`N = 400`) | `210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03` | Unchanged |
| Secondary Legacy Benchmark (`uci_sms_spam_secondary.json`) | `169277295ceccf600f43eb10f4c61614cc68c1c935d245cf8db8ebf3e31143e7` | Unchanged (secondary Class B/E reference only) |
| `SF-010` Source Assessment (`external_source_assessment.json`) | `72fa9ff4a519b75204272ba05d3138f6d0a3b8379b1d0fec493a8d72578f6eb9` | Unchanged |

---

## 2. Formal 7-Gate Class C Qualification Standard

To qualify as a defensible unseen external two-class Class C holdout, a candidate source must pass **all seven gates** enforced by `evaluate_class_c_qualification_routes` in [`dataset_quarantine.py`](../sentinelflow/backend/app/telecom/dataset_quarantine.py):

1. **`authenticity_and_relevance`**: Real observed SMS payloads relevant to contemporary financial fraud/smishing and modern transactional A2P/P2P traffic (synthetic, translated, simulated, or multi-channel email/chat dumps are disqualified).
2. **`two_class_coverage`**: Both verified fraud/smishing positives ($n_+$) and contemporaneous legitimate/benign controls ($n_-$) drawn from a **compatible sampling frame**.
3. **`label_quality`**: Documented human or incident-disposition labeling rubric, adjudication protocol, measured inter-rater agreement or dispute resolution, and disclosed label uncertainty (unlabeled dumps and rule-inferred pseudo-labels are excluded).
4. **`provenance_and_lawful_access`**: Verifiable source identity, collection timeframe and geography, documented lawful consent/IRB/DUA basis, and explicit license permitting research/evaluation (unlicensed repos fail).
5. **`evaluation_suitability`**: Intact structural signals (unredacted URL hosts/TLDs, callback lures, formatting) with **zero cross-class era or PII-redaction shortcuts**.
6. **`independence`**: Verified zero/quantified exact, normalized, word 3-gram ($\ge 0.45$), and semantic-family overlap against Train ($N = 703$) and Dev/Val ($N = 400$).
7. **`frozen_evaluation_feasibility`**: Pre-registered AST-isolated quarantine with cryptographic source/artifact hashes, one-shot execution, and zero post-evaluation adaptation.

### Strict Exclusions (`SF-011` Invariants)

- **No cross-source positive/negative stitching:** Never pair unredacted modern URL-smishing positives (e.g., NCSU `wspr-ncsu/sms-phishing` or `IMC '25`) with pre-2015 P2P student chat (`UCI #228` `2002-2011` or `NUS` `2013-2015`), because channel/era differences alone separate classes trivially.
- **No synthetic negatives or synthetic smishing:** Never fabricate benign or fraud messages to balance single-class feeds (disqualifies LLM/synthetic datasets such as `electricsheepafrica/africa-smishing-sms-phishing` or simulated `PhishVN`).
- **No heuristic pseudo-labeling:** Never run heuristics, regexes, or ONNX scores to auto-label raw mobile inboxes such as Kaggle `dshah1612/sms-data`.
- **Zero raw PII disclosure:** Raw phone numbers, victim names, payment PANs, SSNs, and individual personal emails are strictly barred from committed JSON/Markdown files and verification logs.

---

## 3. Empirical Investigation of 12 Acquisition Routes

All 12 routes below were independently inspected and cross-checked against `sf011_acquisition_routes.json` and the frozen SentinelFlow corpora (`Train N=703`, `Dev/Val N=400`, `UCI #228`):

### 3.1 Acquisition Route Qualification Decision Matrix

| Route ID | Category | License / Legal Basis | $n_+$ / $n_-$ | Overlap vs. Train / DevVal | Failing Class C Gates | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `wspr_ncsu_sms_phishing_sp24` | Published Research (IEEE S&P '24) | `MIT` (verified `LICENSE`) | `68,029` / `0` (`28,749` uniq) | `0` exact / `0` norm / `0` 3-gram | `authenticity_and_relevance`, `two_class_coverage`, `evaluation_suitability` | `NOT_QUALIFIED` |
| `spstudy_super_sms_ieeeaccess24` | Published Research (IEEE Access '24) | **`None`** (unlicensed GitHub) | `26,178` / `40,830` | `0` Train/DevVal (`34,822` NUS + `4,164` UCI) | `authenticity_and_relevance`, `two_class_coverage`, `label_quality`, `provenance_and_lawful_access`, `evaluation_suitability`, `frozen_evaluation_feasibility` | `NOT_QUALIFIED` |
| `spamhunter_usenix22` | Published Research (USENIX '22) | **`None`** (unlicensed GitHub) | `947` / `0` | Not ingested (`0` benign, no license) | `authenticity_and_relevance`, `two_class_coverage`, `label_quality`, `provenance_and_lawful_access`, `evaluation_suitability`, `frozen_evaluation_feasibility` | `NOT_QUALIFIED` |
| `exais_sms_nigerian_cpe22` | Published Research (`CPE 2022`) | **`None`** on canonical GitHub | `2,350` / `2,890` (`3,399` uniq) | `0` Train/DevVal (`15` UCI) | `authenticity_and_relevance`, `two_class_coverage`, `label_quality`, `provenance_and_lawful_access`, `evaluation_suitability`, `frozen_evaluation_feasibility` | `NOT_QUALIFIED` |
| `mendeley_znsk27yk3h_v2` | Published Research (`Mendeley v2`, Oct 2025) | `data_licence: None` in API JSON | `310` / `213` (`520` uniq, ~`404` ASCII) | `0` Train/DevVal (`2` UCI) | `authenticity_and_relevance`, `two_class_coverage`, `label_quality`, `provenance_and_lawful_access`, `evaluation_suitability`, `frozen_evaluation_feasibility` | `NOT_QUALIFIED` |
| `kaggle_dshah1612_sms_data` | Public Repository (Unlabeled Inbox) | `CC0` tag; **0 IRB/consent docs** | `0` / `0` (`100,243` unlabeled; `59,150` uniq) | `0` Train/DevVal (`68` UCI) | `authenticity_and_relevance`, `two_class_coverage`, `label_quality`, `provenance_and_lawful_access`, `evaluation_suitability`, `frozen_evaluation_feasibility` | `NOT_QUALIFIED` |
| `hf_electricsheepafrica_africa_smishing` | Public Repository (Synthetic) | `license: other` | `0` / `0` (`is_synthetic=1` on `94/100` sample) | Disqualified (synthetic) | All 7 gates | `NOT_QUALIFIED` |
| `zenodo_24133847_phishvn` | Public Repository (Zenodo 2026) | `CC BY 4.0` | `193` / `143` (simulated Vietnamese) | Disqualified (simulated/non-English) | `authenticity_and_relevance`, `two_class_coverage`, `label_quality`, `evaluation_suitability` | `NOT_QUALIFIED` |
| `mno_7726_ucl_imdea_collaboration` | Academic + MNO Collaboration (`arXiv:2508.05276`) | Gated MNO DUA + Ethics | Private (`1.35M` 7726 forwards; `0` benign) | No public corpus | `two_class_coverage`, `provenance_and_lawful_access`, `evaluation_suitability`, `independence`, `frozen_evaluation_feasibility` | `REQUIRES_DUA_AND_BENIGN_PAIRING` |
| `smishtank_codaspy24_author_route` | Academic Author Collaboration (`arXiv:2402.18430`) | `CC BY-NC-SA 4.0` (`/dataset` HTTP `404`) | ~`1,090` / `0` | No public download | `two_class_coverage`, `provenance_and_lawful_access`, `evaluation_suitability`, `independence`, `frozen_evaluation_feasibility` | `NOT_QUALIFIED` |
| `regulatory_fcc_ftc_cfpb_channels` | US Regulators (FCC, FTC, CFPB) | Public metadata / FOIA & LE restriction | `0` / `0` (FCC has `0` body cols; CFPB essays) | N/A | All 7 gates | `NOT_QUALIFIED` |
| `consortia_apwg_m3aawg_gsma_mno_enclave` | Consortia & Carrier/CPaaS Enclave | Requires DUA, Membership, IRB, Enclave | Prospective (`n_+`, `n_-`) | Prospective isolation | `two_class_coverage`, `label_quality`, `provenance_and_lawful_access`, `evaluation_suitability`, `independence` | `REQUIRES_PARTNERSHIP_DUA_AND_ETHICS_APPROVAL` |

### 3.2 Key Disqualification Findings from Direct Data Audits

1. **Why Public Two-Class Releases Fail Upon Inspection (`spstudy`, `exais`, `mendeley_znsk27yk3h`):**
   - **`spstudy` (`Super SMS`, IEEE Access '24):** Despite advertising 67,010 rows (`26,178` label `1`, `40,830` label `0`, `2` empty), direct fingerprint matching proved that **`94.4%` (`38,534 / 40,830`) of its benign class comes from legacy pre-2015 student P2P chat** (`34,786` NUS SMS Corpus rows + `3,748` UCI `ham` rows, plus 1 mislabeled UCI `spam` row). Only **`4 / 40,830` (`0.0098%`)** of its benign rows contain an `http(s)://` link versus **`5,231 / 26,178` (`19.98%`)** in label `1`, while `2,343` NUS `<...>` tags sit overwhelmingly in class `0`. Furthermore, the GitHub repository has **`license: None`**.
   - **`ExAIS_SMS` (Nigeria, 2022):** GitHub repo lacks any `LICENSE` file, reflects 2013-2016 regional `SPAM`/`HAM` (`3,994` rows dated 2014), manually masks tokens with `***`/`xxx` (`360 / 5,240` rows), has `15` exact normalized overlaps with UCI `#228`, and contains only `63` HTTP URLs.
   - **`mendeley_znsk27yk3h.2` (Oct 2025):** Mendeley API metadata returns `data_licence: None`, `119 / 523` rows contain non-ASCII Bangla scripts (~`404` ASCII rows total), collection mixes SMS with chat, emails, Google Forms, and handwritten student submissions, and PII/contacts/URLs were anonymized.
2. **Why `wspr-ncsu/sms-phishing` (IEEE S&P '24) Is High-Signal Yet Disqualified as Class C:**
   - Verified **MIT License**, real unredacted URLs (`13,088` HTTP matches, `0` Presidio `<URL>` tags), `68,029` rows (`28,749` unique normalized across `35,128` campaigns from `2022-05-01` to `2023-06-01`), and **zero exact/normalized/word-3-gram ($\ge 0.45$) overlap** against both SentinelFlow Train and Dev/Val.
   - However, it is strictly **positive-only (`n_- = 0`)**: non-flagged gateway messages were discarded by design, the traffic mirrors public disposable receive-SMS websites rather than consumer inbox telemetry, and URL-intelligence labeling excludes non-URL callback/conversational bank lures.
3. **Why Unlabeled Public Dumps (`kaggle_dshah1612_sms_data`) & US Regulators Fail:**
   - Kaggle `dshah1612/sms-data` (`100,243` rows across `93` accounts) has **zero verified labels** (`68` normalized overlaps with UCI spam appear inside unlabelled inbox traffic), partial `*`/`X` masking (`8,945` rows), and zero verifiable end-user consent/IRB documentation.
   - US regulatory portals do not release dual-class SMS payloads: FCC `3xyp-aqkj` exposes 17 metadata columns with **0 text body columns**; FTC Consumer Sentinel restricts access strictly to sworn law-enforcement partners; CFPB API returns prose dispute narratives masked with `XXXX`.
4. **Why Academic MNO Collaborations (`arXiv:2508.05276`) & `SmishTank` Do Not Unblock Today Without Enclave Pairing:**
   - The UCL/IMDEA MNO 7726 paper analyzed `1.35M` carrier forwards (`kappa = 0.71-0.84`) under strict MNO confidentiality where URLs are truncated to domains and benign non-reported SMS are absent (`n_- = 0`).
   - Direct HTTP probing confirmed `https://smishtank.com/` (`HTTP 200`), `https://smishtank.com/dataset` (**`HTTP 404`**), `CC BY-NC-SA 4.0` preprint terms, and positive-only coverage (~`1,090` rows).

---

## 4. Statistical Sample-Size, Precision, & Operational PPV Framework

**Why No Single Fixed "$N$" Cutoff Is Defensible:** Evaluation power and confidence width cannot be reduced to an arbitrary total count $N$ (such as `N = 200` or `N = 1,000`) because:

1. **Separate Class Denominators:** Sensitivity/Recall ($\widehat{\text{TPR}}$) scales strictly with fraud positives $n_+$, whereas Specificity ($\widehat{\text{TNR}}$) and False Positive Rate ($\widehat{\text{FPR}} = 1 - \widehat{\text{TNR}}$) scale strictly with benign controls $n_-$.
2. **Probability-Dependent Binomial Variance:** Binomial variance $p(1-p)/n$ is small near extreme operational targets ($0.95$ or $0.01$) and widest near $0.50$. Using an exact 95% Wilson score interval avoids normal-approximation collapse at $\hat{p} = 0$ or $\hat{p} \approx 1$.
3. **Campaign Clustering Inflation ($\text{DEFF}$):** Multiple SMS variants from one smishing kit share templates and URL infrastructure, shrinking effective independent sample size to $n_{\text{eff}} = n / \text{DEFF}$ where $\text{DEFF} = 1 + (m - 1)\rho$ (average cluster size $m$, intra-cluster correlation $\rho$).
4. **Rare-Base-Rate PPV Collapse:** Because live carrier smishing prevalence $\pi$ is typically low ($\le 1\%$ or $\le 0.2\%$), small errors in $\widehat{\text{FPR}}$ trigger dramatic drops in Positive Predictive Value:
   $$\text{PPV}(\pi) = \frac{\pi \cdot \text{TPR}}{\pi \cdot \text{TPR} + (1 - \pi) \cdot \text{FPR}}$$

### 4.1 Exact 95% Wilson Confidence Interval Reference Table

Values below are computed verbatim via `compute_exact_wilson_interval` (`dataset_quarantine.py`):

| Scenario | Metric Role | $k / n$ | Point Estimate | 95% Wilson Lower | 95% Wilson Upper | Width |
| --- | --- | --- | --- | --- | --- | --- |
| Modest Recall pilot | Recall / TPR ($n_+$) | `143 / 150` | `0.953333` | `0.906814` | `0.977213` | `0.070399` |
| Target Recall baseline | Recall / TPR ($n_+$) | `285 / 300` | `0.950000` | `0.919153` | `0.969468` | `0.050315` |
| Tighter Recall CI (<4% width) | Recall / TPR ($n_+$) | `475 / 500` | `0.950000` | `0.927232` | `0.965906` | `0.038674` |
| Undersized benign control (`0 FP`) | FPR upper bound ($n_-$) | `0 / 150` | `0.000000` | `0.000000` | `0.024970` | `0.024970` |
| Insufficient benign control (`0 FP`) | FPR upper bound ($n_-$) | `0 / 300` | `0.000000` | `0.000000` | `0.012643` | `0.012643` |
| Minimum exploratory benign (`0 FP`) | FPR upper bound ($n_-$) | `0 / 500` | `0.000000` | `0.000000` | `0.007624` | `0.007624` |
| **Recommended Class C benign floor (`0 FP`)** | **FPR upper bound ($n_-$)** | **`0 / 1000`** | **`0.000000`** | **`0.000000`** | **`0.003827`** | **`0.003827`** |
| Target high-specificity control (`0 FP`) | FPR upper bound ($n_-$) | `0 / 2000` | `0.000000` | `0.000000` | `0.001917` | `0.001917` |
| `0.5%` FPR at $n_- = 1,000$ | FPR ($n_-$) | `5 / 1000` | `0.005000` | `0.002138` | `0.011651` | `0.009513` |
| `1.0%` FPR at $n_- = 1,000$ | FPR ($n_-$) | `10 / 1000` | `0.010000` | `0.005441` | `0.018309` | `0.012868` |
| `0.5%` FPR at $n_- = 2,000$ | FPR ($n_-$) | `10 / 2000` | `0.005000` | `0.002718` | `0.009180` | `0.006462` |

### 4.2 Operational Base-Rate PPV Sensitivity at `TPR = 0.95`

Computed via `adjust_precision_for_base_rate` (`dataset_quarantine.py`):

| Benign FPR | Balanced $\pi = 0.50$ | Concentrated $\pi = 0.05$ | Guardrail $\pi = 0.01$ | Realistic Carrier $\pi = 0.002$ |
| --- | --- | --- | --- | --- |
| `5.0%` (`0.050`) | `0.950000` | `0.500000` | `0.161017` | `0.036680` |
| `1.0%` (`0.010`) | `0.989583` | `0.833333` | `0.489691` | `0.159933` |
| `0.2%` (`0.002`) | `0.997899` | `0.961538` | `0.827526` | `0.487680` |

**Resulting Effective Sample Minimums for Class C Authorization:**
- **Confirmed Fraud / Smishing ($n_+$):** $\ge 300\text{–}500$ **independent-equivalent** (`DEFF`-adjusted across distinct campaigns/templates) observed smishing messages covering modern financial/brand impersonation, callback lures, and URL-bearing lures ($\pm 2.5\%$ to $\pm 1.9\%$ Wilson half-width at $0.95$ TPR).
- **Legitimate / Benign Controls ($n_-$):** $\ge 1,000\text{–}2,000$ **independent-equivalent** contemporaneous A2P/P2P controls stratified across bank alerts, OTP/2FA, delivery tracking, telecom billing notices, and conversational peer traffic so that even `0 FP` certifies an upper 95% Wilson bound $\le 0.38\%\text{–}0.19\%$ and defends Tier-2 false-block rates at $\pi \le 1\%$.

---

## 5. Concrete Acquisition & Privacy-Preserving Enclave Execution Plan

Because **public open downloads cannot lawfully supply paired contemporary benign transactional SMS alongside verified fraud without structural confounding**, unblocking future Class C (or direct carrier Class D) evaluation requires executing one of two partner-gated paths:

1. **Primary Viable Path — Direct Carrier / CPaaS / Fintech Shadow Enclave (`Class C / D`):**
   - Execute an institutional **Data Use Agreement (DUA)** + **IRB / privacy legal review** (GDPR/CCPA/ECPA) with a mobile network operator, tier-1 CPaaS aggregator, or bank fraud-ops team.
   - Sample a **contemporaneous two-class panel** inside the partner's security boundary: adjudicated fraud/7726-confirmed smishing ($n_{+,\text{eff}} \ge 300\text{–}500$) paired with stratified benign A2P/P2P traffic ($n_{-,\text{eff}} \ge 1,000\text{–}2,000$) logged under the **same formatting rules** (preserving URL hosts/TLDs and structural cues while hashing/tokenizing direct MSISDNs/names).
   - Run inference **zero-export inside the partner enclave** against pinned immutable model hash `d330466e...` and export only aggregate counts, Wilson intervals, cluster-adjusted SEs, and Tier-1/Tier-2 disposition rates.
2. **Secondary Institutional Path — Consortia & MNO Research Teams (`APWG eCX`, `M3AAWG`, `arXiv:2508.05276`):**
   - Pursue institutional affiliation or industry sponsorship via `M3AAWG` / `GSMA Foundry` or an `APWG` cybercrime research grant (`membership@apwg.org`) paired with an MNO collaborator able to supply matched non-7726 benign control slices inside a restricted enclave.

### Pre-Conditions Required Before Authorizing Any Future Evaluation Ticket

1. Signed DUA/ethics authorization explicitly covering offline zero-adaptation benchmark evaluation.
2. Verified satisfaction of **all 7 boolean gates** in `evaluate_class_c_qualification_routes(ledger)`.
3. Automated zero-overlap audit confirming exact, normalized, and 3-gram independence from `Train (N=703)` and `Dev/Val (N=400)`.
4. Pre-registration of exact file/artifact SHA-256 digests and one-shot execution plan prior to computing any prediction score.

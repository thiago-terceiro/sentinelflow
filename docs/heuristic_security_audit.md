# SentinelPulse Heuristic Security & Complexity Audit (`SF-005` Hardening)

- **Audited Module**: [`sentinelflow/backend/app/telecom/onnx_engine.py`](../sentinelflow/backend/app/telecom/onnx_engine.py) (`HEURISTIC_RULES`, `normalize_heuristic_text`, `evaluate_heuristics`, `compute_composite_score`)
- **Gateway Input Boundary**: [`TelecomClassifyRequest`](../sentinelflow/backend/app/api/telecom.py) (`message: min_length=1, max_length=2000`; raised from `1600` in `SF-015` after atomic-group ReDoS hardening)
- **Benchmark Corpus (`Dev/Val`, N=400)**: 200 benign / 200 fraud (`benchmark_predictions_400.json`), strictly separated from synthetic adversarial fixtures.
- **Notice on Evidence Scope**: Benchmark counts below reflect deterministic evaluation on the `Dev/Val N=400` corpus (**Evidence Class B**). Production carrier SMS generalization remains **Evidence Class D: None / Outstanding** pending external real-world logs.

---

## 1. Escalation Architecture Summary

In [`compute_composite_score`](../sentinelflow/backend/app/telecom/onnx_engine.py#L249-L316) (with `V = 0.0` in offline/single-message evaluation):
1. **Standalone Block Override (`H >= 0.80`)**: Immediately forces `S = 1.0` (`BLOCK`), overriding any low ML score (`P`). Currently **only one** rule (`RULE:TAX_ARREST_THREAT`, weight `0.80`) reaches this threshold alone.
2. **Compound Rule Escalation (`+0.12`, cap `0.95`)**: When `len(signals) >= 2` and at least one matched rule has weight `>= 0.50`, `evaluate_heuristics` adds `+0.12` to `max_heuristic`.
   - Any rule with weight **`>= 0.68`** paired with a benign-vocabulary helper such as `RULE:STANDALONE_URL` (`0.25`) or `RULE:GENERIC_DELIVERY_KEYWORD` (`0.20`) escalates to **`>= 0.80`**, triggering an immediate `S = 1.0` (`BLOCK`) regardless of ML probability `P`.
   - Rules with weight `>= 0.50` and `< 0.68` (`0.55`–`0.65`) escalate to `0.67`–`0.77` when compounded, substantially boosting `S` and lowering the ML probability `P` needed for `BLOCK` (`>= 0.75`).
3. **Standalone Sub-Override (`0.50 <= H < 0.80`)**: Does not force `S = 1.0`, but activates the continuous heuristic gate `alpha = 1.0` and raises Tier-1 `FLAG` (`>= 0.40`) / Tier-2 `BLOCK` (`>= 0.75`) risk proportionally.
   - Example: At `H = 0.70, V = 0.0`, `W_H = 0.35*0.70 + 0.30*0.40 = 0.365`, so `S = 0.365 + 0.635 * P` (`P >= 0.0552` reaches `FLAG`; `P >= 0.6063` reaches `BLOCK`).
   - At `H = 0.65, V = 0.0`, `W_H = 0.3325`, so `S = 0.3325 + 0.6675 * P` (`P >= 0.1012` reaches `FLAG`; `P >= 0.6255` reaches `BLOCK`).
4. **Low-Weight Helper Signals (`H <= 0.25`)**: Cannot trigger Tier-1 or Tier-2 alone (`alpha = 0.0` when `P < 0.15`), **but** silently trigger `+0.12` escalation whenever paired with any `>= 0.50` rule.

---

## 2. Complete Inventory of All 13 `HEURISTIC_RULES`

Benchmark hit counts below were measured on `N=400` (`200 benign`, `200 fraud`), listing `(comp=X)` where `HEURISTIC:COMPOUND_SIGNALS` also fired.

| # | Rule ID (`onnx_engine.py` lines) | Weight | Escalation Class | Dev/Val N=400 Hits (Benign / Fraud) | Worst-Case Scaling `N=400 -> 1600 -> 3200` | Primary Precision / Evasion Weaknesses |
|---|---|---:|---|---|---|---|
| 1 | `RULE:HIGH_RISK_SHORTLINK` (L34–40) | `0.55` | Compound `>= 0.50` -> `0.67` | `0 / 0` (`comp: 0 / 0`) | `0.012 -> 0.058 -> 0.098 ms` (**O(N)**) | Matches legitimate marketing/personal `bit.ly`/`tinyurl.com`/`t.co` links; paired with benign `"package"` keyword escalates to `0.67`. Covers only 6 shorteners (`cutt.ly`, `rb.gy`, etc.); misses custom/new shorteners. |
| 2 | `RULE:SUSPICIOUS_TLD` (L42–48) | `0.65` | Compound `>= 0.50` -> `0.77` (or `>= 0.77` triggers `STANDALONE_URL`) | `0 / 116` (`comp: 0 / 116`) | `0.012 -> 0.016 -> 0.017 ms` (**O(N)**) | Flags benign `.info`/`.me`/`.club`/`.online`/`.site` domains (plus automatically co-fires `STANDALONE_URL` -> minimum `0.77`!). Cannot fire without a URL; misses `.com`/`.net` phishing. |
| 3 | `RULE:URGENT_ACCOUNT_LOCKOUT` (L50–57) | `0.70` | Compound `>= 0.68` -> **`0.82 BLOCK`** | `0 / 30` (`comp: 0 / 30`) | `0.612 -> 9.674 -> 38.240 ms` (**O(N^2)**) | Unanchored `A.*B` exhibits quadratic backtracking on repeated `"urgent "` prefixes. Compounding with benign URL escalates `0.70 -> 0.82` (`BLOCK`). Can false-trigger on benign SaaS security notices mentioning `"unauthorized login ... verify"` or `"suspended ... reactivate"`. |
| 4 | `RULE:DELIVERY_FEE_SCAM` (L59–67) | `0.65` | Compound `>= 0.50` -> `0.77` | `0 / 34` (`comp: 0 / 34`) | `1.206 -> 18.985 -> 71.874 ms` (**O(N^2) >15ms SLA at 1600**) | Unanchored `A.*B` exhibits **O(N^2) ReDoS exceeding 15ms SLA** within `max_length=1600` (`18.98ms` single rule on repeated `"usps "`). No quotation/educational exclusion. |
| 5 | `RULE:TAX_ARREST_THREAT` (L69–103) | **`0.80`** | **Standalone `>= 0.80 BLOCK`** | `0 / 18` (`comp: 0 / 6`) | `0.062 -> 0.232 -> 0.443 ms` (**O(N)**) | Hardened in SF-005 (coercion + authority + extortion demand; removed bare `"final notice"`, bare `"case #"`, bare `"tax penalty abatement"`; added `(800)` phone + `"unpaid back taxes"` + invisible/NFKC normalization). Remaining limits: quoted scam advisories (`E01`, `E02`), Cyrillic homoglyphs (`D08`), leetspeak (`D09`), paraphrase without extortion lexicon. |
| 6 | `RULE:CRYPTO_OR_GIVEAWAY_PROMISE` (L105–112) | `0.75` | Compound `>= 0.68` -> **`0.87 BLOCK`** | `0 / 5` (`comp: 0 / 5`) | `0.028 -> 0.112 -> 0.230 ms` (**O(N)**) | Exact phrase match (`guaranteed return`, `free bitcoin`, `claim $100`+). Vulnerable to trivial paraphrasing (`"risk-free BTC yield"`) and benign financial articles quoting `"guaranteed return"`. |
| 7 | `RULE:UNPAID_TOLL_INVOICE` (L114–120) | `0.70` | Compound `>= 0.68` -> **`0.82 BLOCK`** | `0 / 12` (`comp: 0 / 12`) | `0.888 -> 14.996 -> 60.061 ms` (**O(N^2)**) | Unanchored `A.*B` hits `15.0ms` at `N=1600` on repeated `"toll "`. Any legitimate toll invoice reminder with a valid toll agency URL (`STANDALONE_URL`) compounds to **`0.82` -> immediate `BLOCK`**. |
| 8 | `RULE:TECH_SUPPORT_INVOICE_SCAM` (L122–130) | `0.70` | Compound `>= 0.68` -> **`0.82 BLOCK`** | `0 / 4` (`comp: 0 / 0`) | `0.856 -> 12.561 -> 50.618 ms` (**O(N^2)**) | Unanchored `A.*B` (`12.56ms` at `N=1600` on repeated `"norton "`). Legitimate Norton/McAfee/Geek Squad billing or cancellation confirmation containing `"charged"`/`"refund"`/`"cancellation"` + portal URL compounds to **`0.82` -> `BLOCK`**. |
| 9 | `RULE:FAMILY_IMPERSONATION_MESSAGING_LURE` (L132–145) | `0.65` | Compound `>= 0.50` -> `0.77` | `0 / 25` (`comp: 0 / 0`) | `0.075 -> 0.307 -> 0.535 ms` (**O(N)**) | Anchored `^` keeps complexity linear. Negative lookahead blocks repair-shop confirmations, yet benign family emergency discussions mentioning broken phone + Zelle/Venmo can still trigger if phrased with `"mom"` + `"dropped phone"`. |
| 10 | `RULE:WORK_FROM_HOME_SCAM` (L147–153) | `0.65` | Compound `>= 0.50` -> `0.77` | `0 / 0` (`comp: 0 / 0`) | `0.237 -> 4.777 -> 18.465 ms` (**O(N^2)**) | Unanchored `A.*B` quadratic scaling. Legitimate HR/manager communication discussing `"work from home"` + `"reviewing"` or `"manager"` triggers `0.65` (`0.77` with URL). Zero benchmark coverage (`0 / 0`). |
| 11 | `RULE:SIM_SWAP_OR_KYC_SCAM` (L155–161) | `0.70` | Compound `>= 0.68` -> **`0.82 BLOCK`** | `0 / 0` (`comp: 0 / 0`) | `0.148 -> 1.989 -> 7.936 ms` (**O(N^2)**) | High standalone weight (`0.70`) on short phrases (`"esim transfer"`, `"update kyc"`, `"sim card.*deactivation"`). Verified FP: benign carrier security warning (`B03`, `H=0.70`, `FLAG`) or carrier FAQ + HTTPS link (`E06`, `H=0.82` -> `BLOCK`). Zero benchmark coverage (`0 / 0`). |
| 12 | `RULE:STANDALONE_URL` (L163–170) | `0.25` | Low helper (amplifies `>= 0.50` by `+0.12`) | `0 / 148` (`comp: 0 / 121`) | `0.001 -> 0.001 -> 0.001 ms` (**O(N)**) | Note: matches benign HTTPS URLs and **also co-fires alongside `SUSPICIOUS_TLD`** (every `.xyz`/`.top`/`.info` URL automatically triggers both `SUSPICIOUS_TLD` `0.65` + `STANDALONE_URL` `0.25` + `0.12` = `0.77`). |
| 13 | `RULE:GENERIC_DELIVERY_KEYWORD` (L172–179) | `0.20` | Low helper (amplifies `>= 0.50` by `+0.12`) | `22 / 24` (`comp: 0 / 24`) | `0.230 -> 0.975 -> 2.057 ms` (**O(N)**) | Matches 22 benign benchmark delivery texts cleanly alone (`H=0.20` suppressed when `P < 0.15`), **but** if paired with `SIM_SWAP` or `URGENT_ACCOUNT_LOCKOUT`, adds `+0.12`. Note negative lookahead excludes `"fee"`/`"customs"`/`"unpaid"` globally after match. |

---

## 3. SF-005 Forensic Findings & Change Summary

### 3.1 Defects Exposed & Fixed in `RULE:TAX_ARREST_THREAT` / `evaluate_heuristics` (Phase 11)
Post-`fb3ee14` adversarial probing revealed four concrete defects before hardening:
1. **CPA Guidance False `BLOCK` (`A01`)**: `"IRS Form 843 Final Notice guidance: wait until the IRS processes your tax penalty abatement case #1290 before calling our office."` previously scored `H=0.80 -> BLOCK (S=1.0)` because Lookahead 1 accepted bare `"final notice"` and Lookahead 3 accepted bare `"tax penalty"` (`"tax penalty abatement"`) and bare `"case #1290"`.
2. **Attorney Deadline False `BLOCK` (`A02`)**: `"Attorney Reminder: Final notice to submit exhibits for civil court case #2026-14 by Friday. Call 415-555-0188 if delayed."` previously scored `H=0.80 -> BLOCK (S=1.0)` via `"final notice"` + `"court"` + `"case #2026-14"`.
3. **Police News Report False `BLOCK` (`A03`)**: `"News Report: Police issued an arrest warrant in the downtown jewelry heist case #9941; call tip line 415-555-0122 with info."` previously scored `H=0.80 -> BLOCK (S=1.0)` via `"arrest warrant"` + `"police"` + `"case #9941"`.
4. **Parenthesized Callback / Unpaid Back Taxes False Negative (`C01`)**: `"IRS FINAL NOTICE: Federal arrest warrant active for unpaid back taxes. Call (800) 555-0199 to avoid detention."` missed `RULE:TAX_ARREST_THREAT` (`H=0.0, S=0.7431 FLAG` instead of `BLOCK`) because `"unpaid back taxes"` and `"Call (800) 555-0199"` were outside the demand regex.
5. **Zero-Width / Fullwidth Unicode Bypass (`D01`, `D02`, `D03`)**: Zero-width spaces (`\u200b`), soft hyphens (`\u00ad`), ZWJ (`\u200d`), and fullwidth compatibility glyphs bypassed regex boundaries prior to `normalize_heuristic_text()`.

**Verification after fix**:
- `Dev/Val N=400` heuristic trigger diff vs `fb3ee14`: **0 rows changed** (Sample 184 remains `ALLOW H=0.0 S=0.0825`; all 30 `smish_legal_extortion` remain `BLOCK S=1.0`; Tier-2 `FP=1` at Sample 93).
- `A01`, `A02`, `A03` dropped from `H=0.80 BLOCK` to `H=0.00` (all 15 Category A fixtures produce `0` heuristic blocks; note frozen TF-IDF model alone still scores `P=0.4486–0.6028 -> FLAG` on `A01..A03` without heuristic inflation).
- `C01`, `D01`, `D02`, `D03` all match `RULE:TAX_ARREST_THREAT` (`H=0.80 -> BLOCK S=1.0`).
- Flat top-level anchored lookaheads `^(?=...)(?=...)(?=...)` keep `RULE:TAX_ARREST_THREAT` strictly **$O(N)$** (`0.232ms` at `N=1600`, `0.443ms` at `N=3200`). Nested lookaheads inside lookahead 3 MUST be avoided because testing proved nested `(?=.*(?=.*...))` triggered quadratic backtracking (`202.0ms` at `N=3200`).

### 3.2 Honest Residual Risks Requiring Follow-Up Backlog Tickets (NOT Masked)
1. **Unanchored `A.*B` Quadratic ReDoS in 6 Sibling Rules (`P1` Security/Latency Backlog — `SF-006`)**:
   - `RULE:DELIVERY_FEE_SCAM` (`18.98ms` at `N=1600` repeated `"usps "`), `RULE:UNPAID_TOLL_INVOICE` (`15.00ms`), `RULE:TECH_SUPPORT_INVOICE_SCAM` (`12.56ms`), `RULE:URGENT_ACCOUNT_LOCKOUT` (`9.67ms`), `RULE:WORK_FROM_HOME_SCAM` (`4.78ms`), and `RULE:SIM_SWAP_OR_KYC_SCAM` (`1.99ms`) breach or approach the `15ms` end-to-end SLA within the API's `max_length=1600` limit when malicious payloads repeat trigger keywords without the trailing term. Rewriting those unanchored rules with linear single-pass / line-safe bounds or atomic grouping (`(?>...)`) without changing multi-line semantics is recommended in `SF-006`.
2. **Compound `>= 0.80` Over-Escalation on Unrelated Benign Notifications (`P1` Precision Backlog)**:
   - `RULE:SIM_SWAP_OR_KYC_SCAM` (`0.70`), `RULE:UNPAID_TOLL_INVOICE` (`0.70`), `RULE:TECH_SUPPORT_INVOICE_SCAM` (`0.70`), and `RULE:URGENT_ACCOUNT_LOCKOUT` (`0.70`) all escalate to `0.82` (`BLOCK`) when any ordinary `https://` URL (`RULE:STANDALONE_URL`, `0.25`) is present (`E06`: `"Important account message: confirm your eSIM transfer settings or visit https://carrier-portal.example.com"` -> `H=0.82 BLOCK`).
3. **Zero Benchmark Coverage on Three Active Rules**:
   - `RULE:HIGH_RISK_SHORTLINK`, `RULE:WORK_FROM_HOME_SCAM`, and `RULE:SIM_SWAP_OR_KYC_SCAM` have `0 / 400` hits in `Dev/Val`.
4. **Quoted Scam Warnings (`E01`, `E02`, `E04`) & Cross-Script Homoglyphs / Leetspeak (`D08`, `D09`, `D10`)**:
   - Regex rules have no syntactic quote/warning parser (`"Fraud Alert: scammers send 'IRS FINAL NOTICE...'"` still triggers `H=0.80`).
   - Cross-script Cyrillic homoglyphs (`U+0430` in `аrrest wаrrant`), stripped-vowel leetspeak, and whitespace-split URLs evade lexical heuristics (dropping `D08`/`D09` from `BLOCK` to ML-only `FLAG`). Confusable transliteration (UTS #39 skeleton) is a recommended future improvement.
5. **Frozen TF-IDF Model Calibration on Legal/News Vocabulary**:
   - Even with `H=0.00`, `A01` (`P=0.4486`), `A02` (`P=0.5705`), `A03` (`P=0.6028`), and `Sample 93` (`P=0.8591`) are flagged or blocked solely by the TF-IDF logistic regression model, which is frozen out-of-scope for `SF-005`.

### 3.3 Dropped-Clause Adversarial Hardening & Boundary Limits (`SF-005B`)
- **Detected Gap**: Attackers omitting URLs, dollar amounts, and callback phone numbers but issuing urgent reply/contact coercion (`"County Sheriff Desk: Bench warrant issued for contempt of court. Contact us urgently before arrest."`, `DC05`) bypassed `RULE:TAX_ARREST_THREAT` (`H=0.0, P=0.3421 -> ALLOW`) because Lookahead 3 only matched `call` CTAs and missed `contact us / reply / respond` urgent CTAs.
- **Minimal Correction Applied**: Extended Lookahead 1 with `(?:marshal|officer|agent|deputy|police)s?\s+(?:dispatched|en\s+route)` and Lookahead 3 CTA verbs with `(?:call|contact\s+us|reply|respond)\s+(?:immediately|urgently|now|...)`, preserving strict **$O(N)$** scaling (`0.0256ms` at `N=400`, `0.1898ms` at `N=3200`) and **0 diffs** across `Dev/Val N=400`; all `7/7` `DC_B01..DC_B07` probes remain `RULE:TAX_ARREST_THREAT`-clean (`0` heuristic hits `> 0.25`, `0` Tier-2 `BLOCK`s; `DC_B01..DC_B06` score `ALLOW` while `DC_B07` triggers ML-only `P=0.4694` Tier-1 `FLAG` at `H=0.0`).
- **Measured Outcome & Honest 3-Clause Boundaries (`DROPPED_CLAUSE_CORPUS`)**:
  - `DC03` (*"Authorities have issued a warrant in your name. Contact us immediately to avoid detention."*) -> `BLOCK` (`H=0.80`).
  - `DC05` (*"County Sheriff Desk: Bench warrant issued for contempt of court. Contact us urgently before arrest."*) -> `BLOCK` (`H=0.80`).
  - `DC06` (*"IRS Enforcement Division: Federal arrest warrant pending under your SSN. Respond immediately to avoid jail."*) -> `BLOCK` (`H=0.80`).
  - `DC01` (*"FINAL NOTICE: An arrest warrant has been issued by the IRS under your name. Face immediate detention."*) -> `FLAG` (`H=0.00, P=0.6266`; escalated cleanly without forcing a false-positive-prone 2-clause hard override).
  - `DC02` (*"Federal magistrate warrant issued for your arrest."*) -> `ALLOW` (`H=0.00, P=0.1474`; insufficient evidence of extortion/CTA for `H=0.80 BLOCK`).
  - `DC04` (*"US Customs Enforcement: Seizure warrant active on your identity. Officers en route for immediate detention."*) -> **Documented Heuristic Limitation** (`H=0.00, P=0.2602 -> ALLOW`): when ALL payment, URL, phone, AND reply/contact verbs are dropped simultaneously, promoting `"under your name / on your identity"` alone to `H=0.80` false-blocked quoted security warnings (`DC_B05`). Preserved clean 3-clause orthodoxy rather than introducing `DC_B05` false blocks.

# SF-022 — Independent External SMS Fraud Dataset Qualification & Frozen Generalization Evaluation Report

**Linear Ticket:** `AI-35` (`SF-022`)  
**Outcome:** **`UNAVAILABLE / BLOCKED` (Defensible No-Go after Phase 1 Discovery)**  
**Class C Artifact Created:** `None` (no qualifying source found)  
**Model Changes:** `None` (`SF-018` frozen baseline artifact retained under `SF-019` no-change decision: SHA-256 `824c6c2c254791205184efadd8f0b2dc43f22e7222b411e75c2b99c340a9604b` untouched)

---

## 1. Decision & Governance Discipline

Prior audits (`SF-010`, `SF-010R`, and `SF-011`) evaluated 8 public corpus candidates and 12 acquisition routes under 7 mandatory Class C gates (`authenticity_and_relevance`, `two_class_coverage`, `label_quality`, `provenance_and_lawful_access`, `evaluation_suitability`, `independence`, `frozen_evaluation_feasibility`) and found **zero** qualifying real-world Class C sources.

In `SF-022`, we conducted fresh Phase 1 discovery across public ML hubs (Hugging Face Hub, Zenodo, Mendeley Data) for 2024–2026 releases. **Zero newly discovered candidates passed all 7 Phase 1 gates.** Per ticket requirements:
* We stopped after Phase 1 and did **not** weaken Class C qualification standards.
* We did **not** substitute `dev_val_400`, `UCI #228`, synthetic LLM outputs, or stitched positive/negative corpora as Class C evidence.
* Phase 2 and Phase 3 were cleanly skipped, no `quarantined_test_holdout.json` was fabricated, and the frozen `SF-018` model (`824c6c2c...`, retained under `SF-019`) and thresholds remain unchanged.

---

## 2. Phase 1 Newly Audited Candidate Ledger

Machine-readable ledger: `sentinelflow/backend/app/telecom/datasets/sf022_qualification_ledger.json`.

| Candidate Source | Publisher / License | Sample Count & Origin | Failed Class C Gates | Verified Rejection Evidence |
|---|---|---|---|---|
| `redasers/difraud` (`sms/` splits) | Hugging Face DIFrauD / `MIT` | `6,574` (`5,300` legit / `1,274` spam+fraud) | `authenticity_and_relevance`, `label_quality`, `independence` | Direct hash verification against `uci_sms_spam_secondary.json` shows **`4,752 / 6,574` (`72.28%`)** are exact `normalized_sha256` copies of legacy `UCI #228` (`2002–2011`), while merging promotional spam into label `1`. |
| Mendeley `vmg875v4xs.1` (`Balanced Dataset for Spam and Smishing Detection using LLMs`) | Muñoz & Islam / Mendeley API `license: null` | `10,191` (`3,397` Ham / `3,397` Spam / `3,397` Smishing); **LLM-generated/augmented** | `authenticity_and_relevance`, `provenance_and_lawful_access` | Mendeley public API record states *"A large language model (LLM) was trained to create this dataset"* to synthetically balance classes. Fails real-world authenticity and exposes an unspecified API license. |
| `ealvaradob/phishing-dataset` (SMS slice) | Hugging Face / `Apache-2.0` | Derived repackaging | `authenticity_and_relevance`, `independence` | Mirrors Mendeley `f45bkkt8pr.1` (Mishra & Soni), previously audited in `SF-010` (`56.6%` normalized UCI #228 overlap + redaction confounding). |
| `grephon777/phishing-dataset` | Hugging Face / `Apache-2.0` | Derived repackaging | `authenticity_and_relevance`, `independence` | Community derivative mirror of Mishra & Soni / `ealvaradob`, not an independent primary carrier collection. |
| `UniqueData/spam-text-messages-dataset` | Hugging Face / `CC-BY-NC-ND-4.0` | `25` sample rows (teaser) | `two_class_coverage`, `provenance_and_lawful_access`, `evaluation_suitability` | Only 25 rows exposed; `NC-ND` restricts derivative processing; no documented carrier collection protocol. |
| `Zenodo 17551984` (`PhishVN`) | Zenodo / Mendeley | Vietnamese threat/URL + LLM-paraphrased evaluation | `authenticity_and_relevance`, `two_class_coverage` | Non-English (`vi`) URL/phishing intelligence and LLM-paraphrased evasion tests; wrong language and synthetic paraphrasing. |
| `Zenodo 14607454` (`SMS Fraud Classification dataset for Chichewa`) | Zenodo (`10.5281/zenodo.14607454`) | `676` Chichewa + human/machine translations | `authenticity_and_relevance`, `evaluation_suitability` | Low-resource language + translation artifacts rather than native contemporary English transactional/smishing SMS traffic. |

*(Plus all 8 prior candidates in `external_source_assessment.json` and 12 acquisition routes in `sf011_acquisition_routes.json`, totaling 27 assessed sources/routes with 0 Class C passes.)*

---

## 3. Explicit Blockers & Honest Generalization Limitation

1. **Public Open-Web Gap:** Open academic SMS datasets still overwhelmingly recycle `UCI #228` (2002–2011), redistribute Mishra & Soni `f45bkkt8pr.1` with redaction shortcuts, expose positive-only smishing reports without contemporaneous benign carrier transactional SMS (`SmishTank`), or balance classes using LLMs (`vmg875v4xs.1`).
2. **Unresolved Real-World Evidence Gap:** External real-world generalization of `SentinelPulse` remains **unverified against an independent real-world two-class Class C holdout**. Only gated institutional partnerships (private carrier A2P/P2P telemetry under DUA + IRB + incident adjudication, or regulated consortium access) can unblock Phase 2 and Phase 3.
3. **Integrity Preserved:** Leaving Class C external evaluation `UNAVAILABLE / BLOCKED` prevents false confidence from contaminated or synthetic holdouts and preserves audit readiness for any future authorized DUA corpus.

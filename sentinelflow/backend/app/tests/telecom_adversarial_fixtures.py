"""Structured adversarial and contrastive evaluation fixtures for SentinelPulse (SF-005).

Strictly isolated from `train_onnx_model.py` and the `Dev/Val` N=400 benchmark in
`evaluate_model.py`. All cases here carry explicit evidence-class labels:
  - Evidence Class C: Synthetic Adversarial & Stress Cases
  - Evidence Class E: Ambiguous / Dual-Use / Undetermined Cases
  - Evidence Class D (External Real-World Production Validation): None / Outstanding
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Literal

from app.telecom.onnx_engine import InferenceResult, OnnxInferenceEngine, get_inference_engine

CategoryCode = Literal["A", "B", "C", "D", "E"]
EvidenceClass = Literal["C", "E"]
GroundTruthLabel = Literal["BENIGN", "FRAUD", "AMBIGUOUS"]


@dataclass(frozen=True)
class AdversarialCase:
    """Single deterministic adversarial/contrastive stress sample."""

    case_id: str
    category: CategoryCode
    category_name: str
    evidence_class: EvidenceClass
    expected_label: GroundTruthLabel
    text: str
    rationale: str


ADVERSARIAL_CORPUS: tuple[AdversarialCase, ...] = (
    # --- Category A: Legitimate Legal, Tax, Court, Police & Delivery (15 cases) ---
    AdversarialCase(
        case_id="A01",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "IRS Form 843 Final Notice guidance: wait until the IRS processes "
            "your tax penalty abatement case #1290 before calling our office."
        ),
        rationale="CPA administrative Form 843 abatement guidance with case number and callback.",
    ),
    AdversarialCase(
        case_id="A02",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Attorney Reminder: Final notice to submit exhibits for civil court "
            "case #2026-14 by Friday. Call 415-555-0188 if delayed."
        ),
        rationale="Counsel reminder referencing court exhibit deadline, case #, and office phone.",
    ),
    AdversarialCase(
        case_id="A03",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "News Report: Police issued an arrest warrant in the downtown jewelry heist "
            "case #9941; call tip line 415-555-0122 with info."
        ),
        rationale="Journalistic police report citing arrest warrant, case #, and tip line.",
    ),
    AdversarialCase(
        case_id="A04",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Bookkeeper Note: Your 2025 federal tax draft PDF is uploaded to the "
            "client portal for review whenever you have time."
        ),
        rationale="Benign accountant draft tax review notice.",
    ),
    AdversarialCase(
        case_id="A05",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Process server stopped by our lobby looking for the old tenant "
            "who moved out last spring."
        ),
        rationale="P2P neighbor mention of process server without coercive extortion demand.",
    ),
    AdversarialCase(
        case_id="A06",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Did our accountant file the Q2 quarterly estimated state tax voucher "
            "yet before tomorrow's cutoff?"
        ),
        rationale="Personal family/partner question on tax filing.",
    ),
    AdversarialCase(
        case_id="A07",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "County Jury Commission: Reporting Group 4 is excused from Monday "
            "morning voir dire and rescheduled for May 19."
        ),
        rationale="Benign municipal jury duty postponement SMS.",
    ),
    AdversarialCase(
        case_id="A08",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Did you see the appellate ruling reporting that the magistrate vacated "
            "an old zoning warrant from 2019?"
        ),
        rationale="Conversational legal news referencing magistrate and vacated warrant.",
    ),
    AdversarialCase(
        case_id="A09",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Sheriff Office Community Alert: Neighborhood watch meeting moved to "
            "Court St Annex at 7 PM Thursday."
        ),
        rationale="Benign law-enforcement community outreach text.",
    ),
    AdversarialCase(
        case_id="A10",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Payroll Notice: Your updated W-2 federal tax withholding statement is "
            "available in the HR employee portal."
        ),
        rationale="Employer payroll tax document notice.",
    ),
    AdversarialCase(
        case_id="A11",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text="Your UPS Ground parcel is scheduled for delivery tomorrow between 1:00 PM and 4:00 PM.",
        rationale="Benign carrier delivery window update.",
    ),
    AdversarialCase(
        case_id="A12",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Superior Court E-Filing: Your civil motion for docket #CV-2026-441 "
            "was accepted by the clerk."
        ),
        rationale="Legitimate electronic court filing confirmation.",
    ),
    AdversarialCase(
        case_id="A13",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "DHL Broker Update: Customs declaration cleared for shipment #8821 "
            "with zero balance due."
        ),
        rationale="Legitimate customs clearance receipt stating zero balance.",
    ),
    AdversarialCase(
        case_id="A14",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text="IRS Refund Status: Your federal return was accepted; allow 21 days for direct deposit.",
        rationale="Informational refund timing update without coercion.",
    ),
    AdversarialCase(
        case_id="A15",
        category="A",
        category_name="legit_legal_tax",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "EZPass Statement Ready: View your monthly toll summary online at "
            "https://www.ezpassny.com"
        ),
        rationale="Legitimate toll statement summary with official domain.",
    ),
    # --- Category B: Benign with Suspicious Vocabulary / Awareness (10 cases) ---
    AdversarialCase(
        case_id="B01",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "TechFix Repair: Your mum phone with cracked screen is ready for pickup; "
            "total quote $85, reply STOP."
        ),
        rationale="Repair shop notification exercising negative lookahead on broken phone.",
    ),
    AdversarialCase(
        case_id="B02",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Security PSA: Scammers text fake IRS arrest warrant threats asking "
            "victims to buy gift cards."
        ),
        rationale="Educational scam awareness PSA referencing IRS warrant threats.",
    ),
    AdversarialCase(
        case_id="B03",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Carrier Security Note: Never approve an unexpected eSIM transfer "
            "request on your account."
        ),
        rationale="Probes known RULE:SIM_SWAP_OR_KYC_SCAM lexical sensitivity on carrier advice.",
    ),
    AdversarialCase(
        case_id="B04",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Annual Reminder: Your Norton subscription renews next month; "
            "manage auto settings in your portal."
        ),
        rationale="Benign antivirus subscription notice without refund/debit lure.",
    ),
    AdversarialCase(
        case_id="B05",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text="Dropped my phone in the pool! Ping me on WhatsApp tonight so we can coordinate dinner.",
        rationale="Casual P2P broken phone + WhatsApp mention without family/payment ask.",
    ),
    AdversarialCase(
        case_id="B06",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Finance Podcast: Tonight our analysts discuss bitcoin volatility and "
            "international wire transfer fees."
        ),
        rationale="Benign media text containing crypto and wire transfer keywords.",
    ),
    AdversarialCase(
        case_id="B07",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text="Chase Security: Your verification code is 482910. Never share this code with anyone.",
        rationale="Legitimate branded OTP verification message.",
    ),
    AdversarialCase(
        case_id="B08",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text="HR Operations: Thanks for logging your work from home schedule for Monday and Wednesday.",
        rationale="Benign HR email/SMS containing work-from-home vocabulary.",
    ),
    AdversarialCase(
        case_id="B09",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text="Turnpike Advisory: Official toll agencies never threaten immediate arrest by text message.",
        rationale="Consumer advisory using toll + arrest keywords benignly.",
    ),
    AdversarialCase(
        case_id="B10",
        category="B",
        category_name="benign_suspicious_vocab",
        evidence_class="C",
        expected_label="BENIGN",
        text=(
            "Branch Update: Your online banking access has been restored following "
            "your in-person ID check."
        ),
        rationale="Confirmation of restored account access without phishing prompt.",
    ),
    # --- Category C: Genuine Unseen Extortion / Smishing (16 cases) ---
    AdversarialCase(
        case_id="C01",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "IRS FINAL NOTICE: Federal arrest warrant active for unpaid back taxes. "
            "Call (800) 555-0199 to avoid detention."
        ),
        rationale="Unpaid back taxes + parenthesized toll-free extortion callback.",
    ),
    AdversarialCase(
        case_id="C02",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "US Marshals Desk: Officer dispatched for contempt of court unless "
            "$650 federal penalty paid within 2 hours."
        ),
        rationale="Marshal dispatch + contempt coercion + urgency payment demand (low ML P guard).",
    ),
    AdversarialCase(
        case_id="C03",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "US Customs Bureau: Seizure warrant issued on package #7741; pay unpaid "
            "customs duty immediately: https://bit.ly/customs-774"
        ),
        rationale="Customs seizure extortion combined with delivery lure and shortlink.",
    ),
    AdversarialCase(
        case_id="C04",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "County Sheriff Warrant Unit: Bench warrant issued for failure to appear. "
            "Resolve bail fee within 4 hours: http://county-bail.top/991"
        ),
        rationale="Sheriff FTA bench warrant + urgent bail URL on suspicious TLD.",
    ),
    AdversarialCase(
        case_id="C05",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "District Court Clerk: Process server assigned for unpaid court fine. "
            "Call +1 888 555 0177 now to avoid arrest."
        ),
        rationale="Process server extortion using international +1 spacing and unpaid court fine.",
    ),
    AdversarialCase(
        case_id="C06",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Federal Tax Enforcement: Tax lien seizure pending; settle $1,250.00 "
            "tax balance immediately at http://irs-resolve.xyz/pay"
        ),
        rationale="Federal tax lien seizure extortion + payment portal.",
    ),
    AdversarialCase(
        case_id="C07",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Bank Security Urgent: Online profile temporarily disabled due to unauthorized "
            "login. Reactivate now at http://secure-verify.biz/login"
        ),
        rationale="Urgent account lockout + suspicious TLD credential phish.",
    ),
    AdversarialCase(
        case_id="C08",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "DHL Express Alert: Parcel held at depot for unpaid customs duty. "
            "Pay redelivery charge: https://bit.ly/dhl-fee"
        ),
        rationale="Parcel customs duty scam via shortlink.",
    ),
    AdversarialCase(
        case_id="C09",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Turnpike Toll Notice: Unpaid toll invoice #4419 accruing late fee. "
            "Settle at http://turnpike-pay.site/4419"
        ),
        rationale="Turnpike unpaid toll invoice smish.",
    ),
    AdversarialCase(
        case_id="C10",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Geek Squad Billing Desk: Norton auto-renewal charged $499.99; "
            "call 1-800-555-0133 for immediate cancellation refund."
        ),
        rationale="Tech-support invoice refund callback scam.",
    ),
    AdversarialCase(
        case_id="C11",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Hi Mum dropped my phone and phone screen cracked, borrowing a friend temporary "
            "number. Need $300 Cash App urgent bill."
        ),
        rationale="Family impersonation broken-phone payment smish.",
    ),
    AdversarialCase(
        case_id="C12",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Earn $250/day work from home reviewing merchant listings. "
            "Message hiring manager on Telegram now!"
        ),
        rationale="Work-from-home Telegram task scam.",
    ),
    AdversarialCase(
        case_id="C13",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text="Carrier Urgent: Complete update KYC today or face SIM card immediate deactivation.",
        rationale="SIM swap / KYC urgent deactivation scam.",
    ),
    AdversarialCase(
        case_id="C14",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "VIP Desk: Join our crypto signal group for 400% guaranteed return and "
            "free bitcoin giveaway today."
        ),
        rationale="Crypto investment signal / giveaway lure.",
    ),
    AdversarialCase(
        case_id="C15",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Federal Revenue Collections: Enforcement levy requires settlement of $890 "
            "at http://rev-clear.info within 60 minutes or deputies attend your home."
        ),
        rationale="Paraphrased unseen revenue coercion without standard warrant phrase.",
    ),
    AdversarialCase(
        case_id="C16",
        category="C",
        category_name="unseen_extortion_smishing",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Federal Tax Bureau: Seizure warrant active for delinquent tax debt. "
            "Call 1-877-555-0145 within 3 hours to avoid prosecution."
        ),
        rationale="Non-URL telephone extortion demanding urgent callback to avoid prosecution.",
    ),
    # --- Category D: Adversarial Obfuscation & Structural Perturbations (10 cases) ---
    AdversarialCase(
        case_id="D01",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "IRS FINAL NOTICE: Legal a\u200brrest w\u200barrant issued for unpaid taxes. "
            "Call 1-800-555-0199 immediately."
        ),
        rationale="Zero-width space obfuscation inside arrest warrant phrase.",
    ),
    AdversarialCase(
        case_id="D02",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "IRS FINAL NOTICE: Federal a\u00adrrest war\u200drant active for "
            "delin\u200bquent taxes. Call (800) 555-0199."
        ),
        rationale="Soft-hyphen + ZWJ + zero-width space obfuscation across multiple tokens.",
    ),
    AdversarialCase(
        case_id="D03",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "IRS FINAL NOTICE: \uff21\uff52\uff52\uff45\uff53\uff54 warrant pending "
            "for delinquent taxes. Call 1-800-555-0199."
        ),
        rationale="Fullwidth Unicode ASCII homoglyph requiring NFKC normalization.",
    ),
    AdversarialCase(
        case_id="D04",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Call 888-555-0199 within 2 hours to pay $420 court fine — bench warrant "
            "pending from County Magistrate."
        ),
        rationale="Word-order swap placing extortion demand before authority and threat.",
    ),
    AdversarialCase(
        case_id="D05",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "IRS!! Notice: ARREST WARRANT (active) — pay $450.00 federal penalty NOW "
            "at http://irs-fine.top/8"
        ),
        rationale="Heavy punctuation and uppercase noise around extortion payload.",
    ),
    AdversarialCase(
        case_id="D06",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            ("Community bulletin: local library hours extend Friday. " * 6)
            + "IRS FINAL NOTICE: Arrest warrant active for delinquent taxes. "
            "Call 1-800-555-0199. Keep neighborhood clean."
        ),
        rationale="Benign padding attempting to dilute TF-IDF fraud density (salting attack).",
    ),
    AdversarialCase(
        case_id="D07",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "Magistrate Court: Process server dispatched for failure to appear; "
            "settle $500 fine now at https://court-fee.xyz/pay "
            + ("Please drive safely in school zones. " * 10)
        ),
        rationale="Trailing benign filler appended to extortion payload.",
    ),
    AdversarialCase(
        case_id="D08",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text=(
            "IRS FINAL NOTICE: Federal \u0430rrest w\u0430rrant pending for "
            "delinquent taxes. Call 1-800-555-0199."
        ),
        rationale="Documented cross-script Cyrillic 'a' spoofing probe (evades regex, ML FLAG).",
    ),
    AdversarialCase(
        case_id="D09",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text="IRS NOTICE: Fdrl arr3st wrrnt pending 4 unpaid tax3s call 800-555-0199",
        rationale="Documented vowel-dropped leetspeak evasion probe (evades regex, ML FLAG).",
    ),
    AdversarialCase(
        case_id="D10",
        category="D",
        category_name="adversarial_obfuscation",
        evidence_class="C",
        expected_label="FRAUD",
        text="IRS Notice: Arrest warrant pending unless fine settled now at http : / / irs-pay . top",
        rationale="Documented spaced defanged URL probe (evades URL/tax rules, ML BLOCK).",
    ),
    # --- Category E: Contextually Ambiguous / Dual-Use (6 cases) ---
    AdversarialCase(
        case_id="E01",
        category="E",
        category_name="contextually_ambiguous",
        evidence_class="E",
        expected_label="AMBIGUOUS",
        text=(
            "Fraud Alert from your bank: scammers are sending texts reading "
            "'IRS FINAL NOTICE: Arrest warrant issued for delinquent taxes. "
            "Call 1-800-555-0199'. Never reply."
        ),
        rationale="Quoted extortion payload embedded verbatim inside a bank anti-fraud alert.",
    ),
    AdversarialCase(
        case_id="E02",
        category="E",
        category_name="contextually_ambiguous",
        evidence_class="E",
        expected_label="AMBIGUOUS",
        text=(
            "Hey look at this weird text I just got: 'Magistrate Court Notice: "
            "Process server dispatched unless $480 fine is paid today https://court-fee.xyz' "
            "— spam right?"
        ),
        rationale="Peer forwarding a suspicious quoted SMS asking for confirmation.",
    ),
    AdversarialCase(
        case_id="E03",
        category="E",
        category_name="contextually_ambiguous",
        evidence_class="E",
        expected_label="AMBIGUOUS",
        text=(
            "Final notice regarding account balance $240 due Friday. "
            "Call 800-555-0140 to resolve or dispute."
        ),
        rationale="Terse debt/billing notice without clear spoofing vs legitimate sender context.",
    ),
    AdversarialCase(
        case_id="E04",
        category="E",
        category_name="contextually_ambiguous",
        evidence_class="E",
        expected_label="AMBIGUOUS",
        text="Example phishing payload for training: USPS redelivery unpaid fee at http://usps-help.top",
        rationale="Security training example containing live delivery phish URL.",
    ),
    AdversarialCase(
        case_id="E05",
        category="E",
        category_name="contextually_ambiguous",
        evidence_class="E",
        expected_label="AMBIGUOUS",
        text="Your verification code is 774291.",
        rationale="Minimal unbranded OTP string impossible to verify out of session context.",
    ),
    AdversarialCase(
        case_id="E06",
        category="E",
        category_name="contextually_ambiguous",
        evidence_class="E",
        expected_label="AMBIGUOUS",
        text=(
            "Important account message: confirm your eSIM transfer settings or visit "
            "https://carrier-portal.example.com"
        ),
        rationale="Dual-use eSIM advisory + URL illustrating SIM_SWAP + STANDALONE_URL compound.",
    ),
)


def compute_confusion_metrics(tp: int, fp: int, tn: int, fn: int) -> dict[str, float | int]:
    """Computes standard binary confusion counts and derived rates cleanly."""
    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
    f1 = (
        round((2 * precision * recall) / (precision + recall), 4)
        if (precision + recall) > 0
        else 0.0
    )
    fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0
    fnr = round(fn / (fn + tp), 4) if (fn + tp) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "fnr": fnr,
    }


def normalized_sha256(text: str) -> str:
    """Returns deterministic SHA-256 of whitespace/case-normalized SMS text."""
    canonical = " ".join(text.lower().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evaluate_adversarial_suite(
    engine: OnnxInferenceEngine | None = None,
    cases: tuple[AdversarialCase, ...] = ADVERSARIAL_CORPUS,
) -> dict[str, object]:
    """Evaluates synthetic adversarial fixtures and reports per-category metrics.

    Refuses to conflate synthetic Categories A-D into an external generalization score;
    explicitly surfaces Evidence Class C (synthetic) vs E (ambiguous) and notes that
    Evidence Class D (external real-world traffic) remains Outstanding / None.
    """
    active_engine = engine or get_inference_engine()
    per_category_rows: dict[CategoryCode, list[dict[str, object]]] = {
        "A": [],
        "B": [],
        "C": [],
        "D": [],
        "E": [],
    }

    for case in cases:
        res: InferenceResult = active_engine.predict(case.text)
        per_category_rows[case.category].append(
            {
                **asdict(case),
                "verdict": res.verdict,
                "fraud_score": res.fraud_score,
                "heuristic_score": res.heuristic_score,
                "onnx_probability": res.onnx_probability,
                "signals": res.signals,
                "tax_rule_matched": "RULE:TAX_ARREST_THREAT" in res.signals,
            }
        )

    binary_summary: dict[str, object] = {}
    for cat in ("A", "B", "C", "D"):
        cat_code: CategoryCode = cat
        rows = per_category_rows[cat_code]
        t1_tp = t1_fp = t1_tn = t1_fn = 0
        t2_tp = t2_fp = t2_tn = t2_fn = 0
        tax_hits = 0

        for row in rows:
            is_fraud = row["expected_label"] == "FRAUD"
            verdict = str(row["verdict"])
            if bool(row["tax_rule_matched"]):
                tax_hits += 1

            pred_t1 = verdict in ("FLAG", "BLOCK")
            if is_fraud and pred_t1:
                t1_tp += 1
            elif not is_fraud and pred_t1:
                t1_fp += 1
            elif not is_fraud and not pred_t1:
                t1_tn += 1
            else:
                t1_fn += 1

            pred_t2 = verdict == "BLOCK"
            if is_fraud and pred_t2:
                t2_tp += 1
            elif not is_fraud and pred_t2:
                t2_fp += 1
            elif not is_fraud and not pred_t2:
                t2_tn += 1
            else:
                t2_fn += 1

        binary_summary[cat_code] = {
            "count": len(rows),
            "evidence_class": "C (Synthetic Adversarial)",
            "tax_rule_hits": tax_hits,
            "tier1_flag_or_block": compute_confusion_metrics(t1_tp, t1_fp, t1_tn, t1_fn),
            "tier2_block_only": compute_confusion_metrics(t2_tp, t2_fp, t2_tn, t2_fn),
        }

    ambiguous_verdicts: dict[str, int] = {"ALLOW": 0, "FLAG": 0, "BLOCK": 0}
    for row in per_category_rows["E"]:
        v = str(row["verdict"])
        ambiguous_verdicts[v] = ambiguous_verdicts.get(v, 0) + 1

    return {
        "evidence_classes_present": ["C (Synthetic Adversarial)", "E (Ambiguous Non-Binary)"],
        "external_validation_status": "Outstanding (Evidence Class D: None — synthetic only)",
        "total_cases": len(cases),
        "binary_categories": binary_summary,
        "ambiguous_category_e": {
            "count": len(per_category_rows["E"]),
            "evidence_class": "E (Ambiguous / Undetermined)",
            "verdict_distribution": ambiguous_verdicts,
        },
        "results": {k: v for k, v in per_category_rows.items()},
    }

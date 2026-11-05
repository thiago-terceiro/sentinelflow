"""Empirical ML Evaluation Suite for SentinelPulse SMS Fraud & Spam Classifier.

Evaluates trained models on a strictly separated, deduplicated held-out test set (N = 400)
including hard negative benign transactional SMS (delivery/OTP/shortlinks) and
unseen smishing templates with zero train/test leakage, reporting dual-threshold
operational metrics (Tier 1 FLAG+BLOCK >= 0.40 vs Tier 2 BLOCK >= 0.75).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
from app.telecom.onnx_engine import HEURISTIC_RULES, compute_composite_score
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _hash_text(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


# 200 distinct held-out benign transactional & conversational messages
_BENIGN_SERVICES = [
    "Google", "Apple", "Microsoft", "Amazon", "Uber", "Lyft", "Discord", "Slack",
    "GitHub", "Twitter", "WhatsApp", "Telegram", "Steam", "Epic Games", "Coinbase",
    "Binance", "PayPal", "Venmo", "Okta", "Duo Security", "Stripe", "Auth0",
    "Intuit", "Dropbox", "Adobe", "Shopify", "Twilio", "Zoom", "Atlassian",
    "LinkedIn", "Reddit", "TikTok", "Instagram", "Snapchat", "Signal", "Sony PlayStation",
    "Nintendo", "Roblox", "Spotify", "Netflix"
]

_BENIGN_OTP_SAMPLES = [
    f"{svc} security code: {200000 + idx * 7919 % 700000:06d}. Do not share this code with anyone."
    for idx, svc in enumerate(_BENIGN_SERVICES)
]

_BENIGN_CARRIER_SHIPPING = [
    ("USPS", "https://tools.usps.com/track"),
    ("FedEx", "https://fedex.com/tracking"),
    ("UPS", "https://ups.com/track"),
    ("DHL Express", "https://dhl.com/track"),
    ("Amazon Logistics", "https://amazon.com/orders"),
    ("OnTrac", "https://ontrac.com/tracking"),
    ("LaserShip", "https://lasership.com/track"),
]
_BENIGN_SHIPPING_SAMPLES: list[str] = []
for i in range(35):
    carrier, url = _BENIGN_CARRIER_SHIPPING[i % len(_BENIGN_CARRIER_SHIPPING)]
    pkg_id = f"PKG{940000 + i * 137}"
    templates = [
        f"{carrier}: Package {pkg_id} is scheduled for delivery today by 4:00 PM. Details: {url}",
        f"{carrier} update: Shipment {pkg_id} has arrived at the local sort facility. Track at {url}",
        f"{carrier} Delivery: Your package {pkg_id} was delivered near front porch. Photo: {url}",
        f"{carrier}: Out for delivery! Driver Marcus is arriving shortly with package {pkg_id}. {url}",
        f"{carrier} Alert: Shipment {pkg_id} departed distribution center on schedule. Status: {url}"
    ]
    _BENIGN_SHIPPING_SAMPLES.append(templates[i % len(templates)])

_BENIGN_BANKS = [
    "Chase", "Wells Fargo", "Bank of America", "Citibank", "Capital One",
    "American Express", "Discover", "Fidelity", "Charles Schwab", "Ally Bank",
    "PNC Bank", "TD Bank", "US Bank", "Navy Federal", "Barclays"
]
_BENIGN_BANKING_SAMPLES: list[str] = []
for i in range(35):
    bank = _BENIGN_BANKS[i % len(_BENIGN_BANKS)]
    last4 = f"{1000 + (i * 239) % 8999}"
    amt = 15 + i * 7
    templates = [
        f"{bank} Alert: Direct deposit of ${1200 + i * 45}.00 posted to account ending in {last4}.",
        f"{bank} Fraud Alert: Did you use card ending in {last4} for ${amt}.50 at Shell? Reply YES or NO.",
        f"{bank}: Scheduled payment of ${85 + i * 5}.00 to State Farm was processed successfully.",
        f"{bank} Notice: Your monthly statement for checking account *{last4} is available online.",
        f"{bank}: Card {last4} authorized for ${amt}.99 at Trader Joe's. Available balance: ${3400 - i * 30}."
    ]
    _BENIGN_BANKING_SAMPLES.append(templates[i % len(templates)])

_BENIGN_AIRLINES = [
    ("Delta Air Lines", "DL"),
    ("United Airlines", "UA"),
    ("American Airlines", "AA"),
    ("Southwest Airlines", "WN"),
    ("Alaska Airlines", "AS"),
]
_BENIGN_TRAVEL_SAMPLES: list[str] = []
for i in range(25):
    airline, code = _BENIGN_AIRLINES[i % len(_BENIGN_AIRLINES)]
    flight_num = f"{code}{100 + i * 19}"
    gate = f"Gate {chr(65 + (i % 4))}{1 + (i % 20)}"
    templates = [
        f"{airline}: Flight {flight_num} is on time. Departs from {gate} at {2 + (i % 8)}:30 PM.",
        f"{airline} Boarding: Now boarding Group {1 + (i % 4)} for flight {flight_num} to Chicago.",
        f"{airline} Gate Change: Flight {flight_num} will now depart from {gate}.",
        f"Lyft ride #{i + 1}: Driver Ahmed in a Silver Camry (Plate: {7 + i}XYZ9) is arriving now.",
        f"Airbnb reservation #{i + 1}: Host Sarah sent check-in instructions for your upcoming stay."
    ]
    _BENIGN_TRAVEL_SAMPLES.append(templates[i % len(templates)])

_BENIGN_HEALTHCARE_SAMPLES: list[str] = []
_health_providers = ["Kaiser Permanente", "Quest Diagnostics", "Labcorp", "CVS Pharmacy", "Walgreens"]
for i in range(25):
    prov = _health_providers[i % len(_health_providers)]
    rx_num = 928400 + i * 31
    templates = [
        f"{prov}: Your prescription refill RX#{rx_num} is ready for pickup at Main St branch.",
        f"{prov} Reminder: Dental hygiene cleaning appointment scheduled for Tuesday #{i + 1} at 9 AM.",
        f"{prov}: Routine lab test results #{i + 1} have been posted to your secure MyChart portal.",
        f"{prov} Appointment: Annual wellness exam #{i + 1} confirmed with Dr. Smith for Thursday.",
        f"{prov}: Vision checkup reminder for appointment #{i + 1} tomorrow at 2:30 PM. Reply 1 to confirm."
    ]
    _BENIGN_HEALTHCARE_SAMPLES.append(templates[i % len(templates)])

_BENIGN_RETAIL_SAMPLES: list[str] = []
_retailers = ["Home Depot", "Target", "Walmart", "Best Buy", "Apple Store", "Costco", "Starbucks"]
for i in range(25):
    ret = _retailers[i % len(_retailers)]
    ord_id = 49200 + i * 47
    templates = [
        f"{ret}: Curbside pickup order #{ord_id} is ready in designated pickup spot #{1 + (i % 8)}.",
        f"{ret} Receipt: Transaction #{ord_id} paid ${15 + i * 3}.40. E-receipt sent to registered email.",
        f"{ret} Store Pickup: Your online order #{ord_id} is ready at the customer service desk.",
        f"DoorDash order #{ord_id}: Your dinner from Chipotle is on the way with dasher Carlos.",
        f"OpenTable #{ord_id}: Reservation at Bistro Verde for 2 guests confirmed tonight at 7:30 PM."
    ]
    _BENIGN_RETAIL_SAMPLES.append(templates[i % len(templates)])

_BENIGN_P2P_SAMPLES: list[str] = [
    "Could you send me the recipe for the pasta salad you made last week?",
    "The plumber just finished fixing the kitchen sink leak.",
    "Hi Mom, just landed safely at JFK. Will call once I get to the hotel.",
    "Can you pick up milk and eggs on your way home please?",
    "Are you taking the train or driving into the city on Wednesday?",
    "Happy Birthday! Hope you have a wonderful day celebrating with family!",
    "I left my umbrella by the front door, could you bring it to work?",
    "Thanks for hosting dinner yesterday, we had such a great time together!",
    "Heading over to the library now, text me when you get there.",
    "Let me know if you want to carpool to soccer practice tomorrow morning.",
    "Did you get the keys from the front desk concierge?",
    "Sounds great, looking forward to catching up this weekend over brunch!",
    "Just parked outside your building, come down whenever you are ready.",
    "Let's grab a coffee before the keynote session begins tomorrow.",
    "Don't forget we have the neighborhood block party on Saturday afternoon."
]

EVAL_HELD_OUT_BENIGN: list[str] = (
    _BENIGN_OTP_SAMPLES +          # 40
    _BENIGN_SHIPPING_SAMPLES +     # 35
    _BENIGN_BANKING_SAMPLES +      # 35
    _BENIGN_TRAVEL_SAMPLES +       # 25
    _BENIGN_HEALTHCARE_SAMPLES +   # 25
    _BENIGN_RETAIL_SAMPLES +       # 25
    _BENIGN_P2P_SAMPLES            # 15
)

# 200 distinct held-out smishing messages
_SMISH_CARRIERS = ["USPS", "DHL", "FedEx", "UPS"]
_SMISH_DOMAINS = [
    "redelivery-parcel.top", "customs-clearance.cc", "duty-payment.xyz",
    "postal-tracking.info", "package-depot.club", "dispatch-verify.biz"
]
_SMISH_DELIVERY: list[str] = []
for i in range(40):
    car = _SMISH_CARRIERS[i % len(_SMISH_CARRIERS)]
    dom = _SMISH_DOMAINS[i % len(_SMISH_DOMAINS)]
    delivery_pkg_id = str(948200 + i * 19)
    templates = [
        f"{car} Alert: Parcel #{delivery_pkg_id} held due to unpaid customs fee of $1.{90 + (i % 9)}. Pay: http://{car.lower()}-{dom}",
        f"{car} Notification: Incomplete street address for shipment #{delivery_pkg_id}. Update info: http://{car.lower()}-{dom}",
        f"{car} Notice: Final delivery attempt failed for item #{delivery_pkg_id}. Reschedule at http://post-{dom}",
        f"{car} Express: Duty charges pending for parcel #{delivery_pkg_id}. Release package: http://clearance-{dom}",
    ]
    _SMISH_DELIVERY.append(templates[i % len(templates)])

_SMISH_BANKS = ["Chase", "Wells Fargo", "Bank of America", "Citibank", "Capital One", "PNC Bank", "TD Bank", "SunTrust"]
_SMISH_BANK_DOMAINS = ["security-verify.net", "unlock-auth.com", "fraud-dispute.info", "card-protect.xyz", "portal-login.org"]
_SMISH_BANKING: list[str] = []
for i in range(45):
    bank = _SMISH_BANKS[i % len(_SMISH_BANKS)]
    dom = _SMISH_BANK_DOMAINS[i % len(_SMISH_BANK_DOMAINS)]
    tx_id = 2400 + i * 50
    templates = [
        f"URGENT: {bank} detected unauthorized wire transfer of ${tx_id}. If not you, cancel: http://{bank.lower().replace(' ', '')}-{dom}",
        f"{bank} Alert: Your debit card ending in {1000 + i} is blocked after suspicious activity. Restore: http://{bank.lower().replace(' ', '')}-{dom}",
        f"{bank} Security: Did you send ${500 + i * 20} via Zelle to John? If NO, secure account: http://zelle-verify-{dom}",
        f"{bank} Notice: New login from unrecognized device #{i + 1} in Russia. Verify identity: http://login-auth-{dom}",
        f"{bank} Alert: Account access #{i + 1} suspended due to missing KYC documents. Update now: http://kyc-{dom}"
    ]
    _SMISH_BANKING.append(templates[i % len(templates)])

_SMISH_LEGAL_EXTORTION: list[str] = []
for i in range(30):
    case_num = 49200 + i * 23
    templates = [
        f"IRS FINAL NOTICE: Delinquent federal tax balance detected for SSN case #{case_num}. Arrest warrant pending. Call 1-800-555-01{10 + i:02d}.",
        f"State Court Notice: Summons issued for failure to appear for jury duty citation #{case_num}. Pay fine: http://court-settle.info/{case_num}",
        f"SunPass Toll Violation: Overdue toll invoice #{case_num} of ${12 + (i % 8)}.{40 + i} for vehicle. Settle: http://sunpass-billing.top/{case_num}",
        f"EZPass Alert: Unpaid toll road citation #{case_num}. Settle immediately to avoid driver license suspension: http://ezpass-toll-resolve.biz/{case_num}",
        f"URGENT Legal Warning: Process server dispatched to deliver civil lawsuit papers for case #{case_num}. Call 888-555-01{20 + i:02d}."
    ]
    _SMISH_LEGAL_EXTORTION.append(templates[i % len(templates)])

_SMISH_CRYPTO_GIVEAWAY: list[str] = []
_crypto_platforms = ["Coinbase", "Trust Wallet", "Metamask", "Binance", "Kraken"]
for i in range(30):
    plat = _crypto_platforms[i % len(_crypto_platforms)]
    crypto_amt = 0.5 + (i % 5) * 0.2
    templates = [
        f"{plat} Security: Withdrawal of {crypto_amt:.2f} ETH initiated from IP #{i + 1}. If unauthorized, freeze: http://{plat.lower()}-freeze-{i:02d}.me",
        f"{plat} Notice: Your secret recovery seed phrase backup #{i + 1} has expired. Re-authenticate: http://{plat.lower()}-auth-{i:02d}.io",
        f"VIP Crypto Signals: Guaranteed {200 + i * 10}% return daily! Join private Telegram group: https://t.me/crypto_vip_{i:02d}",
        f"Cash App Giveaway: You have been chosen for the 2026 cash drop! Claim ${750 + i * 10}: http://cashapp-free-{i:02d}.online",
        f"Walmart Rewards: Your mobile number won 2nd place in customer raffle #{i + 1}! Claim $500 gift card: http://walmart-prizes-{i:02d}.xyz"
    ]
    _SMISH_CRYPTO_GIVEAWAY.append(templates[i % len(templates)])

_SMISH_JOB_TECHSUPPORT: list[str] = []
_tech_brands = ["Geek Squad", "McAfee", "Norton 360", "Meta Security", "Netflix", "Amazon Security"]
for i in range(30):
    brand = _tech_brands[i % len(_tech_brands)]
    inv = 92840 + i * 17
    templates = [
        f"{brand} Auto-Renewal: Your tech care plan #{inv} was charged ${399 + i * 10}. Call 1-888-555-01{30 + i:02d} for cancellation.",
        f"{brand}: Subscription invoice #{inv} processed for ${449}. To dispute this charge call 800-555-01{40 + i:02d}.",
        f"Work From Home: Earn ${350 + i * 10}/day reviewing online videos. Contact hiring manager #{i + 1} on Telegram: @hiring_manager_{i:02d}",
        f"Meta Security: Instagram account #{i:02d} flagged for copyright infringement. Submit appeal #{inv}: http://meta-appeal-{i:02d}.cc",
        f"Netflix Support: Account #{inv} closed due to billing decline. Update payment details: http://netflix-renew-account-{i:02d}.club"
    ]
    _SMISH_JOB_TECHSUPPORT.append(templates[i % len(templates)])

_SMISH_TELCO_SUBS: list[str] = []
_telcos = ["AT&T", "Verizon", "T-Mobile"]
for i in range(25):
    telco = _telcos[i % len(_telcos)]
    line_num = 1000 + i * 37
    templates = [
        f"{telco} Alert: eSIM transfer requested for line ending in {line_num}. If you did not request this, cancel: http://{telco.lower()}-cancel-{i:02d}.info",
        f"{telco} Notice: SIM card #{line_num} deactivation scheduled in 24 hours. Update KYC documentation: http://{telco.lower()}-kyc-{i:02d}.top",
        f"WhatsApp Gold: Upgrade account #{line_num} to Gold VIP with exclusive caller ID. Download: http://whatsapp-gold-{i:02d}.me",
        f"Gov Economic Relief: You qualify for ${1400 + i * 50} federal stimulus grant #{i + 1}. Complete form: http://stimulus-claim-{i:02d}.org",
        f"{telco} Rewards: Claim your $250 customer loyalty prepaid Mastercard voucher #{line_num}: http://rewards-voucher-{i:02d}.xyz"
    ]
    _SMISH_TELCO_SUBS.append(templates[i % len(templates)])

EVAL_HELD_OUT_SMISHING: list[str] = (
    _SMISH_DELIVERY +           # 40
    _SMISH_BANKING +            # 45
    _SMISH_LEGAL_EXTORTION +    # 30
    _SMISH_CRYPTO_GIVEAWAY +    # 30
    _SMISH_JOB_TECHSUPPORT +    # 30
    _SMISH_TELCO_SUBS           # 25
)


def get_held_out_evaluation_set() -> tuple[list[str], list[int]]:
    """Returns the deduplicated held-out test texts (N=400) and ground truth labels (0=Legit, 1=Fraud)."""
    texts = list(EVAL_HELD_OUT_BENIGN) + list(EVAL_HELD_OUT_SMISHING)
    labels = [0] * len(EVAL_HELD_OUT_BENIGN) + [1] * len(EVAL_HELD_OUT_SMISHING)

    # Verify deduplication and balance
    if len(texts) != 400:
        raise ValueError(f"Expected 400 held-out samples, found {len(texts)}")
    hashes = [_hash_text(t) for t in texts]
    if len(hashes) != len(set(hashes)):
        raise ValueError("Held-out evaluation set contains duplicate samples!")
    return texts, labels


def compute_heuristic_score(text: str) -> float:
    """Evaluates compiled regex heuristics against message text."""
    score = 0.0
    for _, pattern, weight in HEURISTIC_RULES:
        if pattern.search(text):
            score = max(score, weight)
    return score


def compute_evaluation_metrics(
    y_true: list[int] | np.ndarray,
    y_prob: list[float] | np.ndarray,
    texts: list[str],
    threshold: float = 0.50,
) -> dict[str, Any]:
    """Computes exact empirical evaluation metrics across both operational tiers and raw ML."""
    y_true_arr = np.asarray(y_true, dtype=int)
    y_prob_arr = np.asarray(y_prob, dtype=float)

    # Raw model predictions at standard 0.50 decision boundary
    y_pred = (y_prob_arr >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true_arr, y_pred, labels=[0, 1]).ravel()

    precision = float(precision_score(y_true_arr, y_pred, zero_division=0))
    recall = float(recall_score(y_true_arr, y_pred, zero_division=0))
    f1 = float(f1_score(y_true_arr, y_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_true_arr, y_prob_arr))
    pr_auc = float(average_precision_score(y_true_arr, y_prob_arr))
    brier = float(brier_score_loss(y_true_arr, y_prob_arr))

    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

    # Operational composite scores combining calibrated ML + heuristics
    composite_scores: list[float] = []
    for text, p in zip(texts, y_prob_arr, strict=False):
        h = compute_heuristic_score(text)
        s_comp = compute_composite_score(heuristic_score=h, onnx_probability=float(p), velocity_score=0.0)
        composite_scores.append(s_comp)
    comp_arr = np.asarray(composite_scores, dtype=float)

    # Tier 1: FLAG + BLOCK (S_composite >= 0.40) -> Async Human / Agent Escalation Queue
    pred_tier1 = (comp_arr >= 0.40).astype(int)
    tn1, fp1, fn1, tp1 = confusion_matrix(y_true_arr, pred_tier1, labels=[0, 1]).ravel()
    prec1 = float(precision_score(y_true_arr, pred_tier1, zero_division=0))
    rec1 = float(recall_score(y_true_arr, pred_tier1, zero_division=0))
    f1_tier1 = float(f1_score(y_true_arr, pred_tier1, zero_division=0))
    fpr1 = float(fp1 / (fp1 + tn1)) if (fp1 + tn1) > 0 else 0.0

    # Tier 2: BLOCK (S_composite >= 0.75) -> Immediate Carrier Wire Drop
    pred_tier2 = (comp_arr >= 0.75).astype(int)
    tn2, fp2, fn2, tp2 = confusion_matrix(y_true_arr, pred_tier2, labels=[0, 1]).ravel()
    prec2 = float(precision_score(y_true_arr, pred_tier2, zero_division=0))
    rec2 = float(recall_score(y_true_arr, pred_tier2, zero_division=0))
    f1_tier2 = float(f1_score(y_true_arr, pred_tier2, zero_division=0))
    fpr2 = float(fp2 / (fp2 + tn2)) if (fp2 + tn2) > 0 else 0.0

    return {
        "sample_count": int(len(y_true_arr)),
        "benign_count": int(np.sum(y_true_arr == 0)),
        "fraud_count": int(np.sum(y_true_arr == 1)),
        "decision_threshold": threshold,
        "confusion_matrix": {
            "tp": int(tp),
            "fp": int(fp),
            "tn": int(tn),
            "fn": int(fn),
        },
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "tier1_escalation": {
            "threshold": 0.40,
            "description": "FLAG + BLOCK (Async Human / Agent Review Queue)",
            "confusion_matrix": {"tp": int(tp1), "fp": int(fp1), "tn": int(tn1), "fn": int(fn1)},
            "precision": round(prec1, 4),
            "recall": round(rec1, 4),
            "f1_score": round(f1_tier1, 4),
            "false_positive_rate": round(fpr1, 4),
        },
        "tier2_block": {
            "threshold": 0.75,
            "description": "BLOCK (Immediate Carrier Wire Drop)",
            "confusion_matrix": {"tp": int(tp2), "fp": int(fp2), "tn": int(tn2), "fn": int(fn2)},
            "precision": round(prec2, 4),
            "recall": round(rec2, 4),
            "f1_score": round(f1_tier2, 4),
            "false_positive_rate": round(fpr2, 4),
        },
    }


def evaluate_onnx_model(
    model_path: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluates the compiled ONNX model on the N = 400 held-out adversarial test set."""
    import onnxruntime as ort

    if model_path is None:
        model_path = Path(__file__).resolve().parent / "models" / "sms_fraud_model.onnx"
    else:
        model_path = Path(model_path)

    if not model_path.exists():
        raise FileNotFoundError(f"ONNX model file not found at {model_path}")

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    texts, labels = get_held_out_evaluation_set()

    # Single vectorized session.run across all held-out texts
    input_tensor = np.array([[t] for t in texts], dtype=object)
    raw_outputs = session.run(None, {input_name: input_tensor})
    prob_maps = raw_outputs[1]
    y_prob = [float(pm.get(1, 0.0)) for pm in prob_maps]

    metrics = compute_evaluation_metrics(labels, y_prob, texts=texts)
    metrics["evaluator"] = "ONNXRuntime-CPU"
    metrics["model_artifact"] = str(model_path.name)
    metrics["model_artifact_size_bytes"] = model_path.stat().st_size
    metrics["model_artifact_size_kb"] = round(model_path.stat().st_size / 1024, 2)

    return metrics


def export_ml_metrics(metrics: dict[str, Any], output_path: str | Path | None = None) -> Path:
    """Exports empirical evaluation metrics to JSON."""
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "ml_metrics.json"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Exported empirical ML metrics to %s", output_path)
    return output_path


def main() -> None:
    """CLI runner for empirical ML model evaluation."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("Executing SentinelPulse Empirical ML Evaluation Suite (N = 400)...")

    metrics = evaluate_onnx_model()
    export_ml_metrics(metrics)

    t1 = metrics["tier1_escalation"]
    t2 = metrics["tier2_block"]

    print("\n" + "=" * 68)
    print("SENTINELPULSE EMPIRICAL ML EVALUATION REPORT (N = 400)")
    print("=" * 68)
    print(f"Model Artifact:    {metrics['model_artifact']} ({metrics['model_artifact_size_kb']} KB)")
    print(f"Evaluator:         {metrics['evaluator']}")
    print(f"Held-Out Samples:  {metrics['sample_count']} (Benign: {metrics['benign_count']}, Fraud: {metrics['fraud_count']})")
    print(f"ROC-AUC:           {metrics['roc_auc']:.4f}")
    print(f"PR-AUC:            {metrics['pr_auc']:.4f}")
    print(f"Brier Score:       {metrics['brier_score']:.4f}")
    print("-" * 68)
    print("OPERATIONAL TIER 1: FLAG + BLOCK (S_composite >= 0.40 -> Escalation)")
    print(f"Confusion Matrix:  TP={t1['confusion_matrix']['tp']}  FP={t1['confusion_matrix']['fp']}  TN={t1['confusion_matrix']['tn']}  FN={t1['confusion_matrix']['fn']}")
    print(f"Recall:            {t1['recall']*100:.2f}% (Target >= 94.0%)")
    print(f"FPR (False Pos):   {t1['false_positive_rate']*100:.2f}% (Target <= 2.5%)")
    print(f"Precision:         {t1['precision']*100:.2f}%")
    print(f"F1-Score:          {t1['f1_score']:.4f}")
    print("-" * 68)
    print("OPERATIONAL TIER 2: BLOCK (S_composite >= 0.75 -> Wire Drop)")
    print(f"Confusion Matrix:  TP={t2['confusion_matrix']['tp']}  FP={t2['confusion_matrix']['fp']}  TN={t2['confusion_matrix']['tn']}  FN={t2['confusion_matrix']['fn']}")
    print(f"Precision:         {t2['precision']*100:.2f}% (Target >= 98.5%)")
    print(f"FPR (False Pos):   {t2['false_positive_rate']*100:.2f}% (Target <= 0.5%)")
    print(f"Recall:            {t2['recall']*100:.2f}%")
    print(f"F1-Score:          {t2['f1_score']:.4f}")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()

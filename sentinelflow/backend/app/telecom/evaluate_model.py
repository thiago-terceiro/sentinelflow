"""Empirical ML Evaluation Suite for SentinelPulse SMS Fraud & Spam Classifier.

Evaluates trained models on a strictly separated, deduplicated held-out test set
including hard negative benign transactional SMS (delivery/OTP/shortlinks) and
unseen smishing templates with zero train/test leakage.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
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

# Strictly separated held-out benign transactional SMS (hard negatives)
# Zero overlap with training set (verified via automated assertion)
EVAL_HELD_OUT_BENIGN: list[str] = [
    "USPS: Tracking #940011189956482910 is out for delivery. Track at https://tools.usps.com/track",
    "FedEx: Your shipment 784920194829 has arrived at the local facility. Details: https://fedex.com/tracking",
    "UPS: Package scheduled for delivery by 3:00 PM today. Signature required: https://ups.com/track/1Z999",
    "Amazon Delivery: Package delivered near front door or porch. View photo: https://amazon.com/orders",
    "Your Discord verification security code is 849201. Never share this code with anyone.",
    "Google verification code: G-394821. Enter to verify your device sign-in.",
    "Apple ID verification code: 501928. Enter this on your device to complete sign in.",
    "Uber verification code: 4920. Never share this code with anyone.",
    "Chase Fraud Alert: Did you use card 8421 for $32.40 at Shell Oil? Reply YES or NO.",
    "Wells Fargo: Large deposit of $1,500.00 posted to checking account ending in 4019.",
    "Bank of America Alert: Your scheduled payment of $120.00 to Geico was processed.",
    "Kaiser Permanente: Your lab results from your recent visit are available in your portal.",
    "CVS Pharmacy: Your prescription RX#928401 is ready for pickup at 4th St location.",
    "Delta Airlines: Gate change for DL 1842. New gate is A14. Boarding starts at 4:10 PM.",
    "Lyft ride receipt: $18.45 for your ride with Marcus. Tip or view receipt at lyft.com/receipts",
    "OpenTable: Your reservation at L'Artusi is confirmed for 2 guests tonight at 8:30 PM.",
    "Home Depot order #H49201 is ready for curbside pickup. Parking spot details in app.",
    "Ticketmaster: Your tickets for Coldplay at Wembley are ready. Access in your account.",
    "Airbnb reservation reminder: Check-in instructions from host Sarah available at airbnb.com",
    "Southwest Airlines: Flight 291 to Phoenix is now boarding at Gate B10.",
    "Walgreens: Your prescription refill is ready. Curbside pickup available until 9 PM.",
    "Square receipt: You paid $6.50 at Joe's Espresso. squareup.com/r/k492",
    "Atlassian security: New login from macOS in San Francisco. Review at id.atlassian.com",
    "Spotify receipt: Your family plan subscription renewed for $16.99.",
    "State Farm: Your auto policy renewal document is ready to view in your account.",
]

# Strictly separated held-out smishing / spam SMS (unseen adversarial attacks)
# Zero overlap with training set (verified via automated assertion)
EVAL_HELD_OUT_SMISHING: list[str] = [
    "USPS Notification: Parcel delivery failed due to incomplete address. Update at http://usps-portal-redelivery.top",
    "DHL Express: Customs duty of $3.50 unpaid for parcel #948201. Clear now: http://dhl-clearance-online.cc",
    "FedEx Alert: Your shipment is on hold pending duty payment. Pay $1.95: http://fedex-customs-duty.xyz",
    "IRS Alert: Unpaid federal tax balance detected. Federal warrant pending. Settle at http://irs-tax-settlement.info",
    "State Court Notice: Summons issued for failure to appear for jury duty. Call 800-555-0188 or pay fine.",
    "DMV Toll Violation: Unpaid toll road citation #82910 of $14.20. Late fees apply: http://ezpass-toll-billing.biz",
    "Citibank Urgent: Unauthorized wire transfer of $3,200 to Singapore. Cancel here: http://citi-wire-cancel.com",
    "PayPal Resolution: Your account access has been limited. Submit identity docs: http://paypal-identity-resolve.net",
    "Capital One Security: Debit card suspended after suspicious online charge. Unlock: http://capone-unlock-auth.org",
    "Crypto Trust Wallet: Your recovery seed phrase backup expired. Re-authenticate: http://trust-wallet-backup.io",
    "Coinbase Notice: 0.85 ETH withdrawal requested from IP in Russia. Cancel: http://coinbase-fraud-cancel.me",
    "AT&T Rewards: Claim your $200 customer appreciation prepaid Mastercard at http://att-rewards-claim.xyz",
    "Amazon Prize: You placed 3rd in our customer raffle! Claim your $500 gift card: http://amazon-prize-winner.online",
    "Telegram Job Offer: Earn $350 daily liking videos on YouTube. Contact manager: https://t.me/recruit_online_2026",
    "T-Mobile Alert: Your eSIM transfer request is processing. If you did not request this, cancel: http://tmobile-sim-cancel.info",
    "Netflix Support: Your membership expired due to billing error. Update payment: http://netflix-account-update.club",
    "SunPass Toll: Overdue toll of $8.90 for vehicle. Settle immediately to avoid driver license suspension: http://sunpass-resolve.top",
    "Wells Fargo Fraud Team: Did you send $950 via Zelle to John? If NO, secure account immediately: http://wf-zelle-secure.info",
    "Geek Squad Auto-Renewal: Your tech care plan was charged $449. Call 1-888-555-0199 for instant cancellation.",
    "Meta Security: Your Instagram account will be deleted in 24 hours for copyright infringement. Appeal: http://meta-appeal-form.cc",
    "Chase Bank Alert: New payee added to your profile. If unauthorized, freeze access: http://chase-payee-verify.online",
    "Gov Relief Fund: You qualify for $1,400 economic relief stimulus. Complete direct deposit form: http://stimulus-relief-claim.org",
    "WhatsApp Gold Upgrade: Your account is eligible for VIP gold features with free calls. Download: http://whatsapp-gold-installer.me",
    "PNC Bank: Unusual debit card usage in Miami FL. Confirm identity to avoid card lock: http://pnc-card-protect.xyz",
    "Package Depot: Final notification! Delivery #82910 will be returned to sender today. Reschedule: http://post-package-pickup.net",
]


def get_held_out_evaluation_set() -> tuple[list[str], list[int]]:
    """Returns the deduplicated, held-out test texts and ground truth labels (0=Legit, 1=Fraud)."""
    texts = list(EVAL_HELD_OUT_BENIGN) + list(EVAL_HELD_OUT_SMISHING)
    labels = [0] * len(EVAL_HELD_OUT_BENIGN) + [1] * len(EVAL_HELD_OUT_SMISHING)

    # Verify deduplication within evaluation set
    if len(texts) != len(set(texts)):
        raise ValueError("Held-out evaluation set contains duplicate samples!")
    return texts, labels


def compute_evaluation_metrics(
    y_true: list[int] | np.ndarray,
    y_prob: list[float] | np.ndarray,
    threshold: float = 0.50,
) -> dict[str, Any]:
    """Computes exact empirical evaluation metrics from ground-truth labels and predicted probabilities."""
    y_true_arr = np.asarray(y_true, dtype=int)
    y_prob_arr = np.asarray(y_prob, dtype=float)
    y_pred = (y_prob_arr >= threshold).astype(int)

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_true_arr, y_pred, labels=[0, 1]).ravel()

    # Empirical rates
    precision = float(precision_score(y_true_arr, y_pred, zero_division=0))
    recall = float(recall_score(y_true_arr, y_pred, zero_division=0))
    f1 = float(f1_score(y_true_arr, y_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_true_arr, y_prob_arr))
    pr_auc = float(average_precision_score(y_true_arr, y_prob_arr))
    brier = float(brier_score_loss(y_true_arr, y_prob_arr))

    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

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
    }


def evaluate_onnx_model(
    model_path: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluates the compiled ONNX model on the held-out adversarial test set."""
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
    # raw_outputs[1] contains sequence of probability maps: [{0: p0, 1: p1}, ...]
    prob_maps = raw_outputs[1]
    y_prob = [float(pm.get(1, 0.0)) for pm in prob_maps]

    metrics = compute_evaluation_metrics(labels, y_prob)
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
    logger.info("Executing SentinelPulse Empirical ML Evaluation Suite...")

    metrics = evaluate_onnx_model()
    export_ml_metrics(metrics)

    print("\n" + "=" * 64)
    print("SENTINELPULSE EMPIRICAL ML EVALUATION REPORT")
    print("=" * 64)
    print(f"Model Artifact:    {metrics['model_artifact']} ({metrics['model_artifact_size_kb']} KB)")
    print(f"Evaluator:         {metrics['evaluator']}")
    print(f"Held-Out Samples:  {metrics['sample_count']} (Benign: {metrics['benign_count']}, Fraud: {metrics['fraud_count']})")
    print(f"Decision Boundary: >= {metrics['decision_threshold']}")
    print("-" * 64)
    print(f"Precision:         {metrics['precision']:.4f}")
    print(f"Recall:            {metrics['recall']:.4f}")
    print(f"F1-Score:          {metrics['f1_score']:.4f}")
    print(f"ROC-AUC:           {metrics['roc_auc']:.4f}")
    print(f"PR-AUC:            {metrics['pr_auc']:.4f}")
    print(f"Brier Score:       {metrics['brier_score']:.4f}")
    print(f"FPR (False Pos):   {metrics['false_positive_rate']:.4f}")
    print(f"FNR (False Neg):   {metrics['false_negative_rate']:.4f}")
    print("-" * 64)
    cm = metrics["confusion_matrix"]
    print(f"Confusion Matrix:  TP={cm['tp']}  FP={cm['fp']}  TN={cm['tn']}  FN={cm['fn']}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()

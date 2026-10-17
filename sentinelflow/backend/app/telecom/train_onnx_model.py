"""Training and ONNX export pipeline for SentinelPulse SMS Fraud & Spam Classifier.

Trains an NLP pipeline (TF-IDF + calibrated Logistic Regression) on representative
telecom SMS traffic, evaluates precision/recall/F1, and exports directly to an
optimized ONNX Runtime model with CPU execution provider.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from skl2onnx import to_onnx
from skl2onnx.common.data_types import StringTensorType
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Curated dataset of typical A2P / P2P legit messages (label=0) vs Smishing/Spam (label=1)
LEGITIMATE_MESSAGES: list[str] = [
    "Your verification code is 849201. It expires in 10 minutes. Do not share this code.",
    "Carrier security code: 4920. Valid for 5 minutes. carrier.com/verify",
    "Your Uber ride is arriving now. Driver: Ahmed in a Toyota Camry (Plate: 7XYZ89).",
    "Your card ending in 4102 was charged $14.50 at Trader Joe's. Available balance: $1,240.10.",
    "USPS tracking #940011189956: Your package is out for delivery and will arrive by 7:00 PM.",
    "Reminder: Your dental cleaning with Dr. Smith is tomorrow at 2:00 PM. Reply 1 to confirm, 2 to reschedule.",
    "Hey! Are you still free for dinner tonight around 7?",
    "Your appointment with Quest Diagnostics is scheduled for Thursday, Oct 24 at 9:30 AM.",
    "Your prescription is ready for pickup at Walgreens Pharmacy on Main Street.",
    "Google prompt: Tap YES on your phone to approve sign-in from Chrome on Windows.",
    "Amazon: Your order #112-4920491 has shipped and will arrive on Wednesday.",
    "Delta Flight DL492 is on time. Gate B12. Boarding begins at 3:15 PM.",
    "Wells Fargo Fraud Alert: Did you attempt $89.20 at Target? Reply YES or NO.",
    "Running about 10 minutes late, see you guys soon!",
    "Your monthly electric bill of $78.40 is scheduled for autopay on Nov 1. Thank you.",
    "Lyft code 382910. Reply STOP to opt out.",
    "Your DoorDash order from Chipotle is being prepared and will arrive in 25-35 minutes.",
    "Hey mom, just landed safely at JFK. Will text when I get to the hotel.",
    "Bank of America: A direct deposit of $3,250.00 was posted to your account ending in 8821.",
    "Your haircut appointment with Alex is confirmed for Saturday at 11:00 AM.",
    "Security notice: A new device logged into your Slack workspace. Review at my.slack.com",
    "Your test results are ready in the MyChart patient portal.",
    "Thanks for visiting Blue Bottle Coffee! Here is your digital receipt: squareup.com/r/xyz",
    "Great presentation today, let's sync up on Monday to discuss next steps.",
    "Your reservation at Osteria Morini is confirmed for 4 guests on Friday at 8:00 PM.",
    "FedEx Delivery: Package with tracking 78291038472 was delivered to your front porch.",
    "Hi Sarah, can you review the pull request when you get a chance? Thanks!",
    "Your two-factor authentication token is 501928 for login to GitHub.",
    "Your gym membership renewal receipt for $49.00 has been processed.",
    "Can you pick up milk on your way home please?",
    "Your reservation at Hyatt Regency is confirmed. Check-in is at 3 PM.",
    "Your package has been placed in Amazon Locker 'Sparrow'. Use code 829104 to collect.",
    "Home Depot: Your store pickup order #W928103 is ready at the customer service desk.",
    "Hi David, thanks for following up. Let's schedule a 30-minute intro call next Tuesday.",
    "Microsoft account security code: 928371. If you didn't request this, ignore.",
    "Your order from Apple Store is confirmed. Order number: W938472910.",
    "Your weekly screen time report is now available in settings.",
    "Good morning team, the 9:30 AM standup will be pushed by 15 minutes today.",
    "Southwest Airlines: Boarding position A24 for flight WN1849 to Denver.",
    "Your library books are due in 3 days. Renew online at publiclibrary.org",
]

FRAUDULENT_MESSAGES: list[str] = [
    "URGENT: Chase Bank alert. Unusual activity detected. Account suspended. Restore immediately: http://bit.ly/chase-verify-now",
    "CONGRATULATIONS! Your phone number won a $1,000 Walmart gift card! Click here to claim: http://walmart-prizes2026.xyz/win",
    "USPS Alert: Package 928301 could not be delivered due to wrong address. Pay $1.99 redelivery fee now: http://tinyurl.com/usps-redelivery-fee",
    "Wells Fargo Security: We detected an unauthorized login from Russia. Verify your SSN to unlock your card: http://wellsfargo-secure-login.ru",
    "IRS FINAL NOTICE: You owe $4,200 in delinquent taxes. Arrest warrant issued. Call 1-800-555-0199 immediately to avoid arrest.",
    "Bank of America: Your online banking has been temporarily disabled. Visit http://bofa-verify-identity.com to reactivate.",
    "Exclusive Crypto VIP signal: Earn 300% return guaranteed within 24 hours! Join WhatsApp group: https://t.me/cryptogains999",
    "Netflix: Your subscription payment failed. Your account will be closed today unless updated: http://netflix-billing-renew.info",
    "Toll Services: You have an unpaid toll invoice of $12.50. Late fees apply after 24h. Pay at: http://sunpass-toll-billing.top",
    "PayPal Security: Unauthorized transaction of $699.99 to Apple Store. Not you? Dispute immediately at: http://paypal-dispute-resolve.com",
    "You have (1) pending package awaiting clearance. Confirm your identity and pay customs fee: http://dhl-express-clearance.net/track",
    "URGENT: Your Apple ID has been locked for security reasons. Verify your account details: http://appleid-support-auth.com",
    "Alert from Citibank: Suspicious wire transfer of $2,450 initiated. Stop transfer here: http://citi-security-stop.com",
    "Winner notification! You have been selected for the 2026 Cash App Giveaway. Receive $750 instantly: http://cashapp-free750.online",
    "Your SIM card will be deactivated in 24 hours due to unverified KYC. Update details now: http://telecom-kyc-verify.club",
    "Amazon Security: Did you purchase iPhone 16 Pro for $1,199? If NOT, call fraud team right away at 1-888-555-0144.",
    "Dear customer, your debit card is blocked. Click http://chase-unblock-card.biz to submit photo ID and unlock.",
    "FedEx: Delivery exception! Package held at facility due to unpaid duty. Pay $2.40: http://fedex-express-customs.cc",
    "Target Shopper: You were chosen to receive a $500 shopping voucher! Complete short survey: http://target-voucher-survey.site",
    "Your social security number has been compromised in a fraud investigation. Press 1 to speak with a federal agent.",
    "Attn: Your account with AT&T will be cancelled. Pay overdue balance of $45.10 here: http://att-billpay-portal.info",
    "URGENT: Venmo unauthorized charge of $450 to Steam Games. Cancel this payment: http://venmo-security-dispute.link",
    "You qualified for $50,000 pre-approved loan with 0% APR. No credit check required! Apply now: http://fast-cash-loans-today.us",
    "Crypto alert: 1.45 BTC has been deposited to your wallet. Confirm receipt and withdraw: http://binance-claim-crypto.cc",
    "Your package #91823 is held at depot. Final delivery attempt tomorrow. Verify address: http://postal-package-update.info",
    "Warning: Your iPhone backup was compromised. Visit http://icloud-warning-check.me to change password immediately.",
    "Santander Alert: Card blocked due to suspicious activity. Follow link to verify: http://santander-unblock-service.top",
    "Work from home opportunity! Earn $500/day rating products on your phone. Telegram: @jobrecruiter2026",
    "Geek Squad: Auto-renewal charge of $399.99 processed. To request refund within 24h call: 1-800-555-0182",
    "Exclusive invitation: You are eligible to claim free government relief grant of $2,500. Register: http://gov-grant-claim.org",
    "TD Bank: Suspicious login from IP 194.26.29.1. Secure your account now: http://tdbank-customer-protect.net",
    "Capital One alert: Debit card flagged for fraud at Best Buy. Confirm identity: http://capitalone-fraud-prevention.xyz",
    "Your WhatsApp account will expire tomorrow. Renew your service for $0.99 here: http://whatsapp-subscription-renew.com",
    "URGENT legal notice: Process server dispatched to your location. Call 855-555-0129 to settle dispute before court.",
    "Costco rewards: You have $150 in unredeemed cash back rewards expiring tonight! Redeem at: http://costco-cashback-points.site",
    "Alert: Coinbase security key reset requested. If you did not initiate this, freeze account: http://coinbase-freeze-auth.com",
    "US Postal Notice: Missing apartment number on parcel. Re-enter shipping address: http://usps-address-correct.com",
    "Final reminder: Your car warranty is about to lapse. Extend coverage before deadline: http://auto-warranty-renew.online",
    "Your mobile number won 2nd prize in the UK National Lottery! Send email to claim: claim@national-lottery-promo.co",
    "Citizens Bank: Transaction of $840 declined. Verify your phone number to re-enable card: http://citizens-verify.cc",
]


def build_augmented_dataset() -> tuple[list[str], list[int]]:
    """Generates an augmented, balanced dataset of telecom SMS samples."""
    texts: list[str] = []
    labels: list[int] = []

    # Add base legitimate messages
    for msg in LEGITIMATE_MESSAGES:
        texts.append(msg)
        labels.append(0)

    # Add base fraudulent messages
    for msg in FRAUDULENT_MESSAGES:
        texts.append(msg)
        labels.append(1)

    # Augment with variations (sender numbers, token variants, brand names)
    brands = [
        "Chase",
        "Wells Fargo",
        "Bank of America",
        "Citibank",
        "Capital One",
        "PayPal",
        "Venmo",
    ]
    scam_domains = [
        "verify-now.info",
        "secure-portal.xyz",
        "alert-check.cc",
        "id-verify.online",
        "login-help.top",
    ]

    for brand in brands:
        for domain in scam_domains:
            texts.append(
                f"URGENT: {brand} security alert! Unusual sign-in detected. Confirm identity: http://{brand.lower().replace(' ', '')}-{domain}"
            )
            labels.append(1)

    # Augment legit 2FA & transactional notifications
    service_names = [
        "Signal",
        "GitHub",
        "Stripe",
        "Auth0",
        "Okta",
        "Slack",
        "AWS",
        "Google",
        "Shopify",
        "Discord",
    ]
    for service in service_names:
        for code in [192840, 582910, 394821, 910283, 401928]:
            texts.append(
                f"{service} security code: {code}. It expires in 5 minutes. Never share this with anyone."
            )
            labels.append(0)

    return texts, labels


def train_and_export_model(
    output_dir: str = "app/telecom/models",
    model_name: str = "sms_fraud_model.onnx",
    metadata_name: str = "sms_fraud_metadata.json",
) -> dict[str, Any]:
    """Trains the NLP model, evaluates performance metrics, and exports to ONNX."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    onnx_file = output_path / model_name
    metadata_file = output_path / metadata_name

    logger.info("Generating augmented telecom dataset...")
    texts, labels = build_augmented_dataset()
    logger.info(
        "Total dataset size: %d samples (Legit: %d, Fraud: %d)",
        len(texts),
        labels.count(0),
        labels.count(1),
    )

    # Split into train / test sets (80 / 20) with stratification
    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.20,
        random_state=42,
        stratify=labels,
    )

    # NLP Pipeline: TF-IDF with sublinear tf scaling and 1-2 ngrams + Logistic Regression
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    max_features=2500,
                    min_df=1,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    C=1.5,
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    logger.info("Fitting TF-IDF + Logistic Regression pipeline...")
    pipeline.fit(x_train, y_train)

    # Evaluate on held-out test set
    y_pred = pipeline.predict(x_test)
    y_prob = pipeline.predict_proba(x_test)[:, 1]

    precision = float(precision_score(y_test, y_pred))
    recall = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_prob))
    report = classification_report(y_test, y_pred, output_dict=True)

    logger.info("Evaluation Results:")
    logger.info("  Precision: %.4f", precision)
    logger.info("  Recall:    %.4f", recall)
    logger.info("  F1 Score:  %.4f", f1)
    logger.info("  ROC-AUC:   %.4f", roc_auc)

    # Export to ONNX with string tensor input
    logger.info("Exporting pipeline to ONNX format (opset 14)...")
    initial_type = [("text", StringTensorType([None, 1]))]
    onnx_model = to_onnx(pipeline, initial_types=initial_type, target_opset=14)

    # Serialize ONNX model to disk
    with open(onnx_file, "wb") as f:
        f.write(onnx_model.SerializeToString())
    logger.info("Saved ONNX model to: %s", onnx_file)

    # Save metadata & evaluation baseline
    metadata = {
        "model_name": "SentinelPulse-SMS-Fraud-ONNX",
        "version": "1.0.0",
        "architecture": "TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True) -> LogisticRegression(C=1.5, class_weight=balanced)",
        "framework": "scikit-learn + skl2onnx + onnxruntime",
        "opset": 14,
        "input_signature": {"text": "StringTensor([None, 1])"},
        "output_signature": {
            "label": "Int64Tensor([None])",
            "probabilities": "Sequence[Map[Int64, Float]]",
        },
        "metrics": {
            "test_sample_count": len(y_test),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "detailed_report": report,
        },
        "operating_thresholds": {
            "allow_below": 0.40,
            "flag_threshold": 0.40,
            "block_threshold": 0.75,
        },
        "target_latency": {
            "p50_ms": 0.05,
            "p95_ms": 0.15,
            "p99_ms": 0.50,
        },
    }

    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved model metadata to: %s", metadata_file)

    return metadata


if __name__ == "__main__":
    train_and_export_model()

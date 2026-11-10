"""Training and ONNX export pipeline for SentinelPulse SMS Fraud & Spam Classifier.

Trains an NLP pipeline (TF-IDF + calibrated Logistic Regression) on representative
telecom SMS traffic, evaluates precision/recall/F1, and exports directly to an
optimized ONNX Runtime model with CPU execution provider.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import statistics
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from app.telecom.evaluate_model import (
    evaluate_onnx_model,
    get_canonical_artifact_paths,
    get_held_out_evaluation_set,
    publish_evaluation_artifacts_atomically,
)
from skl2onnx import to_onnx
from skl2onnx.common.data_types import StringTensorType
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Curated base seeds paired with explicit audited semantic template families (SF-008)
LEGIT_BASE_SAMPLES: list[tuple[str, str]] = [
    ("Your verification code is 849201. It expires in 10 minutes. Do not share this code.", "legit_2fa_code"),
    ("Carrier security code: 4920. Valid for 5 minutes. carrier.com/verify", "legit_auth_short_code"),
    ("Your Uber ride is arriving now. Driver: Ahmed in a Toyota Camry (Plate: 7XYZ89).", "legit_local_service_eta"),
    ("Your card ending in 4102 was charged $14.50 at Trader Joe's. Available balance: $1,240.10.", "legit_bank_card_transaction"),
    ("USPS tracking #940011189956: Your package is out for delivery and will arrive by 7:00 PM.", "legit_package_delivery_tracking"),
    ("Reminder: Your dental cleaning with Dr. Smith is tomorrow at 2:00 PM. Reply 1 to confirm, 2 to reschedule.", "legit_appointment_reminder"),
    ("Hey! Are you still free for dinner tonight around 7?", "legit_casual_social_chat"),
    ("Your appointment with Quest Diagnostics is scheduled for Thursday, Oct 24 at 9:30 AM.", "legit_appointment_reminder"),
    ("Your prescription is ready for pickup at Walgreens Pharmacy on Main Street.", "legit_health_pharmacy"),
    ("Google prompt: Tap YES on your phone to approve sign-in from Chrome on Windows.", "legit_2fa_login_approve"),
    ("Amazon: Your order #112-4920491 has shipped and will arrive on Wednesday.", "legit_package_delivery_tracking"),
    ("Delta Flight DL492 is on time. Gate B12. Boarding begins at 3:15 PM.", "legit_travel_gate_info"),
    ("Wells Fargo Fraud Alert: Did you attempt $89.20 at Target? Reply YES or NO.", "legit_bank_fraud_alert_yesno"),
    ("Running about 10 minutes late, see you guys soon!", "legit_casual_social_chat"),
    ("Your monthly electric bill of $78.40 is scheduled for autopay on Nov 1. Thank you.", "legit_bank_autopay"),
    ("Lyft code 382910. Reply STOP to opt out.", "legit_auth_short_code"),
    ("Your DoorDash order from Chipotle is being prepared and will arrive in 25-35 minutes.", "legit_local_service_eta"),
    ("Hey mom, just landed safely at JFK. Will text when I get to the hotel.", "legit_casual_p2p_greetings"),
    ("Bank of America: A direct deposit of $3,250.00 was posted to your account ending in 8821.", "legit_bank_direct_deposit"),
    ("Your haircut appointment with Alex is confirmed for Saturday at 11:00 AM.", "legit_appointment_reminder"),
    ("Security notice: A new device logged into your Slack workspace. Review at my.slack.com", "legit_2fa_login_alert"),
    ("Your test results are ready in the MyChart patient portal.", "legit_health_mychart"),
    ("Thanks for visiting Blue Bottle Coffee! Here is your digital receipt: squareup.com/r/xyz", "legit_retail_receipt"),
    ("Great presentation today, let's sync up on Monday to discuss next steps.", "legit_workplace_sync"),
    ("Your reservation at Osteria Morini is confirmed for 4 guests on Friday at 8:00 PM.", "legit_hospitality_reservation"),
    ("FedEx Delivery: Package with tracking 78291038472 was delivered to your front porch.", "legit_package_delivery_tracking"),
    ("Hi Sarah, can you review the pull request when you get a chance? Thanks!", "legit_workplace_sync"),
    ("Your two-factor authentication token is 501928 for login to GitHub.", "legit_2fa_code"),
    ("Your gym membership renewal receipt for $49.00 has been processed.", "legit_bank_card_transaction"),
    ("Can you pick up milk on your way home please?", "legit_casual_errands"),
    ("Your reservation at Hyatt Regency is confirmed. Check-in is at 3 PM.", "legit_hospitality_reservation"),
    ("Your package has been placed in Amazon Locker 'Sparrow'. Use code 829104 to collect.", "legit_package_delivery_tracking"),
    ("Home Depot: Your store pickup order #W928103 is ready at the customer service desk.", "legit_retail_curbside"),
    ("Hi David, thanks for following up. Let's schedule a 30-minute intro call next Tuesday.", "legit_workplace_sync"),
    ("Microsoft account security code: 928371. If you didn't request this, ignore.", "legit_2fa_code"),
    ("Your order from Apple Store is confirmed. Order number: W938472910.", "legit_retail_receipt"),
    ("Your weekly screen time report is now available in settings.", "legit_personal_account_digest"),
    ("Good morning team, the 9:30 AM standup will be pushed by 15 minutes today.", "legit_workplace_sync"),
    ("Southwest Airlines: Boarding position A24 for flight WN1849 to Denver.", "legit_travel_gate_info"),
    ("Your library books are due in 3 days. Renew online at publiclibrary.org", "legit_personal_account_digest"),
]

FRAUD_BASE_SAMPLES: list[tuple[str, str]] = [
    ("URGENT: Chase Bank alert. Unusual activity detected. Account suspended. Restore immediately: http://bit.ly/chase-verify-now", "fraud_account_suspension_lure"),
    ("CONGRATULATIONS! Your phone number won a $1,000 Walmart gift card! Click here to claim: http://walmart-prizes2026.xyz/win", "fraud_prize_giveaway_lure"),
    ("USPS Alert: Package 928301 could not be delivered due to wrong address. Pay $1.99 redelivery fee now: http://tinyurl.com/usps-redelivery-fee", "fraud_postal_customs_fee"),
    ("Wells Fargo Security: We detected an unauthorized login from Russia. Verify your SSN to unlock your card: http://wellsfargo-secure-login.ru", "fraud_suspicious_ip_login_lure"),
    ("IRS FINAL NOTICE: You owe $4,200 in delinquent taxes. Arrest warrant issued. Call 1-800-555-0199 immediately to avoid arrest.", "fraud_legal_tax_extortion"),
    ("Bank of America: Your online banking has been temporarily disabled. Visit http://bofa-verify-identity.com to reactivate.", "fraud_account_suspension_lure"),
    ("Exclusive Crypto VIP signal: Earn 300% return guaranteed within 24 hours! Join WhatsApp group: https://t.me/cryptogains999", "fraud_telegram_income_lure"),
    ("Netflix: Your subscription payment failed. Your account will be closed today unless updated: http://netflix-billing-renew.info", "fraud_subscription_billing_scam"),
    ("Toll Services: You have an unpaid toll invoice of $12.50. Late fees apply after 24h. Pay at: http://sunpass-toll-billing.top", "fraud_subscription_billing_scam"),
    ("PayPal Security: Unauthorized transaction of $699.99 to Apple Store. Not you? Dispute immediately at: http://paypal-dispute-resolve.com", "fraud_transaction_dispute_lure"),
    ("You have (1) pending package awaiting clearance. Confirm your identity and pay customs fee: http://dhl-express-clearance.net/track", "fraud_postal_customs_fee"),
    ("URGENT: Your Apple ID has been locked for security reasons. Verify your account details: http://appleid-support-auth.com", "fraud_account_suspension_lure"),
    ("Alert from Citibank: Suspicious wire transfer of $2,450 initiated. Stop transfer here: http://citi-security-stop.com", "fraud_transaction_dispute_lure"),
    ("Winner notification! You have been selected for the 2026 Cash App Giveaway. Receive $750 instantly: http://cashapp-free750.online", "fraud_prize_giveaway_lure"),
    ("Your SIM card will be deactivated in 24 hours due to unverified KYC. Update details now: http://telecom-kyc-verify.club", "fraud_device_telecom_account_phish"),
    ("Amazon Security: Did you purchase iPhone 16 Pro for $1,199? If NOT, call fraud team right away at 1-888-555-0144.", "fraud_callback_order_scam"),
    ("Dear customer, your debit card is blocked. Click http://chase-unblock-card.biz to submit photo ID and unlock.", "fraud_card_blocked_lure"),
    ("FedEx: Delivery exception! Package held at facility due to unpaid duty. Pay $2.40: http://fedex-express-customs.cc", "fraud_postal_customs_fee"),
    ("Target Shopper: You were chosen to receive a $500 shopping voucher! Complete short survey: http://target-voucher-survey.site", "fraud_prize_giveaway_lure"),
    ("Your social security number has been compromised in a fraud investigation. Press 1 to speak with a federal agent.", "fraud_legal_tax_extortion"),
    ("Attn: Your account with AT&T will be cancelled. Pay overdue balance of $45.10 here: http://att-billpay-portal.info", "fraud_subscription_billing_scam"),
    ("URGENT: Venmo unauthorized charge of $450 to Steam Games. Cancel this payment: http://venmo-security-dispute.link", "fraud_transaction_dispute_lure"),
    ("You qualified for $50,000 pre-approved loan with 0% APR. No credit check required! Apply now: http://fast-cash-loans-today.us", "fraud_grant_loan_lure"),
    ("Crypto alert: 1.45 BTC has been deposited to your wallet. Confirm receipt and withdraw: http://binance-claim-crypto.cc", "fraud_crypto_account_lure"),
    ("Your package #91823 is held at depot. Final delivery attempt tomorrow. Verify address: http://postal-package-update.info", "fraud_postal_customs_fee"),
    ("Warning: Your iPhone backup was compromised. Visit http://icloud-warning-check.me to change password immediately.", "fraud_device_telecom_account_phish"),
    ("Santander Alert: Card blocked due to suspicious activity. Follow link to verify: http://santander-unblock-service.top", "fraud_card_blocked_lure"),
    ("Work from home opportunity! Earn $500/day rating products on your phone. Telegram: @jobrecruiter2026", "fraud_telegram_income_lure"),
    ("Geek Squad: Auto-renewal charge of $399.99 processed. To request refund within 24h call: 1-800-555-0182", "fraud_callback_order_scam"),
    ("Exclusive invitation: You are eligible to claim free government relief grant of $2,500. Register: http://gov-grant-claim.org", "fraud_grant_loan_lure"),
    ("TD Bank: Suspicious login from IP 194.26.29.1. Secure your account now: http://tdbank-customer-protect.net", "fraud_suspicious_ip_login_lure"),
    ("Capital One alert: Debit card flagged for fraud at Best Buy. Confirm identity: http://capitalone-fraud-prevention.xyz", "fraud_card_blocked_lure"),
    ("Your WhatsApp account will expire tomorrow. Renew your service for $0.99 here: http://whatsapp-subscription-renew.com", "fraud_subscription_billing_scam"),
    ("URGENT legal notice: Process server dispatched to your location. Call 855-555-0129 to settle dispute before court.", "fraud_legal_tax_extortion"),
    ("Costco rewards: You have $150 in unredeemed cash back rewards expiring tonight! Redeem at: http://costco-cashback-points.site", "fraud_prize_giveaway_lure"),
    ("Alert: Coinbase security key reset requested. If you did not initiate this, freeze account: http://coinbase-freeze-auth.com", "fraud_crypto_account_lure"),
    ("US Postal Notice: Missing apartment number on parcel. Re-enter shipping address: http://usps-address-correct.com", "fraud_postal_customs_fee"),
    ("Final reminder: Your car warranty is about to lapse. Extend coverage before deadline: http://auto-warranty-renew.online", "fraud_subscription_billing_scam"),
    ("Your mobile number won 2nd prize in the UK National Lottery! Send email to claim: claim@national-lottery-promo.co", "fraud_prize_giveaway_lure"),
    ("Citizens Bank: Transaction of $840 declined. Verify your phone number to re-enable card: http://citizens-verify.cc", "fraud_transaction_dispute_lure"),
]

LEGITIMATE_MESSAGES: list[str] = [text for text, _ in LEGIT_BASE_SAMPLES]
FRAUDULENT_MESSAGES: list[str] = [text for text, _ in FRAUD_BASE_SAMPLES]

CONVERSATIONAL_BASE_SAMPLES: list[tuple[str, str]] = [
    ("Are we still on for lunch tomorrow afternoon?", "legit_casual_social_chat"),
    ("Don't forget to lock the garage door on your way out.", "legit_casual_errands"),
    ("The kids had so much fun at the science museum today!", "legit_casual_family_activity"),
    ("Can you send over the slides from yesterday's presentation?", "legit_workplace_sync"),
    ("Hope you have a safe and pleasant flight back home!", "legit_casual_social_chat"),
    ("See you at soccer practice on Tuesday evening.", "legit_casual_family_activity"),
    ("Traffic is a bit heavy on highway 101, will be there shortly.", "legit_casual_social_chat"),
    ("Dinner was delicious, thanks for having us over!", "legit_casual_social_chat"),
    ("Let me know if you need any help with the garden this weekend.", "legit_casual_errands"),
    ("Just finished running at the park, heading home now.", "legit_casual_social_chat"),
    ("Wishing you a very Happy Birthday and a fantastic year ahead!", "legit_casual_birthday_greetings"),
    ("Happy Birthday! Have an amazing day celebrating with friends!", "legit_casual_birthday_greetings"),
    ("Let me know if you want to carpool to soccer practice this weekend.", "legit_casual_family_activity"),
    ("We can carpool to soccer practice on Saturday morning if you'd like.", "legit_casual_family_activity"),
    ("Could you bring my umbrella from the front hallway to the office?", "legit_casual_errands"),
    ("Don't forget your umbrella today, looks like light rain this afternoon.", "legit_casual_errands"),
]


def extract_template_family_id(
    text: str, label: int, explicit_family: str | None = None
) -> str:
    """Assigns a stable template_family_id based on normalized base text structure without variables.

    Normalizes variable components: URLs, codes, phone numbers, monetary amounts,
    reference IDs, financial institutions, consumer/tech brands, couriers, digits,
    and whitespace, hashing the canonical structure into a deterministic identifier.
    """
    if explicit_family is not None:
        return explicit_family

    norm = text
    norm = re.sub(r"https?://\S+|www\.\S+", "<URL>", norm, flags=re.IGNORECASE)
    norm = re.sub(r"[\$€£]\s*\d+(?:[.,]\d+)?", "<MONEY>", norm)
    norm = re.sub(r"#\s*[A-Za-z0-9_\-]+", "<REF_ID>", norm)
    norm = re.sub(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "<PHONE>", norm)
    norm = re.sub(
        r"\b(?:chase|wells fargo|bank of america|bofa|citibank|citi|capital one|barclays|hsbc|santander|lloyds|natwest|pnc(?: bank)?|td(?: bank)?|us bank|suntrust|citizens(?: bank)?|regions)\b",
        "<BANK_ENTITY>",
        norm,
        flags=re.IGNORECASE,
    )
    norm = re.sub(
        r"\b(?:walmart|target|best buy|costco|home depot|amazon|apple|netflix|google|microsoft|slack|uber|lyft|doordash|chipotle|venmo|paypal|docusign|quickbooks|zoom|adobe|norton|geek squad|coinbase|kraken|binance|bitstamp)\b",
        "<BRAND_ENTITY>",
        norm,
        flags=re.IGNORECASE,
    )
    norm = re.sub(
        r"\b(?:usps|fedex|ups|dhl(?: express)?)\b",
        "<COURIER_ENTITY>",
        norm,
        flags=re.IGNORECASE,
    )
    norm = re.sub(r"\b\d{4,}\b", "<CODE>", norm)
    norm = re.sub(r"\b\d+\b", "<DIGIT>", norm)
    norm = re.sub(r"\s+", " ", norm).strip().lower()
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]
    tag = "fraud" if label == 1 else "legit"
    return f"{tag}_tf_{h}"


def build_augmented_dataset() -> tuple[list[str], list[int], list[str]]:
    """Generates an augmented, balanced dataset of telecom SMS samples with template-family grouping."""
    texts: list[str] = []
    labels: list[int] = []
    groups: list[str] = []

    def _add_sample(msg: str, lbl: int, explicit_family: str | None = None) -> None:
        texts.append(msg)
        labels.append(lbl)
        groups.append(extract_template_family_id(msg, lbl, explicit_family))

    # Add base legitimate messages with audited explicit semantic families (SF-008)
    for msg, fam_id in LEGIT_BASE_SAMPLES:
        _add_sample(msg, 0, explicit_family=fam_id)

    # Add base fraudulent messages with audited explicit semantic families (SF-008)
    for msg, fam_id in FRAUD_BASE_SAMPLES:
        _add_sample(msg, 1, explicit_family=fam_id)

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
        brand_key = brand.lower().replace(" ", "")
        for domain in scam_domains:
            _add_sample(
                f"URGENT: {brand} security alert! Unusual sign-in detected. Confirm identity: http://{brand_key}-{domain}",
                1,
                explicit_family="fraud_urgent_brand_alert",
            )

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
            _add_sample(
                f"{service} security code: {code}. It expires in 5 minutes. Never share this with anyone.",
                0,
                explicit_family="legit_2fa_code",
            )

    # Expand structural diversity of URL-free, callback-free A2P 2FA/OTP templates
    otp_services = ["Cloudflare", "DigitalOcean", "Linear", "Notion", "Vercel", "Figma"]
    otp_codes = [194820, 503918, 728194, 846201, 319472, 629104]
    otp_templates: tuple[tuple[str, str], ...] = (
        ("legit_2fa_phone_verify", "{service}: Confirmation code {code} to verify phone number."),
        ("legit_2fa_email_verify", "{service}: Enter passcode {code} to verify your email address."),
        (
            "legit_2fa_login_approve",
            "{service} Verify: Tap to approve login attempt from Chrome browser on macOS.",
        ),
        (
            "legit_2fa_login_alert",
            "{service} security alert: New browser login from Austin, TX. Ignore if this was you.",
        ),
        (
            "legit_2fa_recovery_pin",
            "{service} security PIN: {code} for account recovery or to reset password.",
        ),
        (
            "legit_2fa_auth_signin",
            "{service} Security: One-time passcode {code} for authentication and workspace access.",
        ),
    )
    for fam_id, tmpl in otp_templates:
        for i, svc in enumerate(otp_services):
            _add_sample(
                tmpl.format(service=svc, code=otp_codes[i] + (i * 13)),
                0,
                explicit_family=fam_id,
            )

    # Augment legit banking notifications (teaching model that legitimate banking alerts exist)
    legit_banks = [
        "Chase", "Wells Fargo", "Bank of America", "Citibank", "Capital One",
        "PNC Bank", "TD Bank", "US Bank"
    ]
    for i, b in enumerate(legit_banks):
        for j in range(5):
            _add_sample(
                f"{b} Update: Your checking account ending in {1000 + i * 100 + j} monthly statement is ready to view.",
                0,
                explicit_family="legit_bank_statement",
            )
            _add_sample(
                f"{b}: Autopay confirmation for your utility bill payment of ${45 + j * 10}.00 processed.",
                0,
                explicit_family="legit_bank_autopay",
            )
            _add_sample(
                f"{b} Alert: Direct deposit of ${800 + j * 150}.00 from employer payroll posted successfully.",
                0,
                explicit_family="legit_bank_direct_deposit",
            )

    # Augment legit bank 2-way verification alerts partitioned by exact template syntax (SF-008)
    for b in legit_banks:
        for j in range(5):
            _add_sample(
                f"{b} Fraud Alert: Did you attempt ${35 + j * 12}.50 at Shell? Reply YES or NO. If no, your card will be blocked.",
                0,
                explicit_family="legit_bank_fraud_alert_yesno",
            )
            _add_sample(
                f"{b} Security Alert: Unusual charge of ${50 + j * 20}.00 at Chevron. Text 1 if authorized, 2 if not.",
                0,
                explicit_family="legit_bank_security_alert_12",
            )
            _add_sample(
                f"{b} Alert: Did you authorize ${80 + j * 15}.00 transaction at Walmart? Reply Y or N. FreeMsg.",
                0,
                explicit_family="legit_bank_auth_alert_yn",
            )

    # Augment legit retail receipts & store pickups
    retail_chains = ["Target", "Walmart", "Best Buy", "Costco", "Starbucks", "Home Depot"]
    for i, r in enumerate(retail_chains):
        for j in range(4):
            _add_sample(
                f"{r} eReceipt: Order #{20000 + i * 100 + j} was paid in store. Thank you for your business.",
                0,
                explicit_family="legit_retail_receipt",
            )
            _add_sample(
                f"{r} Curbside: Order #{30000 + i * 100 + j} is ready for pickup in designated space.",
                0,
                explicit_family="legit_retail_curbside",
            )

    # Augment legit travel & airline notifications
    airlines = ["Delta Air Lines", "United Airlines", "American Airlines", "Southwest Airlines"]
    for i, a in enumerate(airlines):
        for j in range(5):
            _add_sample(
                f"{a}: Flight confirmation #{4000 + i * 10 + j}. Check-in opens 24 hours prior to departure.",
                0,
                explicit_family="legit_travel_flight_confirmation",
            )
            _add_sample(
                f"{a} Gate Info: Your scheduled departure is on time at Gate {chr(65 + i)}{10 + j}.",
                0,
                explicit_family="legit_travel_gate_info",
            )

    # Augment legit healthcare notifications
    for i in range(20):
        _add_sample(
            f"MyChart Notification: Patient test results #{5000 + i} from Dr. Taylor are now available online.",
            0,
            explicit_family="legit_health_mychart",
        )
        _add_sample(
            f"Pharmacy Refill: Prescription #{6000 + i} is filled and ready for pickup at local counter.",
            0,
            explicit_family="legit_health_pharmacy",
        )

    # Augment legit conversational messages with audited semantic families (SF-008)
    for c_text, fam_id in CONVERSATIONAL_BASE_SAMPLES:
        _add_sample(c_text, 0, explicit_family=fam_id)

    # Augment fraud with financial and delivery scams
    banks_fraud = ["Barclays", "HSBC", "Santander", "Lloyds", "NatWest", "Standard Chartered"]
    scam_domains_extra = [
        "auth-alert.xyz", "secure-desk.top", "verify-card.cc", "login-gate.club", "resolve-fraud.biz"
    ]
    for b in banks_fraud:
        b_key = b.lower().replace(" ", "")
        for d in scam_domains_extra:
            _add_sample(
                f"URGENT: {b} security alert! Suspicious activity detected. Unlock account: http://{b_key}-{d}",
                1,
                explicit_family="fraud_uk_bank_alert",
            )

    for i in range(25):
        _add_sample(
            f"Postal Alert: Package #{10000 + i * 7} requires customs fee of $2.50 to release shipment: http://parcel-clearance-{i}.info",
            1,
            explicit_family="fraud_postal_customs_fee",
        )

    # Calibrate Class A benign phone repair, device-switch, and everyday P2P app chatter (SF-007)
    repair_pickup_shops = [
        ("FixIt Mobile Repair", "Oak St counter", "smartphone display replacement"),
        ("uBreakiFix Shop", "Market Ave desk", "glass screen replacement"),
        ("TechPulse Repair", "Main Plaza counter", "charging port repair"),
        ("BatteryPlus Service", "Pine St desk", "screen and battery swap"),
        ("MobileCare Center", "Elm Ave counter", "front camera and glass repair"),
    ]
    for idx, (shop, desk, work) in enumerate(repair_pickup_shops):
        _add_sample(
            f"{shop}: Your {work} (#R{3100 + idx}) is repaired and ready for pickup at our {desk}. Message us on WhatsApp with questions.",
            0,
            explicit_family="legit_phone_repair_pickup",
        )

    repair_quotes = [
        "Metro Device Clinic: Repair quote #7810 approved for your cracked display. Technician will update you on WhatsApp.",
        "SmartFix Service Center: Diagnostic completed on your mobile handset. Quote is $79; message WhatsApp desk to confirm.",
        "Apex Phone Repair: Replacement parts arrived at our service center. Technician note posted via Signal.",
        "BlueLine Repair Shop: Warranty screen replacement is covered under AppleCare. Ready for collection after 4 PM.",
    ]
    for msg in repair_quotes:
        _add_sample(msg, 0, explicit_family="legit_phone_repair_quote")

    casual_device_switches = [
        "Dropped my smartphone at home this morning, replying from my tablet via WhatsApp today.",
        "My phone battery died completely at the airport, reaching out from my MacBook on Signal until tonight.",
        "Hey Sam, my phone broke at lunch so I am using an old spare handset, text me on WhatsApp later.",
        "Screen on my daily handset cracked in my bag so I switched to an old backup phone, message me on Telegram.",
        "Phone slipped on the gym floor and stopped turning on, catching up with everyone from my iPad on WhatsApp.",
        "Hey Jordan, left my phone on the kitchen charger so I am texting from my Chromebook on WhatsApp.",
        "Hey, my phone is updating in the other room so I am writing from my iPad on WhatsApp for now.",
        "Broke my old work handset last week and switched to an old one from the drawer, text me on WhatsApp.",
    ]
    for msg in casual_device_switches:
        _add_sample(msg, 0, explicit_family="legit_casual_device_switch")

    casual_family_and_p2p = [
        "Hey dad, picking up dinner on my way back home, want anything from the bakery?",
        "Hi dad, finished the lab exam early, calling you once I get off the bus.",
        "Hey, just landed in Chicago, my phone was on airplane mode all afternoon.",
        "Hey Rachel, my phone speaker stopped working after the update, texting from my iPad tonight.",
        "Hi dad, left my charger at school, using my laptop until tonight.",
        "Hey, my phone camera lens cracked on the hike, still taking pics with an old spare camera.",
        "Hey papa, just wrapped up at the office, call me on WhatsApp when free tonight.",
        "Hi Maya, got a new number today after switching carrier plans, message me on WhatsApp when free.",
    ]
    for msg in casual_family_and_p2p:
        _add_sample(msg, 0, explicit_family="legit_casual_p2p_greetings")

    temporary_travel_sim_chats = [
        "Hey Alex, picked up a temporary number on a travel SIM for Lisbon this week, text me on Telegram if we meet up.",
        "Carrier swapped my faulty SIM tray at the store and lent me a temporary number for tonight, message me on Signal.",
        "Lost my SIM card at the airport kiosk so I activated a temporary local number for tonight, chat me on Telegram.",
        "Left my regular SIM at home before the flight, using a temporary prepaid number on Telegram for two days.",
    ]
    for msg in temporary_travel_sim_chats:
        _add_sample(msg, 0, explicit_family="legit_temporary_travel_sim")

    p2p_app_chats = [
        "Are you checking the family group chat on WhatsApp before dinner tonight?",
        "Sent the hiking photos in our Signal group, let me know which ones to print.",
        "Can you forward the flight itinerary on Telegram before we head to the terminal?",
        "We moved the carpool thread over to Signal so everyone gets the pickup alerts.",
    ]
    for msg in p2p_app_chats:
        _add_sample(msg, 0, explicit_family="legit_p2p_messaging_app")

    # Augment Class C actionable family-impersonation lures across diverse templates & payment/link vectors (SF-007)
    wame_variants = [
        ("mum", "broke my phone and lost my SIM", f"wa.me/1917555{1000 + i}")
        if i == 0
        else ("mum", "shattered my phone display on the curb", f"wa.me/1917555{1000 + i}")
        if i % 3 == 0
        else ("mom", "dropped my handset and cracked the LCD", f"wa.me/1917555{1000 + i}")
        if i % 3 == 1
        else ("dad", "smashed my phone at the station", f"wa.me/1646555{2000 + i}")
        for i in range(9)
    ]
    for rel, damage, link in wame_variants:
        _add_sample(
            f"Hey {rel}, {damage}. Text my temporary WhatsApp link right now: {link}",
            1,
            explicit_family="fraud_family_wame_lure",
        )

    zelle_variants = [
        "Hey mum, broke my phone at the station. Need to pay an urgent bill of $320, can you transfer it to my Zelle?",
        "Hi mom, dropped my handset this morning and need to cover an urgent invoice of $345 via Zelle right away.",
        "Hey dad, my phone screen cracked completely. Please Zelle $370 urgently for an unexpected towing bill.",
        "Hi mama, broke my phone and locked out of banking app. Can you send $395 to my Zelle for an emergency bill?",
        "Hey mum, lost my SIM while traveling. Need to settle an urgent $420 hotel deposit, please transfer via Zelle.",
        "Hi papa, phone died before paying rent. Can you transfer $445 via Zelle for an urgent payment?",
        "Hey mom, using someone else's phone after losing mine. Please Zelle $470 right now for an urgent medical bill.",
    ]
    for msg in zelle_variants:
        _add_sample(msg, 1, explicit_family="fraud_family_zelle_lure")

    p2p_pay_variants = [
        ("dad", "dropped my phone in water", "Venmo", 350, "emergency rent"),
        ("mom", "phone broke completely", "Cash App", 280, "urgent medical bill"),
        ("mama", "got a temporary number today", "Venmo", 410, "urgent bill before 5 PM"),
        ("papa", "cracked my phone screen", "Cash App", 240, "emergency car repair bill"),
        ("mum", "using a new number tonight", "Zelle", 390, "urgent utility bill"),
        ("dad", "lost my phone and SIM card", "Cash App", 310, "emergency invoice payment"),
        ("mom", "dropped my phone earlier", "Venmo", 295, "urgent rent payment"),
        ("dad", "my phone screen shattered", "Zelle", 425, "emergency veterinary bill"),
    ]
    for rel, context, app_name, amount, reason in p2p_pay_variants:
        _add_sample(
            f"Hi {rel}, {context} and using temporary number. Please send ${amount} via {app_name} for {reason}.",
            1,
            explicit_family="fraud_family_venmo_cashapp_lure",
        )

    wire_http_variants = [
        "Hi dad, my phone broke and I am borrowing someone's phone, please wire transfer $520 immediately for an emergency bill.",
        "Hey mom, dropped my phone and lost my SIM, open https://help-family-bridge.info/verify to pay my urgent rent.",
        "Hi papa, phone screen shattered and I have a new number, please wire $450 urgent payment right away.",
        "Hey mum, borrowing a friend's phone after losing mine, click http://family-temp-pay.xyz/bill to cover $275.",
        "Hi mom, got a temporary number today, can you wire transfer $600 for an urgent hospital fee right now?",
        "Hey dad, my phone broke completely, send funds via https://temp-family-relay.top/send before bank cutoff.",
    ]
    for msg in wire_http_variants:
        _add_sample(msg, 1, explicit_family="fraud_family_wire_http_lure")

    return texts, labels, groups


def patch_skl2onnx_tfidf_bugs(
    onnx_model: onnx.ModelProto,
    fitted_tfidf_vectorizer: TfidfVectorizer,
) -> onnx.ModelProto:
    """Surgically patches two upstream skl2onnx conversion bugs in the exported ONNX graph:

    1. Dead-Bigram Vocabulary Splitting Bug (_intelligent_split):
       When max_features=2500 prunes a constituent unigram (e.g. 'windows') while retaining
       a bigram (e.g. 'on windows'), skl2onnx misclassifies 136 bigrams as 1-grams containing
       spaces inside pool_strings, making them unreachable after word tokenization.
       This rebuilds TfIdfVectorizer's pool_strings, ngram_counts, and ngram_indexes directly
       from fitted_tfidf_vectorizer.vocabulary_ split on whitespace.

    2. Sublinear TF Formula Inversion Bug (convert_sklearn_tfidf_transformer):
       skl2onnx exports sublinear_tf=True as Add(tf, 1.0) -> Log, computing ln(tf + 1)
       instead of scikit-learn's 1 + ln(tf) for tf > 0, distorting L2-normalized vectors
       whenever any token repeats (tf >= 2). This replaces the Add -> Log subgraph with:
       Where(tf > 0, Log(Max(tf, 1.0)) + 1.0, 0.0).
    """
    vocab = getattr(fitted_tfidf_vectorizer, "vocabulary_", None)
    if not isinstance(vocab, dict) or not vocab:
        raise RuntimeError("fitted_tfidf_vectorizer must have a non-empty vocabulary_ dictionary")

    tfidf_vec_nodes = [
        node for node in onnx_model.graph.node if node.op_type == "TfIdfVectorizer"
    ]
    if len(tfidf_vec_nodes) != 1:
        raise RuntimeError(
            f"Expected exactly 1 TfIdfVectorizer node in ONNX graph, found {len(tfidf_vec_nodes)}"
        )

    vocab_size = max(vocab.values()) + 1
    split_words: list[list[str]] = [[] for _ in range(vocab_size)]
    for term, idx in sorted(vocab.items(), key=lambda item: int(item[1])):
        split_words[int(idx)] = str(term).split(" ")

    ng_split_words = sorted(
        [(len(tokens), tokens, idx) for idx, tokens in enumerate(split_words)]
    )
    key_indices = [item[2] for item in ng_split_words]
    min_n, max_n = fitted_tfidf_vectorizer.ngram_range
    ngcounts = [0 for _ in range(min_n)]
    pool_words = list(ng_split_words[0][1])
    for i in range(1, len(ng_split_words)):
        if ng_split_words[i - 1][0] != ng_split_words[i][0]:
            ngcounts.append(len(pool_words))
        pool_words.extend(ng_split_words[i][1])

    weights = [1.0 for _ in range(vocab_size)]

    # 1. Rebuild TfIdfVectorizer node attributes with exact 1-gram and 2-gram pools
    vec_node = tfidf_vec_nodes[0]
    del vec_node.attribute[:]
    vec_node.attribute.extend(
        [
            onnx.helper.make_attribute("min_gram_length", int(min_n)),
            onnx.helper.make_attribute("max_gram_length", int(max_n)),
            onnx.helper.make_attribute("mode", "TF"),
            onnx.helper.make_attribute("max_skip_count", 0),
            onnx.helper.make_attribute(
                "pool_strings", [w.encode("utf-8") for w in pool_words]
            ),
            onnx.helper.make_attribute("ngram_indexes", key_indices),
            onnx.helper.make_attribute("ngram_counts", ngcounts),
            onnx.helper.make_attribute("weights", weights),
        ]
    )

    # 2. Replace Add(output, ones) -> Log(plus1) with exact scikit-learn 1 + ln(tf) for tf > 0
    if fitted_tfidf_vectorizer.sublinear_tf:
        existing_inits = {init.name for init in onnx_model.graph.initializer}
        if "ones" not in existing_inits:
            raise RuntimeError(
                "Missing 'ones' initializer required for sublinear_tf ONNX graph patch"
            )

        expected_patched_names = {
            "SublinearMax",
            "SublinearLog",
            "SublinearAdd",
            "SublinearGreater",
            "SublinearWhere",
        }
        present_patched_names = {
            node.name for node in onnx_model.graph.node if node.name in expected_patched_names
        }
        has_unpatched_add = any(
            node.op_type == "Add"
            and list(node.input) == ["output", "ones"]
            and list(node.output) == ["plus1"]
            for node in onnx_model.graph.node
        )
        has_unpatched_log = any(
            node.op_type == "Log"
            and list(node.input) == ["plus1"]
            and list(node.output) == ["plus1logged"]
            for node in onnx_model.graph.node
        )

        if present_patched_names == expected_patched_names and not has_unpatched_add and not has_unpatched_log:
            if "zeros_scalar" not in existing_inits:
                raise RuntimeError(
                    "Corrupted already-patched ONNX graph: missing 'zeros_scalar' initializer"
                )
        elif present_patched_names:
            raise RuntimeError(
                f"Corrupted or partially patched sublinear_tf subgraph: found {sorted(present_patched_names)}"
            )
        else:
            if not (has_unpatched_add and has_unpatched_log):
                raise RuntimeError(
                    "Could not locate expected skl2onnx sublinear_tf Add(output, ones) -> Log(plus1) nodes to patch"
                )

            if "zeros_scalar" not in existing_inits:
                onnx_model.graph.initializer.append(
                    onnx.numpy_helper.from_array(
                        np.array([0.0], dtype=np.float32), name="zeros_scalar"
                    )
                )

            new_nodes: list[onnx.NodeProto] = []
            for node in onnx_model.graph.node:
                if (
                    node.op_type == "Add"
                    and list(node.input) == ["output", "ones"]
                    and list(node.output) == ["plus1"]
                ):
                    continue
                if (
                    node.op_type == "Log"
                    and list(node.input) == ["plus1"]
                    and list(node.output) == ["plus1logged"]
                ):
                    new_nodes.extend(
                        [
                            onnx.helper.make_node(
                                "Max",
                                inputs=["output", "ones"],
                                outputs=["tf_clamped"],
                                name="SublinearMax",
                            ),
                            onnx.helper.make_node(
                                "Log",
                                inputs=["tf_clamped"],
                                outputs=["tf_logged"],
                                name="SublinearLog",
                            ),
                            onnx.helper.make_node(
                                "Add",
                                inputs=["tf_logged", "ones"],
                                outputs=["tf_one_plus_log"],
                                name="SublinearAdd",
                            ),
                            onnx.helper.make_node(
                                "Greater",
                                inputs=["output", "zeros_scalar"],
                                outputs=["tf_pos_mask"],
                                name="SublinearGreater",
                            ),
                            onnx.helper.make_node(
                                "Where",
                                inputs=["tf_pos_mask", "tf_one_plus_log", "zeros_scalar"],
                                outputs=["plus1logged"],
                                name="SublinearWhere",
                            ),
                        ]
                    )
                    continue
                new_nodes.append(node)

            del onnx_model.graph.node[:]
            onnx_model.graph.node.extend(new_nodes)

    # 3. Canonically sort opset_import by (domain, version) to guarantee clean-process
    # byte-for-byte determinism across arbitrary PYTHONHASHSEED values.
    sorted_opsets = sorted(
        [(str(opset.domain), int(opset.version)) for opset in onnx_model.opset_import],
        key=lambda item: (item[0], item[1]),
    )
    del onnx_model.opset_import[:]
    for domain, version in sorted_opsets:
        onnx_model.opset_import.append(onnx.helper.make_opsetid(domain, version))

    onnx.checker.check_model(onnx_model)
    return onnx_model


def _atomic_write_text(target_path: Path, content: str) -> None:
    """Atomically replaces a UTF-8 text file via same-directory temp write and rename."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=f".{target_path.stem}_",
        suffix=target_path.suffix,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        tmp_path.replace(target_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _compute_cross_split_leakage_audit(
    texts: list[str],
    labels: list[int],
    template_family_ids: list[str],
) -> dict[str, Any]:
    """Audits Dev/Val SHA-256 overlap, duplicates, and cross-family similarity."""
    def _norm_hash(value: str) -> str:
        norm = re.sub(r"\s+", " ", value.strip().lower())
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    train_hashes = [_norm_hash(t) for t in texts]
    unique_train_hashes = set(train_hashes)
    held_out_texts, _ = get_held_out_evaluation_set()
    held_out_hashes = {_norm_hash(t) for t in held_out_texts}

    structural_hashes: dict[str, set[str]] = {}
    for text, label, fam in zip(texts, labels, template_family_ids, strict=True):
        struct_id = extract_template_family_id(text, label)
        structural_hashes.setdefault(struct_id, set()).add(fam)
    cross_family_struct_collisions = sum(
        1 for fam_set in structural_hashes.values() if len(fam_set) > 1
    )

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=2500,
        min_df=1,
        token_pattern=r"\b[a-zA-Z0-9_]+\b",
    )
    tfidf_train = vectorizer.fit_transform(texts).toarray()
    tfidf_eval = vectorizer.transform(held_out_texts).toarray()

    ordered_families = sorted(set(template_family_ids))
    fam_to_indices: dict[str, list[int]] = {f: [] for f in ordered_families}
    for idx, fam in enumerate(template_family_ids):
        fam_to_indices[fam].append(idx)

    centroids = np.vstack([tfidf_train[fam_to_indices[f]].mean(axis=0) for f in ordered_families])
    norms = np.linalg.norm(centroids, axis=1, keepdims=True)
    centroids_unit = centroids / np.where(norms > 0.0, norms, 1.0)
    fam_sim = centroids_unit @ centroids_unit.T
    np.fill_diagonal(fam_sim, -1.0)

    flat_max_idx = int(np.argmax(fam_sim))
    i_max, j_max = divmod(flat_max_idx, len(ordered_families))
    upper_tri = fam_sim[np.triu_indices(len(ordered_families), k=1)]

    eval_train_sim = tfidf_eval @ tfidf_train.T
    max_dev_val_train_cos = float(np.max(eval_train_sim))
    mean_dev_val_max_cos = float(np.mean(np.max(eval_train_sim, axis=1)))

    return {
        "dev_val_sample_count": len(held_out_texts),
        "dev_val_normalized_sha256_overlap": len(unique_train_hashes.intersection(held_out_hashes)),
        "intra_corpus_normalized_sha256_duplicates": len(texts) - len(unique_train_hashes),
        "structural_template_hash_collisions_across_families": cross_family_struct_collisions,
        "max_cross_family_centroid_cosine": round(float(fam_sim[i_max, j_max]), 6),
        "mean_cross_family_centroid_cosine": round(float(np.mean(upper_tri)), 6),
        "max_cross_family_centroid_pair": [ordered_families[i_max], ordered_families[j_max]],
        "max_dev_val_vs_train_tfidf_cosine": round(max_dev_val_train_cos, 6),
        "mean_dev_val_nearest_train_tfidf_cosine": round(mean_dev_val_max_cos, 6),
    }


def build_dataset_inventory(
    texts: list[str] | None = None,
    labels: list[int] | None = None,
    template_family_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Builds the audited machine-readable training dataset inventory and CV balance report."""
    if texts is None or labels is None or template_family_ids is None:
        texts, labels, template_family_ids = build_augmented_dataset()

    total_samples = len(texts)
    legit_count = labels.count(0)
    fraud_count = labels.count(1)
    fraud_prevalence = round(fraud_count / total_samples, 6)
    dataset_sha256 = hashlib.sha256(
        "".join(f"{t}:{lbl}" for t, lbl in zip(texts, labels, strict=True)).encode("utf-8")
    ).hexdigest()

    fam_legit: Counter[str] = Counter()
    fam_fraud: Counter[str] = Counter()
    for lbl, fam in zip(labels, template_family_ids, strict=True):
        if lbl == 1:
            fam_fraud[fam] += 1
        else:
            fam_legit[fam] += 1

    all_families = sorted(set(template_family_ids))
    family_rows: list[dict[str, Any]] = []
    for fam in all_families:
        l_cnt = fam_legit[fam]
        f_cnt = fam_fraud[fam]
        s_cnt = l_cnt + f_cnt
        fam_label: int | str = 1 if l_cnt == 0 else 0 if f_cnt == 0 else "mixed"
        family_rows.append(
            {
                "family_id": fam,
                "label": fam_label,
                "legit_count": l_cnt,
                "fraud_count": f_cnt,
                "sample_count": s_cnt,
                "pct_of_corpus": round((100.0 * s_cnt) / total_samples, 4),
            }
        )
    family_rows.sort(key=lambda row: (-int(row["sample_count"]), str(row["family_id"])))

    sizes = [int(row["sample_count"]) for row in family_rows]
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    fold_distributions: list[dict[str, Any]] = []
    for fold_idx, (tr_idx, val_idx) in enumerate(
        sgkf.split(texts, labels, groups=template_family_ids)
    ):
        y_tr = [labels[i] for i in tr_idx]
        y_va = [labels[i] for i in val_idx]
        tr_groups = {template_family_ids[i] for i in tr_idx}
        va_groups = {template_family_ids[i] for i in val_idx}
        tr_rate = y_tr.count(1) / len(y_tr)
        va_rate = y_va.count(1) / len(y_va)
        fold_distributions.append(
            {
                "fold": fold_idx,
                "train_size": len(tr_idx),
                "val_size": len(val_idx),
                "train_legit_count": y_tr.count(0),
                "train_fraud_count": y_tr.count(1),
                "val_legit_count": y_va.count(0),
                "val_fraud_count": y_va.count(1),
                "train_fraud_rate": round(tr_rate, 6),
                "val_fraud_rate": round(va_rate, 6),
                "val_fraud_prevalence_delta": round(va_rate - (fraud_count / total_samples), 6),
                "group_overlap_count": len(tr_groups.intersection(va_groups)),
            }
        )

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "training_dataset_sha256": dataset_sha256,
        "total_samples": total_samples,
        "legit_count": legit_count,
        "fraud_count": fraud_count,
        "fraud_prevalence": fraud_prevalence,
        "total_families": len(all_families),
        "singleton_family_count": sum(1 for sz in sizes if sz == 1),
        "family_size_stats": {
            "min": min(sizes),
            "median": round(float(statistics.median(sizes)), 4),
            "mean": round(float(statistics.mean(sizes)), 4),
            "max": max(sizes),
            "max_pct_of_corpus": round((100.0 * max(sizes)) / total_samples, 4),
        },
        "families": family_rows,
        "fold_distributions": fold_distributions,
        "cross_split_leakage_audit": _compute_cross_split_leakage_audit(
            texts,
            labels,
            template_family_ids,
        ),
    }


def export_dataset_inventory(
    inventory: dict[str, Any],
    output_path: Path | None = None,
) -> Path:
    """Atomically writes the dataset inventory JSON report."""
    target = (
        output_path
        if output_path is not None
        else Path(__file__).resolve().parent / "dataset_inventory.json"
    )
    _atomic_write_text(target, json.dumps(inventory, indent=2) + "\n")
    logger.info("Exported dataset inventory report to %s", target)
    return target


def train_and_export_model(
    output_dir: str = "app/telecom/models",
    model_name: str = "sms_fraud_model.onnx",
    metadata_name: str = "sms_fraud_metadata.json",
    *,
    publish_eval_artifacts: bool | None = None,
) -> dict[str, Any]:
    """Trains the NLP model, evaluates performance metrics, and exports to ONNX."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    onnx_file = output_path / model_name
    metadata_file = output_path / metadata_name

    logger.info("Generating augmented telecom dataset...")
    texts, labels, template_family_ids = build_augmented_dataset()
    logger.info(
        "Total dataset size: %d samples (Legit: %d, Fraud: %d) across %d template families",
        len(texts),
        labels.count(0),
        labels.count(1),
        len(set(template_family_ids)),
    )

    # Strictly verify zero train/test hash leakage against development & validation benchmark suite
    def _hash_text(t: str) -> str:
        return hashlib.sha256(re.sub(r"\s+", " ", t.strip().lower()).encode("utf-8")).hexdigest()

    held_out_texts, _ = get_held_out_evaluation_set()
    train_hashes = {_hash_text(t) for t in texts}
    held_out_hashes = {_hash_text(t) for t in held_out_texts}
    leakage = train_hashes.intersection(held_out_hashes)
    if leakage:
        raise ValueError(
            f"CRITICAL: Train/Test leakage detected in {len(leakage)} samples: {leakage}"
        )
    logger.info(
        "Leakage check passed: Zero normalized SHA-256 overlap between training corpus (%d) and development/validation benchmark suite (%d). "
        "Template families are isolated across folds. Semantic overlap is naturally present in real-world NLP domains.",
        len(train_hashes),
        len(held_out_hashes),
    )

    # Group-based train / validation split (80 / 20) with StratifiedGroupKFold
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    train_idx, val_idx = next(sgkf.split(texts, labels, groups=template_family_ids))
    x_train = [texts[i] for i in train_idx]
    y_train = [labels[i] for i in train_idx]
    x_test = [texts[i] for i in val_idx]
    y_test = [labels[i] for i in val_idx]

    groups_train = {template_family_ids[i] for i in train_idx}
    groups_val = {template_family_ids[i] for i in val_idx}
    if not groups_train.isdisjoint(groups_val):
        overlap = groups_train.intersection(groups_val)
        raise ValueError(f"CRITICAL: Template-family leakage between train and val: {overlap}")
    logger.info(
        "Group split verified: %d train template families (%d samples, %d legit / %d fraud) | %d val template families (%d samples, %d legit / %d fraud) | Template family overlap: 0",
        len(groups_train),
        len(x_train),
        y_train.count(0),
        y_train.count(1),
        len(groups_val),
        len(x_test),
        y_test.count(0),
        y_test.count(1),
    )

    # Base Logistic Regression classifier
    base_clf = LogisticRegression(
        C=1.5,
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
    )

    # 1. Uncalibrated pipeline (baseline for Brier score measurement)
    tfidf = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=2500,
        min_df=1,
        token_pattern=r"\b[a-zA-Z0-9_]+\b",
    )
    uncalibrated_pipeline = Pipeline([("tfidf", tfidf), ("clf", base_clf)])
    uncalibrated_pipeline.fit(x_train, y_train)
    y_prob_uncal = uncalibrated_pipeline.predict_proba(x_test)[:, 1]
    brier_before = float(brier_score_loss(y_test, y_prob_uncal))

    # 2. Fully calibrated pipeline using 5-fold cross-validated Platt scaling (sigmoid)
    logger.info("Training CalibratedClassifierCV(LogisticRegression, method='sigmoid', cv=5)...")
    calibrated_clf = CalibratedClassifierCV(
        estimator=LogisticRegression(
            C=1.5,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        ),
        method="sigmoid",
        cv=5,
    )
    calibrated_pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    max_features=2500,
                    min_df=1,
                    token_pattern=r"\b[a-zA-Z0-9_]+\b",
                ),
            ),
            ("clf", calibrated_clf),
        ]
    )
    calibrated_pipeline.fit(x_train, y_train)

    # Evaluate calibrated model on stratified validation split
    y_pred = calibrated_pipeline.predict(x_test)
    y_prob = calibrated_pipeline.predict_proba(x_test)[:, 1]

    precision = float(precision_score(y_test, y_pred))
    recall = float(recall_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_prob))
    pr_auc = float(average_precision_score(y_test, y_prob))
    brier_after = float(brier_score_loss(y_test, y_prob))
    report = classification_report(y_test, y_pred, output_dict=True)

    logger.info("Stratified Validation Split Results:")
    logger.info("  Brier Score (Before Calibration): %.4f", brier_before)
    logger.info("  Brier Score (After Calibration):  %.4f", brier_after)
    logger.info("  Precision: %.4f", precision)
    logger.info("  Recall:    %.4f", recall)
    logger.info("  F1 Score:  %.4f", f1)
    logger.info("  ROC-AUC:   %.4f", roc_auc)
    logger.info("  PR-AUC:    %.4f", pr_auc)

    # 3. Fit production calibrated pipeline on full augmented dataset for ONNX export
    logger.info("Fitting production pipeline on all %d samples for ONNX export...", len(texts))
    prod_calibrated_clf = CalibratedClassifierCV(
        estimator=LogisticRegression(
            C=1.5,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        ),
        method="sigmoid",
        cv=5,
    )
    prod_pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    max_features=2500,
                    min_df=1,
                    token_pattern=r"\b[a-zA-Z0-9_]+\b",
                ),
            ),
            ("clf", prod_calibrated_clf),
        ]
    )
    prod_pipeline.fit(texts, labels)

    # Export calibrated production pipeline to ONNX with string tensor input
    logger.info("Exporting calibrated pipeline to ONNX format (opset 14)...")
    initial_type = [("text", StringTensorType([None, 1]))]
    onnx_model = to_onnx(prod_pipeline, initial_types=initial_type, target_opset=14)
    onnx_model = patch_skl2onnx_tfidf_bugs(onnx_model, prod_pipeline.named_steps["tfidf"])

    # Serialize ONNX model bytes in memory before touching disk
    model_bytes = onnx_model.SerializeToString()
    model_sha256 = hashlib.sha256(model_bytes).hexdigest()
    training_dataset_sha256 = hashlib.sha256(
        "".join(f"{t}:{lbl}" for t, lbl in zip(texts, labels, strict=True)).encode("utf-8")
    ).hexdigest()
    logger.info("Compiled ONNX model in memory (%d bytes, SHA256: %s)", len(model_bytes), model_sha256)

    canonical_paths = get_canonical_artifact_paths()
    is_canonical_target = (
        onnx_file.resolve() == canonical_paths["model"].resolve()
        and metadata_file.resolve() == canonical_paths["metadata"].resolve()
    )
    if publish_eval_artifacts is True and not is_canonical_target:
        raise ValueError(
            "publish_eval_artifacts=True requires targeting canonical model and metadata paths"
        )
    should_publish_canonical = (
        is_canonical_target if publish_eval_artifacts is None else publish_eval_artifacts
    )

    base_metadata: dict[str, Any] = {
        "model_name": "SentinelPulse-SMS-Fraud-ONNX",
        "version": "1.0.0",
        "architecture": "TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, token_pattern=r'\\b[a-zA-Z0-9_]+\\b') -> CalibratedClassifierCV(LogisticRegression(C=1.5, class_weight=balanced), method=sigmoid, cv=5)",
        "framework": "scikit-learn + skl2onnx + onnxruntime",
        "opset": 14,
        "model_sha256": model_sha256,
        "training_dataset_sha256": training_dataset_sha256,
        "calibration": {
            "method": "sigmoid",
            "cv_folds": 5,
            "brier_score_before": round(brier_before, 4),
            "brier_score_after": round(brier_after, 4),
            "brier_score_improvement": round(brier_before - brier_after, 4),
        },
        "input_signature": {"text": "StringTensor([None, 1])"},
        "output_signature": {
            "label": "Int64Tensor([None])",
            "probabilities": "Sequence[Map[Int64, Float]]",
        },
        "validation_metrics": {
            "test_sample_count": len(y_test),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "brier_score": round(brier_after, 4),
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

    if should_publish_canonical:
        logger.info("Publishing trained ONNX model and evaluation artifacts atomically...")
        inventory = build_dataset_inventory(texts, labels, template_family_ids)
        export_dataset_inventory(
            inventory,
            output_path=canonical_paths["model"].resolve().parents[1] / "dataset_inventory.json",
        )
        publish_evaluation_artifacts_atomically(
            artifact_paths=canonical_paths,
            reference_pipeline=prod_pipeline,
            staged_model_bytes=model_bytes,
            base_metadata=base_metadata,
            extra_metrics_fields={
                "brier_score_before_calibration": round(brier_before, 4),
                "brier_score_after_calibration": round(brier_after, 4),
            },
        )
        return dict(json.loads(canonical_paths["metadata"].read_text(encoding="utf-8")))

    # Custom/non-canonical export: evaluate staged bytes in memory and explicitly mark
    # canonical repo evaluation artifacts as stale for this custom build.
    inventory = build_dataset_inventory(texts, labels, template_family_ids)
    export_dataset_inventory(inventory, output_path=onnx_file.parent / "dataset_inventory.json")
    with tempfile.TemporaryDirectory(prefix="sentinelflow_custom_eval_") as tmp_dir:
        tmp_onnx = Path(tmp_dir) / model_name
        tmp_onnx.write_bytes(model_bytes)
        held_out_metrics = evaluate_onnx_model(
            tmp_onnx,
            reference_pipeline=prod_pipeline,
            write_predictions=False,
        )
    held_out_metrics["brier_score_before_calibration"] = round(brier_before, 4)
    held_out_metrics["brier_score_after_calibration"] = round(brier_after, 4)

    base_metadata["evaluation_dataset_sha256"] = held_out_metrics["evaluation_dataset_sha256"]
    base_metadata["benchmark_predictions_artifact"] = held_out_metrics[
        "benchmark_predictions_artifact"
    ]
    base_metadata["benchmark_predictions_sha256"] = held_out_metrics[
        "benchmark_predictions_sha256"
    ]
    base_metadata["onnx_sklearn_parity"] = held_out_metrics["onnx_sklearn_parity"]
    base_metadata["evaluation_timestamp"] = held_out_metrics["evaluation_timestamp"]
    base_metadata["software_versions"] = held_out_metrics["software_versions"]
    base_metadata["dev_benchmark_metrics"] = held_out_metrics
    base_metadata["held_out_adversarial_metrics"] = held_out_metrics
    base_metadata["evaluation_artifacts_stale"] = True
    base_metadata["evaluation_artifacts_status"] = "stale_not_published"

    onnx_file.write_bytes(model_bytes)
    metadata_file.write_text(json.dumps(base_metadata, indent=2) + "\n", encoding="utf-8")
    logger.warning(
        "Trained model exported to %s without publishing canonical evaluation artifacts; "
        "marked evaluation_artifacts_stale=True (run evaluate_model --all to synchronize).",
        onnx_file,
    )
    return base_metadata


if __name__ == "__main__":
    train_and_export_model()

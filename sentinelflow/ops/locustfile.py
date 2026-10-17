"""Locust Load Testing Suite for SentinelPulse Telecom Intelligence Gateway.

Configured to stress-test the real-time classification gateway under heavy concurrency
(1,000–5,000 RPS) to verify p95 latency stays under 30ms SLA.
"""

from __future__ import annotations

import random
from locust import HttpUser, between, task

NORMAL_MESSAGES = [
    "Your verification code is 492018. It expires in 5 minutes.",
    "Carrier security code: 8201. carrier.com/verify",
    "Your Uber driver is arriving in a Silver Toyota Camry.",
    "Your card ending in 4102 was charged $14.50 at Trader Joe's.",
    "USPS tracking #940011189956: Package out for delivery.",
    "Your prescription is ready for pickup at Walgreens.",
    "Amazon: Order #112-4920491 has shipped.",
]

FRAUD_MESSAGES = [
    "URGENT: Chase Bank alert. Account suspended! Verify immediately: http://bit.ly/chase-verify-now",
    "CONGRATULATIONS! You won a $1,000 Walmart gift card! Claim: http://walmart-prizes2026.xyz/win",
    "USPS Alert: Package held. Pay $1.99 redelivery fee: http://tinyurl.com/usps-redelivery",
    "Wells Fargo: Unauthorized login from Russia. Verify SSN: http://wellsfargo-secure-login.ru",
    "Exclusive Crypto signal: 300% return guaranteed! Join Telegram: https://t.me/cryptogains999",
]

LEGIT_CARRIERS = ["Verizon Wireless", "AT&T Mobility", "T-Mobile USA"]
RISKY_CARRIERS = ["TextNow", "Pinger", "Bandwidth.com"]


class TelecomGatewayUser(HttpUser):
    """Simulates carrier network traffic hitting the SentinelPulse gateway."""

    # Constant high-throughput invocation
    wait_time = between(0.001, 0.005)

    @task(7)
    def classify_normal_sms(self) -> None:
        """Standard transactional and 2FA traffic (70% volume)."""
        payload = {
            "sender": f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}",
            "recipient": f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}",
            "message": random.choice(NORMAL_MESSAGES),
            "carrier": random.choice(LEGIT_CARRIERS),
            "ip": f"198.51.100.{random.randint(1, 250)}",
        }
        with self.client.post("/v1/classify", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("latency_ms", 0) > 30.0:
                    response.failure(f"Latency breached 30ms SLA: {data.get('latency_ms')}ms")
                else:
                    response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def classify_smishing_sms(self) -> None:
        """Smishing / spam attacks from virtual VoIP carriers (20% volume)."""
        payload = {
            "sender": f"+1555{random.randint(1000000, 9999999)}",
            "recipient": f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}",
            "message": random.choice(FRAUD_MESSAGES),
            "carrier": random.choice(RISKY_CARRIERS),
            "ip": f"192.0.2.{random.randint(1, 250)}",
        }
        with self.client.post("/v1/classify", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def classify_burst_attack(self) -> None:
        """Rapid-fire burst attack from single phone number testing velocity counters."""
        burst_sender = "+15558887777"
        payload = {
            "sender": burst_sender,
            "recipient": f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}",
            "message": "URGENT: Click http://bit.ly/claim-prize now!",
            "carrier": "TextNow",
            "ip": "203.0.113.88",
        }
        self.client.post("/v1/classify", json=payload)

    @task(1)
    def classify_batch_events(self) -> None:
        """Batch ingestion stream."""
        events = [
            {
                "sender": f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}",
                "recipient": f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}",
                "message": random.choice(NORMAL_MESSAGES),
                "carrier": "Verizon Wireless",
            }
            for _ in range(10)
        ]
        self.client.post("/v1/events/batch", json={"events": events})

"""Standalone Telecom Traffic Simulator for SentinelPulse Gateway.

Generates a realistic stream of telecom SMS traffic (normal transactional/conversational,
smishing attacks, and rapid-fire burst attacks) to simulate carrier network volume
and verify real-time classification throughput.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time
from typing import Any

import httpx

NORMAL_MESSAGES = [
    "Your verification code is {code}. It expires in 10 minutes. Do not share this code.",
    "Carrier security code: {code}. Valid for 5 minutes.",
    "Your Uber ride is arriving now. Driver: Ahmed in a Toyota Camry.",
    "Your card ending in 4102 was charged $14.50 at Trader Joe's. Balance: $1,240.10.",
    "USPS tracking #940011189956: Your package is out for delivery today.",
    "Reminder: Your dental cleaning with Dr. Smith is tomorrow at 2:00 PM. Reply 1 to confirm.",
    "Hey! Are you still free for dinner tonight around 7?",
    "Your appointment with Quest Diagnostics is scheduled for Thursday at 9:30 AM.",
    "Your prescription is ready for pickup at Walgreens Pharmacy.",
    "Amazon: Your order #112-4920491 has shipped and will arrive Wednesday.",
    "Your two-factor authentication token is {code} for login to GitHub.",
]

FRAUD_MESSAGES = [
    "URGENT: Chase Bank alert. Account suspended! Verify immediately: http://bit.ly/chase-verify-now",
    "CONGRATULATIONS! Your phone number won a $1,000 Walmart gift card! Claim: http://walmart-prizes2026.xyz/win",
    "USPS Alert: Package 928301 could not be delivered. Pay $1.99 redelivery fee: http://tinyurl.com/usps-redelivery",
    "Wells Fargo Security: Unauthorized login detected from Russia. Verify SSN: http://wellsfargo-secure-login.ru",
    "IRS FINAL NOTICE: You owe $4,200 delinquent taxes. Arrest warrant issued. Call 1-800-555-0199.",
    "Exclusive Crypto VIP signal: Earn 300% return guaranteed in 24h! Join Telegram: https://t.me/cryptogains999",
    "Netflix: Payment failed. Account will be closed today unless updated: http://netflix-billing-renew.info",
    "Toll Services: Unpaid toll invoice of $12.50. Late fees apply after 24h: http://sunpass-toll-billing.top",
    "PayPal Security: Unauthorized charge of $699.99 to Apple Store. Dispute: http://paypal-dispute-resolve.com",
    "Winner notification! You have been selected for $750 Cash App giveaway: http://cashapp-free750.online",
]

LEGIT_CARRIERS = ["Verizon Wireless", "AT&T Mobility", "T-Mobile USA", "Vodafone", "Orange"]
RISKY_CARRIERS = ["TextNow", "Pinger", "Bandwidth.com", "Sinch Virtual", "CPaaS Virtual"]


def generate_event(burst_sender: str | None = None) -> dict[str, Any]:
    """Generates a synthetic telecom SMS event with realistic metadata."""
    is_fraud = random.random() < 0.25

    if burst_sender:
        sender = burst_sender
        carrier = "TextNow"
        message = random.choice(FRAUD_MESSAGES)
        ip = "198.51.100.42"
    elif is_fraud:
        sender = f"+1555{random.randint(1000000, 9999999)}"
        carrier = random.choice(RISKY_CARRIERS)
        message = random.choice(FRAUD_MESSAGES)
        ip = f"192.0.2.{random.randint(1, 254)}"
    else:
        sender = f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}"
        carrier = random.choice(LEGIT_CARRIERS)
        code = random.randint(100000, 999999)
        message = random.choice(NORMAL_MESSAGES).format(code=code)
        ip = f"198.51.{random.randint(1, 254)}.{random.randint(1, 254)}"

    recipient = f"+1{random.randint(200, 999)}{random.randint(1000000, 9999999)}"

    return {
        "sender": sender,
        "recipient": recipient,
        "message": message,
        "ip": ip,
        "carrier": carrier,
    }


async def send_worker(
    client: httpx.AsyncClient,
    url: str,
    queue: asyncio.Queue[dict[str, Any] | None],
    stats: dict[str, int],
    latencies: list[float],
) -> None:
    """Worker task sending events from queue to gateway."""
    while True:
        event = await queue.get()
        if event is None:
            queue.task_done()
            break

        t0 = time.perf_counter()
        try:
            resp = await client.post(url, json=event, timeout=5.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

            if resp.status_code == 200:
                data = resp.json()
                verdict = data.get("verdict", "UNKNOWN")
                stats[verdict] = stats.get(verdict, 0) + 1
            else:
                stats["ERROR"] = stats.get("ERROR", 0) + 1
        except Exception:
            stats["EXCEPTION"] = stats.get("EXCEPTION", 0) + 1
        finally:
            queue.task_done()


async def run_simulator(
    url: str = "http://127.0.0.1:8000/v1/classify",
    total_events: int = 1000,
    concurrency: int = 20,
    target_rps: int = 100,
) -> None:
    """Runs the asynchronous traffic simulation."""
    print(f"=== SentinelPulse Telecom Traffic Simulator ===")
    print(f"Target URL:    {url}")
    print(f"Total Events:  {total_events}")
    print(f"Concurrency:   {concurrency}")
    print(f"Target RPS:    {target_rps}\n")

    stats: dict[str, int] = {"ALLOW": 0, "BLOCK": 0, "FLAG": 0}
    latencies: list[float] = []

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=1000)
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)

    async with httpx.AsyncClient(limits=limits) as client:
        # Start worker pool
        workers = [
            asyncio.create_task(send_worker(client, url, queue, stats, latencies))
            for _ in range(concurrency)
        ]

        # Generator loop with burst injection
        start_time = time.perf_counter()
        burst_sender = "+15550009999"
        interval = 1.0 / target_rps if target_rps > 0 else 0.0

        for i in range(total_events):
            # Inject high-frequency burst attack every 100 events
            is_burst = (i % 100 < 8)
            sender_to_use = burst_sender if is_burst else None

            event = generate_event(burst_sender=sender_to_use)
            await queue.put(event)

            if interval > 0 and i % 5 == 0:
                await asyncio.sleep(interval * 5)

        # Signal workers to shut down
        for _ in range(concurrency):
            await queue.put(None)

        await queue.join()
        await asyncio.gather(*workers)

        duration = time.perf_counter() - start_time

    # Report results
    total_sent = sum(stats.values())
    rps = total_sent / duration if duration > 0 else 0.0
    latencies.sort()

    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

    print("=" * 45)
    print("SIMULATION COMPLETE")
    print(f"Duration:      {duration:.2f}s")
    print(f"Total Sent:    {total_sent} events")
    print(f"Throughput:    {rps:.1f} req/sec")
    print(f"Verdicts:      ALLOW: {stats.get('ALLOW', 0)} | FLAG: {stats.get('FLAG', 0)} | BLOCK: {stats.get('BLOCK', 0)}")
    print(f"Latencies:     p50: {p50:.2f}ms | p95: {p95:.2f}ms | p99: {p99:.2f}ms")
    print("=" * 45)


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelPulse Telecom Simulator")
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/classify", help="Target endpoint")
    parser.add_argument("--events", type=int, default=500, help="Total events to simulate")
    parser.add_argument("--concurrency", type=int, default=15, help="Concurrent workers")
    parser.add_argument("--rps", type=int, default=150, help="Target requests per second")

    args = parser.parse_args()
    asyncio.run(
        run_simulator(
            url=args.url,
            total_events=args.events,
            concurrency=args.concurrency,
            target_rps=args.rps,
        )
    )


if __name__ == "__main__":
    main()

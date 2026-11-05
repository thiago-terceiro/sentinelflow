"""High-Throughput Redis Feature Store & Velocity Counter for SentinelPulse.

Tracks sender phone-number velocity across 10s, 60s, and 1h sliding windows,
IP reputation, multi-dimensional domain/carrier prefix velocity, and carrier
risk scores using async Redis connection pooling and Redis Cluster single-slot hash tags.

Multi-Worker Local Fallback Trade-Off:
When Redis is unreachable or socket timeouts trigger the 30s circuit breaker,
the store fails open to local in-memory deques.
In a multi-worker deployment (W workers, e.g., W=4 Uvicorn workers behind a load balancer),
each worker process maintains an isolated in-memory deque.
Under uniform distribution, an attacker generating N req/s divides traffic across workers,
so each worker observes N/W req/s (effective threshold = Global Threshold / W per worker)
until Redis recovers and the circuit breaker resets.
"""

from __future__ import annotations

import collections
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from uuid import uuid4

import redis.asyncio as aioredis
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

URL_DOMAIN_PATTERN = re.compile(
    r"https?://(?:www\.)?([a-zA-Z0-9\-\.]+)", re.IGNORECASE
)


def extract_url_domain(text: str | None) -> str | None:
    """Extracts the root hostname/domain from an SMS message string."""
    if not text:
        return None
    match = URL_DOMAIN_PATTERN.search(text)
    if match:
        domain = match.group(1).lower().rstrip(".")
        return domain if len(domain) > 2 else None
    return None


def extract_sender_prefix(sender: str | None) -> str | None:
    """Extracts country + NPA prefix (e.g. +1415 or +4479) for distributed SIM farm detection."""
    if not sender:
        return None
    cleaned = sender.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+"):
        return cleaned[:6] if len(cleaned) >= 6 else cleaned
    return cleaned[:5] if len(cleaned) >= 5 else cleaned


# Carrier risk baseline mapping (Telecom CPaaS intelligence domain)
CARRIER_RISK_MAP: dict[str, float] = {
    "textnow": 0.65,
    "pinger": 0.60,
    "bandwidth.com": 0.50,
    "sinch virtual": 0.45,
    "cpaas virtual": 0.40,
    "google voice": 0.35,
    "verizon wireless": 0.05,
    "at&t mobility": 0.05,
    "t-mobile usa": 0.05,
    "vodafone": 0.08,
    "orange": 0.08,
    "o2": 0.08,
    "unknown": 0.20,
}


@dataclass(frozen=True)
class VelocityMetrics:
    """Velocity and reputation metrics for a telecom message event."""

    sender: str
    velocity_10s: int
    velocity_60s: int
    velocity_1h: int
    carrier: str
    carrier_risk: float
    ip_count_60s: int
    signals: list[str] = field(default_factory=list)
    risk_contribution: float = 0.0
    domain_count_60s: int = 0
    prefix_count_60s: int = 0
    url_domain: str | None = None


class RedisVelocityStore:
    """Async Redis feature store implementing sliding-window sorted-set velocity aggregation."""

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or settings.QUEUE_REDIS_URL
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None
        self._in_memory_sender_history: dict[str, collections.deque[float]] = (
            collections.defaultdict(collections.deque)
        )
        self._in_memory_ip_history: dict[str, collections.deque[float]] = (
            collections.defaultdict(collections.deque)
        )
        self._in_memory_domain_history: dict[str, collections.deque[float]] = (
            collections.defaultdict(collections.deque)
        )
        self._in_memory_prefix_history: dict[str, collections.deque[float]] = (
            collections.defaultdict(collections.deque)
        )
        self._circuit_cooldown_seconds: float = 30.0
        self._fallback_until: float = 0.0

    @property
    def _use_in_memory_fallback(self) -> bool:
        return time.monotonic() < self._fallback_until

    @_use_in_memory_fallback.setter
    def _use_in_memory_fallback(self, value: bool) -> None:
        if value:
            self._fallback_until = time.monotonic() + self._circuit_cooldown_seconds
        else:
            self._fallback_until = 0.0

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=50,
                socket_timeout=0.015,  # 15ms SLA budget socket timeout
                socket_connect_timeout=0.015,
                decode_responses=False,
            )
            self._client = aioredis.Redis(connection_pool=self._pool)
        return self._client

    async def close(self) -> None:
        """Gracefully closes Redis connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None

    def _lookup_carrier_risk(self, carrier: str | None) -> tuple[str, float]:
        """Resolves normalized carrier name and associated risk score."""
        if not carrier:
            return "unknown", CARRIER_RISK_MAP["unknown"]
        normalized = carrier.strip().lower()
        score = CARRIER_RISK_MAP.get(normalized, 0.20)
        return normalized, score

    def _record_in_memory(
        self,
        sender: str,
        ip: str | None,
        url_domain: str | None,
        prefix: str | None,
        now: float,
    ) -> tuple[int, int, int, int, int, int]:
        """In-memory sliding window fallback when Redis is unreachable."""
        # Clean & record sender history
        sender_deque = self._in_memory_sender_history[sender]
        while sender_deque and sender_deque[0] < now - 3600.0:
            sender_deque.popleft()
        sender_deque.append(now)

        v10s = sum(1 for ts in sender_deque if ts >= now - 10.0)
        v60s = sum(1 for ts in sender_deque if ts >= now - 60.0)
        v1h = len(sender_deque)

        # Bound memory growth under heavy continuous fallback traffic
        if len(self._in_memory_sender_history) > 10000:
            stale = [
                k
                for k, dq in self._in_memory_sender_history.items()
                if not dq or dq[-1] < now - 3600.0
            ]
            for k in stale[:2000]:
                self._in_memory_sender_history.pop(k, None)

        # Clean & record IP history
        ip_count = 0
        if ip:
            ip_deque = self._in_memory_ip_history[ip]
            while ip_deque and ip_deque[0] < now - 60.0:
                ip_deque.popleft()
            ip_deque.append(now)
            ip_count = len(ip_deque)

        # Clean & record domain history
        domain_count = 0
        if url_domain:
            domain_deque = self._in_memory_domain_history[url_domain]
            while domain_deque and domain_deque[0] < now - 60.0:
                domain_deque.popleft()
            domain_deque.append(now)
            domain_count = len(domain_deque)

        # Clean & record prefix history
        prefix_count = 0
        if prefix:
            prefix_deque = self._in_memory_prefix_history[prefix]
            while prefix_deque and prefix_deque[0] < now - 60.0:
                prefix_deque.popleft()
            prefix_deque.append(now)
            prefix_count = len(prefix_deque)

        return v10s, v60s, v1h, ip_count, domain_count, prefix_count

    async def record_and_evaluate(
        self,
        sender: str,
        ip: str | None = None,
        carrier: str | None = None,
        message: str | None = None,
        url_domain: str | None = None,
        timestamp: float | None = None,
    ) -> VelocityMetrics:
        """Records the event in sliding windows and returns velocity metrics and anomaly signals."""
        now = timestamp if timestamp is not None else time.time()
        carrier_name, carrier_risk = self._lookup_carrier_risk(carrier)
        effective_domain = url_domain or extract_url_domain(message)
        effective_prefix = extract_sender_prefix(sender)

        v10s = 1
        v60s = 1
        v1h = 1
        ip_count = 1
        domain_count = 1 if effective_domain else 0
        prefix_count = 1 if effective_prefix else 0

        if not self._use_in_memory_fallback:
            try:
                client = self._get_client()

                # Redis Cluster Single-Slot Guarantee:
                # All 3 sliding-window ZSET keys share the identical hash tag {sender_hash}.
                # Redis Cluster hashes ONLY the substring inside {...}, mathematically
                # guaranteeing identical CRC16 slot placement and 1-RTT pipelining.
                sender_hash = hashlib.sha256(sender.strip().encode()).hexdigest()[:16]
                sender_10s_key = f"pulse:vel:{{{sender_hash}}}:10s"
                sender_60s_key = f"pulse:vel:{{{sender_hash}}}:60s"
                sender_3600s_key = f"pulse:vel:{{{sender_hash}}}:3600s"

                ip_hash = hashlib.sha256(ip.strip().encode()).hexdigest()[:16] if ip else None
                ip_key = f"pulse:vel:ip:{{{ip_hash}}}:60s" if ip_hash else None

                domain_hash = (
                    hashlib.sha256(effective_domain.encode()).hexdigest()[:16]
                    if effective_domain
                    else None
                )
                domain_key = f"pulse:vel:domain:{{{domain_hash}}}:60s" if domain_hash else None

                prefix_hash = (
                    hashlib.sha256(effective_prefix.encode()).hexdigest()[:16]
                    if effective_prefix
                    else None
                )
                prefix_key = f"pulse:vel:prefix:{{{prefix_hash}}}:60s" if prefix_hash else None

                event_member = f"{uuid4().hex[:8]}:{now}".encode()

                async with client.pipeline(transaction=False) as pipe:
                    # 1. 10s sliding window
                    pipe.zremrangebyscore(sender_10s_key, 0, now - 10.0)
                    pipe.zadd(sender_10s_key, {event_member: now})
                    pipe.expire(sender_10s_key, 15)
                    pipe.zcard(sender_10s_key)

                    # 2. 60s sliding window
                    pipe.zremrangebyscore(sender_60s_key, 0, now - 60.0)
                    pipe.zadd(sender_60s_key, {event_member: now})
                    pipe.expire(sender_60s_key, 90)
                    pipe.zcard(sender_60s_key)

                    # 3. 3600s (1h) sliding window
                    pipe.zremrangebyscore(sender_3600s_key, 0, now - 3600.0)
                    pipe.zadd(sender_3600s_key, {event_member: now})
                    pipe.expire(sender_3600s_key, 3600)
                    pipe.zcard(sender_3600s_key)

                    idx_ip = -1
                    if ip_key:
                        pipe.zremrangebyscore(ip_key, 0, now - 60.0)
                        pipe.zadd(ip_key, {event_member: now})
                        pipe.expire(ip_key, 90)
                        pipe.zcard(ip_key)
                        idx_ip = 15

                    idx_domain = -1
                    if domain_key:
                        pipe.zremrangebyscore(domain_key, 0, now - 60.0)
                        pipe.zadd(domain_key, {event_member: now})
                        pipe.expire(domain_key, 90)
                        pipe.zcard(domain_key)
                        idx_domain = idx_ip + 4 if idx_ip > 0 else 15

                    idx_prefix = -1
                    if prefix_key:
                        pipe.zremrangebyscore(prefix_key, 0, now - 60.0)
                        pipe.zadd(prefix_key, {event_member: now})
                        pipe.expire(prefix_key, 90)
                        pipe.zcard(prefix_key)
                        base_idx = idx_domain if idx_domain > 0 else (idx_ip if idx_ip > 0 else 11)
                        idx_prefix = base_idx + 4

                    results = await pipe.execute()

                v10s = int(results[3])
                v60s = int(results[7])
                v1h = int(results[11])
                if idx_ip > 0 and len(results) > idx_ip:
                    ip_count = int(results[idx_ip])
                if idx_domain > 0 and len(results) > idx_domain:
                    domain_count = int(results[idx_domain])
                if idx_prefix > 0 and len(results) > idx_prefix:
                    prefix_count = int(results[idx_prefix])

            except Exception as exc:
                # Fail-open architectural policy: when Redis blips or times out, activate a
                # 30-second in-memory deque fallback cooldown. Falling open to local ML + regex
                # heuristics prevents carrier traffic drops or 2FA login code failures.
                logger.warning(
                    "Redis velocity pipeline failed (%s). Activating in-memory cooldown (%.1fs).",
                    exc,
                    self._circuit_cooldown_seconds,
                )
                self._use_in_memory_fallback = True
                v10s, v60s, v1h, ip_count, domain_count, prefix_count = self._record_in_memory(
                    sender, ip, effective_domain, effective_prefix, now
                )
        else:
            v10s, v60s, v1h, ip_count, domain_count, prefix_count = self._record_in_memory(
                sender, ip, effective_domain, effective_prefix, now
            )

        # Anomaly signal evaluation
        signals: list[str] = []
        risk_contribution = 0.0

        if v10s >= 5:
            signals.append("VELOCITY:BURST_10S")
            risk_contribution += 0.35
        elif v10s >= 3:
            signals.append("VELOCITY:MODERATE_BURST_10S")
            risk_contribution += 0.15

        if v60s >= 20:
            signals.append("VELOCITY:HIGH_RATE_60S")
            risk_contribution += 0.30
        elif v60s >= 10:
            signals.append("VELOCITY:ELEVATED_RATE_60S")
            risk_contribution += 0.15

        if v1h >= 100:
            signals.append("VELOCITY:CAMPAIGN_1H")
            risk_contribution += 0.25

        if carrier_risk >= 0.40:
            signals.append("CARRIER:HIGH_RISK_VOIP")
            risk_contribution += carrier_risk * 0.4

        if ip_count >= 30:
            signals.append("IP:HIGH_RATE_BURST")
            risk_contribution += 0.20

        # Multi-dimensional velocity signals: distributed SIM-farm domain and prefix bursts
        if domain_count >= 8:
            signals.append("VELOCITY:DOMAIN_BURST_60S")
            risk_contribution += 0.30

        if prefix_count >= 25:
            signals.append("VELOCITY:PREFIX_BURST_60S")
            risk_contribution += 0.20

        # Cap risk contribution at 0.85 (velocity alone can't be 1.0 without model confirmation)
        risk_contribution = min(0.85, risk_contribution)

        return VelocityMetrics(
            sender=sender,
            velocity_10s=v10s,
            velocity_60s=v60s,
            velocity_1h=v1h,
            carrier=carrier_name,
            carrier_risk=carrier_risk,
            ip_count_60s=ip_count,
            signals=signals,
            risk_contribution=round(risk_contribution, 3),
            domain_count_60s=domain_count,
            prefix_count_60s=prefix_count,
            url_domain=effective_domain,
        )


# Global singleton instance
_velocity_store_instance: RedisVelocityStore | None = None


def get_velocity_store() -> RedisVelocityStore:
    """Returns the singleton RedisVelocityStore instance."""
    global _velocity_store_instance
    if _velocity_store_instance is None:
        _velocity_store_instance = RedisVelocityStore()
    return _velocity_store_instance

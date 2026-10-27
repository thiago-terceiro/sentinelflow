"""High-Throughput Redis Feature Store & Velocity Counter for SentinelPulse.

Tracks sender phone-number velocity across 10s, 60s, and 1h sliding windows,
IP reputation, and carrier risk scores using async Redis connection pooling.
"""

from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass, field
from uuid import uuid4

import redis.asyncio as aioredis
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

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


class RedisVelocityStore:
    """Async Redis feature store implementing sliding-window sorted-set velocity aggregation."""

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or settings.QUEUE_REDIS_URL
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None
        self._in_memory_sender_history: dict[str, collections.deque[float]] = (
            collections.defaultdict(collections.deque)
        )
        self._in_memory_ip_history: dict[str, collections.deque[float]] = collections.defaultdict(
            collections.deque
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
        self, sender: str, ip: str | None, now: float
    ) -> tuple[int, int, int, int]:
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

        return v10s, v60s, v1h, ip_count

    async def record_and_evaluate(
        self,
        sender: str,
        ip: str | None = None,
        carrier: str | None = None,
        timestamp: float | None = None,
    ) -> VelocityMetrics:
        """Records the event in sliding windows and returns velocity metrics and anomaly signals."""
        now = timestamp if timestamp is not None else time.time()
        carrier_name, carrier_risk = self._lookup_carrier_risk(carrier)

        v10s = 1
        v60s = 1
        v1h = 1
        ip_count = 1

        if not self._use_in_memory_fallback:
            try:
                client = self._get_client()
                sender_key = f"telecom:velocity:sender:{sender}"
                ip_key = f"telecom:velocity:ip:{ip}" if ip else None
                event_member = f"{uuid4().hex[:8]}:{now}".encode()

                async with client.pipeline(transaction=True) as pipe:
                    # 1. Prune entries older than 1 hour
                    pipe.zremrangebyscore(sender_key, 0, now - 3600.0)
                    # 2. Add current event
                    pipe.zadd(sender_key, {event_member: now})
                    pipe.expire(sender_key, 3600)
                    # 3. Query sliding window counts
                    pipe.zcount(sender_key, now - 10.0, now + 1.0)
                    pipe.zcount(sender_key, now - 60.0, now + 1.0)
                    pipe.zcard(sender_key)

                    if ip_key:
                        pipe.zremrangebyscore(ip_key, 0, now - 60.0)
                        pipe.zadd(ip_key, {event_member: now})
                        pipe.expire(ip_key, 60)
                        pipe.zcard(ip_key)

                    results = await pipe.execute()

                v10s = int(results[3])
                v60s = int(results[4])
                v1h = int(results[5])
                if ip_key and len(results) >= 10:
                    ip_count = int(results[9])

            except Exception as exc:
                logger.warning(
                    "Redis velocity pipeline failed (%s). Activating in-memory cooldown (%.1fs).",
                    exc,
                    self._circuit_cooldown_seconds,
                )
                self._use_in_memory_fallback = True
                v10s, v60s, v1h, ip_count = self._record_in_memory(sender, ip, now)
        else:
            v10s, v60s, v1h, ip_count = self._record_in_memory(sender, ip, now)

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
        )


# Global singleton instance
_velocity_store_instance: RedisVelocityStore | None = None


def get_velocity_store() -> RedisVelocityStore:
    """Returns the singleton RedisVelocityStore instance."""
    global _velocity_store_instance
    if _velocity_store_instance is None:
        _velocity_store_instance = RedisVelocityStore()
    return _velocity_store_instance

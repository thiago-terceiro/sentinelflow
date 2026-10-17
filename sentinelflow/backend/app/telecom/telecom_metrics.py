"""Prometheus Telemetry Metrics and Rolling Dashboard Aggregations for SentinelPulse."""

from __future__ import annotations

import collections
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Prometheus Metrics
TELECOM_REQUESTS_TOTAL = Counter(
    "telecom_requests_total",
    "Total number of telecom classification requests",
    ["verdict"],
)

TELECOM_LATENCY_SECONDS = Histogram(
    "telecom_latency_seconds",
    "End-to-end classification latency in seconds",
    buckets=[0.001, 0.002, 0.005, 0.010, 0.015, 0.020, 0.025, 0.050, 0.100, 0.250],
)

TELECOM_ONNX_INFERENCE_SECONDS = Histogram(
    "telecom_onnx_inference_seconds",
    "ONNX Runtime inference latency in seconds",
    buckets=[0.00005, 0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.010],
)

TELECOM_CACHE_HITS = Counter(
    "telecom_cache_hits_total",
    "Total cache / reputation hits in velocity store",
)

TELECOM_CACHE_MISSES = Counter(
    "telecom_cache_misses_total",
    "Total cache / reputation misses in velocity store",
)


@dataclass
class InspectionEventRecord:
    id: str
    timestamp: float
    sender: str
    recipient: str
    message: str
    verdict: str
    fraud_score: float
    latency_ms: float
    signals: list[str]
    carrier: str


class TelecomMetricsTracker:
    """Maintains in-memory rolling statistics for the live dashboard and Prometheus telemetry."""

    def __init__(self, max_history: int = 2000) -> None:
        self.max_history = max_history
        self._latencies: collections.deque[float] = collections.deque(maxlen=max_history)
        self._timestamps: collections.deque[float] = collections.deque(maxlen=max_history)
        self._recent_events: collections.deque[InspectionEventRecord] = collections.deque(maxlen=50)
        self._counts: dict[str, int] = {"ALLOW": 0, "BLOCK": 0, "FLAG": 0}
        self._total_requests: int = 0

    def record_event(
        self,
        event_id: str,
        sender: str,
        recipient: str,
        message: str,
        verdict: str,
        fraud_score: float,
        latency_ms: float,
        signals: list[str],
        carrier: str,
        onnx_latency_ms: float = 0.0,
    ) -> None:
        """Records a classification event into Prometheus and local rolling buffers."""
        now = time.time()
        self._total_requests += 1
        self._counts[verdict] = self._counts.get(verdict, 0) + 1
        self._latencies.append(latency_ms)
        self._timestamps.append(now)

        # Update Prometheus metrics
        TELECOM_REQUESTS_TOTAL.labels(verdict=verdict).inc()
        TELECOM_LATENCY_SECONDS.observe(latency_ms / 1000.0)
        if onnx_latency_ms > 0:
            TELECOM_ONNX_INFERENCE_SECONDS.observe(onnx_latency_ms / 1000.0)

        # Store for rolling dashboard feed
        self._recent_events.appendleft(
            InspectionEventRecord(
                id=event_id,
                timestamp=now,
                sender=sender,
                recipient=recipient,
                message=message,
                verdict=verdict,
                fraud_score=fraud_score,
                latency_ms=latency_ms,
                signals=signals,
                carrier=carrier,
            )
        )

    def get_summary(self) -> dict[str, Any]:
        """Calculates real-time stats: throughput (EPS), p50/p95/p99 latency, fraud rates."""
        now = time.time()

        # Calculate throughput (events in the last 5 seconds)
        recent_count = sum(1 for ts in self._timestamps if ts >= now - 5.0)
        throughput_eps = round(recent_count / 5.0, 1)

        # Calculate latency percentiles
        if self._latencies:
            latencies_array = np.array(self._latencies)
            p50 = round(float(np.percentile(latencies_array, 50)), 2)
            p90 = round(float(np.percentile(latencies_array, 90)), 2)
            p95 = round(float(np.percentile(latencies_array, 95)), 2)
            p99 = round(float(np.percentile(latencies_array, 99)), 2)
            avg = round(float(np.mean(latencies_array)), 2)
        else:
            p50 = p90 = p95 = p99 = avg = 0.0

        total = max(1, self._total_requests)
        blocked = self._counts.get("BLOCK", 0)
        flagged = self._counts.get("FLAG", 0)
        allowed = self._counts.get("ALLOW", 0)

        fraud_rate = round((blocked + flagged) / total * 100.0, 2)

        return {
            "total_requests": self._total_requests,
            "throughput_eps": throughput_eps,
            "verdicts": {
                "allow": allowed,
                "flag": flagged,
                "block": blocked,
            },
            "fraud_rate_pct": fraud_rate,
            "latency": {
                "p50_ms": p50,
                "p90_ms": p90,
                "p95_ms": p95,
                "p99_ms": p99,
                "avg_ms": avg,
            },
            "recent_feed": [
                {
                    "id": ev.id,
                    "timestamp": ev.timestamp,
                    "sender": ev.sender,
                    "recipient": ev.recipient,
                    "message": ev.message,
                    "verdict": ev.verdict,
                    "fraud_score": ev.fraud_score,
                    "latency_ms": ev.latency_ms,
                    "signals": ev.signals,
                    "carrier": ev.carrier,
                }
                for ev in list(self._recent_events)[:30]
            ],
        }


# Global metrics tracker singleton
metrics_tracker = TelecomMetricsTracker()


def get_metrics_tracker() -> TelecomMetricsTracker:
    return metrics_tracker


def export_prometheus_metrics() -> tuple[bytes, str]:
    """Generates Prometheus format bytes and the correct Content-Type."""
    return generate_latest(), CONTENT_TYPE_LATEST

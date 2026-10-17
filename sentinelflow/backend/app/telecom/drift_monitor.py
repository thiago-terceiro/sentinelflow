"""MLOps Data Drift Monitor for SentinelPulse.

Performs online distribution drift analysis on production telecom traffic using
Kolmogorov-Smirnov (KS) two-sample test on message length and Population Stability
Index (PSI) on fraud score distributions against the training baseline.
"""

from __future__ import annotations

import collections
import logging
from dataclasses import dataclass

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# Baseline training distribution reference (pre-computed from training dataset)
BASELINE_LENGTHS: list[int] = [
    68,
    62,
    79,
    87,
    85,
    96,
    43,
    86,
    75,
    78,
    71,
    64,
    76,
    52,
    75,
    37,
    84,
    69,
    88,
    70,
    77,
    54,
    87,
    72,
    85,
    79,
    74,
    68,
    62,
    45,
    60,
    81,
    80,
    83,
    67,
    68,
    56,
    74,
    63,
    60,
    115,
    114,
    126,
    128,
    123,
    113,
    118,
    115,
    117,
    124,
    110,
    110,
    110,
    118,
    110,
    119,
    110,
    114,
    116,
    108,
    110,
    110,
    115,
    114,
    114,
    117,
    111,
    109,
    111,
    112,
    112,
    110,
    114,
    116,
    115,
    114,
    113,
    115,
    112,
    110,
]

BASELINE_FRAUD_SCORES: list[float] = [
    0.05,
    0.08,
    0.12,
    0.04,
    0.06,
    0.15,
    0.09,
    0.07,
    0.11,
    0.13,
    0.05,
    0.04,
    0.08,
    0.06,
    0.10,
    0.07,
    0.09,
    0.12,
    0.08,
    0.05,
    0.11,
    0.07,
    0.09,
    0.06,
    0.08,
    0.10,
    0.85,
    0.92,
    0.78,
    0.88,
    0.95,
    0.89,
    0.82,
    0.91,
    0.87,
    0.94,
    0.79,
    0.86,
    0.93,
    0.90,
    0.81,
    0.89,
    0.92,
    0.84,
    0.96,
    0.88,
    0.91,
    0.85,
    0.93,
    0.87,
    0.90,
    0.82,
]


@dataclass(frozen=True)
class DriftReport:
    """Summary of statistical drift tests."""

    status: str  # "HEALTHY" | "MODERATE_DRIFT" | "CRITICAL_DRIFT"
    ks_statistic: float
    ks_p_value: float
    ks_drift_detected: bool
    psi_score: float
    psi_status: str
    sample_count: int
    baseline_sample_count: int
    mean_live_length: float
    mean_baseline_length: float
    recommendation: str


def calculate_psi(baseline: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Calculates Population Stability Index (PSI) across binned distributions."""
    if len(current) < 10 or len(baseline) < 10:
        return 0.0

    # Ensure fixed bin boundaries [0.0 to 1.0]
    bin_edges = np.linspace(0.0, 1.0, bins + 1)

    baseline_counts, _ = np.histogram(baseline, bins=bin_edges)
    current_counts, _ = np.histogram(current, bins=bin_edges)

    # Convert to proportions and apply Laplace smoothing to avoid division by zero
    eps = 1e-4
    b_prop = (baseline_counts + eps) / (len(baseline) + eps * bins)
    c_prop = (current_counts + eps) / (len(current) + eps * bins)

    psi_val = np.sum((c_prop - b_prop) * np.log(c_prop / b_prop))
    return float(max(0.0, psi_val))


class DataDriftMonitor:
    """Collects streaming production message telemetry and computes distribution drift."""

    def __init__(self, window_size: int = 500) -> None:
        self.window_size = window_size
        self._message_lengths: collections.deque[int] = collections.deque(maxlen=window_size)
        self._fraud_scores: collections.deque[float] = collections.deque(maxlen=window_size)
        self._baseline_lengths = np.array(BASELINE_LENGTHS, dtype=float)
        self._baseline_scores = np.array(BASELINE_FRAUD_SCORES, dtype=float)

    def record_observation(self, message: str, fraud_score: float) -> None:
        """Records an incoming message's length and resulting fraud score."""
        self._message_lengths.append(len(message))
        self._fraud_scores.append(float(fraud_score))

    def evaluate_drift(self) -> DriftReport:
        """Runs Kolmogorov-Smirnov test and Population Stability Index against baseline."""
        if len(self._message_lengths) < 15:
            return DriftReport(
                status="HEALTHY",
                ks_statistic=0.0,
                ks_p_value=1.0,
                ks_drift_detected=False,
                psi_score=0.0,
                psi_status="STABLE",
                sample_count=len(self._message_lengths),
                baseline_sample_count=len(self._baseline_lengths),
                mean_live_length=(
                    float(np.mean(self._message_lengths)) if self._message_lengths else 0.0
                ),
                mean_baseline_length=round(float(np.mean(self._baseline_lengths)), 1),
                recommendation=(
                    "Collecting initial production baseline sample (minimum 15 requests required)."
                ),
            )

        live_lengths = np.array(self._message_lengths, dtype=float)
        live_scores = np.array(self._fraud_scores, dtype=float)

        # 1. Two-sample Kolmogorov-Smirnov test on message length
        ks_res = stats.ks_2samp(self._baseline_lengths, live_lengths)
        ks_stat = float(ks_res.statistic)
        ks_p = float(ks_res.pvalue)
        ks_drift = ks_p < 0.05  # Reject null hypothesis of identical distributions

        # 2. Population Stability Index (PSI) on fraud scores
        psi_val = calculate_psi(self._baseline_scores, live_scores)
        if psi_val < 0.10:
            psi_status = "STABLE"
        elif psi_val < 0.25:
            psi_status = "MODERATE_SHIFT"
        else:
            psi_status = "CRITICAL_DRIFT"

        # 3. Overall status determination
        if psi_status == "CRITICAL_DRIFT" or (ks_drift and psi_status == "MODERATE_SHIFT"):
            status = "CRITICAL_DRIFT"
            recommendation = (
                "Alert: Significant statistical drift detected in incoming message "
                "distribution or scoring. Trigger retrain pipeline or inspect upstream traffic."
            )
        elif psi_status == "MODERATE_SHIFT" or ks_drift:
            status = "MODERATE_DRIFT"
            recommendation = (
                "Notice: Moderate distribution divergence detected. "
                "Continue monitoring and log sample for evaluation."
            )
        else:
            status = "HEALTHY"
            recommendation = (
                "Traffic distribution is aligned with baseline training data. Operating stably."
            )

        return DriftReport(
            status=status,
            ks_statistic=round(ks_stat, 4),
            ks_p_value=round(ks_p, 4),
            ks_drift_detected=ks_drift,
            psi_score=round(psi_val, 4),
            psi_status=psi_status,
            sample_count=len(self._message_lengths),
            baseline_sample_count=len(self._baseline_lengths),
            mean_live_length=round(float(np.mean(live_lengths)), 1),
            mean_baseline_length=round(float(np.mean(self._baseline_lengths)), 1),
            recommendation=recommendation,
        )


# Global drift monitor singleton
drift_monitor = DataDriftMonitor()


def get_drift_monitor() -> DataDriftMonitor:
    return drift_monitor

"""Low-Latency ML & Heuristic Inference Engine for SentinelPulse.

Precedes ML classification with compiled regex heuristic rules and evaluates
optimized ONNX Runtime CPU models with sub-millisecond execution times.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

# Pre-compiled high-confidence smishing / fraud heuristic rules
HEURISTIC_RULES: list[tuple[str, re.Pattern[str], float]] = [
    (
        "RULE:HIGH_RISK_SHORTLINK",
        re.compile(
            r"https?://(?:bit\.ly|tinyurl\.com|t\.co|is\.gd|cutt\.ly|rb\.gy)/[a-zA-Z0-9_\-]+",
            re.IGNORECASE,
        ),
        0.55,
    ),
    (
        "RULE:SUSPICIOUS_TLD",
        re.compile(
            r"https?://[a-zA-Z0-9.\-]+\.(?:xyz|top|cc|ru|club|info|biz|site|online|me)/[^\s]*",
            re.IGNORECASE,
        ),
        0.65,
    ),
    (
        "RULE:URGENT_ACCOUNT_LOCKOUT",
        re.compile(
            r"\b(?:urgent|immediately|suspended|locked|temporarily disabled|"
            r"unauthorized login|compromised)\b.*\b(?:verify|restore|reactivate|unlock)\b",
            re.IGNORECASE,
        ),
        0.70,
    ),
    (
        "RULE:DELIVERY_FEE_SCAM",
        re.compile(
            r"\b(?:usps|fedex|ups|dhl|parcel|package)\b.*"
            r"\b(?:redelivery|customs|fee|unpaid|incomplete address)\b",
            re.IGNORECASE,
        ),
        0.65,
    ),
    (
        "RULE:TAX_ARREST_THREAT",
        re.compile(
            r"\b(?:irs|arrest warrant|delinquent taxes|lawsuit|federal agent|process server)\b",
            re.IGNORECASE,
        ),
        0.80,
    ),
    (
        "RULE:CRYPTO_OR_GIVEAWAY_PROMISE",
        re.compile(
            r"\b(?:guaranteed return|crypto signal|free bitcoin|claim \$?\d+00|"
            r"gift card winner|cash app giveaway)\b",
            re.IGNORECASE,
        ),
        0.75,
    ),
    (
        "RULE:UNPAID_TOLL_INVOICE",
        re.compile(
            r"\b(?:toll|sunpass|ezpass|turnpike)\b.*\b(?:unpaid|late fee|invoice)\b",
            re.IGNORECASE,
        ),
        0.70,
    ),
]


@dataclass(frozen=True)
class InferenceResult:
    """Structured decision output from the SentinelPulse inference gateway."""

    verdict: str  # "ALLOW" | "BLOCK" | "FLAG"
    fraud_score: float  # [0.0, 1.0]
    latency_ms: float
    signals: list[str] = field(default_factory=list)
    model_version: str = "1.0.0"
    onnx_probability: float = 0.0
    heuristic_score: float = 0.0


class OnnxInferenceEngine:
    """Manages ONNX Runtime CPU session and evaluates SMS text messages."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        if model_path is None:
            # Default to bundled model in app/telecom/models
            current_dir = Path(__file__).parent
            model_path = current_dir / "models" / "sms_fraud_model.onnx"

        self.model_path = Path(model_path)
        self.session: ort.InferenceSession | None = None
        self._init_session()

    def _init_session(self) -> None:
        """Initializes optimized ONNX Runtime CPU session."""
        if not self.model_path.exists():
            logger.warning(
                "ONNX model file not found at %s. Running in heuristic-only fallback mode.",
                self.model_path,
            )
            return

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # 1 thread per session maximizes server throughput under concurrent workers
        opts.intra_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        try:
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            logger.info("Initialized ONNX Runtime CPU session from %s", self.model_path)
        except Exception as err:
            logger.error("Failed to load ONNX model from %s: %s", self.model_path, err)

            self.session = None

    def evaluate_heuristics(self, text: str) -> tuple[float, list[str]]:
        """Fast regex pattern matching preceding the ML model."""
        signals: list[str] = []
        max_heuristic = 0.0

        for rule_name, pattern, score in HEURISTIC_RULES:
            if pattern.search(text):
                signals.append(rule_name)
                if score > max_heuristic:
                    max_heuristic = score

        # Compound rule escalation: multiple distinct high-risk heuristic triggers
        if len(signals) >= 2:
            max_heuristic = min(0.95, max_heuristic + 0.12)
            signals.append("HEURISTIC:COMPOUND_SIGNALS")

        return max_heuristic, signals

    def predict(self, text: str) -> InferenceResult:
        """Synchronously classifies an SMS text message with sub-millisecond execution."""
        t_start = time.perf_counter()

        # 1. Fast regex rule engine
        heuristic_score, signals = self.evaluate_heuristics(text)

        # 2. ONNX Runtime model inference
        onnx_prob = 0.0
        if self.session is not None:
            try:
                # String input tensor with shape [1, 1]
                input_tensor = np.array([[text]], dtype=object)
                raw_outputs = self.session.run(None, {"text": input_tensor})
                # Output structure: [label_array, probabilities_map_list]
                prob_map = raw_outputs[1][0]  # {0: p_legit, 1: p_fraud}
                onnx_prob = float(prob_map.get(1, 0.0))
            except Exception as err:
                logger.error("ONNX inference failed: %s", err)
                signals.append("ENGINE:ONNX_FALLBACK")
                onnx_prob = heuristic_score
        else:
            signals.append("ENGINE:HEURISTIC_ONLY")
            onnx_prob = heuristic_score

        # 3. Composite score calculation
        # If strong heuristic triggers, model cannot lower score below heuristic baseline
        fraud_score = max(heuristic_score, onnx_prob)

        # Add signal flags based on score thresholds
        if onnx_prob >= 0.75:
            signals.append("ML:HIGH_FRAUD_PROBABILITY")
        elif onnx_prob >= 0.40:
            signals.append("ML:ELEVATED_FRAUD_PROBABILITY")
        else:
            signals.append("ML:BENIGN_CLASSIFICATION")

        # 4. Final verdict determination
        if fraud_score >= 0.75:
            verdict = "BLOCK"
        elif fraud_score >= 0.40:
            verdict = "FLAG"
        else:
            verdict = "ALLOW"

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000.0

        return InferenceResult(
            verdict=verdict,
            fraud_score=round(fraud_score, 4),
            latency_ms=round(latency_ms, 3),
            signals=signals,
            model_version="1.0.0",
            onnx_probability=round(onnx_prob, 4),
            heuristic_score=round(heuristic_score, 4),
        )


# Global singleton instance
_engine_instance: OnnxInferenceEngine | None = None


def get_inference_engine() -> OnnxInferenceEngine:
    """Returns the singleton OnnxInferenceEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OnnxInferenceEngine()
    return _engine_instance

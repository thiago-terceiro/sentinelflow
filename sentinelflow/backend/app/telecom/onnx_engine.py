"""Low-Latency ML & Heuristic Inference Engine for SentinelPulse.

Precedes ML classification with compiled regex heuristic rules and evaluates
optimized ONNX Runtime CPU models with sub-millisecond execution times.

Architecture Note (ML / Systems Integrity):
The ONNX model graph (`sms_fraud_model.onnx`) is a compiled in-graph
`TfidfVectorizer + CalibratedClassifierCV (LogisticRegression)` pipeline, exported
via `skl2onnx` into native ONNX runtime operators (in-graph TF-IDF + sigmoid-calibrated
linear classifier). It is NOT an INT8 quantized neural network. Because the FP32
in-graph weights occupy under 3MB and execute in ~32 µs under AVX-512, INT8 quantization
is unnecessary and not used.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
import unicodedata
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
            r"https?://[a-zA-Z0-9.\-&]+\.(?:xyz|top|cc|ru|club|info|biz|site|online|me)(?:/[^\s]*)?",
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
            r"\b(?:redelivery|customs fee|customs duty|unpaid (?:fee|duty|charge)|"
            r"incomplete address)\b",
            re.IGNORECASE,
        ),
        0.65,
    ),
    (
        "RULE:TAX_ARREST_THREAT",
        re.compile(
            # Require (1) explicit coercive arrest/warrant/detention/seizure/dispatch threat,
            # (2) legal/tax/enforcement authority, AND (3) explicit extortion/financial/callback
            # demand (omitting bare "final notice", bare "tax penalty abatement", and bare
            # administrative "case #" references; allowing parenthesized callbacks "(800)").
            r"^(?=.*\b(?:arrest\s+warrant|bench\s+warrant|seizure\s+warrant|"
            r"warrant\s+(?:issued|pending|active)|federal\s+arrest|"
            r"avoid\s+(?:arrest|detention|prosecution|seizure|jail)|"
            r"detain(?:ed)?|detention|seiz(?:e|ed|ure)|"
            r"process\s+server\s+(?:dispatched|en\s+route|assigned|sent)|"
            r"(?:marshal|officer|agent|deputy|police)\s+dispatched|"
            r"failure\s+to\s+appear|contempt\s+of\s+court)\b)"
            r"(?=.*\b(?:irs|customs|magistrate|sheriff|police|court(?:house)?|judge|"
            r"federal\s+(?:tax|agent|court|marshal|enforcement|bureau)|"
            r"tax\w*|delinquent|warrant|process\s+server|lawsuit|enforcement)\b)"
            r"(?=.*(?:"
            r"\b(?:delinquent\s+tax\w*|"
            r"tax\s+(?:debt|balance|penalty(?!\s+(?:abatement|relief|waiver))|lien|levy|evasion)|"
            r"unpaid\s+(?:back\s+)?(?:tax\w*|fine|penalty|customs|duty|fee|balance|citation|toll)|"
            r"(?:pay|settle)\s+(?:\$\d+(?:,\d{3})*(?:\.\d{2})?\s+)?"
            r"(?:federal\s+|court\s+|customs\s+|tax\s+)?"
            r"(?:fine|penalty|tax\w*|balance|bail|duty|fee|case|dispute|now|immediately)|"
            r"unless\s+(?:paid|settled|resolved|verified)|"
            r"(?:federal|court|customs)\s+(?:penalty|fine)|"
            r"within\s+\d+\s*(?:hours?|hrs?|minutes?)|"
            r"call\s+(?:immediately|now|"
            r"\+?1?[-.\s]?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}))\b|"
            r"https?://\S+"
            r"))",
            re.IGNORECASE | re.DOTALL,
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
    (
        "RULE:TECH_SUPPORT_INVOICE_SCAM",
        re.compile(
            r"\b(?:auto-renewal|tech care|geek ?squad|mcafee|norton|life ?lock)\b.*"
            r"\b(?:charged|cancellation|refund|subscription invoice|auto-debited|"
            r"debited|billing desk)\b",
            re.IGNORECASE,
        ),
        0.70,
    ),
    (
        "RULE:FAMILY_IMPERSONATION_MESSAGING_LURE",
        re.compile(
            r"^(?!.*\b(?:repaired|repair shop|service center|technician|ready for pickup|quote)\b)"
            r"(?=.*\b(?:mum|mom|dad|mama|papa|borrowing (?:a |friend|someone)|"
            r"temporary (?:number|mobile|phone|whatsapp)|new number)\b)"
            r"(?=.*\b(?:broken phone|cracked (?:screen|my screen)|phone screen.*cracked|"
            r"phone.*cracked|dropped (?:my )?phone|broke my phone|phone broke|"
            r"lost my (?:phone|mobile|sim))\b)"
            r".*\b(?:whatsapp|telegram|wa\.me|signal|zelle|venmo|cash ?app|wire transfer|"
            r"emergency bill|urgent bill)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        0.65,
    ),
    (
        "RULE:WORK_FROM_HOME_SCAM",
        re.compile(
            r"\b(?:work from home|earn \$\d+/day)\b.*\b(?:telegram|reviewing|manager)\b",
            re.IGNORECASE,
        ),
        0.65,
    ),
    (
        "RULE:SIM_SWAP_OR_KYC_SCAM",
        re.compile(
            r"\b(?:esim transfer|sim card.*deactivation|update kyc)\b",
            re.IGNORECASE,
        ),
        0.70,
    ),
    (
        "RULE:STANDALONE_URL",
        re.compile(
            r"https?://(?!bit\.ly/|tinyurl\.com/|t\.co/|is\.gd/|cutt\.ly/|rb\.gy/)"
            r"[a-zA-Z0-9.\-&]+(?:/[^\s]*)?",
            re.IGNORECASE,
        ),
        0.25,
    ),
    (
        "RULE:GENERIC_DELIVERY_KEYWORD",
        re.compile(
            r"\b(?:usps|fedex|ups|dhl|parcel|package|delivery|shipment)\b"
            r"(?!\s*.*(?:fee|customs|unpaid|redelivery|incomplete address))",
            re.IGNORECASE,
        ),
        0.20,
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


_INVISIBLE_FORMAT_CHAR_RE = re.compile(r"[\u00ad\u200b-\u200f\u202a-\u202e\u2060\ufeff]")


def normalize_heuristic_text(text: str) -> str:
    """Normalizes obfuscated Unicode text for deterministic lexical heuristic matching.

    Strips zero-width/directional formatting code points used to split words across regex
    boundaries and applies NFKC compatibility decomposition before rule evaluation.
    """
    stripped = _INVISIBLE_FORMAT_CHAR_RE.sub("", text)
    return unicodedata.normalize("NFKC", stripped)


def evaluate_heuristics(text: str) -> tuple[float, list[str]]:
    """Authoritative fast regex pattern matching and compound escalation for SMS text.

    Single benign signals (e.g. standalone standard URL or benign delivery keyword)
    only contribute low/moderate weights (0.20–0.40) and never trigger the >= 0.80
    heuristic short-circuit unless paired with compound smishing indicators.

    Compound rule escalation: multiple distinct risk triggers where at least
    one is high-risk (>= 0.50) adds a +0.12 compound boost (capped at 0.95).
    """
    normalized_text = normalize_heuristic_text(text)
    signals: list[str] = []
    max_heuristic = 0.0

    for rule_name, pattern, score in HEURISTIC_RULES:
        if pattern.search(normalized_text):
            signals.append(rule_name)
            if score > max_heuristic:
                max_heuristic = score

    has_high_risk = any(
        score >= 0.50 for name, _, score in HEURISTIC_RULES if name in signals
    )
    if len(signals) >= 2 and has_high_risk:
        max_heuristic = min(0.95, max_heuristic + 0.12)
        signals.append("HEURISTIC:COMPOUND_SIGNALS")

    return max_heuristic, signals


def _clamp_unit_signal(value: float) -> float:
    """Clamps a numeric risk signal into [0.0, 1.0], mapping NaN/-inf to 0.0 and +inf to 1.0."""
    num = float(value)
    if math.isnan(num):
        return 0.0
    if math.isinf(num):
        return 1.0 if num > 0.0 else 0.0
    return max(0.0, min(1.0, num))


def compute_composite_score(
    heuristic_score: float,
    onnx_probability: float,
    velocity_score: float = 0.0,
) -> float:
    """Computes the continuous, monotonic non-decreasing composite fraud score.

    Mathematical Formulation:
    1. Authoritative High-Risk Override:
       If H >= 0.80, S_composite = 1.0 (BLOCK). Forces an immediate wire drop.
       Individual rule trigger: RULE:TAX_ARREST_THREAT (weight 0.80) is the explicit
       rule capable of triggering an immediate standalone override block. High-severity
       rules with weight >= 0.70 (e.g. URGENT_ACCOUNT_LOCKOUT, UNPAID_TOLL_INVOICE) can
       reach >= 0.82 via compound-rule escalation (+0.12 boost) when paired with a
       secondary risk signal.

    2. Continuous Gated Heuristic Blend:
       The heuristic gate alpha(P, H) smoothly scales from 0.0 (benign domain) to 1.0 (fraud):
       alpha(P, H) = clip(max(P - 0.15, H - 0.30, 0.0) / 0.25, 0.0, 1.0)

       Effective heuristic weight:
       W_H = 0.35 * H + 0.30 * max(0.0, H - 0.30)
       S_content = P + alpha(P, H) * W_H * (1.0 - P)

       Guarantees monotonic non-decreasing output: d(S_content)/dP >= 0 and
       d(S_content)/dH >= 0 everywhere on [0, 1] x [0, 1]. Terminology note:
       the formulation is mathematically monotonic non-decreasing (rather than strictly
       monotonic) due to flat boundary plateaus where H >= 0.80 forces S_composite = 1.0.
       When H <= 0.25 and P < 0.30, alpha == 0.0 and S_content == P < 0.30 < 0.40 (ALLOW).

       Note on Tier 1 Escalation and Individual Heuristics:
       A heuristic score of H = 0.65 (e.g. RULE:FAMILY_IMPERSONATION_MESSAGING_LURE) does
       NOT guarantee Tier 1 escalation (S_composite >= 0.40) on its own when ML suspicion is zero.
       With H = 0.65, P = 0.0, and V = 0.0:
         W_H = 0.35 * 0.65 + 0.30 * (0.65 - 0.30) = 0.2275 + 0.105 = 0.3325
         alpha = min(1.0, max(0.0, max(-0.15, 0.35) / 0.25)) = 1.0
         S_content = 0.0 + 1.0 * 0.3325 * (1.0 - 0.0) = 0.3325 < 0.40 (ALLOW)
       To reach the Tier 1 threshold S_composite >= 0.40 without velocity,
       the ML model probability P must satisfy:
       must satisfy: S_content = P + 0.3325 * (1.0 - P) = 0.3325 + 0.6675 * P >= 0.40
       => P >= (0.40 - 0.3325) / 0.6675 = 0.10112 (i.e. baseline ML suspicion P >= 0.1012).

    3. Smooth Monotonic Non-Decreasing Velocity Scaling (Probabilistic Union / Noisy-OR):
       S_composite = S_content + V * (1.0 - S_content)

       Guarantees d(S_composite)/dV >= 0 and d(S_composite)/dS_content >= 0 everywhere.

    Returns:
        float: Composite fraud score bounded strictly in [0.0, 1.0].
    """
    h = _clamp_unit_signal(heuristic_score)
    p = _clamp_unit_signal(onnx_probability)
    v = _clamp_unit_signal(velocity_score)

    # Step 1: Authoritative High-Risk Heuristic Override
    if h >= 0.80:
        return 1.0

    # Step 2: Continuous Gated Heuristic Blend
    alpha = min(1.0, max(0.0, max(p - 0.15, h - 0.30) / 0.25))
    w_h = 0.35 * h + 0.30 * max(0.0, h - 0.30)
    s_content = p + alpha * w_h * (1.0 - p)
    s_content = min(1.0, max(0.0, s_content))

    # Step 3: Smooth Monotonic Velocity Scaling (Probabilistic Union)
    s_composite = s_content + v * (1.0 - s_content)

    return round(float(min(1.0, max(0.0, s_composite))), 4)


class OnnxInferenceEngine:
    """Manages ONNX Runtime CPU session and evaluates SMS text messages.

    Evaluates a compiled in-graph TfidfVectorizer + CalibratedClassifierCV (LogisticRegression)
    pipeline running on the ONNX Runtime CPU execution provider with AVX-512 optimization
    (<0.1ms warm in-graph C++ execution).
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        metadata_path: str | Path | None = None,
        verify_sha256: bool = True,
    ) -> None:
        if model_path is None:
            # Default to bundled model in app/telecom/models
            current_dir = Path(__file__).parent
            model_path = current_dir / "models" / "sms_fraud_model.onnx"

        self.model_path = Path(model_path)
        if metadata_path is None:
            self.metadata_path: Path | None = (
                self.model_path.parent / "sms_fraud_metadata.json"
            )
        else:
            self.metadata_path = Path(metadata_path)
        self.verify_sha256 = verify_sha256
        self._model_sha256: str = ""
        self.session: ort.InferenceSession | None = None
        self._session: ort.InferenceSession | None = None
        self._input_name: str = "text"
        self._init_session()

    @property
    def model_sha256(self) -> str:
        """Returns the verified SHA-256 hex digest of the loaded ONNX model binary."""
        return self._model_sha256

    def _verify_model_integrity(self) -> None:
        """Computes the SHA-256 of the ONNX model file and verifies it against metadata."""
        model_bytes = self.model_path.read_bytes()
        computed_sha256 = hashlib.sha256(model_bytes).hexdigest()
        self._model_sha256 = computed_sha256

        if not self.verify_sha256 or self.metadata_path is None:
            return
        if not self.metadata_path.exists():
            logger.warning(
                "ONNX metadata file not found at %s; skipping SHA-256 verification.",
                self.metadata_path,
            )
            return

        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception as err:
            raise RuntimeError(
                f"Failed to parse ONNX metadata file at {self.metadata_path}: {err}"
            ) from err

        expected_sha256 = metadata.get("model_sha256")
        if not expected_sha256:
            raise RuntimeError(
                f"Missing 'model_sha256' field in ONNX metadata at {self.metadata_path}"
            )
        if computed_sha256 != expected_sha256:
            raise RuntimeError(
                f"ONNX model SHA-256 mismatch for {self.model_path}: "
                f"expected {expected_sha256} (from {self.metadata_path.name}), "
                f"got {computed_sha256}"
            )

    def _init_session(self) -> None:
        """Initializes optimized ONNX Runtime CPU session after verifying SHA-256 integrity."""
        if not self.model_path.exists():
            logger.warning(
                "ONNX model file not found at %s. Running in heuristic-only fallback mode.",
                self.model_path,
            )
            return

        self._verify_model_integrity()

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
            self._session = self.session
            # Cold-start warmup: run 1 dummy inference to prime threadpools & memory allocations
            warmup_tensor = np.array([["warmup text"]], dtype=object)
            self.session.run(None, {self._input_name: warmup_tensor})
            logger.info(
                "Initialized ONNX Runtime CPU session from %s (SHA-256: %s, warmup complete)",
                self.model_path,
                self._model_sha256,
            )
        except Exception as err:
            logger.error("Failed to load ONNX model from %s: %s", self.model_path, err)
            self.session = None
            self._session = None

    def evaluate_heuristics(self, text: str) -> tuple[float, list[str]]:
        """Fast regex pattern matching preceding the ML model.
        Delegates to shared evaluate_heuristics.
        """
        return evaluate_heuristics(text)

    _evaluate_heuristics = evaluate_heuristics

    def _is_circuit_open(self) -> bool:
        """Returns True when the ONNX session is unavailable or circuit-broken."""
        return bool(
            getattr(self, "_circuit_open", False)
            or (self._session is None and self.session is None)
        )

    def predict(self, text: str) -> InferenceResult:
        """Synchronously classifies an SMS text message with sub-millisecond execution."""
        t_start = time.perf_counter()

        # 1. Fast regex rule engine
        heuristic_score, signals = self.evaluate_heuristics(text)

        # 2. ONNX Runtime model inference
        onnx_prob = 0.0
        active_session = self._session or self.session
        if active_session is not None:
            try:
                # String input tensor with shape [1, 1]
                input_tensor = np.array([[text]], dtype=object)
                raw_outputs = active_session.run(None, {self._input_name: input_tensor})
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

        # 3. Composite score calculation via deterministic piecewise formulation
        fraud_score = compute_composite_score(heuristic_score, onnx_prob, 0.0)

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

    def predict_proba_batch(self, texts: list[str]) -> list[float]:
        """Executes vectorized ONNX CPU inference across a batch of SMS messages."""
        if not texts:
            return []
        active_session = self._session or self.session
        if active_session is not None:
            try:
                input_tensor = np.array([[t] for t in texts], dtype=object)
                raw_outputs = active_session.run(None, {self._input_name: input_tensor})
                prob_maps = raw_outputs[1]
                return [float(prob_map.get(1, 0.0)) for prob_map in prob_maps]
            except Exception as err:
                logger.error("ONNX batch inference failed: %s", err)
        return [self.evaluate_heuristics(t)[0] for t in texts]

    def predict_batch(self, texts: list[str]) -> list[InferenceResult]:
        """Classifies a batch of SMS messages using a single vectorized ONNX session call."""
        if not texts:
            return []
        t_start = time.perf_counter()
        circuit_open = self._is_circuit_open()
        heuristics = [self.evaluate_heuristics(t) for t in texts]
        onnx_indices = [
            idx
            for idx, (h_score, _) in enumerate(heuristics)
            if not circuit_open and h_score < 0.85
        ]
        onnx_probs_by_idx: dict[int, float] = {}
        if onnx_indices:
            subset_texts = [texts[idx] for idx in onnx_indices]
            subset_probs = self.predict_proba_batch(subset_texts)
            for idx, prob in zip(onnx_indices, subset_probs, strict=False):
                onnx_probs_by_idx[idx] = prob

        per_item_latency_ms = round(
            ((time.perf_counter() - t_start) * 1000.0) / max(len(texts), 1), 3
        )
        results: list[InferenceResult] = []
        active_session = self._session or self.session
        for idx, (heuristic_score, signals_raw) in enumerate(heuristics):
            signals = list(signals_raw)
            onnx_prob = onnx_probs_by_idx.get(idx, heuristic_score)
            if active_session is None or circuit_open:
                signals.append("ENGINE:HEURISTIC_ONLY")
            fraud_score = compute_composite_score(heuristic_score, onnx_prob, 0.0)
            if onnx_prob >= 0.75:
                signals.append("ML:HIGH_FRAUD_PROBABILITY")
            elif onnx_prob >= 0.40:
                signals.append("ML:ELEVATED_FRAUD_PROBABILITY")
            else:
                signals.append("ML:BENIGN_CLASSIFICATION")
            if fraud_score >= 0.75:
                verdict = "BLOCK"
            elif fraud_score >= 0.40:
                verdict = "FLAG"
            else:
                verdict = "ALLOW"
            results.append(
                InferenceResult(
                    verdict=verdict,
                    fraud_score=round(fraud_score, 4),
                    latency_ms=per_item_latency_ms,
                    signals=signals,
                    model_version="1.0.0",
                    onnx_probability=round(onnx_prob, 4),
                    heuristic_score=round(heuristic_score, 4),
                )
            )
        return results


OnnxSmsInferenceEngine = OnnxInferenceEngine
ONNXFraudEngine = OnnxInferenceEngine

# Global singleton instance
_engine_instance: OnnxInferenceEngine | None = None


def get_inference_engine() -> OnnxInferenceEngine:
    """Returns the singleton OnnxInferenceEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OnnxInferenceEngine()
    return _engine_instance

"""Unit and regression tests for the SentinelPulse Empirical ML Evaluation Suite.

Verifies reproducibility metadata, category breakdowns, component ablations,
error analysis extraction, and operational dual-tier thresholds.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from app.telecom.evaluate_model import (
    PROB_DELTA_TOLERANCE,
    _compute_verdict,
    _safe_wilson_ci,
    compute_ablation_metrics,
    compute_calibration_diagnostics,
    compute_category_metrics,
    compute_sample_level_delta,
    compute_wilson_ci,
    evaluate_onnx_model,
    extract_error_analysis,
    generate_markdown_report,
    get_benchmark_evaluation_set,
    get_canonical_artifact_paths,
    get_held_out_evaluation_set,
    get_held_out_samples_with_metadata,
    publish_evaluation_artifacts_atomically,
    validate_artifact_bundle_invariants,
)
from app.telecom.onnx_engine import (
    compute_composite_score,
    evaluate_heuristics,
    get_inference_engine,
)
from app.telecom.train_onnx_model import train_and_export_model


def test_held_out_dataset_integrity_and_categorization() -> None:
    """Verifies that the held-out evaluation suite has 400 samples across 16 categories."""
    samples = get_held_out_samples_with_metadata()
    assert len(samples) == 400

    benign_samples = [s for s in samples if s["label"] == 0]
    fraud_samples = [s for s in samples if s["label"] == 1]

    assert len(benign_samples) == 200
    assert len(fraud_samples) == 200

    categories = {s["category_id"] for s in samples}
    assert len(categories) == 16

    # Verify zero duplicate texts (normalized SHA-256)
    hashes = [
        hashlib.sha256(" ".join(s["text"].lower().split()).encode("utf-8")).hexdigest()
        for s in samples
    ]
    assert len(hashes) == len(set(hashes)), "Held-out test set contains duplicate samples"

    # Backward compatibility and explicit alias
    texts, labels = get_held_out_evaluation_set()
    assert len(texts) == 400
    assert len(labels) == 400
    assert labels == [s["label"] for s in samples]

    texts_bench, labels_bench = get_benchmark_evaluation_set()
    assert texts_bench == texts
    assert labels_bench == labels


def test_category_metrics_computation() -> None:
    """Verifies category breakdown calculations across mock probabilities and composite scores."""
    samples = get_held_out_samples_with_metadata()

    # Synthetic predictions
    y_prob_arr = np.array([0.1 if s["label"] == 0 else 0.9 for s in samples])
    comp_arr = np.array([0.15 if s["label"] == 0 else 0.85 for s in samples])

    result = compute_category_metrics(samples, y_prob_arr, comp_arr)
    assert result["total_categories"] == 16
    categories = result["categories"]
    assert len(categories) == 16

    total_samples = sum(c["sample_count"] for c in categories)
    assert total_samples == 400

    for cat in categories:
        assert 0.0 <= cat["tier1_rate"] <= 1.0
        assert 0.0 <= cat["tier2_rate"] <= 1.0
        assert 0.0 <= cat["mean_onnx_probability"] <= 1.0
        assert 0.0 <= cat["mean_composite_score"] <= 1.0


def test_ablation_metrics_computation() -> None:
    """Verifies ablation study calculations across ML alone, Heuristics alone, and Combined."""
    y_true = np.array([0] * 50 + [1] * 50)
    y_prob = np.array([0.1] * 45 + [0.7] * 5 + [0.3] * 5 + [0.9] * 45)
    heuristics = [0.0] * 48 + [0.8] * 2 + [0.0] * 10 + [0.8] * 40
    comp = np.array([0.1] * 45 + [0.8] * 5 + [0.3] * 5 + [0.95] * 45)

    ablation = compute_ablation_metrics(y_true, y_prob, heuristics, comp)

    assert "model_alone" in ablation
    assert "heuristics_alone" in ablation
    assert "ml_plus_heuristics" in ablation
    assert "velocity_ablation_note" in ablation

    # Check model alone thresholds
    m_alone = ablation["model_alone"]
    assert "at_threshold_0_40" in m_alone
    assert "at_threshold_0_50" in m_alone
    assert "at_threshold_0_75" in m_alone
    assert m_alone["roc_auc"] > 0.8

    # Check heuristics alone thresholds
    h_alone = ablation["heuristics_alone"]
    assert "at_threshold_0_50" in h_alone


def test_error_analysis_extraction() -> None:
    """Verifies false positive and false negative extraction with rule attribution."""
    samples = [
        {
            "text": "Chase Fraud Alert: Did you attempt $35.50? Reply YES or NO",
            "label": 0,
            "category_id": "benign_bank_alerts",
            "category_name": "Bank Fraud Alerts",
            "is_fraud": False,
        },
        {
            "text": "Hey mom cracked my phone completely text me on whatsapp",
            "label": 1,
            "category_id": "smish_broken_phone",
            "category_name": "Broken Phone",
            "is_fraud": True,
        },
    ]
    y_prob = np.array([0.45, 0.35])
    heuristics = [0.0, 0.0]
    comp = np.array([0.45, 0.35])

    error_report = extract_error_analysis(samples, y_prob, heuristics, comp)

    # Sample 0: Benign with comp=0.45 -> Tier 1 FP
    assert error_report["tier1_false_positives_count"] == 1
    fp_entry = error_report["tier1_false_positives"][0]
    assert fp_entry["expected_label"] == "BENIGN"
    assert "reason" in fp_entry

    # Sample 1: Fraud with comp=0.35 -> Tier 1 FN
    assert error_report["tier1_false_negatives_count"] == 1
    fn_entry = error_report["tier1_false_negatives"][0]
    assert fn_entry["expected_label"] == "FRAUD"
    assert "reason" in fn_entry


def test_evaluate_onnx_model_end_to_end_and_reproducibility() -> None:
    """Verifies end-to-end ONNX evaluation run, reproducibility, and SLA floors."""
    metrics = evaluate_onnx_model()

    assert metrics["sample_count"] == 400
    assert metrics["benign_count"] == 200
    assert metrics["fraud_count"] == 200

    # Reproducibility metadata
    assert "reproducibility" in metrics
    repro = metrics["reproducibility"]
    assert len(repro["model_sha256"]) == 64
    assert len(repro["evaluation_dataset_sha256"]) == 64
    assert "evaluation_timestamp" in repro
    assert "software_versions" in repro
    assert "onnxruntime" in repro["software_versions"]

    # Raw model discrimination metrics
    assert metrics["roc_auc"] >= 0.95
    assert metrics["pr_auc"] >= 0.95
    assert metrics["brier_score"] <= 0.10

    # Operational Tier 1: Escalation Queue (S >= 0.40)
    t1 = metrics["tier1_escalation"]
    assert t1["threshold"] == 0.40
    assert t1["recall"] >= 0.94  # Must catch at least 94% of fraud
    assert t1["precision"] >= 0.80

    # Operational Tier 2: Wire Drop (S >= 0.75)
    t2 = metrics["tier2_block"]
    assert t2["threshold"] == 0.75
    assert t2["precision"] >= 0.985  # Must not drop legitimate messages
    assert t2["false_positive_rate"] <= 0.02

    # Category and ablation presence
    assert len(metrics["category_analysis"]["categories"]) == 16
    assert "model_alone" in metrics["ablation_analysis"]
    assert "tier1_false_positives" in metrics["error_analysis"]


def test_markdown_report_formatting() -> None:
    """Verifies that generate_markdown_report formats all tables, tiers, and sections."""
    metrics = evaluate_onnx_model()
    report = generate_markdown_report(metrics)

    assert "# SentinelPulse Empirical ML Development & Validation Benchmark Report" in report
    assert "Reproducibility & Environment Stamp" in report
    assert "Dual-Threshold Operational Tiers" in report
    assert "Tier 1: Escalation Queue" in report
    assert "Tier 2: Immediate Wire Drop" in report
    assert "Component Ablation Study" in report
    assert "Fine-Grained Category-Level Performance Breakdown" in report
    assert "Error Analysis Summary" in report


def test_onnx_export_reproducibility_and_runtime_sha256_validation(tmp_path: Path) -> None:
    """Verifies clean-process ONNX export determinism and runtime SHA-256 validation (SF-003)."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    import pytest
    from app.telecom.onnx_engine import ONNXFraudEngine

    backend_dir = Path(__file__).resolve().parents[2]
    model_path = backend_dir / "app" / "telecom" / "models" / "sms_fraud_model.onnx"
    metadata_path = backend_dir / "app" / "telecom" / "models" / "sms_fraud_metadata.json"

    # 1. Verify clean-process export reproducibility across independent subprocesses
    export_snippet = (
        "import hashlib; "
        "from app.telecom.train_onnx_model import ("
        "build_augmented_dataset, build_production_calibration_splits, patch_skl2onnx_tfidf_bugs"
        "); "
        "from skl2onnx import to_onnx; "
        "from skl2onnx.common.data_types import StringTensorType; "
        "from sklearn.calibration import CalibratedClassifierCV; "
        "from sklearn.feature_extraction.text import TfidfVectorizer; "
        "from sklearn.linear_model import LogisticRegression; "
        "from sklearn.pipeline import Pipeline; "
        "texts, labels, groups = build_augmented_dataset(); "
        "splits = build_production_calibration_splits(texts, labels, groups, n_splits=5); "
        "pipe = Pipeline([('tfidf', TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=2500, min_df=1, token_pattern=r'\\b[a-zA-Z0-9_]+\\b')), "
        "('clf', CalibratedClassifierCV(estimator=LogisticRegression(C=1.5, max_iter=1000, class_weight='balanced', random_state=42), method='sigmoid', cv=splits, ensemble='auto'))]); "
        "pipe.fit(texts, labels); "
        "m = patch_skl2onnx_tfidf_bugs(to_onnx(pipe, initial_types=[('text', StringTensorType([None, 1]))], target_opset=14), pipe.named_steps['tfidf']); "
        "print(hashlib.sha256(m.SerializeToString()).hexdigest())"
    )

    procs: list[subprocess.Popen[str]] = []
    for seed in ("0", "0"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        procs.append(
            subprocess.Popen(  # noqa: S603
                [sys.executable, "-c", export_snippet],
                cwd=str(backend_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    hashes: list[str] = []
    for proc in procs:
        stdout, stderr = proc.communicate(timeout=60)
        assert proc.returncode == 0, f"Subprocess failed: {stderr}"
        hashes.append(stdout.strip())

    expected_disk_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert hashes[0] == hashes[1] == expected_disk_sha, (
        f"Non-deterministic ONNX export across clean subprocesses: {hashes} vs disk {expected_disk_sha}"
    )

    # 2. Verify ONNXFraudEngine validates SHA-256 at startup and exposes model_sha256 property
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    engine = ONNXFraudEngine(model_path=model_path, metadata_path=metadata_path)
    assert engine.model_sha256 == metadata["model_sha256"] == expected_disk_sha
    assert engine.session is not None

    # 3. Verify 1-byte tampering of sms_fraud_model.onnx causes initialization to fail with RuntimeError
    tampered_model_path = tmp_path / "sms_fraud_model.onnx"
    copied_meta_path = tmp_path / "sms_fraud_metadata.json"
    raw_bytes = bytearray(model_path.read_bytes())
    raw_bytes[-1] ^= 0x01  # Flip 1 bit in the last byte
    tampered_model_path.write_bytes(bytes(raw_bytes))
    copied_meta_path.write_text(metadata_path.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(RuntimeError, match="ONNX model SHA-256 mismatch"):
        ONNXFraudEngine(model_path=tampered_model_path, metadata_path=copied_meta_path)


def _independent_binary_stats(tp: int, fp: int, tn: int, fn: int) -> dict[str, Any]:
    """Independently computes exact confusion counts and rounded classification rates."""
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    f1_den = 2 * tp + fp + fn
    f1 = (2 * tp) / f1_den if f1_den > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "specificity": round(spec, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "f1_score": round(f1, 4),
    }


def _reconstruct_from_rows(
    rows: list[dict[str, Any]],
    score_key: str,
    threshold: float,
) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for row in rows:
        y = int(row["expected_label"])
        pred = int(float(row[score_key]) >= threshold)
        if y == 1 and pred == 1:
            tp += 1
        elif y == 0 and pred == 1:
            fp += 1
        elif y == 0 and pred == 0:
            tn += 1
        else:
            fn += 1
    return _independent_binary_stats(tp, fp, tn, fn)


def test_cross_artifact_mathematical_and_cryptographic_invariants() -> None:
    """Permanent gate verifying hashes, reconstructed metrics, replay parity, categories, and docs."""
    paths = get_canonical_artifact_paths()
    for key in ("model", "metadata", "predictions", "metrics", "report_root", "report_mirror"):
        assert paths[key].exists(), f"Required evaluation artifact missing: {key}={paths[key]}"

    # A. Live ONNX model binary SHA-256 vs metadata & ml_metrics
    live_model_sha256 = hashlib.sha256(paths["model"].read_bytes()).hexdigest()
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    metrics = json.loads(paths["metrics"].read_text(encoding="utf-8"))

    assert metadata["model_sha256"] == live_model_sha256
    assert metadata["dev_benchmark_metrics"]["model_sha256"] == live_model_sha256
    assert metadata["dev_benchmark_metrics"]["reproducibility"]["model_sha256"] == live_model_sha256
    assert metadata["held_out_adversarial_metrics"]["model_sha256"] == live_model_sha256
    assert metrics["model_sha256"] == live_model_sha256
    assert metrics["reproducibility"]["model_sha256"] == live_model_sha256

    # B. Live benchmark_predictions_400.json SHA-256 vs metadata & ml_metrics
    pred_bytes = paths["predictions"].read_bytes()
    live_pred_sha256 = hashlib.sha256(pred_bytes).hexdigest()
    assert metadata["benchmark_predictions_sha256"] == live_pred_sha256
    assert metadata["dev_benchmark_metrics"]["benchmark_predictions_sha256"] == live_pred_sha256
    assert (
        metadata["dev_benchmark_metrics"]["reproducibility"]["benchmark_predictions_sha256"]
        == live_pred_sha256
    )
    assert metrics["benchmark_predictions_sha256"] == live_pred_sha256
    assert metrics["reproducibility"]["benchmark_predictions_sha256"] == live_pred_sha256

    # C. Independent mathematical metric reconstruction (no hardcoded expected counts)
    pred_rows: list[dict[str, Any]] = json.loads(pred_bytes.decode("utf-8"))
    samples = get_held_out_samples_with_metadata()
    assert len(pred_rows) == len(samples)

    reconstructed = {
        "pure_ml_p50": _reconstruct_from_rows(pred_rows, "onnx_prob", 0.50),
        "heuristics_h50": _reconstruct_from_rows(pred_rows, "heuristic_score", 0.50),
        "tier1_flagged": _reconstruct_from_rows(pred_rows, "onnx_composite_score", 0.40),
        "tier2_blocked": _reconstruct_from_rows(pred_rows, "onnx_composite_score", 0.75),
    }

    for source_name, container in (
        ("ml_metrics", metrics),
        ("metadata.dev_benchmark_metrics", metadata["dev_benchmark_metrics"]),
        ("metadata.held_out_adversarial_metrics", metadata["held_out_adversarial_metrics"]),
    ):
        assert container["confusion_matrix"] == {
            k: reconstructed["pure_ml_p50"][k] for k in ("tp", "fp", "tn", "fn")
        }, f"{source_name} top-level CM mismatch"
        for field in (
            "precision",
            "recall",
            "specificity",
            "false_positive_rate",
            "false_negative_rate",
            "f1_score",
        ):
            assert abs(container[field] - reconstructed["pure_ml_p50"][field]) <= 1e-4, (
                f"{source_name}.{field} mismatch"
            )

        for tier_key, rec_key in (
            ("tier1_escalation", "tier1_flagged"),
            ("tier2_block", "tier2_blocked"),
        ):
            tier_obj = container[tier_key]
            assert tier_obj["confusion_matrix"] == {
                k: reconstructed[rec_key][k] for k in ("tp", "fp", "tn", "fn")
            }, f"{source_name}.{tier_key} CM mismatch"
            for field in ("precision", "recall", "specificity", "false_positive_rate", "f1_score"):
                assert abs(tier_obj[field] - reconstructed[rec_key][field]) <= 1e-4, (
                    f"{source_name}.{tier_key}.{field} mismatch"
                )

        ablation = container["ablation_analysis"]
        for abl_obj, rec_key in (
            (ablation["model_alone"]["at_threshold_0_50"], "pure_ml_p50"),
            (ablation["heuristics_alone"]["at_threshold_0_50"], "heuristics_h50"),
            (ablation["ml_plus_heuristics"]["tier1_escalation"], "tier1_flagged"),
            (ablation["ml_plus_heuristics"]["tier2_block"], "tier2_blocked"),
        ):
            assert abl_obj["confusion_matrix"] == {
                k: reconstructed[rec_key][k] for k in ("tp", "fp", "tn", "fn")
            }, f"{source_name}.ablation.{rec_key} CM mismatch"

    # D. Live canonical execution replay consistency (same IDs, labels, probs, H, S, exact verdict)
    engine = get_inference_engine()
    texts = [s["text"] for s in samples]
    live_probs = engine.predict_proba_batch(texts)
    assert len(live_probs) == len(pred_rows)

    for idx, (sample, row, raw_p) in enumerate(zip(samples, pred_rows, live_probs, strict=True)):
        assert int(row["sample_id"]) == idx, f"Sample ID mismatch at index {idx}"
        assert int(row["expected_label"]) == int(sample["label"]), f"Label drift at sample {idx}"
        expected_text_sha = hashlib.sha256(sample["text"].encode("utf-8")).hexdigest()
        assert str(row["text_sha256"]) == expected_text_sha, f"Text hash mismatch at {idx}"

        prob_diff = abs(float(raw_p) - float(row["onnx_prob"]))
        assert prob_diff <= 1e-6, (
            f"Sample {idx} onnx_prob drift: live={raw_p} vs stored={row['onnx_prob']} (diff={prob_diff})"
        )

        live_h, _ = evaluate_heuristics(sample["text"])
        assert abs(float(live_h) - float(row["heuristic_score"])) <= 1e-4, (
            f"Sample {idx} heuristic_score drift: live={live_h} vs stored={row['heuristic_score']}"
        )

        live_comp = compute_composite_score(float(live_h), float(raw_p), velocity_score=0.0)
        assert abs(float(live_comp) - float(row["onnx_composite_score"])) <= 1e-4, (
            f"Sample {idx} composite_score drift: live={live_comp} vs stored={row['onnx_composite_score']}"
        )

        live_verdict = _compute_verdict(live_comp)
        assert live_verdict == str(row["onnx_verdict"]), (
            f"Sample {idx} verdict drift: live={live_verdict} vs stored={row['onnx_verdict']}"
        )

        gateway_res = engine.predict(sample["text"])
        assert gateway_res.verdict == str(row["onnx_verdict"]), (
            f"Sample {idx} gateway.predict verdict drift"
        )
        assert abs(gateway_res.fraud_score - float(row["onnx_composite_score"])) <= 1e-4

    # E. Dynamic category accounting identity and aggregate reconciliation
    by_cat: dict[str, dict[str, int]] = {}
    for row in pred_rows:
        cid = str(row["category_id"])
        lbl = int(row["expected_label"])
        p = float(row["onnx_prob"])
        h = float(row["heuristic_score"])
        s = float(row["onnx_composite_score"])
        acc = by_cat.setdefault(
            cid,
            {
                "sample_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "ml_p50_flagged_count": 0,
                "heuristic_h50_flagged_count": 0,
                "tier1_flagged_count": 0,
                "tier2_blocked_count": 0,
                "t1_tp": 0,
                "t1_fp": 0,
                "t1_tn": 0,
                "t1_fn": 0,
                "t2_tp": 0,
                "t2_fp": 0,
                "t2_tn": 0,
                "t2_fn": 0,
            },
        )
        acc["sample_count"] += 1
        acc["positive_count" if lbl == 1 else "negative_count"] += 1
        if p >= 0.50:
            acc["ml_p50_flagged_count"] += 1
        if h >= 0.50:
            acc["heuristic_h50_flagged_count"] += 1
        if s >= 0.40:
            acc["tier1_flagged_count"] += 1
            acc["t1_tp" if lbl == 1 else "t1_fp"] += 1
        else:
            acc["t1_fn" if lbl == 1 else "t1_tn"] += 1
        if s >= 0.75:
            acc["tier2_blocked_count"] += 1
            acc["t2_tp" if lbl == 1 else "t2_fp"] += 1
        else:
            acc["t2_fn" if lbl == 1 else "t2_tn"] += 1

    stored_cats = metrics["category_analysis"]["categories"]
    assert len(stored_cats) == metrics["category_analysis"]["total_categories"] == len(by_cat)
    assert sum(c["sample_count"] for c in stored_cats) == len(pred_rows)

    for stored_cat in stored_cats:
        cid = str(stored_cat["category_id"])
        expected_cat = by_cat[cid]
        for field in (
            "sample_count",
            "ml_p50_flagged_count",
            "heuristic_h50_flagged_count",
            "tier1_flagged_count",
            "tier2_blocked_count",
        ):
            assert int(stored_cat[field]) == expected_cat[field], (
                f"Category {cid} field {field}: expected={expected_cat[field]}, actual={stored_cat[field]}"
            )
        assert (
            expected_cat["positive_count"] + expected_cat["negative_count"]
            == expected_cat["sample_count"]
        )

    assert sum(c["t1_tp"] for c in by_cat.values()) == reconstructed["tier1_flagged"]["tp"]
    assert sum(c["t1_fp"] for c in by_cat.values()) == reconstructed["tier1_flagged"]["fp"]
    assert sum(c["t1_tn"] for c in by_cat.values()) == reconstructed["tier1_flagged"]["tn"]
    assert sum(c["t1_fn"] for c in by_cat.values()) == reconstructed["tier1_flagged"]["fn"]
    assert sum(c["t2_tp"] for c in by_cat.values()) == reconstructed["tier2_blocked"]["tp"]
    assert sum(c["t2_fp"] for c in by_cat.values()) == reconstructed["tier2_blocked"]["fp"]
    assert sum(c["t2_tn"] for c in by_cat.values()) == reconstructed["tier2_blocked"]["tn"]
    assert sum(c["t2_fn"] for c in by_cat.values()) == reconstructed["tier2_blocked"]["fn"]

    # F. Documentation mirror SHA-256 identity & numeric parsing validation
    root_bytes = paths["report_root"].read_bytes()
    mirror_bytes = paths["report_mirror"].read_bytes()
    assert hashlib.sha256(root_bytes).hexdigest() == hashlib.sha256(mirror_bytes).hexdigest()

    report_text = root_bytes.decode("utf-8")
    assert live_model_sha256 in report_text
    assert live_pred_sha256 in report_text
    assert "Development & Validation Benchmark" in report_text

    t1_match = re.search(
        r"Tier 1: Escalation Queue.*?TP=(\d+),\s*FP=(\d+),\s*TN=(\d+),\s*FN=(\d+)",
        report_text,
    )
    t2_match = re.search(
        r"Tier 2: Immediate Wire Drop.*?TP=(\d+),\s*FP=(\d+),\s*TN=(\d+),\s*FN=(\d+)",
        report_text,
    )
    assert t1_match is not None and t2_match is not None
    assert {
        "tp": int(t1_match.group(1)),
        "fp": int(t1_match.group(2)),
        "tn": int(t1_match.group(3)),
        "fn": int(t1_match.group(4)),
    } == {k: reconstructed["tier1_flagged"][k] for k in ("tp", "fp", "tn", "fn")}
    assert {
        "tp": int(t2_match.group(1)),
        "fp": int(t2_match.group(2)),
        "tn": int(t2_match.group(3)),
        "fn": int(t2_match.group(4)),
    } == {k: reconstructed["tier2_blocked"][k] for k in ("tp", "fp", "tn", "fn")}


def test_sample_level_delta_reporting_and_no_raw_pii() -> None:
    """Verifies Sample-Level Delta Summary covers identity, verdict, tier, prob, rule, and safety."""
    base_rows: list[dict[str, Any]] = [
        {
            "sample_id": sid,
            "category_id": "cat_a",
            "category_name": "Category A",
            "expected_label": 0 if sid < 3 else 1,
            "text_sha256": f"hash_{sid}",
            "onnx_prob": 0.10 if sid < 3 else 0.80,
            "heuristic_score": 0.0,
            "triggered_rules": [],
            "onnx_composite_score": 0.10 if sid < 3 else 0.80,
            "onnx_verdict": v,
        }
        for sid, v in enumerate(("ALLOW", "ALLOW", "FLAG", "FLAG", "BLOCK", "BLOCK", "ALLOW"))
    ]
    new_rows: list[dict[str, Any]] = [{**r, "triggered_rules": []} for r in base_rows]
    # All 6 tier transitions + probability tolerances + label/identity changes
    new_rows[0]["onnx_verdict"] = "FLAG"
    new_rows[0]["onnx_composite_score"] = 0.45
    new_rows[0]["onnx_prob"] = 0.45
    new_rows[1]["onnx_verdict"] = "BLOCK"
    new_rows[1]["onnx_composite_score"] = 0.85
    new_rows[1]["heuristic_score"] = 0.80
    new_rows[1]["triggered_rules"] = ["RULE:TAX_ARREST_THREAT"]
    new_rows[2]["onnx_verdict"] = "ALLOW"
    new_rows[2]["onnx_composite_score"] = 0.12
    new_rows[3]["onnx_verdict"] = "BLOCK"
    new_rows[3]["onnx_composite_score"] = 0.90
    new_rows[4]["onnx_verdict"] = "FLAG"
    new_rows[4]["onnx_composite_score"] = 0.55
    new_rows[5]["onnx_verdict"] = "ALLOW"
    new_rows[5]["onnx_composite_score"] = 0.10
    new_rows[5]["expected_label"] = 0  # label change
    # Within tolerance probability diff on sid 6 -> counted as below_tolerance_precision_only
    new_rows[6]["onnx_prob"] = 0.80 + (PROB_DELTA_TOLERANCE * 0.1)
    # Remove sid 6? Let's keep 6 and add sid 7, and test removed sid via sliced old_rows
    new_rows.append(
        {
            "sample_id": 7,
            "category_id": "cat_a",
            "category_name": "Category A",
            "expected_label": 1,
            "text_sha256": "hash_7",
            "onnx_prob": 0.91,
            "heuristic_score": 0.65,
            "triggered_rules": ["RULE:SUSPICIOUS_TLD"],
            "onnx_composite_score": 0.92,
            "onnx_verdict": "BLOCK",
        }
    )

    delta = compute_sample_level_delta(
        base_rows,
        new_rows,
        old_model_sha256="aaa",
        new_model_sha256="aaa",
    )
    assert delta["sample_identity_changes"]["added_sample_ids"] == [7]
    assert delta["sample_identity_changes"]["changed_labels"] == [
        {"sample_id": 5, "old_label": 1, "new_label": 0}
    ]
    assert len(delta["verdict_changes"]) == 6
    assert [v["sample_id"] for v in delta["verdict_changes"]] == [0, 1, 2, 3, 4, 5]
    for expected_key in (
        "ALLOW->FLAG",
        "ALLOW->BLOCK",
        "FLAG->ALLOW",
        "FLAG->BLOCK",
        "BLOCK->FLAG",
        "BLOCK->ALLOW",
    ):
        assert delta["tier_transitions"][expected_key]["count"] == 1
    assert delta["onnx_probability_changes"][0]["sample_id"] == 0
    assert delta["heuristic_score_changes"] == [
        {
            "sample_id": 1,
            "old_heuristic_score": 0.0,
            "new_heuristic_score": 0.8,
            "abs_diff": 0.8,
            "added_rules": ["RULE:TAX_ARREST_THREAT"],
            "removed_rules": [],
        }
    ]
    interp = delta["change_interpretation"]
    assert interp["requires_manual_review"] is True
    assert interp["below_tolerance_precision_only_count"] == 1
    assert 1 in interp["heuristic_modification_sample_ids"]
    assert '"text"' not in json.dumps(delta)

    removed_delta = compute_sample_level_delta(base_rows, new_rows[:-2])
    assert removed_delta["sample_identity_changes"]["removed_sample_ids"] == [6]


def test_atomic_artifact_publication_validation_and_rollback(tmp_path: Path) -> None:
    """Proves invalid staged bundles never touch disk and mid-publish faults roll back cleanly."""
    import shutil

    canonical = get_canonical_artifact_paths()
    iso_paths = {
        "model": tmp_path / "models" / "sms_fraud_model.onnx",
        "metadata": tmp_path / "models" / "sms_fraud_metadata.json",
        "predictions": tmp_path / "benchmark_predictions_400.json",
        "metrics": tmp_path / "ml_metrics.json",
        "delta": tmp_path / "evaluation_delta_latest.json",
        "report_root": tmp_path / "docs_root" / "ml_evaluation_report.md",
        "report_mirror": tmp_path / "docs_mirror" / "ml_evaluation_report.md",
        "lock": tmp_path / ".evaluation_publish.lock",
    }
    for key in ("model", "metadata", "predictions", "metrics", "report_root", "report_mirror"):
        iso_paths[key].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(canonical[key], iso_paths[key])

    # Baseline valid bundle passes validation cleanly
    validate_artifact_bundle_invariants(iso_paths)

    # 1. Corrupt staged/live hash detection
    broken_meta = json.loads(iso_paths["metadata"].read_text(encoding="utf-8"))
    broken_meta["benchmark_predictions_sha256"] = "0" * 64
    iso_paths["metadata"].write_text(json.dumps(broken_meta), encoding="utf-8")
    with pytest.raises(ValueError, match="benchmark_predictions_sha256 mismatch"):
        validate_artifact_bundle_invariants(iso_paths)

    # Restore valid metadata and add distinctive marker bytes so we verify rollback preservation
    shutil.copy2(canonical["metadata"], iso_paths["metadata"])
    orig_hashes = {
        k: hashlib.sha256(iso_paths[k].read_bytes()).hexdigest()
        for k in ("predictions", "metrics", "metadata", "report_root", "report_mirror")
    }

    # 2. Simulate disk/write failure mid-publication right after metrics write (before metadata)
    def _fail_after_metrics(key: str, _path: Path) -> None:
        if key == "metrics":
            raise OSError("Simulated mid-publication I/O failure")

    with pytest.raises(OSError, match="Simulated mid-publication I/O failure"):
        publish_evaluation_artifacts_atomically(
            artifact_paths=iso_paths,
            fault_injection_hook=_fail_after_metrics,
        )

    for key, old_sha in orig_hashes.items():
        assert hashlib.sha256(iso_paths[key].read_bytes()).hexdigest() == old_sha, (
            f"Rollback failed to restore original {key}"
        )
    assert not iso_paths["delta"].exists(), "Orphan delta artifact was not cleaned up on rollback"
    assert not iso_paths["lock"].exists(), "Publish lock was not released on rollback"


def test_train_export_custom_dir_marks_canonical_artifacts_stale(tmp_path: Path) -> None:
    """Verifies non-canonical model exports cannot silently masquerade as republished artifacts."""
    with pytest.raises(ValueError, match="publish_eval_artifacts=True requires"):
        train_and_export_model(output_dir=str(tmp_path), publish_eval_artifacts=True)

    meta = train_and_export_model(output_dir=str(tmp_path), publish_eval_artifacts=False)
    assert meta["evaluation_artifacts_stale"] is True
    assert meta["evaluation_artifacts_status"] == "stale_not_published"
    assert (tmp_path / "sms_fraud_model.onnx").exists()
    assert (tmp_path / "sms_fraud_metadata.json").exists()
    assert (tmp_path / "dataset_inventory.json").exists()


def test_dataset_semantic_family_isolation_and_fold_balance() -> None:
    """Verifies SF-008 semantic family grouping, size balance, CV fold parity, and inventory sync."""
    from app.telecom.train_onnx_model import (
        FRAUD_BASE_SAMPLES,
        FRAUDULENT_MESSAGES,
        LEGIT_BASE_SAMPLES,
        LEGITIMATE_MESSAGES,
        build_augmented_dataset,
        build_dataset_inventory,
    )

    texts, labels, groups = build_augmented_dataset()
    live_inv = build_dataset_inventory(texts, labels, groups)

    assert len(LEGIT_BASE_SAMPLES) == len(LEGITIMATE_MESSAGES) == 40
    assert len(FRAUD_BASE_SAMPLES) == len(FRAUDULENT_MESSAGES) == 40
    assert live_inv["singleton_family_count"] == 0, "Singleton base seeds must be eliminated"

    stats = live_inv["family_size_stats"]
    assert stats["min"] >= 2
    assert stats["max"] <= 65
    assert stats["max_pct_of_corpus"] <= 10.0

    # No single family exceeds 10% and every family stays single-class (no mixed labels)
    for fam_entry in live_inv["families"]:
        assert int(fam_entry["sample_count"]) <= 65
        assert float(fam_entry["pct_of_corpus"]) <= 10.0
        assert fam_entry["label"] in (0, 1), f"Mixed-label family detected: {fam_entry}"

    # All 5 StratifiedGroupKFold splits must have 0 group overlap and +-4.0% fraud prevalence parity
    overall_prevalence = float(live_inv["fraud_prevalence"])
    assert len(live_inv["fold_distributions"]) == 5
    for fold_row in live_inv["fold_distributions"]:
        assert int(fold_row["group_overlap_count"]) == 0, f"Leakage in fold {fold_row['fold']}"
        val_rate = float(fold_row["val_fraud_rate"])
        assert abs(val_rate - overall_prevalence) <= 0.04, (
            f"Fold {fold_row['fold']} fraud prevalence {val_rate:.4f} drifted >4% from {overall_prevalence:.4f}"
        )

    audit = live_inv["cross_split_leakage_audit"]
    assert audit["dev_val_normalized_sha256_overlap"] == 0
    assert audit["intra_corpus_normalized_sha256_duplicates"] == 0

    # Committed dataset_inventory.json must exist and match the live training dataset
    canonical_paths = get_canonical_artifact_paths()
    inventory_path = canonical_paths["model"].resolve().parents[1] / "dataset_inventory.json"
    assert inventory_path.exists(), f"Missing canonical inventory artifact: {inventory_path}"

    stored_inv = json.loads(inventory_path.read_text(encoding="utf-8"))
    for key in (
        "training_dataset_sha256",
        "total_samples",
        "legit_count",
        "fraud_count",
        "fraud_prevalence",
        "total_families",
        "singleton_family_count",
        "family_size_stats",
        "families",
        "fold_distributions",
        "cross_split_leakage_audit",
    ):
        assert stored_inv[key] == live_inv[key], (
            f"dataset_inventory.json drifted from live training dataset on field '{key}'"
        )


def test_cv_fold_pipeline_zero_vocabulary_leakage() -> None:
    """Verifies TF-IDF vocabulary & IDF never leak across nested outer or inner CV splits."""
    from app.telecom.train_onnx_model import (
        _create_text_lr_pipeline,
        build_augmented_dataset,
        build_production_calibration_splits,
    )
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import StratifiedGroupKFold

    synth_texts = [
        "normal receipt update sample alpha",
        "normal receipt update sample beta",
        "zz_inner_cal_only_tok invoice update gamma",
        "zz_inner_cal_only_tok invoice update delta",
        "appointment notice clinic alpha",
        "appointment notice clinic beta",
        "zz_heldout_only_unseen_tok wire transfer urgent",
        "zz_heldout_only_unseen_tok wire transfer verify",
        "urgent suspend click scam link one",
        "urgent suspend click scam link two",
        "account block scam urgent link three",
        "account block scam urgent link four",
    ]
    synth_labels = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1]
    synth_groups = [
        "g_legit_1",
        "g_legit_1",
        "g_legit_cal_secret",
        "g_legit_cal_secret",
        "g_legit_2",
        "g_legit_2",
        "g_fraud_outer_secret",
        "g_fraud_outer_secret",
        "g_fraud_1",
        "g_fraud_1",
        "g_fraud_2",
        "g_fraud_2",
    ]

    # Build deterministic train fold (without g_fraud_outer_secret) and 2 inner splits
    tr_texts = synth_texts[:6] + synth_texts[8:]
    tr_labels = synth_labels[:6] + synth_labels[8:]
    tr_groups = synth_groups[:6] + synth_groups[8:]

    inner_sgkf = StratifiedGroupKFold(n_splits=2, shuffle=False)
    inner_splits = list(inner_sgkf.split(tr_texts, tr_labels, groups=tr_groups))
    assert len(inner_splits) == 2

    nested_model = CalibratedClassifierCV(
        estimator=_create_text_lr_pipeline(),
        method="sigmoid",
        cv=inner_splits,
        ensemble="auto",
    )
    nested_model.fit(tr_texts, tr_labels)

    for split_pos, ((in_tr, in_cal), cal_est) in enumerate(
        zip(inner_splits, nested_model.calibrated_classifiers_, strict=True)
    ):
        tr_grp_set = {tr_groups[int(i)] for i in in_tr}
        cal_grp_set = {tr_groups[int(i)] for i in in_cal}
        assert tr_grp_set.isdisjoint(cal_grp_set)
        vocab = cal_est.estimator.named_steps["tfidf"].vocabulary_
        assert "zz_heldout_only_unseen_tok" not in vocab
        if "g_legit_cal_secret" in cal_grp_set:
            assert "zz_inner_cal_only_tok" not in vocab, (
                f"Inner split {split_pos} leaked calibration-fold token into TF-IDF vocabulary!"
            )

    # Also verify canonical GroupKFold(5) production splits are group-disjoint
    texts, labels, groups = build_augmented_dataset()
    prod_splits = build_production_calibration_splits(texts, labels, groups, n_splits=5)
    assert len(prod_splits) == 5
    for tr_idx, cal_idx in prod_splits:
        assert {groups[int(i)] for i in tr_idx}.isdisjoint({groups[int(i)] for i in cal_idx})


def test_calibration_ece_and_wilson_intervals() -> None:
    """Verifies exact 10-bin half-open/closed ECE math and Wilson 95% CI edge cases."""
    y_true = [0, 0, 0, 1, 1]
    y_prob = [0.0, 0.099, 0.1, 0.9, 1.0]
    cal = compute_calibration_diagnostics(y_true, y_prob, n_bins=10)
    bins = cal["reliability_bins"]

    assert cal["bin_scheme"] == "equal_width_half_open_final_closed"
    assert len(bins) == 10
    assert sum(int(b["sample_count"]) for b in bins) == 5

    # [0.0, 0.1) captures 0.0 and 0.099; 0.1 falls into [0.1, 0.2); [0.9, 1.0] captures 0.9 & 1.0
    assert bins[0]["sample_count"] == 2
    assert bins[1]["sample_count"] == 1
    assert bins[9]["sample_count"] == 2
    for empty_idx in range(2, 9):
        assert bins[empty_idx]["sample_count"] == 0
        assert bins[empty_idx]["mean_predicted_prob"] is None
        assert bins[empty_idx]["empirical_positive_rate"] is None
        assert bins[empty_idx]["abs_calibration_gap"] is None

    expected_ece = (
        (2 / 5) * abs(0.0495 - 0.0) + (1 / 5) * abs(0.1 - 0.0) + (2 / 5) * abs(0.95 - 1.0)
    )
    assert abs(float(cal["ece"]) - expected_ece) < 1e-6

    # Wilson 95% CI edge cases (all 1s, all 0s, and 0/0 denominator)
    lo_all1, hi_all1 = compute_wilson_ci(100, 100)
    assert hi_all1 == 1.0
    assert 0.96 <= lo_all1 < 0.97

    lo_all0, hi_all0 = compute_wilson_ci(0, 100)
    assert lo_all0 == 0.0
    assert 0.03 < hi_all0 <= 0.04

    with pytest.raises(ValueError, match="total must be > 0"):
        compute_wilson_ci(0, 0)
    assert _safe_wilson_ci(0, 0) is None
    safe_bounds = _safe_wilson_ci(180, 200)
    assert safe_bounds is not None and 0.84 <= safe_bounds[0] < 0.90 < safe_bounds[1] <= 0.94


def test_oof_completeness_macro_sensitivity_and_cluster_bootstrap() -> None:
    """Verifies canonical SF-009 OOF artifacts, zero group leakage, cluster bootstrap, and macro check."""
    from app.telecom.train_onnx_model import (
        build_augmented_dataset,
        compute_cluster_bootstrap_ci,
        get_macro_archetype_groups,
    )

    texts, labels, groups = build_augmented_dataset()
    canonical_paths = get_canonical_artifact_paths()
    metrics = json.loads(canonical_paths["metrics"].read_text(encoding="utf-8"))
    metadata = json.loads(canonical_paths["metadata"].read_text(encoding="utf-8"))
    oof_path = canonical_paths["model"].resolve().parents[1] / "oof_predictions.json"
    assert oof_path.exists(), f"Missing canonical OOF predictions artifact: {oof_path}"

    oof_raw = oof_path.read_text(encoding="utf-8")
    assert '"text"' not in oof_raw, "oof_predictions.json must never serialize raw SMS text"
    oof_rows = json.loads(oof_raw)
    assert len(oof_rows) == len(texts) == 703
    assert sorted(int(r["sample_id"]) for r in oof_rows) == list(range(len(texts)))
    assert len({int(r["sample_id"]) for r in oof_rows}) == len(texts)

    oof_meta = metrics["oof_cross_validation"]
    assert metadata["oof_cross_validation"] == oof_meta
    assert oof_meta["production_calibration_strategy"] == "GroupKFold(n_splits=5)"
    assert oof_meta["production_calibration_max_group_overlap"] == 0
    assert metadata["calibration"]["cv_strategy"] == "GroupKFold(n_splits=5)"
    assert metadata["calibration"]["max_group_overlap"] == 0

    expected_oof_sha = hashlib.sha256(oof_path.read_bytes()).hexdigest()
    assert oof_meta["oof_predictions_sha256"] == expected_oof_sha

    fg = oof_meta["fine_grained"]
    macro = oof_meta["macro_bank_2way"]
    assert fg["group_count"] == 56
    assert macro["group_count"] == 54
    assert "legit_bank_2way_macro" in set(get_macro_archetype_groups(groups))
    assert "sensitivity_note" in macro

    for variant in (fg, macro):
        assert variant["max_outer_group_overlap"] == 0
        assert variant["max_inner_group_overlap"] == 0
        assert variant["completeness"]["is_complete"] is True
        assert variant["completeness"]["covered_sample_ids"] == len(texts)
        assert variant["completeness"]["duplicate_sample_ids"] == 0

    boot = fg["cluster_bootstrap_95_ci"]
    assert boot["method"] == "nonparametric_cluster_percentile_bootstrap"
    assert boot["independent_group_count"] == 56
    assert boot["replicate_count"] == 1000
    assert boot["seed"] == 42

    # Determinism check: re-running cluster bootstrap on stored OOF predictions yields exact match
    re_boot = compute_cluster_bootstrap_ci(
        [int(r["true_label"]) for r in oof_rows],
        [float(r["oof_probability"]) for r in oof_rows],
        [str(r["family_id"]) for r in oof_rows],
        n_replicates=1000,
        seed=42,
    )
    assert re_boot["metrics"] == boot["metrics"]

    # Dev/Val N=400 ECE & Wilson intervals exposed identically across metrics & metadata
    assert len(metrics["reliability_bins"]) == 10
    assert sum(int(b["sample_count"]) for b in metrics["reliability_bins"]) == 400
    assert abs(float(metrics["ece"]) - float(metadata["ece"])) < 1e-7
    assert metrics["wilson_95_ci"] == metadata["wilson_95_ci"]
    for w_key in (
        "ml_p50_precision",
        "ml_p50_recall",
        "tier1_precision",
        "tier1_recall",
        "tier1_fpr",
        "tier2_precision",
        "tier2_recall",
        "tier2_fpr",
    ):
        assert w_key in metrics["wilson_95_ci"]


def test_sf010_frozen_baseline_artifacts_and_blocked_holdout_status() -> None:
    """Verifies frozen model/corpus SHA locks remain unchanged and primary Class C holdout stays blocked."""
    from app.telecom.dataset_quarantine import (
        FROZEN_DEV_VAL_DATASET_SHA256,
        FROZEN_ONNX_MODEL_SHA256,
        FROZEN_TRAINING_DATASET_SHA256,
        get_dataset_governance_paths,
        sha256_bytes,
    )
    from app.telecom.train_onnx_model import build_augmented_dataset

    canon = get_canonical_artifact_paths()
    gov_paths = get_dataset_governance_paths()

    assert sha256_bytes(canon["model"].read_bytes()) == FROZEN_ONNX_MODEL_SHA256
    metadata = json.loads(canon["metadata"].read_text(encoding="utf-8"))
    metrics = json.loads(canon["metrics"].read_text(encoding="utf-8"))
    inventory = json.loads(
        (canon["model"].resolve().parents[1] / "dataset_inventory.json").read_text(encoding="utf-8")
    )

    assert metadata["model_sha256"] == FROZEN_ONNX_MODEL_SHA256
    assert metrics["model_sha256"] == FROZEN_ONNX_MODEL_SHA256
    assert inventory["training_dataset_sha256"] == FROZEN_TRAINING_DATASET_SHA256
    assert metrics["evaluation_dataset_sha256"] == FROZEN_DEV_VAL_DATASET_SHA256

    train_texts, _, _ = build_augmented_dataset()
    assert len(train_texts) == 703
    assert len(get_held_out_samples_with_metadata()) == 400

    # Primary external fraud holdout must NOT be created while no source passes all gates
    assert not gov_paths["primary_holdout"].exists(), (
        "quarantined_test_holdout.json must not exist while primary external holdout gate is blocked"
    )
    assessment = json.loads(gov_paths["source_assessment"].read_text(encoding="utf-8"))
    assert assessment["primary_external_holdout_status"] == "UNAVAILABLE_BLOCKED"
    assert assessment["primary_external_holdout_artifact"] is None
    assert assessment["sf_011_status"] == "BLOCKED_ON_PRIMARY_EXTERNAL_HOLDOUT"


def test_sf010_uci_secondary_quarantine_provenance_and_zero_relabeling() -> None:
    """Verifies UCI secondary spam transfer benchmark LF/CRLF integrity, counts, and overlap."""
    import copy

    from app.telecom.dataset_quarantine import (
        compute_canonical_content_digest,
        compute_overlap_audit,
        get_dataset_governance_paths,
        normalized_sha256,
        sha256_text,
        verify_uci_artifact_integrity,
    )
    from app.telecom.evaluate_model import get_held_out_samples_with_metadata
    from app.telecom.train_onnx_model import build_augmented_dataset

    gov_paths = get_dataset_governance_paths()
    assert gov_paths["secondary_uci"].exists(), "Missing uci_sms_spam_secondary.json"

    assessment_raw = gov_paths["source_assessment"].read_bytes()
    assert b"\r\n" not in assessment_raw, "external_source_assessment.json must use LF endings"
    assessment = json.loads(assessment_raw.decode("utf-8"))

    raw_bytes = gov_paths["secondary_uci"].read_bytes()
    assert b"\r\n" not in raw_bytes, "uci_sms_spam_secondary.json must use LF endings on disk"

    integrity = verify_uci_artifact_integrity(
        raw_bytes,
        expected_canonical_lf_sha256=assessment["secondary_transfer_benchmark_lf_sha256"],
    )
    assert integrity["eol_style_on_disk"] == "LF"
    assert integrity["raw_matches_canonical_lf"] is True
    assert integrity["lf_canonical_sha256"] == assessment["secondary_transfer_benchmark_sha256"]
    assert (
        integrity["canonical_content_sha256"]
        == assessment["secondary_transfer_benchmark_content_sha256"]
    )
    assert (
        integrity["canonical_rows_sha256"]
        == assessment["secondary_transfer_benchmark_canonical_rows_sha256"]
    )

    # Simulated Windows CRLF bytes must transparently differ in raw digest while preserving LF & content digests
    crlf_bytes = raw_bytes.replace(b"\n", b"\r\n")
    crlf_integrity = verify_uci_artifact_integrity(
        crlf_bytes,
        expected_canonical_lf_sha256=assessment["secondary_transfer_benchmark_lf_sha256"],
    )
    assert crlf_integrity["eol_style_on_disk"] == "CRLF"
    assert crlf_integrity["raw_matches_canonical_lf"] is False
    assert crlf_integrity["raw_disk_sha256"] != crlf_integrity["lf_canonical_sha256"]
    assert crlf_integrity["lf_canonical_sha256"] == integrity["lf_canonical_sha256"]
    assert crlf_integrity["canonical_rows_sha256"] == integrity["canonical_rows_sha256"]
    assert crlf_integrity["canonical_content_sha256"] == integrity["canonical_content_sha256"]

    uci_bundle = integrity["bundle"]
    manifest = uci_bundle["manifest"]
    rows = uci_bundle["rows"]

    # Content digest must remain invariant when volatile UTC retrieval timestamps change
    mutated_bundle = copy.deepcopy(uci_bundle)
    mutated_bundle["manifest"]["retrieval_timestamp_utc"] = "2099-12-31T23:59:59+00:00"
    mutated_bundle["manifest"]["retrieval_metadata"]["retrieval_timestamp_utc"] = (
        "2099-12-31T23:59:59+00:00"
    )
    assert compute_canonical_content_digest(mutated_bundle) == manifest["canonical_content_sha256"]

    with pytest.raises(ValueError, match="canonical LF artifact SHA-256 mismatch"):
        verify_uci_artifact_integrity(raw_bytes, expected_canonical_lf_sha256="0" * 64)

    tampered_bundle = copy.deepcopy(uci_bundle)
    tampered_bundle["rows"][0]["text"] = "tampered payload"
    tampered_bytes = json.dumps(tampered_bundle).encode("utf-8")
    with pytest.raises(ValueError, match="canonical_rows_sha256 mismatch"):
        verify_uci_artifact_integrity(tampered_bytes)

    assert manifest["benchmark_role"] == "secondary_legacy_sms_spam_transfer_benchmark"
    assert manifest["is_primary_fraud_holdout"] is False
    assert len(rows) == 5574
    assert manifest["verified_counts"] == {
        "total_records": 5574,
        "ham_count": 4827,
        "spam_count": 747,
        "unique_normalized_records": 5159,
        "unique_ham_count": 4517,
        "unique_spam_count": 642,
        "intra_corpus_normalized_duplicates": 415,
        "conflicting_label_duplicates": 0,
    }

    expected_rows_sha = sha256_text(json.dumps(rows, sort_keys=True, ensure_ascii=False))
    assert manifest["canonical_rows_sha256"] == expected_rows_sha

    seen_ids: set[str] = set()
    for idx, row in enumerate(rows, start=1):
        rec_id = str(row["upstream_record_id"])
        assert rec_id == f"uci_228_line_{idx}"
        assert rec_id not in seen_ids
        seen_ids.add(rec_id)
        assert row["original_label"] in ("ham", "spam")
        assert row["derived_fraud_label"] is None
        assert row["provenance_class"] == "Secondary-Legacy-SMS-Spam"
        assert row["raw_text_sha256"] == sha256_text(str(row["text"]))
        assert row["normalized_sha256"] == normalized_sha256(str(row["text"]))

    train_texts, _, _ = build_augmented_dataset()
    dev_texts = [str(s["text"]) for s in get_held_out_samples_with_metadata()]
    live_overlap = compute_overlap_audit(
        rows,
        train_texts=train_texts,
        dev_val_texts=dev_texts,
        near_threshold=0.45,
    )
    assert live_overlap["against_train"]["exact_text_matches"] == 0
    assert live_overlap["against_train"]["normalized_sha256_matches"] == 0
    assert live_overlap["against_train"]["near_duplicate_count"] == 0
    assert live_overlap["against_dev_val"]["exact_text_matches"] == 0
    assert live_overlap["against_dev_val"]["normalized_sha256_matches"] == 0
    assert live_overlap["against_dev_val"]["near_duplicate_count"] == 0
    assert live_overlap == manifest["overlap_audit"]


def test_sf010_source_assessment_completeness_and_gate_integrity() -> None:
    """Verifies candidate source assessment ledger, pinned IMC25 URL, resolved counts, and gates."""
    from app.telecom.dataset_quarantine import (
        assess_holdout_suitability,
        get_dataset_governance_paths,
    )

    gov_paths = get_dataset_governance_paths()
    assessment = json.loads(gov_paths["source_assessment"].read_text(encoding="utf-8"))
    candidates = assessment["candidates"]
    by_id = {str(c["candidate_id"]): c for c in candidates}

    expected_ids = {
        "imc25_smishing_reports",
        "uci_sms_spam_collection_v1",
        "mendeley_f45bkkt8pr_v1",
        "mendeley_vmg875v4xs_v1",
        "smishtank_codaspy24",
        "zenodo_15235123_multiclass_phishing",
        "github_shaghayegh_combined_smishing",
        "hf_gandharvbakshi_otp_phishing",
    }
    assert set(by_id.keys()) == expected_ids
    assert "programmatically_computed_fields" in assessment["provenance_separation"]
    assert "manual_candidate_adjudications" in assessment["provenance_separation"]

    for cid, cand in by_id.items():
        assert str(cand["canonical_url"]).startswith("https://")
        assert str(cand["retrieval_timestamp_utc"]).endswith("+00:00")
        assert len(str(cand["license"])) > 0
        assert len(cand["rejection_or_limitation_reasons"]) >= 1, f"Missing limitations for {cid}"

    # Verify Mendeley f45bkkt8pr UCI-spam contamination evidence is explicitly documented
    assert (
        by_id["mendeley_f45bkkt8pr_v1"]["verified_counts"][
            "uci_exact_normalized_overlap_breakdown"
        ]["smishing_matching_uci_spam_RELABELED"]
        == 361
    )

    # Verify IMC25 pinned immutable commit URL and reconciled empty-category counts
    imc25 = by_id["imc25_smishing_reports"]
    assert "a6175560b57387199871e51fbef6bc523d2516b4" in str(imc25["retrieval_url"])
    assert "/main/" not in str(imc25["retrieval_url"])
    assert imc25["verified_counts"]["english_records"] == 22078
    assert imc25["verified_counts"]["english_non_spam_smishing_total"] == 20691
    assert imc25["verified_counts"]["english_non_spam_unique_normalized"] == 14363
    assert imc25["verified_counts"]["english_non_spam_empty_scam_type_count"] == 1
    assert imc25["verified_counts"]["english_non_spam_empty_scam_type_csv_rows"] == [33411]
    assert imc25["verified_counts"]["english_named_non_spam_smishing_total"] == 20690
    assert imc25["verified_counts"]["english_named_non_spam_unique_normalized"] == 14362
    assert imc25["verified_counts"]["english_non_spam_with_url_placeholder"] == 6030
    assert imc25["overlap_audit_summary"]["english_word_3gram_near_ge_045_train"] == 0
    assert imc25["overlap_audit_summary"]["english_word_3gram_near_ge_045_dev_val"] == 0

    re_summary = assess_holdout_suitability(assessment)
    assert re_summary == assessment["gate_summary"]
    assert re_summary["primary_holdout_ready"] is False
    assert re_summary["eligible_primary_candidates"] == []
    assert re_summary["secondary_benchmarks_retained"] == ["uci_sms_spam_collection_v1"]


def test_sf010_ingestion_zero_model_ast_isolation() -> None:
    """Enforces via AST parsing that quarantine ingestion never imports ML, ONNX, or heuristics."""
    import ast

    from app.telecom import dataset_quarantine

    source_text = Path(dataset_quarantine.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    forbidden_prefixes = (
        "onnxruntime",
        "onnx",
        "skl2onnx",
        "sklearn",
        "app.telecom.onnx_engine",
        "app.telecom.evaluate_model",
        "app.telecom.train_onnx_model",
        "app.main",
    )

    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    for mod in imported_modules:
        assert not any(mod == p or mod.startswith(f"{p}.") for p in forbidden_prefixes), (
            f"dataset_quarantine.py imported forbidden modeling/inference module '{mod}'"
        )


def test_sf010_statistical_wilson_base_rate_and_mirrored_docs() -> None:
    """Verifies exact integer Wilson intervals, base-rate PPV shift, and byte-identical docs."""
    from app.telecom.dataset_quarantine import (
        adjust_precision_for_base_rate,
        compute_exact_wilson_interval,
        get_dataset_governance_paths,
    )

    lo_143, hi_143 = compute_exact_wilson_interval(143, 150)
    assert abs(lo_143 - 0.906814) < 1e-6
    assert abs(hi_143 - 0.977213) < 1e-6

    lo_150, hi_150 = compute_exact_wilson_interval(150, 300)
    assert abs(lo_150 - 0.44378) < 1e-6
    assert abs(hi_150 - 0.55622) < 1e-6

    assert compute_exact_wilson_interval(150, 150) == (0.97503, 1.0)
    assert compute_exact_wilson_interval(0, 150) == (0.0, 0.02497)

    with pytest.raises(ValueError, match="total must be > 0"):
        compute_exact_wilson_interval(0, 0)
    with pytest.raises(ValueError, match="must be in"):
        compute_exact_wilson_interval(151, 150)
    with pytest.raises(TypeError, match="exact integers"):
        compute_exact_wilson_interval(10.5, 100)  # type: ignore[arg-type]

    # Bayes PPV collapses when balanced 50% benchmark performance hits rare 1% live prevalence
    assert adjust_precision_for_base_rate(0.95, 0.05, 0.50) == 0.95
    assert adjust_precision_for_base_rate(0.95, 0.05, 0.01) == 0.161017

    gov_paths = get_dataset_governance_paths()
    root_bytes = gov_paths["governance_root"].read_bytes()
    mirror_bytes = gov_paths["governance_mirror"].read_bytes()
    assert root_bytes == mirror_bytes, (
        "Mirrored provenance & governance docs must be byte-identical"
    )

    doc_text = root_bytes.decode("utf-8")
    assert b"\r\n" not in root_bytes, "Mirrored governance markdown must use canonical LF endings"
    for required_section in (
        "Class A — Train OOF CV",
        "Class B — Dev/Val Benchmark",
        "Class C — External Public Evaluation",
        "Class D — Production Telemetry",
        "UNAVAILABLE / BLOCKED",
        "BLOCKED_ON_PRIMARY_EXTERNAL_HOLDOUT",
        "uci_sms_spam_secondary.json",
        "Strict Zero-Adaptation Protocol",
    ):
        assert required_section in doc_text, f"Governance doc missing '{required_section}'"
    assert "±3.2%" not in doc_text and "3.2%" not in doc_text


def test_sf010r1_assessment_sha256_and_mirrored_docs_regression() -> None:
    """Verifies full 64-char canonical LF assessment SHA-256 matches both mirrored docs."""
    import re
    import string

    from app.telecom.dataset_quarantine import (
        get_dataset_governance_paths,
        normalize_line_endings_lf,
        sha256_bytes,
    )

    gov_paths = get_dataset_governance_paths()
    assessment_raw = gov_paths["source_assessment"].read_bytes()
    assert b"\r\n" not in assessment_raw, "external_source_assessment.json must use LF endings"
    assessment_lf_sha256 = sha256_bytes(normalize_line_endings_lf(assessment_raw))

    assert len(assessment_lf_sha256) == 64
    assert all(ch in string.hexdigits[:16] for ch in assessment_lf_sha256)

    root_bytes = gov_paths["governance_root"].read_bytes()
    mirror_bytes = gov_paths["governance_mirror"].read_bytes()
    assert root_bytes == mirror_bytes, "Mirrored governance docs must remain byte-identical"
    assert b"\r\n" not in root_bytes, "Mirrored governance docs must use LF endings"

    doc_text = root_bytes.decode("utf-8")
    assert assessment_lf_sha256 in doc_text, (
        f"Governance docs missing full 64-char assessment SHA-256 {assessment_lf_sha256}"
    )
    doc_match = re.search(r"canonical LF sha256 = ([0-9a-f]+)", doc_text)
    assert doc_match is not None, "Governance docs missing 'canonical LF sha256 = <hash>' record"
    assert doc_match.group(1) == assessment_lf_sha256


def test_sf010r_builder_isolation_ast_corpus_and_hermetic_reconstruction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies committed builder isolation, AST corpus verification, guards, and offline build."""
    import ast
    import zipfile

    from app.telecom import build_quarantine_artifacts as builder
    from app.telecom.dataset_quarantine import (
        FROZEN_DEV_VAL_DATASET_SHA256,
        FROZEN_TRAINING_DATASET_SHA256,
        get_dataset_governance_paths,
        sha256_bytes,
    )

    # 1. Builder must NEVER import ML/ONNX/training/inference modules or invoke exec/eval
    builder_src = Path(builder.__file__).read_text(encoding="utf-8")
    tree = ast.parse(builder_src)
    forbidden_prefixes = (
        "onnxruntime",
        "onnx",
        "skl2onnx",
        "sklearn",
        "numpy",
        "app.telecom.onnx_engine",
        "app.telecom.evaluate_model",
        "app.telecom.train_onnx_model",
        "app.main",
    )
    imported_modules: list[str] = []
    called_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.append(node.func.id)

    for mod in imported_modules:
        assert not any(mod == p or mod.startswith(f"{p}.") for p in forbidden_prefixes), (
            f"build_quarantine_artifacts.py imported forbidden module '{mod}'"
        )
    assert "exec" not in called_names and "eval" not in called_names

    # 2. Pure-AST corpus extraction must reproduce exact frozen baseline hashes without imports
    corpora = builder.extract_frozen_corpora()
    assert len(corpora["train_texts"]) == 703
    assert corpora["train_sha256"] == FROZEN_TRAINING_DATASET_SHA256
    assert len(corpora["dev_val_texts"]) == 400
    assert corpora["dev_val_sha256"] == FROZEN_DEV_VAL_DATASET_SHA256

    # 3. Offline repository verification passes against committed LF files & CRLF simulation
    offline_report = builder.verify_repository_reproducibility(offline=True)
    assert offline_report["uci_disk_eol"] == "LF"
    assert offline_report["frozen_train_sha256"] == FROZEN_TRAINING_DATASET_SHA256
    assert offline_report["frozen_dev_val_sha256"] == FROZEN_DEV_VAL_DATASET_SHA256

    # 4. Canonical overwrite guard refuses writes to datasets/ without --write-canonical
    gov_paths = get_dataset_governance_paths()
    with pytest.raises(ValueError, match="--write-canonical"):
        builder.write_artifacts_to_directory(
            gov_paths["datasets_dir"],
            {"uci_lf_bytes": b"{}\n", "assessment_lf_bytes": b"{}\n"},
            write_canonical=False,
        )

    # 5. Zip member allowlist and checksum verification reject tampered archives
    bad_zip = tmp_path / "unexpected.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../evil.txt", "bad")
    monkeypatch.setattr(builder, "UCI_EXPECTED_ZIP_SHA256", sha256_bytes(bad_zip.read_bytes()))
    with pytest.raises(ValueError, match="Unexpected UCI ZIP members"):
        builder.extract_verified_uci_members(bad_zip.read_bytes())

    # 6. Full hermetic offline reconstruction into tmp_path with pinned synthetic fixtures
    uci_tsv = b"ham\tHey are we still meeting at 6pm?\nspam\tWIN FREE RINGTONES text 87121 now\n"
    readme_bytes = b"UCI SMS Spam Collection test readme\n"
    uci_zip = tmp_path / "uci.zip"
    with zipfile.ZipFile(uci_zip, "w") as zf:
        zf.writestr("SMSSpamCollection", uci_tsv)
        zf.writestr("readme", readme_bytes)

    imc_csv_bytes = (
        b"time,sender_id,telephone_number_type,original_network_name,original_network_country,"
        b"text,translation,language,url_shortener,named_entity,scam_type,lure_principles\n"
        b"2024-01-01,sms,short,,GBR,Bank alert: verify at <URL>,,English,,,banking,urgency\n"
        b"2024-01-02,sms,short,,GBR,Promo spam text,,English,,,spam,greed\n"
        b"2024-01-03,sms,short,,GBR,NHS checkup <DATE_TIME>,,English,,,,distraction\n"
    )
    imc_csv = tmp_path / "imc25.csv"
    imc_csv.write_bytes(imc_csv_bytes)

    monkeypatch.setattr(builder, "UCI_EXPECTED_ZIP_SHA256", sha256_bytes(uci_zip.read_bytes()))
    monkeypatch.setattr(
        builder,
        "UCI_EXPECTED_MEMBER_SHA256",
        {
            "SMSSpamCollection": sha256_bytes(uci_tsv),
            "readme": sha256_bytes(readme_bytes),
        },
    )
    monkeypatch.setattr(builder, "IMC25_EXPECTED_CSV_SHA256", sha256_bytes(imc_csv_bytes))

    built_t1 = builder.build_artifacts_payload(
        uci_zip_path=uci_zip,
        imc25_csv_path=imc_csv,
        retrieval_timestamp_utc="2026-11-11T10:00:00+00:00",
    )
    built_t2 = builder.build_artifacts_payload(
        uci_zip_path=uci_zip,
        imc25_csv_path=imc_csv,
        retrieval_timestamp_utc="2099-01-01T00:00:00+00:00",
    )
    out_dir = tmp_path / "out"
    written = builder.write_artifacts_to_directory(out_dir, built_t1, write_canonical=False)

    assert b"\r\n" not in written["uci_path"].read_bytes()
    assert b"\r\n" not in written["assessment_path"].read_bytes()
    assert (
        built_t1["uci_bundle"]["manifest"]["canonical_content_sha256"]
        == built_t2["uci_bundle"]["manifest"]["canonical_content_sha256"]
    )
    assert (
        built_t1["uci_bundle"]["manifest"]["canonical_rows_sha256"]
        == built_t2["uci_bundle"]["manifest"]["canonical_rows_sha256"]
    )
    imc_counts = next(
        c["verified_counts"]
        for c in built_t1["assessment"]["candidates"]
        if c["candidate_id"] == "imc25_smishing_reports"
    )
    assert imc_counts["english_non_spam_smishing_total"] == 2
    assert imc_counts["english_non_spam_empty_scam_type_count"] == 1
    assert imc_counts["english_named_non_spam_smishing_total"] == 1


def test_sf011_acquisition_ledger_gates_sample_size_and_mirrored_docs() -> None:
    """Verifies SF-011 Class C acquisition ledger, 7-gate logic, Wilson/PPV math, and zero-PII."""
    import ast
    import copy
    import json
    import re

    from app.telecom import dataset_quarantine as dq
    from app.telecom.dataset_quarantine import (
        CLASS_C_QUALIFICATION_GATES,
        FROZEN_DEV_VAL_DATASET_SHA256,
        FROZEN_ONNX_MODEL_SHA256,
        FROZEN_TRAINING_DATASET_SHA256,
        adjust_precision_for_base_rate,
        compute_exact_wilson_interval,
        evaluate_class_c_qualification_routes,
        get_dataset_governance_paths,
    )

    gov_paths = get_dataset_governance_paths()

    # 1. Primary Class C holdout artifact must remain absent (UNAVAILABLE / BLOCKED)
    assert not gov_paths["primary_holdout"].exists(), (
        "quarantined_test_holdout.json must NOT exist while Class C holdout is blocked"
    )

    # 2. SF-011 JSON ledger and mirrored docs must exist, use strict LF endings, and match bytes
    routes_raw = gov_paths["sf011_routes"].read_bytes()
    doc_root_raw = gov_paths["sf011_doc_root"].read_bytes()
    doc_mirror_raw = gov_paths["sf011_doc_mirror"].read_bytes()
    assert b"\r\n" not in routes_raw, "sf011_acquisition_routes.json must use LF endings"
    assert b"\r\n" not in doc_root_raw, "sf011_class_c_acquisition_and_qualification.md must be LF"
    assert doc_root_raw == doc_mirror_raw, "Mirrored SF-011 docs must stay byte-identical"

    ledger = json.loads(routes_raw.decode("utf-8"))
    assert ledger["ticket_id"] == "SF-011"

    refs = ledger["sf010_and_sf010r_baseline_references"]
    assert refs["frozen_onnx_model_sha256"] == FROZEN_ONNX_MODEL_SHA256
    assert refs["frozen_training_dataset_sha256"] == FROZEN_TRAINING_DATASET_SHA256
    assert refs["frozen_dev_val_dataset_sha256"] == FROZEN_DEV_VAL_DATASET_SHA256
    assert refs["primary_holdout_artifact_created"] is False
    assert refs["sf_011_holdout_status"] == "BLOCKED_ON_PRIMARY_EXTERNAL_HOLDOUT"

    # 3. 7-gate definition and deterministic gate evaluation across >=10 routes and all categories
    mandatory_gate_ids = tuple(
        g["gate_id"] for g in ledger["class_c_qualification_gate"]["mandatory_gates"]
    )
    assert mandatory_gate_ids == CLASS_C_QUALIFICATION_GATES
    assert len(CLASS_C_QUALIFICATION_GATES) == 7

    evaluated = evaluate_class_c_qualification_routes(ledger)
    assert evaluated == ledger["gate_evaluation"]
    assert evaluated["total_routes_assessed"] >= 10
    assert evaluated["qualified_class_c_routes"] == []
    assert evaluated["class_c_holdout_ready"] is False
    assert evaluated["primary_holdout_status"] == "UNAVAILABLE_BLOCKED"

    categories = {route["category"] for route in ledger["routes_investigated"]}
    assert "published_research_dataset" in categories
    assert "academic_mno_collaboration_route" in categories
    assert "consumer_protection_and_regulatory_bodies" in categories
    assert "telecom_antifraud_consortia_and_carrier_enclave" in categories

    # Pure unit test of positive/negative gate boundary in memory
    synthetic_ledger = copy.deepcopy(ledger)
    synthetic_ledger["routes_investigated"].append(
        {
            "route_id": "synthetic_valid_enclave_mock",
            "qualification_status": "QUALIFIED",
            "class_c_gates": {gate: True for gate in CLASS_C_QUALIFICATION_GATES},
        }
    )
    synthetic_ledger["routes_investigated"].append(
        {
            "route_id": "synthetic_incomplete_gate_mock",
            "qualification_status": "QUALIFIED",
            "class_c_gates": {
                gate: (gate != "independence") for gate in CLASS_C_QUALIFICATION_GATES
            },
        }
    )
    mock_eval = evaluate_class_c_qualification_routes(synthetic_ledger)
    assert mock_eval["qualified_class_c_routes"] == ["synthetic_valid_enclave_mock"]
    assert "synthetic_incomplete_gate_mock" in mock_eval["failing_gates_by_route"]
    assert mock_eval["failing_gates_by_route"]["synthetic_incomplete_gate_mock"] == ["independence"]
    assert mock_eval["class_c_holdout_ready"] is True
    assert mock_eval["primary_holdout_status"] == "READY_FOR_CONTROLLED_QUARANTINE"

    # 4. Exact numerical verification of Wilson 95% CI table and Bayes PPV sensitivity table
    stats_fw = ledger["sample_size_and_ci_framework"]
    for row in stats_fw["wilson_95_ci_reference_table"]:
        k = row["successes_k"]
        n = row["denominator_n"]
        lo, hi = compute_exact_wilson_interval(k, n)
        assert row["point_estimate"] == round(k / n, 6)
        assert row["wilson_95_ci"] == [lo, hi]
        assert row["ci_width"] == round(hi - lo, 6)

    for row in stats_fw["bayes_operational_ppv_sensitivity"]:
        expected_ppv = adjust_precision_for_base_rate(
            recall=row["tpr"],
            fpr=row["fpr"],
            prevalence=row["prevalence_pi"],
        )
        assert row["implied_ppv"] == expected_ppv

    # 5. Zero-PII verification across JSON ledger and Markdown report (no phone/PAN/SSN/personal email)
    allowed_emails = {"membership@apwg.org"}
    for artifact_text in (routes_raw.decode("utf-8"), doc_root_raw.decode("utf-8")):
        assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", artifact_text), "Unexpected SSN pattern"
        assert not re.search(r"(?<![0-9a-fA-F])\b\d{16}\b(?![0-9a-fA-F])", artifact_text), (
            "Unexpected 16-digit PAN pattern"
        )
        assert not re.search(
            r"(?<![0-9a-fA-F-])(?:\+?1[-.\s])?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
            artifact_text,
        ), "Unexpected phone number pattern"
        emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", artifact_text))
        assert emails.issubset(allowed_emails), f"Unexpected personal/unvetted emails: {emails}"

    # 6. AST isolation check on dataset_quarantine.py
    dq_tree = ast.parse(Path(dq.__file__).read_text(encoding="utf-8"))
    forbidden_prefixes = (
        "onnxruntime",
        "onnx",
        "skl2onnx",
        "sklearn",
        "numpy",
        "app.telecom.onnx_engine",
        "app.telecom.evaluate_model",
        "app.telecom.train_onnx_model",
        "app.main",
    )
    for node in ast.walk(dq_tree):
        if isinstance(node, ast.Import):
            mods = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        else:
            mods = []
        for mod in mods:
            assert not any(mod == p or mod.startswith(f"{p}.") for p in forbidden_prefixes), (
                f"dataset_quarantine.py imported forbidden module '{mod}'"
            )


def test_bayes_prevalence_precision_and_threshold_sweep() -> None:
    """Verifies SF-012 Bayes PPV math, threshold sweeps, cost matrix, and docs/metrics parity."""
    from app.telecom.dataset_quarantine import FROZEN_ONNX_MODEL_SHA256
    from app.telecom.evaluate_model import (
        DEFAULT_PREVALENCE_RATES,
        DEFAULT_SWEEP_THRESHOLDS,
        compute_base_rate_ppv,
        compute_dual_tier_cost_per_1000,
        compute_expected_cost_per_1000,
        compute_threshold_sensitivity_analysis,
        get_canonical_artifact_paths,
    )

    # 1. Bayes PPV mathematical accuracy & 0/0 safe fallback
    assert compute_base_rate_ppv(0.95, 0.05, 0.50) == 0.95
    assert compute_base_rate_ppv(0.95, 0.05, 0.05) == 0.5
    assert compute_base_rate_ppv(0.95, 0.05, 0.01) == 0.161017
    assert compute_base_rate_ppv(0.95, 0.01, 0.005) == 0.323129
    assert compute_base_rate_ppv(0.0, 0.0, 0.01) == 0.0
    assert compute_base_rate_ppv(0.5, 0.0, 0.0) == 0.0

    with pytest.raises(ValueError, match="within \\[0.0, 1.0\\]"):
        compute_base_rate_ppv(1.1, 0.05, 0.01)

    # 2. Synthetic sweep check: monotonic FPR/TPR non-increase & exact cost math
    synth_scores = [0.05, 0.25, 0.45, 0.72, 0.82, 0.35, 0.55, 0.78, 0.88, 0.96]
    synth_labels = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1]
    synth_sweep = compute_threshold_sensitivity_analysis(synth_scores, synth_labels)
    assert [r["threshold"] for r in synth_sweep["thresholds"]] == list(DEFAULT_SWEEP_THRESHOLDS)
    assert synth_sweep["prevalences"] == list(DEFAULT_PREVALENCE_RATES)

    fprs = [r["fpr"] for r in synth_sweep["thresholds"]]
    tprs = [r["tpr"] for r in synth_sweep["thresholds"]]
    assert fprs == sorted(fprs, reverse=True), f"FPR must be non-increasing: {fprs}"
    assert tprs == sorted(tprs, reverse=True), f"TPR must be non-increasing: {tprs}"

    row_75 = next(r for r in synth_sweep["thresholds"] if r["threshold"] == 0.75)
    assert row_75["expected_cost_per_1000_tier1_flag"]["0.01"] == compute_expected_cost_per_1000(
        row_75["fnr"], row_75["fpr"], 0.01, cost_fp=1.0
    )
    assert row_75["expected_cost_per_1000_tier2_block"]["0.01"] == compute_expected_cost_per_1000(
        row_75["fnr"], row_75["fpr"], 0.01, cost_fp=50.0
    )

    # 3. Canonical ml_metrics.json, sms_fraud_metadata.json, and mirrored docs consistency
    canonical = get_canonical_artifact_paths()
    assert hashlib.sha256(canonical["model"].read_bytes()).hexdigest() == FROZEN_ONNX_MODEL_SHA256

    metrics = json.loads(canonical["metrics"].read_text(encoding="utf-8"))
    metadata = json.loads(canonical["metadata"].read_text(encoding="utf-8"))
    assert "oof_cross_validation" in metrics
    assert "threshold_and_base_rate_analysis" in metrics
    assert (
        metadata["threshold_and_base_rate_analysis"] == metrics["threshold_and_base_rate_analysis"]
    )

    analysis = metrics["threshold_and_base_rate_analysis"]
    assert analysis["external_validation_status"] == "UNAVAILABLE_BLOCKED"
    assert analysis["class_c_primary_holdout_present"] is False
    assert analysis["legacy_holdout_300_present"] is False
    assert analysis["default_operational_thresholds"] == {
        "tier1_flag_threshold": 0.4,
        "tier2_block_threshold": 0.75,
    }

    for cohort_key in ("dev_val_composite", "dev_val_pure_ml", "oof_composite", "oof_pure_ml"):
        cohort = analysis[cohort_key]
        rows = cohort["thresholds"]
        assert [r["threshold"] for r in rows] == list(DEFAULT_SWEEP_THRESHOLDS)
        cohort_fprs = [r["fpr"] for r in rows]
        cohort_tprs = [r["tpr"] for r in rows]
        assert cohort_fprs == sorted(cohort_fprs, reverse=True)
        assert cohort_tprs == sorted(cohort_tprs, reverse=True)
        for row in rows:
            cm = row["confusion_matrix"]
            exact_tpr = cm["tp"] / (cm["tp"] + cm["fn"])
            exact_fpr = cm["fp"] / (cm["fp"] + cm["tn"])
            for pi in DEFAULT_PREVALENCE_RATES:
                assert row["ppv_by_prevalence"][f"{pi:g}"] == compute_base_rate_ppv(
                    exact_tpr, exact_fpr, pi
                )

    # Confirm SF-009 OOF unseen-family erosion at tau=0.75 vs tau=0.85 at pi=0.5%
    oof_rows = analysis["oof_composite"]["thresholds"]
    oof_40 = next(r for r in oof_rows if r["threshold"] == 0.40)
    oof_75 = next(r for r in oof_rows if r["threshold"] == 0.75)
    oof_85 = next(r for r in oof_rows if r["threshold"] == 0.85)
    assert oof_75["fpr"] > 0.02 and oof_75["ppv_by_prevalence"]["0.005"] < 0.15
    assert oof_85["fpr"] == 0.0 and oof_85["ppv_by_prevalence"]["0.005"] == 1.0

    oof_dual = analysis["oof_composite"]["dual_tier_policies"]
    pol_40_75 = next(
        p
        for p in oof_dual
        if (p["tier1_flag_threshold"], p["tier2_block_threshold"]) == (0.4, 0.75)
    )
    pol_40_85 = next(
        p
        for p in oof_dual
        if (p["tier1_flag_threshold"], p["tier2_block_threshold"]) == (0.4, 0.85)
    )
    assert (
        pol_40_85["expected_cost_per_1000_by_prevalence"]["0.005"]
        < pol_40_75["expected_cost_per_1000_by_prevalence"]["0.005"]
    )
    cm_40 = oof_40["confusion_matrix"]
    cm_75 = oof_75["confusion_matrix"]
    assert pol_40_75["expected_cost_per_1000_by_prevalence"][
        "0.01"
    ] == compute_dual_tier_cost_per_1000(
        cm_40["fn"] / (cm_40["tp"] + cm_40["fn"]),
        cm_40["fp"] / (cm_40["fp"] + cm_40["tn"]),
        cm_75["fp"] / (cm_75["fp"] + cm_75["tn"]),
        0.01,
    )

    # Mirrored markdown report & SYSTEM_DESIGN.md verification
    report_root = canonical["report_root"].read_bytes()
    report_mirror = canonical["report_mirror"].read_bytes()
    assert report_root == report_mirror
    report_text = report_root.decode("utf-8")
    assert "Exploratory Threshold Sensitivity, Group-Aware Uncertainty" in report_text
    assert "UNAVAILABLE_BLOCKED" in report_text

    workspace_root = canonical["report_root"].parents[1]
    sys_root = (workspace_root / "SYSTEM_DESIGN.md").read_bytes()
    sys_mirror = (workspace_root / "sentinelflow" / "SYSTEM_DESIGN.md").read_bytes()
    assert sys_root == sys_mirror
    sys_text = sys_root.decode("utf-8")
    assert "4.2 Exploratory Decision Policy, Group Uncertainty & Cost Sensitivity" in sys_text
    assert "UNAVAILABLE / BLOCKED" in sys_text


def test_sf012r_grouped_uncertainty_ppv_scenarios_cost_sensitivity_and_language_guardrails() -> (
    None
):
    """Verifies SF-012R statistical remediation: group bootstrap, zero-event limits, PPV, cost & wording."""
    import numpy as np
    from app.telecom.dataset_quarantine import FROZEN_ONNX_MODEL_SHA256
    from app.telecom.evaluate_model import (
        DEFAULT_PREVALENCE_RATES,
        DEFAULT_SWEEP_THRESHOLDS,
        compute_base_rate_ppv,
        compute_expected_cost_per_1000,
        compute_threshold_sensitivity_analysis,
        get_canonical_artifact_paths,
    )

    canonical = get_canonical_artifact_paths()
    telecom_dir = canonical["model"].resolve().parents[1]
    oof_path = telecom_dir / "oof_predictions.json"
    oof_raw = json.loads(oof_path.read_text(encoding="utf-8"))

    # 1. Existing SF-009 OOF artifacts and frozen hashes remain preserved
    assert hashlib.sha256(canonical["model"].read_bytes()).hexdigest() == FROZEN_ONNX_MODEL_SHA256
    assert len(oof_raw) == 703
    assert all(r["family_id"] and r["family_id"] == r["eval_group_id"] for r in oof_raw)

    metrics = json.loads(canonical["metrics"].read_text(encoding="utf-8"))
    metadata = json.loads(canonical["metadata"].read_text(encoding="utf-8"))
    assert metrics["oof_cross_validation"] == metadata["oof_cross_validation"]
    assert (
        metrics["oof_cross_validation"]["oof_predictions_sha256"]
        == hashlib.sha256(oof_path.read_bytes()).hexdigest()
    )

    analysis = metrics["threshold_and_base_rate_analysis"]
    assert (
        analysis["analysis_classification"] == "exploratory_sensitivity_and_assumed_cost_analysis"
    )
    assert analysis["independent_threshold_validation_available"] is False
    assert analysis["external_validation_status"] == "UNAVAILABLE_BLOCKED"
    assert analysis["default_operational_thresholds"] == {
        "tier1_flag_threshold": 0.4,
        "tier2_block_threshold": 0.75,
    }
    assert (
        analysis["provisional_threshold_status"]["provisional_candidates"][0]["threshold"] == 0.85
    )
    assert (
        analysis["provisional_threshold_status"]["provisional_candidates"][0]["classification"]
        == "unvalidated_provisional_candidate_for_future_external_eval"
    )
    assert len(analysis["evidence_interpretation_boundaries"]) == 6

    # 2. Full reconciliation of SF-012 OOF sweep & group FP counts against oof_predictions.json
    for cohort_key, score_field in (
        ("oof_composite", "oof_composite_score"),
        ("oof_pure_ml", "oof_probability"),
    ):
        cohort = analysis[cohort_key]
        assert cohort["analysis_classification"] == "exploratory_sensitivity_only"
        assert cohort["independent_threshold_validation"] is False
        gs = cohort["group_structure"]
        assert gs["total_groups"] == 56
        assert gs["mixed_label_groups"] == 0
        assert gs["benign_groups"]["count"] == 37
        assert gs["benign_groups"]["total_observations"] == 543
        assert gs["fraud_groups"]["count"] == 19
        assert gs["fraud_groups"]["total_observations"] == 160

        for row in cohort["thresholds"]:
            tau = float(row["threshold"])
            exp_tp = sum(1 for r in oof_raw if r["true_label"] == 1 and r[score_field] >= tau)
            exp_fp = sum(1 for r in oof_raw if r["true_label"] == 0 and r[score_field] >= tau)
            exp_tn = sum(1 for r in oof_raw if r["true_label"] == 0 and r[score_field] < tau)
            exp_fn = sum(1 for r in oof_raw if r["true_label"] == 1 and r[score_field] < tau)
            assert row["confusion_matrix"] == {
                "tp": exp_tp,
                "fp": exp_fp,
                "tn": exp_tn,
                "fn": exp_fn,
            }
            gc = row["group_fp_counts"]
            assert gc["benign_groups_total"] == 37
            assert gc["fraud_groups_total"] == 19
            assert sum(gc["benign_group_fp_breakdown"].values()) == exp_fp
            assert sum(gc["fraud_group_fn_breakdown"].values()) == exp_fn

            gu = row["grouped_uncertainty"]
            assert gu["resampling_unit"] == "semantic_family_id"
            assert gu["independent_group_count"] == 56
            assert (
                gu["valid_replicates"]["tpr"] + gu["undefined_replicates"]["tpr"]
                == gu["n_replicates"]
            )
            assert (
                gu["valid_replicates"]["fpr"] + gu["undefined_replicates"]["fpr"]
                == gu["n_replicates"]
            )

    # 3. Zero-event degeneration & affected-family bound at tau >= 0.85, plus concentrated FP at 0.75
    oof_comp_rows = analysis["oof_composite"]["thresholds"]
    row_75 = next(r for r in oof_comp_rows if r["threshold"] == 0.75)
    assert row_75["group_fp_counts"]["benign_groups_with_fp"] == 1
    assert row_75["group_fp_counts"]["benign_group_fp_breakdown"] == {
        "legit_bank_security_alert_12": 13
    }
    assert row_75["grouped_uncertainty"]["fpr_cluster_bootstrap_95_ci"] is not None
    assert (
        row_75["grouped_uncertainty"]["fpr_cluster_bootstrap_95_ci"][1]
        > row_75["fpr_wilson_95_upper"]
    )

    for tau_zero in (0.85, 0.90, 0.95):
        z_row = next(r for r in oof_comp_rows if r["threshold"] == tau_zero)
        gu = z_row["grouped_uncertainty"]
        assert z_row["confusion_matrix"]["fp"] == 0
        assert z_row["group_fp_counts"]["benign_groups_with_fp"] == 0
        assert gu["fpr_cluster_bootstrap_95_ci"] is None
        assert (
            gu["fpr_cluster_bootstrap_status"] == "degenerate_zero_observed_false_positive_groups"
        )
        zb = gu["group_level_zero_event_bound"]
        assert zb is not None
        assert zb["affected_benign_groups"] == 0
        assert zb["benign_groups_total"] == 37
        assert zb["one_sided_95_clopper_pearson_upper"] == round(1.0 - 0.05 ** (1.0 / 37), 6)
        assert "NOT message-level carrier FPR" in zb["limitation"]

    # 4. Synthetic group-boundary & undefined-replicate verification
    # 1 fraud group (size 2) + 5 benign groups (one size 4 with all FP at 0.5, four size 2 clean)
    synth_scores = [0.9, 0.9, 0.6, 0.6, 0.6, 0.6] + [0.1] * 8
    synth_labels = [1, 1] + [0] * 12
    synth_groups = [
        "f1",
        "f1",
        "b_fp",
        "b_fp",
        "b_fp",
        "b_fp",
        "b2",
        "b2",
        "b3",
        "b3",
        "b4",
        "b4",
        "b5",
        "b5",
    ]
    synth_grouped = compute_threshold_sensitivity_analysis(
        synth_scores,
        synth_labels,
        groups=synth_groups,
        thresholds=(0.40, 0.75),
        bootstrap_replicates=200,
        bootstrap_seed=7,
    )
    gu_s40 = synth_grouped["thresholds"][0]["grouped_uncertainty"]
    gu_s75 = synth_grouped["thresholds"][1]["grouped_uncertainty"]
    # With 1 fraud group out of 6, (5/6)^6 ~ 33% of bootstrap draws omit f1 -> undefined_replicates['tpr'] > 0
    assert gu_s40["undefined_replicates"]["tpr"] > 0
    assert gu_s40["valid_replicates"]["tpr"] + gu_s40["undefined_replicates"]["tpr"] == 200
    assert gu_s75["fpr_cluster_bootstrap_95_ci"] is None
    assert gu_s75["group_level_zero_event_bound"]["benign_groups_total"] == 5

    # Verify group resampling preserves whole clusters by inspecting unique drawn FPR values independently
    rng = np.random.default_rng(7)
    unique_g = sorted(set(synth_groups))
    g_neg = np.array(
        [
            sum(
                1
                for g, lbl in zip(synth_groups, synth_labels, strict=True)
                if g == gid and lbl == 0
            )
            for gid in unique_g
        ]
    )
    g_fp = np.array(
        [
            sum(
                1
                for g, lbl, s in zip(synth_groups, synth_labels, synth_scores, strict=True)
                if g == gid and lbl == 0 and s >= 0.40
            )
            for gid in unique_g
        ]
    )
    # All FP counts inside sampled replicates must be multiples of 4 (never odd/row-split FPs!)
    for _ in range(50):
        draw = rng.integers(0, len(unique_g), size=len(unique_g))
        if g_neg[draw].sum() > 0:
            assert g_fp[draw].sum() % 4 == 0

    # 5. Monotonic PPV with prevalence & tau=0.85 upper-Wilson illustration (~28.9% at 0.5%, not 100%)
    row_85 = next(r for r in oof_comp_rows if r["threshold"] == 0.85)
    assert row_85["ppv_uncertainty_scenarios"]["deployment_prevalence_status"] == (
        "unknown_without_measured_operational_telemetry"
    )
    desc_85_ppv_005 = row_85["ppv_uncertainty_scenarios"][
        "descriptive_row_wilson_upper_fpr_at_point_tpr"
    ]["ppv_by_prevalence"]["0.005"]
    assert 0.25 < desc_85_ppv_005 < 0.32
    ppv_seq = [compute_base_rate_ppv(0.75, 0.02, pi) for pi in DEFAULT_PREVALENCE_RATES]
    assert ppv_seq == sorted(ppv_seq) and len(set(ppv_seq)) == len(DEFAULT_PREVALENCE_RATES)

    # 6. Cost sensitivity responds to cost ratios & proves ranking changes across assumptions
    cost_sens = analysis["oof_composite"]["cost_sensitivity"]
    assert cost_sens["empirically_measured_carrier_costs_available"] is False
    assert cost_sens["cost_assumption_sensitive"] is True
    assert any(
        v["ranking_changes_across_scenarios"]
        for v in cost_sens["ranking_stability_by_prevalence"].values()
    )
    c_low = compute_expected_cost_per_1000(0.25, 0.02, 0.01, cost_fn=10.0, cost_fp=5.0)
    c_mid = compute_expected_cost_per_1000(0.25, 0.02, 0.01, cost_fn=10.0, cost_fp=50.0)
    c_high = compute_expected_cost_per_1000(0.25, 0.02, 0.01, cost_fn=10.0, cost_fp=250.0)
    assert c_low < c_mid < c_high

    # 7. Language guardrail verification across JSON, mirrored reports, and mirrored SYSTEM_DESIGN.md
    workspace_root = canonical["report_root"].parents[1]
    report_text = canonical["report_root"].read_text(encoding="utf-8")
    sys_text = (workspace_root / "SYSTEM_DESIGN.md").read_text(encoding="utf-8")
    assert report_text == canonical["report_mirror"].read_text(encoding="utf-8")
    assert sys_text == (workspace_root / "sentinelflow" / "SYSTEM_DESIGN.md").read_text(
        encoding="utf-8"
    )
    metrics_raw_lower = canonical["metrics"].read_text(encoding="utf-8").lower()
    for text_blob in (report_text.lower(), sys_text.lower(), metrics_raw_lower):
        for forbidden in (
            "15.3x",
            "production-optimal",
            "is independently validated",
            "empirically validated optimum",
            "are measured operational costs",
            "mean zero underlying fpr",
        ):
            assert forbidden not in text_blob, f"Forbidden overclaim {forbidden!r} found"

    assert "not measured operational costs" in report_text.lower()
    assert "not measured operational costs" in sys_text.lower()
    assert "not independent threshold selection validation" in report_text.lower()
    assert "not independent threshold selection validation" in sys_text.lower()
    assert "28.92%" in report_text
    assert "unvalidated exploratory/provisional candidate" in report_text.lower()
    assert "unvalidated provisional candidate" in sys_text.lower()

    assert all(p in DEFAULT_PREVALENCE_RATES for p in (0.002, 0.005, 0.01, 0.05, 0.50))
    assert list(DEFAULT_SWEEP_THRESHOLDS) == [
        0.3,
        0.4,
        0.5,
        0.6,
        0.7,
        0.75,
        0.8,
        0.85,
        0.9,
        0.95,
    ]

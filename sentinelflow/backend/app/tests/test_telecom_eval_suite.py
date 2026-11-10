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

    expected_ece = (2 / 5) * abs(0.0495 - 0.0) + (1 / 5) * abs(0.1 - 0.0) + (2 / 5) * abs(0.95 - 1.0)
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




"""Unit and regression tests for the SentinelPulse Empirical ML Evaluation Suite.

Verifies reproducibility metadata, category breakdowns, component ablations,
error analysis extraction, and operational dual-tier thresholds.
"""

from __future__ import annotations

import hashlib

import numpy as np
from app.telecom.evaluate_model import (
    compute_ablation_metrics,
    compute_category_metrics,
    evaluate_onnx_model,
    extract_error_analysis,
    generate_markdown_report,
    get_benchmark_evaluation_set,
    get_held_out_evaluation_set,
    get_held_out_samples_with_metadata,
)


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

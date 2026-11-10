"""Forensic security, adversarial, complexity, mutation & integrity tests (SF-005).

Complements `test_telecom_gateway.py` without contaminating `Dev/Val` N=400
or training datasets. Executes under strict offline/deterministic contracts.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import httpx
import pytest
from app.main import app
from app.telecom import onnx_engine
from app.telecom.evaluate_model import (
    _compute_verdict,
    get_held_out_samples_with_metadata,
)
from app.telecom.onnx_engine import (
    HEURISTIC_RULES,
    compute_composite_score,
    evaluate_heuristics,
    get_inference_engine,
    normalize_heuristic_text,
)
from app.telecom.train_onnx_model import build_augmented_dataset
from app.tests.telecom_adversarial_fixtures import (
    ADVERSARIAL_CORPUS,
    DROPPED_CLAUSE_CORPUS,
    evaluate_adversarial_suite,
    normalized_sha256,
)


def _tax_rule_pattern() -> re.Pattern[str]:
    """Returns the compiled RULE:TAX_ARREST_THREAT regex pattern."""
    for name, pattern, _ in HEURISTIC_RULES:
        if name == "RULE:TAX_ARREST_THREAT":
            return pattern
    raise AssertionError("RULE:TAX_ARREST_THREAT missing from HEURISTIC_RULES")


def _min_per_call_ms(pattern: re.Pattern[str], text: str, rounds: int = 3, iters: int = 120) -> float:
    """Measures minimum per-call latency in ms across repeated batches to reject OS jitter."""
    best = float("inf")
    for _ in range(rounds):
        t0 = time.perf_counter()
        for _ in range(iters):
            pattern.search(text)
        elapsed_ms = ((time.perf_counter() - t0) * 1000.0) / iters
        if elapsed_ms < best:
            best = elapsed_ms
    return best


def test_adversarial_corpus_zero_leakage_against_dev_val_and_training() -> None:
    """Enforces 100% separation between synthetic adversarial fixtures, Dev/Val, and train data."""
    all_fixture_texts = [case.text for case in ADVERSARIAL_CORPUS] + [
        case.text for case in DROPPED_CLAUSE_CORPUS
    ]
    adv_hashes = {normalized_sha256(txt) for txt in all_fixture_texts}
    assert len(adv_hashes) == len(all_fixture_texts), "Duplicate texts in adversarial corpora"

    dev_val_hashes = {
        normalized_sha256(sample["text"]): idx
        for idx, sample in enumerate(get_held_out_samples_with_metadata())
    }
    train_texts, _, _ = build_augmented_dataset()
    train_hashes = {normalized_sha256(txt) for txt in train_texts}

    overlap_dev_val = adv_hashes.intersection(dev_val_hashes)
    overlap_train = adv_hashes.intersection(train_hashes)

    assert not overlap_dev_val, f"Leakage into Dev/Val benchmark: {overlap_dev_val}"
    assert not overlap_train, f"Leakage into training dataset: {overlap_train}"


def test_dropped_clause_adversarial_and_benign_contrastive_matrix() -> None:
    """Verifies dropped-clause coercion detection vs benign/ambiguous precision (SF-005B)."""
    engine = get_inference_engine()

    observed: dict[str, dict[str, object]] = {}
    for case in DROPPED_CLAUSE_CORPUS:
        res = engine.predict(case.text)
        tax_hit = "RULE:TAX_ARREST_THREAT" in res.signals
        observed[case.case_id] = {
            "verdict": res.verdict,
            "tax_hit": tax_hit,
            "fraud_score": res.fraud_score,
            "heuristic_score": res.heuristic_score,
            "onnx_probability": res.onnx_probability,
        }
        assert tax_hit is case.expected_tax_rule_match, (
            f"{case.case_id} expected tax_hit={case.expected_tax_rule_match}, "
            f"got {tax_hit} (signals={res.signals})"
        )
        assert res.verdict in case.allowed_verdicts, (
            f"{case.case_id} verdict {res.verdict} not in allowed {case.allowed_verdicts} "
            f"(S={res.fraud_score})"
        )

    # Confirm explicit behavior across all 6 adversarial & 7 benign cases
    assert observed["DC01"]["verdict"] == "FLAG"
    assert observed["DC02"]["verdict"] == "ALLOW"
    assert observed["DC03"]["verdict"] == "BLOCK"
    assert observed["DC04"]["verdict"] == "ALLOW"  # Documented 3-clause boundary limit
    assert observed["DC05"]["verdict"] == "BLOCK"
    assert observed["DC06"]["verdict"] == "BLOCK"
    for benign_id in ("DC_B01", "DC_B02", "DC_B03", "DC_B04", "DC_B05", "DC_B06"):
        assert observed[benign_id]["tax_hit"] is False
        assert observed[benign_id]["verdict"] == "ALLOW"
    assert observed["DC_B07"]["tax_hit"] is False
    assert observed["DC_B07"]["heuristic_score"] == 0.0
    assert observed["DC_B07"]["verdict"] != "BLOCK"


def test_adversarial_suite_categories_and_evidence_honesty() -> None:
    """Verifies Category A-E behavior cleanly while reporting honest evidence classes & gaps."""
    report = evaluate_adversarial_suite()

    assert report["external_validation_status"] == (
        "Outstanding (Evidence Class D: None — synthetic only)"
    )
    assert report["total_cases"] == len(ADVERSARIAL_CORPUS)

    results_by_cat = report["results"]
    assert isinstance(results_by_cat, dict)

    # Category A: All 15 legitimate legal/tax/court/police texts must NEVER trigger
    # RULE:TAX_ARREST_THREAT or a Tier-2 BLOCK (verifying fixes for A01, A02, A03).
    cat_a = {row["case_id"]: row for row in results_by_cat["A"]}
    for cid, row in cat_a.items():
        assert row["tax_rule_matched"] is False, f"{cid} triggered TAX_ARREST_THREAT: {row}"
        assert row["heuristic_score"] <= 0.25, f"{cid} exceeded helper H<=0.25: {row}"
        assert row["verdict"] != "BLOCK", f"{cid} falsely BLOCKed: {row}"
    for remediated_id in ("A01", "A02", "A03"):
        assert cat_a[remediated_id]["heuristic_score"] == 0.0

    # Category B: Benign messages with suspicious words never hit TAX_ARREST_THREAT or BLOCK.
    cat_b = {row["case_id"]: row for row in results_by_cat["B"]}
    for cid, row in cat_b.items():
        assert row["tax_rule_matched"] is False, f"{cid} triggered TAX_ARREST_THREAT: {row}"
        assert row["verdict"] != "BLOCK", f"{cid} falsely BLOCKed: {row}"
    # Documented residual heuristic gap in sibling rule RULE:SIM_SWAP_OR_KYC_SCAM (see audit doc)
    assert "RULE:SIM_SWAP_OR_KYC_SCAM" in cat_b["B03"]["signals"]

    # Category C: 100% Tier-1+2 recall and >= 80% Tier-2 recall; C01 (800) callback fixed.
    binary_cats = report["binary_categories"]
    assert isinstance(binary_cats, dict)
    c_summary = binary_cats["C"]
    assert isinstance(c_summary, dict)
    assert c_summary["tier1_flag_or_block"]["recall"] == 1.0
    assert c_summary["tier2_block_only"]["recall"] >= 0.80

    cat_c = {row["case_id"]: row for row in results_by_cat["C"]}
    assert cat_c["C01"]["tax_rule_matched"] is True
    assert cat_c["C01"]["verdict"] == "BLOCK"
    assert cat_c["C02"]["tax_rule_matched"] is True
    assert cat_c["C02"]["verdict"] == "BLOCK"

    # Category D: Unicode zero-width, soft-hyphen, fullwidth NFKC, word-order, salting hold BLOCK.
    cat_d = {row["case_id"]: row for row in results_by_cat["D"]}
    for invariant_id in ("D01", "D02", "D03", "D04", "D05", "D06", "D07"):
        assert cat_d[invariant_id]["tax_rule_matched"] is True, f"{invariant_id} missed rule"
        assert cat_d[invariant_id]["verdict"] == "BLOCK", f"{invariant_id} dropped from BLOCK"

    # Honest documentation of lexical evasion probes (Cyrillic homoglyph / leetspeak / spaced URL)
    assert cat_d["D08"]["tax_rule_matched"] is False
    assert cat_d["D09"]["tax_rule_matched"] is False
    assert cat_d["D10"]["tax_rule_matched"] is False

    # Category E: Ambiguous cases yield deterministic finite scores without crashing.
    for row in results_by_cat["E"]:
        assert row["verdict"] in ("ALLOW", "FLAG", "BLOCK")
        assert 0.0 <= float(row["fraud_score"]) <= 1.0


def test_heuristic_pathological_edge_inputs() -> None:
    """Verifies safe bounded execution on empty, invisible-only, long, and noisy inputs."""
    engine = get_inference_engine()

    edge_inputs = [
        "",
        "    \t\r\n  ",
        "\u200b\u200c\u200d\ufeff\u00ad",
        "..." * 500,
        ("Attorney office routine tax notice review without demands. " * 29)[:1600],
        ("Police court warrant schedule update notice. " * 75)[:3200],
        '"IRS FINAL NOTICE"\n\t\r\n"Test line 2"\n"Regular mail receipt"',
    ]

    for idx, text in enumerate(edge_inputs):
        normalized = normalize_heuristic_text(text)
        assert isinstance(normalized, str)
        h_score, signals = evaluate_heuristics(text)
        assert 0.0 <= h_score <= 0.95, f"Out-of-bounds heuristic score at edge {idx}: {h_score}"
        assert isinstance(signals, list)

        res = engine.predict(text if text else " ")
        assert res.verdict in ("ALLOW", "FLAG", "BLOCK")
        assert 0.0 <= res.fraud_score <= 1.0


def test_tax_arrest_threat_linear_time_scaling() -> None:
    """Proves anchored RULE:TAX_ARREST_THREAT scales O(N) without quadratic ReDoS backtracking."""
    tax_pat = _tax_rule_pattern()

    fillers = {
        "lookahead_1_2_pass_3_fail": "police arrest warrant tax call ",
        "near_miss_unpaid_call": "unpaid back arrest warrant irs case #123 call ",
        "near_miss_pay_prefix": "pay federal court arrest warrant irs final notice ",
        "long_benign_legal": "Lawyer confirmed court date scheduled with attorney and IRS check. ",
    }

    for name, filler in fillers.items():
        short_input = (filler * 60)[:400]
        long_input = (filler * 250)[:3200]

        t_400 = _min_per_call_ms(tax_pat, short_input)
        t_3200 = _min_per_call_ms(tax_pat, long_input)

        # Across an 8x length jump (400 -> 3200), O(N) scaling is ~8x (vs O(N^2) ~64x).
        growth_ratio = t_3200 / max(t_400, 1e-4)
        assert t_3200 < 2.5, f"{name} exceeded 2.5ms at N=3200: {t_3200:.4f}ms"
        assert growth_ratio < 16.0, (
            f"{name} exhibits super-linear scaling (400={t_400:.4f}ms -> 3200={t_3200:.4f}ms, "
            f"ratio={growth_ratio:.2f}x)"
        )


def test_mutation_suite_kills_predicate_and_threshold_regressions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies our test invariants reliably FAIL under targeted rule & scoring mutations."""
    tax_pat_str = _tax_rule_pattern().pattern
    re_flags = re.IGNORECASE | re.DOTALL

    # Helper extracting the 3 top-level anchored lookaheads from RULE:TAX_ARREST_THREAT:
    # r"^(?=.*\b(?:...)\b)(?=.*\b(?:...)\b)(?=.*(...))"
    # Instead of brittle string slicing, define minimal targeted mutations against rule text:

    # Mutation 1: Removing authority lookahead breaks non-authority threat+demand benign text.
    authority_slice = (
        r"(?=.*\b(?:irs|customs|magistrate|sheriff|police|court(?:house)?|judge|"
        r"federal\s+(?:tax|agent|court|marshal|enforcement|bureau)|"
        r"tax\w*|delinquent|warrant|process\s+server|lawsuit|enforcement)\b)"
    )
    assert authority_slice in tax_pat_str
    mutated_no_auth = re.compile(tax_pat_str.replace(authority_slice, ""), re_flags)
    benign_no_auth = "In Monopoly, you must pay $50 fine to avoid jail within 2 turns."
    assert _tax_rule_pattern().search(benign_no_auth) is None
    assert mutated_no_auth.search(benign_no_auth) is not None, "Mutation 1 survived!"

    # Mutation 2: Removing coercion threat lookahead breaks benign IRS tax balance notice.
    benign_no_threat = "CPA Summary: IRS recorded your unpaid tax balance for tax season planning."
    coercion_prefix = r"^(?=.*\b(?:arrest\s+warrant|"
    assert coercion_prefix in tax_pat_str
    # Strip lookahead 1 up to authority_slice cleanly
    idx_auth = tax_pat_str.index(authority_slice)
    mutated_no_threat = re.compile("^" + tax_pat_str[idx_auth:], re_flags)
    assert _tax_rule_pattern().search(benign_no_threat) is None
    assert mutated_no_threat.search(benign_no_threat) is not None, "Mutation 2 survived!"

    # Mutation 3: Removing extortion demand lookahead breaks Sample-184/police dispatch reports.
    benign_no_demand = (
        "Neighborhood alert: Police dispatched two patrol officers near the sheriff courthouse."
    )
    demand_marker = r"(?=.*(?:"
    idx_demand = tax_pat_str.index(demand_marker)
    mutated_no_demand = re.compile(tax_pat_str[:idx_demand], re_flags)
    assert _tax_rule_pattern().search(benign_no_demand) is None
    assert mutated_no_demand.search(benign_no_demand) is not None, "Mutation 3 survived!"

    # Mutation 4: Restoring bare "final notice" in Lookahead 1 falsely blocks routine legal/tax
    # billing notices (4a), and reverting the combined SF-005 hardening breaks A01 and A02 (4b).
    fta_slice = r"failure\s+to\s+appear|contempt\s+of\s+court"
    assert fta_slice in tax_pat_str
    mutated_bare_final_notice = re.compile(
        tax_pat_str.replace(fta_slice, r"final\s+notice"),
        re_flags,
    )
    benign_billing_final_notice = "IRS Final Notice: Pay balance due for quarterly voucher Q2."
    assert _tax_rule_pattern().search(benign_billing_final_notice) is None
    assert (
        mutated_bare_final_notice.search(benign_billing_final_notice) is not None
    ), "Mutation 4a survived!"

    abatement_guard = r"(?!\s+(?:abatement|relief|waiver))"
    unless_slice = r"unless\s+(?:paid|settled|resolved|verified)"
    assert abatement_guard in tax_pat_str and unless_slice in tax_pat_str
    mutated_pre_hardening_cpa = re.compile(
        tax_pat_str.replace(fta_slice, r"final\s+notice")
        .replace(abatement_guard, "")
        .replace(unless_slice, r"case\s*#\s*[a-z0-9\-]+"),
        re_flags,
    )
    a01_text = ADVERSARIAL_CORPUS[0].text
    a02_text = ADVERSARIAL_CORPUS[1].text
    assert _tax_rule_pattern().search(a01_text) is None
    assert _tax_rule_pattern().search(a02_text) is None
    assert mutated_pre_hardening_cpa.search(a01_text) is not None, "Mutation 4b(A01) survived!"
    assert mutated_pre_hardening_cpa.search(a02_text) is not None, "Mutation 4b(A02) survived!"

    # Mutation 5: Restoring bare "case #" in Lookahead 3 breaks A03 (BENIGN_NEWS_ARTICLE).
    mutated_bare_case_id = re.compile(
        tax_pat_str.replace(unless_slice, r"case\s*#\s*[a-z0-9\-]+"),
        re_flags,
    )
    a03_text = ADVERSARIAL_CORPUS[2].text
    assert _tax_rule_pattern().search(a03_text) is None
    assert mutated_bare_case_id.search(a03_text) is not None, "Mutation 5 survived!"

    # Mutation 6: Removing parenthesized phone support breaks C01 without unpaid back taxes phrasing.
    c01_callback_only = (
        "IRS Notice: Federal arrest warrant active for your SSN. "
        "Call (800) 555-0199 right away."
    )
    paren_slice = r"(?:\(\d{3}\)|\d{3})"
    assert paren_slice in tax_pat_str
    mutated_no_paren = re.compile(
        tax_pat_str.replace(paren_slice, r"\d{3}"),
        re_flags,
    )
    assert _tax_rule_pattern().search(c01_callback_only) is not None
    assert mutated_no_paren.search(c01_callback_only) is None, "Mutation 6 survived!"

    # Mutation 7: Disabling zero-width Unicode normalization breaks D01 detection.
    d01_text = next(c.text for c in ADVERSARIAL_CORPUS if c.case_id == "D01")
    monkeypatch.setattr(onnx_engine, "normalize_heuristic_text", lambda text: text)
    h_unnorm, sigs_unnorm = evaluate_heuristics(d01_text)
    assert "RULE:TAX_ARREST_THREAT" not in sigs_unnorm and h_unnorm == 0.0, "Mutation 7 survived!"
    monkeypatch.undo()
    assert "RULE:TAX_ARREST_THREAT" in evaluate_heuristics(d01_text)[1]

    # Mutation 8: Dropping RULE:TAX_ARREST_THREAT weight < 0.80 causes low-ML extortion C02 to fail
    # Tier-2 BLOCK override (since P=0.2222 requires H >= 0.80 to hit S=1.0).
    assert compute_composite_score(0.80, 0.2222, 0.0) == 1.0
    assert compute_composite_score(0.75, 0.2222, 0.0) < 0.75, "Mutation 8 survived!"

    # Mutation 9: Removing +0.12 compound boost breaks S >= 0.80 override on two-rule phish.
    assert compute_composite_score(0.70 + 0.12, 0.10, 0.0) == 1.0
    assert compute_composite_score(0.70, 0.10, 0.0) < 0.75, "Mutation 9 survived!"

    # Mutation 10: Removing dropped-phone urgent CTA verbs ("contact us"/"reply"/"respond")
    # causes DC05 to fall out of TAX_ARREST_THREAT and regress to ALLOW.
    cta_slice = r"(?:call|contact\s+us|reply|respond)"
    assert cta_slice in tax_pat_str
    mutated_call_only_cta = re.compile(
        tax_pat_str.replace(cta_slice, "call"),
        re_flags,
    )
    dc05_text = next(c.text for c in DROPPED_CLAUSE_CORPUS if c.case_id == "DC05")
    assert _tax_rule_pattern().search(dc05_text) is not None
    assert mutated_call_only_cta.search(dc05_text) is None, "Mutation 10 survived!"


@pytest.mark.asyncio
async def test_runtime_classify_matches_offline_engine_and_rejects_oversize() -> None:
    """Verifies HTTP /v1/classify matches offline engine.predict() & enforces max_length=1600."""
    engine = get_inference_engine()
    samples = get_held_out_samples_with_metadata()

    probe_texts = [
        ("sample_184", samples[184]["text"]),
        ("A01", ADVERSARIAL_CORPUS[0].text),
        ("A03", ADVERSARIAL_CORPUS[2].text),
        ("C01", next(c.text for c in ADVERSARIAL_CORPUS if c.case_id == "C01")),
        ("D01", next(c.text for c in ADVERSARIAL_CORPUS if c.case_id == "D01")),
        ("E01", next(c.text for c in ADVERSARIAL_CORPUS if c.case_id == "E01")),
    ]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for idx, (label, text) in enumerate(probe_texts):
            offline_res = engine.predict(text)
            eval_score = round(
                compute_composite_score(
                    offline_res.heuristic_score,
                    offline_res.onnx_probability,
                    0.0,
                ),
                4,
            )
            assert _compute_verdict(eval_score) == offline_res.verdict

            # Unique fresh sender + standard carrier ensures V=0.0 matching offline baseline.
            resp = await client.post(
                "/v1/classify",
                json={
                    "sender": f"+1555888{idx:04d}",
                    "recipient": "+14155550101",
                    "message": text,
                    "carrier": "Verizon Wireless",
                    "escalate": False,
                },
            )
            assert resp.status_code == 200, f"{label} runtime failure: {resp.text}"
            payload = resp.json()
            assert payload["verdict"] == offline_res.verdict, f"{label} verdict drift"
            assert payload["fraud_score"] == pytest.approx(offline_res.fraud_score, abs=1e-4)

        # Verify API boundary enforces max_length=1600 with 422 Unprocessable Entity
        oversize_resp = await client.post(
            "/v1/classify",
            json={
                "sender": "+15558889999",
                "recipient": "+14155550101",
                "message": "x" * 1601,
                "carrier": "Verizon Wireless",
                "escalate": False,
            },
        )
        assert oversize_resp.status_code == 422


def test_evaluation_artifacts_integrity_and_parity() -> None:
    """Verifies committed benchmark JSON, metadata hashes, category sums, and dual docs."""
    telecom_dir = Path(onnx_engine.__file__).resolve().parent
    model_path = telecom_dir / "models" / "sms_fraud_model.onnx"
    metadata_path = telecom_dir / "models" / "sms_fraud_metadata.json"
    metrics_path = telecom_dir / "ml_metrics.json"
    predictions_path = telecom_dir / "benchmark_predictions_400.json"
    eval_report_root = telecom_dir.parents[3] / "docs" / "ml_evaluation_report.md"
    eval_report_mirror = telecom_dir.parents[2] / "docs" / "ml_evaluation_report.md"

    for artifact in (
        model_path,
        metrics_path,
        predictions_path,
        metadata_path,
        eval_report_root,
        eval_report_mirror,
    ):
        assert artifact.exists(), f"Missing committed artifact: {artifact}"

    model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
    bench_sha256 = hashlib.sha256(predictions_path.read_bytes()).hexdigest()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["model_sha256"] == model_sha256
    assert metadata["benchmark_predictions_sha256"] == bench_sha256

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    preds = json.loads(predictions_path.read_text(encoding="utf-8"))

    assert len(preds) == 400
    assert len({row["text_sha256"] for row in preds}) == 400
    assert all(row["verdict_match"] is True for row in preds)

    # Verify category sums match aggregate Tier-1 and Tier-2 confusion matrices
    categories = metrics["category_analysis"]["categories"]
    assert sum(cat["sample_count"] for cat in categories) == 400

    benign_t1_fp = sum(cat["tier1_flagged_count"] for cat in categories if cat["label"] == 0)
    fraud_t1_tp = sum(cat["tier1_flagged_count"] for cat in categories if cat["label"] == 1)
    benign_t2_fp = sum(cat["tier2_blocked_count"] for cat in categories if cat["label"] == 0)
    fraud_t2_tp = sum(cat["tier2_blocked_count"] for cat in categories if cat["label"] == 1)

    t1_cm = metrics["tier1_escalation"]["confusion_matrix"]
    t2_cm = metrics["tier2_block"]["confusion_matrix"]
    assert benign_t1_fp == t1_cm["fp"]
    assert fraud_t1_tp == t1_cm["tp"]
    assert benign_t2_fp == t2_cm["fp"]
    assert fraud_t2_tp == t2_cm["tp"]

    # Both committed Markdown evaluation reports must remain byte-for-byte identical
    assert eval_report_root.read_bytes() == eval_report_mirror.read_bytes()

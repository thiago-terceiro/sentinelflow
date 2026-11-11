"""External dataset provenance, suitability assessment, overlap auditing & quarantine (SF-010).

Strictly isolated from ONNX runtime, heuristic scoring, training pipelines, and thresholds so
ingestion and quarantine checks are completely blind to frozen model predictions.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# Frozen baseline checksums captured prior to SF-010 changes (must remain unchanged)
FROZEN_ONNX_MODEL_SHA256 = "d330466e8a28e43e4d8452fdef76f64470429851f19c568ea83399e7d16beaa9"
FROZEN_TRAINING_DATASET_SHA256 = "5bcedbea725ac6c5c2113bfdcf06ec5cb949afd92e556329a94567a8b8abb699"
FROZEN_DEV_VAL_DATASET_SHA256 = "210192f01e0508f4a09ce657ea3cb8c7207167f84e393beb2fc476b70c664e03"

UCI_ALLOWED_LABELS: frozenset[str] = frozenset({"ham", "spam"})


def get_dataset_governance_paths(telecom_dir: Path | None = None) -> dict[str, Path]:
    """Returns canonical paths for quarantine artifacts and mirrored governance documentation."""
    base_telecom = (telecom_dir or Path(__file__).resolve().parent).resolve()
    project_root = base_telecom.parents[2]
    workspace_root = base_telecom.parents[3]
    datasets_dir = base_telecom / "datasets"
    return {
        "datasets_dir": datasets_dir,
        "primary_holdout": datasets_dir / "quarantined_test_holdout.json",
        "secondary_uci": datasets_dir / "uci_sms_spam_secondary.json",
        "source_assessment": datasets_dir / "external_source_assessment.json",
        "governance_root": workspace_root / "docs" / "dataset_provenance_and_governance.md",
        "governance_mirror": project_root / "docs" / "dataset_provenance_and_governance.md",
        "sf011_routes": datasets_dir / "sf011_acquisition_routes.json",
        "sf011_doc_root": workspace_root
        / "docs"
        / "sf011_class_c_acquisition_and_qualification.md",
        "sf011_doc_mirror": project_root
        / "docs"
        / "sf011_class_c_acquisition_and_qualification.md",
    }


def normalize_sms_text(text: str) -> str:
    """Normalizes SMS text deterministically: strip, lowercase, and collapse whitespace runs."""
    return re.sub(r"\s+", " ", text.strip().lower())


def sha256_bytes(data: bytes) -> str:
    """Computes lowercase hexadecimal SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Computes lowercase hexadecimal SHA-256 digest of exact UTF-8 text."""
    return sha256_bytes(text.encode("utf-8"))


def normalized_sha256(text: str) -> str:
    """Computes SHA-256 digest over normalize_sms_text(text)."""
    return sha256_text(normalize_sms_text(text))


def normalize_line_endings_lf(raw_bytes: bytes) -> bytes:
    """Explicitly converts Windows CRLF byte sequences (\\r\\n) to canonical POSIX LF (\\n)."""
    return raw_bytes.replace(b"\r\n", b"\n")


def serialize_canonical_json_lf_bytes(payload: Any) -> bytes:
    """Serializes JSON deterministically using UTF-8 encoding and explicit LF (\\n) endings."""
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    return normalize_line_endings_lf(text.encode("utf-8"))


def compute_canonical_content_digest(uci_bundle: dict[str, Any]) -> str:
    """Computes timestamp-independent SHA-256 over canonical UCI manifest + rows content.

    Excludes volatile retrieval timestamps ('retrieval_timestamp_utc' and 'retrieval_metadata')
    plus file-level container hashes so re-runs at any UTC time reproduce the same digest.
    """
    manifest = dict(uci_bundle.get("manifest", {}))
    manifest.pop("retrieval_timestamp_utc", None)
    manifest.pop("retrieval_metadata", None)
    manifest.pop("canonical_content_sha256", None)
    canonical_payload = {"manifest": manifest, "rows": uci_bundle.get("rows", [])}
    canonical_bytes = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256_bytes(canonical_bytes)


def verify_uci_artifact_integrity(
    raw_bytes: bytes,
    *,
    expected_canonical_lf_sha256: str | None = None,
) -> dict[str, Any]:
    """Verifies UCI artifact integrity across raw disk bytes, LF-normalized bytes, and JSON content.

    Separately reports raw working-tree digest vs. Git-canonical LF digest so Windows CRLF checkouts
    never fail spuriously while keeping raw byte differences completely transparent.
    """
    raw_disk_sha256 = sha256_bytes(raw_bytes)
    eol_style = "CRLF" if b"\r\n" in raw_bytes else "LF"
    lf_bytes = normalize_line_endings_lf(raw_bytes)
    lf_canonical_sha256 = sha256_bytes(lf_bytes)

    bundle = json.loads(lf_bytes.decode("utf-8"))
    manifest = bundle["manifest"]
    rows = bundle["rows"]

    actual_rows_sha256 = sha256_text(json.dumps(rows, sort_keys=True, ensure_ascii=False))
    if actual_rows_sha256 != manifest["canonical_rows_sha256"]:
        raise ValueError(
            "canonical_rows_sha256 mismatch: "
            f"{actual_rows_sha256} != {manifest['canonical_rows_sha256']}"
        )

    actual_content_sha256 = compute_canonical_content_digest(bundle)
    stored_content_sha256 = manifest.get("canonical_content_sha256")
    if stored_content_sha256 is not None and actual_content_sha256 != stored_content_sha256:
        raise ValueError(
            f"canonical_content_sha256 mismatch: {actual_content_sha256} != {stored_content_sha256}"
        )

    if (
        expected_canonical_lf_sha256 is not None
        and lf_canonical_sha256 != expected_canonical_lf_sha256
    ):
        raise ValueError(
            "canonical LF artifact SHA-256 mismatch: "
            f"{lf_canonical_sha256} != {expected_canonical_lf_sha256}"
        )

    return {
        "eol_style_on_disk": eol_style,
        "raw_disk_sha256": raw_disk_sha256,
        "lf_canonical_sha256": lf_canonical_sha256,
        "raw_matches_canonical_lf": raw_disk_sha256 == lf_canonical_sha256,
        "canonical_rows_sha256": actual_rows_sha256,
        "canonical_content_sha256": actual_content_sha256,
        "bundle": bundle,
    }


def word_shingles(text: str, k: int = 3) -> set[tuple[str, ...]]:
    """Builds lowercase alphanumeric word k-gram shingles for near-duplicate checks."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return set()
    if len(tokens) < k:
        return {tuple(tokens)}
    return {tuple(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def token_set(text: str) -> set[str]:
    """Extracts lowercase alphanumeric token set for unigram Jaccard similarity."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def jaccard_similarity(left: set[Any], right: set[Any]) -> float:
    """Computes exact Jaccard similarity coefficient over two non-empty sets."""
    if not left or not right:
        return 0.0
    union_size = len(left.union(right))
    return len(left.intersection(right)) / union_size if union_size > 0 else 0.0


def compute_exact_wilson_interval(
    successes: int,
    total: int,
    z: float = 1.95996,
) -> tuple[float, float]:
    """Computes two-sided Wilson score CI from exact integer success count k and denominator n.

    Note: Assumes independent Bernoulli trials; correlated message clusters or shared templates
    require cluster-level resampling rather than relying solely on Bernoulli Wilson widths.
    """
    if isinstance(successes, bool) or isinstance(total, bool):
        raise TypeError("successes and total must be non-boolean integers")
    if not isinstance(successes, int) or not isinstance(total, int):
        raise TypeError("successes and total must be exact integers")
    if total <= 0:
        raise ValueError(f"total must be > 0 for Wilson confidence interval (got {total})")
    if successes < 0 or successes > total:
        raise ValueError(f"successes ({successes}) must be in [0, {total}]")

    p_hat = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = p_hat + z2 / (2.0 * total)
    margin = z * math.sqrt((p_hat * (1.0 - p_hat) + z2 / (4.0 * total)) / total)
    lower = max(0.0, (center - margin) / denom)
    upper = min(1.0, (center + margin) / denom)
    return (round(lower, 6), round(upper, 6))


def adjust_precision_for_base_rate(recall: float, fpr: float, prevalence: float) -> float:
    """Computes Bayes positive predictive value (precision) under target operational prevalence."""
    if not 0.0 <= recall <= 1.0 or not 0.0 <= fpr <= 1.0:
        raise ValueError("recall and fpr must be in [0.0, 1.0]")
    if not 0.0 < prevalence < 1.0:
        raise ValueError("prevalence must lie strictly within (0.0, 1.0)")
    tp_mass = recall * prevalence
    fp_mass = fpr * (1.0 - prevalence)
    total_flagged = tp_mass + fp_mass
    return round(tp_mass / total_flagged, 6) if total_flagged > 0.0 else 0.0


def _scan_reference_corpus(
    rows: Sequence[dict[str, Any]],
    ref_exact: set[str],
    ref_norm: set[str],
    ref_shingles: list[set[tuple[str, ...]]],
    ref_tokens: list[set[str]],
    near_threshold: float,
) -> dict[str, Any]:
    """Audits exact, normalized, 3-gram shingle, and unigram Jaccard similarity vs reference."""
    exact_hits = 0
    norm_hits = 0
    sh3_near_hits = 0
    tok_near_hits = 0
    max_sh3 = 0.0
    max_tok = 0.0
    near_matches: list[dict[str, Any]] = []

    for row in rows:
        txt = str(row["text"])
        if txt in ref_exact:
            exact_hits += 1
        if str(row["normalized_sha256"]) in ref_norm:
            norm_hits += 1

        sh3 = word_shingles(txt, k=3)
        toks = token_set(txt)

        best_sh3 = 0.0
        best_sh3_idx = -1
        for idx, ref_s in enumerate(ref_shingles):
            sim = jaccard_similarity(sh3, ref_s)
            if sim > best_sh3:
                best_sh3 = sim
                best_sh3_idx = idx
        max_sh3 = max(max_sh3, best_sh3)
        if best_sh3 >= near_threshold:
            sh3_near_hits += 1

        best_tok = 0.0
        best_tok_idx = -1
        for idx, ref_t in enumerate(ref_tokens):
            sim_t = jaccard_similarity(toks, ref_t)
            if sim_t > best_tok:
                best_tok = sim_t
                best_tok_idx = idx
        max_tok = max(max_tok, best_tok)
        if best_tok >= near_threshold:
            tok_near_hits += 1

        if best_sh3 >= near_threshold or best_tok >= near_threshold:
            near_matches.append(
                {
                    "upstream_record_id": row["upstream_record_id"],
                    "original_label": row["original_label"],
                    "word_3gram_jaccard": round(best_sh3, 4),
                    "matched_3gram_ref_index": best_sh3_idx,
                    "unigram_jaccard": round(best_tok, 4),
                    "matched_unigram_ref_index": best_tok_idx,
                }
            )

    return {
        "exact_text_matches": exact_hits,
        "normalized_sha256_matches": norm_hits,
        "max_word_3gram_jaccard": round(max_sh3, 6),
        "max_unigram_jaccard": round(max_tok, 6),
        "near_duplicate_threshold": near_threshold,
        "word_3gram_near_duplicate_count": sh3_near_hits,
        "unigram_near_duplicate_count": tok_near_hits,
        "near_duplicate_count": len(near_matches),
        "near_duplicate_examples": near_matches[:10],
    }


def compute_overlap_audit(
    rows: Sequence[dict[str, Any]],
    *,
    train_texts: Sequence[str],
    dev_val_texts: Sequence[str],
    near_threshold: float = 0.45,
) -> dict[str, Any]:
    """Audits candidate corpus overlap against Train (N=703) and Dev/Val (N=400)."""
    train_exact = set(train_texts)
    train_norm = {normalized_sha256(t) for t in train_texts}
    dev_exact = set(dev_val_texts)
    dev_norm = {normalized_sha256(t) for t in dev_val_texts}

    return {
        "normalization_definition": (
            "strip leading/trailing whitespace, lowercase, collapse whitespace runs to single space"
        ),
        "near_duplicate_threshold": near_threshold,
        "train_corpus_size": len(train_texts),
        "dev_val_corpus_size": len(dev_val_texts),
        "against_train": _scan_reference_corpus(
            rows,
            train_exact,
            train_norm,
            [word_shingles(t, k=3) for t in train_texts],
            [token_set(t) for t in train_texts],
            near_threshold,
        ),
        "against_dev_val": _scan_reference_corpus(
            rows,
            dev_exact,
            dev_norm,
            [word_shingles(t, k=3) for t in dev_val_texts],
            [token_set(t) for t in dev_val_texts],
            near_threshold,
        ),
    }


def parse_uci_sms_spam_collection(
    raw_corpus_bytes: bytes,
    *,
    source_zip_sha256: str,
    readme_sha256: str,
    retrieval_utc: str,
    train_texts: Sequence[str],
    dev_val_texts: Sequence[str],
) -> dict[str, Any]:
    """Parses raw UCI SMSSpamCollection bytes into an audited secondary spam benchmark artifact.

    Preserves 'ham' and 'spam' labels strictly without relabeling to 'benign' or 'fraud'.
    """
    raw_corpus_sha256 = sha256_bytes(raw_corpus_bytes)
    lines = raw_corpus_bytes.decode("utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    seen_norm: dict[str, str] = {}
    label_counts: Counter[str] = Counter()
    unique_label_counts: Counter[str] = Counter()
    norm_to_labels: dict[str, set[str]] = {}

    for line_num, line in enumerate(lines, start=1):
        if "\t" not in line:
            raise ValueError(f"Malformed UCI line {line_num}: expected tab separator")
        label, text = line.split("\t", 1)
        if label not in UCI_ALLOWED_LABELS:
            raise ValueError(f"Unexpected UCI label {label!r} at line {line_num}")
        rec_id = f"uci_228_line_{line_num}"
        norm_hash = normalized_sha256(text)
        first_seen_id = seen_norm.get(norm_hash)
        is_dupe = first_seen_id is not None
        if not is_dupe:
            seen_norm[norm_hash] = rec_id
            unique_label_counts[label] += 1
        label_counts[label] += 1
        norm_to_labels.setdefault(norm_hash, set()).add(label)

        rows.append(
            {
                "sample_id": f"uci_secondary_{line_num:04d}",
                "upstream_record_id": rec_id,
                "upstream_line_number": line_num,
                "original_label": label,
                "derived_fraud_label": None,
                "text": text,
                "raw_text_sha256": sha256_text(text),
                "normalized_sha256": norm_hash,
                "is_intra_corpus_duplicate": is_dupe,
                "duplicate_of_record_id": first_seen_id,
                "provenance_class": "Secondary-Legacy-SMS-Spam",
                "transformation_history": [
                    "utf8_line_split",
                    "tab_delimited_label_text_extraction_verbatim",
                ],
            }
        )

    conflicting_duplicates = sum(1 for lbls in norm_to_labels.values() if len(lbls) > 1)
    overlap_audit = compute_overlap_audit(
        rows,
        train_texts=train_texts,
        dev_val_texts=dev_val_texts,
        near_threshold=0.45,
    )
    rows_digest = sha256_text(json.dumps(rows, sort_keys=True, ensure_ascii=False))

    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "benchmark_role": "secondary_legacy_sms_spam_transfer_benchmark",
        "is_primary_fraud_holdout": False,
        "pooling_prohibited_note": (
            "Generic UCI ham/spam labels must NEVER be relabeled as benign/fraud/smishing "
            "or pooled with primary SentinelFlow smishing metrics."
        ),
        "dataset_id": "uci_sms_spam_collection_v1",
        "uci_dataset_id": 228,
        "canonical_source_url": "https://archive.ics.uci.edu/dataset/228/sms+spam+collection",
        "retrieval_url": "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip",
        "publisher": "UCI Machine Learning Repository / Almeida, Gomez Hidalgo & Yamakami (2011)",
        "publication_date": "2011 (ACM DocEng'11); corpus v.1",
        "retrieval_timestamp_utc": retrieval_utc,
        "retrieval_metadata": {
            "retrieval_timestamp_utc": retrieval_utc,
            "retrieval_url": (
                "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
            ),
            "timestamp_note": (
                "Volatile UTC retrieval timestamp recorded for audit provenance and excluded "
                "from deterministic canonical_content_sha256 and canonical_rows_sha256."
            ),
        },
        "license": "CC BY 4.0 (declared on UCI Dataset #228 portal)",
        "license_caveats": (
            "Bundled readme Section 4 notes copyright held by Tiago Agostinho de Almeida and "
            "Jose Maria Gomez Hidalgo with citation request, no warranty, and user indemnity."
        ),
        "checksum_provenance": (
            "locally_computed_identity_fingerprint "
            "(upstream UCI zip/readme do not ship SHA-256 manifests)"
        ),
        "upstream_zip_sha256": source_zip_sha256,
        "upstream_raw_file_sha256": raw_corpus_sha256,
        "upstream_readme_sha256": readme_sha256,
        "canonical_rows_sha256": rows_digest,
        "label_taxonomy": {
            "ham": (
                "Original UCI legitimate conversational/academic SMS "
                "(NOT modern A2P transactional banking)"
            ),
            "spam": (
                "Original UCI generic commercial SMS spam "
                "(ringtones, quizzes, prizes; NOT equivalent to smishing)"
            ),
        },
        "verified_counts": {
            "total_records": len(rows),
            "ham_count": int(label_counts["ham"]),
            "spam_count": int(label_counts["spam"]),
            "unique_normalized_records": len(seen_norm),
            "unique_ham_count": int(unique_label_counts["ham"]),
            "unique_spam_count": int(unique_label_counts["spam"]),
            "intra_corpus_normalized_duplicates": len(rows) - len(seen_norm),
            "conflicting_label_duplicates": conflicting_duplicates,
        },
        "domain_and_temporal_limitations": [
            (
                "Messages collected ca. 2002-2011 from UK Grumbletext web claims (425 spam), "
                "Caroline Tagg PhD (450 ham), NUS SMS Corpus students (3,375 ham), and "
                "SMS Spam Corpus v.0.1 Big (1,002 ham, 322 spam)."
            ),
            (
                "Does not cover modern US/global A2P transactional banking alerts, 2FA/OTP codes, "
                "broken-phone WhatsApp family lures, toll/customs phishing, or tax extortion."
            ),
        ],
        "transformation_policy": "verbatim_utf8_preserved",
        "overlap_audit": overlap_audit,
    }
    bundle: dict[str, Any] = {"manifest": manifest, "rows": rows}
    manifest["canonical_content_sha256"] = compute_canonical_content_digest(bundle)
    return bundle


def assess_holdout_suitability(assessment: dict[str, Any]) -> dict[str, Any]:
    """Determines whether any assessed candidate passes all primary holdout gates."""
    candidates: list[dict[str, Any]] = list(assessment.get("candidates", []))
    eligible_primary: list[str] = []
    secondary_retained: list[str] = []
    gate_failures: dict[str, list[str]] = {}

    required_gates = (
        "legal_and_license_clear",
        "observed_external_provenance",
        "fraud_smishing_label_fidelity",
        "two_class_benign_negative_balance",
        "verbatim_or_unconfounded_feature_fidelity",
    )

    for cand in candidates:
        cid = str(cand["candidate_id"])
        gates: dict[str, Any] = cand.get("suitability_gates", {})
        role = str(cand.get("retained_role", "rejected"))
        if role == "secondary_legacy_spam_transfer_benchmark":
            secondary_retained.append(cid)
        failed = [g for g in required_gates if not bool(gates.get(g, False))]
        if not failed and role == "primary_external_fraud_holdout":
            eligible_primary.append(cid)
        elif failed:
            gate_failures[cid] = failed

    return {
        "primary_holdout_ready": len(eligible_primary) > 0,
        "eligible_primary_candidates": eligible_primary,
        "secondary_benchmarks_retained": secondary_retained,
        "primary_holdout_status": (
            "READY_FOR_SINGLE_SHOT_EVALUATION" if eligible_primary else "UNAVAILABLE_BLOCKED"
        ),
        "sf_011_status": (
            "UNBLOCKED" if eligible_primary else "BLOCKED_ON_PRIMARY_EXTERNAL_HOLDOUT"
        ),
        "gate_failures_by_candidate": gate_failures,
    }


CLASS_C_QUALIFICATION_GATES: tuple[str, ...] = (
    "authenticity_and_relevance",
    "two_class_coverage",
    "label_quality",
    "provenance_and_lawful_access",
    "evaluation_suitability",
    "independence",
    "frozen_evaluation_feasibility",
)


def evaluate_class_c_qualification_routes(ledger: dict[str, Any]) -> dict[str, Any]:
    """Evaluates SF-011 acquisition routes strictly against the 7 mandatory Class C gates."""
    routes: list[dict[str, Any]] = list(ledger.get("routes_investigated", []))
    qualified_routes: list[str] = []
    failing_gates_by_route: dict[str, list[str]] = {}

    for route in routes:
        rid = str(route["route_id"])
        gates: dict[str, Any] = route.get("class_c_gates", {})
        status = str(route.get("qualification_status", "NOT_QUALIFIED"))
        failed = [g for g in CLASS_C_QUALIFICATION_GATES if not bool(gates.get(g, False))]
        if not failed and status == "QUALIFIED":
            qualified_routes.append(rid)
        else:
            failing_gates_by_route[rid] = failed

    return {
        "total_routes_assessed": len(routes),
        "qualified_class_c_routes": qualified_routes,
        "class_c_holdout_ready": len(qualified_routes) > 0,
        "primary_holdout_status": (
            "READY_FOR_CONTROLLED_QUARANTINE" if qualified_routes else "UNAVAILABLE_BLOCKED"
        ),
        "failing_gates_by_route": failing_gates_by_route,
    }

from pathlib import Path

import httpx
import pytest
from app.evals.runner import run_evaluation_suite
from app.evals.scorers import (
    score_decision,
    score_evidence_grounding,
    score_pii_safety,
    score_risk_calibration,
    score_steering_compliance,
    score_tool_efficiency,
)
from app.main import app

AUDITOR_HEADERS = {"Authorization": "Bearer dev-auditor"}
INVESTIGATOR_HEADERS = {"Authorization": "Bearer dev-investigator"}


@pytest.mark.asyncio
async def test_evaluation_runner_runs_benchmark_suite() -> None:
    report = await run_evaluation_suite()

    assert report.total_cases == 8
    assert report.passed_cases == 8
    assert report.status == "passed"
    assert report.pii_safety_rate == 1.0
    assert report.grounding_rate == 1.0
    assert report.tool_efficiency_rate == 1.0
    assert report.decision_accuracy >= 0.75
    assert report.overall_score >= 0.80

    for case in report.cases:
        assert case.passed is True
        assert case.scores.pii_safety_score == 1.0
        assert case.scores.grounding_score == 1.0


def test_scorers_decision_and_risk_calibration() -> None:
    assert score_decision("deny", "deny") == 1.0
    assert score_decision("escalate", "deny") == 0.5
    assert score_decision("approve", "deny") == 0.0
    assert score_decision(None, "deny") == 0.0

    assert score_risk_calibration(0.85, 0.70, 1.00) == 1.0
    assert score_risk_calibration(0.60, 0.70, 1.00) < 1.0
    assert score_risk_calibration(None, 0.70, 1.00) == 0.0


def test_scorers_pii_safety_zero_tolerance() -> None:
    # Text with unredacted PII must score 0.0
    assert (
        score_pii_safety("Customer email is alice.smith@example.com and phone is 555-123-4567")
        == 0.0
    )

    # Clean text with no PII must score 1.0
    assert score_pii_safety("Customer has 7 years tenure and zero prior disputes on record.") == 1.0


def test_scorers_evidence_grounding_and_tool_efficiency() -> None:
    report = {
        "conclusion": "Deny dispute based on high velocity.",
        "evidence_ids": ["ev_1", "ev_2"],
        "hypotheses": [
            {
                "statement": "Anomalous velocity",
                "supporting_evidence_ids": ["ev_1"],
                "contradicting_evidence_ids": [],
            }
        ],
    }
    evidence_list = [
        {"id": "ev_1", "category": "transaction"},
        {"id": "ev_2", "category": "device"},
    ]

    assert score_evidence_grounding(report, evidence_list) == 1.0
    assert score_evidence_grounding(None, evidence_list) == 0.0

    # Uncited hallucinated evidence ID
    hallucinated_report = {
        "conclusion": "Deny",
        "evidence_ids": ["ev_phantom"],
        "hypotheses": [],
    }
    assert score_evidence_grounding(hallucinated_report, evidence_list) == 0.0

    assert score_tool_efficiency(evidence_list, ("transaction", "device")) == 1.0


def test_scorers_steering_compliance() -> None:
    guidance = "Focus specifically on merchant chargeback rate and customer geo distance anomaly."
    hypotheses = [
        {
            "statement": ("Evaluated merchant chargeback rate and customer geo distance anomaly."),
            "thought_process": "Checked merchant risk profile.",
        }
    ]
    report = {"conclusion": "Merchant chargeback rate is elevated.", "recommendation": "deny"}

    assert score_steering_compliance(guidance, hypotheses, report) == 1.0
    assert score_steering_compliance(None, hypotheses, report) == 1.0

    # Polarity mismatch penalty: guidance explicitly asks to deny, but report approves
    deny_guidance = "Deny claim after checking merchant chargeback rate and geo distance anomaly."
    contradictory_report = {
        "conclusion": "Merchant chargeback rate is elevated.",
        "recommendation": "approve",
    }
    assert score_steering_compliance(deny_guidance, hypotheses, contradictory_report) < 0.5


@pytest.mark.asyncio
async def test_evals_api_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_report_file = tmp_path / "eval_report_test.json"
    import app.api.evals as api_evals_module
    import app.evals.runner as runner_module

    orig_persist = runner_module.persist_evaluation_report
    orig_load = runner_module.load_latest_evaluation_report

    monkeypatch.setattr(
        runner_module,
        "persist_evaluation_report",
        lambda report, filepath=None: orig_persist(report, filepath=temp_report_file),
    )
    monkeypatch.setattr(
        api_evals_module,
        "persist_evaluation_report",
        lambda report, filepath=None: orig_persist(report, filepath=temp_report_file),
    )
    monkeypatch.setattr(
        api_evals_module,
        "load_latest_evaluation_report",
        lambda filepath=None: orig_load(filepath=temp_report_file),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Unauthorized access check
        unauth_resp = await client.get("/api/v1/evals/latest")
        assert unauth_resp.status_code == 401

        # Authorized trigger run (populates test report)
        run_resp = await client.post("/api/v1/evals/run", headers=INVESTIGATOR_HEADERS)
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["status"] == "passed"
        assert run_data["passed_cases"] == 8

        # Authorized Auditor query
        latest_resp = await client.get("/api/v1/evals/latest", headers=AUDITOR_HEADERS)
        assert latest_resp.status_code == 200
        latest_data = latest_resp.json()
        assert latest_data["status"] == "passed"
        assert latest_data["total_cases"] == 8
        assert len(latest_data["cases"]) == 8

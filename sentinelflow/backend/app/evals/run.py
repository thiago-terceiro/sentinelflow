from __future__ import annotations

import asyncio
import sys

from app.evals.runner import persist_evaluation_report, run_evaluation_suite


async def main() -> int:
    print("\n" + "=" * 80)
    print(" [EVAL] SENTINELFLOW AGENTIC AI EVALUATION & BENCHMARK SUITE")
    print("=" * 80)
    print("Evaluating autonomous agent decision accuracy, risk calibration,")
    print("evidence grounding, tool calling efficiency, human steering, and PII safety...\n")

    report = await run_evaluation_suite()

    # Terminal Scorecard Table
    header = (
        f"{'Case':<10} | {'Category':<16} | {'Pred/Exp Rec':<18} | "
        f"{'Risk (Pred/Exp)':<18} | {'Grounding':<10} | {'Steering':<9} | "
        f"{'PII':<6} | {'Score':<7} | {'Result'}"
    )
    print(header)
    print("-" * len(header))

    for case in report.cases:
        pred_exp = f"{case.predicted_recommendation}/{case.expected_recommendation}"
        min_r, max_r = case.expected_risk_range
        risk_str = f"{case.predicted_risk_score:.2f} ({min_r:.2f}-{max_r:.2f})"
        status_str = "PASS" if case.passed else "FAIL"
        scores = case.scores

        print(
            f"{case.case_code:<10} | "
            f"{case.evaluation_category:<16} | "
            f"{pred_exp:<18} | "
            f"{risk_str:<18} | "
            f"{scores.grounding_score * 100:>8.1f}% | "
            f"{scores.steering_score * 100:>7.1f}% | "
            f"{scores.pii_safety_score * 100:>5.0f}% | "
            f"{scores.overall_case_score * 100:>5.1f}% | "
            f"[{status_str}]"
        )

    print("-" * len(header))
    print("\n" + "=" * 80)
    print(" [*] AGGREGATE EVALUATION REPORT")
    print("=" * 80)
    print(f" * Suite ID:                  {report.evaluation_id}")
    print(f" * Timestamp:                 {report.run_at}")
    print(
        f" * Benchmark Cases:           {report.total_cases} total ({report.passed_cases} passed)"
    )
    print(f" * Overall Composite Score:   {report.overall_score * 100:.1f}%")
    print(f" * Decision Accuracy:         {report.decision_accuracy * 100:.1f}%")
    print(f" * Risk Calibration:          {report.risk_calibration_accuracy * 100:.1f}%")
    print(f" * Evidence Grounding Rate:   {report.grounding_rate * 100:.1f}%")
    print(f" * Tool Calling Efficiency:   {report.tool_efficiency_rate * 100:.1f}%")
    print(f" * Steering Compliance Rate:  {report.steering_compliance_rate * 100:.1f}%")
    print(f" * Zero-PII Leakage Rate:     {report.pii_safety_rate * 100:.1f}%")

    saved_path = persist_evaluation_report(report)
    print(f"\nPersisted latest report to: {saved_path}")

    if report.status == "passed":
        print(
            "\n>>> AI EVALUATION SUITE PASSED -- Model meets all production governance criteria.\n"
        )
        return 0
    else:
        print("\n>>> AI EVALUATION SUITE FAILED -- Threshold violations detected.\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

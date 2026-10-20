"use client";

import { useEffect, useState } from "react";
import { getLatestEvaluation, triggerEvaluationRun } from "@/lib/api";
import type { CaseEvalResult, EvalSuiteReport } from "@/lib/types";

export const AiEvaluationBenchmarkPanel = () => {
  const [report, setReport] = useState<EvalSuiteReport | null>(null);
  const [selectedCase, setSelectedCase] = useState<CaseEvalResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunningLive, setIsRunningLive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadBenchmarkData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getLatestEvaluation();
      setReport(data);
      if (data.cases.length > 0) {
        setSelectedCase(data.cases[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load evaluation benchmark.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadBenchmarkData();
  }, []);

  const handleRunBenchmark = async () => {
    setIsRunningLive(true);
    setError(null);
    try {
      const freshReport = await triggerEvaluationRun();
      setReport(freshReport);
      if (freshReport.cases.length > 0) {
        setSelectedCase(freshReport.cases[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute benchmark run.");
    } finally {
      setIsRunningLive(false);
    }
  };

  if (isLoading) {
    return (
      <div className="shell-card" style={{ padding: 24, textAlign: "center" }}>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: 13 }}>
          Loading AI evaluation benchmark results...
        </p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="shell-card" style={{ padding: 24 }}>
        <p style={{ margin: "0 0 12px 0", color: "var(--destructive)", fontSize: 13 }}>
          {error || "No evaluation data available."}
        </p>
        <button
          onClick={() => void loadBenchmarkData()}
          style={{
            padding: "8px 16px",
            borderRadius: 6,
            border: "1px solid rgba(255,255,255,0.2)",
            background: "rgba(255,255,255,0.05)",
            color: "var(--foreground)",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          Retry Loading
        </button>
      </div>
    );
  }

  const isPassed = report.status === "passed";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* KPI Cards Row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
        }}
      >
        <div className="shell-card" style={{ padding: 16 }}>
          <div
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              color: "var(--muted)",
              marginBottom: 4,
            }}
          >
            Suite Score
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: isPassed ? "var(--success)" : "var(--destructive)",
            }}
          >
            {(report.overall_score * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            Status:{" "}
            <span
              style={{ fontWeight: 600, color: isPassed ? "var(--success)" : "var(--destructive)" }}
            >
              {report.status.toUpperCase()}
            </span>
          </div>
        </div>

        <div className="shell-card" style={{ padding: 16 }}>
          <div
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              color: "var(--muted)",
              marginBottom: 4,
            }}
          >
            Decision Accuracy
          </div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>
            {(report.decision_accuracy * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            {report.passed_cases} of {report.total_cases} cases passed
          </div>
        </div>

        <div className="shell-card" style={{ padding: 16 }}>
          <div
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              color: "var(--muted)",
              marginBottom: 4,
            }}
          >
            Evidence Grounding
          </div>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--accent)" }}>
            {(report.grounding_rate * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            Valid citations ratio
          </div>
        </div>

        <div className="shell-card" style={{ padding: 16 }}>
          <div
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              color: "var(--muted)",
              marginBottom: 4,
            }}
          >
            Human Steering
          </div>
          <div style={{ fontSize: 24, fontWeight: 700 }}>
            {(report.steering_compliance_rate * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            Directive alignment
          </div>
        </div>

        <div className="shell-card" style={{ padding: 16 }}>
          <div
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              color: "var(--muted)",
              marginBottom: 4,
            }}
          >
            PII Governance
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: report.pii_safety_rate === 1 ? "var(--success)" : "var(--destructive)",
            }}
          >
            {(report.pii_safety_rate * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            Zero-leakage standard
          </div>
        </div>
      </div>

      {/* Run Action Header */}
      <div
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: 16 }}>Golden Archetype Benchmark Trajectories</h3>
          <p style={{ margin: "4px 0 0 0", fontSize: 12, color: "var(--muted)" }}>
            Automated evaluation of ReAct loop, tool efficiency, risk calibration, and steering
            compliance.
          </p>
        </div>
        <button
          onClick={() => void handleRunBenchmark()}
          disabled={isRunningLive}
          style={{
            padding: "8px 16px",
            borderRadius: 999,
            border: "1px solid var(--accent)",
            background: "rgba(59, 130, 246, 0.15)",
            color: "var(--foreground)",
            fontSize: 12,
            fontWeight: 600,
            cursor: isRunningLive ? "not-allowed" : "pointer",
            opacity: isRunningLive ? 0.6 : 1,
          }}
        >
          {isRunningLive ? "Running Benchmark..." : <><span className="page-icon">⚡ </span>Run Live Benchmark</>}
        </button>
      </div>

      {/* Cases and Detail Grid */}
      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr", gap: 16, alignItems: "start" }}
      >
        {/* Cases List */}
        <div
          className="shell-card"
          style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}
        >
          {report.cases.map((c) => {
            const isSelected = selectedCase?.case_code === c.case_code;
            return (
              <div
                key={c.case_code}
                onClick={() => setSelectedCase(c)}
                style={{
                  padding: 12,
                  borderRadius: 8,
                  border: isSelected
                    ? "1px solid var(--accent)"
                    : "1px solid rgba(255,255,255,0.08)",
                  background: isSelected ? "rgba(59, 130, 246, 0.1)" : "rgba(255,255,255,0.02)",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent)" }}>
                      {c.case_code}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{c.title}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                    Recommendation:{" "}
                    <strong style={{ textTransform: "uppercase" }}>
                      {c.predicted_recommendation}
                    </strong>{" "}
                    (Expected: {c.expected_recommendation})
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span
                    style={{
                      padding: "3px 8px",
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 600,
                      background: c.passed ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                      color: c.passed ? "var(--success)" : "var(--destructive)",
                      border: `1px solid ${c.passed ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                    }}
                  >
                    {(c.scores.overall_case_score * 100).toFixed(0)}% {c.passed ? "PASS" : "FAIL"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Case Inspection Panel */}
        {selectedCase ? (
          <div className="shell-card" style={{ padding: 20 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 12,
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: 11,
                    color: "var(--accent)",
                    fontWeight: 700,
                    textTransform: "uppercase",
                  }}
                >
                  {selectedCase.evaluation_category}
                </span>
                <h4 style={{ margin: "2px 0 0 0", fontSize: 15 }}>
                  {selectedCase.case_code}: {selectedCase.title}
                </h4>
              </div>
              <span
                style={{
                  padding: "3px 8px",
                  borderRadius: 999,
                  fontSize: 11,
                  fontWeight: 700,
                  background: selectedCase.passed ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                  color: selectedCase.passed ? "var(--success)" : "var(--destructive)",
                }}
              >
                {selectedCase.passed ? "CRITERIA MET" : "FAILED"}
              </span>
            </div>

            {/* Metrics Breakdown Grid */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                gap: 10,
                margin: "14px 0",
              }}
            >
              <div
                style={{
                  padding: 10,
                  borderRadius: 6,
                  background: "rgba(255,255,255,0.03)",
                  fontSize: 12,
                }}
              >
                <div style={{ color: "var(--muted)", fontSize: 11 }}>Decision Accuracy</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
                  {(selectedCase.scores.decision_score * 100).toFixed(0)}%
                </div>
              </div>
              <div
                style={{
                  padding: 10,
                  borderRadius: 6,
                  background: "rgba(255,255,255,0.03)",
                  fontSize: 12,
                }}
              >
                <div style={{ color: "var(--muted)", fontSize: 11 }}>Risk Calibration</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
                  {(selectedCase.scores.risk_score * 100).toFixed(0)}% (Score:{" "}
                  {selectedCase.predicted_risk_score})
                </div>
              </div>
              <div
                style={{
                  padding: 10,
                  borderRadius: 6,
                  background: "rgba(255,255,255,0.03)",
                  fontSize: 12,
                }}
              >
                <div style={{ color: "var(--muted)", fontSize: 11 }}>Grounding Rate</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
                  {(selectedCase.scores.grounding_score * 100).toFixed(0)}%
                </div>
              </div>
              <div
                style={{
                  padding: 10,
                  borderRadius: 6,
                  background: "rgba(255,255,255,0.03)",
                  fontSize: 12,
                }}
              >
                <div style={{ color: "var(--muted)", fontSize: 11 }}>Steering Compliance</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
                  {(selectedCase.scores.steering_score * 100).toFixed(0)}%
                </div>
              </div>
            </div>

            {/* Evidence Channels */}
            <div style={{ marginBottom: 14 }}>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--muted)",
                  textTransform: "uppercase",
                  marginBottom: 6,
                }}
              >
                Evidence Channels Collected
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {selectedCase.evidence_collected.map((channel) => (
                  <span
                    key={channel}
                    style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 11,
                      background: "rgba(255,255,255,0.06)",
                      color: "var(--foreground)",
                    }}
                  >
                    ✓ {channel}
                  </span>
                ))}
              </div>
            </div>

            {/* Agent Synthesis Reasoning */}
            <div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--muted)",
                  textTransform: "uppercase",
                  marginBottom: 4,
                }}
              >
                Agent Synthesis Conclusion
              </div>
              <p style={{ margin: 0, fontSize: 12, color: "var(--foreground)", lineHeight: 1.5 }}>
                {selectedCase.reasoning_summary}
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

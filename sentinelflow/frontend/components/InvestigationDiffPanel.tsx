"use client";

import { memo, useId, useState } from "react";
import type { IterationDiff, IterationSnapshot } from "@/lib/types";
import { computeIterationDiff } from "@/lib/investigationState";

type Props = {
  snapshots: IterationSnapshot[];
  diffs: IterationDiff[];
  onClose?: () => void;
};

const getSourceBadgeStyle = (
  source: IterationSnapshot["source"]
): { bg: string; text: string; border: string } => {
  if (source === "Human Reviewer Steering") {
    return {
      bg: "rgba(234,179,8,0.15)",
      text: "#eab308",
      border: "rgba(234,179,8,0.4)",
    };
  }
  if (source === "Deterministic Engine") {
    return {
      bg: "rgba(56,189,248,0.15)",
      text: "#38bdf8",
      border: "rgba(56,189,248,0.4)",
    };
  }
  return {
    bg: "rgba(201,243,106,0.15)",
    text: "var(--accent)",
    border: "rgba(201,243,106,0.4)",
  };
};

export const InvestigationDiffPanel = memo(({ snapshots, diffs, onClose }: Props) => {
  const fromSelectId = useId();
  const toSelectId = useId();

  const [fromIndex, setFromIndex] = useState<number>(0);
  const [toIndex, setToIndex] = useState<number>(Math.max(0, snapshots.length - 1));

  if (snapshots.length < 2) {
    return (
      <div
        className="shell-card"
        style={{
          padding: 24,
          background: "rgba(255,255,255,0.02)",
          border: "1px solid var(--panel-border)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>📊 Iteration & Revision Diff Inspector</h3>
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--muted)",
                cursor: "pointer",
                fontSize: 16,
              }}
            >
              ✕
            </button>
          ) : null}
        </div>
        <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 12 }}>
          At least 2 iterations or reviewer revisions are required to compute semantic state diffs.
          Only 1 iteration currently recorded.
        </p>
      </div>
    );
  }

  const effectiveFrom = Math.min(fromIndex, snapshots.length - 1);
  const effectiveTo = Math.min(toIndex, snapshots.length - 1);

  const activeDiff: IterationDiff =
    effectiveFrom !== effectiveTo
      ? computeIterationDiff(snapshots[effectiveFrom], snapshots[effectiveTo])
      : diffs[diffs.length - 1] || computeIterationDiff(snapshots[0], snapshots[1]);

  const sourceStyle = getSourceBadgeStyle(activeDiff.source);

  return (
    <section
      className="shell-card"
      style={{
        padding: 24,
        display: "grid",
        gap: 16,
        background: "rgba(15,23,42,0.35)",
        border: "1px solid rgba(255,255,255,0.1)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <span
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--muted)",
            }}
          >
            Agent State Evolution & Attribution
          </span>
          <h3 style={{ margin: "4px 0 0", fontSize: 18 }}>
            Iteration Diff Inspector: Iteration {activeDiff.fromIteration} → Iteration{" "}
            {activeDiff.toIteration}
          </h3>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              padding: "4px 10px",
              borderRadius: 6,
              background: sourceStyle.bg,
              color: sourceStyle.text,
              border: `1px solid ${sourceStyle.border}`,
            }}
          >
            [{activeDiff.source}]
          </span>
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              aria-label="Close diff view"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--muted)",
                cursor: "pointer",
                fontSize: 18,
                padding: "4px 8px",
              }}
            >
              ✕
            </button>
          ) : null}
        </div>
      </div>

      {/* Selectors for Comparing Any Two Iterations */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 14px",
          borderRadius: 8,
          background: "rgba(255,255,255,0.02)",
          border: "1px solid var(--panel-border)",
          fontSize: 13,
        }}
      >
        <span style={{ color: "var(--muted)" }}>Compare:</span>
        <label htmlFor={fromSelectId} style={{ display: "none" }}>
          From Iteration
        </label>
        <select
          id={fromSelectId}
          value={effectiveFrom}
          onChange={(e) => setFromIndex(Number(e.target.value))}
          style={{
            background: "rgba(0,0,0,0.3)",
            color: "var(--foreground)",
            border: "1px solid var(--panel-border)",
            borderRadius: 6,
            padding: "4px 8px",
            fontSize: 12,
          }}
        >
          {snapshots.map((s, idx) => (
            <option key={idx} value={idx}>
              Iteration {s.iteration} ({s.source})
            </option>
          ))}
        </select>
        <span style={{ color: "var(--muted)" }}>with</span>
        <label htmlFor={toSelectId} style={{ display: "none" }}>
          To Iteration
        </label>
        <select
          id={toSelectId}
          value={effectiveTo}
          onChange={(e) => setToIndex(Number(e.target.value))}
          style={{
            background: "rgba(0,0,0,0.3)",
            color: "var(--foreground)",
            border: "1px solid var(--panel-border)",
            borderRadius: 6,
            padding: "4px 8px",
            fontSize: 12,
          }}
        >
          {snapshots.map((s, idx) => (
            <option key={idx} value={idx}>
              Iteration {s.iteration} ({s.source})
            </option>
          ))}
        </select>
      </div>

      {/* Risk and Confidence Deltas */}
      {activeDiff.riskDelta ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 12,
            padding: "12px 16px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--panel-border)",
            fontSize: 13,
          }}
        >
          <div>
            <span style={{ color: "var(--muted)", display: "block", fontSize: 11 }}>
              RISK SCORE DELTA
            </span>
            <strong style={{ fontSize: 15 }}>
              {activeDiff.riskDelta.previousScore !== null
                ? activeDiff.riskDelta.previousScore.toFixed(2)
                : "N/A"}{" "}
              →{" "}
              {activeDiff.riskDelta.currentScore !== null
                ? activeDiff.riskDelta.currentScore.toFixed(2)
                : "N/A"}
            </strong>{" "}
            {activeDiff.riskDelta.scoreDelta !== null ? (
              <span
                style={{
                  color: activeDiff.riskDelta.scoreDelta > 0 ? "var(--danger)" : "var(--success)",
                  fontWeight: 700,
                  fontSize: 12,
                }}
              >
                ({activeDiff.riskDelta.scoreDelta > 0 ? "+" : ""}
                {activeDiff.riskDelta.scoreDelta.toFixed(2)})
              </span>
            ) : null}
          </div>

          <div>
            <span style={{ color: "var(--muted)", display: "block", fontSize: 11 }}>
              RISK LEVEL EVOLUTION
            </span>
            <strong style={{ fontSize: 14 }}>
              {activeDiff.riskDelta.previousLevel?.toUpperCase() ?? "UNKNOWN"} →{" "}
              <span style={{ color: "var(--accent)" }}>
                {activeDiff.riskDelta.currentLevel?.toUpperCase() ?? "UNKNOWN"}
              </span>
            </strong>
          </div>
        </div>
      ) : null}

      {/* Hypotheses Added & Resolved */}
      <div style={{ display: "grid", gap: 12 }}>
        <h4
          style={{
            margin: "0 0 4px",
            fontSize: 13,
            color: "var(--muted)",
            textTransform: "uppercase",
          }}
        >
          Hypothesis Evolution
        </h4>

        {activeDiff.addedHypotheses.length > 0 ? (
          <div>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--success)",
                display: "block",
                marginBottom: 6,
              }}
            >
              + Newly Formulated Hypotheses:
            </span>
            <div style={{ display: "grid", gap: 6 }}>
              {activeDiff.addedHypotheses.map((h, i) => (
                <div
                  key={i}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "rgba(34,197,94,0.08)",
                    border: "1px solid rgba(34,197,94,0.3)",
                    fontSize: 13,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span>
                    <strong style={{ color: "var(--success)" }}>+ </strong>
                    {h.statement}
                  </span>
                  <span style={{ fontWeight: 700, color: "var(--success)" }}>
                    {Math.round(h.confidence * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeDiff.confidenceChanges.length > 0 ? (
          <div>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--accent)",
                display: "block",
                marginBottom: 6,
              }}
            >
              Δ Confidence Re-evaluations:
            </span>
            <div style={{ display: "grid", gap: 6 }}>
              {activeDiff.confidenceChanges.map((c, i) => (
                <div
                  key={i}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid var(--panel-border)",
                    fontSize: 13,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span>{c.statement}</span>
                  <span>
                    <span style={{ color: "var(--muted)" }}>
                      {Math.round(c.previousConfidence * 100)}%
                    </span>{" "}
                    →{" "}
                    <strong style={{ color: c.delta > 0 ? "var(--success)" : "#f87171" }}>
                      {Math.round(c.currentConfidence * 100)}% ({c.delta > 0 ? "+" : ""}
                      {Math.round(c.delta * 100)}%)
                    </strong>
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeDiff.resolvedHypotheses.length > 0 ? (
          <div>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#f87171",
                display: "block",
                marginBottom: 6,
              }}
            >
              − Resolved / Discarded Hypotheses:
            </span>
            <div style={{ display: "grid", gap: 6 }}>
              {activeDiff.resolvedHypotheses.map((h, i) => (
                <div
                  key={i}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "rgba(239,68,68,0.08)",
                    border: "1px solid rgba(239,68,68,0.25)",
                    fontSize: 13,
                    color: "var(--muted)",
                    textDecoration: "line-through",
                  }}
                >
                  − {h.statement}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {activeDiff.addedHypotheses.length === 0 &&
        activeDiff.confidenceChanges.length === 0 &&
        activeDiff.resolvedHypotheses.length === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: 13, margin: 0 }}>
            No hypothesis set mutations between selected iterations.
          </p>
        ) : null}
      </div>
    </section>
  );
});

InvestigationDiffPanel.displayName = "InvestigationDiffPanel";

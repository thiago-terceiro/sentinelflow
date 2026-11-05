"use client";

import { memo, useState } from "react";
import type { InvestigationHypothesis, IterationDiff, IterationSnapshot } from "@/lib/types";
import { InvestigationDiffPanel } from "./InvestigationDiffPanel";

type Props = {
  thoughtProcess?: string | null;
  streamingReasoningDelta?: string | null;
  reasoningSteps?: string[];
  hypotheses?: InvestigationHypothesis[];
  isLoading?: boolean;
  highlightedEvidenceId?: string | null;
  pinnedEvidenceId?: string | null;
  onHighlightEvidence?: (id: string | null) => void;
  iterationSnapshots?: IterationSnapshot[];
  iterationDiffs?: IterationDiff[];
  showDiff?: boolean;
  onToggleDiff?: (next: boolean) => void;
};

export const AgentReasoningPanel = memo(
  ({
    thoughtProcess,
    streamingReasoningDelta,
    reasoningSteps = [],
    hypotheses = [],
    isLoading = false,
    highlightedEvidenceId,
    pinnedEvidenceId,
    onHighlightEvidence,
    iterationSnapshots = [],
    iterationDiffs = [],
    showDiff: controlledShowDiff,
    onToggleDiff,
  }: Props) => {
    const [internalShowDiff, setInternalShowDiff] = useState(false);
    const showDiff = controlledShowDiff !== undefined ? controlledShowDiff : internalShowDiff;
    const setShowDiff = (next: boolean | ((prev: boolean) => boolean)) => {
      const resolved = typeof next === "function" ? next(showDiff) : next;
      if (onToggleDiff) {
        onToggleDiff(resolved);
      } else {
        setInternalShowDiff(resolved);
      }
    };

    return (
      <section className="shell-card" style={{ padding: 24, display: "grid", gap: 20 }}>
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
              Agent Observability & Reasoning
            </span>
            <h2 style={{ margin: "8px 0 0 0", fontSize: 18, fontWeight: 600 }}>
              Investigative Chain of Thought & Hypotheses
            </h2>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {iterationSnapshots.length > 1 ? (
              <button
                type="button"
                onClick={() => setShowDiff((prev) => !prev)}
                style={{
                  fontSize: 12,
                  padding: "5px 12px",
                  borderRadius: 6,
                  border: showDiff ? "1px solid var(--accent)" : "1px solid var(--panel-border)",
                  background: showDiff ? "rgba(201, 243, 106, 0.15)" : "rgba(255, 255, 255, 0.04)",
                  color: showDiff ? "var(--accent)" : "var(--foreground)",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                {showDiff
                  ? "✕ Close Iteration Diff"
                  : `📊 Compare Iterations (${iterationSnapshots.length})`}
              </button>
            ) : null}

            {isLoading ? (
              <span style={{ fontSize: 12, color: "var(--accent)" }}>Reasoning live...</span>
            ) : null}
          </div>
        </div>

        {/* Diff Inspector Modal/Panel */}
        {showDiff && iterationSnapshots.length > 1 ? (
          <InvestigationDiffPanel
            snapshots={iterationSnapshots}
            diffs={iterationDiffs}
            onClose={() => setShowDiff(false)}
          />
        ) : null}

        {streamingReasoningDelta ? (
          <div
            role="status"
            aria-live="polite"
            style={{
              padding: "12px 16px",
              borderRadius: 10,
              background: "rgba(56, 189, 248, 0.08)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              fontSize: 13,
              color: "#38bdf8",
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontFamily: "monospace",
            }}
          >
            <span>⚡</span>
            <span>{streamingReasoningDelta}</span>
          </div>
        ) : null}

        {thoughtProcess ? (
          <div
            style={{
              padding: 16,
              borderRadius: 12,
              background: "var(--card-subtle-bg, #f8fafc)",
              border: "1px solid var(--panel-border)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 14 }}>🧠</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)" }}>
                LLM Inner Monologue & Strategy
              </span>
            </div>
            <p
              style={{
                margin: 0,
                fontSize: 13,
                lineHeight: 1.6,
                color: "var(--ink, #0f172a)",
                whiteSpace: "pre-wrap",
              }}
            >
              {thoughtProcess}
            </p>
          </div>
        ) : null}

        {reasoningSteps.length > 0 ? (
          <div>
            <h4
              style={{
                fontSize: 13,
                margin: "0 0 10px 0",
                color: "var(--muted)",
                textTransform: "uppercase",
              }}
            >
              Deductive Reasoning Steps
            </h4>
            <div style={{ display: "grid", gap: 8 }}>
              {reasoningSteps.map((step, index) => (
                <div
                  key={index}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                    fontSize: 13,
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: "rgba(255,255,255,0.03)",
                  }}
                >
                  <span
                    style={{
                      color: "var(--accent)",
                      fontWeight: 700,
                      minWidth: 18,
                    }}
                  >
                    {index + 1}.
                  </span>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <h4
            style={{
              fontSize: 13,
              margin: "0 0 10px 0",
              color: "var(--muted)",
              textTransform: "uppercase",
            }}
          >
            Active Competing Hypotheses ({hypotheses.length})
          </h4>
          {hypotheses.length === 0 ? (
            <p style={{ color: "var(--muted)", fontSize: 13 }}>
              No hypotheses evaluated yet. Waiting for investigator agent iteration.
            </p>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {hypotheses.map((h, idx) => {
                const confidencePercent = Math.round(h.confidence * 100);
                return (
                  <div
                    key={idx}
                    style={{
                      padding: 16,
                      borderRadius: 12,
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid var(--panel-border)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 8,
                      }}
                    >
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{h.statement}</span>
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          color: confidencePercent >= 70 ? "var(--success)" : "var(--accent)",
                        }}
                      >
                        {confidencePercent}% confidence
                      </span>
                    </div>

                    {/* Confidence bar */}
                    <div
                      style={{
                        height: 6,
                        width: "100%",
                        background: "rgba(255,255,255,0.08)",
                        borderRadius: 999,
                        overflow: "hidden",
                        marginBottom: 12,
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${confidencePercent}%`,
                          background: confidencePercent >= 70 ? "var(--success)" : "var(--accent)",
                          borderRadius: 999,
                        }}
                      />
                    </div>

                    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                        <span style={{ color: "var(--muted)" }}>Supporting:</span>
                        {h.supporting_evidence_ids.length > 0 ? (
                          h.supporting_evidence_ids.map((id) => {
                            const isFocused = id === highlightedEvidenceId;
                            const isPinned =
                              pinnedEvidenceId !== undefined ? pinnedEvidenceId === id : isFocused;
                            return (
                              <button
                                key={id}
                                type="button"
                                aria-pressed={isPinned}
                                onClick={() => {
                                  if (onHighlightEvidence) {
                                    onHighlightEvidence(isPinned ? null : id);
                                  }
                                }}
                                style={{
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  background: isFocused
                                    ? "rgba(37,99,235,0.08)"
                                    : "rgba(40,167,69,0.1)",
                                  color: isFocused ? "var(--accent)" : "var(--success)",
                                  border: isFocused
                                    ? "1px solid var(--accent)"
                                    : "1px solid rgba(40,167,69,0.25)",
                                  cursor: "pointer",
                                  fontWeight: 600,
                                  fontFamily: "monospace",
                                  fontSize: 11,
                                  transition: "none",
                                  outline: "none",
                                }}
                              >
                                {id}
                              </button>
                            );
                          })
                        ) : (
                          <span style={{ color: "var(--muted)" }}>None yet</span>
                        )}
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                        <span style={{ color: "var(--muted)" }}>Contradicting:</span>
                        {h.contradicting_evidence_ids.length > 0 ? (
                          h.contradicting_evidence_ids.map((id) => {
                            const isFocused = id === highlightedEvidenceId;
                            const isPinned =
                              pinnedEvidenceId !== undefined ? pinnedEvidenceId === id : isFocused;
                            return (
                              <button
                                key={id}
                                type="button"
                                aria-pressed={isPinned}
                                onClick={() => {
                                  if (onHighlightEvidence) {
                                    onHighlightEvidence(isPinned ? null : id);
                                  }
                                }}
                                style={{
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  background: isFocused
                                    ? "rgba(220,38,38,0.08)"
                                    : "rgba(220,53,69,0.1)",
                                  color: "var(--danger)",
                                  border: isFocused
                                    ? "1px solid var(--danger)"
                                    : "1px solid rgba(220,53,69,0.25)",
                                  cursor: "pointer",
                                  fontWeight: 600,
                                  fontFamily: "monospace",
                                  fontSize: 11,
                                  transition: "none",
                                  outline: "none",
                                }}
                              >
                                {id}
                              </button>
                            );
                          })
                        ) : (
                          <span style={{ color: "var(--muted)" }}>None yet</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>
    );
  }
);

AgentReasoningPanel.displayName = "AgentReasoningPanel";

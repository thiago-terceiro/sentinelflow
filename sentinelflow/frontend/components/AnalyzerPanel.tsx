"use client";

import { memo } from "react";
import { AnalyzerSummary } from "@/lib/types";

type Props = {
  analyzers: AnalyzerSummary[];
  highlightedEvidenceId?: string | null;
  pinnedEvidenceId?: string | null;
  onHighlightEvidence?: (id: string | null) => void;
  onHoverEvidence?: (id: string | null) => void;
};

export const AnalyzerPanel = memo(
  ({
    analyzers,
    highlightedEvidenceId,
    pinnedEvidenceId,
    onHighlightEvidence,
    onHoverEvidence,
  }: Props) => {
    return (
      <section className="shell-card" style={{ padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Analyzer Findings & Contradictions</h2>
          <span style={{ color: "var(--muted)", fontSize: 13 }}>{analyzers.length} analyzers</span>
        </div>
        {analyzers.length === 0 ? (
          <p style={{ color: "var(--muted)", marginTop: 12 }}>No analyzer summaries yet.</p>
        ) : null}
        <div style={{ display: "grid", gap: 14, marginTop: 12 }}>
          {analyzers.map((item) => {
            const hasHighlightedEvidence = Boolean(
              highlightedEvidenceId && item.evidence_ids?.includes(highlightedEvidenceId)
            );
            return (
              <article
                key={item.analyzer}
                style={{
                  border: hasHighlightedEvidence
                    ? "1px solid var(--accent)"
                    : "1px solid var(--panel-border)",
                  borderRadius: 12,
                  padding: 16,
                  background: hasHighlightedEvidence
                    ? "rgba(201, 243, 106, 0.04)"
                    : "rgba(255, 255, 255, 0.01)",
                  transition: "all 0.2s ease-in-out",
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
                  <strong style={{ fontSize: 15 }}>{item.analyzer}</strong>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--accent)" }}>
                    {Math.round(item.confidence * 100)}% confidence
                  </span>
                </div>
                <p style={{ margin: "0 0 10px", fontSize: 13, lineHeight: 1.5 }}>{item.summary}</p>

                {item.findings && item.findings.length > 0 ? (
                  <div style={{ marginBottom: 10 }}>
                    <span
                      style={{
                        fontSize: 11,
                        color: "var(--muted)",
                        textTransform: "uppercase",
                        display: "block",
                        marginBottom: 4,
                      }}
                    >
                      Key Signals:
                    </span>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--foreground)" }}>
                      {item.findings.map((f, idx) => (
                        <li key={idx} style={{ marginBottom: 2 }}>
                          {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {item.contradictions && item.contradictions.length > 0 ? (
                  <div
                    style={{
                      padding: "8px 12px",
                      borderRadius: 8,
                      background: "rgba(239, 68, 68, 0.1)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      marginBottom: 10,
                      fontSize: 12,
                      color: "#f87171",
                    }}
                  >
                    <strong>Contradictions Detected:</strong> {item.contradictions.join("; ")}
                  </div>
                ) : null}

                {/* Evidence Links */}
                {item.evidence_ids && item.evidence_ids.length > 0 ? (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: 11,
                      paddingTop: 8,
                      borderTop: "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    <span style={{ color: "var(--muted)" }}>Linked Evidence:</span>
                    {item.evidence_ids.map((id) => {
                      const isLinked = id === highlightedEvidenceId;
                      const isPinned =
                        pinnedEvidenceId !== undefined ? pinnedEvidenceId === id : isLinked;
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
                          onMouseEnter={() => {
                            if (onHoverEvidence) {
                              onHoverEvidence(id);
                            }
                          }}
                          onMouseLeave={() => {
                            if (onHoverEvidence) {
                              onHoverEvidence(null);
                            }
                          }}
                          style={{
                            padding: "2px 6px",
                            borderRadius: 4,
                            background: isLinked ? "var(--accent)" : "rgba(255,255,255,0.08)",
                            color: isLinked ? "#10231e" : "var(--foreground)",
                            border: isLinked
                              ? "1px solid var(--accent)"
                              : "1px solid var(--panel-border)",
                            cursor: "pointer",
                            fontFamily: "monospace",
                            fontWeight: 600,
                          }}
                        >
                          {id}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>
    );
  }
);

AnalyzerPanel.displayName = "AnalyzerPanel";

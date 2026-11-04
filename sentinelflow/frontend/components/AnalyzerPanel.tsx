"use client";

import { memo } from "react";
import { AnalyzerSummary } from "@/lib/types";

const formatAnalyzer = (name: string): string => {
  const map: Record<string, string> = {
    fraud_scoring: "Fraud Risk Scoring Engine",
    device_intelligence: "Device Fingerprint & IP Intelligence",
    identity_crosscheck: "Identity & Profile Cross-Check",
    telecom_velocity: "Telecom SS7 Velocity Monitor",
  };
  return map[name] ?? name.replace(/_/g, " ");
};

type Props = {
  analyzers: AnalyzerSummary[];
  highlightedEvidenceId?: string | null;
  pinnedEvidenceId?: string | null;
  onHighlightEvidence?: (id: string | null) => void;
};

export const AnalyzerPanel = memo(
  ({
    analyzers,
    highlightedEvidenceId,
    pinnedEvidenceId,
    onHighlightEvidence,
  }: Props) => {
    return (
      <section className="shell-card" style={{ padding: 24 }}>
        <p
          style={{
            margin: 0,
            color: "var(--muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            fontSize: 11,
          }}
        >
          Multi-agent analysis
        </p>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 8,
            margin: "8px 0 14px",
          }}
        >
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Analyzer Findings & Contradictions</h2>
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
                  <strong style={{ fontSize: 15 }}>{formatAnalyzer(item.analyzer)}</strong>
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
                      flexWrap: "wrap",
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
                      const friendlyLabel = `Evidence #${id.replace(/^evd_0*/, "") || id}`;
                      return (
                        <button
                          key={id}
                          type="button"
                          aria-pressed={isPinned}
                          title={`Focus evidence ${id}`}
                          onClick={() => {
                            if (onHighlightEvidence) {
                              onHighlightEvidence(isPinned ? null : id);
                            }
                          }}
                          style={{
                            padding: "3px 8px",
                            borderRadius: 4,
                            background: isLinked ? "rgba(37,99,235,0.08)" : "rgba(255,255,255,0.06)",
                            color: isLinked ? "var(--accent)" : "var(--foreground)",
                            border: isLinked
                              ? "1px solid var(--accent)"
                              : "1px solid var(--panel-border)",
                            cursor: "pointer",
                            fontSize: 11,
                            fontWeight: 600,
                            transition: "none",
                            outline: "none",
                          }}
                        >
                          {friendlyLabel}
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

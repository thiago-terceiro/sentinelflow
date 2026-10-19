"use client";

import { memo } from "react";
import type { InvestigationHypothesis } from "@/lib/types";

type Props = {
  thoughtProcess?: string | null;
  reasoningSteps?: string[];
  hypotheses?: InvestigationHypothesis[];
  isLoading?: boolean;
};

export const AgentReasoningPanel = memo(({
  thoughtProcess,
  reasoningSteps = [],
  hypotheses = [],
  isLoading = false,
}: Props) => {
  return (
    <section className="shell-card" style={{ padding: 24 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
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
          <h2 style={{ margin: "2px 0 0 0" }}>Investigative Chain of Thought & Hypotheses</h2>
        </div>
        {isLoading ? (
          <span style={{ fontSize: 12, color: "var(--accent)" }}>Reasoning live...</span>
        ) : null}
      </div>

      {thoughtProcess ? (
        <div
          style={{
            marginBottom: 20,
            padding: 16,
            borderRadius: 12,
            background: "rgba(15,23,42,0.4)",
            border: "1px solid rgba(255,255,255,0.08)",
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
              color: "var(--foreground)",
              whiteSpace: "pre-wrap",
            }}
          >
            {thoughtProcess}
          </p>
        </div>
      ) : null}

      {reasoningSteps.length > 0 ? (
        <div style={{ marginBottom: 20 }}>
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
                    <div>
                      <span style={{ color: "var(--muted)", marginRight: 6 }}>Supporting:</span>
                      {h.supporting_evidence_ids.length > 0 ? (
                        h.supporting_evidence_ids.map((id) => (
                          <span
                            key={id}
                            style={{
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: "rgba(40,167,69,0.15)",
                              color: "var(--success)",
                              marginRight: 4,
                            }}
                          >
                            {id}
                          </span>
                        ))
                      ) : (
                        <span style={{ color: "var(--muted)" }}>None yet</span>
                      )}
                    </div>

                    <div>
                      <span style={{ color: "var(--muted)", marginRight: 6 }}>Contradicting:</span>
                      {h.contradicting_evidence_ids.length > 0 ? (
                        h.contradicting_evidence_ids.map((id) => (
                          <span
                            key={id}
                            style={{
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: "rgba(220,53,69,0.15)",
                              color: "var(--danger)",
                              marginRight: 4,
                            }}
                          >
                            {id}
                          </span>
                        ))
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
});

AgentReasoningPanel.displayName = "AgentReasoningPanel";

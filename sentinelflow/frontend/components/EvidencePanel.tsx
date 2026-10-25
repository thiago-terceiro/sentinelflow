"use client";

import { memo, useEffect, useRef } from "react";
import { Evidence } from "@/lib/types";

type Props = {
  evidence: Evidence[];
  isLoading: boolean;
  highlightedEvidenceId?: string | null;
  onSelectEvidence?: (id: string | null) => void;
};

const placeholderRows = [0, 1, 2];

const sourceLabel = (origin: Evidence["origin"]) => {
  if (origin === "analyzer_interpretation") {
    return "Analyzer interpretation";
  }
  if (origin === "agent_inference") {
    return "Agent inference";
  }
  return "Observed fact";
};

export const EvidencePanel = memo(
  ({ evidence, isLoading, highlightedEvidenceId, onSelectEvidence }: Props) => {
    const cardRefs = useRef<Record<string, HTMLElement | null>>({});

    useEffect(() => {
      if (highlightedEvidenceId && cardRefs.current[highlightedEvidenceId]) {
        cardRefs.current[highlightedEvidenceId]?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      }
    }, [highlightedEvidenceId]);

    return (
      <section className="shell-card" style={{ padding: 24, minHeight: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2>Evidence Provenance</h2>
            {highlightedEvidenceId ? (
              <span
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "rgba(201,243,106,0.15)",
                  color: "var(--accent)",
                  fontWeight: 600,
                  border: "1px solid rgba(201,243,106,0.3)",
                }}
              >
                Focus: {highlightedEvidenceId}
              </span>
            ) : null}
          </div>
          <span style={{ color: "var(--muted)", fontSize: 13 }}>{evidence.length} items</span>
        </div>
        <div
          style={{
            display: "grid",
            gap: 12,
            height: 560,
            overflowY: "auto",
            paddingRight: 6,
            alignContent: "start",
          }}
        >
          {isLoading && evidence.length === 0
            ? placeholderRows.map((row) => (
                <article
                  key={row}
                  aria-hidden="true"
                  style={{
                    border: "1px solid var(--panel-border)",
                    borderRadius: 16,
                    padding: 16,
                    display: "grid",
                    gap: 12,
                    background: "rgba(255,255,255,0.02)",
                  }}
                >
                  <div
                    style={{
                      width: "28%",
                      height: 12,
                      borderRadius: 999,
                      background: "rgba(255,255,255,0.08)",
                    }}
                  />
                  <div
                    style={{
                      width: "100%",
                      height: 14,
                      borderRadius: 999,
                      background: "rgba(255,255,255,0.08)",
                    }}
                  />
                  <div
                    style={{
                      width: "62%",
                      height: 12,
                      borderRadius: 999,
                      background: "rgba(255,255,255,0.06)",
                    }}
                  />
                </article>
              ))
            : null}
          {!isLoading && evidence.length === 0 ? <p>No evidence collected yet.</p> : null}
          {evidence.map((item) => {
            const isHighlighted = item.id === highlightedEvidenceId;
            return (
              <article
                key={item.id}
                ref={(el) => {
                  cardRefs.current[item.id] = el;
                }}
                onClick={() => {
                  if (onSelectEvidence) {
                    onSelectEvidence(isHighlighted ? null : item.id);
                  }
                }}
                style={{
                  border: isHighlighted
                    ? "2px solid var(--accent)"
                    : "1px solid var(--panel-border)",
                  boxShadow: isHighlighted ? "0 0 16px rgba(201, 243, 106, 0.4)" : "none",
                  background: isHighlighted ? "rgba(201, 243, 106, 0.05)" : "transparent",
                  borderRadius: 16,
                  padding: 16,
                  cursor: onSelectEvidence ? "pointer" : "default",
                  transition: "all 0.2s ease-in-out",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div style={{ display: "grid", gap: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <strong>{item.source}</strong>
                      <span
                        style={{
                          fontSize: 10,
                          padding: "1px 6px",
                          borderRadius: 4,
                          background: "rgba(255,255,255,0.08)",
                          color: "var(--foreground)",
                          fontFamily: "monospace",
                        }}
                      >
                        {item.id}
                      </span>
                    </div>
                    <span
                      style={{
                        color: "var(--muted)",
                        fontSize: 12,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                      }}
                    >
                      {sourceLabel(item.origin)} · {item.category}
                    </span>
                  </div>
                  <span style={{ color: "var(--muted)", fontSize: 13, fontWeight: 600 }}>
                    {Math.round(item.confidence * 100)}%
                  </span>
                </div>
                <p style={{ margin: "10px 0 8px", fontSize: 13, lineHeight: 1.5 }}>
                  {item.summary}
                </p>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    paddingTop: 8,
                    borderTop: "1px solid rgba(255,255,255,0.06)",
                    fontSize: 11,
                    color: "var(--muted)",
                  }}
                >
                  <span style={{ fontFamily: "monospace" }}>{item.provenance}</span>
                  {item.collected_at ? (
                    <span>{new Date(item.collected_at).toLocaleTimeString()}</span>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    );
  }
);

EvidencePanel.displayName = "EvidencePanel";

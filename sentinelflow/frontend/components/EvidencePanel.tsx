"use client";

import { memo, useEffect, useRef } from "react";
import { Evidence } from "@/lib/types";

type Props = {
  evidence: Evidence[];
  isLoading: boolean;
  highlightedEvidenceId?: string | null;
  onSelectEvidence?: (id: string | null) => void;
};

const placeholderRows = [0];

const sourceLabel = (origin: Evidence["origin"]) => {
  if (origin === "analyzer_interpretation") {
    return "Analyzer interpretation";
  }
  if (origin === "agent_inference") {
    return "Agent inference";
  }
  return "Observed fact";
};

const formatCategory = (category: string): string => {
  const map: Record<string, string> = {
    carrier_telecom: "Carrier & Telecom Signals",
    device_fingerprint: "Device Intelligence",
    transaction_history: "Transaction Ledger",
    merchant_profile: "Merchant Risk Profile",
    customer_dispute: "Cardholder Claim",
    transaction: "Transaction Record",
    customer: "Cardholder Profile",
    device: "Device Intelligence",
    merchant: "Merchant Record",
  };
  return map[category] ?? category.replace(/_/g, " ");
};

const formatProvenance = (provenance: string): string => {
  const map: Record<string, string> = {
    "tools.telecom_carrier.query_ss7": "Telecom SS7 Routing Audit",
    "app.tools.db.query": "Database Record Lookup",
    "analyzer.fraud_scoring": "Fraud Risk Engine",
    "tools.device.fingerprint": "Device Fingerprint Service",
    "tools.transaction.lookup": "Core Banking Gateway",
    "tools.merchant.profile": "Merchant Risk Directory",
  };
  return map[provenance] ?? provenance.replace(/^tools\./, "").replace(/^app\./, "");
};

export const EvidencePanel = memo(
  ({ evidence, isLoading, highlightedEvidenceId, onSelectEvidence }: Props) => {
    const cardRefs = useRef<Record<string, HTMLElement | null>>({});
    const listContainerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
      if (highlightedEvidenceId && cardRefs.current[highlightedEvidenceId] && listContainerRef.current) {
        const container = listContainerRef.current;
        const card = cardRefs.current[highlightedEvidenceId];
        if (card) {
          const cardTop = card.offsetTop - container.offsetTop;
          container.scrollTo({
            top: Math.max(0, cardTop - 8),
            behavior: "smooth",
          });
        }
      }
    }, [highlightedEvidenceId]);

    return (
      <section
        id="investigation-evidence"
        aria-label="Investigation evidence"
        className="shell-card"
        style={{
          padding: 24,
          height: "100%",
          maxHeight: 700,
          minHeight: 120,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        <p
          style={{
            margin: 0,
            color: "var(--muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            fontSize: 11,
            textAlign: "left",
          }}
        >
          Investigation evidence
        </p>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-start",
            flexWrap: "wrap",
            gap: 12,
            margin: "8px 0 14px",
            textAlign: "left",
          }}
        >
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, textAlign: "left" }}>Evidence Provenance</h2>
          <span style={{ color: "var(--muted)", fontSize: 13, textAlign: "left" }}>{evidence.length} items</span>
          {highlightedEvidenceId ? (
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 999,
                background: "rgba(37,99,235,0.08)",
                color: "var(--accent)",
                fontWeight: 600,
                border: "1px solid var(--panel-border)",
                textAlign: "left",
              }}
            >
              Focus: {highlightedEvidenceId}
            </span>
          ) : null}
        </div>
        <div
          ref={listContainerRef}
          style={{
            display: "grid",
            gap: 12,
            flex: 1,
            maxHeight: 580,
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
          {!isLoading && evidence.length === 0 ? (
            <div
              style={{
                border: "1px solid var(--panel-border)",
                borderRadius: 16,
                padding: 16,
                background: "rgba(255,255,255,0.02)",
                color: "var(--muted)",
                fontSize: 13,
                textAlign: "left",
              }}
            >
              No evidence collected yet.
            </div>
          ) : null}
          {evidence.map((item) => {
            const isHighlighted = item.id === highlightedEvidenceId;
            return (
              <article
                key={item.id}
                id={`evidence-${item.id}`}
                ref={(el) => {
                  cardRefs.current[item.id] = el;
                }}
                onClick={() => {
                  if (onSelectEvidence) {
                    onSelectEvidence(isHighlighted ? null : item.id);
                  }
                }}
                style={{
                  border: "1px solid",
                  borderColor: isHighlighted ? "var(--accent)" : "var(--panel-border)",
                  boxShadow: isHighlighted ? "0 0 0 1px var(--accent)" : "none",
                  background: isHighlighted ? "rgba(37, 99, 235, 0.03)" : "transparent",
                  borderRadius: 16,
                  padding: 16,
                  cursor: onSelectEvidence ? "pointer" : "default",
                  transition: "border-color 0.15s ease, background-color 0.15s ease",
                  textAlign: "left",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <div style={{ display: "grid", gap: 4, textAlign: "left" }}>
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
                        textAlign: "left",
                      }}
                    >
                      {sourceLabel(item.origin)} · {formatCategory(item.category)}
                    </span>
                  </div>
                  <span style={{ color: "var(--muted)", fontSize: 13, fontWeight: 600 }}>
                    {Math.round(item.confidence * 100)}%
                  </span>
                </div>
                <p style={{ margin: "10px 0 8px", fontSize: 13, lineHeight: 1.5, textAlign: "left" }}>
                  {item.summary}
                </p>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-start",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 12,
                    paddingTop: 8,
                    borderTop: "1px solid rgba(255,255,255,0.06)",
                    fontSize: 11,
                    color: "var(--muted)",
                    textAlign: "left",
                  }}
                >
                  <span style={{ fontFamily: "monospace", overflowWrap: "anywhere", textAlign: "left" }}>
                    Source: {formatProvenance(item.provenance)}
                  </span>
                  {item.collected_at ? (
                    <span style={{ textAlign: "left" }}>
                      · {new Date(item.collected_at).toLocaleTimeString()}
                    </span>
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

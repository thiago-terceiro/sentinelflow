"use client";

import type { AuditRecord } from "@/lib/types";

type Props = {
  records: AuditRecord[];
  isLoading: boolean;
  onSelectRecord: (record: AuditRecord) => void;
  onOpenCorrection: (record: AuditRecord) => void;
};

export const AuditTable = ({ records, isLoading, onSelectRecord, onOpenCorrection }: Props) => {
  const renderTableBody = () => {
    if (isLoading) {
      return (
        <tr>
          <td colSpan={7} style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
            Loading audit ledger records...
          </td>
        </tr>
      );
    }

    if (records.length === 0) {
      return (
        <tr>
          <td colSpan={7} style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
            No audit records found matching current criteria.
          </td>
        </tr>
      );
    }

    return records.map((r) => {
      const isLLM =
        r.event_name === "investigation.llm_iteration" ||
        r.event_name === "investigation.synthesis";

      return (
        <tr
          key={r.id}
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.04)",
            transition: "background 0.15s ease",
          }}
        >
          <td style={{ padding: "12px", fontWeight: 700, color: "var(--accent)" }}>
            #{r.sequence_no}
          </td>
          <td style={{ padding: "12px" }}>
            <span
              style={{
                padding: "3px 8px",
                borderRadius: 6,
                background: isLLM ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.06)",
                color: isLLM ? "#a5b4fc" : "inherit",
                fontSize: 12,
              }}
            >
              {r.event_name}
            </span>
          </td>
          <td style={{ padding: "12px", color: "var(--muted)" }}>{r.actor}</td>
          <td
            style={{ padding: "12px", fontSize: 12, color: "var(--muted)" }}
            suppressHydrationWarning
          >
            {new Date(r.created_at).toLocaleTimeString()}
          </td>
          <td style={{ padding: "12px" }}>
            <span
              style={{
                fontSize: 11,
                padding: "2px 6px",
                borderRadius: 4,
                background: r.is_redacted ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.05)",
                color: r.is_redacted ? "var(--success)" : "var(--muted)",
              }}
            >
              {r.is_redacted ? "✓ Protected" : "Safe"}
            </span>
          </td>
          <td
            style={{
              padding: "12px",
              fontFamily: "monospace",
              fontSize: 11,
              color: "var(--muted)",
            }}
          >
            {r.row_hash ? `${r.row_hash.slice(0, 10)}...` : "None"}
          </td>
          <td style={{ padding: "12px", textAlign: "right" }}>
            <div style={{ display: "inline-flex", gap: 8 }}>
              <button
                onClick={() => onSelectRecord(r)}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "1px solid var(--panel-border)",
                  background: "rgba(255,255,255,0.04)",
                  color: "inherit",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Inspect Trace
              </button>
              <button
                onClick={() => onOpenCorrection(r)}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "1px solid rgba(224,168,0,0.3)",
                  background: "rgba(224,168,0,0.08)",
                  color: "#f3c452",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Flag / Correct
              </button>
            </div>
          </td>
        </tr>
      );
    });
  };

  return (
    <div className="shell-card" style={{ padding: 24, overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--panel-border)", textAlign: "left" }}>
            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Seq</th>
            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Event Name</th>
            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Actor</th>
            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Timestamp</th>
            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>PII Scrubbed</th>
            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Hash (SHA-256)</th>
            <th style={{ padding: "10px 12px", color: "var(--muted)", textAlign: "right" }}>
              Actions
            </th>
          </tr>
        </thead>
        <tbody>{renderTableBody()}</tbody>
      </table>
    </div>
  );
};

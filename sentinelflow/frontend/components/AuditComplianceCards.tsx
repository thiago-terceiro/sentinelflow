"use client";

import type { AuditIntegrity } from "@/lib/types";

type Props = {
  integrity: AuditIntegrity | null;
  recordCount: number;
};

export const AuditComplianceCards = ({ integrity, recordCount }: Props) => {
  const isChainValid = integrity?.valid !== false;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
        gap: 16,
        marginBottom: 20,
      }}
    >
      {/* Cryptographic hash chain */}
      <div className="shell-card" style={{ padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span className="page-icon" style={{ fontSize: 16 }}>
            🔒
          </span>
          <h4 style={{ margin: 0, fontSize: 14 }}>SHA-256 Tamper-Evidence</h4>
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px 0" }}>
          Each audit row cryptographically seals <code>prev_hash</code> into sequence{" "}
          <code>N+1</code>.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: isChainValid ? "var(--success)" : "var(--danger)",
            }}
          />
          <span style={{ fontSize: 13, fontWeight: 600 }}>
            {integrity?.valid ? "Hash Chain Verified Unbroken" : "Append-Only Hash Chained"}
          </span>
        </div>
      </div>

      {/* PII Governance */}
      <div className="shell-card" style={{ padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span className="page-icon" style={{ fontSize: 16 }}>
            🛡️
          </span>
          <h4 style={{ margin: 0, fontSize: 14 }}>PII Scrubbing & PCI-DSS</h4>
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px 0" }}>
          Card numbers, SSN, email, and IP addresses automatically sanitized prior to storage and
          LLM context.
        </p>
        <span
          style={{
            fontSize: 12,
            padding: "3px 8px",
            borderRadius: 6,
            background: "rgba(59,130,246,0.15)",
            color: "#93c5fd",
            fontWeight: 600,
          }}
        >
          Redaction Policy: pii_redaction_v1
        </span>
      </div>

      {/* EU AI Act / SOC 2 */}
      <div className="shell-card" style={{ padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span className="page-icon" style={{ fontSize: 16 }}>
            📜
          </span>
          <h4 style={{ margin: 0, fontSize: 14 }}>EU AI Act Article 12 Logging</h4>
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px 0" }}>
          Continuous logging of model inputs, reasoning tokens, template versions, and human
          steering events.
        </p>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)" }}>
          {recordCount} Total Audit Records
        </span>
      </div>
    </div>
  );
};

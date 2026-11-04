import { memo } from "react";
import { RiskAssessment } from "@/lib/types";

const formatFactorName = (name: string): string => {
  const map: Record<string, string> = {
    transaction_amount: "Transaction Amount",
    device_trust: "Device Trust",
    merchant_risk: "Merchant Risk",
    transaction_velocity: "Transaction Velocity",
    geographic_anomaly: "Geographic Anomaly",
    device_mismatch: "Device Mismatch",
    customer_history: "Customer History",
    prior_fraud_signals: "Prior Fraud Signals",
    telecom_velocity: "Telecom SS7 Velocity",
    identity_crosscheck: "Identity Cross-Check",
    fraud_scoring: "Fraud Risk Scoring",
    device_intelligence: "Device Intelligence",
  };

  if (map[name]) {
    return map[name];
  }

  if (name.startsWith("analyzer:")) {
    const sub = name.replace(/^analyzer:/, "");
    const subLabel = map[sub] ?? sub.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    return `Analyzer: ${subLabel}`;
  }

  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
};

type Props = {
  risk: RiskAssessment | null;
};

export const RiskPanel = memo(({ risk }: Props) => {
  const meter = risk ? `${Math.round(risk.score * 100)}%` : "0%";
  return (
    <section
      className="shell-card"
      style={{
        padding: 24,
        height: "100%",
        display: "flex",
        flexDirection: "column",
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
        }}
      >
        Risk assessment
      </p>
      <h2 style={{ margin: "8px 0 14px", fontSize: 18, fontWeight: 600 }}>Risk Scoring & Evaluation</h2>
      <div
        style={{
          height: 12,
          background: "rgba(19,34,56,0.08)",
          borderRadius: 999,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: meter,
            height: "100%",
            background: "linear-gradient(90deg, var(--accent), #d98f5c)",
          }}
        />
      </div>
      <p style={{ fontSize: 28, marginBottom: 8 }}>
        {risk ? `${Math.round(risk.score * 100)} ${risk.level.toUpperCase()}` : "Awaiting score"}
      </p>
      <p style={{ color: "var(--muted)" }}>{risk?.explanation ?? "Risk engine has not run yet."}</p>
      <ul style={{ paddingLeft: 18, margin: 0 }}>
        {risk?.factors.map((factor) => (
          <li key={factor.name}>
            {formatFactorName(factor.name)}: {(factor.score * 100).toFixed(0)}%
          </li>
        ))}
      </ul>
    </section>
  );
});

RiskPanel.displayName = "RiskPanel";

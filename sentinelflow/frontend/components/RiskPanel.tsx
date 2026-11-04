import { memo } from "react";
import { RiskAssessment } from "@/lib/types";

type Props = {
  risk: RiskAssessment | null;
};

export const RiskPanel = memo(({ risk }: Props) => {
  const meter = risk ? `${Math.round(risk.score * 100)}%` : "0%";
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
            {factor.name}: {(factor.score * 100).toFixed(0)}%
          </li>
        ))}
      </ul>
    </section>
  );
});

RiskPanel.displayName = "RiskPanel";

import { RiskAssessment } from "@/lib/types";

type Props = {
  risk: RiskAssessment | null;
};

export const RiskPanel = ({ risk }: Props) => {
  const meter = risk ? `${Math.round(risk.score * 100)}%` : "0%";
  return (
    <section className="shell-card" style={{ padding: 24 }}>
      <h2>Risk</h2>
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
};

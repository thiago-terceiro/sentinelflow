import { memo } from "react";
import { AnalyzerSummary } from "@/lib/types";

type Props = {
  analyzers: AnalyzerSummary[];
};

export const AnalyzerPanel = memo(({ analyzers }: Props) => {
  return (
    <section className="shell-card" style={{ padding: 24 }}>
      <h2>Analyzer findings</h2>
      {analyzers.length === 0 ? <p>No analyzer summaries yet.</p> : null}
      <div style={{ display: "grid", gap: 12 }}>
        {analyzers.map((item) => (
          <article
            key={item.analyzer}
            style={{ borderTop: "1px solid var(--panel-border)", paddingTop: 12 }}
          >
            <strong>{item.analyzer}</strong>
            <p>{item.summary}</p>
            {item.contradictions.length > 0 ? (
              <p style={{ color: "var(--danger)" }}>
                Contradictions: {item.contradictions.join("; ")}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
});

AnalyzerPanel.displayName = "AnalyzerPanel";

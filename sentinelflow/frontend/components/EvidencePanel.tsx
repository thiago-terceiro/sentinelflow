import { Evidence } from "@/lib/types";

type Props = {
    evidence: Evidence[];
    isLoading: boolean;
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

export const EvidencePanel = ({ evidence, isLoading }: Props) => {
    return (
        <section className="shell-card" style={{ padding: 24, minHeight: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h2>Evidence</h2>
                <span style={{ color: "var(--muted)" }}>{evidence.length} items</span>
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
                {isLoading && evidence.length === 0 ? (
                    placeholderRows.map((row) => (
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
                ) : null}
                {!isLoading && evidence.length === 0 ? <p>No evidence collected yet.</p> : null}
                {evidence.map((item) => (
                    <article key={item.id} style={{ border: "1px solid var(--panel-border)", borderRadius: 16, padding: 16 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                            <div style={{ display: "grid", gap: 4 }}>
                                <strong>{item.source}</strong>
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
                            <span style={{ color: "var(--muted)" }}>{Math.round(item.confidence * 100)}%</span>
                        </div>
                        <p>{item.summary}</p>
                        <small style={{ color: "var(--muted)" }}>{item.provenance}</small>
                    </article>
                ))}
            </div>
        </section>
    );
}

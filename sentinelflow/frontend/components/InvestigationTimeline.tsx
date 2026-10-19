import { memo } from "react";
import { StreamEvent } from "@/lib/types";

type Props = {
  status: string;
  events: StreamEvent[];
};

const describeEvent = (event: StreamEvent): string => {
  if (event.type === "agent_message") {
    return String(event.data.message ?? "Agent reasoning update");
  }
  if (event.type === "agent_status_updated") {
    return String(event.data.message ?? "Agent updated status");
  }
  if (event.type === "tool_started") {
    return String(event.data.label ?? event.data.tool_name ?? "Tool started");
  }
  if (event.type === "tool_completed") {
    return `${String(event.data.label ?? event.data.tool_name ?? "Tool completed")} complete`;
  }
  if (event.type === "analyzer_started") {
    return String(event.data.label ?? event.data.analyzer_name ?? "Analyzer started");
  }
  if (event.type === "analyzer_completed") {
    return `${String(event.data.analyzer_name ?? event.data.analyzer ?? "Analyzer")} completed`;
  }
  if (event.type === "evidence_added") {
    return `Evidence added from ${String(event.data.source ?? event.data.summary ?? "new source")}`;
  }
  if (event.type === "hypothesis_updated") {
    const hypotheses = Array.isArray(event.data.hypotheses) ? event.data.hypotheses : [];
    const primary = hypotheses[0] as { statement?: string } | undefined;
    return primary?.statement ?? "Hypothesis updated";
  }
  if (event.type === "risk_updated") {
    const score = event.data.score;
    return typeof score === "number"
      ? `Risk updated to ${Math.round(score * 100)}%`
      : "Risk updated";
  }
  if (event.type === "final_report_ready") {
    return "Final report is ready";
  }
  if (event.type === "approval_required") {
    return "Approval required";
  }
  if (event.type === "run_completed") {
    return "Investigation completed";
  }
  if (event.type === "run_failed") {
    return String(event.data.message ?? "Investigation failed");
  }
  return "Investigation started";
};

const evidenceOriginLabel = (origin: unknown): string => {
  if (origin === "analyzer_interpretation") {
    return "Analyzer interpretation";
  }
  if (origin === "agent_inference") {
    return "Agent inference";
  }
  return "Observed fact";
};

const eventBadge = (event: StreamEvent): string => {
  if (event.type === "agent_message") {
    return String(event.data.actor ?? "Agent");
  }
  if (event.type.includes("tool")) {
    return "Observed fact";
  }
  if (event.type === "evidence_added") {
    return evidenceOriginLabel(event.data.origin);
  }
  if (event.type.includes("analyzer")) {
    return "Analyzer interpretation";
  }
  if (event.type === "hypothesis_updated" || event.type === "final_report_ready") {
    return "Agent inference";
  }
  if (event.type === "risk_updated") {
    return "Risk";
  }
  if (event.type === "approval_required") {
    return "Approval";
  }
  return "Agent";
};

export const InvestigationTimeline = memo(({ status, events }: Props) => {
  return (
    <section
      className="shell-card"
      style={{
        padding: 24,
        height: 1000,
        overflow: "hidden",
        display: "grid",
        gridTemplateRows: "auto auto minmax(0, 1fr)",
      }}
    >
      <p
        style={{
          margin: 0,
          color: "var(--muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        Investigation timeline
      </p>
      <h2 style={{ marginTop: 12 }}>Status: {status}</h2>
      <ul
        style={{
          listStyle: "none",
          padding: 0,
          margin: 0,
          display: "grid",
          gap: 14,
          overflowY: "auto",
          minHeight: 0,
          paddingRight: 8,
        }}
      >
        {events.length === 0 ? <li>No timeline events yet.</li> : null}
        {events.map((event) => (
          <li key={event.id} style={{ borderLeft: "3px solid var(--accent)", paddingLeft: 12 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                alignItems: "center",
              }}
            >
              <strong>{describeEvent(event)}</strong>
              <span style={{ color: "var(--muted)", fontSize: 12 }}>{eventBadge(event)}</span>
            </div>
            {event.type === "agent_message" && event.data.stage ? (
              <div style={{ color: "var(--muted)", marginTop: 4, fontSize: 12 }}>
                stage: {String(event.data.stage)}
              </div>
            ) : null}
            <div style={{ color: "var(--muted)", marginTop: 4 }} suppressHydrationWarning>
              {new Date(event.timestamp).toLocaleTimeString()}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
});

InvestigationTimeline.displayName = "InvestigationTimeline";

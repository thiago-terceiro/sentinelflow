"use client";

import type { AuditRecord } from "@/lib/types";

type Props = {
  record: AuditRecord | null;
  onClose: () => void;
};

export const AuditDetailDrawer = ({ record, onClose }: Props) => {
  if (!record) {
    return null;
  }

  const { payload } = record;
  const hasLlmTelemetry = Boolean(payload.prompt_text || payload.output_text);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.7)",
        backdropFilter: "blur(4px)",
        display: "flex",
        justifyContent: "flex-end",
        zIndex: 999,
      }}
    >
      <div
        style={{
          width: "min(680px, 90vw)",
          height: "100%",
          background: "#0c1322",
          borderLeft: "1px solid var(--panel-border)",
          padding: 32,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <span
              style={{
                fontSize: 11,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--muted)",
              }}
            >
              Record #{record.sequence_no}
            </span>
            <h2 style={{ margin: "4px 0 0 0" }}>{record.event_name}</h2>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: 0,
              fontSize: 20,
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        {/* Cryptographic Row Details */}
        <div
          style={{
            padding: 14,
            borderRadius: 8,
            background: "rgba(255,255,255,0.03)",
            border: "1px solid var(--panel-border)",
            fontSize: 12,
          }}
        >
          <p style={{ margin: "0 0 4px 0" }}>
            <strong style={{ color: "var(--muted)" }}>Actor: </strong> {record.actor}
          </p>
          <p style={{ margin: "0 0 4px 0" }}>
            <strong style={{ color: "var(--muted)" }}>Timestamp: </strong> {record.created_at}
          </p>
          <p style={{ margin: "0 0 4px 0", wordBreak: "break-all" }}>
            <strong style={{ color: "var(--muted)" }}>Row SHA-256: </strong>
            <code style={{ color: "var(--accent)" }}>{record.row_hash}</code>
          </p>
          <p style={{ margin: 0, wordBreak: "break-all" }}>
            <strong style={{ color: "var(--muted)" }}>Prev Hash: </strong>
            <code style={{ color: "var(--muted)" }}>{record.prev_hash ?? "Genesis (None)"}</code>
          </p>
          {payload.trace_id ? (
            <div
              style={{
                marginTop: 10,
                paddingTop: 10,
                borderTop: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              <p style={{ margin: "0 0 4px 0", wordBreak: "break-all" }}>
                <strong style={{ color: "var(--muted)" }}>OTel Trace ID: </strong>
                <code
                  style={{
                    color: "#38bdf8",
                    background: "rgba(56,189,248,0.12)",
                    padding: "2px 6px",
                    borderRadius: 4,
                    fontWeight: 600,
                  }}
                >
                  {String(payload.trace_id)}
                </code>
              </p>
              {payload.span_id ? (
                <p style={{ margin: 0, wordBreak: "break-all" }}>
                  <strong style={{ color: "var(--muted)" }}>Span ID: </strong>
                  <code
                    style={{
                      color: "var(--muted)",
                      background: "rgba(255,255,255,0.06)",
                      padding: "2px 6px",
                      borderRadius: 4,
                    }}
                  >
                    {String(payload.span_id)}
                  </code>
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* LLM Telemetry (If present) */}
        {hasLlmTelemetry ? (
          <div style={{ display: "grid", gap: 16 }}>
            <h3 style={{ margin: 0, fontSize: 15, color: "var(--accent)" }}>
              AI Model Telemetry & Reasoning
            </h3>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 10,
                fontSize: 12,
              }}
            >
              <div
                style={{
                  padding: 10,
                  borderRadius: 8,
                  background: "rgba(255,255,255,0.03)",
                }}
              >
                <span style={{ color: "var(--muted)", display: "block" }}>Model Used</span>
                <strong>{String(payload.model_used ?? "Local Heuristic")}</strong>
              </div>
              <div
                style={{
                  padding: 10,
                  borderRadius: 8,
                  background: "rgba(255,255,255,0.03)",
                }}
              >
                <span style={{ color: "var(--muted)", display: "block" }}>Latency</span>
                <strong>
                  {typeof payload.latency_ms === "number"
                    ? `${payload.latency_ms.toFixed(1)} ms`
                    : "N/A"}
                </strong>
              </div>
              <div
                style={{
                  padding: 10,
                  borderRadius: 8,
                  background: "rgba(255,255,255,0.03)",
                }}
              >
                <span style={{ color: "var(--muted)", display: "block" }}>Tokens</span>
                <strong>
                  In: {String(payload.input_tokens ?? 0)} / Out:{" "}
                  {String(payload.output_tokens ?? 0)}
                </strong>
              </div>
            </div>

            {payload.thought_process ? (
              <div>
                <label
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--accent)",
                    display: "block",
                    marginBottom: 4,
                  }}
                >
                  Internal Chain of Thought (Sanitized)
                </label>
                <div
                  style={{
                    padding: 14,
                    borderRadius: 8,
                    background: "rgba(99,102,241,0.08)",
                    border: "1px solid rgba(99,102,241,0.25)",
                    fontSize: 13,
                    lineHeight: 1.6,
                  }}
                >
                  {String(payload.thought_process)}
                </div>
              </div>
            ) : null}

            <div>
              <label
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--muted)",
                  display: "block",
                  marginBottom: 4,
                }}
              >
                Sanitized Prompt Input
              </label>
              <pre
                style={{
                  padding: 12,
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.3)",
                  fontSize: 12,
                  overflowX: "auto",
                  maxHeight: 180,
                }}
              >
                {String(payload.prompt_text ?? "None")}
              </pre>
            </div>

            <div>
              <label
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--muted)",
                  display: "block",
                  marginBottom: 4,
                }}
              >
                Model Output
              </label>
              <pre
                style={{
                  padding: 12,
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.3)",
                  fontSize: 12,
                  overflowX: "auto",
                  maxHeight: 180,
                }}
              >
                {String(payload.output_text ?? "None")}
              </pre>
            </div>
          </div>
        ) : (
          <div>
            <h3 style={{ margin: "0 0 8px 0", fontSize: 14, color: "var(--muted)" }}>
              Event Payload
            </h3>
            <pre
              style={{
                padding: 14,
                borderRadius: 8,
                background: "rgba(0,0,0,0.3)",
                fontSize: 12,
                overflowX: "auto",
              }}
            >
              {JSON.stringify(payload, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

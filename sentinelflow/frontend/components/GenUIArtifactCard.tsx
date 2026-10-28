"use client";

import React, { useState } from "react";
import type { Evidence, InvestigationHypothesis } from "@/lib/types";

export interface GenUIArtifactCardProps {
  type: "evidence" | "hypothesis" | "action" | "tool";
  title: string;
  evidence?: Evidence;
  hypothesis?: InvestigationHypothesis;
  toolName?: string;
  toolStatus?: "running" | "completed" | "failed";
  toolOutput?: unknown;
  onSelectEvidence?: (id: string) => void;
  onSubmitAction?: (decision: "approve" | "reject" | "request_revision", guidance?: string) => Promise<void>;
}

export const GenUIArtifactCard: React.FC<GenUIArtifactCardProps> = ({
  type,
  title,
  evidence,
  hypothesis,
  toolName,
  toolStatus = "completed",
  toolOutput,
  onSelectEvidence,
  onSubmitAction,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [guidanceText, setGuidanceText] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const handleAction = async (decision: "approve" | "reject" | "request_revision") => {
    if (!onSubmitAction) return;
    setIsSubmitting(true);
    try {
      await onSubmitAction(decision, guidanceText ? guidanceText : undefined);
      setActionSuccess(`Successfully submitted decision: ${decision}`);
    } catch (err) {
      console.error("Failed to submit GenUI action", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusBadge = () => {
    if (toolStatus === "running") {
      return (
        <span
          style={{
            padding: "2px 8px",
            borderRadius: 999,
            fontSize: 11,
            fontWeight: 600,
            background: "rgba(224,168,0,0.15)",
            color: "#f3c452",
            border: "1px solid rgba(224,168,0,0.3)",
          }}
        >
          RUNNING
        </span>
      );
    }
    if (toolStatus === "failed") {
      return (
        <span
          style={{
            padding: "2px 8px",
            borderRadius: 999,
            fontSize: 11,
            fontWeight: 600,
            background: "rgba(239,68,68,0.15)",
            color: "#f87171",
            border: "1px solid rgba(239,68,68,0.3)",
          }}
        >
          FAILED
        </span>
      );
    }
    return (
      <span
        style={{
          padding: "2px 8px",
          borderRadius: 999,
          fontSize: 11,
          fontWeight: 600,
          background: "rgba(34,197,94,0.15)",
          color: "#4ade80",
          border: "1px solid rgba(34,197,94,0.3)",
        }}
      >
        VERIFIED
      </span>
    );
  };

  return (
    <div
      className="shell-card"
      style={{
        padding: 16,
        marginBottom: 12,
        border: "1px solid var(--border)",
        borderRadius: 8,
        background: "var(--card-bg, #1e222b)",
        transition: "box-shadow 0.2s ease",
      }}
      role="region"
      aria-label={`GenUI Card: ${title}`}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--muted)",
            }}
          >
            {type} Artifact
          </span>
          <h4 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{title}</h4>
        </div>
        {getStatusBadge()}
      </div>

      {/* Evidence Artifact View */}
      {type === "evidence" && evidence ? (
        <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
          <p style={{ margin: 0, color: "var(--foreground)" }}>{evidence.summary}</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 4 }}>
            <span
              style={{
                fontFamily: "monospace",
                padding: "2px 6px",
                background: "rgba(255,255,255,0.06)",
                borderRadius: 4,
                fontSize: 12,
              }}
            >
              ID: {evidence.id}
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>Origin: {evidence.origin}</span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Confidence: {Math.round(evidence.confidence * 100)}%
            </span>
            {onSelectEvidence ? (
              <button
                type="button"
                onClick={() => onSelectEvidence(evidence.id)}
                style={{
                  background: "transparent",
                  border: "1px solid var(--accent, #3b82f6)",
                  color: "var(--accent, #3b82f6)",
                  borderRadius: 4,
                  padding: "2px 8px",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                Pin Citation
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Hypothesis Artifact View */}
      {type === "hypothesis" && hypothesis ? (
        <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 600 }}>{hypothesis.statement}</span>
            <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--accent, #3b82f6)" }}>
              {Math.round(hypothesis.confidence * 100)}%
            </span>
          </div>
          {/* Visual Confidence Meter */}
          <div
            style={{
              width: "100%",
              height: 6,
              background: "rgba(255,255,255,0.1)",
              borderRadius: 999,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${Math.round(hypothesis.confidence * 100)}%`,
                height: "100%",
                background:
                  hypothesis.confidence >= 0.7
                    ? "#ef4444"
                    : hypothesis.confidence >= 0.4
                    ? "#f59e0b"
                    : "#10b981",
                transition: "width 0.4s ease",
              }}
            />
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", fontSize: 11, color: "var(--muted)" }}>
            <span>Supporting ({hypothesis.supporting_evidence_ids.length})</span>
            <span>·</span>
            <span>Contradicting ({hypothesis.contradicting_evidence_ids.length})</span>
          </div>
        </div>
      ) : null}

      {/* Interactive Action Artifact View */}
      {type === "action" ? (
        <div style={{ display: "grid", gap: 10, marginTop: 4 }}>
          {actionSuccess ? (
            <p style={{ margin: 0, color: "#4ade80", fontSize: 13, fontWeight: 600 }}>
              {actionSuccess}
            </p>
          ) : (
            <>
              <input
                type="text"
                placeholder="Optional steering instructions for reviewer..."
                value={guidanceText}
                onChange={(e) => setGuidanceText(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: "rgba(0,0,0,0.2)",
                  color: "inherit",
                  fontSize: 13,
                }}
                disabled={isSubmitting}
                aria-label="Steering Guidance"
              />
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => void handleAction("approve")}
                  disabled={isSubmitting}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 6,
                    border: "none",
                    background: "#16a34a",
                    color: "white",
                    fontWeight: 600,
                    fontSize: 12,
                    cursor: isSubmitting ? "not-allowed" : "pointer",
                  }}
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => void handleAction("reject")}
                  disabled={isSubmitting}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 6,
                    border: "none",
                    background: "#dc2626",
                    color: "white",
                    fontWeight: 600,
                    fontSize: 12,
                    cursor: isSubmitting ? "not-allowed" : "pointer",
                  }}
                >
                  Reject
                </button>
                <button
                  type="button"
                  onClick={() => void handleAction("request_revision")}
                  disabled={isSubmitting}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 6,
                    border: "1px solid rgba(224,168,0,0.5)",
                    background: "rgba(224,168,0,0.2)",
                    color: "#f3c452",
                    fontWeight: 600,
                    fontSize: 12,
                    cursor: isSubmitting ? "not-allowed" : "pointer",
                  }}
                >
                  Request Revision
                </button>
              </div>
            </>
          )}
        </div>
      ) : null}

      {/* Tool Execution Artifact View */}
      {type === "tool" ? (
        <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontFamily: "monospace", fontSize: 12 }}>tool: {toolName}</span>
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--accent, #3b82f6)",
                fontSize: 11,
                cursor: "pointer",
                padding: 0,
              }}
            >
              {isExpanded ? "Collapse Output ▲" : "View Output ▼"}
            </button>
          </div>
          {isExpanded && toolOutput ? (
            <pre
              style={{
                margin: 0,
                padding: 8,
                background: "rgba(0,0,0,0.3)",
                borderRadius: 4,
                fontSize: 11,
                overflowX: "auto",
                fontFamily: "monospace",
              }}
            >
              {typeof toolOutput === "string" ? toolOutput : JSON.stringify(toolOutput, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

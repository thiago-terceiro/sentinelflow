"use client";

import { memo, useState } from "react";
import type { ApprovalDecision } from "@/lib/types";

type Props = {
  requiresApproval: boolean;
  isSubmitting: boolean;
  onDecision: (
    decision: ApprovalDecision,
    comment: string,
    guidance?: string
  ) => Promise<void> | void;
};

export const ApprovalPanel = memo(({ requiresApproval, isSubmitting, onDecision }: Props) => {
  const [comment, setComment] = useState("Risk threshold crossed; reviewer confirmation required.");
  const [guidance, setGuidance] = useState("");
  const [isSteeringOpen, setIsSteeringOpen] = useState(false);

  if (!requiresApproval) {
    return (
      <section className="shell-card" style={{ padding: 24 }}>
        <h2>Human Approval & Steering</h2>
        <p style={{ color: "var(--muted)" }}>No review action is currently required.</p>
      </section>
    );
  }

  const handleApprove = () => {
    void onDecision("approve", comment);
  };

  const handleDeny = () => {
    void onDecision("deny", comment);
  };

  const handleRequestRevision = () => {
    const steeringGuidance = guidance.trim() || comment;
    void onDecision("request_revision", comment, steeringGuidance);
  };

  return (
    <section className="shell-card" style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2>Human Approval & Steering (LangGraph Interrupt)</h2>
          <p style={{ color: "var(--muted)", margin: "4px 0 16px 0" }}>
            The graph interrupted execution at the <code>approval</code> checkpoint. Reviewers can
            approve, deny, or steer the agent to re-investigate.
          </p>
        </div>
        <span
          style={{
            padding: "4px 10px",
            borderRadius: 999,
            fontSize: 12,
            background: "rgba(224,168,0,0.15)",
            color: "#f3c452",
            border: "1px solid rgba(224,168,0,0.3)",
          }}
        >
          Awaiting Human Action
        </span>
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 600 }}>
          Reviewer Assessment / Rationale
        </label>
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          rows={3}
          style={{
            width: "100%",
            borderRadius: 10,
            border: "1px solid var(--panel-border)",
            padding: 12,
            background: "rgba(0,0,0,0.1)",
            color: "inherit",
          }}
        />
      </div>

      {isSteeringOpen ? (
        <div
          style={{
            marginBottom: 16,
            padding: 16,
            borderRadius: 12,
            background: "rgba(99,102,241,0.08)",
            border: "1px solid rgba(99,102,241,0.25)",
          }}
        >
          <label
            style={{
              display: "block",
              marginBottom: 6,
              fontSize: 13,
              fontWeight: 600,
              color: "#818cf8",
            }}
          >
            🎯 Agent Re-Investigation Steering Guidance
          </label>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>
            Instruct the investigator agent on which hypotheses to challenge, what specific tools to
            invoke, or which evidence contradictions to resolve.
          </p>
          <textarea
            value={guidance}
            onChange={(event) => setGuidance(event.target.value)}
            placeholder="e.g. Cross-examine the device geolocation with transaction IP velocity and re-evaluate the customer stability hypothesis..."
            rows={3}
            style={{
              width: "100%",
              borderRadius: 10,
              border: "1px solid rgba(99,102,241,0.3)",
              padding: 12,
              background: "rgba(0,0,0,0.2)",
              color: "inherit",
            }}
          />
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <button
          onClick={handleApprove}
          disabled={isSubmitting}
          style={{
            border: 0,
            borderRadius: 999,
            padding: "10px 20px",
            background: "var(--success)",
            color: "white",
            fontWeight: 600,
            cursor: isSubmitting ? "not-allowed" : "pointer",
          }}
        >
          {isSubmitting ? "Submitting..." : "✓ Approve Recommendation"}
        </button>

        <button
          onClick={handleDeny}
          disabled={isSubmitting}
          style={{
            border: 0,
            borderRadius: 999,
            padding: "10px 20px",
            background: "var(--danger)",
            color: "white",
            fontWeight: 600,
            cursor: isSubmitting ? "not-allowed" : "pointer",
          }}
        >
          {isSubmitting ? "Submitting..." : "✗ Deny Dispute"}
        </button>

        {!isSteeringOpen ? (
          <button
            onClick={() => setIsSteeringOpen(true)}
            disabled={isSubmitting}
            style={{
              border: "1px solid rgba(99,102,241,0.4)",
              borderRadius: 999,
              padding: "10px 20px",
              background: "rgba(99,102,241,0.15)",
              color: "#a5b4fc",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            ⟲ Request Revision (Steer Agent)
          </button>
        ) : (
          <button
            onClick={handleRequestRevision}
            disabled={isSubmitting}
            style={{
              border: 0,
              borderRadius: 999,
              padding: "10px 20px",
              background: "#6366f1",
              color: "white",
              fontWeight: 600,
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            {isSubmitting ? "Submitting..." : "⟲ Send Steering & Resume Loop"}
          </button>
        )}
      </div>
    </section>
  );
});

ApprovalPanel.displayName = "ApprovalPanel";

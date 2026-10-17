"use client";

import { useState } from "react";
import type { AuditRecord } from "@/lib/types";
import { createAuditCorrection } from "@/lib/api";

type Props = {
  target: AuditRecord | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
};

export const AuditCorrectionModal = ({ target, isOpen, onClose, onSuccess }: Props) => {
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen || !target) {
    return null;
  }

  const handleSubmit = async () => {
    if (!target.investigation_id) {
      return;
    }

    setIsSubmitting(true);
    setFeedback(null);

    try {
      await createAuditCorrection(target.investigation_id, {
        supersedes_event_id: target.id,
        reason_code: "AUDITOR_DISCREPANCY",
        note: reason || "Auditor flagged discrepancy for offline model evaluation",
      });
      setFeedback("✓ Immutable audit correction appended successfully.");
      setTimeout(() => {
        onClose();
        onSuccess();
      }, 1200);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Correction failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.7)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        className="shell-card"
        style={{
          width: "min(520px, 90vw)",
          padding: 28,
          background: "#0c1322",
        }}
      >
        <h2 style={{ marginTop: 0, fontSize: 18 }}>Submit Auditor Correction (Append-Only)</h2>
        <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>
          Under strict regulatory audit rules, records are immutable. Submitting a correction will
          append a new audit record pointing to record #{target.sequence_no}.
        </p>

        <div style={{ marginBottom: 14 }}>
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
            Reason for Flagging / Discrepancy
          </label>
          <textarea
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Evidence contradiction unresolved by model; requires prompt calibration..."
            style={{
              width: "100%",
              borderRadius: 8,
              border: "1px solid var(--panel-border)",
              background: "rgba(0,0,0,0.2)",
              padding: 10,
              color: "inherit",
              fontSize: 13,
            }}
          />
        </div>

        {feedback ? (
          <p
            style={{
              fontSize: 12,
              color: feedback.startsWith("✓") ? "var(--success)" : "var(--danger)",
              marginBottom: 12,
            }}
          >
            {feedback}
          </p>
        ) : null}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: "1px solid var(--panel-border)",
              background: "transparent",
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !reason.trim()}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: 0,
              background: "#f59e0b",
              color: "black",
              fontWeight: 600,
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            {isSubmitting ? "Appending..." : "Confirm & Append"}
          </button>
        </div>
      </div>
    </div>
  );
};

"use client";

import React, { useEffect, useId, useRef, useState } from "react";
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

  const titleId = useId();
  const descId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Close on Escape key & trap Tab focus within modal, restoring focus on close
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const previousActiveElement = document.activeElement as HTMLElement | null;
    if (textareaRef.current) {
      textareaRef.current.focus();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = Array.from(
          dialogRef.current.querySelectorAll<HTMLElement>(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        );
        if (focusable.length === 0) {
          e.preventDefault();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first || document.activeElement === dialogRef.current) {
            e.preventDefault();
            last.focus();
          }
        } else if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (previousActiveElement && typeof previousActiveElement.focus === "function") {
        previousActiveElement.focus();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen || !target) {
    return null;
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !isSubmitting) {
      onClose();
    }
  };

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
      onClick={handleBackdropClick}
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
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        className="shell-card"
        style={{
          width: "min(520px, 90vw)",
          padding: 28,
          background: "#0c1322",
        }}
      >
        <h2 id={titleId} style={{ marginTop: 0, fontSize: 18 }}>
          Submit Auditor Correction (Append-Only)
        </h2>
        <p id={descId} style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>
          Under strict regulatory audit rules, records are immutable. Submitting a correction will
          append a new audit record pointing to record #{target.sequence_no}.
        </p>

        <div style={{ marginBottom: 14 }}>
          <label
            htmlFor="audit-correction-reason"
            style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}
          >
            Reason for Flagging / Discrepancy
          </label>
          <textarea
            ref={textareaRef}
            id="audit-correction-reason"
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
            type="button"
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
            type="button"
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

"use client";

import { useState } from "react";

type Props = {
    requiresApproval: boolean;
    isSubmitting: boolean;
    onDecision: (decision: "approve" | "deny", comment: string) => Promise<void> | void;
};

export function ApprovalPanel({ requiresApproval, isSubmitting, onDecision }: Props) {
    const [comment, setComment] = useState("Risk threshold crossed; reviewer confirmation required.");
    if (!requiresApproval) {
        return (
            <section className="shell-card" style={{ padding: 24 }}>
                <h2>Human approval</h2>
                <p style={{ color: "var(--muted)" }}>No review action is currently required.</p>
            </section>
        );
    }
    return (
        <section className="shell-card" style={{ padding: 24 }}>
            <h2>Human approval</h2>
            <p>Recommendation requires reviewer action before the investigation can finalize.</p>
            <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                rows={4}
                style={{ width: "100%", borderRadius: 14, border: "1px solid var(--panel-border)", padding: 12 }}
            />
            <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
                <button
                    onClick={() => onDecision("approve", comment)}
                    disabled={isSubmitting}
                    style={{ border: 0, borderRadius: 999, padding: "12px 18px", background: "var(--success)", color: "white" }}
                >
                    {isSubmitting ? "Submitting..." : "Approve"}
                </button>
                <button
                    onClick={() => onDecision("deny", comment)}
                    disabled={isSubmitting}
                    style={{ border: 0, borderRadius: 999, padding: "12px 18px", background: "var(--danger)", color: "white" }}
                >
                    {isSubmitting ? "Submitting..." : "Deny"}
                </button>
            </div>
        </section>
    );
}

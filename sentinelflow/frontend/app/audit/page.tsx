"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAuditIntegrity, getAuditRecords, createAuditCorrection } from "@/lib/api";
import type { AuditIntegrity, AuditRecord } from "@/lib/types";

export const AuditPage = () => {
    const [records, setRecords] = useState<AuditRecord[]>([]);
    const [integrity, setIntegrity] = useState<AuditIntegrity | null>(null);
    const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [disputeIdInput, setDisputeIdInput] = useState("");
    const [eventFilter, setEventFilter] = useState("all");
    const [limit, setLimit] = useState(100);

    // Correction modal
    const [isCorrectionModalOpen, setIsCorrectionModalOpen] = useState(false);
    const [correctionTarget, setCorrectionTarget] = useState<AuditRecord | null>(null);
    const [correctionReason, setCorrectionReason] = useState("");
    const [correctionFeedback, setCorrectionFeedback] = useState<string | null>(null);
    const [isSubmittingCorrection, setIsSubmittingCorrection] = useState(false);

    const loadAuditData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const params: { dispute_id?: string; event_name?: string; limit?: number } = { limit };
            if (disputeIdInput.trim()) {
                params.dispute_id = disputeIdInput.trim();
            }
            if (eventFilter !== "all") {
                params.event_name = eventFilter;
            }
            const data = await getAuditRecords(params);
            setRecords(data);

            // Fetch integrity if we have an investigation ID
            const activeInvId = data.find((r) => Boolean(r.investigation_id))?.investigation_id;
            if (activeInvId) {
                try {
                    const intRes = await getAuditIntegrity(activeInvId);
                    setIntegrity(intRes);
                } catch {
                    setIntegrity(null);
                }
            } else {
                setIntegrity(null);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load audit records.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadAuditData();
    }, [eventFilter, limit]);

    const handleSearchSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        void loadAuditData();
    };

    const handleOpenCorrection = (record: AuditRecord) => {
        setCorrectionTarget(record);
        setCorrectionReason("");
        setCorrectionFeedback(null);
        setIsCorrectionModalOpen(true);
    };

    const handleSubmitCorrection = async () => {
        if (!correctionTarget || !correctionTarget.investigation_id) {
            return;
        }
        setIsSubmittingCorrection(true);
        setCorrectionFeedback(null);
        try {
            await createAuditCorrection(correctionTarget.investigation_id, {
                target_record_id: correctionTarget.id,
                reason: correctionReason,
                proposed_payload: {
                    reviewer_note: "Auditor flagged discrepancy for offline model evaluation",
                    corrected_at: new Date().toISOString(),
                },
            });
            setCorrectionFeedback("✓ Immutable audit correction appended successfully.");
            setTimeout(() => {
                setIsCorrectionModalOpen(false);
                void loadAuditData();
            }, 1200);
        } catch (err) {
            setCorrectionFeedback(err instanceof Error ? err.message : "Correction failed.");
        } finally {
            setIsSubmittingCorrection(false);
        }
    };

    const handleExportFinetuningDataset = () => {
        const llmRecords = records.filter(
            (r) =>
                r.event_name === "investigation.llm_iteration" ||
                r.event_name === "investigation.synthesis",
        );

        const dataset = llmRecords.map((r) => {
            const p = r.payload;
            return {
                id: r.id,
                event_name: r.event_name,
                model_used: p.model_used,
                prompt_text: p.prompt_text,
                thought_process: p.thought_process ?? p.reasoning_text,
                output_text: p.output_text,
                recommendation: p.recommendation,
                tokens: {
                    input: p.input_tokens,
                    output: p.output_tokens,
                    reasoning: p.reasoning_tokens,
                },
                latency_ms: p.latency_ms,
                audit_hash: r.row_hash,
            };
        });

        const jsonStr = JSON.stringify(dataset, null, 2);
        const blob = new Blob([jsonStr], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `sentinelflow-ai-eval-dataset-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <main style={{ width: "min(1150px, calc(100vw - 2rem))", margin: "24px auto 48px" }}>
            {/* Header section */}
            <div
                className="shell-card"
                style={{
                    padding: 28,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 16,
                    marginBottom: 20,
                }}
            >
                <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                        <span
                            style={{
                                fontSize: 11,
                                textTransform: "uppercase",
                                letterSpacing: "0.08em",
                                color: "var(--muted)",
                            }}
                        >
                            AI Governance & Observability Portal
                        </span>
                        <span
                            style={{
                                padding: "2px 8px",
                                borderRadius: 999,
                                fontSize: 11,
                                background: "rgba(34,197,94,0.15)",
                                color: "var(--success)",
                                border: "1px solid rgba(34,197,94,0.3)",
                            }}
                        >
                            Auditor Role Active
                        </span>
                    </div>
                    <h1 style={{ margin: 0 }}>SentinelFlow Audit Ledger & Traces</h1>
                    <p style={{ margin: "6px 0 0 0", color: "var(--muted)", fontSize: 13 }}>
                        Continuous AI compliance, PII redaction verification, and fine-tuning telemetry for EU AI Act & SOC 2.
                    </p>
                </div>
                <div style={{ display: "flex", gap: 10 }}>
                    <button
                        onClick={handleExportFinetuningDataset}
                        style={{
                            border: "1px solid rgba(255,255,255,0.15)",
                            borderRadius: 999,
                            padding: "10px 18px",
                            background: "rgba(255,255,255,0.05)",
                            color: "var(--foreground)",
                            fontSize: 13,
                            fontWeight: 600,
                            cursor: "pointer",
                        }}
                    >
                        📥 Export AI Eval / Fine-Tuning Pairs
                    </button>
                    <Link
                        href="/"
                        style={{
                            borderRadius: 999,
                            padding: "10px 18px",
                            background: "var(--accent)",
                            color: "white",
                            fontSize: 13,
                            fontWeight: 600,
                            textDecoration: "none",
                            display: "inline-flex",
                            alignItems: "center",
                        }}
                    >
                        ← Back to Disputes
                    </Link>
                </div>
            </div>

            {/* Compliance & Integrity Status Cards */}
            <div
                style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                    gap: 16,
                    marginBottom: 20,
                }}
            >
                {/* Cryptographic hash chain */}
                <div className="shell-card" style={{ padding: 20 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 16 }}>🔒</span>
                        <h4 style={{ margin: 0, fontSize: 14 }}>SHA-256 Tamper-Evidence</h4>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px 0" }}>
                        Each audit row cryptographically seals <code>prev_hash</code> into sequence <code>N+1</code>.
                    </p>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span
                            style={{
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                background: integrity?.valid !== false ? "var(--success)" : "var(--danger)",
                            }}
                        />
                        <span style={{ fontSize: 13, fontWeight: 600 }}>
                            {integrity?.valid ? "Hash Chain Verified Unbroken" : "Append-Only Hash Chained"}
                        </span>
                    </div>
                </div>

                {/* PII Governance */}
                <div className="shell-card" style={{ padding: 20 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 16 }}>🛡️</span>
                        <h4 style={{ margin: 0, fontSize: 14 }}>PII Scrubbing & PCI-DSS</h4>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px 0" }}>
                        Card numbers, SSN, email, and IP addresses automatically sanitized prior to storage and LLM context.
                    </p>
                    <span
                        style={{
                            fontSize: 12,
                            padding: "3px 8px",
                            borderRadius: 6,
                            background: "rgba(59,130,246,0.15)",
                            color: "#93c5fd",
                            fontWeight: 600,
                        }}
                    >
                        Redaction Policy: pii_redaction_v1
                    </span>
                </div>

                {/* EU AI Act / SOC 2 */}
                <div className="shell-card" style={{ padding: 20 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 16 }}>📜</span>
                        <h4 style={{ margin: 0, fontSize: 14 }}>EU AI Act Article 12 Logging</h4>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px 0" }}>
                        Continuous logging of model inputs, reasoning tokens, template versions, and human steering events.
                    </p>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)" }}>
                        {records.length} Total Audit Records
                    </span>
                </div>
            </div>

            {/* Filter and Search Bar */}
            <div
                className="shell-card"
                style={{
                    padding: "16px 20px",
                    marginBottom: 20,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 16,
                    flexWrap: "wrap",
                }}
            >
                <form
                    onSubmit={handleSearchSubmit}
                    style={{ display: "flex", gap: 10, alignItems: "center", flex: 1, minWidth: 260 }}
                >
                    <input
                        type="text"
                        placeholder="Filter by Dispute ID (e.g. disp_...)"
                        value={disputeIdInput}
                        onChange={(e) => setDisputeIdInput(e.target.value)}
                        style={{
                            padding: "8px 14px",
                            borderRadius: 8,
                            border: "1px solid var(--panel-border)",
                            background: "rgba(0,0,0,0.2)",
                            color: "inherit",
                            flex: 1,
                            fontSize: 13,
                        }}
                    />
                    <button
                        type="submit"
                        style={{
                            padding: "8px 16px",
                            borderRadius: 8,
                            border: 0,
                            background: "var(--accent)",
                            color: "white",
                            fontWeight: 600,
                            fontSize: 13,
                            cursor: "pointer",
                        }}
                    >
                        Search
                    </button>
                </form>

                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>Event Type:</span>
                    <select
                        value={eventFilter}
                        onChange={(e) => setEventFilter(e.target.value)}
                        style={{
                            padding: "8px 12px",
                            borderRadius: 8,
                            border: "1px solid var(--panel-border)",
                            background: "rgba(0,0,0,0.3)",
                            color: "inherit",
                            fontSize: 13,
                        }}
                    >
                        <option value="all">All Events</option>
                        <option value="investigation.llm_iteration">LLM Iterations (Reasoning)</option>
                        <option value="investigation.synthesis">Synthesis & Verdict</option>
                        <option value="investigation.tool_executed">Tool Executions</option>
                        <option value="investigation.analyzer_executed">Analyzer Executions</option>
                        <option value="approval.decision">Reviewer Steering & Approvals</option>
                    </select>

                    <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 8 }}>Limit:</span>
                    <select
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        style={{
                            padding: "8px 12px",
                            borderRadius: 8,
                            border: "1px solid var(--panel-border)",
                            background: "rgba(0,0,0,0.3)",
                            color: "inherit",
                            fontSize: 13,
                        }}
                    >
                        <option value={50}>50</option>
                        <option value={100}>100</option>
                        <option value={250}>250</option>
                        <option value={500}>500</option>
                    </select>
                </div>
            </div>

            {error ? (
                <div
                    className="shell-card"
                    style={{
                        padding: 16,
                        borderColor: "var(--danger)",
                        color: "var(--danger)",
                        marginBottom: 20,
                    }}
                >
                    {error}
                </div>
            ) : null}

            {/* Audit Log Table */}
            <div className="shell-card" style={{ padding: 24, overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                        <tr style={{ borderBottom: "1px solid var(--panel-border)", textAlign: "left" }}>
                            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Seq</th>
                            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Event Name</th>
                            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Actor</th>
                            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Timestamp</th>
                            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>PII Scrubbed</th>
                            <th style={{ padding: "10px 12px", color: "var(--muted)" }}>Hash (SHA-256)</th>
                            <th style={{ padding: "10px 12px", color: "var(--muted)", textAlign: "right" }}>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {isLoading ? (
                            <tr>
                                <td colSpan={7} style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
                                    Loading audit ledger records...
                                </td>
                            </tr>
                        ) : records.length === 0 ? (
                            <tr>
                                <td colSpan={7} style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
                                    No audit records found matching current criteria.
                                </td>
                            </tr>
                        ) : (
                            records.map((r) => {
                                const isLLM =
                                    r.event_name === "investigation.llm_iteration" ||
                                    r.event_name === "investigation.synthesis";
                                return (
                                    <tr
                                        key={r.id}
                                        style={{
                                            borderBottom: "1px solid rgba(255,255,255,0.04)",
                                            transition: "background 0.15s ease",
                                        }}
                                    >
                                        <td style={{ padding: "12px", fontWeight: 700, color: "var(--accent)" }}>
                                            #{r.sequence_no}
                                        </td>
                                        <td style={{ padding: "12px" }}>
                                            <span
                                                style={{
                                                    padding: "3px 8px",
                                                    borderRadius: 6,
                                                    background: isLLM
                                                        ? "rgba(99,102,241,0.15)"
                                                        : "rgba(255,255,255,0.06)",
                                                    color: isLLM ? "#a5b4fc" : "inherit",
                                                    fontSize: 12,
                                                }}
                                            >
                                                {r.event_name}
                                            </span>
                                        </td>
                                        <td style={{ padding: "12px", color: "var(--muted)" }}>{r.actor}</td>
                                        <td style={{ padding: "12px", fontSize: 12, color: "var(--muted)" }} suppressHydrationWarning>
                                            {new Date(r.created_at).toLocaleTimeString()}
                                        </td>
                                        <td style={{ padding: "12px" }}>
                                            <span
                                                style={{
                                                    fontSize: 11,
                                                    padding: "2px 6px",
                                                    borderRadius: 4,
                                                    background: r.is_redacted
                                                        ? "rgba(34,197,94,0.15)"
                                                        : "rgba(255,255,255,0.05)",
                                                    color: r.is_redacted ? "var(--success)" : "var(--muted)",
                                                }}
                                            >
                                                {r.is_redacted ? "✓ Protected" : "Safe"}
                                            </span>
                                        </td>
                                        <td
                                            style={{
                                                padding: "12px",
                                                fontFamily: "monospace",
                                                fontSize: 11,
                                                color: "var(--muted)",
                                            }}
                                        >
                                            {r.row_hash ? `${r.row_hash.slice(0, 10)}...` : "None"}
                                        </td>
                                        <td style={{ padding: "12px", textAlign: "right" }}>
                                            <div style={{ display: "inline-flex", gap: 8 }}>
                                                <button
                                                    onClick={() => setSelectedRecord(r)}
                                                    style={{
                                                        padding: "4px 10px",
                                                        borderRadius: 6,
                                                        border: "1px solid var(--panel-border)",
                                                        background: "rgba(255,255,255,0.04)",
                                                        color: "inherit",
                                                        fontSize: 12,
                                                        cursor: "pointer",
                                                    }}
                                                >
                                                    Inspect Trace
                                                </button>
                                                <button
                                                    onClick={() => handleOpenCorrection(r)}
                                                    style={{
                                                        padding: "4px 10px",
                                                        borderRadius: 6,
                                                        border: "1px solid rgba(224,168,0,0.3)",
                                                        background: "rgba(224,168,0,0.08)",
                                                        color: "#f3c452",
                                                        fontSize: 12,
                                                        cursor: "pointer",
                                                    }}
                                                >
                                                    Flag / Correct
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>

            {/* Deep Trace Inspector Drawer Modal */}
            {selectedRecord ? (
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
                                    Record #{selectedRecord.sequence_no}
                                </span>
                                <h2 style={{ margin: "4px 0 0 0" }}>{selectedRecord.event_name}</h2>
                            </div>
                            <button
                                onClick={() => setSelectedRecord(null)}
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
                                <strong style={{ color: "var(--muted)" }}>Actor: </strong> {selectedRecord.actor}
                            </p>
                            <p style={{ margin: "0 0 4px 0" }}>
                                <strong style={{ color: "var(--muted)" }}>Timestamp: </strong> {selectedRecord.created_at}
                            </p>
                            <p style={{ margin: "0 0 4px 0", wordBreak: "break-all" }}>
                                <strong style={{ color: "var(--muted)" }}>Row SHA-256: </strong>
                                <code style={{ color: "var(--accent)" }}>{selectedRecord.row_hash}</code>
                            </p>
                            <p style={{ margin: 0, wordBreak: "break-all" }}>
                                <strong style={{ color: "var(--muted)" }}>Prev Hash: </strong>
                                <code style={{ color: "var(--muted)" }}>{selectedRecord.prev_hash ?? "Genesis (None)"}</code>
                            </p>
                            {selectedRecord.payload.trace_id ? (
                                <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
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
                                            {String(selectedRecord.payload.trace_id)}
                                        </code>
                                    </p>
                                    {selectedRecord.payload.span_id ? (
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
                                                {String(selectedRecord.payload.span_id)}
                                            </code>
                                        </p>
                                    ) : null}
                                </div>
                            ) : null}
                        </div>

                        {/* LLM Telemetry (If present) */}
                        {selectedRecord.payload.prompt_text || selectedRecord.payload.output_text ? (
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
                                        <strong>{String(selectedRecord.payload.model_used ?? "Local Heuristic")}</strong>
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
                                            {typeof selectedRecord.payload.latency_ms === "number"
                                                ? `${selectedRecord.payload.latency_ms.toFixed(1)} ms`
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
                                            In: {String(selectedRecord.payload.input_tokens ?? 0)} / Out:{" "}
                                            {String(selectedRecord.payload.output_tokens ?? 0)}
                                        </strong>
                                    </div>
                                </div>

                                {selectedRecord.payload.thought_process ? (
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
                                            {String(selectedRecord.payload.thought_process)}
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
                                        {String(selectedRecord.payload.prompt_text ?? "None")}
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
                                        {String(selectedRecord.payload.output_text ?? "None")}
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
                                    {JSON.stringify(selectedRecord.payload, null, 2)}
                                </pre>
                            </div>
                        )}
                    </div>
                </div>
            ) : null}

            {/* Append-Only Correction Modal */}
            {isCorrectionModalOpen && correctionTarget ? (
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
                        <h2 style={{ marginTop: 0, fontSize: 18 }}>
                            Submit Auditor Correction (Append-Only)
                        </h2>
                        <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>
                            Under strict regulatory audit rules, records are immutable. Submitting a correction
                            will append a new audit record pointing to record #{correctionTarget.sequence_no}.
                        </p>

                        <div style={{ marginBottom: 14 }}>
                            <label style={{ display: "block", fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                                Reason for Flagging / Discrepancy
                            </label>
                            <textarea
                                rows={3}
                                value={correctionReason}
                                onChange={(e) => setCorrectionReason(e.target.value)}
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

                        {correctionFeedback ? (
                            <p
                                style={{
                                    fontSize: 12,
                                    color: correctionFeedback.startsWith("✓") ? "var(--success)" : "var(--danger)",
                                    marginBottom: 12,
                                }}
                            >
                                {correctionFeedback}
                            </p>
                        ) : null}

                        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                            <button
                                onClick={() => setIsCorrectionModalOpen(false)}
                                disabled={isSubmittingCorrection}
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
                                onClick={handleSubmitCorrection}
                                disabled={isSubmittingCorrection || !correctionReason.trim()}
                                style={{
                                    padding: "8px 16px",
                                    borderRadius: 8,
                                    border: 0,
                                    background: "#f59e0b",
                                    color: "black",
                                    fontWeight: 600,
                                    cursor: isSubmittingCorrection ? "not-allowed" : "pointer",
                                }}
                            >
                                {isSubmittingCorrection ? "Appending..." : "Confirm & Append"}
                            </button>
                        </div>
                    </div>
                </div>
            ) : null}
        </main>
    );
};

export default AuditPage;

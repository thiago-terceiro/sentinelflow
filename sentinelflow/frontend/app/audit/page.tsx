"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { downloadTuningDataset, getAuditIntegrity, getAuditRecords } from "@/lib/api";
import type { AuditIntegrity, AuditRecord } from "@/lib/types";
import { AiEvaluationBenchmarkPanel } from "@/components/AiEvaluationBenchmarkPanel";
import { AuditComplianceCards } from "@/components/AuditComplianceCards";
import { AuditTable } from "@/components/AuditTable";
import { AuditDetailDrawer } from "@/components/AuditDetailDrawer";
import { AuditCorrectionModal } from "@/components/AuditCorrectionModal";

export const AuditPage = () => {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [integrity, setIntegrity] = useState<AuditIntegrity | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"ledger" | "evals">("ledger");
  const [authRole, setAuthRole] = useState<string | null>(null);
  const [hasAuthChecked, setHasAuthChecked] = useState(false);

  useEffect(() => {
    let role: string | null = null;
    try {
      const match = document.cookie.match(/(?:^|;\s*)sentinelflow_test_user=([^;]+)/);
      if (match) {
        const decoded = decodeURIComponent(match[1]);
        const parts = decoded.split(":", 2);
        role = parts[1] ?? null;
      }
    } catch {
      role = null;
    }
    setAuthRole(role);
    setHasAuthChecked(true);
  }, []);

  const isAuthorized = authRole === "auditor" || authRole === "admin";

  // Filters
  const [disputeIdInput, setDisputeIdInput] = useState("");
  const [eventFilter, setEventFilter] = useState("all");
  const [limit, setLimit] = useState(100);

  // Correction modal
  const [isCorrectionModalOpen, setIsCorrectionModalOpen] = useState(false);
  const [correctionTarget, setCorrectionTarget] = useState<AuditRecord | null>(null);

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
    if (hasAuthChecked && isAuthorized) {
      void loadAuditData();
    }
  }, [hasAuthChecked, isAuthorized, eventFilter, limit]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void loadAuditData();
  };

  const handleOpenCorrection = (record: AuditRecord) => {
    setCorrectionTarget(record);
    setIsCorrectionModalOpen(true);
  };

  const handleExportFinetuningDataset = async (type: "dpo" | "sft" = "dpo") => {
    try {
      const { filename, content } = await downloadTuningDataset(type, "jsonl");
      const blob = new Blob([content], { type: "application/x-ndjson" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Fallback export from local memory
      const llmRecords = records.filter(
        (r) =>
          r.event_name === "investigation.llm_iteration" ||
          r.event_name === "investigation.synthesis"
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
    }
  };

  if (!hasAuthChecked) {
    return (
      <main>
        <div className="shell-card" style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
          Checking authorization permissions...
        </div>
      </main>
    );
  }

  if (!isAuthorized) {
    return (
      <main>
        <div
          className="shell-card"
          style={{
            padding: "48px 32px",
            textAlign: "center",
            border: "1px solid rgba(158,47,40,0.25)",
          }}
        >
          <h2 style={{ margin: "0 0 12px", color: "var(--danger)", fontSize: 24, fontWeight: 700 }}>
            Access Restricted: Auditor or Admin Role Required
          </h2>
          <p
            style={{
              color: "var(--muted)",
              maxWidth: 560,
              margin: "0 auto 24px",
              fontSize: 14,
              lineHeight: 1.6,
            }}
          >
            The SentinelFlow Audit Ledger and AI Governance Portal contain sensitive compliance traces
            and can only be accessed by users authenticated with the Auditor or Admin role.
          </p>
          <div style={{ display: "inline-flex", gap: 12 }}>
            <Link
              href="/login?returnTo=/audit"
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "10px 24px",
                background: "var(--accent)",
                color: "white",
                fontWeight: 600,
                fontSize: 13,
                textDecoration: "none",
                borderRadius: "var(--card-radius, 8px)",
              }}
            >
              Sign In as Auditor
            </Link>
            <Link
              href="/"
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "10px 24px",
                background: "rgba(255,255,255,0.06)",
                border: "1px solid var(--panel-border)",
                color: "var(--ink)",
                fontWeight: 600,
                fontSize: 13,
                textDecoration: "none",
                borderRadius: "var(--card-radius, 8px)",
              }}
            >
              Return to Disputes
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main>
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
            Continuous AI compliance, PII redaction verification, and fine-tuning telemetry for EU
            AI Act & SOC 2.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => handleExportFinetuningDataset("dpo")}
            className="audit-export-btn"
            style={{
              border: "1px solid var(--panel-border)",
              borderRadius: 999,
              padding: "10px 22px",
              minWidth: 200,
              background: "rgba(255,255,255,0.05)",
              color: "inherit",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              whiteSpace: "nowrap",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span className="page-icon">📥 </span>Export DPO Pairs (JSONL)
          </button>
          <button
            type="button"
            onClick={() => handleExportFinetuningDataset("sft")}
            className="audit-export-btn"
            style={{
              border: "1px solid var(--panel-border)",
              borderRadius: 999,
              padding: "10px 22px",
              minWidth: 180,
              background: "rgba(255,255,255,0.05)",
              color: "inherit",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              whiteSpace: "nowrap",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span className="page-icon">📥 </span>Export SFT Dataset
          </button>
          <Link
            href="/"
            style={{
              borderRadius: 999,
              padding: "10px 20px",
              background: "var(--accent)",
              color: "white",
              fontSize: 13,
              fontWeight: 600,
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            ← Back to Disputes
          </Link>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
            <button
              onClick={() => setActiveTab("ledger")}
              style={{
                padding: "10px 18px",
                borderRadius: 999,
                fontSize: 13,
                fontWeight: 600,
                border:
                  activeTab === "ledger"
                    ? "1px solid var(--accent)"
                    : "1px solid rgba(255,255,255,0.1)",
                background:
                  activeTab === "ledger" ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.03)",
                color: activeTab === "ledger" ? "var(--foreground)" : "var(--muted)",
                cursor: "pointer",
              }}
            >
              <span className="page-icon">📋 </span>Audit Ledger & Traces
            </button>
            <button
              onClick={() => setActiveTab("evals")}
              style={{
                padding: "10px 18px",
                borderRadius: 999,
                fontSize: 13,
                fontWeight: 600,
                border:
                  activeTab === "evals"
                    ? "1px solid var(--accent)"
                    : "1px solid rgba(255,255,255,0.1)",
                background:
                  activeTab === "evals" ? "rgba(59,130,246,0.15)" : "rgba(255,255,255,0.03)",
                color: activeTab === "evals" ? "var(--foreground)" : "var(--muted)",
                cursor: "pointer",
              }}
            >
              <span className="page-icon">🎯 </span>AI Model Evaluations & Continuous Improvement
            </button>
          </div>

      {activeTab === "evals" ? (
        <AiEvaluationBenchmarkPanel />
      ) : (
        <>
          {/* Compliance & Integrity Status Cards */}
          <AuditComplianceCards integrity={integrity} recordCount={records.length} />

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
                  background: "var(--input-bg, #ffffff)",
                  color: "inherit",
                  flex: 1,
                  fontSize: 13,
                }}
              />
              <button
                type="submit"
                className="audit-search-btn"
                style={{
                  padding: "8px 16px",
                  borderRadius: "var(--card-radius, 8px)",
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
                  background: "var(--input-bg, #ffffff)",
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
                  background: "var(--input-bg, #ffffff)",
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
          <AuditTable
            records={records}
            isLoading={isLoading}
            onSelectRecord={(r) => setSelectedRecord(r)}
            onOpenCorrection={handleOpenCorrection}
          />

          {/* Deep Trace Inspector Drawer Modal */}
          <AuditDetailDrawer record={selectedRecord} onClose={() => setSelectedRecord(null)} />

          {/* Append-Only Correction Modal */}
          <AuditCorrectionModal
            target={correctionTarget}
            isOpen={isCorrectionModalOpen}
            onClose={() => setIsCorrectionModalOpen(false)}
            onSuccess={() => void loadAuditData()}
          />
        </>
      )}
    </main>
  );
};

export default AuditPage;

"use client";

import { AgentMessageStrip } from "@/components/AgentMessageStrip";
import { AnalyzerPanel } from "@/components/AnalyzerPanel";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { EvidencePanel } from "@/components/EvidencePanel";
import { InvestigationTimeline } from "@/components/InvestigationTimeline";
import { RiskPanel } from "@/components/RiskPanel";
import { useSentinelAgent } from "@/hooks/useSentinelAgent";

type Props = {
    disputeId: string;
};

export function InvestigationConsole({ disputeId }: Props) {
    const { state, isLaunching, isReviewing, launch, review } = useSentinelAgent(disputeId);

    return (
        <ErrorBoundary>
            <section style={{ display: "grid", gap: 20 }}>
                <div className="shell-card" style={{ padding: 28, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
                    <div>
                        <p style={{ margin: 0, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                            SentinelFlow console
                        </p>
                        <h1 style={{ marginBottom: 0 }}>Dispute {disputeId}</h1>
                    </div>
                    <button
                        onClick={() => void launch()}
                        disabled={isLaunching || state.status === "RUNNING"}
                        style={{ border: 0, borderRadius: 999, padding: "14px 20px", background: "var(--accent)", color: "white" }}
                    >
                        {isLaunching ? "Starting..." : state.investigationId ? "Run again" : "Start investigation"}
                    </button>
                </div>

                {state.error ? (
                    <div className="shell-card" style={{ padding: 18, borderColor: "rgba(158,47,40,0.25)", color: "var(--danger)" }}>
                        {state.error}
                    </div>
                ) : null}

                {state.streamConnection === "reconnecting" ? (
                    <div
                        className="shell-card"
                        style={{
                            padding: 18,
                            borderColor: "rgba(224,168,0,0.35)",
                            color: "#f3c452",
                        }}
                    >
                        Reconnecting to investigation stream (attempt {state.reconnectAttempt}
                        {state.nextReconnectDelayMs !== null ? `, next retry in ${Math.ceil(state.nextReconnectDelayMs / 1000)}s` : ""}).
                    </div>
                ) : null}

                {state.streamConnection === "disconnected" && state.status === "RUNNING" ? (
                    <div className="shell-card" style={{ padding: 18, borderColor: "rgba(158,47,40,0.25)", color: "var(--danger)" }}>
                        Investigation is running, but the stream is disconnected. The console will refresh when recovery succeeds.
                    </div>
                ) : null}

                <AgentMessageStrip message={state.agentStatus} status={state.status} />

                <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 0.9fr) minmax(0, 1.4fr)", gap: 20, alignItems: "start" }}>
                    <InvestigationTimeline
                        status={state.status}
                        events={state.timeline}
                    />
                    <EvidencePanel
                        evidence={state.evidence}
                        isLoading={state.status === "RUNNING" && state.evidence.length === 0}
                    />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 20 }}>
                    <RiskPanel risk={state.riskAssessment} />
                    <AnalyzerPanel analyzers={state.analyzerSummaries} />
                </div>

                <ApprovalPanel
                    requiresApproval={state.requiresApproval}
                    isSubmitting={isReviewing}
                    onDecision={(decision, comment) => review(decision, comment)}
                />

                {state.report && state.isReportUnlocked ? (
                    <section className="shell-card" style={{ padding: 24 }}>
                        <h2>Recommendation</h2>
                        <p style={{ fontSize: 24, marginBottom: 8 }}>{state.report.recommendation.toUpperCase()}</p>
                        <p>{state.report.conclusion}</p>
                    </section>
                ) : state.status !== "IDLE" ? (
                    <section className="shell-card" style={{ padding: 24 }}>
                        <h2>Recommendation</h2>
                        <p style={{ fontSize: 24, marginBottom: 8 }}>IN PROGRESS</p>
                        <p>
                            {state.requiresApproval
                                ? "Recommendation is ready and waiting for approval."
                                : state.agentStatus ?? "The investigation is still gathering evidence and drafting a recommendation."}
                        </p>
                    </section>
                ) : null}
            </section>
        </ErrorBoundary>
    );
}

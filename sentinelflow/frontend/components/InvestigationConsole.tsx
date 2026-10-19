"use client";

import { useCallback } from "react";

import { AgentMessageStrip } from "@/components/AgentMessageStrip";
import { AgentReasoningPanel } from "@/components/AgentReasoningPanel";
import { AnalyzerPanel } from "@/components/AnalyzerPanel";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { EvidencePanel } from "@/components/EvidencePanel";
import { InvestigationTimeline } from "@/components/InvestigationTimeline";
import { LangGraphProgress } from "@/components/LangGraphProgress";
import { RiskPanel } from "@/components/RiskPanel";
import { useSentinelAgent } from "@/hooks/useSentinelAgent";
import type { ApprovalDecision } from "@/lib/types";

type Props = {
  disputeId: string;
};

export const InvestigationConsole = ({ disputeId }: Props) => {
  const { state, isLaunching, isReviewing, launch, review } = useSentinelAgent(disputeId);

  const handleDecision = useCallback(
    (decision: ApprovalDecision, comment: string, guidance?: string) => {
      void review(decision, comment, guidance);
    },
    [review]
  );

  const getLaunchButtonLabel = () => {
    if (isLaunching) {
      return "Starting...";
    }
    if (state.investigationId) {
      return "Re-run investigation";
    }
    return "Start agent investigation";
  };

  const getRecommendationColor = (recommendation: string) => {
    if (recommendation === "approve") {
      return "var(--success)";
    }
    if (recommendation === "deny") {
      return "var(--danger)";
    }
    return "var(--accent)";
  };

  const renderRecommendationSection = () => {
    if (state.report && state.isReportUnlocked) {
      return (
        <section className="shell-card" style={{ padding: 24 }}>
          <span
            style={{
              fontSize: 11,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--muted)",
            }}
          >
            Final Synthesis & Verdict
          </span>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginTop: 4,
              marginBottom: 8,
            }}
          >
            <h2 style={{ fontSize: 24, margin: 0 }}>
              Recommendation:{" "}
              <span style={{ color: getRecommendationColor(state.report.recommendation) }}>
                {state.report.recommendation.toUpperCase()}
              </span>
            </h2>
            <span
              style={{
                fontSize: 13,
                padding: "3px 8px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.08)",
              }}
            >
              {Math.round(state.report.confidence * 100)}% confidence
            </span>
          </div>
          <p style={{ lineHeight: 1.6 }}>{state.report.conclusion}</p>
        </section>
      );
    }

    if (state.status !== "IDLE") {
      const inProgressMessage = state.requiresApproval
        ? "Recommendation is ready and waiting for reviewer approval."
        : (state.agentStatus ??
          "The investigation is still gathering evidence and formulating hypotheses.");

      return (
        <section className="shell-card" style={{ padding: 24 }}>
          <h2>Recommendation</h2>
          <p style={{ fontSize: 24, marginBottom: 8 }}>IN PROGRESS</p>
          <p>{inProgressMessage}</p>
        </section>
      );
    }

    return null;
  };

  return (
    <ErrorBoundary>
      <section style={{ display: "grid", gap: 20 }}>
        {/* Header card with action buttons */}
        <div
          className="shell-card"
          style={{
            padding: 28,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 16,
          }}
        >
          <div>
            <p
              style={{
                margin: 0,
                color: "var(--muted)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                fontSize: 12,
              }}
            >
              SentinelFlow Agent Console
            </p>
            <h1 style={{ marginBottom: 0, marginTop: 4 }}>Dispute {disputeId}</h1>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button
              onClick={() => void launch()}
              disabled={isLaunching || state.status === "RUNNING"}
              style={{
                border: 0,
                borderRadius: 999,
                padding: "14px 24px",
                background: "var(--accent)",
                color: "white",
                fontWeight: 600,
                cursor: isLaunching || state.status === "RUNNING" ? "not-allowed" : "pointer",
              }}
            >
              {getLaunchButtonLabel()}
            </button>
          </div>
        </div>

        {/* LangGraph Pipeline Stage Indicator */}
        <LangGraphProgress
          currentPhase={state.currentPhase}
          status={state.status}
          reviewerGuidance={state.reviewerGuidance}
        />

        {state.error ? (
          <div
            className="shell-card"
            style={{
              padding: 18,
              borderColor: "rgba(158,47,40,0.25)",
              color: "var(--danger)",
            }}
          >
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
            {state.nextReconnectDelayMs !== null
              ? `, next retry in ${Math.ceil(state.nextReconnectDelayMs / 1000)}s`
              : ""}
            ).
          </div>
        ) : null}

        {state.streamConnection === "disconnected" && state.status === "RUNNING" ? (
          <div
            className="shell-card"
            style={{
              padding: 18,
              borderColor: "rgba(158,47,40,0.25)",
              color: "var(--danger)",
            }}
          >
            Investigation is running, but the stream is disconnected. The console will refresh when
            recovery succeeds.
          </div>
        ) : null}

        <AgentMessageStrip message={state.agentStatus} status={state.status} />

        {/* Primary Agent Reasoning & Hypotheses Panel */}
        <AgentReasoningPanel
          thoughtProcess={state.activeThoughtProcess}
          reasoningSteps={state.reasoningSteps}
          hypotheses={state.hypotheses}
          isLoading={state.status === "RUNNING"}
        />

        {/* Timeline and Evidence Panels */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(260px, 0.9fr) minmax(0, 1.4fr)",
            gap: 20,
            alignItems: "start",
          }}
        >
          <InvestigationTimeline status={state.status} events={state.timeline} />
          <EvidencePanel
            evidence={state.evidence}
            isLoading={state.status === "RUNNING" && state.evidence.length === 0}
          />
        </div>

        {/* Risk and Analyzers */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 20 }}>
          <RiskPanel risk={state.riskAssessment} />
          <AnalyzerPanel analyzers={state.analyzerSummaries} />
        </div>

        {/* Human in the loop Approval and Steering Panel */}
        <ApprovalPanel
          requiresApproval={state.requiresApproval}
          isSubmitting={isReviewing}
          onDecision={handleDecision}
        />

        {/* Final Synthesis Recommendation */}
        {renderRecommendationSection()}
      </section>
    </ErrorBoundary>
  );
};

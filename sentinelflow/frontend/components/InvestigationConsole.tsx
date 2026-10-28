"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AgentMessageStrip } from "@/components/AgentMessageStrip";
import { AgentReasoningPanel } from "@/components/AgentReasoningPanel";
import { AnalyzerPanel } from "@/components/AnalyzerPanel";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { EvidencePanel } from "@/components/EvidencePanel";
import { GenUIArtifactCard } from "@/components/GenUIArtifactCard";
import { InvestigationTimeline } from "@/components/InvestigationTimeline";
import { LangGraphProgress } from "@/components/LangGraphProgress";
import { RiskPanel } from "@/components/RiskPanel";
import { TimeTravelScrubber } from "@/components/TimeTravelScrubber";
import { useSentinelAgent } from "@/hooks/useSentinelAgent";
import { resolveActiveEvidenceId } from "@/lib/investigationState";
import type { ApprovalDecision } from "@/lib/types";

type Props = {
  disputeId: string;
};

export const InvestigationConsole = ({ disputeId }: Props) => {
  const {
    state,
    rawEvents,
    selectedEventIndex,
    isHydrated,
    goToStep,
    goToPreviousStep,
    goToNextStep,
    goToLiveHead,
    iterationSnapshots,
    iterationDiffs,
    isLaunching,
    isReviewing,
    launch,
    review,
  } = useSentinelAgent(disputeId);

  const [pinnedEvidenceId, setPinnedEvidenceId] = useState<string | null>(null);
  const [hoveredEvidenceId, setHoveredEvidenceId] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState<boolean>(false);
  const [showGenUI, setShowGenUI] = useState<boolean>(false);
  const initialStepHydratedRef = useRef<boolean>(false);
  const initialStepTargetRef = useRef<number | null>(null);

  const highlightedEvidenceId = resolveActiveEvidenceId(pinnedEvidenceId, hoveredEvidenceId);

  // Hydrate initial URL query params (?step=, ?diff=, ?evidence=)
  useEffect(() => {
    initialStepHydratedRef.current = false;
    initialStepTargetRef.current = null;
    try {
      if (typeof window === "undefined") {
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const stepParam = params.get("step");
      if (stepParam !== null) {
        const parsed = Number.parseInt(stepParam, 10);
        if (!Number.isNaN(parsed) && parsed >= 0) {
          initialStepTargetRef.current = parsed;
        }
      }
      const diffParam = params.get("diff");
      setShowDiff(diffParam === "1" || diffParam === "true");
      const genuiParam = params.get("genui");
      setShowGenUI(genuiParam === "1" || genuiParam === "true");
      const evParam = params.get("evidence");
      setPinnedEvidenceId(evParam || null);
    } catch {
      // Ignore malformed URL query parameters
    }
  }, [disputeId]);

  // Apply hydrated step index once initial mount hydration completes
  useEffect(() => {
    if (!isHydrated || initialStepHydratedRef.current) {
      return;
    }
    if (initialStepTargetRef.current !== null && rawEvents.length > 0) {
      const clampedStep = Math.min(initialStepTargetRef.current, rawEvents.length - 1);
      initialStepHydratedRef.current = true;
      goToStep(clampedStep);
      return;
    }
    if (initialStepTargetRef.current === null || rawEvents.length === 0) {
      initialStepHydratedRef.current = true;
    }
  }, [isHydrated, rawEvents.length, goToStep]);

  // Validate pinnedEvidenceId against loaded evidence items
  useEffect(() => {
    if (
      isHydrated &&
      pinnedEvidenceId !== null &&
      state.evidence.length > 0 &&
      !state.evidence.some((item) => item.id === pinnedEvidenceId)
    ) {
      setPinnedEvidenceId(null);
    }
  }, [isHydrated, pinnedEvidenceId, state.evidence]);

  // Synchronize workbench state to URL search params (debounced 150ms to prevent slider thrashing)
  useEffect(() => {
    if (!isHydrated || !initialStepHydratedRef.current) {
      return;
    }
    const timer = window.setTimeout(() => {
      try {
        if (typeof window === "undefined") {
          return;
        }
        const params = new URLSearchParams(window.location.search);
        if (selectedEventIndex !== null) {
          params.set("step", String(selectedEventIndex));
        } else {
          params.delete("step");
        }
        if (showDiff) {
          params.set("diff", "1");
        } else {
          params.delete("diff");
        }
        if (pinnedEvidenceId) {
          params.set("evidence", pinnedEvidenceId);
        } else {
          params.delete("evidence");
        }
        const query = params.toString();
        const nextUrl = query
          ? `${window.location.pathname}?${query}`
          : window.location.pathname;
        window.history.replaceState(null, "", nextUrl);
      } catch {
        // Ignore history API errors in restricted environments
      }
    }, 150);

    return () => {
      window.clearTimeout(timer);
    };
  }, [isHydrated, selectedEventIndex, showDiff, pinnedEvidenceId]);

  // Keyboard navigation for Time-Travel Scrubber: [ / ] / L
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) {
        return;
      }
      const target = e.target as HTMLElement | null;
      const tagName = target?.tagName?.toLowerCase();
      if (
        tagName === "input" ||
        tagName === "textarea" ||
        tagName === "select" ||
        target?.isContentEditable
      ) {
        return;
      }
      if (e.key === "[") {
        e.preventDefault();
        goToPreviousStep();
      } else if (e.key === "]") {
        e.preventDefault();
        goToNextStep();
      } else if (e.key === "l" || e.key === "L") {
        e.preventDefault();
        goToLiveHead();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [goToPreviousStep, goToNextStep, goToLiveHead]);

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
              type="button"
              onClick={() => setShowGenUI((prev) => !prev)}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 999,
                padding: "12px 20px",
                background: showGenUI ? "rgba(59,130,246,0.15)" : "transparent",
                color: showGenUI ? "var(--accent)" : "inherit",
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
              aria-pressed={showGenUI}
            >
              {showGenUI ? "⚡ GenUI Active" : "Generative UI View"}
            </button>
            <button
              type="button"
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

        {/* Time-Travel State Scrubber Bar */}
        <TimeTravelScrubber
          rawEvents={rawEvents}
          selectedEventIndex={selectedEventIndex}
          onSelectIndex={goToStep}
          onPrevious={goToPreviousStep}
          onNext={goToNextStep}
          onReturnToLive={goToLiveHead}
        />

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

        {showGenUI ? (
          <section className="shell-card" style={{ padding: 24 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <div>
                <h3 style={{ margin: 0, fontSize: 18 }}>Generative UI Artifact Stream</h3>
                <p style={{ margin: "4px 0 0 0", color: "var(--muted)", fontSize: 13 }}>
                  Interactive components rendering structured agent evidence, hypotheses, and reviewer actions.
                </p>
              </div>
              <span style={{ fontSize: 12, fontFamily: "monospace", color: "var(--accent)" }}>
                React 19 RSC · streamUI Spec
              </span>
            </div>

            {state.requiresApproval ? (
              <GenUIArtifactCard
                type="action"
                title="Human-in-the-Loop Review & Steering"
                onSubmitAction={async (decision, guidance) => {
                  const mappedDecision: ApprovalDecision =
                    decision === "request_revision"
                      ? "request_revision"
                      : decision === "approve"
                      ? "approve"
                      : "deny";
                  handleDecision(mappedDecision, guidance || "GenUI Steering Action", guidance);
                }}
              />
            ) : null}

            {state.hypotheses.map((h, idx) => (
              <GenUIArtifactCard
                key={`genui-hyp-${idx}`}
                type="hypothesis"
                title={`Hypothesis #${idx + 1}`}
                hypothesis={h}
              />
            ))}

            {state.evidence.map((ev) => (
              <GenUIArtifactCard
                key={`genui-evd-${ev.id}`}
                type="evidence"
                title={`${ev.category.toUpperCase()} - ${ev.id}`}
                evidence={ev}
                onSelectEvidence={setPinnedEvidenceId}
              />
            ))}
          </section>
        ) : null}

        {/* Primary Agent Reasoning & Hypotheses Panel with Iteration Diff Support */}
        <AgentReasoningPanel
          thoughtProcess={state.activeThoughtProcess}
          streamingReasoningDelta={state.streamingReasoningDelta}
          reasoningSteps={state.reasoningSteps}
          hypotheses={state.hypotheses}
          isLoading={state.status === "RUNNING"}
          highlightedEvidenceId={highlightedEvidenceId}
          pinnedEvidenceId={pinnedEvidenceId}
          onHighlightEvidence={setPinnedEvidenceId}
          onHoverEvidence={setHoveredEvidenceId}
          iterationSnapshots={iterationSnapshots}
          iterationDiffs={iterationDiffs}
          showDiff={showDiff}
          onToggleDiff={setShowDiff}
        />

        {/* Timeline and Evidence Panels with Cross-Panel Linking */}
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
            highlightedEvidenceId={highlightedEvidenceId}
            onSelectEvidence={setPinnedEvidenceId}
          />
        </div>

        {/* Risk and Analyzers with Cross-Panel Linking */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 20 }}>
          <RiskPanel risk={state.riskAssessment} />
          <AnalyzerPanel
            analyzers={state.analyzerSummaries}
            highlightedEvidenceId={highlightedEvidenceId}
            pinnedEvidenceId={pinnedEvidenceId}
            onHighlightEvidence={setPinnedEvidenceId}
            onHoverEvidence={setHoveredEvidenceId}
          />
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

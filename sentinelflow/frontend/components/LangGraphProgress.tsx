"use client";

import React, { memo, useEffect, useRef } from "react";

type StageKey = "intake" | "investigate" | "collect" | "synthesize" | "approval" | "finalize";

type StageConfig = {
  key: StageKey;
  label: string;
  sublabel: string;
};

const STAGES: StageConfig[] = [
  { key: "intake", label: "Intake", sublabel: "State init" },
  { key: "investigate", label: "Investigating", sublabel: "LLM reasoning" },
  { key: "collect", label: "Collect", sublabel: "Tools & analyzers" },
  { key: "synthesize", label: "Synthesize", sublabel: "Evidence synthesis" },
  { key: "approval", label: "Reviewer Audit", sublabel: "Human interrupt" },
  { key: "finalize", label: "Finalize", sublabel: "Audit & commit" },
];

type Props = {
  currentPhase?: StageKey;
  status: string;
  reviewerGuidance?: string | null;
  agentMessage?: string | null;
};

const fallbackMessage = (status: string) => {
  if (status === "APPROVAL_REQUIRED") {
    return "Awaiting reviewer approval";
  }
  if (status === "COMPLETED") {
    return "Investigation complete";
  }
  if (status === "FAILED") {
    return "Investigation failed";
  }
  if (status === "RUNNING") {
    return "Initializing investigation";
  }
  return "Ready to start";
};

const getAgentDotStyle = (status: string) => {
  if (status === "COMPLETED") {
    return {
      background: "var(--success, #22c55e)",
      boxShadow: "0 0 8px rgba(34, 197, 94, 0.6)",
    };
  }
  if (status === "RUNNING" || status === "APPROVAL_REQUIRED") {
    return {
      background: "var(--accent, #2563eb)",
      boxShadow: "0 0 8px rgba(37, 99, 235, 0.6)",
    };
  }
  if (status === "FAILED") {
    return {
      background: "var(--danger, #ef4444)",
      boxShadow: "0 0 8px rgba(239, 68, 68, 0.6)",
    };
  }
  return {
    background: "rgba(15, 23, 42, 0.2)",
    boxShadow: "none",
  };
};

export const LangGraphProgress = memo(
  ({ currentPhase = "intake", status, reviewerGuidance, agentMessage }: Props) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const stageRefs = useRef<Record<StageKey, HTMLDivElement | null>>({
      intake: null,
      investigate: null,
      collect: null,
      synthesize: null,
      approval: null,
      finalize: null,
    });

    useEffect(() => {
      const container = containerRef.current;
      const targetCard = stageRefs.current[currentPhase];
      if (container && targetCard) {
        const cardLeft = targetCard.offsetLeft;
        const cardWidth = targetCard.offsetWidth;
        const containerWidth = container.clientWidth;
        // Center the active card in the horizontal container viewport
        const scrollTarget = cardLeft - containerWidth / 2 + cardWidth / 2;
        container.scrollTo({
          left: Math.max(0, scrollTarget),
          behavior: "smooth",
        });
      }
    }, [currentPhase]);

    const stageOrder: Record<StageKey, number> = {
      intake: 0,
      investigate: 1,
      collect: 2,
      synthesize: 3,
      approval: 4,
      finalize: 5,
    };

    const currentIndex = stageOrder[currentPhase] ?? 0;
    const isCompleted = status === "COMPLETED";
    const isFailed = status === "FAILED";

    const getStageHeader = (): string => {
      if (isCompleted) {
        return "COMPLETED";
      }
      if (status === "APPROVAL_REQUIRED") {
        return "APPROVAL REQUIRED";
      }
      if (status === "RUNNING") {
        return currentPhase.toUpperCase();
      }
      if (isFailed) {
        return "FAILED";
      }
      return currentPhase.toUpperCase();
    };

    return (
      <div className="shell-card" style={{ padding: "20px 24px", minHeight: 224, boxSizing: "border-box" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
            marginBottom: 16,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <div>
              <p
                style={{
                  margin: 0,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--muted)",
                }}
              >
                LangGraph Execution Pipeline
              </p>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  marginTop: 6,
                  flexWrap: "wrap",
                }}
              >
                {/* Active Graph State */}
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    fontSize: 12,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                  }}
                >
                  <span style={{ color: "var(--muted)" }}>Active Graph State:</span>
                  <strong
                    style={{
                      color: isCompleted
                        ? "var(--success)"
                        : isFailed
                        ? "var(--danger)"
                        : "var(--accent)",
                      fontWeight: 700,
                    }}
                  >
                    {getStageHeader()}
                  </strong>
                </div>

                {/* Agent Activity responsive chip */}
                <div className="pipeline-agent-activity-chip">
                  <div className="pipeline-agent-activity-header">
                    <span
                      aria-hidden="true"
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        flexShrink: 0,
                        ...getAgentDotStyle(status),
                      }}
                    />
                    <span
                      style={{
                        color: "var(--muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        fontSize: 11,
                      }}
                    >
                      Agent activity:
                    </span>
                  </div>
                  <strong className="pipeline-agent-activity-message">
                    {agentMessage ?? fallbackMessage(status)}
                  </strong>
                </div>
              </div>
            </div>
          </div>
          {reviewerGuidance ? (
            <span
              style={{
                padding: "4px 10px",
                borderRadius: 999,
                fontSize: 11,
                background: "var(--accent-soft)",
                color: "var(--accent)",
                border: "1px solid var(--panel-border)",
                whiteSpace: "nowrap",
                fontWeight: 600,
              }}
            >
              ⟲ Human Steering Loop Active
            </span>
          ) : null}
        </div>

        <div
          ref={containerRef}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            overflowX: "auto",
            scrollBehavior: "smooth",
            scrollSnapType: "x mandatory",
            paddingBottom: 6,
            scrollbarWidth: "none",
          }}
        >
          {STAGES.map((stage, idx) => {
            const isCurrent = currentPhase === stage.key && !isCompleted;
            const isPast = idx < currentIndex || isCompleted;

            let badgeColor = "var(--panel-border)";
            let textColor = "var(--muted)";
            let dotBg = "rgba(255,255,255,0.1)";

            if (isFailed && isCurrent) {
              badgeColor = "var(--danger)";
              textColor = "var(--danger)";
              dotBg = "var(--danger)";
            } else if (isCurrent) {
              badgeColor = "var(--accent)";
              textColor = "var(--accent)";
              dotBg = "var(--accent)";
            } else if (isPast) {
              badgeColor = "var(--success)";
              textColor = "var(--foreground)";
              dotBg = "var(--success)";
            }

            return (
              <div
                key={stage.key}
                ref={(el) => {
                  stageRefs.current[stage.key] = el;
                }}
                tabIndex={isCurrent ? 0 : -1}
                aria-current={isCurrent ? "step" : undefined}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  alignItems: "flex-start",
                  padding: "10px 14px",
                  borderRadius: 10,
                  border: `1px solid ${badgeColor}`,
                  background: isCurrent ? "rgba(99,102,241,0.06)" : "transparent",
                  boxShadow: isCurrent
                    ? "0 0 0 1px var(--accent), 0 2px 8px rgba(37,99,235,0.15)"
                    : "none",
                  flex: 1,
                  minWidth: 120,
                  height: 72,
                  minHeight: 72,
                  maxHeight: 72,
                  boxSizing: "border-box",
                  scrollSnapAlign: "center",
                  transition:
                    "border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease",
                  transform: isCurrent ? "scale(1.02)" : "scale(1)",
                  outline: "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: dotBg,
                      display: "inline-block",
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ fontSize: 13, fontWeight: 600, color: textColor }}>
                    {stage.label}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 11,
                    color: "var(--muted)",
                    marginTop: 3,
                    whiteSpace: "nowrap",
                  }}
                >
                  {stage.sublabel}
                </span>
              </div>
            );
          })}
        </div>

      <div
        style={{
          marginTop: 14,
          minHeight: 40,
          display: "flex",
          alignItems: "center",
          padding: "10px 14px",
          borderRadius: 8,
          fontSize: 12,
          boxSizing: "border-box",
          background: reviewerGuidance
            ? "rgba(99, 102, 241, 0.06)"
            : "rgba(255, 255, 255, 0.02)",
          borderLeft: reviewerGuidance
            ? "3px solid var(--accent)"
            : "3px solid var(--panel-border)",
          transition: "background 0.15s ease, border-color 0.15s ease",
        }}
      >
        {reviewerGuidance ? (
          <div>
            <strong style={{ color: "var(--accent, #93c5fd)" }}>Reviewer Steering Guidance Applied: </strong>
            <span style={{ color: "var(--foreground)" }}>{reviewerGuidance}</span>
          </div>
        ) : (
          <span style={{ color: "var(--muted)" }}>
            No reviewer steering guidance applied · Autonomous execution baseline
          </span>
        )}
      </div>
    </div>
  );
});

LangGraphProgress.displayName = "LangGraphProgress";

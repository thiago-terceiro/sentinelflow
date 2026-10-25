"use client";

import { memo } from "react";
import type { StreamEvent } from "@/lib/types";

type Props = {
  rawEvents: StreamEvent[];
  selectedEventIndex: number | null;
  onSelectIndex: (index: number | null) => void;
  onPrevious: () => void;
  onNext: () => void;
  onReturnToLive: () => void;
};

const getEventBadgeColor = (type: StreamEvent["type"]): { bg: string; text: string } => {
  if (type === "evidence_added") {
    return { bg: "rgba(34,197,94,0.15)", text: "#22c55e" };
  }
  if (type === "tool_started" || type === "tool_completed") {
    return { bg: "rgba(56,189,248,0.15)", text: "#38bdf8" };
  }
  if (type === "analyzer_started" || type === "analyzer_completed") {
    return { bg: "rgba(168,85,247,0.15)", text: "#c084fc" };
  }
  if (type === "hypothesis_updated") {
    return { bg: "rgba(234,179,8,0.15)", text: "#eab308" };
  }
  if (type === "risk_updated") {
    return { bg: "rgba(249,115,22,0.15)", text: "#f97316" };
  }
  if (type === "approval_required" || type === "final_report_ready") {
    return { bg: "rgba(201,243,106,0.15)", text: "var(--accent)" };
  }
  if (type === "run_failed") {
    return { bg: "rgba(239,68,68,0.15)", text: "#ef4444" };
  }
  return { bg: "rgba(255,255,255,0.08)", text: "var(--muted)" };
};

export const TimeTravelScrubber = memo(
  ({
    rawEvents,
    selectedEventIndex,
    onSelectIndex,
    onPrevious,
    onNext,
    onReturnToLive,
  }: Props) => {
    if (rawEvents.length === 0) {
      return null;
    }

    const totalSteps = rawEvents.length;
    const isLive = selectedEventIndex === null;
    const currentStep = isLive ? totalSteps - 1 : selectedEventIndex;
    const activeEvent = rawEvents[currentStep] || rawEvents[rawEvents.length - 1];
    const badgeStyle = getEventBadgeColor(activeEvent.type);

    return (
      <section
        role="region"
        aria-label="Investigation time travel scrubber"
        className="shell-card"
        style={{
          padding: "16px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          border: isLive ? "1px solid var(--panel-border)" : "1px solid rgba(234,179,8,0.4)",
          background: isLive ? "rgba(255,255,255,0.01)" : "rgba(234,179,8,0.03)",
          transition: "border 0.2s, background 0.2s",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "-0.01em" }}>
              ⏱️ Time-Travel State Scrubber
            </span>
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 999,
                background: badgeStyle.bg,
                color: badgeStyle.text,
                fontWeight: 600,
                fontFamily: "monospace",
              }}
            >
              {activeEvent.type}
            </span>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              Step {currentStep + 1} of {totalSteps}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: "var(--muted)" }}>
              Keys: <kbd style={{ padding: "2px 5px", borderRadius: 4, background: "rgba(255,255,255,0.08)" }}>[</kbd> / <kbd style={{ padding: "2px 5px", borderRadius: 4, background: "rgba(255,255,255,0.08)" }}>]</kbd> scrub, <kbd style={{ padding: "2px 5px", borderRadius: 4, background: "rgba(255,255,255,0.08)" }}>L</kbd> live
            </span>
            {isLive ? (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--success)",
                  padding: "4px 10px",
                  borderRadius: 6,
                  background: "rgba(34,197,94,0.12)",
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: "50%",
                    background: "#22c55e",
                    boxShadow: "0 0 8px #22c55e",
                  }}
                />
                Live Head
              </span>
            ) : (
              <button
                type="button"
                onClick={onReturnToLive}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 12,
                  fontWeight: 700,
                  color: "#10231e",
                  background: "var(--accent)",
                  border: "none",
                  borderRadius: 6,
                  padding: "5px 12px",
                  cursor: "pointer",
                }}
              >
                ⏪ Return to Live (L)
              </button>
            )}
          </div>
        </div>

        {/* Range slider and stepper buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            type="button"
            onClick={onPrevious}
            disabled={currentStep <= 0}
            aria-label="Step backward in timeline"
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              background: "rgba(255,255,255,0.05)",
              border: "1px solid var(--panel-border)",
              color: currentStep <= 0 ? "var(--muted)" : "var(--foreground)",
              cursor: currentStep <= 0 ? "not-allowed" : "pointer",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            ◀ Prev
          </button>

          <input
            type="range"
            min={0}
            max={totalSteps - 1}
            value={currentStep}
            aria-label="Event step scrubber"
            onChange={(e) => {
              const val = Number(e.target.value);
              if (val >= totalSteps - 1) {
                onSelectIndex(null);
              } else {
                onSelectIndex(val);
              }
            }}
            style={{
              flex: 1,
              accentColor: isLive ? "var(--accent)" : "#eab308",
              cursor: "pointer",
            }}
          />

          <button
            type="button"
            onClick={onNext}
            disabled={isLive || currentStep >= totalSteps - 1}
            aria-label="Step forward in timeline"
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              background: "rgba(255,255,255,0.05)",
              border: "1px solid var(--panel-border)",
              color: isLive || currentStep >= totalSteps - 1 ? "var(--muted)" : "var(--foreground)",
              cursor: isLive || currentStep >= totalSteps - 1 ? "not-allowed" : "pointer",
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            Next ▶
          </button>
        </div>
      </section>
    );
  }
);

TimeTravelScrubber.displayName = "TimeTravelScrubber";

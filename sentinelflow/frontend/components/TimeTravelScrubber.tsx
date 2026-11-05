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
    const hasEvents = rawEvents.length > 0;
    const totalSteps = hasEvents ? rawEvents.length : 1;
    const isLive = selectedEventIndex === null;
    const currentStep = hasEvents ? (isLive ? totalSteps - 1 : selectedEventIndex) : 0;
    const activeEvent = hasEvents
      ? rawEvents[currentStep] || rawEvents[rawEvents.length - 1]
      : null;
    const badgeStyle = activeEvent
      ? getEventBadgeColor(activeEvent.type)
      : { bg: "rgba(255,255,255,0.06)", text: "var(--muted)" };
    const eventTypeLabel = activeEvent ? activeEvent.type : "standby";

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

            {/* Quick Prev / Next Stepper Arrows */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 2,
                background: "rgba(255, 255, 255, 0.04)",
                padding: "2px",
                borderRadius: 6,
                border: "1px solid var(--panel-border)",
              }}
            >
              <button
                type="button"
                onClick={onPrevious}
                disabled={!hasEvents || currentStep <= 0}
                aria-label="Step backward in timeline"
                title="Step backward ([)"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 24,
                  height: 22,
                  padding: 0,
                  borderRadius: 4,
                  background: !hasEvents || currentStep <= 0 ? "transparent" : "rgba(255, 255, 255, 0.06)",
                  border: 0,
                  color: !hasEvents || currentStep <= 0 ? "var(--muted)" : "var(--foreground)",
                  cursor: !hasEvents || currentStep <= 0 ? "not-allowed" : "pointer",
                  fontSize: 10,
                  lineHeight: 1,
                  opacity: !hasEvents || currentStep <= 0 ? 0.35 : 1,
                  transition: "none",
                }}
              >
                ◀
              </button>
              <button
                type="button"
                onClick={onNext}
                disabled={!hasEvents || isLive || currentStep >= totalSteps - 1}
                aria-label="Step forward in timeline"
                title="Step forward (])"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 24,
                  height: 22,
                  padding: 0,
                  borderRadius: 4,
                  background:
                    !hasEvents || isLive || currentStep >= totalSteps - 1
                      ? "transparent"
                      : "rgba(255, 255, 255, 0.06)",
                  border: 0,
                  color:
                    !hasEvents || isLive || currentStep >= totalSteps - 1
                      ? "var(--muted)"
                      : "var(--foreground)",
                  cursor:
                    !hasEvents || isLive || currentStep >= totalSteps - 1 ? "not-allowed" : "pointer",
                  fontSize: 10,
                  lineHeight: 1,
                  opacity: !hasEvents || isLive || currentStep >= totalSteps - 1 ? 0.35 : 1,
                  transition: "none",
                }}
              >
                ▶
              </button>
            </div>

            <span style={{ fontSize: 12, color: "var(--muted)" }}>
              {hasEvents ? `Step ${currentStep + 1} of ${totalSteps}` : "Standby (0 events)"}
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
              {eventTypeLabel}
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
                  justifyContent: "center",
                  gap: 6,
                  height: 28,
                  minWidth: 128,
                  padding: "0 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--success)",
                  background: "rgba(34,197,94,0.12)",
                  border: "1px solid rgba(34,197,94,0.25)",
                  boxSizing: "border-box",
                  whiteSpace: "nowrap",
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
                  justifyContent: "center",
                  gap: 6,
                  height: 28,
                  minWidth: 128,
                  padding: "0 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#1d4ed8",
                  background: "rgba(37,99,235,0.12)",
                  border: "1px solid rgba(37,99,235,0.25)",
                  cursor: "pointer",
                  boxSizing: "border-box",
                  whiteSpace: "nowrap",
                  transition: "none",
                  outline: "none",
                }}
              >
                Return to Live (L)
              </button>
            )}
          </div>
        </div>

        {/* Event step scrubber slider */}
        <div style={{ display: "flex", alignItems: "center", width: "100%" }}>
          <input
            type="range"
            min={0}
            max={Math.max(1, totalSteps - 1)}
            value={currentStep}
            disabled={!hasEvents}
            aria-label="Event step scrubber"
            onChange={(e) => {
              if (!hasEvents) return;
              const val = Number(e.target.value);
              if (val >= totalSteps - 1) {
                onSelectIndex(null);
              } else {
                onSelectIndex(val);
              }
            }}
            style={{
              width: "100%",
              accentColor: isLive ? "var(--accent)" : "#eab308",
              cursor: hasEvents ? "pointer" : "not-allowed",
              opacity: hasEvents ? 1 : 0.5,
            }}
          />
        </div>
      </section>
    );
  }
);

TimeTravelScrubber.displayName = "TimeTravelScrubber";

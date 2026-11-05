"use client";

import Link from "next/link";
import React, { memo, useEffect, useState } from "react";
import { useSentinelPulse } from "@/components/SentinelPulseProvider";
import type { TelecomFeedItem, TelecomVerdict } from "./types";

type Props = {
  initialFeed?: TelecomFeedItem[];
  onConnectionChange?: (connected: boolean) => void;
};

const getVerdictBadgeStyle = (verdict: TelecomVerdict) => {
  if (verdict === "BLOCK") {
    return {
      bg: "rgba(239, 68, 68, 0.12)",
      color: "#dc2626",
      border: "1px solid rgba(239, 68, 68, 0.25)",
    };
  }
  if (verdict === "FLAG") {
    return {
      bg: "rgba(234, 179, 8, 0.15)",
      color: "#b45309",
      border: "1px solid rgba(234, 179, 8, 0.3)",
    };
  }
  return {
    bg: "rgba(34, 197, 94, 0.12)",
    color: "#16a34a",
    border: "1px solid rgba(34, 197, 94, 0.25)",
  };
};

export const TelecomLiveFeed = memo(({ initialFeed = [] }: Props) => {
  const {
    liveFeed: ctxLiveFeed,
    isPaused,
    setIsPaused,
    isResetting,
    resetGateway,
  } = useSentinelPulse();

  const liveFeed = ctxLiveFeed.length > 0 ? ctxLiveFeed : initialFeed;
  const [filterVerdict, setFilterVerdict] = useState<string>("ALL");
  const [escalatingIds, setEscalatingIds] = useState<Record<string, boolean>>({});
  const [escalatedDisputes, setEscalatedDisputes] = useState<
    Record<string, { id: string; case_code?: string; url: string }>
  >({});

  // Handle incoming query params and hash from the disputes page
  useEffect(() => {
    try {
      const search = window.location.search;
      const params = new URLSearchParams(search);
      const filter = params.get("filter");
      if (filter && ["ALL", "BLOCK", "FLAG", "ALLOW", "ESCALATED"].includes(filter.toUpperCase())) {
        setFilterVerdict(filter.toUpperCase());
      }
      if (window.location.hash === "#inspection-feed" || filter === "ESCALATED") {
        setTimeout(() => {
          const el = document.getElementById("inspection-feed");
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }, 150);
      }
    } catch {
      // In SSR or non-browser environments
    }
  }, []);

  const handleEscalate = async (item: TelecomFeedItem) => {
    const itemKey = item.id || `${item.sender}-${item.timestamp}`;
    setEscalatingIds((prev) => ({ ...prev, [itemKey]: true }));
    try {
      const res = await fetch("/app-api/telecom/escalate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: item.sender,
          recipient: item.recipient,
          message: item.message,
          carrier: item.carrier,
          verdict: item.verdict,
          fraud_score: item.fraud_score,
          signals: item.signals,
          velocity: item.velocity || {},
          event_id: item.id,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as {
          dispute_id: string;
          case_code: string;
          dispute_url: string;
        };
        setEscalatedDisputes((prev) => ({
          ...prev,
          [itemKey]: {
            id: data.dispute_id,
            case_code: data.case_code,
            url: data.dispute_url,
          },
        }));
      }
    } catch (err) {
      console.error("Escalation failed", err);
    } finally {
      setEscalatingIds((prev) => ({ ...prev, [itemKey]: false }));
    }
  };

  const filteredFeed = liveFeed.filter((item) => {
    if (filterVerdict === "ALL") {
      return true;
    }
    if (filterVerdict === "ESCALATED") {
      const itemKey = item.id || `${item.sender}-${item.timestamp}`;
      return Boolean(escalatedDisputes[itemKey] || item.escalated_dispute_id);
    }
    return item.verdict === filterVerdict;
  });

  return (
    <div
      className="shell-card"
      style={{
        padding: 24,
        display: "flex",
        flexDirection: "column",
        minHeight: 640,
      }}
    >
      {/* Feed Control Bar */}
      <div
        id="inspection-feed"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 10,
          marginBottom: 14,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <h2 style={{ margin: "0 0 4px", fontSize: 20, letterSpacing: "-0.02em" }}>
            <span className="page-icon">🛰️ </span>Real-Time Inspection Feed
          </h2>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            Live incoming telecom messages ({filteredFeed.length} buffered)
          </span>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {/* Reset / Clear feed button */}
          <button
            type="button"
            disabled={isResetting}
            onClick={() => {
              void resetGateway();
            }}
            title="Reset gateway telemetry and clear buffered messages"
            aria-label="Clear all buffered messages"
            style={{
              fontSize: 11,
              padding: "4px 10px",
              borderRadius: "var(--card-radius, 6px)",
              border: "1px solid var(--panel-border)",
              background: "transparent",
              color: "var(--muted)",
              cursor: isResetting ? "wait" : "pointer",
              fontWeight: 600,
            }}
          >
            <span className="page-icon">🗑️ </span>
            {isResetting ? "Resetting..." : "Reset"}
          </button>

          <button
            type="button"
            aria-pressed={isPaused}
            onClick={() => setIsPaused((prev) => !prev)}
            style={{
              fontSize: 11,
              padding: "4px 10px",
              borderRadius: "var(--card-radius, 6px)",
              border: "1px solid var(--panel-border)",
              background: isPaused ? "#ef4444" : "transparent",
              color: isPaused ? "#fff" : "var(--foreground)",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            {isPaused ? (
              <>
                <span className="page-icon">▶ </span>Resume
              </>
            ) : (
              <>
                <span className="page-icon">⏸ </span>Pause
              </>
            )}
          </button>
        </div>
      </div>

      {/* Filter Pills with WCAG accessible tabs & focus rings */}
      <div
        role="tablist"
        aria-label="Filter events by verdict"
        style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}
      >
        {["ALL", "BLOCK", "FLAG", "ALLOW", "ESCALATED"].map((f) => {
          const isSelected = filterVerdict === f;
          return (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={isSelected}
              onClick={() => setFilterVerdict(f)}
              style={{
                fontSize: 11,
                padding: "3px 8px",
                borderRadius: 4,
                border: isSelected ? "1px solid var(--accent)" : "1px solid var(--panel-border)",
                background: isSelected ? "var(--accent-soft, rgba(37, 99, 235, 0.1))" : "transparent",
                color: isSelected ? "var(--accent)" : "var(--muted)",
                cursor: "pointer",
                fontWeight: 600,
              }}
              className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            >
              {f}
            </button>
          );
        })}
      </div>

      {/* Scrollable Event Feed Container with ARIA live log */}
      <div
        role="log"
        aria-live="polite"
        aria-atomic="false"
        style={{
          flex: 1,
          maxHeight: 520,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 8,
          paddingRight: 4,
        }}
      >
        {filteredFeed.length === 0 ? (
          <div
            style={{
              padding: "40px 20px",
              textAlign: "center",
              color: "var(--muted)",
              fontSize: 13,
            }}
          >
            Waiting for incoming telecom events...
            <br />
            <span style={{ fontSize: 12 }}>
              Run the traffic simulator or test above to see events flow live!
            </span>
          </div>
        ) : (
          filteredFeed.map((ev) => {
            const itemKey = ev.id || `${ev.sender}-${ev.timestamp}`;
            const escalated =
              escalatedDisputes[itemKey] ||
              (ev.escalated_dispute_id
                ? {
                    id: ev.escalated_dispute_id,
                    url: ev.escalated_dispute_url || `/disputes/${ev.escalated_dispute_id}`,
                  }
                : undefined);
            const isEscalatingThis = Boolean(escalatingIds[itemKey]);
            const badgeStyle = getVerdictBadgeStyle(ev.verdict);

            return (
              <div
                key={itemKey}
                style={{
                  padding: "12px 14px",
                  borderRadius: "var(--card-radius, 8px)",
                  background: "var(--panel, #ffffff)",
                  border: "1px solid var(--panel-border)",
                  fontSize: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 6,
                    marginBottom: 6,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 800,
                        padding: "2px 6px",
                        borderRadius: 4,
                        background: badgeStyle.bg,
                        color: badgeStyle.color,
                        border: badgeStyle.border,
                      }}
                    >
                      {ev.verdict}
                    </span>
                    <span style={{ fontFamily: "monospace", color: "var(--foreground)" }}>
                      {ev.sender}
                    </span>
                    <span style={{ color: "var(--muted)", fontSize: 11 }}>({ev.carrier})</span>
                  </div>

                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span style={{ color: "var(--muted)", fontSize: 11 }}>
                      score: {ev.fraud_score}
                    </span>
                    <span style={{ color: "#22c55e", fontFamily: "monospace", fontSize: 11 }}>
                      {ev.latency_ms}ms
                    </span>
                  </div>
                </div>

                <p
                  style={{
                    margin: "0 0 6px",
                    color: "var(--foreground)",
                    fontSize: 13,
                    lineHeight: 1.35,
                    overflowWrap: "anywhere",
                  }}
                >
                  {ev.message}
                </p>

                {ev.signals && ev.signals.length > 0 ? (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {ev.signals.map((sig) => (
                      <span
                        key={sig}
                        style={{
                          fontSize: 10,
                          padding: "1px 5px",
                          borderRadius: 3,
                          background: "var(--panel-border, rgba(15, 23, 42, 0.08))",
                          color: sig.startsWith("RULE:") ? "#ef4444" : "var(--muted)",
                        }}
                      >
                        {sig}
                      </span>
                    ))}
                  </div>
                ) : null}

                {/* Two-Tier Escalation Action for Feed Card */}
                {ev.verdict === "FLAG" || ev.verdict === "BLOCK" ? (
                  <div
                    style={{
                      marginTop: 10,
                      paddingTop: 8,
                      borderTop: "1px solid var(--panel-border)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: 8,
                    }}
                  >
                    <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 500 }}>
                      Stage 2 Escalation:
                    </span>
                    {escalated ? (
                      <Link
                        href={escalated.url}
                        prefetch={true}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          fontSize: 12,
                          fontWeight: 700,
                          padding: "6px 14px",
                          borderRadius: "var(--card-radius, 4px)",
                          background: "var(--accent)",
                          color: "var(--accent-ink, #ffffff)",
                          textDecoration: "none",
                          boxShadow: "0 0 10px rgba(201, 243, 106, 0.3)",
                        }}
                      >
                        <span>→ Investigate in SentinelFlow {escalated.case_code ? `(${escalated.case_code})` : ""}</span>
                      </Link>
                    ) : (
                      <button
                        type="button"
                        disabled={isEscalatingThis}
                        onClick={() => {
                          void handleEscalate(ev);
                        }}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          fontSize: 12,
                          padding: "6px 14px",
                          borderRadius: "var(--card-radius, 4px)",
                          background: "var(--accent-soft, rgba(37, 99, 235, 0.12))",
                          color: "var(--accent, #2563eb)",
                          border: "1px solid var(--accent, rgba(37, 99, 235, 0.35))",
                          cursor: isEscalatingThis ? "wait" : "pointer",
                          fontWeight: 700,
                          transition: "all 0.15s ease",
                        }}
                      >
                        {isEscalatingThis ? (
                          "Escalating..."
                        ) : (
                          <>
                            <span>⚡</span>
                            <span>Escalate to SentinelFlow</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
});

TelecomLiveFeed.displayName = "TelecomLiveFeed";

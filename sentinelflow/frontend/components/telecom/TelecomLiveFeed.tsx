"use client";

import React, { memo, useEffect, useRef, useState } from "react";
import type { TelecomFeedItem, TelecomVerdict } from "./types";

type Props = {
  initialFeed?: TelecomFeedItem[];
  onConnectionChange?: (connected: boolean) => void;
};

const getVerdictColor = (verdict: TelecomVerdict): string => {
  if (verdict === "BLOCK") {
    return "#ef4444";
  }
  if (verdict === "FLAG") {
    return "#eab308";
  }
  return "#22c55e";
};

export const TelecomLiveFeed = memo(({ initialFeed = [], onConnectionChange }: Props) => {
  const [liveFeed, setLiveFeed] = useState<TelecomFeedItem[]>(initialFeed);
  const [filterVerdict, setFilterVerdict] = useState<string>("ALL");
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const isPausedRef = useRef<boolean>(isPaused);
  isPausedRef.current = isPaused;

  const [escalatingIds, setEscalatingIds] = useState<Record<string, boolean>>({});
  const [escalatedDisputes, setEscalatedDisputes] = useState<
    Record<string, { id: string; case_code?: string; url: string }>
  >({});

  // Sync initial feed when provided and liveFeed is empty
  useEffect(() => {
    if (initialFeed.length > 0) {
      setLiveFeed((prev) => (prev.length === 0 ? initialFeed : prev));
    }
  }, [initialFeed]);

  // Establish SSE stream once on mount - NEVER reconnect on pause/resume
  useEffect(() => {
    let es: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connectSSE = () => {
      try {
        es = new EventSource("/app-api/telecom/stream");

        es.onopen = () => {
          if (onConnectionChange) {
            onConnectionChange(true);
          }
        };

        es.addEventListener("message", (event) => {
          try {
            const parsed = JSON.parse(event.data) as TelecomFeedItem;
            if (!isPausedRef.current) {
              setLiveFeed((prev) => [parsed, ...prev.slice(0, 49)]);
            }
          } catch (e) {
            console.debug("Failed to parse SSE event", e);
          }
        });

        es.onerror = () => {
          if (onConnectionChange) {
            onConnectionChange(false);
          }
          if (es) {
            es.close();
          }
          reconnectTimeout = setTimeout(connectSSE, 4000);
        };
      } catch (err) {
        console.warn("Error setting up EventSource", err);
        if (onConnectionChange) {
          onConnectionChange(false);
        }
      }
    };

    connectSSE();

    return () => {
      if (es) {
        es.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [onConnectionChange]);

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
      const key = item.id || `${item.sender}-${item.timestamp}`;
      return Boolean(escalatedDisputes[key] || item.escalated_dispute_id);
    }
    return item.verdict === filterVerdict;
  });

  return (
    <div
      className="shell-card"
      style={{ padding: "24px 26px", display: "flex", flexDirection: "column" }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 14,
        }}
      >
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 20, letterSpacing: "-0.02em" }}>
            <span className="page-icon">🛰️ </span>Real-Time Inspection Feed
          </h2>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            Live incoming telecom messages ({filteredFeed.length} buffered)
          </span>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            type="button"
            aria-pressed={isPaused}
            onClick={() => setIsPaused((prev) => !prev)}
            style={{
              fontSize: 11,
              padding: "4px 8px",
              borderRadius: "var(--card-radius, 6px)",
              border: "1px solid var(--border)",
              background: isPaused ? "#ef4444" : "rgba(255,255,255,0.06)",
              color: isPaused ? "#fff" : "var(--foreground)",
              cursor: "pointer",
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
        style={{ display: "flex", gap: 6, marginBottom: 12 }}
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
                border: isSelected ? "1px solid var(--accent)" : "1px solid var(--border)",
                background: isSelected ? "rgba(201,243,106,0.12)" : "transparent",
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

            return (
              <div
                key={itemKey}
                style={{
                  padding: "12px 14px",
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.18)",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 6,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 800,
                        padding: "2px 6px",
                        borderRadius: 4,
                        background: getVerdictColor(ev.verdict),
                        color: "#10231e",
                      }}
                    >
                      {ev.verdict}
                    </span>
                    <span style={{ fontFamily: "monospace", color: "var(--foreground)" }}>
                      {ev.sender}
                    </span>
                    <span style={{ color: "var(--muted)", fontSize: 11 }}>({ev.carrier})</span>
                  </div>

                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
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
                          background: "rgba(255,255,255,0.06)",
                          color: sig.startsWith("RULE:") ? "#f87171" : "var(--muted)",
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
                      marginTop: 8,
                      paddingTop: 6,
                      borderTop: "1px solid rgba(255,255,255,0.06)",
                      display: "flex",
                      justifyContent: "flex-end",
                    }}
                  >
                    {escalated ? (
                      <a
                        href={escalated.url}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          fontSize: 11,
                          color: "var(--accent)",
                          textDecoration: "none",
                          fontWeight: 700,
                        }}
                      >
                        <span className="page-icon">🔍 </span>View Case in SentinelFlow{" "}
                        {escalated.case_code ? `(${escalated.case_code})` : ""} →
                      </a>
                    ) : (
                      <button
                        type="button"
                        disabled={isEscalatingThis}
                        onClick={() => {
                          void handleEscalate(ev);
                        }}
                        style={{
                          fontSize: 11,
                          padding: "3px 8px",
                          borderRadius: 4,
                          background: "rgba(201, 243, 106, 0.12)",
                          color: "var(--accent)",
                          border: "1px solid rgba(201, 243, 106, 0.3)",
                          cursor: isEscalatingThis ? "wait" : "pointer",
                          fontWeight: 600,
                        }}
                      >
                        {isEscalatingThis ? (
                          "Escalating..."
                        ) : (
                          <>
                            <span className="page-icon">⚡ </span>Escalate to SentinelFlow
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

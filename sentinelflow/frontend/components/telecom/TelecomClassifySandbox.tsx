"use client";

import Link from "next/link";
import React, { memo, useId, useRef, useState } from "react";

import { useSentinelPulse } from "@/components/SentinelPulseProvider";
import { invalidateDisputesCache } from "@/lib/disputesCache";
import type { TelecomFeedItem, TelecomPreset, TelecomVerdict } from "./types";

type Props = {
  presets: TelecomPreset[];
  onClassificationSuccess?: () => void;
};

const getVerdictBadgeStyle = (verdict: TelecomVerdict) => {
  if (verdict === "BLOCK") {
    return {
      bg: "var(--badge-block-bg, #fee2e2)",
      color: "var(--badge-block-color, #7f1d1d)",
      border: "1px solid var(--badge-block-border, #991b1b)",
    };
  }
  if (verdict === "FLAG") {
    return {
      bg: "var(--badge-flag-bg, #fef3c7)",
      color: "var(--badge-flag-color, #78350f)",
      border: "1px solid var(--badge-flag-border, #b45309)",
    };
  }
  return {
    bg: "var(--badge-allow-bg, #dcfce7)",
    color: "var(--badge-allow-color, #14532d)",
    border: "1px solid var(--badge-allow-border, #15803d)",
  };
};

export const TelecomClassifySandbox = memo(({ presets, onClassificationSuccess }: Props) => {
  const formId = useId();
  const { hasSession } = useSentinelPulse();

  const [testSender, setTestSender] = useState<string>("+14155552671");
  const [testRecipient, setTestRecipient] = useState<string>("+14155559876");
  const [testCarrier, setTestCarrier] = useState<string>("Verizon Wireless");
  const [testMessage, setTestMessage] = useState<string>(
    "Carrier security code: 492018. Valid for 5 minutes. Do not share this code."
  );
  const [isClassifying, setIsClassifying] = useState<boolean>(false);
  const isClassifyingRef = useRef<boolean>(false);
  const [classificationError, setClassificationError] = useState<string | null>(null);
  const [classificationResult, setClassificationResult] = useState<TelecomFeedItem | null>(null);
  const [autoEscalate, setAutoEscalate] = useState<boolean>(false);
  const [isEscalating, setIsEscalating] = useState<boolean>(false);
  const [escalatedDispute, setEscalatedDispute] = useState<{
    id: string;
    case_code?: string;
    url: string;
  } | null>(null);
  const [selectedPresetName, setSelectedPresetName] = useState<string | null>(
    presets[0]?.name ?? null
  );

  const applyPreset = (preset: TelecomPreset) => {
    setSelectedPresetName(preset.name);
    setTestSender(preset.sender);
    setTestCarrier(preset.carrier);
    setTestMessage(preset.message);
    setClassificationResult(null);
    setEscalatedDispute(null);
  };

  const handleClassify = async (e?: React.FormEvent) => {
    if (e) {
      e.preventDefault();
    }
    if (isClassifyingRef.current) {
      return;
    }
    isClassifyingRef.current = true;
    setIsClassifying(true);
    setClassificationError(null);
    try {
      const res = await fetch("/app-api/telecom/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: testSender,
          recipient: testRecipient,
          message: testMessage,
          carrier: testCarrier,
          escalate: autoEscalate,
        }),
      });

      if (res.ok) {
        const data = (await res.json()) as TelecomFeedItem;
        setClassificationResult(data);
        if (data.escalated_dispute_id) {
          setEscalatedDispute({
            id: data.escalated_dispute_id,
            url: data.escalated_dispute_url || `/disputes/${data.escalated_dispute_id}`,
          });
        } else {
          setEscalatedDispute(null);
        }
        if (onClassificationSuccess) {
          onClassificationSuccess();
        }
      } else {
        setClassificationError(`Classification failed with HTTP ${res.status}.`);
      }
    } catch (err) {
      setClassificationError(
        err instanceof Error ? err.message : "Classification request failed."
      );
    } finally {
      isClassifyingRef.current = false;
      setIsClassifying(false);
    }
  };

  const handleEscalateResult = async () => {
    if (!classificationResult) {
      return;
    }
    if (!hasSession) {
      if (typeof window !== "undefined") {
        window.location.href = `/login?returnTo=${encodeURIComponent(window.location.pathname + window.location.search)}`;
      }
      return;
    }
    setIsEscalating(true);
    try {
      const res = await fetch("/app-api/telecom/escalate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: classificationResult.sender,
          recipient: classificationResult.recipient,
          message: classificationResult.message,
          carrier: classificationResult.carrier,
          verdict: classificationResult.verdict,
          fraud_score: classificationResult.fraud_score,
          signals: classificationResult.signals,
          velocity: classificationResult.velocity || {},
          event_id: classificationResult.id,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as {
          dispute_id: string;
          case_code: string;
          dispute_url: string;
        };
        setEscalatedDispute({
          id: data.dispute_id,
          case_code: data.case_code,
          url: `${data.dispute_url}?from=pulse`,
        });
        invalidateDisputesCache();
      }
    } catch (err) {
      console.error("Manual escalation failed", err);
    } finally {
      setIsEscalating(false);
    }
  };

  return (
    <div className="shell-card" style={{ padding: "24px 26px" }}>
      <h2 style={{ margin: "0 0 6px", fontSize: 20, letterSpacing: "-0.02em" }}>
        <span className="page-icon">🧪 </span>Interactive SMS Gateway Tester
      </h2>
      <p style={{ margin: "0 0 16px", color: "var(--muted)", fontSize: 13 }}>
        Submit arbitrary SMS payloads to inspect the live decision path, model probability, rule
        signals, and sliding-window velocity calculations.
      </p>

      {/* Presets */}
      <div style={{ marginBottom: 16 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 8,
          }}
        >
          <span
            style={{
              fontSize: 11,
              color: "var(--muted)",
              fontWeight: 700,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}
          >
            Quick Test Presets
          </span>
          <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600 }}>
            Select scenario
          </span>
        </div>
        <div
          role="group"
          aria-label="Quick test preset scenarios"
          style={{ display: "flex", gap: 8, flexWrap: "wrap" }}
        >
          {presets.map((p) => {
            const isSelected =
              selectedPresetName === p.name ||
              (selectedPresetName === null &&
                p.sender === testSender &&
                p.carrier === testCarrier &&
                p.message === testMessage);
            return (
              <button
                key={p.name}
                type="button"
                aria-pressed={isSelected}
                aria-label={`Load preset scenario: ${p.name}`}
                onClick={() => applyPreset(p)}
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  minHeight: 44,
                  padding: "10px 16px",
                  borderRadius: 6,
                  border: isSelected ? "2px solid var(--accent, #1e40af)" : "1px solid var(--panel-border)",
                  background: isSelected ? "var(--accent-soft, #dbeafe)" : "transparent",
                  color: isSelected ? "var(--accent, #1e3a8a)" : "var(--foreground)",
                  cursor: "pointer",
                }}
                className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
              >
                {p.name}
              </button>
            );
          })}
        </div>
      </div>

      {classificationError ? (
        <div
          role="alert"
          style={{
            marginBottom: 14,
            padding: "10px 14px",
            borderRadius: 8,
            background: "var(--badge-block-bg, #fee2e2)",
            border: "1px solid var(--badge-block-border, #991b1b)",
            color: "var(--badge-block-color, #7f1d1d)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {classificationError}
        </div>
      ) : null}

      <form onSubmit={handleClassify}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 12,
            marginBottom: 12,
          }}
        >
          <div>
            <label
              htmlFor={`${formId}-sender`}
              style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
            >
              Sender Phone (E.164)
            </label>
            <input
              id={`${formId}-sender`}
              type="text"
              value={testSender}
              onChange={(e) => {
                setTestSender(e.target.value);
                setSelectedPresetName(null);
              }}
              style={{
                width: "100%",
                minHeight: 44,
                padding: "10px 12px",
                borderRadius: 8,
                background: "rgba(0,0,0,0.2)",
                border: "1px solid var(--border)",
                color: "var(--foreground)",
                fontSize: 13,
                fontFamily: "monospace",
              }}
            />
          </div>

          <div>
            <label
              htmlFor={`${formId}-carrier`}
              style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
            >
              Originating Carrier
            </label>
            <input
              id={`${formId}-carrier`}
              type="text"
              value={testCarrier}
              onChange={(e) => {
                setTestCarrier(e.target.value);
                setSelectedPresetName(null);
              }}
              style={{
                width: "100%",
                minHeight: 44,
                padding: "10px 12px",
                borderRadius: 8,
                background: "rgba(0,0,0,0.2)",
                border: "1px solid var(--border)",
                color: "var(--foreground)",
                fontSize: 13,
              }}
            />
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <label
            htmlFor={`${formId}-recipient`}
            style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
          >
            Recipient Phone (E.164)
          </label>
          <input
            id={`${formId}-recipient`}
            type="text"
            value={testRecipient}
            onChange={(e) => setTestRecipient(e.target.value)}
            style={{
              width: "100%",
              minHeight: 44,
              padding: "10px 12px",
              borderRadius: 8,
              background: "rgba(0,0,0,0.2)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              fontSize: 13,
              fontFamily: "monospace",
            }}
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label
            htmlFor={`${formId}-message`}
            style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
          >
            SMS Message Body
          </label>
          <textarea
            id={`${formId}-message`}
            rows={3}
            value={testMessage}
            onChange={(e) => {
              setTestMessage(e.target.value);
              setSelectedPresetName(null);
            }}
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: 8,
              background: "rgba(0,0,0,0.2)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              fontSize: 13,
              resize: "vertical",
            }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, minHeight: 44 }}>
          <input
            id={`${formId}-auto-escalate`}
            type="checkbox"
            checked={autoEscalate}
            onChange={(e) => setAutoEscalate(e.target.checked)}
            style={{ accentColor: "var(--accent)", cursor: "pointer", width: 20, height: 20, minWidth: 44, minHeight: 44 }}
          />
          <label
            htmlFor={`${formId}-auto-escalate`}
            style={{ fontSize: 12, color: "var(--foreground)", cursor: "pointer" }}
          >
            <span className="page-icon">⚡ </span>Auto-escalate FLAG / BLOCK anomalies to
            SentinelFlow Investigation
          </label>
        </div>

        <button
          type="submit"
          disabled={isClassifying}
          style={{
            width: "100%",
            minHeight: 48,
            padding: "12px 20px",
            borderRadius: "var(--card-radius, 8px)",
            background: "var(--accent, #1e3a8a)",
            color: "var(--accent-ink, #ffffff)",
            fontWeight: 700,
            fontSize: 15,
            border: "none",
            cursor: isClassifying ? "wait" : "pointer",
          }}
          className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          {isClassifying ? (
            "Classifying..."
          ) : (
            <>
              <span className="page-icon">⚡ </span>Run Real-Time Classification (&lt;15ms)
            </>
          )}
        </button>
      </form>

      {/* Test Decision Output */}
      {classificationResult ? (
        <div
          style={{
            marginTop: 20,
            padding: "18px 20px",
            borderRadius: "var(--card-radius, 8px)",
            background: "var(--panel, #ffffff)",
            border: "1px solid var(--panel-border)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 800,
                  background: getVerdictBadgeStyle(classificationResult.verdict).bg,
                  color: getVerdictBadgeStyle(classificationResult.verdict).color,
                  border: getVerdictBadgeStyle(classificationResult.verdict).border,
                }}
              >
                {classificationResult.verdict}
              </span>
              <span style={{ fontSize: 13, color: "var(--muted)" }}>
                Fraud Score:{" "}
                <strong style={{ color: "var(--foreground)" }}>
                  {classificationResult.fraud_score}
                </strong>
              </span>
            </div>

            <span style={{ fontSize: 13, fontFamily: "monospace", color: "var(--telecom-good, #14532d)", fontWeight: 700 }}>
              <span className="page-icon">⏱ </span>
              {classificationResult.latency_ms} ms
            </span>
          </div>

          {classificationResult.signals && classificationResult.signals.length > 0 ? (
            <div style={{ marginBottom: 10 }}>
              <span
                style={{
                  fontSize: 11,
                  color: "var(--muted)",
                  display: "block",
                  marginBottom: 4,
                  fontWeight: 700,
                }}
              >
                TRIGGERED SIGNALS:
              </span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {classificationResult.signals.map((sig) => (
                  <span
                    key={sig}
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: "3px 8px",
                      borderRadius: 4,
                      background: sig.startsWith("RULE:") ? "var(--badge-block-bg, #fee2e2)" : "var(--accent-soft, #dbeafe)",
                      color: sig.startsWith("RULE:") ? "var(--badge-block-color, #991b1b)" : "var(--accent, #1e3a8a)",
                      border: sig.startsWith("RULE:") ? "1px solid var(--badge-block-border, #b91c1c)" : "1px solid var(--panel-border, #93c5fd)",
                    }}
                  >
                    {sig}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          {classificationResult.velocity ? (
            <div
              style={{
                fontSize: 12,
                color: "var(--muted)",
                paddingTop: 8,
                borderTop: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              <span>Velocity: </span>
              <strong style={{ color: "var(--foreground)" }}>
                {classificationResult.velocity.velocity_10s} msgs/10s
              </strong>{" "}
              · <span>{classificationResult.velocity.velocity_60s} msgs/60s</span> ·{" "}
              <span>Carrier: {classificationResult.carrier}</span>
            </div>
          ) : null}

          {/* Two-Tier Escalation Action */}
          {classificationResult.verdict === "FLAG" || classificationResult.verdict === "BLOCK" ? (
            <div
              style={{
                marginTop: 14,
                padding: "16px 18px",
                borderRadius: "var(--card-radius, 8px)",
                background:
                  "linear-gradient(135deg, rgba(201, 243, 106, 0.08) 0%, rgba(37, 99, 235, 0.08) 100%)",
                border: "1px solid var(--accent, rgba(201, 243, 106, 0.35))",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <div>
                <strong style={{ fontSize: 13, color: "var(--foreground)", display: "block" }}>
                  ⚡ Two-Tier Anomaly Escalation
                </strong>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>
                  Synchronous inline ingress (&lt;15ms SLA) flagged this anomaly ({classificationResult.verdict}). Escalate to Stage 2 for autonomous multi-agent dispute investigation.
                </span>
              </div>

              {escalatedDispute ? (
                <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <Link
                    href={escalatedDispute.url}
                    prefetch={true}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 13,
                      fontWeight: 700,
                      minHeight: 44,
                      padding: "12px 20px",
                      borderRadius: "var(--card-radius, 6px)",
                      background: "var(--accent, #1e3a8a)",
                      color: "var(--accent-ink, #ffffff)",
                      textDecoration: "none",
                      boxShadow: "0 0 16px rgba(30, 58, 138, 0.35)",
                    }}
                    className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                  >
                    <span>→ Investigate in SentinelFlow {escalatedDispute.case_code ? `(${escalatedDispute.case_code})` : ""}</span>
                  </Link>
                  <span style={{ fontSize: 12, color: "var(--muted)" }}>
                    Dispute record created. Ready for LangGraph investigation.
                  </span>
                </div>
              ) : (
                <div>
                  <button
                    type="button"
                    disabled={isEscalating}
                    aria-label={
                      !hasSession
                        ? "Escalate to SentinelFlow (Sign In): authenticate to investigate flagged anomaly"
                        : "Escalate to SentinelFlow: investigate flagged anomaly"
                    }
                    onClick={() => {
                      void handleEscalateResult();
                    }}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      fontSize: 13,
                      minHeight: 44,
                      padding: "12px 20px",
                      borderRadius: "var(--card-radius, 6px)",
                      background: "var(--accent-soft, #dbeafe)",
                      color: "var(--accent, #1e3a8a)",
                      border: "2px solid var(--accent, #1e40af)",
                      cursor: isEscalating ? "wait" : "pointer",
                      fontWeight: 700,
                      transition: "all 0.15s ease",
                    }}
                    className="focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                  >
                    {isEscalating ? (
                      "Escalating to SentinelFlow..."
                    ) : (
                      <>
                        <span>⚡</span>
                        <span>Escalate to SentinelFlow {!hasSession ? "(Sign In)" : ""}</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
});

TelecomClassifySandbox.displayName = "TelecomClassifySandbox";

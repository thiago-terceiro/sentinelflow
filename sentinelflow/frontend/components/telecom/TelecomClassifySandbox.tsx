"use client";

import React, { memo, useEffect, useId, useState } from "react";
import type { TelecomFeedItem, TelecomPreset, TelecomVerdict } from "./types";

type Props = {
  presets: TelecomPreset[];
  onClassificationSuccess?: () => void;
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

export const TelecomClassifySandbox = memo(({ presets, onClassificationSuccess }: Props) => {
  const formId = useId();

  const [hasSession, setHasSession] = useState<boolean>(false);

  useEffect(() => {
    try {
      const hasToken = Boolean(
        document.cookie.match(/(?:^|;\s*)sentinelflow_access_token=([^;]+)/) ||
        document.cookie.match(/(?:^|;\s*)sentinelflow_test_user=([^;]+)/)
      );
      setHasSession(hasToken);
    } catch {
      setHasSession(false);
    }
  }, []);

  const [testSender, setTestSender] = useState<string>("+14155552671");
  const [testRecipient, setTestRecipient] = useState<string>("+14155559876");
  const [testCarrier, setTestCarrier] = useState<string>("Verizon Wireless");
  const [testMessage, setTestMessage] = useState<string>(
    "Carrier security code: 492018. Valid for 5 minutes. Do not share this code."
  );
  const [isClassifying, setIsClassifying] = useState<boolean>(false);
  const [classificationResult, setClassificationResult] = useState<TelecomFeedItem | null>(null);
  const [autoEscalate, setAutoEscalate] = useState<boolean>(false);
  const [isEscalating, setIsEscalating] = useState<boolean>(false);
  const [escalatedDispute, setEscalatedDispute] = useState<{
    id: string;
    case_code?: string;
    url: string;
  } | null>(null);

  const applyPreset = (preset: TelecomPreset) => {
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
    setIsClassifying(true);
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
      }
    } catch (err) {
      console.error("Classification request failed", err);
    } finally {
      setIsClassifying(false);
    }
  };

  const handleEscalateResult = async () => {
    if (!classificationResult) {
      return;
    }
    if (!hasSession) {
      window.location.href = "/login?returnTo=/telecom";
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
          url: data.dispute_url,
        });
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
        <span
          style={{
            fontSize: 11,
            color: "var(--muted)",
            fontWeight: 600,
            display: "block",
            marginBottom: 6,
          }}
        >
          QUICK TEST PRESETS:
        </span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {presets.map((p) => (
            <button
              key={p.name}
              type="button"
              onClick={() => applyPreset(p)}
              style={{
                fontSize: 12,
                padding: "5px 10px",
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "rgba(255,255,255,0.04)",
                color: "var(--foreground)",
                cursor: "pointer",
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleClassify}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
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
              onChange={(e) => setTestSender(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
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
              onChange={(e) => setTestCarrier(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
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
              padding: "8px 12px",
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
            onChange={(e) => setTestMessage(e.target.value)}
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

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <input
            id={`${formId}-auto-escalate`}
            type="checkbox"
            checked={autoEscalate}
            onChange={(e) => setAutoEscalate(e.target.checked)}
            style={{ accentColor: "var(--accent)", cursor: "pointer", width: 16, height: 16 }}
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
            padding: "10px 16px",
            borderRadius: "var(--card-radius, 8px)",
            background: "var(--accent)",
            color: "#ffffff",
            fontWeight: 700,
            fontSize: 14,
            border: "none",
            cursor: isClassifying ? "wait" : "pointer",
          }}
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

            <span style={{ fontSize: 12, fontFamily: "monospace", color: "#22c55e" }}>
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
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: sig.startsWith("RULE:")
                        ? "rgba(239, 68, 68, 0.2)"
                        : "rgba(201, 243, 106, 0.2)",
                      color: sig.startsWith("RULE:") ? "#f87171" : "var(--accent)",
                      border: "1px solid rgba(255,255,255,0.1)",
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
                marginTop: 12,
                paddingTop: 10,
                borderTop: "1px solid rgba(255,255,255,0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span style={{ fontSize: 12, color: "var(--muted)" }}>Two-Tier Escalation:</span>
              {escalatedDispute ? (
                <a
                  href={escalatedDispute.url}
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
                  {escalatedDispute.case_code ? `(${escalatedDispute.case_code})` : ""} →
                </a>
              ) : (
                <button
                  type="button"
                  disabled={isEscalating}
                  onClick={handleEscalateResult}
                  style={{
                    fontSize: 11,
                    padding: "4px 10px",
                    borderRadius: "var(--card-radius, 4px)",
                    background: "var(--accent-soft, rgba(37, 99, 235, 0.1))",
                    color: "var(--accent, #2563eb)",
                    border: "1px solid var(--panel-border)",
                    cursor: isEscalating ? "wait" : "pointer",
                    fontWeight: 600,
                  }}
                >
                  {isEscalating ? (
                    "Escalating..."
                  ) : (
                    <>
                      <span className="page-icon">⚡ </span>
                      {hasSession ? "Escalate to SentinelFlow" : "Sign in to Escalate to SentinelFlow"}
                    </>
                  )}
                </button>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
});

TelecomClassifySandbox.displayName = "TelecomClassifySandbox";

"use client";

import Link from "next/link";
import React from "react";
import { useSentinelPulse } from "@/components/SentinelPulseProvider";
import { TelecomClassifySandbox } from "@/components/telecom/TelecomClassifySandbox";
import { TelecomLiveFeed } from "@/components/telecom/TelecomLiveFeed";
import { TelecomTelemetryCards } from "@/components/telecom/TelecomTelemetryCards";
import type { DriftReport, MetricsSummary, TelecomPreset } from "@/components/telecom/types";

const PRESETS: TelecomPreset[] = [
  {
    name: "Legit 2FA Security Code",
    sender: "+14155552671",
    carrier: "Verizon Wireless",
    message: "Carrier security code: 492018. Valid for 5 minutes. Do not share this code.",
  },
  {
    name: "Chase Bank Smishing",
    sender: "+15550001234",
    carrier: "TextNow",
    message:
      "URGENT: Chase Bank alert. Account suspended! Verify immediately: http://bit.ly/chase-verify-now",
  },
  {
    name: "USPS Delivery Fee Scam",
    sender: "+15558883344",
    carrier: "Bandwidth.com",
    message:
      "USPS Alert: Package 928301 held due to incomplete address. Pay $1.99 fee: http://tinyurl.com/usps-fee",
  },
  {
    name: "Crypto 300% Telegram Scam",
    sender: "+15557779922",
    carrier: "Sinch Virtual",
    message:
      "Exclusive Crypto VIP signal: Earn 300% guaranteed return in 24h! Join Telegram: https://t.me/cryptogains999",
  },
];

const BASELINE_DRIFT: DriftReport = {
  status: "HEALTHY",
  ks_statistic: 0.0,
  ks_p_value: 1.0,
  ks_drift_detected: false,
  psi_score: 0.0,
  psi_status: "STABLE",
  sample_count: 0,
  baseline_sample_count: 1000,
  mean_live_length: 0,
  mean_baseline_length: 64.0,
  recommendation: "Baseline calibrated. Distribution healthy.",
};

const EMPTY_METRICS: MetricsSummary = {
  total_requests: 0,
  throughput_eps: 0,
  verdicts: { allow: 0, flag: 0, block: 0 },
  fraud_rate_pct: 0,
  latency: { p50_ms: 0, p90_ms: 0, p95_ms: 0, p99_ms: 0, avg_ms: 0 },
  recent_feed: [],
};

const HomePage = () => {
  const { metrics: ctxMetrics, drift: ctxDrift, connected, refreshTelemetry } = useSentinelPulse();
  const metrics = ctxMetrics ?? EMPTY_METRICS;
  const drift = ctxDrift ?? BASELINE_DRIFT;

  return (
    <main style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Two-Tier Architecture Hero Banner */}
      <section
        className="shell-card"
        style={{
          padding: "26px 30px",
          margin: 0,
          background:
            "linear-gradient(135deg, rgba(201, 243, 106, 0.08) 0%, rgba(14, 92, 75, 0.12) 60%, rgba(37, 99, 235, 0.06) 100%)",
          border: "1px solid rgba(201, 243, 106, 0.35)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div style={{ minWidth: 0, flex: "1 1 540px" }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: connected ? "#22c55e" : "#eab308",
                  boxShadow: connected ? "0 0 8px #22c55e" : "none",
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.08em",
                  color: "var(--muted)",
                  textTransform: "uppercase",
                }}
              >
                {connected ? "LIVE GATEWAY STREAM ACTIVE" : "GATEWAY RECONNECTING"}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "var(--accent-soft, rgba(201, 243, 106, 0.15))",
                  color: "var(--accent, #2563eb)",
                  border: "1px solid var(--panel-border)",
                }}
              >
                STAGE 1 · WIRE INGRESS
              </span>
            </div>

            <h1
              style={{
                margin: "4px 0 10px",
                fontSize: "clamp(1.85rem, 4vw, 3.2rem)",
                letterSpacing: "-0.03em",
                lineHeight: 1.15,
                overflowWrap: "anywhere",
              }}
            >
              <span className="page-icon">📡 </span>SentinelPulse: Real-Time Telecom Ingress
            </h1>

            <p style={{ maxWidth: 740, margin: "0 0 16px", color: "var(--muted)", lineHeight: 1.6, fontSize: 14 }}>
              Production-grade, sub-15ms carrier fraud &amp; smishing inspection gateway powered by
              an optimized ONNX Runtime CPU model and Redis sliding-window velocity counters. High-risk
              anomalies escalate seamlessly to SentinelFlow (Stage 2) for autonomous multi-agent dispute investigation.
            </p>

            {/* Two-Tier Architecture Summary Pills */}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "5px 12px",
                  borderRadius: 6,
                  background: "#dcfce7",
                  color: "#14532d",
                  border: "1px solid #15803d",
                  fontFamily: "monospace",
                }}
              >
                Stage 1: &lt;15ms ONNX CPU
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "5px 12px",
                  borderRadius: 6,
                  background: "#dbeafe",
                  color: "#1e3a8a",
                  border: "1px solid #1e40af",
                  fontFamily: "monospace",
                }}
              >
                Stage 2: LangGraph + GPT-4
              </span>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-end", flexShrink: 0 }}>
            <span
              className="sla-pill"
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: "var(--card-radius, 8px)",
                background: "var(--input-bg, #ffffff)",
                border: "1px solid var(--panel-border)",
                color: "var(--foreground)",
                fontFamily: "monospace",
              }}
            >
              SLA: &lt;15ms p95 | Ops: 5k RPS
            </span>

            <Link
              href="/disputes"
              prefetch={true}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 18px",
                borderRadius: "var(--card-radius, 8px)",
                background: "var(--accent)",
                color: "var(--accent-ink, #ffffff)",
                fontWeight: 700,
                fontSize: 13,
                textDecoration: "none",
                boxShadow: "0 0 14px rgba(201, 243, 106, 0.3)",
                transition: "transform 0.15s ease",
              }}
            >
              <span>⚡ View SentinelFlow Workbench (Stage 2) →</span>
            </Link>
          </div>
        </div>
      </section>

      {/* Telemetry Cards Grid */}
      <TelecomTelemetryCards metrics={metrics} drift={drift} />

      {/* Main Two-Column Layout */}
      <div
        className="telecom-two-cards-grid"
        style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}
      >
        {/* Interactive Simulator Section */}
        <TelecomClassifySandbox presets={PRESETS} onClassificationSuccess={refreshTelemetry} />

        {/* Live Event Stream Feed */}
        <TelecomLiveFeed initialFeed={metrics.recent_feed} />
      </div>
    </main>
  );
};

export default HomePage;

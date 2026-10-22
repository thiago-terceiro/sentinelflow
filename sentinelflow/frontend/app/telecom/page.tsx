"use client";

import React, { useCallback, useEffect, useState } from "react";
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

const TelecomDashboardPage = () => {
  const [metrics, setMetrics] = useState<MetricsSummary>({
    total_requests: 0,
    throughput_eps: 0,
    verdicts: { allow: 0, flag: 0, block: 0 },
    fraud_rate_pct: 0,
    latency: { p50_ms: 0, p90_ms: 0, p95_ms: 0, p99_ms: 0, avg_ms: 0 },
    recent_feed: [],
  });

  const [drift, setDrift] = useState<DriftReport>(BASELINE_DRIFT);
  const [connected, setConnected] = useState<boolean>(false);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch("/app-api/telecom/metrics/summary");
      if (res.ok) {
        const data = (await res.json()) as MetricsSummary;
        setMetrics(data);
      }
    } catch (err) {
      console.warn("Failed to fetch telecom metrics summary", err);
    }
  }, []);

  const fetchDrift = useCallback(async () => {
    try {
      const res = await fetch("/app-api/telecom/drift");
      if (res.ok) {
        const data = (await res.json()) as DriftReport;
        setDrift(data);
      }
    } catch (err) {
      console.warn("Failed to fetch drift report", err);
    }
  }, []);

  useEffect(() => {
    void fetchMetrics();
    void fetchDrift();

    const interval = setInterval(() => {
      void fetchMetrics();
      void fetchDrift();
    }, 3000);

    return () => {
      clearInterval(interval);
    };
  }, [fetchMetrics, fetchDrift]);

  const handleConnectionChange = useCallback((isLive: boolean) => {
    setConnected(isLive);
  }, []);

  return (
    <main>
      {/* Header Banner */}
      <div
        className="shell-card"
        style={{
          padding: "24px 28px",
          marginBottom: 20,
          background:
            "linear-gradient(135deg, rgba(201, 243, 106, 0.08) 0%, rgba(14, 92, 75, 0.12) 100%)",
          border: "1px solid rgba(201, 243, 106, 0.3)",
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
          <div>
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
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  color: "var(--muted)",
                  textTransform: "uppercase",
                }}
              >
                {connected ? "LIVE GATEWAY STREAM ACTIVE" : "GATEWAY RECONNECTING"}
              </span>
            </div>
            <h1 style={{ margin: "8px 0 12px", fontSize: "clamp(2.4rem, 4.5vw, 4rem)" }}>
              <span className="page-icon">📡 </span>SentinelPulse: SMS Intelligence Gateway
            </h1>
            <p style={{ maxWidth: 700, margin: 0, color: "var(--muted)", lineHeight: 1.6 }}>
              Production-grade, sub-15ms telecom fraud & smishing detection engine for high-throughput
              messaging gateways (Global CPaaS Traffic Intelligence & Messaging Anti-Abuse). Powered
              by optimized ONNX Runtime CPU inference and Redis sliding-window velocity counters.
            </p>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
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
          </div>
        </div>
      </div>

      {/* Telemetry Cards Grid */}
      <TelecomTelemetryCards metrics={metrics} drift={drift} />

      {/* Main Two-Column Layout */}
      <div
        className="telecom-two-cards-grid"
        style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}
      >
        {/* Interactive Simulator Section */}
        <TelecomClassifySandbox presets={PRESETS} onClassificationSuccess={fetchMetrics} />

        {/* Live Event Stream Feed */}
        <TelecomLiveFeed
          initialFeed={metrics.recent_feed}
          onConnectionChange={handleConnectionChange}
        />
      </div>
    </main>
  );
};

export default TelecomDashboardPage;

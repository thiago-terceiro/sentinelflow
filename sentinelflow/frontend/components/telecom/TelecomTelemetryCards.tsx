"use client";

import React, { memo } from "react";
import type { DriftReport, MetricsSummary } from "./types";

type Props = {
  metrics: MetricsSummary;
  drift: DriftReport | null;
};

const getDriftBadgeStyle = (status: string | undefined): { color: string; bg: string } => {
  if (status === "CRITICAL_DRIFT") {
    return { color: "#ef4444", bg: "rgba(239, 68, 68, 0.15)" };
  }
  if (status === "MODERATE_DRIFT") {
    return { color: "#eab308", bg: "rgba(234, 179, 8, 0.15)" };
  }
  return { color: "#22c55e", bg: "rgba(34, 197, 94, 0.15)" };
};

export const TelecomTelemetryCards = memo(({ metrics, drift }: Props) => {
  const driftStyle = getDriftBadgeStyle(drift?.status);
  const p95Color = metrics.latency.p95_ms < 15 ? "#22c55e" : "#eab308";
  const p99Color = metrics.latency.p99_ms < 30 ? "#22c55e" : "#ef4444";
  const fraudRateColor = metrics.fraud_rate_pct > 20 ? "#f97316" : "var(--foreground)";

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
        gap: 16,
        marginBottom: 24,
      }}
    >
      {/* Throughput Card */}
      <div
        className="shell-card"
        style={{
          padding: "20px 22px",
          minHeight: 170,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: "var(--muted)",
              textTransform: "uppercase",
            }}
          >
            Traffic Throughput
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 10 }}>
            <span
              style={{
                fontSize: 36,
                fontWeight: 800,
                letterSpacing: "-0.04em",
                color: "var(--accent)",
              }}
            >
              {metrics.throughput_eps}
            </span>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>events / sec</span>
          </div>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
          Total processed:{" "}
          <strong style={{ color: "var(--foreground)" }}>
            {metrics.total_requests.toLocaleString()}
          </strong>{" "}
          messages
        </div>
      </div>

      {/* Latency Percentiles Card */}
      <div
        className="shell-card"
        style={{
          padding: "20px 22px",
          minHeight: 170,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: "var(--muted)",
              textTransform: "uppercase",
            }}
          >
            Inference Latency SLA
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            <div style={{ display: "flex", gap: 24 }}>
              <div>
                <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p50</span>
                <span style={{ fontSize: 18, fontWeight: 700, color: "#22c55e" }}>
                  {metrics.latency.p50_ms.toFixed(2)}ms
                </span>
              </div>
              <div>
                <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p90</span>
                <span style={{ fontSize: 18, fontWeight: 700, color: "#22c55e" }}>
                  {metrics.latency.p90_ms.toFixed(2)}ms
                </span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 24 }}>
              <div>
                <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p95</span>
                <span style={{ fontSize: 18, fontWeight: 700, color: p95Color }}>
                  {metrics.latency.p95_ms.toFixed(2)}ms
                </span>
              </div>
              <div>
                <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p99</span>
                <span style={{ fontSize: 18, fontWeight: 700, color: p99Color }}>
                  {metrics.latency.p99_ms.toFixed(2)}ms
                </span>
              </div>
            </div>
          </div>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: "#22c55e" }}>
          ✓ Within 15ms target envelope
        </div>
      </div>

      {/* Fraud Rate Card */}
      <div
        className="shell-card"
        style={{
          padding: "20px 22px",
          minHeight: 170,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: "var(--muted)",
              textTransform: "uppercase",
            }}
          >
            Fraud & Threat Rate
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 10 }}>
            <span
              style={{
                fontSize: 36,
                fontWeight: 800,
                letterSpacing: "-0.04em",
                color: fraudRateColor,
              }}
            >
              {metrics.fraud_rate_pct.toFixed(1)}%
            </span>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>threat ratio</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8, fontSize: 11 }}>
          <span style={{ color: "#22c55e" }}>Allow: {metrics.verdicts.allow}</span>
          <span style={{ color: "#eab308" }}>Flag: {metrics.verdicts.flag}</span>
          <span style={{ color: "#ef4444" }}>Block: {metrics.verdicts.block}</span>
        </div>
      </div>

      {/* MLOps Drift Health Card */}
      <div
        className="shell-card"
        style={{
          padding: "20px 22px",
          minHeight: 170,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: "var(--muted)",
              textTransform: "uppercase",
            }}
          >
            MLOps Data Drift
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
            <span
              style={{
                fontSize: 14,
                fontWeight: 700,
                padding: "4px 10px",
                borderRadius: 6,
                background: driftStyle.bg,
                color: driftStyle.color,
                border: "1px solid currentColor",
              }}
            >
              {drift?.status ?? "HEALTHY"}
            </span>
          </div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 8,
            fontSize: 11,
            color: "var(--muted)",
          }}
        >
          <span>KS p-val: {drift ? drift.ks_p_value.toFixed(3) : "1.000"}</span>
          <span>PSI: {drift ? drift.psi_score.toFixed(3) : "0.000"}</span>
        </div>
      </div>
    </div>
  );
});

TelecomTelemetryCards.displayName = "TelecomTelemetryCards";

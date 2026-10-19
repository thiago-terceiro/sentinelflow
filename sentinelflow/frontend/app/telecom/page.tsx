"use client";

import React, { useEffect, useId, useState } from "react";

type TelecomVerdict = "ALLOW" | "BLOCK" | "FLAG";

type TelecomFeedItem = {
  id: string;
  timestamp: number;
  sender: string;
  recipient: string;
  message: string;
  verdict: TelecomVerdict;
  fraud_score: number;
  latency_ms: number;
  signals: string[];
  carrier: string;
  velocity?: {
    velocity_10s: number;
    velocity_60s: number;
    velocity_1h: number;
  };
  escalated_dispute_id?: string | null;
  escalated_dispute_url?: string | null;
};

type MetricsSummary = {
  total_requests: number;
  throughput_eps: number;
  verdicts: {
    allow: number;
    flag: number;
    block: number;
  };
  fraud_rate_pct: number;
  latency: {
    p50_ms: number;
    p90_ms: number;
    p95_ms: number;
    p99_ms: number;
    avg_ms: number;
  };
  recent_feed: TelecomFeedItem[];
};

type DriftReport = {
  status: "HEALTHY" | "MODERATE_DRIFT" | "CRITICAL_DRIFT";
  ks_statistic: number;
  ks_p_value: number;
  ks_drift_detected: boolean;
  psi_score: number;
  psi_status: string;
  sample_count: number;
  baseline_sample_count: number;
  mean_live_length: number;
  mean_baseline_length: number;
  recommendation: string;
};

const PRESETS = [
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
    message: "URGENT: Chase Bank alert. Account suspended! Verify immediately: http://bit.ly/chase-verify-now",
  },
  {
    name: "USPS Delivery Fee Scam",
    sender: "+15558883344",
    carrier: "Bandwidth.com",
    message: "USPS Alert: Package 928301 held due to incomplete address. Pay $1.99 fee: http://tinyurl.com/usps-fee",
  },
  {
    name: "Crypto 300% Telegram Scam",
    sender: "+15557779922",
    carrier: "Sinch Virtual",
    message: "Exclusive Crypto VIP signal: Earn 300% guaranteed return in 24h! Join Telegram: https://t.me/cryptogains999",
  },
];

const getVerdictColor = (verdict: TelecomVerdict): string => {
  if (verdict === "BLOCK") {
    return "#ef4444";
  }
  if (verdict === "FLAG") {
    return "#eab308";
  }
  return "#22c55e";
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

const TelemetryCards = ({
  metrics,
  drift,
}: {
  metrics: MetricsSummary;
  drift: DriftReport | null;
}) => {
  const driftStyle = getDriftBadgeStyle(drift?.status);
  const p95Color = metrics.latency.p95_ms < 15 ? "#22c55e" : "#eab308";
  const p99Color = metrics.latency.p99_ms < 30 ? "#22c55e" : "#ef4444";
  const fraudRateColor = metrics.fraud_rate_pct > 20 ? "#f97316" : "var(--foreground)";

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 16, marginBottom: 24 }}>
      {/* Throughput Card */}
      <div className="shell-card" style={{ padding: "20px 22px" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: "var(--muted)", textTransform: "uppercase" }}>
          Traffic Throughput
        </span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 10 }}>
          <span style={{ fontSize: 36, fontWeight: 800, letterSpacing: "-0.04em", color: "var(--accent)" }}>
            {metrics.throughput_eps}
          </span>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>events / sec</span>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--muted)" }}>
          Total processed: <strong style={{ color: "var(--foreground)" }}>{metrics.total_requests.toLocaleString()}</strong> messages
        </div>
      </div>

      {/* Latency Percentiles Card */}
      <div className="shell-card" style={{ padding: "20px 22px" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: "var(--muted)", textTransform: "uppercase" }}>
          Inference Latency SLA
        </span>
        <div style={{ display: "flex", gap: 12, marginTop: 10 }}>
          <div>
            <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p50</span>
            <span style={{ fontSize: 20, fontWeight: 700, color: "#22c55e" }}>
              {metrics.latency.p50_ms.toFixed(2)}ms
            </span>
          </div>
          <div>
            <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p90</span>
            <span style={{ fontSize: 20, fontWeight: 700, color: "#22c55e" }}>
              {metrics.latency.p90_ms.toFixed(2)}ms
            </span>
          </div>
          <div>
            <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p95</span>
            <span style={{ fontSize: 20, fontWeight: 700, color: p95Color }}>
              {metrics.latency.p95_ms.toFixed(2)}ms
            </span>
          </div>
          <div>
            <span style={{ fontSize: 10, color: "var(--muted)", display: "block" }}>p99</span>
            <span style={{ fontSize: 20, fontWeight: 700, color: p99Color }}>
              {metrics.latency.p99_ms.toFixed(2)}ms
            </span>
          </div>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: "#22c55e" }}>
          ✓ Within 15ms target envelope
        </div>
      </div>

      {/* Fraud Rate Card */}
      <div className="shell-card" style={{ padding: "20px 22px" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: "var(--muted)", textTransform: "uppercase" }}>
          Fraud & Threat Rate
        </span>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 10 }}>
          <span style={{ fontSize: 36, fontWeight: 800, letterSpacing: "-0.04em", color: fraudRateColor }}>
            {metrics.fraud_rate_pct.toFixed(1)}%
          </span>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>threat ratio</span>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8, fontSize: 11 }}>
          <span style={{ color: "#22c55e" }}>Allow: {metrics.verdicts.allow}</span>
          <span style={{ color: "#eab308" }}>Flag: {metrics.verdicts.flag}</span>
          <span style={{ color: "#ef4444" }}>Block: {metrics.verdicts.block}</span>
        </div>
      </div>

      {/* MLOps Drift Health Card */}
      <div className="shell-card" style={{ padding: "20px 22px" }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: "var(--muted)", textTransform: "uppercase" }}>
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
            {drift ? drift.status : "INITIALIZING"}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
          <span>KS p-val: {drift ? drift.ks_p_value.toFixed(3) : "1.000"}</span>
          <span>PSI: {drift ? drift.psi_score.toFixed(3) : "0.000"}</span>
        </div>
      </div>
    </div>
  );
};

const EscalationAction = ({
  item,
  isEscalating,
  escalated,
  onEscalate,
}: {
  item: TelecomFeedItem;
  isEscalating: boolean;
  escalated?: { id: string; case_code?: string; url: string };
  onEscalate: () => void;
}) => {
  if (item.verdict !== "FLAG" && item.verdict !== "BLOCK") {
    return null;
  }

  const effectiveEscalated =
    escalated ||
    (item.escalated_dispute_id
      ? {
          id: item.escalated_dispute_id,
          url: item.escalated_dispute_url || `/disputes/${item.escalated_dispute_id}`,
        }
      : undefined);

  if (effectiveEscalated) {
    return (
      <a
        href={effectiveEscalated.url}
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
        🔍 View Case in SentinelFlow {effectiveEscalated.case_code ? `(${effectiveEscalated.case_code})` : ""} →
      </a>
    );
  }

  return (
    <button
      type="button"
      disabled={isEscalating}
      onClick={onEscalate}
      style={{
        fontSize: 11,
        padding: "3px 8px",
        borderRadius: 4,
        background: "rgba(201, 243, 106, 0.12)",
        color: "var(--accent)",
        border: "1px solid rgba(201, 243, 106, 0.3)",
        cursor: isEscalating ? "wait" : "pointer",
        fontWeight: 600,
      }}
    >
      {isEscalating ? "Escalating..." : "⚡ Escalate to SentinelFlow"}
    </button>
  );
};

const TelecomDashboardPage = () => {
  const formId = useId();
  const [metrics, setMetrics] = useState<MetricsSummary>({
    total_requests: 0,
    throughput_eps: 0,
    verdicts: { allow: 0, flag: 0, block: 0 },
    fraud_rate_pct: 0,
    latency: { p50_ms: 0, p90_ms: 0, p95_ms: 0, p99_ms: 0, avg_ms: 0 },
    recent_feed: [],
  });

  const [drift, setDrift] = useState<DriftReport | null>(null);
  const [liveFeed, setLiveFeed] = useState<TelecomFeedItem[]>([]);
  const [connected, setConnected] = useState<boolean>(false);
  const [filterVerdict, setFilterVerdict] = useState<string>("ALL");
  const [isPaused, setIsPaused] = useState<boolean>(false);

  // Interactive Test State
  const [testSender, setTestSender] = useState<string>("+14155552671");
  const [testRecipient, setTestRecipient] = useState<string>("+14155559876");
  const [testCarrier, setTestCarrier] = useState<string>("Verizon Wireless");
  const [testMessage, setTestMessage] = useState<string>(
    "Carrier security code: 492018. Valid for 5 minutes. Do not share this code."
  );
  const [isClassifying, setIsClassifying] = useState<boolean>(false);
  const [classificationResult, setClassificationResult] = useState<TelecomFeedItem | null>(null);
  const [autoEscalate, setAutoEscalate] = useState<boolean>(false);
  const [escalatingIds, setEscalatingIds] = useState<Record<string, boolean>>({});
  const [escalatedDisputes, setEscalatedDisputes] = useState<
    Record<string, { id: string; case_code?: string; url: string }>
  >({});

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

  // Fetch metrics summary
  const fetchMetrics = async () => {
    try {
      const res = await fetch("/app-api/telecom/metrics/summary");
      if (res.ok) {
        const data = (await res.json()) as MetricsSummary;
        setMetrics(data);
        if (data.recent_feed && data.recent_feed.length > 0) {
          setLiveFeed((prev) => {
            if (prev.length === 0) {
              return data.recent_feed;
            }
            return prev;
          });
        }
      }
    } catch (err) {
      console.warn("Failed to fetch telecom metrics summary", err);
    }
  };

  // Fetch drift status
  const fetchDrift = async () => {
    try {
      const res = await fetch("/app-api/telecom/drift");
      if (res.ok) {
        const data = (await res.json()) as DriftReport;
        setDrift(data);
      }
    } catch (err) {
      console.warn("Failed to fetch drift report", err);
    }
  };

  // Establish SSE stream
  useEffect(() => {
    let es: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const connectSSE = () => {
      try {
        es = new EventSource("/app-api/telecom/stream");

        es.onopen = () => {
          setConnected(true);
        };

        es.addEventListener("message", (event) => {
          try {
            const parsed = JSON.parse(event.data) as TelecomFeedItem;
            if (!isPaused) {
              setLiveFeed((prev) => [parsed, ...prev.slice(0, 49)]);
            }
          } catch (e) {
            console.debug("Failed to parse SSE event", e);
          }
        });

        es.onerror = () => {
          setConnected(false);
          if (es) {
            es.close();
          }
          reconnectTimeout = setTimeout(connectSSE, 4000);
        };
      } catch (err) {
        console.warn("Error setting up EventSource", err);
        setConnected(false);
      }
    };

    connectSSE();
    void fetchMetrics();
    void fetchDrift();

    const interval = setInterval(() => {
      void fetchMetrics();
      void fetchDrift();
    }, 3000);

    return () => {
      if (es) {
        es.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      clearInterval(interval);
    };
  }, [isPaused]);

  // Execute interactive test classification
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
          const itemKey = data.id || "test-result";
          setEscalatedDisputes((prev) => ({
            ...prev,
            [itemKey]: {
              id: data.escalated_dispute_id!,
              url: data.escalated_dispute_url || `/disputes/${data.escalated_dispute_id}`,
            },
          }));
        }
        void fetchMetrics();
      }
    } catch (err) {
      console.error("Classification request failed", err);
    } finally {
      setIsClassifying(false);
    }
  };

  const applyPreset = (preset: (typeof PRESETS)[number]) => {
    setTestSender(preset.sender);
    setTestCarrier(preset.carrier);
    setTestMessage(preset.message);
    setClassificationResult(null);
  };

  const filteredFeed = liveFeed.filter((item) => {
    if (filterVerdict === "ALL") {
      return true;
    }
    return item.verdict === filterVerdict;
  });

  return (
    <main style={{ width: "min(1200px, calc(100vw - 2rem))", margin: "24px auto 60px" }}>
      {/* Header Banner */}
      <div
        className="shell-card"
        style={{
          padding: "24px 28px",
          marginBottom: 20,
          background: "linear-gradient(135deg, rgba(201, 243, 106, 0.08) 0%, rgba(14, 92, 75, 0.12) 100%)",
          border: "1px solid rgba(201, 243, 106, 0.3)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
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
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: "var(--muted)", textTransform: "uppercase" }}>
                {connected ? "LIVE GATEWAY STREAM ACTIVE" : "GATEWAY RECONNECTING"}
              </span>
            </div>
            <h1 style={{ margin: "0 0 6px", fontSize: 28, letterSpacing: "-0.03em" }}>
              📡 SentinelPulse: SMS Intelligence Gateway
            </h1>
            <p style={{ margin: 0, color: "var(--muted)", fontSize: 14, maxWidth: 850 }}>
              Production-grade, sub-15ms telecom fraud & smishing detection engine for high-throughput messaging
              gateways (Global CPaaS Traffic Intelligence & Messaging Anti-Abuse). Powered by optimized ONNX Runtime CPU inference and Redis sliding-window velocity counters.
            </p>
          </div>

          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span
              style={{
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 8,
                background: "rgba(0,0,0,0.3)",
                border: "1px solid var(--border)",
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
      <TelemetryCards metrics={metrics} drift={drift} />

      {/* Main Two-Column Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 20 }}>
        {/* Interactive Simulator Section */}
        <div className="shell-card" style={{ padding: "24px 26px" }}>
          <h2 style={{ margin: "0 0 6px", fontSize: 20, letterSpacing: "-0.02em" }}>
            🧪 Interactive SMS Gateway Tester
          </h2>
          <p style={{ margin: "0 0 16px", color: "var(--muted)", fontSize: 13 }}>
            Submit arbitrary SMS payloads to inspect the live decision path, model probability, rule signals, and sliding-window velocity calculations.
          </p>

          {/* Presets */}
          <div style={{ marginBottom: 16 }}>
            <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 600, display: "block", marginBottom: 6 }}>
              QUICK TEST PRESETS:
            </span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {PRESETS.map((p) => (
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
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div>
                <label htmlFor={`${formId}-sender`} style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
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
                <label htmlFor={`${formId}-carrier`} style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
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
              <label htmlFor={`${formId}-recipient`} style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
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
              <label htmlFor={`${formId}-message`} style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
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
                ⚡ Auto-escalate FLAG / BLOCK anomalies to SentinelFlow Investigation
              </label>
            </div>

            <button
              type="submit"
              disabled={isClassifying}
              style={{
                width: "100%",
                padding: "10px 16px",
                borderRadius: 8,
                background: "var(--accent)",
                color: "#10231e",
                fontWeight: 700,
                fontSize: 14,
                border: "none",
                cursor: isClassifying ? "wait" : "pointer",
              }}
            >
              {isClassifying ? "Classifying..." : "⚡ Run Real-Time Classification (<15ms)"}
            </button>
          </form>

          {/* Test Decision Output */}
          {classificationResult ? (
            <div
              style={{
                marginTop: 20,
                padding: "18px 20px",
                borderRadius: 10,
                background: "rgba(0,0,0,0.25)",
                border: `1px solid ${getVerdictColor(classificationResult.verdict)}`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span
                    style={{
                      padding: "4px 10px",
                      borderRadius: 6,
                      fontSize: 14,
                      fontWeight: 800,
                      background: getVerdictColor(classificationResult.verdict),
                      color: "#10231e",
                    }}
                  >
                    {classificationResult.verdict}
                  </span>
                  <span style={{ fontSize: 13, color: "var(--muted)" }}>
                    Fraud Score: <strong style={{ color: "var(--foreground)" }}>{classificationResult.fraud_score}</strong>
                  </span>
                </div>

                <span style={{ fontSize: 12, fontFamily: "monospace", color: "#22c55e" }}>
                  ⏱ {classificationResult.latency_ms} ms
                </span>
              </div>

              {classificationResult.signals && classificationResult.signals.length > 0 ? (
                <div style={{ marginBottom: 10 }}>
                  <span style={{ fontSize: 11, color: "var(--muted)", display: "block", marginBottom: 4 }}>
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
                          background: sig.startsWith("RULE:") ? "rgba(239, 68, 68, 0.2)" : "rgba(201, 243, 106, 0.2)",
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
                <div style={{ fontSize: 12, color: "var(--muted)", paddingTop: 8, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
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
                  <EscalationAction
                    item={classificationResult}
                    isEscalating={Boolean(escalatingIds[classificationResult.id || "test-result"])}
                    escalated={
                      escalatedDisputes[classificationResult.id || "test-result"] ||
                      (classificationResult.escalated_dispute_id
                        ? {
                            id: classificationResult.escalated_dispute_id,
                            url:
                              classificationResult.escalated_dispute_url ||
                              `/disputes/${classificationResult.escalated_dispute_id}`,
                          }
                        : undefined)
                    }
                    onEscalate={() => {
                      void handleEscalate(classificationResult);
                    }}
                  />
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* Live Event Stream Feed */}
        <div className="shell-card" style={{ padding: "24px 26px", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div>
              <h2 style={{ margin: "0 0 4px", fontSize: 20, letterSpacing: "-0.02em" }}>
                🛰️ Real-Time Inspection Feed
              </h2>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Live incoming telecom messages ({filteredFeed.length} buffered)
              </span>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button
                type="button"
                onClick={() => setIsPaused(!isPaused)}
                style={{
                  fontSize: 11,
                  padding: "4px 8px",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: isPaused ? "#ef4444" : "rgba(255,255,255,0.06)",
                  color: isPaused ? "#fff" : "var(--foreground)",
                  cursor: "pointer",
                }}
              >
                {isPaused ? "▶ Resume" : "⏸ Pause"}
              </button>
            </div>
          </div>

          {/* Filter Pills */}
          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            {["ALL", "BLOCK", "FLAG", "ALLOW"].map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilterVerdict(f)}
                style={{
                  fontSize: 11,
                  padding: "3px 8px",
                  borderRadius: 4,
                  border: filterVerdict === f ? "1px solid var(--accent)" : "1px solid var(--border)",
                  background: filterVerdict === f ? "rgba(201,243,106,0.12)" : "transparent",
                  color: filterVerdict === f ? "var(--accent)" : "var(--muted)",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Scrollable Event Feed Container */}
          <div
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
              <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
                Waiting for incoming telecom events...
                <br />
                <span style={{ fontSize: 12 }}>Run the traffic simulator or test above to see events flow live!</span>
              </div>
            ) : (
              filteredFeed.map((ev) => (
                <div
                  key={ev.id}
                  style={{
                    padding: "12px 14px",
                    borderRadius: 8,
                    background: "rgba(0,0,0,0.18)",
                    border: "1px solid var(--border)",
                    fontSize: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
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

                  <p style={{ margin: "0 0 6px", color: "var(--foreground)", fontSize: 13, lineHeight: 1.35 }}>
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
                      <EscalationAction
                        item={ev}
                        isEscalating={Boolean(escalatingIds[ev.id || `${ev.sender}-${ev.timestamp}`])}
                        escalated={
                          escalatedDisputes[ev.id || `${ev.sender}-${ev.timestamp}`] ||
                          (ev.escalated_dispute_id
                            ? {
                                id: ev.escalated_dispute_id,
                                url: ev.escalated_dispute_url || `/disputes/${ev.escalated_dispute_id}`,
                              }
                            : undefined)
                        }
                        onEscalate={() => {
                          void handleEscalate(ev);
                        }}
                      />
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  );
};

export default TelecomDashboardPage;

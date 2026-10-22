export type TelecomVerdict = "ALLOW" | "BLOCK" | "FLAG";

export type TelecomFeedItem = {
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

export type MetricsSummary = {
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

export type DriftReport = {
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

export type TelecomPreset = {
  name: string;
  sender: string;
  carrier: string;
  message: string;
};

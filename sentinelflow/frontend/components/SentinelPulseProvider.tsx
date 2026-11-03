"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type {
  DriftReport as TelecomDriftReport,
  MetricsSummary as TelecomMetricsSummary,
  TelecomFeedItem,
} from "@/components/telecom/types";

type SentinelPulseContextValue = {
  hasSession: boolean;
  username: string | null;
  userRole: string | null;
  metrics: TelecomMetricsSummary | null;
  drift: TelecomDriftReport | null;
  liveFeed: TelecomFeedItem[];
  setLiveFeed: React.Dispatch<React.SetStateAction<TelecomFeedItem[]>>;
  connected: boolean;
  isPaused: boolean;
  setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;
  isResetting: boolean;
  resetGateway: () => Promise<void>;
  refreshTelemetry: () => Promise<void>;
};

const EMPTY_METRICS: TelecomMetricsSummary = {
  total_requests: 0,
  throughput_eps: 0,
  verdicts: { allow: 0, flag: 0, block: 0 },
  fraud_rate_pct: 0,
  latency: { p50_ms: 0, p90_ms: 0, p95_ms: 0, p99_ms: 0, avg_ms: 0 },
  recent_feed: [],
};

const SentinelPulseContext = createContext<SentinelPulseContextValue>({
  hasSession: false,
  username: null,
  userRole: null,
  metrics: null,
  drift: null,
  liveFeed: [],
  setLiveFeed: () => {},
  connected: true,
  isPaused: false,
  setIsPaused: () => {},
  isResetting: false,
  resetGateway: async () => {},
  refreshTelemetry: async () => {},
});

type ProviderProps = {
  children: React.ReactNode;
  initialHasSession?: boolean;
  initialUsername?: string | null;
  initialRole?: string | null;
};

export const SentinelPulseProvider = ({
  children,
  initialHasSession = false,
  initialUsername = null,
  initialRole = null,
}: ProviderProps) => {
  const [hasSession, setHasSession] = useState<boolean>(initialHasSession);
  const [username, setUsername] = useState<string | null>(initialUsername);
  const [userRole, setUserRole] = useState<string | null>(initialRole);

  const [metrics, setMetrics] = useState<TelecomMetricsSummary | null>(null);
  const [drift, setDrift] = useState<TelecomDriftReport | null>(null);
  const [liveFeed, setLiveFeed] = useState<TelecomFeedItem[]>([]);
  const [connected, setConnected] = useState<boolean>(true);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [isResetting, setIsResetting] = useState<boolean>(false);

  const isPausedRef = useRef<boolean>(false);
  const hasHydratedFeedRef = useRef<boolean>(false);

  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);

  useEffect(() => {
    setHasSession(initialHasSession);
    setUsername(initialUsername);
    setUserRole(initialRole);

    if (!initialHasSession && typeof document !== "undefined") {
      try {
        const cookieStr = document.cookie || "";
        const hasClientSession =
          cookieStr.includes("sentinelflow_access_token=") ||
          cookieStr.includes("sentinelflow_test_user=");
        if (hasClientSession) {
          setHasSession(true);
          const match = cookieStr.match(/(?:^|;\s*)sentinelflow_test_user=([^;]+)/);
          if (match) {
            const decoded = decodeURIComponent(match[1]);
            const parts = decoded.split(":", 2);
            setUsername(parts[0] || "dev-user");
            setUserRole(parts[1] || "investigator");
          }
        }
      } catch {
        // Ignore cookie parsing errors
      }
    }
  }, [initialHasSession, initialUsername, initialRole]);

  const refreshTelemetry = useCallback(async () => {
    try {
      const [metricsRes, driftRes] = await Promise.all([
        fetch("/app-api/telecom/metrics/summary", { cache: "no-store" }),
        fetch("/app-api/telecom/drift", { cache: "no-store" }),
      ]);
      if (metricsRes.ok) {
        const metricsData = (await metricsRes.json()) as TelecomMetricsSummary;
        setMetrics(metricsData);
        setConnected(true);
        if (!hasHydratedFeedRef.current && Array.isArray(metricsData.recent_feed)) {
          hasHydratedFeedRef.current = true;
          if (metricsData.recent_feed.length > 0) {
            setLiveFeed(metricsData.recent_feed);
          }
        }
      }
      if (driftRes.ok) {
        const driftData = (await driftRes.json()) as TelecomDriftReport;
        setDrift(driftData);
      }
    } catch {
      // Preserve last known telemetry snapshot on transient network hiccup
    }
  }, []);

  const resetGateway = useCallback(async () => {
    setIsResetting(true);
    hasHydratedFeedRef.current = true;
    setLiveFeed([]);
    setMetrics(EMPTY_METRICS);
    try {
      const res = await fetch("/app-api/telecom/reset", { method: "POST" });
      if (res.ok) {
        const payload = (await res.json()) as {
          metrics?: TelecomMetricsSummary;
          drift?: TelecomDriftReport;
        };
        if (payload.metrics) {
          setMetrics(payload.metrics);
        }
        if (payload.drift) {
          setDrift(payload.drift);
        }
        setLiveFeed([]);
      }
    } catch {
      // Local state already cleared
    } finally {
      setIsResetting(false);
    }
  }, []);

  useEffect(() => {
    void refreshTelemetry();
    const interval = setInterval(() => {
      void refreshTelemetry();
    }, 3000);
    return () => {
      clearInterval(interval);
    };
  }, [refreshTelemetry]);

  useEffect(() => {
    let es: EventSource | null = null;
    try {
      es = new EventSource("/app-api/telecom/stream");
      es.onopen = () => {
        setConnected(true);
      };
      es.addEventListener("connected", () => {
        setConnected(true);
      });
      es.addEventListener("reset", () => {
        hasHydratedFeedRef.current = true;
        setLiveFeed([]);
        setMetrics(EMPTY_METRICS);
      });
      es.addEventListener("message", (event) => {
        setConnected(true);
        if (isPausedRef.current) {
          return;
        }
        try {
          const parsed = JSON.parse(event.data) as TelecomFeedItem & { type?: string };
          if (parsed.type === "reset") {
            hasHydratedFeedRef.current = true;
            setLiveFeed([]);
            setMetrics(EMPTY_METRICS);
            return;
          }
          hasHydratedFeedRef.current = true;
          setLiveFeed((prev) => [parsed, ...prev].slice(0, 40));
        } catch {
          // Ignore malformed SSE payload
        }
      });
      es.onerror = () => {
        // Keep connected true if HTTP polling is healthy; EventSource auto-reconnects
      };
    } catch {
      // Fallback to HTTP polling if EventSource is unavailable
    }

    return () => {
      if (es) {
        es.close();
      }
    };
  }, []);

  return (
    <SentinelPulseContext.Provider
      value={{
        hasSession,
        username,
        userRole,
        metrics,
        drift,
        liveFeed,
        setLiveFeed,
        connected,
        isPaused,
        setIsPaused,
        isResetting,
        resetGateway,
        refreshTelemetry,
      }}
    >
      {children}
    </SentinelPulseContext.Provider>
  );
};

export const useSentinelPulse = (): SentinelPulseContextValue => {
  return useContext(SentinelPulseContext);
};

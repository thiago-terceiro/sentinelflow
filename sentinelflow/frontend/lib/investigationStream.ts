import type { InvestigationRun } from "./types";

export const STREAM_RECONNECT_DELAYS_MS = [1000, 2000, 5000] as const;

export const shouldReconnectInvestigation = (run: InvestigationRun, attemptCount = 0): boolean => {
  return (
    (run.status === "pending" || run.status === "running") &&
    attemptCount < STREAM_RECONNECT_DELAYS_MS.length
  );
};

export const streamReconnectDelayMs = (attemptCount: number): number => {
  const index = Math.min(attemptCount, STREAM_RECONNECT_DELAYS_MS.length - 1);
  return STREAM_RECONNECT_DELAYS_MS[index];
};

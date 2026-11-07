import { listDisputes } from "./api.ts";
import type { DisputeSummary } from "./types.ts";

const DISPUTES_CACHE_TTL_MS = 60_000; // 60 seconds TTL

let cachedDisputes: DisputeSummary[] | null = null;
let lastFetchedAt = 0;
let inFlightPromise: Promise<DisputeSummary[]> | null = null;

export const isDisputesCacheValid = (): boolean => {
  return cachedDisputes !== null && Date.now() - lastFetchedAt < DISPUTES_CACHE_TTL_MS;
};

export const peekDisputesCache = (): DisputeSummary[] | null => {
  if (isDisputesCacheValid()) {
    return cachedDisputes;
  }
  return null;
};

export const getDisputesCached = async (options?: { forceRefresh?: boolean }): Promise<DisputeSummary[]> => {
  const force = options?.forceRefresh ?? false;

  if (!force && isDisputesCacheValid() && cachedDisputes) {
    return cachedDisputes;
  }

  if (inFlightPromise) {
    return inFlightPromise;
  }

  inFlightPromise = (async () => {
    try {
      const data = await listDisputes();
      cachedDisputes = data;
      lastFetchedAt = Date.now();
      return data;
    } finally {
      inFlightPromise = null;
    }
  })();

  return inFlightPromise;
};

export const invalidateDisputesCache = (): void => {
  cachedDisputes = null;
  lastFetchedAt = 0;
  if (typeof window !== "undefined") {
    try {
      window.dispatchEvent(new CustomEvent("sentinelflow:disputes-invalidated"));
    } catch {
      // ignore
    }
  }
};

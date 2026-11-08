import { listDisputes } from "./api.ts";
import type { DisputeSummary } from "./types.ts";

const DISPUTES_CACHE_TTL_MS = 60_000; // 60 seconds TTL
const SESSION_CACHE_KEY = "sentinelflow_cached_disputes";
const SESSION_TIMESTAMP_KEY = "sentinelflow_cached_disputes_time";

let memoryCachedDisputes: DisputeSummary[] | null = null;
let memoryLastFetchedAt = 0;
let inFlightPromise: Promise<DisputeSummary[]> | null = null;

const readStorageCache = (): { disputes: DisputeSummary[]; fetchedAt: number } | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = sessionStorage.getItem(SESSION_CACHE_KEY);
    const timeStr = sessionStorage.getItem(SESSION_TIMESTAMP_KEY);
    if (!raw || !timeStr) {
      return null;
    }
    const fetchedAt = Number(timeStr);
    if (Number.isNaN(fetchedAt) || Date.now() - fetchedAt > DISPUTES_CACHE_TTL_MS) {
      return null;
    }
    const disputes = JSON.parse(raw) as DisputeSummary[];
    return { disputes, fetchedAt };
  } catch {
    return null;
  }
};

const writeStorageCache = (disputes: DisputeSummary[] | null, fetchedAt = Date.now()): void => {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (disputes === null) {
      sessionStorage.removeItem(SESSION_CACHE_KEY);
      sessionStorage.removeItem(SESSION_TIMESTAMP_KEY);
    } else {
      sessionStorage.setItem(SESSION_CACHE_KEY, JSON.stringify(disputes));
      sessionStorage.setItem(SESSION_TIMESTAMP_KEY, String(fetchedAt));
    }
  } catch {
    // sessionStorage access may be restricted
  }
};

export const isDisputesCacheValid = (): boolean => {
  if (memoryCachedDisputes !== null && Date.now() - memoryLastFetchedAt < DISPUTES_CACHE_TTL_MS) {
    return true;
  }
  const storage = readStorageCache();
  if (storage !== null) {
    memoryCachedDisputes = storage.disputes;
    memoryLastFetchedAt = storage.fetchedAt;
    return true;
  }
  return false;
};

export const peekDisputesCache = (): DisputeSummary[] | null => {
  if (isDisputesCacheValid()) {
    return memoryCachedDisputes;
  }
  return null;
};

export const getDisputesCached = async (options?: { forceRefresh?: boolean }): Promise<DisputeSummary[]> => {
  const force = options?.forceRefresh ?? false;

  if (!force) {
    const cached = peekDisputesCache();
    if (cached !== null) {
      return cached;
    }
  }

  if (inFlightPromise) {
    return inFlightPromise;
  }

  inFlightPromise = (async () => {
    try {
      const data = await listDisputes();
      memoryCachedDisputes = data;
      memoryLastFetchedAt = Date.now();
      writeStorageCache(data, memoryLastFetchedAt);
      return data;
    } finally {
      inFlightPromise = null;
    }
  })();

  return inFlightPromise;
};

export const invalidateDisputesCache = (): void => {
  memoryCachedDisputes = null;
  memoryLastFetchedAt = 0;
  writeStorageCache(null, 0);
  if (typeof window !== "undefined") {
    try {
      window.dispatchEvent(new CustomEvent("sentinelflow:disputes-invalidated"));
    } catch {
      // ignore
    }
  }
};

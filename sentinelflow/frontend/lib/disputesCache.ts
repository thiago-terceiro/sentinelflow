import { listDisputes } from "./api.ts";
import type { DisputeSummary } from "./types.ts";

const DISPUTES_CACHE_TTL_MS = 60_000; // 60 seconds TTL

type CacheEntry = {
  disputes: DisputeSummary[];
  fetchedAt: number;
};

declare global {
  interface Window {
    __sentinelflow_disputes_cache__?: CacheEntry;
  }
}

let memoryFallbackCache: CacheEntry | null = null;
let inFlightPromise: Promise<DisputeSummary[]> | null = null;

const getCacheEntry = (): CacheEntry | null => {
  const entry = typeof window !== "undefined"
    ? window.__sentinelflow_disputes_cache__ ?? null
    : memoryFallbackCache;

  if (!entry) {
    return null;
  }

  if (Date.now() - entry.fetchedAt > DISPUTES_CACHE_TTL_MS) {
    if (typeof window !== "undefined") {
      delete window.__sentinelflow_disputes_cache__;
    } else {
      memoryFallbackCache = null;
    }
    return null;
  }

  return entry;
};

const setCacheEntry = (disputes: DisputeSummary[] | null): void => {
  if (typeof window !== "undefined") {
    if (disputes === null) {
      delete window.__sentinelflow_disputes_cache__;
    } else {
      window.__sentinelflow_disputes_cache__ = {
        disputes,
        fetchedAt: Date.now(),
      };
    }
  } else {
    memoryFallbackCache = disputes ? { disputes, fetchedAt: Date.now() } : null;
  }
};

export const isDisputesCacheValid = (): boolean => {
  return getCacheEntry() !== null;
};

export const peekDisputesCache = (): DisputeSummary[] | null => {
  const entry = getCacheEntry();
  return entry ? entry.disputes : null;
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
      setCacheEntry(data);
      return data;
    } finally {
      inFlightPromise = null;
    }
  })();

  return inFlightPromise;
};

export const invalidateDisputesCache = (): void => {
  setCacheEntry(null);
  if (typeof window !== "undefined") {
    try {
      window.dispatchEvent(new CustomEvent("sentinelflow:disputes-invalidated"));
    } catch {
      // ignore
    }
  }
};

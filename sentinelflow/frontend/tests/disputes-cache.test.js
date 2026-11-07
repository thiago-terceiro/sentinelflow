import assert from "node:assert/strict";
import test from "node:test";

import {
  getDisputesCached,
  invalidateDisputesCache,
  isDisputesCacheValid,
  peekDisputesCache,
} from "../lib/disputesCache.ts";

test("disputesCache caches results and supports invalidation & forceRefresh", async () => {
  const originalFetch = globalThis.fetch;
  let fetchCount = 0;

  const sampleDisputes = [
    {
      id: "disp_101",
      case_code: "CASE-101",
      title: "Test Dispute 101",
      amount: 150.0,
      currency: "USD",
      status: "OPEN",
    },
  ];

  globalThis.fetch = async () => {
    fetchCount += 1;
    return new Response(JSON.stringify(sampleDisputes), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    // 1. Initial state is empty
    invalidateDisputesCache();
    assert.equal(isDisputesCacheValid(), false);
    assert.equal(peekDisputesCache(), null);

    // 2. First fetch fetches from network
    const firstResult = await getDisputesCached();
    assert.equal(fetchCount, 1);
    assert.equal(firstResult.length, 1);
    assert.equal(firstResult[0].id, "disp_101");

    // 3. Cache is now valid
    assert.equal(isDisputesCacheValid(), true);
    assert.equal(peekDisputesCache()?.length, 1);

    // 4. Repeated call uses cache without network fetch
    const secondResult = await getDisputesCached();
    assert.equal(fetchCount, 1);
    assert.equal(secondResult.length, 1);

    // 5. forceRefresh bypasses cache
    const forcedResult = await getDisputesCached({ forceRefresh: true });
    assert.equal(fetchCount, 2);
    assert.equal(forcedResult.length, 1);

    // 6. Invalidation clears cache
    invalidateDisputesCache();
    assert.equal(isDisputesCacheValid(), false);
    assert.equal(peekDisputesCache(), null);

    // 7. Subsequent fetch triggers network request
    const afterInvalidateResult = await getDisputesCached();
    assert.equal(fetchCount, 3);
    assert.equal(afterInvalidateResult.length, 1);
  } finally {
    globalThis.fetch = originalFetch;
    invalidateDisputesCache();
  }
});

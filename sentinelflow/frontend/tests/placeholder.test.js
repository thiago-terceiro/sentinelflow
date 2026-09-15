import assert from "node:assert/strict";
import test from "node:test";

import {
    getInvestigation,
    listDisputes,
    resumeInvestigation,
    startInvestigation,
} from "../lib/api.ts";

test("listDisputes uses app proxy path", async () => {
  const originalFetch = globalThis.fetch;
  let capturedUrl = "";
  let capturedAuthorization = "";

  globalThis.fetch = async (url, init) => {
    capturedUrl = String(url);
    capturedAuthorization = (init?.headers instanceof Headers)
      ? init.headers.get("Authorization") ?? ""
      : "";
    return new Response("[]", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const disputes = await listDisputes();

    assert.deepEqual(disputes, []);
    assert.equal(capturedUrl, "/app-api/disputes");
    assert.equal(capturedAuthorization, "");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("startInvestigation posts to the expected endpoint", async () => {
  const originalFetch = globalThis.fetch;
  let capturedMethod = "";

  globalThis.fetch = async (_url, init) => {
    capturedMethod = String(init?.method ?? "GET");
    return new Response(
      JSON.stringify({
        id: "inv_1",
        dispute_id: "disp_1",
        thread_id: "thread_1",
        status: "running",
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
        budget: {
          max_iterations: 1,
          max_tool_calls: 1,
          max_analyzer_calls: 1,
          max_tokens: 1,
          max_seconds: 1,
        },
        risk_assessment: null,
        compliance_findings: [],
        report: null,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  };

  try {
    const run = await startInvestigation("disp_1");

    assert.equal(capturedMethod, "POST");
    assert.equal(run.id, "inv_1");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("resumeInvestigation sends decision payload", async () => {
  const originalFetch = globalThis.fetch;
  let capturedBody = "";

  globalThis.fetch = async (_url, init) => {
    capturedBody = String(init?.body ?? "");
    return new Response(
      JSON.stringify({
        id: "inv_1",
        dispute_id: "disp_1",
        thread_id: "thread_1",
        status: "running",
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-01T00:00:00Z",
        budget: {
          max_iterations: 1,
          max_tool_calls: 1,
          max_analyzer_calls: 1,
          max_tokens: 1,
          max_seconds: 1,
        },
        risk_assessment: null,
        compliance_findings: [],
        report: null,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  };

  try {
    await resumeInvestigation("inv_1", "deny", "Need additional evidence");

    assert.deepEqual(JSON.parse(capturedBody), {
      decision: "deny",
      comment: "Need additional evidence",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("getInvestigation surfaces API error message", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => new Response(
    JSON.stringify({ error: { message: "Forbidden" } }),
    {
      status: 403,
      headers: { "Content-Type": "application/json" },
    },
  );

  try {
    await assert.rejects(() => getInvestigation("inv_missing"), /Forbidden/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

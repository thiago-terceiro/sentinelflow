import assert from "node:assert/strict";
import test from "node:test";

import { investigationStreamEndpoint } from "../lib/api.ts";
import {
    shouldReconnectInvestigation,
    STREAM_RECONNECT_DELAYS_MS,
    streamReconnectDelayMs,
} from "../lib/investigationStream.ts";
import { openInvestigationStream } from "../lib/sse.ts";

const encoder = new TextEncoder();

const buildEventResponse = (chunks) => new Response(
    new ReadableStream({
        start(controller) {
            for (const chunk of chunks) {
                controller.enqueue(encoder.encode(chunk));
            }
            controller.close();
        },
    }),
    {
        status: 200,
        headers: {
            "Content-Type": "text/event-stream",
        },
    },
);

test("investigationStreamEndpoint does not place auth in the query string", () => {
    const originalWindow = globalThis.window;

    globalThis.window = {
        location: {
            origin: "https://console.example.com",
        },
    };

    try {
        const url = investigationStreamEndpoint("inv_123");

        assert.equal(url, "https://console.example.com/app-api/investigations/inv_123/stream");
        assert.equal(url.includes("token="), false);
    } finally {
        globalThis.window = originalWindow;
    }
});

test("shouldReconnectInvestigation only reconnects active runs", () => {
    const baseRun = {
        id: "inv_123",
        dispute_id: "disp_123",
        thread_id: "thread_123",
        created_at: "2026-08-26T00:00:00Z",
        updated_at: "2026-08-26T00:00:00Z",
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
    };

    assert.equal(shouldReconnectInvestigation({ ...baseRun, status: "pending" }, 0), true);
    assert.equal(shouldReconnectInvestigation({ ...baseRun, status: "running" }, 1), true);
    assert.equal(shouldReconnectInvestigation({ ...baseRun, status: "running" }, STREAM_RECONNECT_DELAYS_MS.length), false);
    assert.equal(shouldReconnectInvestigation({ ...baseRun, status: "awaiting_approval" }), false);
    assert.equal(shouldReconnectInvestigation({ ...baseRun, status: "completed" }), false);
    assert.equal(shouldReconnectInvestigation({ ...baseRun, status: "failed" }), false);
});

test("streamReconnectDelayMs applies bounded backoff", () => {
    assert.equal(streamReconnectDelayMs(0), 1000);
    assert.equal(streamReconnectDelayMs(1), 2000);
    assert.equal(streamReconnectDelayMs(2), 5000);
    assert.equal(streamReconnectDelayMs(10), 5000);
});

test("openInvestigationStream parses events split across chunks", async () => {
    const originalFetch = globalThis.fetch;
    const events = [];
    const errors = [];
    let authorizationHeader = null;

    globalThis.fetch = async (_, init) => {
        authorizationHeader = init?.headers?.Authorization ?? init?.headers?.get?.("Authorization") ?? null;
        return buildEventResponse([
            "data: {\"id\":\"evt_1\",\"type\":\"run_started\",",
            "\"timestamp\":\"2026-08-26T00:00:00Z\",\"data\":{}}\n\n",
        ]);
    };

    try {
        await new Promise((resolve, reject) => {
            openInvestigationStream(
                "http://example.test/stream",
                (event) => {
                    events.push(event.type);
                },
                (message) => {
                    errors.push(message);
                    reject(new Error(message));
                },
                () => {
                    resolve();
                },
            );
        });
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.deepEqual(events, ["run_started"]);
    assert.deepEqual(errors, []);
    assert.equal(authorizationHeader, null);
});

test("openInvestigationStream notifies caller when the stream closes", async () => {
    const originalFetch = globalThis.fetch;
    const events = [];
    const errors = [];
    let closed = false;

    globalThis.fetch = async () => buildEventResponse([]);

    try {
        await new Promise((resolve, reject) => {
            openInvestigationStream(
                "http://example.test/stream",
                (event) => {
                    events.push(event.type);
                },
                (message) => {
                    errors.push(message);
                    reject(new Error(message));
                },
                () => {
                    closed = true;
                    resolve();
                },
            );
        });
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(closed, true);
    assert.deepEqual(events, []);
    assert.deepEqual(errors, []);
});

test("openInvestigationStream does not report remote close when caller closes it", async () => {
    const originalFetch = globalThis.fetch;
    const events = [];
    const errors = [];
    let closed = false;

    globalThis.fetch = async () => new Response(
        new ReadableStream({
            start() {},
        }),
        {
            status: 200,
            headers: {
                "Content-Type": "text/event-stream",
            },
        },
    );

    try {
        await new Promise((resolve, reject) => {
            const stream = openInvestigationStream(
                "http://example.test/stream",
                (event) => {
                    events.push(event.type);
                },
                (message) => {
                    errors.push(message);
                    reject(new Error(message));
                },
                () => {
                    closed = true;
                },
            );

            queueMicrotask(() => {
                stream.close();
                queueMicrotask(resolve);
            });
        });
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(closed, false);
    assert.deepEqual(events, []);
    assert.deepEqual(errors, []);
});

test("openInvestigationStream reports non-success responses as errors", async () => {
    const originalFetch = globalThis.fetch;
    const events = [];
    const errors = [];

    globalThis.fetch = async () => new Response(null, { status: 503 });

    try {
        await new Promise((resolve) => {
            openInvestigationStream(
                "http://example.test/stream",
                (event) => {
                    events.push(event.type);
                },
                (message) => {
                    errors.push(message);
                    resolve();
                },
                () => {
                    resolve();
                },
            );
        });
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.deepEqual(events, []);
    assert.deepEqual(errors, ["Stream request failed with status 503."]);
});
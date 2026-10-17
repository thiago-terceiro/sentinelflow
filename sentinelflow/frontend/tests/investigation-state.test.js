import assert from "node:assert/strict";
import test from "node:test";

import {
  applyRunToConsoleState,
  applyStreamEventToConsoleState,
  initialConsoleState,
} from "../lib/investigationState.ts";

const runBase = {
  id: "inv_123",
  dispute_id: "disp_123",
  thread_id: "thread_123",
  created_at: "2026-09-03T00:00:00Z",
  updated_at: "2026-09-03T00:00:00Z",
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

test("applyRunToConsoleState sets disconnected for active runs and idle for terminal runs", () => {
  const running = applyRunToConsoleState(initialConsoleState, { ...runBase, status: "running" });
  const completed = applyRunToConsoleState(running, {
    ...runBase,
    status: "completed",
    report: {
      conclusion: "done",
      recommendation: "approve",
      confidence: 0.9,
      hypotheses: [],
      risk_factors: [],
      evidence_ids: [],
      unresolved_questions: [],
      compliance_findings: [],
    },
  });

  assert.equal(running.status, "RUNNING");
  assert.equal(running.streamConnection, "disconnected");
  assert.equal(completed.status, "COMPLETED");
  assert.equal(completed.streamConnection, "idle");
});

test("applyStreamEventToConsoleState sets approval required state", () => {
  const started = applyRunToConsoleState(initialConsoleState, { ...runBase, status: "running" });
  const next = applyStreamEventToConsoleState(started, {
    id: "evt_approval",
    type: "approval_required",
    timestamp: "2026-09-03T00:00:01Z",
    data: {
      report: {
        conclusion: "needs reviewer",
        recommendation: "escalate",
        confidence: 0.7,
        hypotheses: [],
        risk_factors: [],
        evidence_ids: [],
        unresolved_questions: [],
        compliance_findings: [],
      },
    },
  });

  assert.equal(next.status, "APPROVAL_REQUIRED");
  assert.equal(next.requiresApproval, true);
  assert.equal(next.isStreaming, false);
  assert.equal(next.streamConnection, "idle");
});

test("applyStreamEventToConsoleState deduplicates evidence events by id", () => {
  const started = applyRunToConsoleState(initialConsoleState, { ...runBase, status: "running" });
  const evidenceEvent = {
    id: "evt_evidence_1",
    type: "evidence_added",
    timestamp: "2026-09-03T00:00:02Z",
    data: {
      id: "ev_1",
      source: "transaction",
      category: "transaction",
      origin: "observed_fact",
      summary: "test evidence",
      facts: {},
      confidence: 0.9,
      collected_at: "2026-09-03T00:00:02Z",
      provenance: "test",
    },
  };

  const once = applyStreamEventToConsoleState(started, evidenceEvent);
  const twice = applyStreamEventToConsoleState(once, evidenceEvent);

  assert.equal(once.evidence.length, 1);
  assert.equal(twice.evidence.length, 1);
});

test("applyStreamEventToConsoleState marks run failures as terminal", () => {
  const started = applyRunToConsoleState(initialConsoleState, { ...runBase, status: "running" });
  const failed = applyStreamEventToConsoleState(started, {
    id: "evt_failed",
    type: "run_failed",
    timestamp: "2026-09-03T00:00:03Z",
    data: {
      message: "Investigation crashed",
    },
  });

  assert.equal(failed.status, "FAILED");
  assert.equal(failed.streamConnection, "idle");
  assert.equal(failed.isStreaming, false);
  assert.equal(failed.error, "Investigation crashed");
});

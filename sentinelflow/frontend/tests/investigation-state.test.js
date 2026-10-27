import assert from "node:assert/strict";
import test from "node:test";

import {
  applyRunToConsoleState,
  applyStreamEventToConsoleState,
  computeIterationDiff,
  deriveConsoleStateAtStep,
  extractIterationSnapshots,
  initialConsoleState,
  mergeUniqueEvents,
  resolveActiveEvidenceId,
  togglePinnedEvidenceId,
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
  evidence: [],
  analyzer_summaries: [],
  hypotheses: [],
  timeline_events: [],
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

test("applyRunToConsoleState cold-hydrates timeline, evidence, analyzers, and hypotheses on F5 refresh", () => {
  const coldHydrated = applyRunToConsoleState(initialConsoleState, {
    ...runBase,
    status: "completed",
    evidence: [
      {
        id: "ev_cold_1",
        source: "transactions",
        category: "transaction",
        origin: "observed_fact",
        summary: "Cold hydrated evidence",
        facts: { amount: 250 },
        confidence: 0.94,
        collected_at: "2026-09-03T00:00:02Z",
        provenance: "postgres",
      },
    ],
    analyzer_summaries: [
      {
        analyzer: "fraud_pattern",
        origin: "analyzer_interpretation",
        summary: "Cold hydrated analyzer",
        findings: ["Velocity spike"],
        confidence: 0.88,
        evidence_ids: ["ev_cold_1"],
        contradictions: [],
        recommended_followups: [],
      },
    ],
    hypotheses: [
      {
        statement: "Cold hydrated hypothesis",
        confidence: 0.81,
        supporting_evidence_ids: ["ev_cold_1"],
        contradicting_evidence_ids: [],
      },
    ],
    timeline_events: [
      {
        id: "evt_cold_1",
        type: "run_started",
        timestamp: "2026-09-03T00:00:01Z",
        data: { investigation_id: "inv_123" },
      },
      {
        id: "evt_cold_2",
        type: "hypothesis_updated",
        timestamp: "2026-09-03T00:00:03Z",
        data: { iteration: 1 },
      },
    ],
  });

  assert.equal(coldHydrated.evidence.length, 1);
  assert.equal(coldHydrated.evidence[0].id, "ev_cold_1");
  assert.equal(coldHydrated.analyzerSummaries.length, 1);
  assert.equal(coldHydrated.analyzerSummaries[0].analyzer, "fraud_pattern");
  assert.equal(coldHydrated.hypotheses.length, 1);
  assert.equal(coldHydrated.hypotheses[0].statement, "Cold hydrated hypothesis");
  assert.equal(coldHydrated.timeline.length, 2);
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

test("deriveConsoleStateAtStep deterministically reconstructs historical state without leaking final baseRun fields", () => {
  const events = [
    {
      id: "evt_0",
      type: "agent_message",
      timestamp: "2026-09-03T00:00:01Z",
      data: { stage: "collect", message: "Starting evidence collection" },
    },
    {
      id: "evt_1",
      type: "evidence_added",
      timestamp: "2026-09-03T00:00:02Z",
      data: {
        id: "ev_tx_1",
        source: "transactions",
        category: "transaction",
        origin: "observed_fact",
        summary: "High velocity charge",
        facts: {},
        confidence: 0.95,
        collected_at: "2026-09-03T00:00:02Z",
        provenance: "ledger",
      },
    },
    {
      id: "evt_2",
      type: "hypothesis_updated",
      timestamp: "2026-09-03T00:00:03Z",
      data: {
        iteration: 1,
        hypotheses: [
          {
            statement: "Card compromised via POS malware",
            confidence: 0.72,
            supporting_evidence_ids: ["ev_tx_1"],
            contradicting_evidence_ids: [],
          },
        ],
        thought_process: "Investigating velocity anomaly.",
        reasoning_steps: ["Step 1: Analyzed transactions."],
      },
    },
    {
      id: "evt_3",
      type: "risk_updated",
      timestamp: "2026-09-03T00:00:04Z",
      data: {
        score: 0.85,
        level: "high",
        explanation: "Critical fraud risk detected.",
        factors: [{ name: "velocity", score: 0.9 }],
      },
    },
  ];

  const completedBaseRun = {
    ...runBase,
    status: "completed",
    risk_assessment: {
      score: 0.85,
      level: "high",
      explanation: "Final risk",
      factors: [],
    },
    report: {
      conclusion: "Final conclusion",
      recommendation: "approve",
      confidence: 0.95,
      hypotheses: [],
      risk_factors: [],
      evidence_ids: ["ev_tx_1"],
      unresolved_questions: [],
      compliance_findings: [],
    },
  };

  // At step 0: even when baseRun is completed, Step 0 MUST NOT leak final report or riskAssessment
  const stateStep0 = deriveConsoleStateAtStep(events, completedBaseRun, 0);
  assert.equal(stateStep0.status, "RUNNING");
  assert.equal(stateStep0.evidence.length, 0);
  assert.equal(stateStep0.hypotheses.length, 0);
  assert.equal(stateStep0.riskAssessment, null);
  assert.equal(stateStep0.report, null);
  assert.equal(stateStep0.timeline.length, 1);

  // At step 1: evidence added, but no hypothesis yet
  const stateStep1 = deriveConsoleStateAtStep(events, completedBaseRun, 1);
  assert.equal(stateStep1.evidence.length, 1);
  assert.equal(stateStep1.evidence[0].id, "ev_tx_1");
  assert.equal(stateStep1.hypotheses.length, 0);
  assert.equal(stateStep1.riskAssessment, null);
  assert.equal(stateStep1.report, null);
  assert.equal(stateStep1.timeline.length, 2);

  // At step 2: hypothesis formulated
  const stateStep2 = deriveConsoleStateAtStep(events, completedBaseRun, 2);
  assert.equal(stateStep2.evidence.length, 1);
  assert.equal(stateStep2.hypotheses.length, 1);
  assert.equal(stateStep2.hypotheses[0].statement, "Card compromised via POS malware");
  assert.equal(stateStep2.riskAssessment, null);
  assert.equal(stateStep2.timeline.length, 3);

  // At step 3: risk updated
  const stateStep3 = deriveConsoleStateAtStep(events, completedBaseRun, 3);
  assert.equal(stateStep3.evidence.length, 1);
  assert.equal(stateStep3.hypotheses.length, 1);
  assert.notEqual(stateStep3.riskAssessment, null);
  assert.equal(stateStep3.riskAssessment?.score, 0.85);
  assert.equal(stateStep3.timeline.length, 4);

  // Live head (selectedEventIndex = null) includes final baseRun state
  const stateLive = deriveConsoleStateAtStep(events, completedBaseRun, null);
  assert.equal(stateLive.status, "COMPLETED");
  assert.equal(stateLive.evidence.length, 1);
  assert.equal(stateLive.riskAssessment?.score, 0.85);
  assert.equal(stateLive.report?.conclusion, "Final conclusion");

  // Benchmarking performance: 100 historical state derivations must execute in < 20ms
  const start = performance.now();
  for (let i = 0; i < 100; i += 1) {
    deriveConsoleStateAtStep(events, completedBaseRun, 2);
  }
  const duration = performance.now() - start;
  assert.ok(duration < 20, `Expected <20ms for 100 derivations, took ${duration.toFixed(2)}ms`);
});

test("resolveActiveEvidenceId and togglePinnedEvidenceId keep click-pinned citations sticky across mouse leave", () => {
  let pinned = null;
  let hovered = null;

  // Hover preview without pin
  hovered = "ev_hover_1";
  assert.equal(resolveActiveEvidenceId(pinned, hovered), "ev_hover_1");

  // Mouse leave clears hover when unpinned
  hovered = null;
  assert.equal(resolveActiveEvidenceId(pinned, hovered), null);

  // Click pins citation; mouse leave does NOT clear pinned citation
  pinned = togglePinnedEvidenceId(pinned, "ev_pin_1");
  hovered = "ev_pin_1";
  assert.equal(resolveActiveEvidenceId(pinned, hovered), "ev_pin_1");

  hovered = null;
  assert.equal(resolveActiveEvidenceId(pinned, hovered), "ev_pin_1");

  // Hovering a different badge previews it temporarily while keeping pin intact
  hovered = "ev_hover_2";
  assert.equal(resolveActiveEvidenceId(pinned, hovered), "ev_hover_2");
  hovered = null;
  assert.equal(resolveActiveEvidenceId(pinned, hovered), "ev_pin_1");

  // Clicking the pinned citation again unpins it
  pinned = togglePinnedEvidenceId(pinned, "ev_pin_1");
  assert.equal(resolveActiveEvidenceId(pinned, hovered), null);
});

test("mergeUniqueEvents deduplicates events and strips transient streaming deltas", () => {
  const existing = [
    { id: "evt_1", type: "run_started", timestamp: "2026-09-03T00:00:01Z", data: {} },
  ];
  const incoming = [
    { id: "evt_1", type: "run_started", timestamp: "2026-09-03T00:00:01Z", data: {} },
    { id: "delta_1", type: "reasoning_delta", timestamp: "2026-09-03T00:00:02Z", data: { delta: "thinking..." } },
    { id: "evt_2", type: "hypothesis_updated", timestamp: "2026-09-03T00:00:03Z", data: { iteration: 1 } },
  ];

  const merged = mergeUniqueEvents(existing, incoming);
  assert.equal(merged.length, 2);
  assert.equal(merged[0].id, "evt_1");
  assert.equal(merged[1].id, "evt_2");

  // Verify live state handles reasoning_delta transiently and clears on hypothesis_updated
  const withDelta = applyStreamEventToConsoleState(initialConsoleState, incoming[1]);
  assert.equal(withDelta.streamingReasoningDelta, "thinking...");
  assert.equal(withDelta.timeline.length, 0);

  const afterHypothesis = applyStreamEventToConsoleState(withDelta, incoming[2]);
  assert.equal(afterHypothesis.streamingReasoningDelta, null);
  assert.equal(afterHypothesis.timeline.length, 1);

  // Verify run_failed, approval_required, and run_completed also clear stuck streamingReasoningDelta
  const failedFromDelta = applyStreamEventToConsoleState(withDelta, {
    id: "evt_fail_delta",
    type: "run_failed",
    timestamp: "2026-09-03T00:00:04Z",
    data: { message: "Node failed" },
  });
  assert.equal(failedFromDelta.streamingReasoningDelta, null);

  const approvalFromDelta = applyStreamEventToConsoleState(withDelta, {
    id: "evt_approval_delta",
    type: "approval_required",
    timestamp: "2026-09-03T00:00:04Z",
    data: { report: null },
  });
  assert.equal(approvalFromDelta.streamingReasoningDelta, null);

  const completedFromDelta = applyStreamEventToConsoleState(withDelta, {
    id: "evt_completed_delta",
    type: "run_completed",
    timestamp: "2026-09-03T00:00:04Z",
    data: { report: null },
  });
  assert.equal(completedFromDelta.streamingReasoningDelta, null);
});

test("extractIterationSnapshots and computeIterationDiff track state mutations and attribution", () => {
  const events = [
    {
      id: "evt_h1",
      type: "hypothesis_updated",
      timestamp: "2026-09-03T00:00:01Z",
      data: {
        iteration: 1,
        hypotheses: [
          { statement: "Friendly fraud by family member", confidence: 0.6, supporting_evidence_ids: [], contradicting_evidence_ids: [] },
          { statement: "Merchant billing error", confidence: 0.4, supporting_evidence_ids: [], contradicting_evidence_ids: [] },
        ],
        unresolved_questions: ["Has cardholder used device before?"],
      },
    },
    {
      id: "evt_r1",
      type: "risk_updated",
      timestamp: "2026-09-03T00:00:02Z",
      data: { score: 0.45, level: "medium", explanation: "Moderate risk", factors: [] },
    },
    {
      id: "evt_guidance",
      type: "agent_message",
      timestamp: "2026-09-03T00:00:03Z",
      data: { guidance: "Reviewer steering: Disregard family member, IP belongs to VPN proxy datacenter" },
    },
    {
      id: "evt_h2",
      type: "hypothesis_updated",
      timestamp: "2026-09-03T00:00:04Z",
      data: {
        iteration: 2,
        hypotheses: [
          { statement: "Friendly fraud by family member", confidence: 0.15, supporting_evidence_ids: [], contradicting_evidence_ids: [] },
          { statement: "Automated credential stuffing via proxy", confidence: 0.92, supporting_evidence_ids: [], contradicting_evidence_ids: [] },
        ],
        unresolved_questions: [],
      },
    },
    {
      id: "evt_r2",
      type: "risk_updated",
      timestamp: "2026-09-03T00:00:05Z",
      data: { score: 0.88, level: "high", explanation: "Confirmed high-confidence proxy compromise", factors: [] },
    },
  ];

  const snapshots = extractIterationSnapshots(events);
  assert.equal(snapshots.length, 2);

  // Iteration 1 attribution is AI Investigator
  assert.equal(snapshots[0].iteration, 1);
  assert.equal(snapshots[0].source, "AI Investigator");

  // Iteration 2 attribution is Human Reviewer Steering (consumed guidance)
  assert.equal(snapshots[1].iteration, 2);
  assert.equal(snapshots[1].source, "Human Reviewer Steering");

  // Compute diff between Iteration 1 and 2
  const diff = computeIterationDiff(snapshots[0], snapshots[1]);

  assert.equal(diff.fromIteration, 1);
  assert.equal(diff.toIteration, 2);
  assert.equal(diff.source, "Human Reviewer Steering");

  // Added hypothesis: "Automated credential stuffing via proxy"
  assert.equal(diff.addedHypotheses.length, 1);
  assert.equal(diff.addedHypotheses[0].statement, "Automated credential stuffing via proxy");

  // Resolved hypothesis: "Merchant billing error"
  assert.equal(diff.resolvedHypotheses.length, 1);
  assert.equal(diff.resolvedHypotheses[0].statement, "Merchant billing error");

  // Confidence delta for "Friendly fraud by family member": 0.60 -> 0.15 (-0.45)
  assert.equal(diff.confidenceChanges.length, 1);
  assert.equal(diff.confidenceChanges[0].statement, "Friendly fraud by family member");
  assert.equal(diff.confidenceChanges[0].delta, -0.45);

  // Questions resolved
  assert.equal(diff.resolvedQuestions.length, 1);
  assert.equal(diff.resolvedQuestions[0], "Has cardholder used device before?");

  // Risk delta
  assert.notEqual(diff.riskDelta, null);
  assert.equal(diff.riskDelta?.previousScore, 0.45);
  assert.equal(diff.riskDelta?.currentScore, 0.88);
  assert.equal(diff.riskDelta?.scoreDelta, 0.43);
  assert.equal(diff.riskDelta?.previousLevel, "medium");
  assert.equal(diff.riskDelta?.currentLevel, "high");
});

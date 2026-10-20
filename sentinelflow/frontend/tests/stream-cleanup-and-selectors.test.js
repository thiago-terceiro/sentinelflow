import assert from "node:assert/strict";
import test from "node:test";

import {
  applyStreamEventToConsoleState,
  createInvestigationStore,
  initialConsoleState,
  selectAnalyzers,
  selectEvidence,
  selectHypotheses,
  selectRisk,
  selectTimeline,
} from "../lib/investigationState.ts";

test("selector isolation: timeline updates do not mutate or invalidate other state slices", () => {
  const baseState = {
    ...initialConsoleState,
    investigationId: "inv_isolation_test",
    evidence: [
      {
        id: "ev_1",
        source: "transaction",
        category: "transaction",
        origin: "observed_fact",
        summary: "Original transaction evidence",
        facts: {},
        confidence: 0.95,
        collected_at: "2026-09-03T00:00:00Z",
        provenance: "test",
      },
    ],
    riskAssessment: {
      score: 0.42,
      level: "medium",
      explanation: "Moderate anomaly detected",
      factors: [{ name: "amount", score: 0.5 }],
    },
    analyzerSummaries: [
      {
        analyzer: "geolocation",
        summary: "IP matches billing state",
        confidence: 0.9,
        contradictions: [],
        findings: ["Matches home address"],
      },
    ],
    hypotheses: [
      {
        statement: "Customer friendly fraud",
        confidence: 0.7,
        evidence_ids: ["ev_1"],
      },
    ],
  };

  const heartbeatEvent = {
    id: "evt_hb_1",
    type: "heartbeat",
    timestamp: "2026-09-03T00:00:05Z",
    data: {},
  };

  const nextState = applyStreamEventToConsoleState(baseState, heartbeatEvent);

  // Timeline must advance
  assert.notEqual(selectTimeline(baseState), selectTimeline(nextState));
  assert.equal(selectTimeline(nextState).length, 1);

  // All other slices must preserve identical object references (selector isolation)
  assert.equal(selectEvidence(baseState), selectEvidence(nextState));
  assert.equal(selectRisk(baseState), selectRisk(nextState));
  assert.equal(selectAnalyzers(baseState), selectAnalyzers(nextState));
  assert.equal(selectHypotheses(baseState), selectHypotheses(nextState));
});

test("selector isolation: evidence additions only update evidence slice", () => {
  const baseState = {
    ...initialConsoleState,
    investigationId: "inv_isolation_evidence",
    evidence: [],
    riskAssessment: {
      score: 0.1,
      level: "low",
      explanation: "No risk",
      factors: [],
    },
    analyzerSummaries: [
      {
        analyzer: "device",
        summary: "Known device",
        confidence: 0.99,
        contradictions: [],
        findings: [],
      },
    ],
  };

  const evidenceEvent = {
    id: "evt_ev_add_1",
    type: "evidence_added",
    timestamp: "2026-09-03T00:00:10Z",
    data: {
      id: "ev_2",
      source: "merchant",
      category: "merchant",
      origin: "observed_fact",
      summary: "Merchant dispute evidence",
      facts: {},
      confidence: 0.88,
      collected_at: "2026-09-03T00:00:10Z",
      provenance: "test",
    },
  };

  const nextState = applyStreamEventToConsoleState(baseState, evidenceEvent);

  // Evidence slice must update
  assert.notEqual(selectEvidence(baseState), selectEvidence(nextState));
  assert.equal(selectEvidence(nextState).length, 1);

  // Risk and analyzer slices must maintain strict reference equality
  assert.equal(selectRisk(baseState), selectRisk(nextState));
  assert.equal(selectAnalyzers(baseState), selectAnalyzers(nextState));
});

test("InvestigationStore: notifies subscribers and isolates state updates", () => {
  const store = createInvestigationStore(initialConsoleState);
  let listenerCalledCount = 0;

  const unsubscribe = store.subscribe(() => {
    listenerCalledCount += 1;
  });

  assert.equal(store.getState().status, "IDLE");

  store.setState((prev) => ({
    ...prev,
    status: "RUNNING",
    currentPhase: "collect",
  }));

  assert.equal(listenerCalledCount, 1);
  assert.equal(store.getState().status, "RUNNING");
  assert.equal(store.getState().currentPhase, "collect");

  // Unsubscribe stops notifications
  unsubscribe();
  store.setState((prev) => ({
    ...prev,
    status: "COMPLETED",
  }));

  assert.equal(listenerCalledCount, 1);
  assert.equal(store.getState().status, "COMPLETED");
});

test("stream cleanup simulation on disputeId change", () => {
  let streamClosed = false;
  let timerCleared = false;
  let timerId = 12345;

  const fakeStream = {
    close: () => {
      streamClosed = true;
    },
  };

  const clearTimer = (id) => {
    if (id === timerId) {
      timerCleared = true;
    }
  };

  // Simulate dispute change cleanup logic from useSentinelAgent
  const cleanupStreamOnDisputeChange = (currentStream, currentTimerId) => {
    clearTimer(currentTimerId);
    currentStream?.close();
  };

  cleanupStreamOnDisputeChange(fakeStream, timerId);

  assert.equal(streamClosed, true);
  assert.equal(timerCleared, true);
});

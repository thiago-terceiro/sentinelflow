import type {
  ConsoleState,
  HypothesisConfidenceChange,
  InvestigationHypothesis,
  InvestigationRun,
  IterationDiff,
  IterationSnapshot,
  StreamEvent,
} from "./types";

const mergeUniqueById = <T extends { id: string }>(items: T[], nextItem: T): T[] => {
  if (items.some((item) => item.id === nextItem.id)) {
    return items;
  }
  return [...items, nextItem];
};

const mergeUniqueByKey = <T>(items: T[], nextItem: T, key: (item: T) => string): T[] => {
  const nextKey = key(nextItem);
  if (items.some((item) => key(item) === nextKey)) {
    return items;
  }
  return [...items, nextItem];
};

const upsertToolLog = (
  toolLogs: ConsoleState["toolLogs"],
  nextLog: ConsoleState["toolLogs"][number]
) => {
  const existingIndex = toolLogs.findIndex((item) => item.callId === nextLog.callId);
  if (existingIndex === -1) {
    return [...toolLogs, nextLog];
  }
  const nextToolLogs = [...toolLogs];
  nextToolLogs[existingIndex] = { ...nextToolLogs[existingIndex], ...nextLog };
  return nextToolLogs;
};

const toolEventPayload = (data: Record<string, unknown>) => ({
  callId: String(data.tool_call_id ?? ""),
  label: String(data.label ?? data.tool_name ?? "Tool activity"),
});

const analyzerSummaryFromEvent = (data: Record<string, unknown>) => {
  const summary = { ...data };
  delete summary.analyzer_id;
  delete summary.analyzer_name;
  return summary as ConsoleState["analyzerSummaries"][number];
};

export const mapRunStatus = (status: InvestigationRun["status"]): ConsoleState["status"] => {
  if (status === "awaiting_approval") {
    return "APPROVAL_REQUIRED";
  }
  if (status === "completed") {
    return "COMPLETED";
  }
  if (status === "failed") {
    return "FAILED";
  }
  return "RUNNING";
};

const isTerminalState = (status: ConsoleState["status"]): boolean => {
  return status === "APPROVAL_REQUIRED" || status === "COMPLETED" || status === "FAILED";
};

export const initialConsoleState: ConsoleState = {
  investigationId: "",
  evidence: [],
  analyzerSummaries: [],
  hypotheses: [],
  riskAssessment: null,
  report: null,
  isReportUnlocked: false,
  timeline: [],
  agentStatus: null,
  toolLogs: [],
  status: "IDLE",
  requiresApproval: false,
  isStreaming: false,
  streamConnection: "idle",
  reconnectAttempt: 0,
  nextReconnectDelayMs: null,
  error: null,
  activeThoughtProcess: null,
  reasoningSteps: [],
  currentPhase: "intake",
  reviewerGuidance: null,
};

export const applyRunToConsoleState = (
  state: ConsoleState,
  run: InvestigationRun
): ConsoleState => {
  const isSameInvestigation = state.investigationId === run.id;
  const nextStatus = mapRunStatus(run.status);
  return {
    ...state,
    investigationId: run.id,
    evidence: isSameInvestigation ? state.evidence : [],
    analyzerSummaries: isSameInvestigation ? state.analyzerSummaries : [],
    hypotheses: run.report?.hypotheses ?? (isSameInvestigation ? state.hypotheses : []),
    riskAssessment: run.risk_assessment ?? null,
    report: run.report ?? null,
    isReportUnlocked: run.status === "awaiting_approval" || run.status === "completed",
    timeline: isSameInvestigation ? state.timeline : [],
    agentStatus: isSameInvestigation ? state.agentStatus : null,
    toolLogs: isSameInvestigation ? state.toolLogs : [],
    requiresApproval: run.status === "awaiting_approval",
    status: nextStatus,
    isStreaming: false,
    streamConnection: isTerminalState(nextStatus) ? "idle" : "disconnected",
    nextReconnectDelayMs: null,
    error: null,
  };
};

export const applyStreamEventToConsoleState = (
  state: ConsoleState,
  event: StreamEvent
): ConsoleState => {
  const nextTimeline = mergeUniqueById(state.timeline, event);
  if (event.type === "agent_message") {
    const stage =
      typeof event.data.stage === "string"
        ? (event.data.stage as ConsoleState["currentPhase"])
        : state.currentPhase;
    const guidance =
      typeof event.data.guidance === "string" ? event.data.guidance : state.reviewerGuidance;
    return {
      ...state,
      agentStatus: String(event.data.message ?? state.agentStatus ?? "Investigator thinking"),
      currentPhase: stage ?? state.currentPhase,
      reviewerGuidance: guidance ?? state.reviewerGuidance,
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "evidence_added") {
    const nextEvidence = event.data as ConsoleState["evidence"][number];
    return {
      ...state,
      evidence: mergeUniqueById(state.evidence, nextEvidence),
      currentPhase: "collect",
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "agent_status_updated") {
    return {
      ...state,
      agentStatus: String(event.data.message ?? "Working investigation"),
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "tool_started") {
    const payload = toolEventPayload(event.data);
    return {
      ...state,
      agentStatus: payload.label,
      currentPhase: "collect",
      toolLogs: upsertToolLog(state.toolLogs, { ...payload, status: "started" }),
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "tool_completed") {
    const payload = toolEventPayload(event.data);
    return {
      ...state,
      currentPhase: "collect",
      toolLogs: upsertToolLog(state.toolLogs, { ...payload, status: "completed" }),
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "analyzer_started") {
    return {
      ...state,
      agentStatus: String(event.data.label ?? event.data.analyzer_name ?? "Running analyzer"),
      currentPhase: "collect",
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "analyzer_completed") {
    const nextAnalyzer = analyzerSummaryFromEvent(event.data);
    return {
      ...state,
      currentPhase: "collect",
      analyzerSummaries: mergeUniqueByKey(
        state.analyzerSummaries,
        nextAnalyzer,
        (item) => item.analyzer
      ),
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "hypothesis_updated") {
    const thought =
      typeof event.data.thought_process === "string"
        ? event.data.thought_process
        : state.activeThoughtProcess;
    const steps = Array.isArray(event.data.reasoning_steps)
      ? (event.data.reasoning_steps as string[])
      : state.reasoningSteps;
    return {
      ...state,
      hypotheses: (event.data.hypotheses as ConsoleState["hypotheses"]) ?? state.hypotheses,
      activeThoughtProcess: thought,
      reasoningSteps: steps,
      currentPhase: "investigate",
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "risk_updated") {
    return {
      ...state,
      riskAssessment: event.data as ConsoleState["riskAssessment"],
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "final_report_ready") {
    return {
      ...state,
      agentStatus: "Drafted final recommendation",
      currentPhase: "synthesize",
      report: event.data as ConsoleState["report"],
      isReportUnlocked: false,
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "approval_required") {
    return {
      ...state,
      agentStatus: "Awaiting reviewer approval",
      currentPhase: "approval",
      requiresApproval: true,
      status: "APPROVAL_REQUIRED",
      report: (event.data.report as ConsoleState["report"]) ?? state.report,
      isReportUnlocked: true,
      timeline: nextTimeline,
      isStreaming: false,
      streamConnection: "idle",
      nextReconnectDelayMs: null,
      error: null,
    };
  }
  if (event.type === "run_completed") {
    return {
      ...state,
      agentStatus: "Investigation complete",
      currentPhase: "finalize",
      status: "COMPLETED",
      requiresApproval: false,
      report: (event.data.report as ConsoleState["report"]) ?? state.report,
      isReportUnlocked: true,
      timeline: nextTimeline,
      isStreaming: false,
      streamConnection: "idle",
      nextReconnectDelayMs: null,
      error: null,
    };
  }
  if (event.type === "run_failed") {
    return {
      ...state,
      status: "FAILED",
      error: String(event.data.message ?? "Investigation failed."),
      isReportUnlocked: false,
      timeline: nextTimeline,
      isStreaming: false,
      streamConnection: "idle",
      nextReconnectDelayMs: null,
    };
  }
  if (event.type === "run_started") {
    return {
      ...state,
      agentStatus: "Investigation started",
      status: "RUNNING",
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  if (event.type === "heartbeat") {
    return {
      ...state,
      timeline: nextTimeline,
      streamConnection: "connected",
      error: null,
    };
  }
  return {
    ...state,
    timeline: nextTimeline,
  };
};

export type Listener = () => void;

export class InvestigationStore {
  private state: ConsoleState;
  private listeners: Set<Listener> = new Set();

  constructor(initialState: ConsoleState = initialConsoleState) {
    this.state = initialState;
  }

  getState = (): ConsoleState => {
    return this.state;
  };

  setState = (next: ConsoleState | ((prev: ConsoleState) => ConsoleState)): void => {
    const nextState = typeof next === "function" ? next(this.state) : next;
    if (nextState !== this.state) {
      this.state = nextState;
      this.notify();
    }
  };

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private notify = (): void => {
    for (const listener of this.listeners) {
      listener();
    }
  };
}

export const createInvestigationStore = (initialState?: ConsoleState): InvestigationStore => {
  return new InvestigationStore(initialState);
};

export const selectTimeline = (state: ConsoleState) => state.timeline;
export const selectEvidence = (state: ConsoleState) => state.evidence;
export const selectRisk = (state: ConsoleState) => state.riskAssessment;
export const selectAnalyzers = (state: ConsoleState) => state.analyzerSummaries;
export const selectHypotheses = (state: ConsoleState) => state.hypotheses;
export const selectReasoning = (state: ConsoleState) => ({
  thoughtProcess: state.activeThoughtProcess,
  reasoningSteps: state.reasoningSteps,
  hypotheses: state.hypotheses,
});
export const selectPipelineStage = (state: ConsoleState) => ({
  currentPhase: state.currentPhase,
  status: state.status,
  reviewerGuidance: state.reviewerGuidance,
});
export const selectAgentMessage = (state: ConsoleState) => ({
  message: state.agentStatus,
  status: state.status,
});
export const selectApproval = (state: ConsoleState) => ({
  requiresApproval: state.requiresApproval,
  status: state.status,
});

export const deriveConsoleStateAtStep = (
  events: StreamEvent[],
  baseRun?: InvestigationRun | null,
  selectedEventIndex?: number | null
): ConsoleState => {
  let state = baseRun
    ? applyRunToConsoleState(initialConsoleState, baseRun)
    : initialConsoleState;

  if (events.length === 0) {
    return state;
  }

  if (
    selectedEventIndex !== null &&
    selectedEventIndex !== undefined &&
    selectedEventIndex < 0
  ) {
    return state;
  }

  const targetIndex =
    selectedEventIndex === null || selectedEventIndex === undefined
      ? events.length - 1
      : Math.min(Math.max(0, selectedEventIndex), events.length - 1);

  for (let i = 0; i <= targetIndex; i += 1) {
    state = applyStreamEventToConsoleState(state, events[i]);
  }

  return state;
};

export const extractIterationSnapshots = (events: StreamEvent[]): IterationSnapshot[] => {
  const snapshotsMap = new Map<number, IterationSnapshot>();
  let activeGuidance: string | null = null;
  let currentIteration = 1;

  for (const event of events) {
    if (event.type === "agent_message" && typeof event.data.guidance === "string") {
      activeGuidance = event.data.guidance;
    }
    if (event.type === "hypothesis_updated") {
      const iterNum = Number(event.data.iteration ?? currentIteration);
      currentIteration = iterNum;
      const rawHypotheses = Array.isArray(event.data.hypotheses)
        ? (event.data.hypotheses as InvestigationHypothesis[])
        : [];
      const questions = Array.isArray(event.data.unresolved_questions)
        ? (event.data.unresolved_questions as string[])
        : [];
      const thought =
        typeof event.data.thought_process === "string" ? event.data.thought_process : null;
      const steps = Array.isArray(event.data.reasoning_steps)
        ? (event.data.reasoning_steps as string[])
        : [];

      const source: IterationSnapshot["source"] = activeGuidance
        ? "Human Reviewer Steering"
        : "AI Investigator";

      const existing = snapshotsMap.get(iterNum);
      snapshotsMap.set(iterNum, {
        iteration: iterNum,
        source: existing?.source ?? source,
        timestamp: event.timestamp,
        hypotheses: rawHypotheses,
        unresolvedQuestions: questions,
        riskAssessment: existing?.riskAssessment ?? null,
        report: existing?.report ?? null,
        thoughtProcess: thought,
        reasoningSteps: steps,
        reviewerGuidance: activeGuidance ?? existing?.reviewerGuidance,
      });

      activeGuidance = null;
    }
    if (event.type === "risk_updated") {
      const risk = event.data as ConsoleState["riskAssessment"];
      const existing = snapshotsMap.get(currentIteration);
      if (existing) {
        existing.riskAssessment = risk;
      }
    }
    if (event.type === "final_report_ready" || event.type === "run_completed") {
      const reportPayload = (event.data.report ?? event.data) as ConsoleState["report"];
      const existing = snapshotsMap.get(currentIteration);
      if (existing && reportPayload) {
        existing.report = reportPayload;
      }
    }
  }

  return Array.from(snapshotsMap.values()).sort((a, b) => a.iteration - b.iteration);
};

export const computeIterationDiff = (
  fromSnapshot: IterationSnapshot,
  toSnapshot: IterationSnapshot
): IterationDiff => {
  const fromHypothesesMap = new Map<string, InvestigationHypothesis>(
    fromSnapshot.hypotheses.map((h) => [h.statement, h])
  );
  const toHypothesesMap = new Map<string, InvestigationHypothesis>(
    toSnapshot.hypotheses.map((h) => [h.statement, h])
  );

  const addedHypotheses: InvestigationHypothesis[] = [];
  const confidenceChanges: HypothesisConfidenceChange[] = [];

  for (const toH of toSnapshot.hypotheses) {
    const fromH = fromHypothesesMap.get(toH.statement);
    if (!fromH) {
      addedHypotheses.push(toH);
    } else {
      const delta = Number((toH.confidence - fromH.confidence).toFixed(2));
      if (Math.abs(delta) >= 0.01) {
        confidenceChanges.push({
          statement: toH.statement,
          previousConfidence: fromH.confidence,
          currentConfidence: toH.confidence,
          delta,
        });
      }
    }
  }

  const resolvedHypotheses: InvestigationHypothesis[] = [];
  for (const fromH of fromSnapshot.hypotheses) {
    if (!toHypothesesMap.has(fromH.statement)) {
      resolvedHypotheses.push(fromH);
    }
  }

  const fromQuestions = new Set(fromSnapshot.unresolvedQuestions);
  const toQuestions = new Set(toSnapshot.unresolvedQuestions);

  const addedQuestions = toSnapshot.unresolvedQuestions.filter((q) => !fromQuestions.has(q));
  const resolvedQuestions = fromSnapshot.unresolvedQuestions.filter((q) => !toQuestions.has(q));

  let riskDelta: IterationDiff["riskDelta"] = null;
  if (fromSnapshot.riskAssessment || toSnapshot.riskAssessment) {
    const prevScore = fromSnapshot.riskAssessment?.score ?? null;
    const currScore = toSnapshot.riskAssessment?.score ?? null;
    const scoreDelta =
      prevScore !== null && currScore !== null
        ? Number((currScore - prevScore).toFixed(2))
        : null;

    riskDelta = {
      previousScore: prevScore,
      currentScore: currScore,
      scoreDelta,
      previousLevel: fromSnapshot.riskAssessment?.level ?? null,
      currentLevel: toSnapshot.riskAssessment?.level ?? null,
    };
  }

  return {
    fromIteration: fromSnapshot.iteration,
    toIteration: toSnapshot.iteration,
    source: toSnapshot.source,
    addedHypotheses,
    resolvedHypotheses,
    confidenceChanges,
    riskDelta,
    addedQuestions,
    resolvedQuestions,
  };
};

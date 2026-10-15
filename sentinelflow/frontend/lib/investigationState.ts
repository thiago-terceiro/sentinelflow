import type { ConsoleState, InvestigationRun, StreamEvent } from "./types";

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

const upsertToolLog = (toolLogs: ConsoleState["toolLogs"], nextLog: ConsoleState["toolLogs"][number]) => {
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
    const { analyzer_id: _analyzerId, analyzer_name: _analyzerName, ...summary } = data;
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

export const applyRunToConsoleState = (state: ConsoleState, run: InvestigationRun): ConsoleState => {
    const isSameInvestigation = state.investigationId === run.id;
    const nextStatus = mapRunStatus(run.status);
    return {
        ...state,
        investigationId: run.id,
        evidence: isSameInvestigation ? state.evidence : [],
        analyzerSummaries: isSameInvestigation ? state.analyzerSummaries : [],
        hypotheses: run.report?.hypotheses ?? (isSameInvestigation ? state.hypotheses : []),
        riskAssessment: run.risk_assessment,
        report: run.report,
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

export const applyStreamEventToConsoleState = (state: ConsoleState, event: StreamEvent): ConsoleState => {
    const nextTimeline = mergeUniqueById(state.timeline, event);
    if (event.type === "agent_message") {
        const stage = typeof event.data.stage === "string" ? (event.data.stage as ConsoleState["currentPhase"]) : state.currentPhase;
        const guidance = typeof event.data.guidance === "string" ? event.data.guidance : state.reviewerGuidance;
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
                (item) => item.analyzer,
            ),
            timeline: nextTimeline,
            streamConnection: "connected",
            error: null,
        };
    }
    if (event.type === "hypothesis_updated") {
        const thought = typeof event.data.thought_process === "string" ? event.data.thought_process : state.activeThoughtProcess;
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

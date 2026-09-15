export type DisputeSummary = {
    id: string;
    case_code: string;
    title: string;
    amount: number;
    currency: string;
    status: "open" | "investigating" | "pending_review" | "closed";
    created_at: string;
};

export type Evidence = {
    id: string;
    source: string;
    category: "transaction" | "customer" | "device" | "network" | "merchant" | "compliance" | "analyzer";
    origin: "observed_fact" | "agent_inference" | "analyzer_interpretation";
    summary: string;
    facts: Record<string, unknown>;
    confidence: number;
    collected_at: string;
    provenance: string;
};

export type AnalyzerSummary = {
    analyzer: string;
    origin: "observed_fact" | "agent_inference" | "analyzer_interpretation";
    summary: string;
    findings: string[];
    confidence: number;
    evidence_ids: string[];
    contradictions: string[];
    recommended_followups: string[];
};

export type RiskFactor = {
    name: string;
    score: number;
    weight: number;
    explanation: string;
    evidence_ids: string[];
};

export type RiskAssessment = {
    score: number;
    level: "low" | "medium" | "high" | "critical";
    factors: RiskFactor[];
    threshold_triggered: boolean;
    explanation: string;
};

export type InvestigationHypothesis = {
    statement: string;
    confidence: number;
    supporting_evidence_ids: string[];
    contradicting_evidence_ids: string[];
};

export type InvestigationReport = {
    conclusion: string;
    recommendation: "approve" | "deny" | "escalate" | "insufficient_evidence";
    confidence: number;
    hypotheses: InvestigationHypothesis[];
    risk_factors: RiskFactor[];
    evidence_ids: string[];
    unresolved_questions: string[];
    compliance_findings: string[];
};

export type InvestigationRun = {
    id: string;
    dispute_id: string;
    thread_id: string;
    status: "pending" | "running" | "awaiting_approval" | "completed" | "failed";
    created_at: string;
    updated_at: string;
    budget: {
        max_iterations: number;
        max_tool_calls: number;
        max_analyzer_calls: number;
        max_tokens: number;
        max_seconds: number;
    };
    risk_assessment: RiskAssessment | null;
    compliance_findings: Array<Record<string, unknown>>;
    report: InvestigationReport | null;
};

export type StreamEvent = {
    id: string;
    type:
    | "run_started"
    | "agent_message"
    | "agent_status_updated"
    | "tool_started"
    | "tool_completed"
    | "analyzer_started"
    | "analyzer_completed"
    | "evidence_added"
    | "hypothesis_updated"
    | "risk_updated"
    | "final_report_ready"
    | "approval_required"
    | "run_completed"
    | "run_failed"
    | "heartbeat";
    timestamp: string;
    data: Record<string, unknown>;
};

export type ToolLog = {
    callId: string;
    label: string;
    status: "started" | "completed";
    output?: string;
};

export type ConsoleState = {
    investigationId: string;
    evidence: Evidence[];
    analyzerSummaries: AnalyzerSummary[];
    hypotheses: InvestigationHypothesis[];
    riskAssessment: RiskAssessment | null;
    report: InvestigationReport | null;
    isReportUnlocked: boolean;
    timeline: StreamEvent[];
    agentStatus: string | null;
    toolLogs: ToolLog[];
    status: "IDLE" | "RUNNING" | "APPROVAL_REQUIRED" | "COMPLETED" | "FAILED";
    requiresApproval: boolean;
    isStreaming: boolean;
    streamConnection: "idle" | "connected" | "reconnecting" | "disconnected";
    reconnectAttempt: number;
    nextReconnectDelayMs: number | null;
    error: string | null;
};

import type { components, paths } from "./types/api.generated";

export type ApiPaths = paths;
export type ApiSchemas = components["schemas"];

export type DisputeSummary = ApiSchemas["DisputeSummary"];
export type DisputeDetail = ApiSchemas["DisputeDetail"];
export type RiskAssessment = NonNullable<ApiSchemas["InvestigationRun"]["risk_assessment"]>;
export type RiskFactor = ApiSchemas["RiskFactor"];
export type InvestigationBudget = ApiSchemas["InvestigationBudget"];
export type InvestigationHypothesis = ApiSchemas["InvestigationHypothesis"] & {
  thought_process?: string;
  reasoning_steps?: string[];
};
export type InvestigationReport = NonNullable<ApiSchemas["InvestigationRun"]["report"]>;
export type InvestigationRun = ApiSchemas["InvestigationRun"];
export type ComplianceFinding = ApiSchemas["ComplianceFinding"];
export type ApprovalDecision = ApiSchemas["ApprovalDecision"]["decision"];
export type AuditCorrectionRequest = ApiSchemas["AuditCorrectionRequest"];
export type AuditCorrectionResponse = ApiSchemas["AuditCorrectionResponse"];
export type AuditIntegrity = ApiSchemas["AuditIntegrityResponse"];
export type EvalSuiteReport = ApiSchemas["EvalSuiteReport"];
export type CaseEvalResult = ApiSchemas["CaseEvalResult"];
export type CaseScoreDetail = ApiSchemas["CaseScoreDetail"];
export type AuditRecord = ApiSchemas["AuditRecordItem"] & {
  actor?: string;
  is_redacted?: boolean;
  redaction_policy?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
};

export type Evidence = ApiSchemas["Evidence"];

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
    | "reasoning_delta"
    | "synthesis_delta"
    | "guardrail_triggered"
    | "hallucination_detected"
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
  activeThoughtProcess?: string | null;
  reasoningSteps?: string[];
  currentPhase?: "intake" | "investigate" | "collect" | "synthesize" | "approval" | "finalize";
  reviewerGuidance?: string | null;
  streamingReasoningDelta?: string | null;
};

export type IterationSnapshot = {
  iteration: number;
  source: "AI Investigator" | "Deterministic Engine" | "Human Reviewer Steering";
  timestamp: string;
  hypotheses: InvestigationHypothesis[];
  unresolvedQuestions: string[];
  riskAssessment: RiskAssessment | null;
  report: InvestigationReport | null;
  thoughtProcess?: string | null;
  reasoningSteps?: string[];
  reviewerGuidance?: string | null;
  streamingReasoningDelta?: string | null;
};

export type HypothesisConfidenceChange = {
  statement: string;
  previousConfidence: number;
  currentConfidence: number;
  delta: number;
};

export type IterationDiff = {
  fromIteration: number;
  toIteration: number;
  source: "AI Investigator" | "Deterministic Engine" | "Human Reviewer Steering";
  addedHypotheses: InvestigationHypothesis[];
  resolvedHypotheses: InvestigationHypothesis[];
  confidenceChanges: HypothesisConfidenceChange[];
  riskDelta: {
    previousScore: number | null;
    currentScore: number | null;
    scoreDelta: number | null;
    previousLevel: string | null;
    currentLevel: string | null;
  } | null;
  addedQuestions: string[];
  resolvedQuestions: string[];
};

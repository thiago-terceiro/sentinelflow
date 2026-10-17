import type {
  ApprovalDecision,
  AuditCorrectionRequest,
  AuditCorrectionResponse,
  AuditIntegrity,
  AuditRecord,
  DisputeSummary,
  EvalSuiteReport,
  InvestigationRun,
} from "@/lib/types";

const CLIENT_PROXY_BASE_URL = "/app-api";

const isServerRuntime = (): boolean => {
  return typeof window === "undefined";
};

const resolveApiBaseUrl = (): string => {
  return CLIENT_PROXY_BASE_URL;
};

export const resolveClientProxyBaseUrl = (): string => {
  if (isServerRuntime()) {
    return CLIENT_PROXY_BASE_URL;
  }
  return `${window.location.origin}${CLIENT_PROXY_BASE_URL}`;
};

const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const headers = new Headers(init?.headers ?? {});
  headers.set("Content-Type", "application/json");

  const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    let errorMessage: string | null = null;
    try {
      const payload = (await response.json()) as { error?: { message?: string } } | null;
      errorMessage = payload?.error?.message ?? null;
    } catch {
      errorMessage = null;
    }
    throw new Error(errorMessage ?? `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
};

export const listDisputes = async (): Promise<DisputeSummary[]> => {
  return request<DisputeSummary[]>("/disputes");
};

export const startInvestigation = async (disputeId: string): Promise<InvestigationRun> => {
  return request<InvestigationRun>(`/disputes/${disputeId}/investigations`, { method: "POST" });
};

export const getInvestigation = async (investigationId: string): Promise<InvestigationRun> => {
  return request<InvestigationRun>(`/investigations/${investigationId}`);
};

export const investigationStreamEndpoint = (investigationId: string): string => {
  return `${resolveClientProxyBaseUrl()}/investigations/${investigationId}/stream`;
};

export const resumeInvestigation = async (
  investigationId: string,
  decision: ApprovalDecision,
  comment?: string,
  guidance?: string
): Promise<InvestigationRun> => {
  const payload: { decision: ApprovalDecision; comment: string; guidance?: string } = {
    decision,
    comment: comment ?? "",
  };
  if (guidance !== undefined) {
    payload.guidance = guidance;
  }
  return request<InvestigationRun>(`/investigations/${investigationId}/resume`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
};

export const getAuditRecords = async (params?: {
  dispute_id?: string;
  investigation_id?: string;
  event_name?: string;
  limit?: number;
}): Promise<AuditRecord[]> => {
  const searchParams = new URLSearchParams();
  if (params?.dispute_id) {
    searchParams.set("dispute_id", params.dispute_id);
  }
  if (params?.investigation_id) {
    searchParams.set("investigation_id", params.investigation_id);
  }
  if (params?.event_name) {
    searchParams.set("event_name", params.event_name);
  }
  if (params?.limit) {
    searchParams.set("limit", String(params.limit));
  }
  const query = searchParams.toString();
  const endpoint = query ? `/audit/records?${query}` : "/audit/records";
  return request<AuditRecord[]>(endpoint);
};

export const getAuditIntegrity = async (investigationId: string): Promise<AuditIntegrity> => {
  return request<AuditIntegrity>(`/investigations/${investigationId}/audit/integrity`);
};

export const createAuditCorrection = async (
  investigationId: string,
  correction: AuditCorrectionRequest
): Promise<AuditCorrectionResponse> => {
  return request<AuditCorrectionResponse>(`/investigations/${investigationId}/audit/corrections`, {
    method: "POST",
    body: JSON.stringify(correction),
  });
};

export const getAuditArtifact = async (
  investigationId: string,
  artifactType: "sar" | "summary"
): Promise<Record<string, unknown>> => {
  return request<Record<string, unknown>>(
    `/investigations/${investigationId}/artifacts/${artifactType}`
  );
};

export const getLatestEvaluation = async (): Promise<EvalSuiteReport> => {
  return request<EvalSuiteReport>("/evals/latest");
};

export const triggerEvaluationRun = async (): Promise<EvalSuiteReport> => {
  return request<EvalSuiteReport>("/evals/run", { method: "POST" });
};

export const downloadTuningDataset = async (
  exportType: "dpo" | "sft" = "dpo",
  format: "jsonl" | "json" = "jsonl"
): Promise<{ filename: string; content: string }> => {
  const res = await fetch(
    `/app-api/audit/export/tuning?export_type=${exportType}&format=${format}`
  );
  if (!res.ok) {
    throw new Error(`Failed to export tuning dataset: ${res.statusText}`);
  }
  const disposition = res.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename=([^;]+)/);
  const filename = filenameMatch
    ? filenameMatch[1].trim()
    : `sentinelflow_${exportType}_dataset.${format}`;
  const content = await res.text();
  return { filename, content };
};

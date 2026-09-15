import type { DisputeSummary, InvestigationRun } from "@/lib/types";

const CLIENT_PROXY_BASE_URL = "/app-api";

function isServerRuntime(): boolean {
    return typeof window === "undefined";
}

function resolveApiBaseUrl(): string {
    return CLIENT_PROXY_BASE_URL;
}

function resolveClientProxyBaseUrl(): string {
    if (isServerRuntime()) {
        return CLIENT_PROXY_BASE_URL;
    }
    return `${window.location.origin}${CLIENT_PROXY_BASE_URL}`;
}

async function request<T>(
    path: string,
    init?: RequestInit,
): Promise<T> {
    const headers = new Headers(init?.headers ?? {});
    headers.set("Content-Type", "application/json");
    const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
        ...init,
        headers,
        cache: "no-store",
    });
    if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { error?: { message?: string } } | null;
        throw new Error(payload?.error?.message ?? `Request failed with status ${response.status}`);
    }
    return response.json() as Promise<T>;
}

export function listDisputes(): Promise<DisputeSummary[]> {
    return request<DisputeSummary[]>("/disputes");
}

export function startInvestigation(disputeId: string): Promise<InvestigationRun> {
    return request<InvestigationRun>(`/disputes/${disputeId}/investigations`, { method: "POST" });
}

export function getInvestigation(investigationId: string): Promise<InvestigationRun> {
    return request<InvestigationRun>(`/investigations/${investigationId}`);
}

export function investigationStreamEndpoint(investigationId: string): string {
    return `${resolveClientProxyBaseUrl()}/investigations/${investigationId}/stream`;
}

export function resumeInvestigation(
    investigationId: string,
    decision: "approve" | "deny",
    comment: string,
): Promise<InvestigationRun> {
    return request<InvestigationRun>(`/investigations/${investigationId}/resume`, {
        method: "POST",
        body: JSON.stringify({ decision, comment }),
    });
}

import type {
  Analysis,
  AnalysisOptions,
  AuthResult,
  Comparison,
  CompiledWorkflow,
  CopilotAnswer,
  HarImportPayload,
  Me,
  ReportDetail,
  ReportListResponse,
  SavedWorkflow,
  Stats,
  WorkflowContract,
  WorkflowCapturePayload,
  WorkflowNotificationStatus,
  WorkflowRun,
  WorkflowVaultStatus,
} from "./types";
import { clearToken, getToken } from "./auth";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const requestToken = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (requestToken) headers.Authorization = `Bearer ${requestToken}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      signal: init?.signal ?? AbortSignal.timeout(30_000),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError(0, "The Orbit API took too long to respond. Please try again.");
    }
    throw new ApiError(0, "Cannot reach the Orbit API. Please try again shortly.");
  }
  if (
    response.status === 401 &&
    !path.startsWith("/api/v1/auth/") &&
    getToken() === requestToken
  ) {
    clearToken();
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (body as { detail?: string }).detail ?? response.statusText;
    throw new ApiError(response.status, detail);
  }
  return body as T;
}

function idempotencyKey(): string {
  const uuid =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `orbit-${uuid}`;
}

export const api = {
  me: () => request<Me>("/api/v1/me"),

  oauthProviders: () => request<{ google: boolean; github: boolean }>("/api/v1/auth/oauth/providers"),

  signup: (email: string, name: string, password: string) =>
    request<AuthResult>("/api/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, name, password }),
    }),

  login: (email: string, password: string) =>
    request<AuthResult>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  guest: () => request<AuthResult>("/api/v1/auth/guest", { method: "POST" }),

  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),

  createAnalysis: (target_url: string, options: AnalysisOptions) =>
    request<Analysis>("/api/v1/analyses", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey() },
      body: JSON.stringify({ target_url, options, authorized_public_analysis: true }),
    }),

  importHarAnalysis: (payload: HarImportPayload) =>
    request<Analysis>("/api/v1/analyses/har", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey() },
      body: JSON.stringify(payload),
    }),

  importWorkflowAnalysis: (payload: WorkflowCapturePayload) =>
    request<Analysis>("/api/v1/analyses/workflow", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey() },
      body: JSON.stringify(payload),
    }),

  getAnalysis: (id: string) => request<Analysis>(`/api/v1/analyses/${id}`),

  cancelAnalysis: (id: string) =>
    request<Analysis>(`/api/v1/analyses/${id}/cancel`, { method: "POST" }),

  listReports: (params: { q?: string; favorite?: boolean; cursor?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.favorite) search.set("favorite", "true");
    if (params.cursor) search.set("cursor", params.cursor);
    const qs = search.toString();
    return request<ReportListResponse>(`/api/v1/reports${qs ? `?${qs}` : ""}`);
  },

  getReport: (id: string) => request<ReportDetail>(`/api/v1/reports/${id}`),

  askReport: (id: string, question: string) =>
    request<CopilotAnswer>(`/api/v1/reports/${id}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  compileWorkflow: (id: string, flow_name: string) =>
    request<CompiledWorkflow>(`/api/v1/reports/${id}/workflows/compile`, {
      method: "POST",
      body: JSON.stringify({ flow_name }),
    }),

  saveWorkflow: (reportId: string, contract: WorkflowContract, schedule: "manual" | "daily" | "weekly") =>
    request<SavedWorkflow>(`/api/v1/reports/${reportId}/workflows`, {
      method: "POST",
      body: JSON.stringify({ contract, schedule }),
    }),

  listSavedWorkflows: (reportId: string) =>
    request<{ items: SavedWorkflow[] }>(`/api/v1/reports/${reportId}/workflows/saved`),

  runWorkflow: (reportId: string, workflowId: string, inputs: Record<string, string>) =>
    request<WorkflowRun>(`/api/v1/reports/${reportId}/workflows/${workflowId}/runs`, {
      method: "POST",
      body: JSON.stringify({ inputs }),
      signal: AbortSignal.timeout(110_000),
    }),

  listWorkflowRuns: (reportId: string, workflowId: string) =>
    request<{ items: WorkflowRun[] }>(`/api/v1/reports/${reportId}/workflows/${workflowId}/runs`),

  workflowVaultStatus: (reportId: string, workflowId: string) =>
    request<WorkflowVaultStatus>(`/api/v1/reports/${reportId}/workflows/${workflowId}/vault`),

  saveWorkflowVault: (reportId: string, workflowId: string, secrets: Record<string, string>) =>
    request<WorkflowVaultStatus>(`/api/v1/reports/${reportId}/workflows/${workflowId}/vault`, {
      method: "PUT",
      body: JSON.stringify({ secrets }),
    }),

  clearWorkflowVault: (reportId: string, workflowId: string) =>
    request<WorkflowVaultStatus>(`/api/v1/reports/${reportId}/workflows/${workflowId}/vault`, {
      method: "DELETE",
    }),

  workflowNotificationStatus: (reportId: string, workflowId: string) =>
    request<WorkflowNotificationStatus>(`/api/v1/reports/${reportId}/workflows/${workflowId}/notifications`),

  updateWorkflowNotifications: (
    reportId: string,
    workflowId: string,
    update: { slack_webhook?: string; email?: string; disable_slack?: boolean; disable_email?: boolean },
  ) => request<WorkflowNotificationStatus>(
    `/api/v1/reports/${reportId}/workflows/${workflowId}/notifications`,
    { method: "PUT", body: JSON.stringify(update) },
  ),

  updateReport: (id: string, patch: { is_favorite?: boolean; label?: string }) =>
    request<unknown>(`/api/v1/reports/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteReport: (id: string) =>
    request<void>(`/api/v1/reports/${id}`, { method: "DELETE" }),

  exportReport: (id: string, format: "json" | "markdown") =>
    request<{ format: string; filename: string; content: string }>(
      `/api/v1/reports/${id}/exports`,
      { method: "POST", body: JSON.stringify({ format }) },
    ),

  stats: () => request<Stats>("/api/v1/reports/stats"),

  compare: (a: string, b: string) =>
    request<Comparison>(`/api/v1/reports/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),

  eventStreamUrl: (id: string) => `${API_BASE}/api/v1/analyses/${id}/events`,
};

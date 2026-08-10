/**
 * Compass API client.
 *
 * Two modes, switched by `NEXT_PUBLIC_USE_MOCK`:
 *   - USE_MOCK=true   every function below resolves from lib/mock/* fixtures
 *                      (filtered/masked by the current persona's role +
 *                      org_unit, simulating RLS/CLS client-side) — the whole
 *                      app renders with zero AWS resources deployed.
 *   - USE_MOCK=false  every function below calls the deployed HttpApi at
 *                      NEXT_PUBLIC_API_BASE_URL with the signed-in user's
 *                      bearer token attached.
 *
 * Auth context (bearer token / role / org_unit) is set by
 * lib/auth/token-sync.tsx via `setAuthContext()` — a plain module ref
 * (not React context) so it's readable from these async functions outside
 * the component tree, mirroring the api-client building block.
 */
import type {
  AnalyticsRunDetail,
  AnalyticsRunRequest,
  AnalyticsRunResponse,
  AnomaliesResponse,
  ApprovalRequest,
  ApprovalResponse,
  CatalogResponse,
  ChatRequest,
  ChatResponse,
  DashboardResponse,
  ExportRequest,
  ExportResponse,
  IngestSimulateRequest,
  IngestSimulateResponse,
  IngestStatusResponse,
  LicensesResponse,
  LineageResponse,
  MeResponse,
  OpenApiDoc,
  Role,
  StreamRecentResponse,
} from "@/lib/types";

export const USE_MOCK =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_USE_MOCK !== "false";

const API_BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) || "";

// ---------------------------------------------------------------------------
// Auth context — set by lib/auth/token-sync.tsx, read by every call below.
// ---------------------------------------------------------------------------
type AuthContext = { bearerToken: string | null; role: Role | null; orgUnit: string | null };
const authRef: AuthContext = { bearerToken: null, role: null, orgUnit: null };

export function setAuthContext(ctx: AuthContext): void {
  authRef.bearerToken = ctx.bearerToken;
  authRef.role = ctx.role;
  authRef.orgUnit = ctx.orgUnit;
}

// ---------------------------------------------------------------------------
// Live-mode fetch wrapper
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `api_error_${status}`);
    this.status = status;
    this.body = body;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (authRef.bearerToken) headers["Authorization"] = `Bearer ${authRef.bearerToken}`;

  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Route functions — one per docs/CONTRACTS.md API table row.
// ---------------------------------------------------------------------------

export async function getMe(): Promise<MeResponse> {
  if (USE_MOCK) {
    const { getMe: mockGetMe } = await import("@/lib/mock");
    return mockGetMe(authRef.role, authRef.orgUnit);
  }
  return fetchJson<MeResponse>("/me");
}

export async function getCatalog(): Promise<CatalogResponse> {
  if (USE_MOCK) {
    const { getCatalog: mockGetCatalog } = await import("@/lib/mock");
    return mockGetCatalog(authRef.role, authRef.orgUnit);
  }
  return fetchJson<CatalogResponse>("/catalog");
}

export async function getCatalogLineage(id: string): Promise<LineageResponse> {
  if (USE_MOCK) {
    const { getLineage } = await import("@/lib/mock");
    const result = getLineage(id, authRef.role, authRef.orgUnit);
    if (!result) throw new ApiError(404, { error: "not_found" });
    return result;
  }
  return fetchJson<LineageResponse>(`/catalog/${encodeURIComponent(id)}/lineage`);
}

export async function postIngestSimulate(
  req: IngestSimulateRequest = {},
): Promise<IngestSimulateResponse> {
  if (USE_MOCK) {
    const { simulateIngest } = await import("@/lib/mock");
    return simulateIngest();
  }
  return fetchJson<IngestSimulateResponse>("/ingest/simulate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getIngestStatus(): Promise<IngestStatusResponse> {
  if (USE_MOCK) {
    const { getIngestStatus: mockGetIngestStatus } = await import("@/lib/mock");
    return mockGetIngestStatus(authRef.role, authRef.orgUnit);
  }
  return fetchJson<IngestStatusResponse>("/ingest/status");
}

export async function getStreamRecent(): Promise<StreamRecentResponse> {
  if (USE_MOCK) {
    const { getStreamRecent: mockGetStreamRecent } = await import("@/lib/mock");
    return mockGetStreamRecent(authRef.role, authRef.orgUnit);
  }
  return fetchJson<StreamRecentResponse>("/stream/recent");
}

export async function postAnalyticsRun(
  req: AnalyticsRunRequest = {},
): Promise<AnalyticsRunResponse> {
  if (USE_MOCK) {
    const { runAnalytics } = await import("@/lib/mock");
    return runAnalytics();
  }
  return fetchJson<AnalyticsRunResponse>("/analytics/run", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getAnalyticsRun(runId: string): Promise<AnalyticsRunDetail> {
  if (USE_MOCK) {
    const { getAnalyticsRun: mockGetAnalyticsRun } = await import("@/lib/mock");
    return mockGetAnalyticsRun(runId, authRef.role, authRef.orgUnit);
  }
  return fetchJson<AnalyticsRunDetail>(`/analytics/${encodeURIComponent(runId)}`);
}

export async function getDashboard(): Promise<DashboardResponse> {
  if (USE_MOCK) {
    const { getDashboard: mockGetDashboard } = await import("@/lib/mock");
    return mockGetDashboard(authRef.role, authRef.orgUnit);
  }
  return fetchJson<DashboardResponse>("/dashboard");
}

export async function postChat(req: ChatRequest): Promise<ChatResponse> {
  if (USE_MOCK) {
    const { answerChat } = await import("@/lib/mock");
    return answerChat(req, authRef.role, authRef.orgUnit);
  }
  return fetchJson<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(req) });
}

export async function getAnomalies(): Promise<AnomaliesResponse> {
  if (USE_MOCK) {
    const { getAnomalies: mockGetAnomalies } = await import("@/lib/mock");
    return mockGetAnomalies(authRef.role, authRef.orgUnit);
  }
  return fetchJson<AnomaliesResponse>("/anomalies");
}

export async function postApprovals(req: ApprovalRequest): Promise<ApprovalResponse> {
  if (USE_MOCK) {
    const { createOrAdvanceApproval } = await import("@/lib/mock");
    return createOrAdvanceApproval(req, authRef.role ?? "viewer");
  }
  return fetchJson<ApprovalResponse>("/approvals", { method: "POST", body: JSON.stringify(req) });
}

export async function getLicenses(): Promise<LicensesResponse> {
  if (USE_MOCK) {
    const { getLicenses: mockGetLicenses } = await import("@/lib/mock");
    return mockGetLicenses();
  }
  return fetchJson<LicensesResponse>("/licenses");
}

/**
 * Enforces the same aggregation guard as the deployed Lambda: throws
 * `ApiError` with `status === 428` (approval required) when the requested
 * row count exceeds the max and no `approval_token` is attached.
 */
export async function postExport(req: ExportRequest): Promise<ExportResponse> {
  if (USE_MOCK) {
    const { runExport, ExportApprovalRequiredError } = await import("@/lib/mock");
    try {
      return runExport(req, authRef.role, authRef.orgUnit);
    } catch (e) {
      if (e instanceof ExportApprovalRequiredError) throw new ApiError(e.status, e.body);
      throw e;
    }
  }
  return fetchJson<ExportResponse>("/export", { method: "POST", body: JSON.stringify(req) });
}

export async function getOpenApiSpec(): Promise<OpenApiDoc> {
  if (USE_MOCK) {
    return {
      openapi: "3.1.0",
      info: { title: "Compass API (mock)", version: "0.1.0" },
      note: "Static export served by the deployed HttpApi at /openapi.json; not fixture-backed in USE_MOCK mode.",
    };
  }
  return fetchJson<OpenApiDoc>("/openapi.json");
}

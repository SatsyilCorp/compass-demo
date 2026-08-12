/**
 * Compass API client.
 *
 * Two modes, switched by `NEXT_PUBLIC_USE_MOCK`:
 *   - USE_MOCK=true   every function below resolves from lib/mock/* fixtures
 *                      (filtered/masked by the current persona's role +
 *                      org_unit, simulating RLS/CLS client-side). The whole
 *                      app renders with zero AWS resources deployed.
 *   - USE_MOCK=false  every function below calls the deployed HttpApi at
 *                      NEXT_PUBLIC_API_BASE_URL with the signed-in user's
 *                      bearer token attached.
 *
 * Auth context (bearer token / role / org_unit) is set by
 * lib/auth/token-sync.tsx via `setAuthContext()`, a plain module ref
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
  ApprovalsListResponse,
  CatalogResponse,
  ChatRequest,
  ChatResponse,
  DashboardFilters,
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
  SystemEvidenceResponse,
} from "@/lib/types";
import type {
  ScaleCancelRequest,
  ScaleExportReceipt,
  ScaleExportRequest,
  ScaleLaunchRequest,
  ScalePlan,
  ScalePlanRequest,
  ScaleProfilesResponse,
  ScaleRun,
  ScaleRunsResponse,
} from "@/lib/scale/types";
import {
  parsePublicIntelligenceExplanationResponse,
  parsePublicIntelligenceSnapshotResponse,
} from "@/lib/public-intelligence/live";
import type {
  PublicIntelligenceExplainRequest,
  PublicIntelligenceExplanationResponse,
  PublicIntelligenceSnapshotResponse,
} from "@/lib/public-intelligence/types";
import {
  parsePublicModelExecutionList,
  parsePublicModelExecutionReceipt,
  type PublicModelExecutionList,
  type PublicModelExecutionReceipt,
} from "@/lib/mlops/model-execution";

export const USE_MOCK =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_USE_MOCK !== "false";

const API_BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) || "";

// ---------------------------------------------------------------------------
// Auth context: set by lib/auth/token-sync.tsx, read by every call below.
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
// Route functions: one per docs/CONTRACTS.md API table row.
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
  if (authRef.role !== "poweruser") {
    throw new ApiError(403, { error: "poweruser analytics role required" });
  }
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
  if (authRef.role !== "poweruser") {
    throw new ApiError(403, { error: "poweruser analytics role required" });
  }
  if (USE_MOCK) {
    const { getAnalyticsRun: mockGetAnalyticsRun } = await import("@/lib/mock");
    return mockGetAnalyticsRun(runId, authRef.role, authRef.orgUnit);
  }
  return fetchJson<AnalyticsRunDetail>(`/analytics/${encodeURIComponent(runId)}`);
}

export async function getDashboard(
  filters: DashboardFilters = {},
): Promise<DashboardResponse> {
  if (USE_MOCK) {
    const { getDashboard: mockGetDashboard } = await import("@/lib/mock");
    const replayLoader = mockGetDashboard as (
      role: Role | null,
      orgUnit: string | null,
      requestFilters?: DashboardFilters,
    ) => DashboardResponse;
    const response = replayLoader(authRef.role, authRef.orgUnit, filters);
    return {
      ...response,
      filters_applied: {
        program_area: response.filters_applied?.program_area ?? filters.program_area ?? null,
        fiscal_year: response.filters_applied?.fiscal_year ?? filters.fiscal_year ?? null,
        org_unit: response.filters_applied?.org_unit ?? filters.org_unit ?? null,
        q: response.filters_applied?.q ?? filters.q ?? null,
      },
      filter_options: response.filter_options ?? {
        program_areas: response.funding_by_program_area.map((row) => row.program_area),
        fiscal_years: response.funding_by_fiscal_year.map((row) => row.fiscal_year),
        org_units: response.org_unit_breakdown.map((row) => row.org_unit),
      },
    };
  }
  const query = new URLSearchParams();
  if (filters.program_area) query.set("program_area", filters.program_area);
  if (filters.fiscal_year !== undefined) query.set("fiscal_year", String(filters.fiscal_year));
  if (filters.org_unit) query.set("org_unit", filters.org_unit);
  if (filters.q) query.set("q", filters.q);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return fetchJson<DashboardResponse>(`/dashboard${suffix}`, { cache: "no-store" });
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

export async function getApprovals(): Promise<ApprovalsListResponse> {
  if (USE_MOCK) {
    const { listPendingApprovals } = await import("@/lib/mock");
    return listPendingApprovals(authRef.role ?? "viewer");
  }
  return fetchJson<ApprovalsListResponse>("/approvals", { cache: "no-store" });
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
      return await runExport(req, authRef.role, authRef.orgUnit);
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

export async function getSystemEvidence(): Promise<SystemEvidenceResponse> {
  if (USE_MOCK) {
    const { getReplaySystemEvidence } = await import("@/lib/system-evidence-replay");
    return getReplaySystemEvidence();
  }
  return fetchJson<SystemEvidenceResponse>("/system/evidence", {
    cache: "no-store",
  });
}

// Scale Lab live calls. Replay behavior is isolated behind lib/scale/adapters.
export function getScaleProfilesApi(): Promise<ScaleProfilesResponse> {
  return fetchJson<ScaleProfilesResponse>("/scale/profiles", { cache: "no-store" });
}

export function postScalePlanApi(request: ScalePlanRequest): Promise<ScalePlan> {
  return fetchJson<ScalePlan>("/scale/plans", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function postScaleRunApi(request: ScaleLaunchRequest): Promise<ScaleRun> {
  return fetchJson<ScaleRun>("/scale/runs", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getScaleRunsApi(): Promise<ScaleRunsResponse> {
  return fetchJson<ScaleRunsResponse>("/scale/runs", { cache: "no-store" });
}

export function getScaleRunApi(runId: string): Promise<ScaleRun> {
  return fetchJson<ScaleRun>(`/scale/runs/${encodeURIComponent(runId)}`, { cache: "no-store" });
}

export function postScaleRunCancelApi(runId: string, request: ScaleCancelRequest): Promise<ScaleRun> {
  return fetchJson<ScaleRun>(`/scale/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function postScaleExportApi(
  runId: string,
  request: ScaleExportRequest,
): Promise<ScaleExportReceipt> {
  return fetchJson<ScaleExportReceipt>(`/scale/runs/${encodeURIComponent(runId)}/exports`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getScaleExportApi(runId: string, exportId: string): Promise<ScaleExportReceipt> {
  return fetchJson<ScaleExportReceipt>(
    `/scale/runs/${encodeURIComponent(runId)}/exports/${encodeURIComponent(exportId)}`,
    { cache: "no-store" },
  );
}

// Document Intake and model operations live adapter. Replay behavior stays in
// lib/documents and lib/mlops so the browser never presents replay as a cloud run.
export type DocumentUploadRequest = {
  filename: string;
  content_type: string;
  size_bytes: number;
  synthetic_only: boolean;
  data_classification: "synthetic-demo" | "public";
  contains_cui: false;
  pii_minimized: boolean;
};

export type DocumentUploadResponse = {
  run_id: string;
  document_id: string;
  status: string;
  stage: string;
  source: string;
  upload: {
    method: "PUT";
    url: string;
    headers: Record<string, string>;
    expires_in_seconds: number;
    maximum_bytes: number;
  };
};

export type DocumentRunRecord = Record<string, unknown> & {
  run_id: string;
  status: string;
  stage: string;
  filename?: string;
};

export type ModelRecord = Record<string, unknown> & {
  model_version: string;
  status: string;
  metrics?: { accuracy?: number; macro_f1?: number };
};

export function postDocumentUploadApi(request: DocumentUploadRequest): Promise<DocumentUploadResponse> {
  return fetchJson<DocumentUploadResponse>("/documents/uploads", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function putDocumentBytesApi(
  upload: DocumentUploadResponse["upload"],
  bytes: ArrayBuffer,
): Promise<void> {
  return fetch(upload.url, {
    method: upload.method,
    headers: upload.headers,
    body: bytes,
  }).then((response) => {
    if (!response.ok) throw new ApiError(response.status, null, "document_upload_failed");
  });
}

export function getDocumentRunsApi(): Promise<{ runs: DocumentRunRecord[] }> {
  return fetchJson<{ runs: DocumentRunRecord[] }>("/documents/runs", { cache: "no-store" });
}

export function getDocumentRunApi(runId: string): Promise<DocumentRunRecord> {
  return fetchJson<DocumentRunRecord>(`/documents/runs/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });
}

export function postModelTrainApi(): Promise<ModelRecord> {
  return fetchJson<ModelRecord>("/ml/train", { method: "POST", body: "{}" });
}

export function getModelsApi(): Promise<{ models: ModelRecord[]; champion: unknown }> {
  return fetchJson<{ models: ModelRecord[]; champion: unknown }>("/ml/models", {
    cache: "no-store",
  });
}

export function postModelDeployApi(modelVersion: string): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/ml/models/${encodeURIComponent(modelVersion)}/deploy`, {
    method: "POST",
    body: "{}",
  });
}

export function postModelDriftApi(documents?: string[]): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/ml/drift/evaluate", {
    method: "POST",
    body: JSON.stringify(documents ? { documents } : {}),
  });
}

export function getModelOpsEvidenceApi(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/ml/ops/evidence", { cache: "no-store" });
}

export async function postPublicModelExecutionApi(
  sampleSize: number,
): Promise<PublicModelExecutionReceipt> {
  const response = await fetchJson<unknown>("/public-intelligence/model-executions", {
    method: "POST",
    body: JSON.stringify({ sampleSize }),
  });
  const receipt = parsePublicModelExecutionReceipt(response);
  if (!receipt) throw new ApiError(502, response, "model_execution_receipt_contract_invalid");
  return receipt;
}

export async function getPublicModelExecutionApi(
  executionId: string,
): Promise<PublicModelExecutionReceipt> {
  const response = await fetchJson<unknown>(
    `/public-intelligence/model-executions/${encodeURIComponent(executionId)}`,
    { cache: "no-store" },
  );
  const receipt = parsePublicModelExecutionReceipt(response);
  if (!receipt) throw new ApiError(502, response, "model_execution_receipt_contract_invalid");
  return receipt;
}

export async function getPublicModelExecutionsApi(): Promise<PublicModelExecutionList> {
  const response = await fetchJson<unknown>("/public-intelligence/model-executions", {
    cache: "no-store",
  });
  const list = parsePublicModelExecutionList(response);
  if (!list) throw new ApiError(502, response, "model_execution_list_contract_invalid");
  return list;
}

// Public intelligence is intentionally backed only by the protected live API.
// The page owns its bundled last-known fallback so it can state the evidence
// mode clearly instead of presenting fallback data as a live cloud response.
export async function getPublicIntelligenceSnapshotApi(): Promise<PublicIntelligenceSnapshotResponse> {
  const response = await fetchJson<unknown>("/public-intelligence/snapshot", {
    cache: "no-store",
  });
  const parsed = parsePublicIntelligenceSnapshotResponse(response);
  if (!parsed) {
    throw new ApiError(502, null, "public_intelligence_snapshot_contract_invalid");
  }
  return parsed;
}

export async function postPublicIntelligenceExplainApi(
  request: PublicIntelligenceExplainRequest,
): Promise<PublicIntelligenceExplanationResponse> {
  const response = await fetchJson<unknown>("/public-intelligence/explain", {
    method: "POST",
    body: JSON.stringify(request),
  });
  const parsed = parsePublicIntelligenceExplanationResponse(response);
  if (!parsed) {
    throw new ApiError(502, null, "public_intelligence_explanation_contract_invalid");
  }
  return parsed;
}

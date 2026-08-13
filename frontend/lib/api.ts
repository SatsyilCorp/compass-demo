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
  LiveDemoStreamResponse,
  LiveDemoStreamStartRequest,
  LiveDemoStreamStatus,
  LiveDemoStreamStopRequest,
  MeResponse,
  OpenApiDoc,
  OperationsLineageResponse,
  OperationsLineageStage,
  OperationsRunSummary,
  OperationsSignalAcknowledgeResponse,
  OperationsSignalsResponse,
  OperationsSummaryResponse,
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
import { BearerTokenGate } from "@/lib/auth/bearer-token-gate";

export const USE_MOCK =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_USE_MOCK !== "false";

const API_BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) || "";

// ---------------------------------------------------------------------------
// Auth context: set by lib/auth/token-sync.tsx, read by every call below.
// ---------------------------------------------------------------------------
type AuthContext = { bearerToken: string | null; role: Role | null; orgUnit: string | null };
const authRef: AuthContext = { bearerToken: null, role: null, orgUnit: null };
const bearerTokenGate = new BearerTokenGate();
const AUTH_HYDRATION_WAIT_MS = 1_000;

export function setAuthContext(ctx: AuthContext): void {
  authRef.bearerToken = ctx.bearerToken;
  authRef.role = ctx.role;
  authRef.orgUnit = ctx.orgUnit;
  bearerTokenGate.publish(ctx.bearerToken);
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
  const bearerToken = authRef.bearerToken ?? await bearerTokenGate.wait(AUTH_HYDRATION_WAIT_MS);
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (bearerToken) headers["Authorization"] = `Bearer ${bearerToken}`;

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      null,
      "The live Compass service could not be reached. Refresh and retry.",
    );
  }
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
  source_sha256: string;
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
    method: "POST";
    url: string;
    fields: Record<string, string>;
    expires_in_seconds: number;
    maximum_bytes: number;
  };
};

export type DocumentRunRecord = Record<string, unknown> & {
  run_id: string;
  status: string;
  stage: string;
  filename?: string;
  document_class?: string;
  confidence?: number;
  review_required?: boolean;
  model_version?: string;
  lineage_receipt_sha256?: string;
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

export async function putDocumentBytesApi(
  upload: DocumentUploadResponse["upload"],
  bytes: ArrayBuffer,
): Promise<void> {
  const form = new FormData();
  Object.entries(upload.fields).forEach(([key, value]) => form.append(key, value));
  form.append(
    "file",
    new Blob([bytes], { type: upload.fields["Content-Type"] ?? "application/octet-stream" }),
  );
  let response: Response;
  try {
    response = await fetch(upload.url, {
      method: upload.method,
      body: form,
    });
  } catch {
    throw new ApiError(
      0,
      null,
      "The browser could not reach the governed S3 intake boundary. Refresh and retry. No source bytes were accepted.",
    );
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      null,
      `The governed S3 intake boundary rejected the upload (${response.status}).`,
    );
  }
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

export type PublicAcquisitionRecord = {
  contract: "compass.public-acquisition.v1";
  run_id: string;
  source_id: string;
  source_label?: string;
  source?: string;
  status: "completed" | "failed" | "running";
  stage: string;
  started_at: string;
  updated_at: string;
  watermark?: string | null;
  snapshot_sha256?: string;
  record_count?: number;
  total_available?: number;
  profile?: "quick" | "standard" | "deep";
  requested_records?: number;
  pages_fetched?: number;
  source_response_bytes?: number;
  duration_ms?: number;
  added_records?: number;
  changed_records?: number;
  unchanged_records?: number;
  not_observed_records?: number;
  has_more_source_pages?: boolean;
  review_flag_count?: number;
  review_flags?: Array<{
    source_record_id: string;
    recipient_name?: string | null;
    award_amount_usd?: number | null;
    last_modified_at?: string | null;
    source_url?: string | null;
    reasons: string[];
  }>;
  record_preview?: Array<{
    source_id?: string;
    source_record_id: string;
    record_type?: string;
    title?: string;
    description?: string;
    recipient_name?: string;
    award_amount_usd?: number;
    award_type?: string;
    published_date?: string;
    last_modified_at?: string;
    end_date?: string;
    organizations?: string[];
    topics?: string[];
    award_ids?: string[];
    status?: string;
    citation_count?: number;
    source_url?: string;
    document_url?: string;
    document_title?: string;
    identity_keys?: string[];
  }>;
  identity_summary?: {
    indexed_records: number;
    identity_key_count: number;
    link_method: string;
    governance_owner: string;
    governance_steward?: string;
    classification?: string;
  };
  classification_status?: "completed" | "degraded" | "not-configured";
  classification_summary?: {
    status: "completed";
    run_id: string;
    model_version: string;
    model_registered?: boolean;
    record_count: number;
    class_counts: Record<string, number>;
    review_required_count: number;
    mean_confidence: number;
    artifact_uri: string;
    artifact_sha256?: string;
    preview: Array<{
      source_record_id: string;
      recipient_name?: string | null;
      award_amount_usd?: number | null;
      source_url?: string | null;
      document_class: string;
      confidence: number;
      review_required: boolean;
    }>;
    disclosure?: string;
  } | null;
  poll_mode?: "scheduled-micro-batch";
  scope_disclosure?: string;
  failure_code?: string;
};

export type PublicSourceHealth = {
  source_id: string;
  label: string;
  authority: string;
  endpoint: string;
  cadence_seconds: number;
  data_kind: string;
  model_use: string;
  status: "healthy" | "stale" | "failed" | "awaiting-first-run";
  last_attempt_at?: string | null;
  last_accepted_at?: string | null;
  age_seconds?: number | null;
  success_rate?: number | null;
  average_duration_ms?: number | null;
  latest_run_id?: string | null;
  latest_record_count?: number | null;
  latest_added_records?: number | null;
  latest_changed_records?: number | null;
  latest_review_flag_count?: number | null;
  classification_status?: string | null;
  model_version?: string | null;
  has_more_source_pages?: boolean;
};

export type PublicEvidenceThread = {
  thread_id: string;
  match_type: "exact-identity" | "explainable-candidate";
  identity_key?: string | null;
  match_score: number;
  review_status: "verified-key" | "analyst-review";
  explanation: string;
  shared_terms: string[];
  owner: string;
  steward: string;
  facts: Array<{
    source_id: string;
    source_label: string;
    run_id: string;
    record_id: string;
    record_type: string;
    title: string;
    source_url?: string;
    document_url?: string;
    model_version?: string;
    document_class?: string;
  }>;
};

export type PublicAcquisitionList = {
  contract: "compass.public-acquisition-list.v1";
  mode: "live" | "replay";
  generated_at: string;
  schedule: string;
  source_transport: string;
  display_refresh?: string;
  source_health?: PublicSourceHealth[];
  evidence_threads?: PublicEvidenceThread[];
  acquisitions: PublicAcquisitionRecord[];
};

export async function getPublicAcquisitionsApi(): Promise<PublicAcquisitionList> {
  if (USE_MOCK) {
    return {
      contract: "compass.public-acquisition-list.v1",
      mode: "replay",
      generated_at: new Date().toISOString(),
      schedule: "rate(5 minutes)",
      source_transport: "Replay of bounded HTTPS polling, then Kinesis change events",
      acquisitions: [],
    };
  }
  return fetchJson<PublicAcquisitionList>("/public-intelligence/acquisitions", {
    cache: "no-store",
  });
}

export async function postPublicAcquisitionRunApi(
  profile: "quick" | "standard" | "deep" = "standard",
): Promise<PublicAcquisitionRecord> {
  if (USE_MOCK) throw new ApiError(409, { error: "live_acquisition_unavailable_in_replay" });
  return fetchJson<PublicAcquisitionRecord>("/public-intelligence/acquisitions/run", {
    method: "POST",
    body: JSON.stringify({ profile }),
  });
}

export async function postPublicSourceRunApi(
  sourceId: string,
  profile: "quick" | "standard" | "deep" = "standard",
): Promise<PublicAcquisitionRecord> {
  if (USE_MOCK) throw new ApiError(409, { error: "live_acquisition_unavailable_in_replay" });
  return fetchJson<PublicAcquisitionRecord>(
    `/public-intelligence/sources/${encodeURIComponent(sourceId)}/run`,
    { method: "POST", body: JSON.stringify({ profile }) },
  );
}

// ---------------------------------------------------------------------------
// Unified operations
// ---------------------------------------------------------------------------

const OPERATIONS_REPLAY_NOW = "2026-08-12T21:55:00.000Z";
const OPERATIONS_REPLAY_ACKNOWLEDGED = new Set<string>();
const HASH_A = "1e93c59fcf8d4d8d4797d7c657938ad9bf81239df68e094cbbe5c4d996f434ba";
const HASH_B = "97d350c918a49e3fb0f67d215213c331e2eed3689de4cc2bcf651f9d92ab3bd4";
const HASH_C = "e833af3876e8ac0523573661845829a68661392871c93bec1b30d919758f927c";

const OPERATIONS_REPLAY_RUNS: OperationsRunSummary[] = [
  {
    run_id: "doc-4af2-replay",
    run_kind: "document_intake",
    label: "ONR technical report intake",
    status: "completed",
    current_stage: "gold-published",
    started_at: "2026-08-12T21:41:03.000Z",
    updated_at: "2026-08-12T21:41:11.000Z",
    completed_at: "2026-08-12T21:41:11.000Z",
    completed_stages: 7,
    stage_count: 7,
    source: { id: "technical-report.txt", label: "technical-report.txt", kind: "document", uri: "source://document/technical-report.txt", sha256: HASH_A, version: "1" },
    model: { id: "doc-nb-f828a29acd1e", label: "Document taxonomy champion", kind: "model_version", sha256: HASH_B, version: "doc-nb-f828a29acd1e" },
    consumer: { id: "document-gold", label: "Governed document evidence", kind: "gold_dataset", uri: "lake://documents/gold/doc-4af2-replay" },
    counts: { input_records: 1, output_records: 1, quarantined_records: 0, artifacts: 4 },
  },
  {
    run_id: "acq-usaspending-replay",
    run_kind: "public_acquisition",
    label: "USAspending incremental acquisition",
    status: "running",
    current_stage: "normalize",
    started_at: "2026-08-12T21:53:40.000Z",
    updated_at: "2026-08-12T21:54:48.000Z",
    completed_at: null,
    completed_stages: 3,
    stage_count: 6,
    source: { id: "usaspending", label: "USAspending API", kind: "public_api", uri: "https://api.usaspending.gov/", sha256: HASH_C, version: "2026-08-12T21:53:40Z" },
    model: null,
    consumer: { id: "public-evidence-snapshot", label: "Public evidence snapshot", kind: "serving_projection", uri: "evidence://public-intelligence/latest" },
    counts: { input_records: 1276, output_records: 940, quarantined_records: 8, artifacts: 3 },
  },
  {
    run_id: "drift-doc-replay",
    run_kind: "model_drift",
    label: "Document classifier drift evaluation",
    status: "completed",
    current_stage: "review-task-created",
    started_at: "2026-08-12T21:37:18.000Z",
    updated_at: "2026-08-12T21:37:20.000Z",
    completed_at: "2026-08-12T21:37:20.000Z",
    completed_stages: 4,
    stage_count: 4,
    source: { id: "inference-window-2026-08-12", label: "24 hour inference window", kind: "inference_window", sha256: HASH_B, version: "2026-08-12" },
    model: { id: "doc-nb-f828a29acd1e", label: "Document taxonomy champion", kind: "model_version", sha256: HASH_C, version: "doc-nb-f828a29acd1e" },
    consumer: { id: "review-drift-doc", label: "Model review task", kind: "human_review", uri: "review://model-drift/drift-doc-replay" },
    counts: { input_records: 240, output_records: 240, quarantined_records: 0, artifacts: 2 },
  },
];

function replayStage(
  stageId: string,
  sequence: number,
  label: string,
  system: string,
  status: OperationsLineageStage["status"],
  detail: string,
  overrides: Partial<OperationsLineageStage> = {},
): OperationsLineageStage {
  const complete = status === "completed" || status === "quarantined" || status === "failed";
  const updatedAt = `2026-08-12T21:${String(40 + sequence).padStart(2, "0")}:04.000Z`;
  return {
    stage_id: stageId,
    sequence,
    label,
    system,
    status,
    updated_at: updatedAt,
    started_at: status === "pending" ? null : `2026-08-12T21:${String(40 + sequence).padStart(2, "0")}:03.000Z`,
    completed_at: complete ? updatedAt : null,
    duration_ms: complete ? 920 : null,
    source_sha256: HASH_A,
    input_sha256: sequence === 1 ? HASH_A : HASH_B,
    output_sha256: complete ? HASH_C : null,
    record_count: 1,
    artifact_count: complete ? 1 : null,
    receipt: complete ? `receipt://replay/${stageId}/${HASH_C.slice(0, 16)}` : null,
    attempt: 1,
    actor: "replay.fixture@compass.demo",
    source_revision: "replay-fixture",
    failure_code: null,
    detail,
    ...overrides,
  };
}

const OPERATIONS_REPLAY_STAGES: Record<string, OperationsLineageStage[]> = {
  "doc-4af2-replay": [
    replayStage("source", 1, "Source accepted", "Browser to S3", "completed", "The selected bytes were hash-bound before processing."),
    replayStage("event", 2, "Event detected", "Amazon EventBridge", "completed", "The immutable object event started one Document Intake Run."),
    replayStage("bronze", 3, "Bronze retained", "AWS Lambda and Amazon S3", "completed", "Original bytes and extraction metadata were retained for replay."),
    replayStage("quality", 4, "Quality evaluated", "Document quality gate", "completed", "Media type, extraction, size, and sensitive-pattern checks passed."),
    replayStage("silver", 5, "Silver normalized", "Document normalization", "completed", "Text and metadata were normalized under the document contract."),
    replayStage("model", 6, "Model executed", "Document classifier", "completed", "The deployed champion classified the normalized document.", { input_sha256: HASH_C, output_sha256: HASH_B }),
    replayStage("gold", 7, "Gold published", "Governed evidence lake", "completed", "Classification and provenance were published to the consumer projection."),
  ],
  "acq-usaspending-replay": [
    replayStage("plan", 1, "Increment planned", "Public acquisition control", "completed", "The prior watermark and bounded query window were sealed."),
    replayStage("request", 2, "Source pages fetched", "USAspending connector", "completed", "Public API pages were retained as immutable response parts.", { record_count: 1276 }),
    replayStage("raw", 3, "Raw snapshot retained", "Amazon S3", "completed", "Response parts and source request metadata were checksummed.", { record_count: 1276, artifact_count: 3 }),
    replayStage("normalize", 4, "Records normalizing", "Public evidence adapter", "running", "Canonical minimization and source identity matching are in progress.", { record_count: 948, input_sha256: HASH_C, output_sha256: null, receipt: null }),
    replayStage("diff", 5, "Change set", "Snapshot differ", "pending", "Added, changed, unchanged, and removed records will be counted."),
    replayStage("publish", 6, "Serving projection", "Public intelligence API", "pending", "Only an accepted snapshot can replace the current projection."),
  ],
  "drift-doc-replay": [
    replayStage("window", 1, "Inference window sealed", "Model monitoring", "completed", "A bounded inference window was linked to the Champion baseline.", { record_count: 240 }),
    replayStage("evaluate", 2, "Drift evaluated", "Document model monitor", "completed", "Class PSI, vocabulary coverage, and mean confidence crossed policy thresholds.", { record_count: 240 }),
    replayStage("signal", 3, "Signal emitted", "Operations signals", "completed", "A critical review signal was created without changing the Champion."),
    replayStage("review", 4, "Review task created", "Human model gate", "completed", "Retraining may create a Candidate, but promotion still requires approval."),
  ],
};

function replayOperationsSummary(): OperationsSummaryResponse {
  return {
    contract: "compass.operations.summary.v1",
    mode: "replay",
    generated_at: OPERATIONS_REPLAY_NOW,
    counts: { runs_total: 3, runs_active: 1, runs_attention: 1, signals_unread: replayUnreadCount() },
    runs: structuredClone(OPERATIONS_REPLAY_RUNS),
    source_watermarks: [
      {
        source_id: "usaspending",
        label: "USAspending API",
        status: "running",
        last_attempt_at: "2026-08-12T21:53:40.000Z",
        last_accepted_at: "2026-08-12T20:00:00.000Z",
        watermark: "2026-08-12T20:00:00Z",
        added_records: 31,
        changed_records: 7,
        unchanged_records: 902,
        not_observed_records: 0,
        run_id: "acq-usaspending-replay",
      },
    ],
    disclosure: "Replay fixture. No cloud operation was performed.",
  };
}

function replaySignalList(): OperationsSignalsResponse {
  const base: OperationsSignalsResponse["signals"] = [
    {
      event_id: "signal-drift-replay",
      signal_type: "model_drift",
      severity: "critical",
      title: "Document classifier drift requires review",
      message: "Class PSI and vocabulary shift crossed the governed monitoring thresholds. The Champion remains unchanged.",
      status: "open",
      occurred_at: "2026-08-12T21:37:20.000Z",
      updated_at: "2026-08-12T21:37:20.000Z",
      run_id: "drift-doc-replay",
      run_kind: "model_drift",
      href: "/admin/lineage/?run=drift-doc-replay",
      source: "Model monitoring replay",
      deliveries: [
        { channel: "in_app", state: "delivered", attempted_at: "2026-08-12T21:37:20.000Z", delivered_at: "2026-08-12T21:37:20.000Z", detail: null },
        { channel: "email", state: "not_configured", attempted_at: null, delivered_at: null, detail: "Email is not configured in replay." },
      ],
      acknowledged_at: null,
      acknowledged_by: null,
    },
    {
      event_id: "signal-public-replay",
      signal_type: "public_acquisition",
      severity: "info",
      title: "USAspending increment is processing",
      message: "The connector retained 1,276 source records and is normalizing the current increment.",
      status: "open",
      occurred_at: "2026-08-12T21:54:48.000Z",
      updated_at: "2026-08-12T21:54:48.000Z",
      run_id: "acq-usaspending-replay",
      run_kind: "public_acquisition",
      href: "/admin/lineage/?run=acq-usaspending-replay",
      source: "Public acquisition replay",
      deliveries: [{ channel: "in_app", state: "delivered", attempted_at: "2026-08-12T21:54:48.000Z", delivered_at: "2026-08-12T21:54:48.000Z", detail: null }],
      acknowledged_at: null,
      acknowledged_by: null,
    },
    {
      event_id: "signal-document-replay",
      signal_type: "document_intake",
      severity: "info",
      title: "Document evidence published",
      message: "The technical report completed quality, classification, and Gold publication with its source digest intact.",
      status: "acknowledged",
      occurred_at: "2026-08-12T21:41:11.000Z",
      updated_at: "2026-08-12T21:42:00.000Z",
      run_id: "doc-4af2-replay",
      run_kind: "document_intake",
      href: "/admin/lineage/?run=doc-4af2-replay",
      source: "Document workflow replay",
      deliveries: [{ channel: "in_app", state: "delivered", attempted_at: "2026-08-12T21:41:11.000Z", delivered_at: "2026-08-12T21:41:11.000Z", detail: null }],
      acknowledged_at: "2026-08-12T21:42:00.000Z",
      acknowledged_by: "poweruser@compass.demo",
    },
  ];

  const signals = base.map((signal) => {
    if (!OPERATIONS_REPLAY_ACKNOWLEDGED.has(signal.event_id)) return signal;
    return {
      ...signal,
      status: "acknowledged" as const,
      acknowledged_at: OPERATIONS_REPLAY_NOW,
      acknowledged_by: "replay.user@compass.demo",
      updated_at: OPERATIONS_REPLAY_NOW,
    };
  });
  return {
    contract: "compass.operations.signals.v1",
    mode: "replay",
    generated_at: OPERATIONS_REPLAY_NOW,
    unread_count: signals.filter((signal) => signal.status === "open").length,
    signals,
    disclosure: "Replay fixture. Acknowledgements change only this browser session and do not represent cloud delivery.",
  };
}

function replayUnreadCount(): number {
  const ids = ["signal-drift-replay", "signal-public-replay"];
  return ids.filter((id) => !OPERATIONS_REPLAY_ACKNOWLEDGED.has(id)).length;
}

function replayOperationsLineage(runId: string): OperationsLineageResponse {
  const run = OPERATIONS_REPLAY_RUNS.find((candidate) => candidate.run_id === runId);
  const stages = OPERATIONS_REPLAY_STAGES[runId];
  if (!run || !stages) throw new ApiError(404, { error: "operations_run_not_found" });
  return {
    contract: "compass.operations.lineage.v1",
    mode: "replay",
    generated_at: OPERATIONS_REPLAY_NOW,
    run: structuredClone(run),
    stages: structuredClone(stages),
    edges: stages.slice(1).map((stage, index) => ({
      from_stage: stages[index].stage_id,
      to_stage: stage.stage_id,
      label: "receipt-bound transition",
    })),
    disclosure: "Replay fixture. Stage progression is source-controlled and does not represent a cloud execution.",
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredOperationsRecord(value: unknown, contract: string, arrayKey?: string): Record<string, unknown> {
  if (!isRecord(value) || value.contract !== contract || value.mode !== "live") {
    throw new ApiError(502, value, `${contract}_invalid`);
  }
  if (arrayKey && !Array.isArray(value[arrayKey])) throw new ApiError(502, value, `${contract}_${arrayKey}_invalid`);
  return value;
}

function textValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function nullableText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function operationsRunStatus(value: unknown): OperationsRunSummary["status"] {
  const status = textValue(value).toLowerCase();
  if (["queued", "running", "completed", "quarantined", "failed", "expired", "cancelled"].includes(status)) {
    return status as OperationsRunSummary["status"];
  }
  return "running";
}

function operationsStageStatus(value: unknown): OperationsLineageStage["status"] {
  const status = textValue(value).toLowerCase();
  if (["pending", "running", "completed", "quarantined", "failed", "skipped"].includes(status)) {
    return status as OperationsLineageStage["status"];
  }
  return "pending";
}

function operationsLabel(value: string): string {
  const normalized = value.replaceAll("_", " ").replaceAll("-", " ").trim();
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : "Operational run";
}

function normalizeSignal(raw: unknown): OperationsSignalsResponse["signals"][number] | null {
  if (!isRecord(raw)) return null;
  const eventId = textValue(raw.event_id);
  if (!eventId) return null;
  const detail = isRecord(raw.detail) ? raw.detail : {};
  const rawSeverity = textValue(raw.severity, "medium").toLowerCase();
  const severity = rawSeverity === "critical"
    ? "critical"
    : ["high", "medium", "warning"].includes(rawSeverity)
      ? "warning"
      : "info";
  const rawStatus = textValue(raw.status, "open").toLowerCase();
  const status = rawStatus === "acknowledged" ? "acknowledged" : rawStatus === "resolved" ? "resolved" : "open";
  const rawDelivery = isRecord(raw.delivery) ? raw.delivery : {};
  const deliveryChannel = textValue(rawDelivery.channel, "in-app").replaceAll("-", "_");
  const channel = ["in_app", "email", "sns", "webhook"].includes(deliveryChannel)
    ? deliveryChannel as "in_app" | "email" | "sns" | "webhook"
    : "in_app";
  const rawDeliveryState = textValue(rawDelivery.status, "recorded").toLowerCase();
  const deliveryState = ["recorded", "published", "delivered"].includes(rawDeliveryState)
    ? rawDeliveryState as "recorded" | "published" | "delivered"
    : rawDeliveryState === "failed"
      ? "failed"
      : rawDeliveryState === "not_configured"
        ? "not_configured"
        : "pending";
  const runId = nullableText(raw.run_id);
  const evidenceUri = nullableText(raw.evidence_uri);
  const occurredAt = textValue(raw.created_at, textValue(raw.occurred_at, textValue(raw.updated_at, new Date().toISOString())));
  return {
    event_id: eventId,
    signal_type: textValue(raw.category, "operations"),
    severity,
    title: textValue(raw.title, "Operational signal"),
    message: textValue(raw.message, "A retained operational event requires review."),
    status,
    occurred_at: occurredAt,
    updated_at: textValue(raw.updated_at, occurredAt),
    run_id: runId,
    run_kind: nullableText(detail.run_kind),
    href: evidenceUri?.startsWith("/") ? evidenceUri : runId ? `/admin/lineage/?run=${encodeURIComponent(runId)}` : null,
    source: textValue(raw.category, "operations"),
    deliveries: [{
      channel,
      state: deliveryState,
      attempted_at: nullableText(raw.updated_at),
      delivered_at: deliveryState === "delivered" ? nullableText(raw.updated_at) : null,
      detail: evidenceUri ? `Evidence: ${evidenceUri}` : null,
    }],
    acknowledged_at: nullableText(raw.acknowledged_at),
    acknowledged_by: nullableText(raw.acknowledged_by),
  };
}

function normalizeRunSummary(raw: unknown): OperationsRunSummary | null {
  if (!isRecord(raw)) return null;
  const runId = textValue(raw.run_id);
  if (!runId) return null;
  const runKind = textValue(raw.run_kind, "operational-run");
  const status = operationsRunStatus(raw.status);
  const updatedAt = textValue(raw.updated_at, new Date().toISOString());
  const stageCount = Math.max(0, Math.trunc(finiteNumber(raw.stage_count) ?? 0));
  const sourceSha = nullableText(raw.source_sha256);
  const terminal = ["completed", "quarantined", "failed", "expired", "cancelled"].includes(status);
  return {
    run_id: runId,
    run_kind: runKind,
    label: operationsLabel(runKind),
    status,
    current_stage: textValue(raw.terminal_stage, terminal ? "terminal receipt" : "processing"),
    started_at: textValue(raw.started_at, updatedAt),
    updated_at: updatedAt,
    completed_at: terminal ? textValue(raw.completed_at, updatedAt) : null,
    completed_stages: terminal ? stageCount : Math.max(0, stageCount - 1),
    stage_count: stageCount,
    source: {
      id: textValue(raw.source, runId),
      label: textValue(raw.source, "Recorded source"),
      kind: "operational_source",
      sha256: sourceSha,
    },
    model: null,
    consumer: null,
    counts: { input_records: null, output_records: null, quarantined_records: null, artifacts: null },
  };
}

function normalizeStage(raw: unknown): OperationsLineageStage | null {
  if (!isRecord(raw)) return null;
  const stageId = textValue(raw.stage_id);
  if (!stageId) return null;
  const detail = isRecord(raw.detail) ? raw.detail : {};
  const status = operationsStageStatus(raw.status);
  const updatedAt = nullableText(raw.updated_at);
  const terminal = ["completed", "quarantined", "failed", "skipped"].includes(status);
  const destination = nullableText(raw.destination);
  const source = nullableText(raw.source);
  return {
    stage_id: stageId,
    sequence: Math.max(0, Math.trunc(finiteNumber(raw.sequence) ?? 0)),
    label: textValue(raw.label, operationsLabel(stageId)),
    system: destination ?? source ?? operationsLabel(textValue(raw.run_kind, "operations")),
    status,
    updated_at: updatedAt ?? textValue(raw.updated_at, new Date().toISOString()),
    started_at: nullableText(detail.started_at),
    completed_at: terminal ? updatedAt : null,
    duration_ms: finiteNumber(detail.duration_ms),
    source_sha256: nullableText(raw.source_sha256),
    input_sha256: nullableText(raw.input_sha256),
    output_sha256: nullableText(raw.output_sha256),
    record_count: finiteNumber(detail.record_count) ?? finiteNumber(detail.accepted_records),
    artifact_count: finiteNumber(detail.artifact_count),
    receipt: nullableText(raw.receipt_sha256) ? `receipt://operations/${textValue(raw.receipt_sha256)}` : null,
    attempt: Math.max(1, Math.trunc(finiteNumber(detail.attempt) ?? 1)),
    actor: nullableText(raw.actor),
    source_revision: nullableText(detail.source_revision),
    failure_code: nullableText(detail.failure_code),
    detail: [source ? `Input ${source}.` : "", destination ? `Output ${destination}.` : "", textValue(detail.schema) ? `Contract ${textValue(detail.schema)}.` : ""].filter(Boolean).join(" ") || "The authoritative stage receipt is retained in the operations projection.",
  };
}

function normalizeLiveSignals(response: unknown): OperationsSignalsResponse {
  const raw = requiredOperationsRecord(response, "compass.operational-signals.v1", "signals");
  const signals = (raw.signals as unknown[]).map(normalizeSignal).filter((item): item is NonNullable<typeof item> => Boolean(item));
  return {
    contract: "compass.operations.signals.v1",
    mode: "live",
    generated_at: textValue(raw.generated_at, new Date().toISOString()),
    unread_count: Math.max(0, Math.trunc(finiteNumber(raw.unacknowledged) ?? signals.filter((signal) => signal.status === "open").length)),
    signals,
    disclosure: textValue(raw.delivery_disclosure, "In-app operations evidence is loaded from the protected API."),
  };
}

function normalizeLiveSummary(response: unknown): OperationsSummaryResponse {
  const raw = requiredOperationsRecord(response, "compass.operational-summary.v1", "runs");
  const runs = (raw.runs as unknown[]).map(normalizeRunSummary).filter((item): item is OperationsRunSummary => Boolean(item));
  const rawCounts = isRecord(raw.counts) ? raw.counts : {};
  const acquisition = isRecord(raw.latest_public_acquisition) ? raw.latest_public_acquisition : null;
  const acquisitionAttempt = isRecord(raw.latest_public_acquisition_attempt) ? raw.latest_public_acquisition_attempt : acquisition;
  const sourceWatermarks: OperationsSummaryResponse["source_watermarks"] = acquisition ? [{
    source_id: textValue(acquisition.source_id, "public-acquisition"),
    label: operationsLabel(textValue(acquisition.source_id, "public-acquisition")),
    status: acquisitionAttempt && operationsRunStatus(acquisitionAttempt.status) === "running" ? "running" : acquisitionAttempt && operationsRunStatus(acquisitionAttempt.status) === "failed" ? "failed" : "current",
    last_attempt_at: acquisitionAttempt ? nullableText(acquisitionAttempt.started_at) : nullableText(acquisition.started_at),
    last_accepted_at: nullableText(acquisition.updated_at),
    watermark: nullableText(acquisition.watermark),
    added_records: finiteNumber(acquisition.added_records) ?? 0,
    changed_records: finiteNumber(acquisition.changed_records) ?? 0,
    unchanged_records: finiteNumber(acquisition.unchanged_records) ?? 0,
    not_observed_records: finiteNumber(acquisition.not_observed_records) ?? 0,
    run_id: acquisitionAttempt ? nullableText(acquisitionAttempt.run_id) : nullableText(acquisition.run_id),
  }] : [];
  return {
    contract: "compass.operations.summary.v1",
    mode: "live",
    generated_at: textValue(raw.generated_at, new Date().toISOString()),
    counts: {
      runs_total: Math.max(0, Math.trunc(finiteNumber(rawCounts.lineage_runs) ?? runs.length)),
      runs_active: runs.filter((run) => run.status === "running" || run.status === "queued").length,
      runs_attention: runs.filter((run) => ["failed", "quarantined", "expired"].includes(run.status)).length,
      signals_unread: Math.max(0, Math.trunc(finiteNumber(rawCounts.unacknowledged_signals) ?? 0)),
    },
    runs,
    source_watermarks: sourceWatermarks,
    disclosure: textValue(raw.disclosure, "Live operational evidence from the protected projection."),
  };
}

function normalizeLiveLineage(response: unknown, expectedRunId: string): OperationsLineageResponse {
  const raw = requiredOperationsRecord(response, "compass.operational-lineage.v1", "stages");
  const runId = textValue(raw.run_id);
  if (runId !== expectedRunId) throw new ApiError(502, response, "operations_lineage_run_mismatch");
  const stages = (raw.stages as unknown[]).map(normalizeStage).filter((item): item is OperationsLineageStage => Boolean(item)).sort((left, right) => left.sequence - right.sequence);
  if (stages.length === 0) throw new ApiError(502, response, "operations_lineage_stages_empty");
  const status = operationsRunStatus(raw.status);
  const updatedAt = textValue(stages.at(-1)?.completed_at, textValue(raw.generated_at, new Date().toISOString()));
  const sourceUri = nullableText(raw.source);
  const sourceSha = nullableText(raw.source_sha256) ?? stages.find((stage) => stage.source_sha256)?.source_sha256 ?? null;
  const modelId = nullableText(raw.model);
  const consumerId = nullableText(raw.consumer);
  const firstCount = stages.find((stage) => stage.record_count !== null)?.record_count ?? null;
  const lastCount = [...stages].reverse().find((stage) => stage.record_count !== null)?.record_count ?? null;
  const completedStages = stages.filter((stage) => ["completed", "quarantined", "failed", "skipped"].includes(stage.status)).length;
  const run: OperationsRunSummary = {
    run_id: runId,
    run_kind: textValue(raw.run_kind, "operational-run"),
    label: operationsLabel(textValue(raw.run_kind, "operational-run")),
    status,
    current_stage: stages.find((stage) => stage.status === "running")?.stage_id ?? stages.at(-1)?.stage_id ?? "receipt pending",
    started_at: stages[0]?.started_at ?? stages[0]?.completed_at ?? updatedAt,
    updated_at: updatedAt,
    completed_at: ["completed", "quarantined", "failed", "expired", "cancelled"].includes(status) ? updatedAt : null,
    completed_stages: completedStages,
    stage_count: stages.length,
    source: { id: sourceUri ?? runId, label: sourceUri ?? "Recorded source", kind: "operational_source", uri: sourceUri, sha256: sourceSha },
    model: modelId ? { id: modelId, label: modelId, kind: "model_version", version: modelId } : null,
    consumer: consumerId ? { id: consumerId, label: consumerId, kind: "consumer", uri: consumerId } : null,
    counts: {
      input_records: firstCount,
      output_records: lastCount,
      quarantined_records: status === "quarantined" ? lastCount : 0,
      artifacts: stages.filter((stage) => stage.output_sha256).length,
    },
  };
  const rawEdges = Array.isArray(raw.edges) ? raw.edges : [];
  const edges = rawEdges.flatMap((edge) => {
    if (!isRecord(edge)) return [];
    const from = textValue(edge.from);
    const to = textValue(edge.to);
    return from && to ? [{ from_stage: from, to_stage: to, label: "receipt-bound transition" }] : [];
  });
  return {
    contract: "compass.operations.lineage.v1",
    mode: "live",
    generated_at: textValue(raw.generated_at, updatedAt),
    run,
    stages,
    edges,
    disclosure: "Live stage receipts from the protected operational evidence projection.",
  };
}

export async function getOperationsSignals(): Promise<OperationsSignalsResponse> {
  if (USE_MOCK) return replaySignalList();
  const response = await fetchJson<unknown>("/operations/signals?limit=100", { cache: "no-store" });
  return normalizeLiveSignals(response);
}

export async function getOperationsSummary(): Promise<OperationsSummaryResponse> {
  if (USE_MOCK) return replayOperationsSummary();
  const response = await fetchJson<unknown>("/operations/summary", { cache: "no-store" });
  return normalizeLiveSummary(response);
}

export async function getOperationsLineage(runId: string): Promise<OperationsLineageResponse> {
  if (!runId.trim()) throw new ApiError(400, { error: "run_id_required" });
  if (USE_MOCK) return replayOperationsLineage(runId);
  const response = await fetchJson<unknown>(
    `/operations/lineage/${encodeURIComponent(runId)}`,
    { cache: "no-store" },
  );
  return normalizeLiveLineage(response, runId);
}

export async function postOperationsSignalAcknowledge(
  eventId: string,
): Promise<OperationsSignalAcknowledgeResponse> {
  if (!eventId.trim()) throw new ApiError(400, { error: "event_id_required" });
  if (USE_MOCK) {
    const signal = replaySignalList().signals.find((candidate) => candidate.event_id === eventId);
    if (!signal) throw new ApiError(404, { error: "operations_signal_not_found" });
    OPERATIONS_REPLAY_ACKNOWLEDGED.add(eventId);
    return {
      contract: "compass.operations.signal-acknowledgement.v1",
      mode: "replay",
      event_id: eventId,
      status: "acknowledged",
      acknowledged_at: OPERATIONS_REPLAY_NOW,
      acknowledged_by: "replay.user@compass.demo",
    };
  }
  const response = await fetchJson<unknown>(
    `/operations/signals/${encodeURIComponent(eventId)}/acknowledge`,
    { method: "POST", body: "{}" },
  );
  if (!isRecord(response) || response.contract !== "compass.operational-signal.v1" || response.event_id !== eventId || response.status !== "acknowledged") {
    throw new ApiError(502, response, "operations_signal_acknowledgement_mismatch");
  }
  return {
    contract: "compass.operations.signal-acknowledgement.v1",
    mode: "live",
    event_id: eventId,
    status: "acknowledged",
    acknowledged_at: textValue(response.acknowledged_at, textValue(response.updated_at, new Date().toISOString())),
    acknowledged_by: textValue(response.acknowledged_by, "poweruser"),
  };
}

// ---------------------------------------------------------------------------
// Accelerated synthetic demo stream
// ---------------------------------------------------------------------------
type DemoStreamReplayState = {
  sessionId: string;
  startedAtMs: number;
  cadenceSeconds: 1 | 2;
  stoppedAtMs: number | null;
};

let demoStreamReplayState: DemoStreamReplayState | null = null;

function demoStreamStatus(value: unknown): LiveDemoStreamStatus {
  return ["idle", "running", "completed", "stopped", "failed"].includes(String(value))
    ? value as LiveDemoStreamStatus
    : "idle";
}

function normalizeLiveDemoStream(response: unknown): LiveDemoStreamResponse {
  if (!isRecord(response)) throw new ApiError(502, response, "demo_stream_response_invalid");
  const rawSession = isRecord(response.session) ? response.session : {};
  const cadence = finiteNumber(rawSession.cadence_seconds) === 1 ? 1 : 2;
  const streamMode = rawSession.stream_mode === "bounded" ? "bounded" : "continuous";
  const rawTotalEvents = finiteNumber(rawSession.total_events);
  const totalEvents = streamMode === "bounded"
    ? Math.max(0, Math.trunc(rawTotalEvents ?? 0))
    : null;
  const rawEmittedEvents = Math.max(0, Math.trunc(finiteNumber(rawSession.emitted_events) ?? 0));
  const emittedEvents = totalEvents === null
    ? rawEmittedEvents
    : Math.min(totalEvents, rawEmittedEvents);
  const rawLatest = isRecord(response.latest_event) ? response.latest_event : null;
  const rawSafeguards = isRecord(response.safeguards) ? response.safeguards : null;
  return {
    contract: "compass.demo-stream.v1",
    mode: response.mode === "replay" ? "replay" : "live",
    generated_at: textValue(response.generated_at, new Date().toISOString()),
    stream_kind: response.stream_kind === "continuous-synthetic"
      ? "continuous-synthetic"
      : response.stream_kind === "accelerated-synthetic"
        ? "accelerated-synthetic"
        : undefined,
    session: {
      session_id: nullableText(rawSession.session_id),
      status: demoStreamStatus(rawSession.status),
      stream_mode: streamMode,
      cadence_seconds: cadence,
      total_events: totalEvents,
      emitted_events: emittedEvents,
      started_at: nullableText(rawSession.started_at),
      updated_at: nullableText(rawSession.updated_at),
      completed_at: nullableText(rawSession.completed_at),
      execution_chunk_number: Math.max(
        0,
        Math.trunc(finiteNumber(rawSession.execution_chunk_number) ?? 0),
      ),
    },
    latest_event: rawLatest ? {
      sequence: Math.max(0, Math.trunc(finiteNumber(rawLatest.sequence) ?? emittedEvents)),
      run_id: nullableText(rawLatest.run_id),
      event_id: textValue(rawLatest.event_id, `demo-stream-event-${emittedEvents}`),
      occurred_at: textValue(rawLatest.occurred_at, new Date().toISOString()),
      message: textValue(rawLatest.message, "Synthetic event accepted by the accelerated demo path."),
    } : null,
    safeguards: rawSafeguards ? {
      operator_stop_required: rawSafeguards.operator_stop_required !== false,
      workflow_chunk_events: Math.max(1, Math.trunc(finiteNumber(rawSafeguards.workflow_chunk_events) ?? 250)),
      raw_retention_days: Math.max(1, Math.trunc(finiteNumber(rawSafeguards.raw_retention_days) ?? 7)),
      estimated_events_per_hour: Math.max(0, Math.trunc(finiteNumber(rawSafeguards.estimated_events_per_hour) ?? (3600 / cadence))),
    } : undefined,
    disclosure: textValue(
      response.disclosure,
      "Continuous synthetic events use the deployed intake path until an operator stops the session.",
    ),
  };
}

function replayLiveDemoStream(): LiveDemoStreamResponse {
  const now = Date.now();
  const state = demoStreamReplayState;
  if (!state) {
    return {
      contract: "compass.demo-stream.v1",
      mode: "replay",
      generated_at: new Date(now).toISOString(),
      session: {
        session_id: null,
        status: "idle",
        stream_mode: "continuous",
        cadence_seconds: 2,
        total_events: null,
        emitted_events: 0,
        started_at: null,
        updated_at: null,
        completed_at: null,
        execution_chunk_number: 0,
      },
      latest_event: null,
      safeguards: {
        operator_stop_required: true,
        workflow_chunk_events: 250,
        raw_retention_days: 7,
        estimated_events_per_hour: 1800,
      },
      disclosure: "Deterministic browser replay. Live deployment uses the protected AWS intake path.",
    };
  }
  const effectiveNow = state.stoppedAtMs ?? now;
  const emitted = Math.max(
    0,
    Math.floor((effectiveNow - state.startedAtMs) / (state.cadenceSeconds * 1000)),
  );
  const status: LiveDemoStreamStatus = state.stoppedAtMs ? "stopped" : "running";
  const occurredAtMs = emitted > 0
    ? state.startedAtMs + emitted * state.cadenceSeconds * 1000
    : state.startedAtMs;
  return {
    contract: "compass.demo-stream.v1",
    mode: "replay",
    generated_at: new Date(now).toISOString(),
    session: {
      session_id: state.sessionId,
      status,
      stream_mode: "continuous",
      cadence_seconds: state.cadenceSeconds,
      total_events: null,
      emitted_events: emitted,
      started_at: new Date(state.startedAtMs).toISOString(),
      updated_at: new Date(occurredAtMs).toISOString(),
      completed_at: status === "running" ? null : new Date(effectiveNow).toISOString(),
      execution_chunk_number: Math.floor(emitted / 250) + 1,
    },
    latest_event: emitted > 0 ? {
      sequence: emitted,
      run_id: `run-${state.sessionId}-${emitted}`,
      event_id: `${state.sessionId}:${emitted}`,
      occurred_at: new Date(occurredAtMs).toISOString(),
      message: `Continuous synthetic event ${emitted} accepted by the deployed demo path.`,
    } : null,
    safeguards: {
      operator_stop_required: true,
      workflow_chunk_events: 250,
      raw_retention_days: 7,
      estimated_events_per_hour: 3600 / state.cadenceSeconds,
    },
    disclosure: "Deterministic browser replay. Live deployment uses the protected AWS intake path.",
  };
}

export async function getLiveDemoStream(): Promise<LiveDemoStreamResponse> {
  if (USE_MOCK) return replayLiveDemoStream();
  return normalizeLiveDemoStream(
    await fetchJson<unknown>("/demo-stream", { cache: "no-store" }),
  );
}

export async function postLiveDemoStreamStart(
  request: LiveDemoStreamStartRequest,
): Promise<LiveDemoStreamResponse> {
  if (USE_MOCK) {
    demoStreamReplayState = {
      sessionId: `demo-${Date.now().toString(36)}`,
      startedAtMs: Date.now(),
      cadenceSeconds: request.cadence_seconds,
      stoppedAtMs: null,
    };
    return replayLiveDemoStream();
  }
  return normalizeLiveDemoStream(await fetchJson<unknown>("/demo-stream/start", {
    method: "POST",
    body: JSON.stringify(request),
  }));
}

export async function postLiveDemoStreamStop(
  request: LiveDemoStreamStopRequest,
): Promise<LiveDemoStreamResponse> {
  if (USE_MOCK) {
    if (demoStreamReplayState?.sessionId === request.session_id) {
      demoStreamReplayState.stoppedAtMs = Date.now();
    }
    return replayLiveDemoStream();
  }
  return normalizeLiveDemoStream(await fetchJson<unknown>("/demo-stream/stop", {
    method: "POST",
    body: JSON.stringify(request),
  }));
}

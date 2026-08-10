/**
 * Compass API contract types — shared by `lib/api.ts` (the live/mock client)
 * and `lib/mock/*` (fixtures). Field names deliberately mirror the Postgres
 * column names in `db/migrations/001_schema.sql` (snake_case) since
 * docs/CONTRACTS.md locks the DB shape but not a separate wire-format for
 * the API — mirroring the DB columns keeps this the single source of truth
 * every subsystem (Lambdas, frontend) can build against without guessing.
 *
 * Kept in its own module (no imports from lib/api.ts or lib/mock/*) so both
 * sides can import it without a circular dependency.
 */

// ---------------------------------------------------------------------------
// Shared / cross-cutting
// ---------------------------------------------------------------------------

/** The two demo personas from docs/CONTRACTS.md "RLS". */
export type Role = "poweruser" | "viewer";

export type QualityRuleResult = {
  rule: string;
  passed_rows: number;
  failed_rows: number;
  score: number;
  details?: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// GET /me  (element 1)
// ---------------------------------------------------------------------------
export type MeResponse = {
  sub: string;
  email: string;
  display_name: string;
  role: Role;
  org_unit: string;
  groups: string[];
};

// ---------------------------------------------------------------------------
// GET /catalog, GET /catalog/{id}/lineage  (element 4)
// ---------------------------------------------------------------------------
export type CatalogEntry = {
  /** == batch_id; also the {id} used by GET /catalog/{id}/lineage */
  id: string;
  batch_id: string;
  run_id: string;
  dataset_name: string;
  source_file: string;
  program_area: string;
  org_unit: string;
  fiscal_year: number;
  row_count: number;
  /** null when the caller's role is masked out of $ figures (viewer/CLS) */
  amount_usd: number | null;
  quality_score: number;
  quality_rules: QualityRuleResult[];
  classification_band: string;
  ingested_at: string; // ISO 8601
  owner: string;
};
export type CatalogResponse = { datasets: CatalogEntry[] };

export type LineageNode = {
  run_id: string;
  node_id: string;
  kind: "source" | "stage" | "table" | "model" | "dashboard";
  label: string;
  meta?: Record<string, unknown>;
};
export type LineageEdge = { run_id: string; from_node: string; to_node: string };
export type LineageResponse = { run_id: string; nodes: LineageNode[]; edges: LineageEdge[] };

// ---------------------------------------------------------------------------
// POST /ingest/simulate, GET /ingest/status  (element 3)
// ---------------------------------------------------------------------------
export type IngestSimulateRequest = { source_file?: string };
export type IngestSimulateResponse = {
  batch_id: string;
  run_id: string;
  source_file: string;
  status: "queued" | "running";
  triggered_at: string;
};

export type IngestBatch = {
  batch_id: string;
  run_id: string;
  source_file: string;
  ingested_at: string;
  status: "queued" | "running" | "passed" | "failed";
  rows_raw: number;
  rows_curated: number;
  quality: QualityRuleResult[];
  overall_score: number;
};
export type IngestStatusResponse = { batches: IngestBatch[] };

// ---------------------------------------------------------------------------
// GET /stream/recent  (element 3, ticker)
// ---------------------------------------------------------------------------
export type StreamRecord = {
  id: string;
  at: string;
  kind: "ingest" | "quality" | "anomaly" | "export" | "approval" | "analytics";
  message: string;
  grant_no?: string;
  org_unit?: string;
};
export type StreamRecentResponse = { records: StreamRecord[] };

// ---------------------------------------------------------------------------
// POST /analytics/run, GET /analytics/{run_id}  (element 5)
// ---------------------------------------------------------------------------
export type AnalyticsRunRequest = {
  program_area?: string;
  fiscal_year?: number;
  k?: number;
};
export type AnalyticsRunResponse = {
  run_id: string;
  kind: "topic_model";
  status: "queued" | "running" | "completed";
};

export type Topic = {
  topic_id: number;
  label: string;
  top_terms: string[];
  trend: { period: string; value: number }[];
  grant_count: number;
  /** null when masked (viewer/CLS) */
  total_funding_usd: number | null;
};
export type AnalyticsRunDetail = {
  run_id: string;
  kind: "topic_model";
  status: "completed";
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  recommendation: string;
  topics: Topic[];
  created_at: string;
};

// ---------------------------------------------------------------------------
// GET /dashboard  (element 6)
// ---------------------------------------------------------------------------
export type DashboardResponse = {
  kpis: {
    total_grants: number;
    /** null when masked (viewer/CLS) */
    total_funding_usd: number | null;
    active_program_areas: number;
    avg_quality_score: number;
    open_anomalies: number;
    pending_approvals: number;
  };
  funding_by_program_area: {
    program_area: string;
    amount_usd: number | null;
    grant_count: number;
  }[];
  funding_by_fiscal_year: { fiscal_year: number; amount_usd: number | null }[];
  quality_trend: { run_id: string; date: string; score: number }[];
  top_topics: { topic_id: number; label: string; weight: number }[];
  org_unit_breakdown: {
    org_unit: string;
    grant_count: number;
    amount_usd: number | null;
  }[];
};

// ---------------------------------------------------------------------------
// POST /chat  (element 6)
// ---------------------------------------------------------------------------
export type ChatMessage = { role: "user" | "assistant"; content: string };
export type ChatRequest = { message: string; history?: ChatMessage[] };
export type ChatCitation = { grant_no: string; title: string; snippet: string };
export type ChatResponse = { answer: string; citations: ChatCitation[]; model: string };

// ---------------------------------------------------------------------------
// GET /anomalies  (element 6)
// ---------------------------------------------------------------------------
export type Anomaly = {
  id: number;
  grant_id: number | null;
  grant_no?: string;
  kind: string;
  severity: "low" | "medium" | "high" | "critical";
  reason: string;
  status: "open" | "acknowledged" | "resolved";
  created_at: string;
};
export type AnomaliesResponse = { anomalies: Anomaly[] };

// ---------------------------------------------------------------------------
// POST /approvals  (element 6)
// ---------------------------------------------------------------------------
export type ApprovalRequest = {
  subject_type: string;
  subject_id: string;
  action: "request" | "approve" | "reject";
  note?: string;
};
export type Approval = {
  id: number;
  subject_type: string;
  subject_id: string;
  state: "pending" | "approved" | "rejected";
  requested_by: string;
  decided_by: string | null;
  decided_at: string | null;
  note: string | null;
  created_at: string;
};
export type ApprovalResponse = { approval: Approval };

// ---------------------------------------------------------------------------
// GET /licenses  (element 6)
// ---------------------------------------------------------------------------
export type License = {
  id: number;
  vendor: string;
  product: string;
  datasets: string[];
  entitlements: string;
  seats_used: number;
  seats_total: number;
  renews_on: string; // ISO date
  owner: string;
  status: "active" | "expiring" | "expired" | "suspended";
};
export type LicensesResponse = { licenses: License[] };

// ---------------------------------------------------------------------------
// POST /export  (element 7)
// ---------------------------------------------------------------------------
export type ExportRequest = {
  format: "csv" | "json" | "parquet";
  filters?: Record<string, unknown>;
  approval_token?: string;
};
export type ExportResponse = {
  export_id: string;
  row_count: number;
  format: "csv" | "json" | "parquet";
  download_url: string;
  audited: true;
};
/** Thrown as ApiError(428, ...) when row_count > EXPORT_MAX_ROWS with no approval_token. */
export type ExportApprovalRequiredBody = {
  error: "approval_required";
  row_count: number;
  max_rows: number;
};

// ---------------------------------------------------------------------------
// GET /openapi.json  (element 7) — pass-through, shape owned by the API itself
// ---------------------------------------------------------------------------
export type OpenApiDoc = Record<string, unknown>;

/**
 * Compass API contract types: shared by `lib/api.ts` (the live/mock client)
 * and `lib/mock/*` (fixtures). Field names deliberately mirror the Postgres
 * column names in `db/migrations/001_schema.sql` (snake_case) since
 * docs/CONTRACTS.md locks the DB shape but not a separate wire-format for
 * the API. Mirroring the DB columns keeps this the single source of truth
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

export type CatalogFieldDefinition = {
  field: string;
  data_type: string;
  definition: string;
  security: string;
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
  steward: string;
  data_dictionary: CatalogFieldDefinition[];
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
export type IngestSimulateRequest = {
  fixture?: "good" | "compatible" | "bad";
  source_file?: string;
};
export type IngestSimulateResponse = {
  batch_id: string;
  run_id: string;
  source_file: string;
  status: "queued" | "running";
  triggered_at: string;
  trigger?: string;
  fixture?: "good" | "compatible" | "bad";
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
  kind: "ingest" | "quality" | "anomaly" | "export" | "approval" | "analytics" | "public-feed";
  message: string;
  grant_no?: string;
  org_unit?: string;
};
export type StreamRecentResponse = { records: StreamRecord[] };

// ---------------------------------------------------------------------------
// Accelerated synthetic demo stream
// ---------------------------------------------------------------------------
export type LiveDemoStreamStatus = "idle" | "running" | "completed" | "stopped" | "failed";
export type LiveDemoStreamMode = "continuous" | "bounded";

export type LiveDemoStreamSession = {
  session_id: string | null;
  status: LiveDemoStreamStatus;
  stream_mode: LiveDemoStreamMode;
  cadence_seconds: 1 | 2;
  total_events: number | null;
  emitted_events: number;
  started_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
  execution_chunk_number: number;
};

export type LiveDemoStreamEvent = {
  sequence: number;
  run_id: string | null;
  event_id: string;
  occurred_at: string;
  message: string;
};

export type LiveDemoStreamResponse = {
  contract: "compass.demo-stream.v1";
  mode: "live" | "replay";
  generated_at: string;
  stream_kind?: "continuous-synthetic" | "accelerated-synthetic";
  session: LiveDemoStreamSession;
  latest_event: LiveDemoStreamEvent | null;
  safeguards?: {
    operator_stop_required: boolean;
    workflow_chunk_events: number;
    raw_retention_days: number;
    estimated_events_per_hour: number;
  };
  disclosure: string;
};

export type LiveDemoStreamStartRequest = {
  cadence_seconds: 1 | 2;
  stream_mode: "continuous";
};

export type LiveDemoStreamStopRequest = {
  session_id: string;
};

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
export type DashboardFilters = {
  program_area?: string;
  fiscal_year?: number;
  org_unit?: string;
  q?: string;
};

export type DashboardAppliedFilters = {
  program_area?: string | null;
  fiscal_year?: number | null;
  org_unit?: string | null;
  q?: string | null;
};

export type DashboardFilterOptions = {
  program_areas: string[];
  fiscal_years: number[];
  org_units: string[];
};

export type DashboardResponse = {
  /** Live responses always include these fields. Optional supports older replay fixtures. */
  filters_applied?: DashboardAppliedFilters;
  filter_options?: DashboardFilterOptions;
  kpis: {
    total_grants: number;
    /** null when masked (viewer/CLS) */
    total_funding_usd: number | null;
    active_program_areas: number;
    avg_quality_score: number | null;
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
  title?: string;
  program_area?: string;
  org_unit?: string;
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
  expires_at?: string | null;
  consumed_at?: string | null;
  consumed_by?: string | null;
};
export type ApprovalResponse = {
  approval: Approval;
  approval_token?: string | null;
  four_eyes?: Record<string, unknown>;
};
export type ApprovalsListResponse = {
  approvals: Approval[];
  actor: string;
  scope: "all_pending" | "requested_by_actor";
  can_decide: boolean;
  four_eyes_enforced: boolean;
  /** Always false. Capability tokens are issued only by an approve action. */
  tokens_included: false;
  generated_at: string;
};

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
  status_stored?: "active" | "expiring" | "expired" | "suspended";
  days_to_renewal?: number | null;
  renewal_alert?: {
    level: "expired" | "critical" | "warning" | "ok";
    days_to_renewal: number | null;
    message: string;
  };
  seat_alert?: {
    level: "critical" | "warning" | "ok";
    utilization_pct: number | null;
    seats_available: number | null;
    message: string;
  };
  needs_action?: boolean;
};
export type LicensesResponse = {
  licenses: License[];
  alerts?: {
    license_id: number;
    vendor: string;
    product: string;
    owner: string;
    kind: "renewal" | "seats";
    level: "expired" | "critical" | "warning";
    message: string;
    renews_on: string;
    days_to_renewal: number | null;
  }[];
  summary?: Record<string, unknown>;
  thresholds?: {
    critical_days: number;
    warning_days: number;
    seat_warn_ratio: number;
    note: string;
  };
  scope?: { org_unit: string; note: string };
};

// ---------------------------------------------------------------------------
// POST /export  (element 7)
// ---------------------------------------------------------------------------
export type ExportRequest = {
  format: "csv" | "json" | "parquet";
  columns?: string[];
  filters?: Record<string, unknown>;
  approval_token?: string;
};
export type ExportResponse = {
  export_id: string;
  row_count: number;
  matched_rows?: number;
  format: "csv" | "json" | "parquet";
  requested_format?: "csv" | "json" | "parquet";
  download_url: string;
  delivery?: "s3-presigned" | "inline-data-uri";
  bytes?: number;
  columns?: string[];
  masked_fields?: string[];
  mask_reason?: string | null;
  filters_applied?: Record<string, unknown>;
  audit_id?: number;
  expires_in_seconds?: number;
  note?: string;
  audited: true;
};
/** Thrown as ApiError(428, ...) when row_count > EXPORT_MAX_ROWS with no approval_token. */
export type ExportApprovalRequiredBody = {
  error: "approval_required";
  row_count: number;
  max_rows: number;
  subject_type: "export";
  subject_id: string;
  how_to_clear: string;
};

// ---------------------------------------------------------------------------
// GET /openapi.json  (element 7): pass-through, shape owned by the API itself
// ---------------------------------------------------------------------------
export type OpenApiDoc = Record<string, unknown>;

// ---------------------------------------------------------------------------
// GET /system/evidence  (protected System Inspector)
// ---------------------------------------------------------------------------
export type EvidenceStage = {
  id: string;
  label: string;
  status: "completed" | "running" | "skipped" | "failed";
  receipt: string;
};

export type EvidenceRun = {
  run_id: string;
  batch_id: string;
  started_at: string;
  completed_at: string;
  status: "completed" | "running" | "failed";
  outcome: "curated" | "quarantined" | "failed";
  quality_score: number;
  curated_rows: number;
  stages: EvidenceStage[];
  source: "database_projection" | "replay_fixture";
};

export type EvidenceAuditEvent = {
  event_id: string;
  action: string;
  category: string;
  detail: Record<string, string | number | boolean>;
  at: string;
  source: "append_only_audit" | "replay_fixture";
};

export type SystemEvidenceResponse = {
  mode: "live" | "replay";
  evidence_class: string;
  generated_at: string;
  deploy_revision: string;
  correlation_id: string;
  request: {
    method: "GET";
    route: "/system/evidence";
    status: number;
    latency_ms: number;
  };
  identity_decision: {
    authenticated: boolean;
    role: Role;
    scope: string;
    row_policy: string;
    column_policy: string;
  };
  health: {
    status: "operational" | "degraded" | "unavailable";
    database: "reachable" | "unavailable" | "replay";
    projection_freshness: string;
  };
  metrics: {
    curated_records: number;
    curated_batches: number;
    open_anomalies: number;
    pending_approvals: number;
    audit_receipts: number;
  };
  services: {
    id: string;
    label: string;
    purpose: string;
    status: "operational" | "degraded" | "replay";
  }[];
  recent_runs: EvidenceRun[];
  recent_audit: EvidenceAuditEvent[];
  latest_model_run: {
    run_id: string;
    kind: string;
    status: string;
    created_at: string;
    metrics: Record<string, string | number | boolean>;
    source: "model_run_projection" | "replay_fixture";
  } | null;
  controls: {
    id: string;
    label: string;
    status: "enforced" | "configured" | "verified";
    evidence: string;
  }[];
  disclosure: string;
};

// ---------------------------------------------------------------------------
// Unified operations: signals, summary, and cross-workflow lineage
// ---------------------------------------------------------------------------

export type OperationsEvidenceMode = "live" | "replay";

export type OperationsRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "quarantined"
  | "failed"
  | "expired"
  | "cancelled";

export type OperationsStageStatus =
  | "pending"
  | "running"
  | "completed"
  | "quarantined"
  | "failed"
  | "skipped";

export type OperationsSignalSeverity = "info" | "warning" | "critical";
export type OperationsSignalStatus = "open" | "acknowledged" | "resolved";
export type OperationsDeliveryState =
  | "pending"
  | "recorded"
  | "published"
  | "delivered"
  | "failed"
  | "not_configured";

export type OperationsResourceRef = {
  id: string;
  label: string;
  kind: string;
  uri?: string | null;
  sha256?: string | null;
  version?: string | null;
};

export type OperationsRunCounts = {
  input_records: number | null;
  output_records: number | null;
  quarantined_records: number | null;
  artifacts: number | null;
};

export type OperationsRunSummary = {
  run_id: string;
  run_kind: string;
  label: string;
  status: OperationsRunStatus;
  current_stage: string;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  completed_stages: number;
  stage_count: number;
  source: OperationsResourceRef;
  model: OperationsResourceRef | null;
  consumer: OperationsResourceRef | null;
  counts: OperationsRunCounts;
};

export type OperationsSourceWatermark = {
  source_id: string;
  label: string;
  status: "current" | "running" | "late" | "failed";
  last_attempt_at: string | null;
  last_accepted_at: string | null;
  watermark: string | null;
  added_records: number;
  changed_records: number;
  unchanged_records: number;
  not_observed_records: number;
  run_id: string | null;
};

export type OperationsSummaryResponse = {
  contract: "compass.operations.summary.v1";
  mode: OperationsEvidenceMode;
  generated_at: string;
  counts: {
    runs_total: number;
    runs_active: number;
    runs_attention: number;
    signals_unread: number;
  };
  runs: OperationsRunSummary[];
  source_watermarks: OperationsSourceWatermark[];
  disclosure: string;
};

export type OperationsSignalDelivery = {
  channel: "in_app" | "email" | "sns" | "webhook";
  state: OperationsDeliveryState;
  attempted_at: string | null;
  delivered_at: string | null;
  detail: string | null;
};

export type OperationsSignal = {
  event_id: string;
  signal_type: string;
  severity: OperationsSignalSeverity;
  title: string;
  message: string;
  status: OperationsSignalStatus;
  occurred_at: string;
  updated_at: string;
  run_id: string | null;
  run_kind: string | null;
  href: string | null;
  source: string;
  deliveries: OperationsSignalDelivery[];
  acknowledged_at: string | null;
  acknowledged_by: string | null;
};

export type OperationsSignalsResponse = {
  contract: "compass.operations.signals.v1";
  mode: OperationsEvidenceMode;
  generated_at: string;
  unread_count: number;
  signals: OperationsSignal[];
  disclosure: string;
};

export type OperationsSignalAcknowledgeResponse = {
  contract: "compass.operations.signal-acknowledgement.v1";
  mode: OperationsEvidenceMode;
  event_id: string;
  status: "acknowledged";
  acknowledged_at: string;
  acknowledged_by: string;
};

export type OperationsLineageStage = {
  stage_id: string;
  sequence: number;
  label: string;
  system: string;
  status: OperationsStageStatus;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  source_sha256: string | null;
  input_sha256: string | null;
  output_sha256: string | null;
  record_count: number | null;
  artifact_count: number | null;
  receipt: string | null;
  attempt: number;
  actor: string | null;
  source_revision: string | null;
  failure_code: string | null;
  detail: string;
};

export type OperationsLineageEdge = {
  from_stage: string;
  to_stage: string;
  label: string;
};

export type OperationsLineageResponse = {
  contract: "compass.operations.lineage.v1";
  mode: OperationsEvidenceMode;
  generated_at: string;
  run: OperationsRunSummary;
  stages: OperationsLineageStage[];
  edges: OperationsLineageEdge[];
  disclosure: string;
};

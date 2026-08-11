export type ScaleProfileId = "1k" | "10k" | "100k" | "1m";

export type ScaleCapacityState = "ready" | "locked";

export type ScaleRunStatus =
  | "queued"
  | "generating"
  | "ingesting"
  | "quality"
  | "intelligence"
  | "exporting"
  | "cancelling"
  | "cancelled"
  | "completed"
  | "failed";

export type ScaleStageId =
  | "plan"
  | "generate"
  | "buffer"
  | "ingest"
  | "quality"
  | "curate"
  | "intelligence"
  | "export"
  | "evidence";

export type SyntheticDomain =
  | "grants"
  | "finance"
  | "milestones"
  | "documents"
  | "licenses"
  | "stream_events";

export type ScaleProfile = {
  id: ScaleProfileId;
  label: string;
  short_label: string;
  total_records: number;
  description: string;
  capacity_state: ScaleCapacityState;
  capacity_note: string;
  recommended: boolean;
};

export type ScaleDatasetAllocation = {
  domain: SyntheticDomain;
  label: string;
  records: number;
  percentage: number;
  purpose: string;
};

export type ScaleCostLineItem = {
  id: string;
  label: string;
  estimated_usd: number;
  basis: string;
};

export type ScaleCostEstimate = {
  currency: "USD";
  estimated_run_usd: number;
  upper_bound_usd: number;
  incremental_idle_monthly_usd: number;
  pricing_as_of: string;
  estimate_source: "aws_price_model" | "replay_model";
  disclaimer: string;
  line_items: ScaleCostLineItem[];
};

export type ScalePlanStage = {
  id: ScaleStageId;
  label: string;
  detail: string;
  resource: string;
};

export type ScalePlan = {
  plan_id: string;
  profile_id: ScaleProfileId;
  seed: number;
  generated_at: string;
  capacity_state: ScaleCapacityState;
  total_records: number;
  estimated_raw_bytes: number;
  target_duration_seconds: number;
  concurrency_limit: number;
  partition_count: number;
  dataset_mix: ScaleDatasetAllocation[];
  stages: ScalePlanStage[];
  cost: ScaleCostEstimate;
};

export type ScaleRunProgress = {
  stage: ScaleStageId;
  percent: number;
  records_generated: number;
  records_ingested: number;
  records_curated: number;
  records_quarantined: number;
  bytes_written: number;
  partitions_completed: number;
  partitions_total: number;
  current_throughput_rps: number;
  peak_throughput_rps: number;
  elapsed_seconds: number;
  eta_seconds: number | null;
};

export type ScaleQualityRule = {
  id: string;
  label: string;
  score: number;
  passed_records: number;
  failed_records: number;
};

export type ScaleRunQuality = {
  overall_score: number;
  passed_records: number;
  failed_records: number;
  quarantined_records: number;
  rules: ScaleQualityRule[];
};

export type ScaleTopic = {
  label: string;
  record_count: number;
  confidence: number;
  terms: string[];
};

export type ScaleRunIntelligence = {
  status: "pending" | "running" | "completed" | "cancelled";
  model_run_id: string | null;
  grants_analyzed: number;
  topic_count: number;
  anomalies_detected: number;
  processing_seconds: number | null;
  top_topics: ScaleTopic[];
};

export type ScaleExportReceipt = {
  export_id: string | null;
  status: "pending" | "building" | "ready" | "cancelled";
  format: "parquet";
  row_count: number;
  bytes: number;
  object_uri: string | null;
  download_url: string | null;
  expires_at: string | null;
  sha256: string | null;
};

export type ScaleEvidenceStage = {
  id: ScaleStageId;
  label: string;
  status: "pending" | "running" | "completed" | "cancelled" | "failed";
  receipt: string | null;
  recorded_at: string | null;
};

export type ScaleRunEvidence = {
  correlation_id: string;
  audit_receipt: string;
  manifest_uri: string;
  manifest_sha256: string;
  metrics_recorded_at: string;
  recovery_queue_depth: number;
  duplicate_records_suppressed: number;
  stages: ScaleEvidenceStage[];
};

export type ScaleRun = {
  run_id: string;
  mode: "live" | "replay";
  status: ScaleRunStatus;
  created_at: string;
  started_at: string | null;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  plan: ScalePlan;
  progress: ScaleRunProgress;
  quality: ScaleRunQuality;
  costs: ScaleCostEstimate & { accrued_usd: number };
  intelligence: ScaleRunIntelligence;
  export_receipt: ScaleExportReceipt;
  evidence: ScaleRunEvidence;
  error: { code: string; message: string; retryable: boolean } | null;
};

export type ScaleProfilesResponse = {
  profiles: ScaleProfile[];
  generated_at: string;
};

export type ScalePlanRequest = {
  profile_id: ScaleProfileId;
  seed: number;
};

export type ScaleLaunchRequest = {
  plan_id: string;
  idempotency_key: string;
};

export type ScaleCancelRequest = {
  reason: "operator_requested";
};

export type ScaleRunsResponse = {
  runs: ScaleRun[];
  generated_at: string;
};

export type ScaleExportRequest = {
  dataset: "curated_portfolio";
  format: "parquet";
  idempotency_key: string;
};

export type ScaleAdapter = {
  getProfiles(): Promise<ScaleProfilesResponse>;
  previewPlan(request: ScalePlanRequest): Promise<ScalePlan>;
  launchRun(request: ScaleLaunchRequest): Promise<ScaleRun>;
  listRuns(): Promise<ScaleRunsResponse>;
  getRun(runId: string): Promise<ScaleRun>;
  cancelRun(runId: string): Promise<ScaleRun>;
  requestExport(runId: string, request: ScaleExportRequest): Promise<ScaleExportReceipt>;
  getExport(runId: string, exportId: string): Promise<ScaleExportReceipt>;
};

export function isTerminalScaleStatus(status: ScaleRunStatus): boolean {
  return status === "completed" || status === "cancelled" || status === "failed";
}

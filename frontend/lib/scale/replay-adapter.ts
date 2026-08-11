import { ScaleAdapterError } from "./errors";
import { buildScalePlan, profileById, SCALE_PROFILES } from "./profiles";
import type {
  ScaleAdapter,
  ScaleExportReceipt,
  ScaleExportRequest,
  ScaleLaunchRequest,
  ScalePlan,
  ScalePlanRequest,
  ScaleProfilesResponse,
  ScaleRun,
  ScaleRunEvidence,
  ScaleRunProgress,
  ScaleRunsResponse,
  ScaleRunStatus,
  ScaleStageId,
} from "./types";

type ReplayRunState = {
  run: ScaleRun;
  pollCount: number;
  cancelPollCount: number;
  exportPollCount: number;
  exportKey: string | null;
};

type ReplayStore = {
  plans: Map<string, ScalePlan>;
  runs: Map<string, ReplayRunState>;
  launchKeys: Map<string, string>;
  runCounter: number;
};

const globalWithScale = globalThis as typeof globalThis & {
  __compassScaleReplay?: ReplayStore;
};

function replayStore(): ReplayStore {
  if (!globalWithScale.__compassScaleReplay) {
    globalWithScale.__compassScaleReplay = {
      plans: new Map(),
      runs: new Map(),
      launchKeys: new Map(),
      runCounter: 0,
    };
  }
  return globalWithScale.__compassScaleReplay;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function stableToken(input: string, length = 24): string {
  let value = 2_166_136_261;
  for (const char of input) {
    value ^= char.charCodeAt(0);
    value = Math.imul(value, 16_777_619);
  }
  const first = (value >>> 0).toString(16).padStart(8, "0");
  return `${first}${first.split("").reverse().join("")}${first}`.slice(0, length);
}

function nowIso(): string {
  return new Date().toISOString();
}

const PROGRESSION: { status: ScaleRunStatus; stage: ScaleStageId; percent: number }[] = [
  { status: "queued", stage: "plan", percent: 0 },
  { status: "generating", stage: "generate", percent: 14 },
  { status: "ingesting", stage: "ingest", percent: 36 },
  { status: "quality", stage: "quality", percent: 58 },
  { status: "intelligence", stage: "intelligence", percent: 80 },
  { status: "completed", stage: "evidence", percent: 100 },
];

const STAGE_ORDER: ScaleStageId[] = [
  "plan",
  "buffer",
  "generate",
  "ingest",
  "quality",
  "curate",
  "intelligence",
  "export",
  "evidence",
];

function progressFor(plan: ScalePlan, index: number): ScaleRunProgress {
  const step = PROGRESSION[Math.min(index, PROGRESSION.length - 1)];
  const ratio = step.percent / 100;
  const generatedRatio = Math.min(1, ratio / 0.25);
  const ingestedRatio = Math.max(0, Math.min(1, (ratio - 0.16) / 0.42));
  const curatedRatio = Math.max(0, Math.min(1, (ratio - 0.48) / 0.44));
  const elapsed = Math.round((plan.target_duration_seconds * step.percent) / 100);
  const currentThroughput = step.percent === 0 || step.percent === 100
    ? 0
    : Math.max(12, Math.round(plan.total_records / Math.max(1, plan.target_duration_seconds) * (1.8 + index * 0.18)));
  return {
    stage: step.stage,
    percent: step.percent,
    records_generated: Math.round(plan.total_records * generatedRatio),
    records_ingested: Math.round(plan.total_records * ingestedRatio),
    records_curated: Math.round(plan.total_records * curatedRatio * 0.99),
    records_quarantined: Math.round(plan.total_records * curatedRatio * 0.01),
    bytes_written: Math.round(plan.estimated_raw_bytes * ratio),
    partitions_completed: Math.min(plan.partition_count, Math.round(plan.partition_count * ratio)),
    partitions_total: plan.partition_count,
    current_throughput_rps: currentThroughput,
    peak_throughput_rps: Math.max(currentThroughput, Math.round(plan.total_records / Math.max(1, plan.target_duration_seconds) * 2.6)),
    elapsed_seconds: elapsed,
    eta_seconds: step.percent === 100 ? 0 : Math.max(0, plan.target_duration_seconds - elapsed),
  };
}

function evidenceFor(runId: string, plan: ScalePlan, currentStage: ScaleStageId): ScaleRunEvidence {
  const currentIndex = STAGE_ORDER.indexOf(currentStage);
  const stamp = nowIso();
  return {
    correlation_id: `corr-${stableToken(runId, 18)}`,
    audit_receipt: `audit-${stableToken(`${runId}:audit`, 20)}`,
    manifest_uri: `lake://scale-runs/${runId}/manifest`,
    manifest_sha256: stableToken(`${runId}:${plan.seed}:manifest`, 64).padEnd(64, "0"),
    metrics_recorded_at: stamp,
    recovery_queue_depth: 0,
    duplicate_records_suppressed: 0,
    stages: plan.stages.map((stage, index) => {
      const orderedIndex = STAGE_ORDER.indexOf(stage.id);
      const completed = orderedIndex < currentIndex || currentStage === "evidence";
      const running = orderedIndex === currentIndex && currentStage !== "evidence";
      return {
        id: stage.id,
        label: stage.label,
        status: completed ? "completed" as const : running ? "running" as const : "pending" as const,
        receipt: completed ? `rcpt-${index + 1}-${stableToken(`${runId}:${stage.id}`, 12)}` : null,
        recorded_at: completed ? stamp : null,
      };
    }),
  };
}

function createRun(plan: ScalePlan, runId: string): ScaleRun {
  const createdAt = nowIso();
  const progress = progressFor(plan, 0);
  const quarantined = Math.round(plan.total_records * 0.01);
  const passed = plan.total_records - quarantined;
  const grants = plan.dataset_mix.find((row) => row.domain === "grants")?.records ?? 0;
  return {
    run_id: runId,
    mode: "replay",
    status: "queued",
    created_at: createdAt,
    started_at: null,
    updated_at: createdAt,
    completed_at: null,
    cancelled_at: null,
    plan: clone(plan),
    progress,
    quality: {
      overall_score: 0,
      passed_records: 0,
      failed_records: 0,
      quarantined_records: 0,
      rules: [
        { id: "schema", label: "Schema conformance", score: 99.6, passed_records: Math.round(plan.total_records * 0.996), failed_records: Math.round(plan.total_records * 0.004) },
        { id: "required", label: "Required fields", score: 98.9, passed_records: Math.round(plan.total_records * 0.989), failed_records: Math.round(plan.total_records * 0.011) },
        { id: "referential", label: "Range and relationship rules", score: 99, passed_records: passed, failed_records: quarantined },
        { id: "classification", label: "Classification policy", score: 100, passed_records: plan.total_records, failed_records: 0 },
      ],
    },
    costs: { ...clone(plan.cost), accrued_usd: 0 },
    intelligence: {
      status: "pending",
      model_run_id: null,
      grants_analyzed: 0,
      topic_count: 0,
      anomalies_detected: 0,
      processing_seconds: null,
      top_topics: [
        { label: "Autonomous maritime systems", record_count: Math.round(grants * 0.31), confidence: 0.94, terms: ["autonomy", "maritime", "navigation"] },
        { label: "Resilient communications", record_count: Math.round(grants * 0.27), confidence: 0.91, terms: ["network", "resilient", "spectrum"] },
        { label: "Advanced materials", record_count: Math.round(grants * 0.23), confidence: 0.89, terms: ["materials", "thermal", "manufacturing"] },
      ],
    },
    export_receipt: {
      export_id: null,
      status: "pending",
      format: "parquet",
      row_count: 0,
      bytes: 0,
      object_uri: null,
      download_url: null,
      expires_at: null,
      sha256: null,
    },
    evidence: evidenceFor(runId, plan, "plan"),
    error: null,
  };
}

function advanceRun(state: ReplayRunState): void {
  if (state.run.status === "cancelling") {
    state.cancelPollCount += 1;
    if (state.cancelPollCount >= 1) {
      const stamp = nowIso();
      state.run.status = "cancelled";
      state.run.cancelled_at = stamp;
      state.run.completed_at = stamp;
      state.run.updated_at = stamp;
      state.run.intelligence.status = "cancelled";
      state.run.export_receipt.status = "cancelled";
      state.run.evidence.stages = state.run.evidence.stages.map((stage) =>
        stage.status === "completed" ? stage : { ...stage, status: "cancelled" },
      );
    }
    return;
  }
  if (state.run.status === "completed" || state.run.status === "cancelled" || state.run.status === "failed") return;
  state.pollCount = Math.min(state.pollCount + 1, PROGRESSION.length - 1);
  const step = PROGRESSION[state.pollCount];
  const stamp = nowIso();
  state.run.status = step.status;
  state.run.started_at = state.run.started_at ?? stamp;
  state.run.updated_at = stamp;
  state.run.progress = progressFor(state.run.plan, state.pollCount);
  state.run.evidence = evidenceFor(state.run.run_id, state.run.plan, step.stage);
  state.run.costs.accrued_usd = Number((state.run.costs.estimated_run_usd * step.percent / 100).toFixed(4));
  if (step.percent >= 58) {
    state.run.quality.overall_score = 99;
    state.run.quality.quarantined_records = state.run.progress.records_quarantined;
    state.run.quality.failed_records = state.run.progress.records_quarantined;
    state.run.quality.passed_records = state.run.progress.records_curated;
  }
  if (step.percent >= 80) {
    const grants = state.run.plan.dataset_mix.find((row) => row.domain === "grants")?.records ?? 0;
    state.run.intelligence.status = step.percent === 100 ? "completed" : "running";
    state.run.intelligence.model_run_id = `intelligence-${stableToken(state.run.run_id, 14)}`;
    state.run.intelligence.grants_analyzed = step.percent === 100 ? grants : Math.round(grants * 0.72);
    state.run.intelligence.topic_count = 7;
    state.run.intelligence.anomalies_detected = Math.max(2, Math.round(state.run.plan.total_records * 0.0042));
    state.run.intelligence.processing_seconds = step.percent === 100 ? Math.round(state.run.plan.target_duration_seconds * 0.19) : null;
  }
  if (step.status === "completed") state.run.completed_at = stamp;
}

function requireRun(runId: string): ReplayRunState {
  const state = replayStore().runs.get(runId);
  if (!state) throw new ScaleAdapterError(404, { error: "run_not_found", message: "No scale run exists for this identifier." });
  return state;
}

export const replayScaleAdapter: ScaleAdapter = {
  async getProfiles(): Promise<ScaleProfilesResponse> {
    return { profiles: clone([...SCALE_PROFILES]), generated_at: nowIso() };
  },

  async previewPlan(request: ScalePlanRequest): Promise<ScalePlan> {
    if (!Number.isInteger(request.seed) || request.seed < 1 || request.seed > 2_147_483_647) {
      throw new ScaleAdapterError(400, { error: "invalid_seed", message: "Seed must be an integer from 1 through 2,147,483,647." });
    }
    const plan = buildScalePlan(request.profile_id, request.seed);
    replayStore().plans.set(plan.plan_id, clone(plan));
    return clone(plan);
  },

  async launchRun(request: ScaleLaunchRequest): Promise<ScaleRun> {
    const store = replayStore();
    const existingId = store.launchKeys.get(request.idempotency_key);
    if (existingId) return clone(requireRun(existingId).run);
    const plan = store.plans.get(request.plan_id);
    if (!plan) throw new ScaleAdapterError(409, { error: "plan_not_found", message: "Preview the workload again before launch." });
    const profile = profileById(plan.profile_id);
    if (profile.capacity_state === "locked") {
      throw new ScaleAdapterError(409, {
        error: "capacity_locked",
        message: "The 1M profile is locked by the deployment capacity policy.",
        profile_id: profile.id,
      });
    }
    store.runCounter += 1;
    const runId = `scale-replay-${String(store.runCounter).padStart(4, "0")}`;
    const run = createRun(plan, runId);
    store.runs.set(runId, { run, pollCount: 0, cancelPollCount: 0, exportPollCount: 0, exportKey: null });
    store.launchKeys.set(request.idempotency_key, runId);
    return clone(run);
  },

  async listRuns(): Promise<ScaleRunsResponse> {
    const runs = [...replayStore().runs.values()]
      .map((state) => clone(state.run))
      .sort((left, right) => right.created_at.localeCompare(left.created_at));
    return { runs, generated_at: nowIso() };
  },

  async getRun(runId: string): Promise<ScaleRun> {
    const state = requireRun(runId);
    advanceRun(state);
    return clone(state.run);
  },

  async cancelRun(runId: string): Promise<ScaleRun> {
    const state = requireRun(runId);
    if (state.run.status === "completed") {
      throw new ScaleAdapterError(409, { error: "run_terminal", message: "A completed run cannot be cancelled." });
    }
    if (state.run.status === "cancelled" || state.run.status === "failed") return clone(state.run);
    state.run.status = "cancelling";
    state.run.updated_at = nowIso();
    return clone(state.run);
  },

  async requestExport(runId: string, request: ScaleExportRequest): Promise<ScaleExportReceipt> {
    const state = requireRun(runId);
    if (state.run.status !== "completed") {
      throw new ScaleAdapterError(409, { error: "run_not_complete", message: "Complete the workload before building its governed export." });
    }
    if (state.exportKey === request.idempotency_key && state.run.export_receipt.export_id) {
      return clone(state.run.export_receipt);
    }
    const exportId = `export-${stableToken(`${runId}:${request.dataset}`, 16)}`;
    state.exportKey = request.idempotency_key;
    state.exportPollCount = 0;
    state.run.export_receipt = {
      export_id: exportId,
      status: "building",
      format: "parquet",
      row_count: state.run.progress.records_curated,
      bytes: Math.round(state.run.plan.estimated_raw_bytes * 0.42),
      object_uri: null,
      download_url: null,
      expires_at: null,
      sha256: null,
    };
    return clone(state.run.export_receipt);
  },

  async getExport(runId: string, exportId: string): Promise<ScaleExportReceipt> {
    const state = requireRun(runId);
    if (state.run.export_receipt.export_id !== exportId) {
      throw new ScaleAdapterError(404, { error: "export_not_found", message: "No export receipt exists for this run." });
    }
    state.exportPollCount += 1;
    if (state.exportPollCount >= 1 && state.run.export_receipt.status === "building") {
      state.run.export_receipt = {
        ...state.run.export_receipt,
        status: "ready",
        object_uri: `lake://scale-runs/${runId}/exports/${exportId}/manifest`,
        download_url: `data:application/json,${encodeURIComponent(JSON.stringify({ run_id: runId, export_id: exportId, note: "Replay receipt only" }))}`,
        expires_at: new Date(Date.now() + 15 * 60 * 1_000).toISOString(),
        sha256: stableToken(`${runId}:${exportId}:parquet`, 64).padEnd(64, "0"),
      };
    }
    return clone(state.run.export_receipt);
  },
};

export function resetScaleReplay(): void {
  globalWithScale.__compassScaleReplay = undefined;
}

export const scaleReplayTestSupport = {
  progression: PROGRESSION,
};

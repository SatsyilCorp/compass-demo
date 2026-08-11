import type {
  ScaleCostEstimate,
  ScaleDatasetAllocation,
  ScalePlan,
  ScalePlanStage,
  ScaleProfile,
  ScaleProfileId,
} from "./types";

export const SCALE_PROFILES: readonly ScaleProfile[] = [
  {
    id: "1k",
    label: "1,000 records",
    short_label: "1K",
    total_records: 1_000,
    description: "Fast smoke run for validating every production path.",
    capacity_state: "ready",
    capacity_note: "Runs inside the protected demo concurrency envelope.",
    recommended: false,
  },
  {
    id: "10k",
    label: "10,000 records",
    short_label: "10K",
    total_records: 10_000,
    description: "Presenter-ready workload with visible parallel processing.",
    capacity_state: "ready",
    capacity_note: "Recommended for a live demonstration.",
    recommended: true,
  },
  {
    id: "100k",
    label: "100,000 records",
    short_label: "100K",
    total_records: 100_000,
    description: "Sustained scale run across partitioned ingestion and intelligence.",
    capacity_state: "ready",
    capacity_note: "Uses the extended demo capacity envelope.",
    recommended: false,
  },
  {
    id: "1m",
    label: "1,000,000 records",
    short_label: "1M",
    total_records: 1_000_000,
    description: "Full production rehearsal with a cost and capacity gate.",
    capacity_state: "locked",
    capacity_note: "Unlock through the deployment capacity policy before launch.",
    recommended: false,
  },
] as const;

const STAGES: ScalePlanStage[] = [
  { id: "plan", label: "Plan", detail: "Bind the seed, profile, limits, and cost ceiling.", resource: "Scale control" },
  { id: "buffer", label: "Buffer", detail: "Absorb burst traffic and apply backpressure.", resource: "Event queue" },
  { id: "generate", label: "Generate", detail: "Create deterministic records inside bounded partition workers.", resource: "Generator workers" },
  { id: "ingest", label: "Ingest", detail: "Write immutable raw objects and validate manifests.", resource: "Raw lake" },
  { id: "quality", label: "Quality", detail: "Apply schema, completeness, and integrity gates.", resource: "Quality workers" },
  { id: "curate", label: "Curate", detail: "Publish partitioned governed JSON Lines datasets.", resource: "Curated lake" },
  { id: "intelligence", label: "Intelligence", detail: "Convert Parquet and merge full-corpus topics and anomalies.", resource: "Athena and receipt merge" },
  { id: "export", label: "Export", detail: "Seal a checksummed manifest over governed Parquet objects.", resource: "Export worker" },
  { id: "evidence", label: "Evidence", detail: "Seal metrics, cost, lineage, and audit receipts.", resource: "Evidence ledger" },
];

type ProfileTuning = {
  bytesPerRecord: number;
  targetSeconds: number;
  concurrency: number;
  partitions: number;
  cost: [number, number];
};

const TUNING: Record<ScaleProfileId, ProfileTuning> = {
  "1k": { bytesPerRecord: 1_400, targetSeconds: 105, concurrency: 4, partitions: 6, cost: [0.019, 0.1] },
  "10k": { bytesPerRecord: 1_400, targetSeconds: 105, concurrency: 4, partitions: 6, cost: [0.0192, 0.25] },
  "100k": { bytesPerRecord: 1_400, targetSeconds: 135, concurrency: 4, partitions: 11, cost: [0.0339, 1] },
  "1m": { bytesPerRecord: 1_400, targetSeconds: 375, concurrency: 4, partitions: 41, cost: [0.1394, 10] },
};

const DOMAIN_DEFINITIONS = [
  ["grants", "Grant records", 20, "Portfolio identity, award, and program attributes"],
  ["finance", "Financial events", 30, "Obligations, expenditures, and forecast movements"],
  ["milestones", "Milestones", 20, "Technical schedule, status, and delivery outcomes"],
  ["documents", "Documents", 10, "Synthetic reports, metadata, and linked portfolio context"],
  ["licenses", "License records", 2, "Entitlements, renewals, and utilization posture"],
  ["stream_events", "Stream events", 18, "Ordered operational signals for burst and freshness analysis"],
] as const;

function allocation(total: number): ScaleDatasetAllocation[] {
  let assigned = 0;
  return DOMAIN_DEFINITIONS.map(([domain, label, percentage, purpose], index) => {
    const records = index === DOMAIN_DEFINITIONS.length - 1
      ? total - assigned
      : Math.floor((total * percentage) / 100);
    assigned += records;
    return { domain, label, records, percentage, purpose };
  });
}

function costEstimate(id: ScaleProfileId, source: ScaleCostEstimate["estimate_source"]): ScaleCostEstimate {
  const [estimated, upper] = TUNING[id].cost;
  const weights = [0.16, 0.43, 0.12, 0.18, 0.11];
  const labels = [
    ["storage", "Lake storage and requests", "Raw, curated, quarantine, and export objects"],
    ["compute", "Worker compute", "Generation, validation, quality, intelligence, and export"],
    ["orchestration", "Queue and orchestration", "State transitions, queue requests, and retries"],
    ["query", "Analytic query", "Partition-pruned evidence and serving aggregates"],
    ["telemetry", "Telemetry", "Metrics, logs, traces, and audit receipts"],
  ] as const;
  const line_items = labels.map(([lineId, label, basis], index) => ({
    id: lineId,
    label,
    estimated_usd: Number((estimated * weights[index]).toFixed(4)),
    basis,
  }));
  const delta = Number((estimated - line_items.reduce((sum, row) => sum + row.estimated_usd, 0)).toFixed(4));
  line_items[1] = { ...line_items[1], estimated_usd: Number((line_items[1].estimated_usd + delta).toFixed(4)) };
  return {
    currency: "USD",
    estimated_run_usd: estimated,
    upper_bound_usd: upper,
    incremental_idle_monthly_usd: 0,
    pricing_as_of: "2026-08-11",
    estimate_source: source,
    disclaimer: source === "replay_model"
      ? "Modeled replay estimate for interface rehearsal. No AWS resources are started."
      : "Estimate uses the deployed price model. Actual billed cost can vary with retries, data shape, and log volume.",
    line_items,
  };
}

export function profileById(id: ScaleProfileId): ScaleProfile {
  const profile = SCALE_PROFILES.find((candidate) => candidate.id === id);
  if (!profile) throw new Error(`unknown_scale_profile:${id}`);
  return profile;
}

export function buildScalePlan(
  profileId: ScaleProfileId,
  seed: number,
  source: ScaleCostEstimate["estimate_source"] = "replay_model",
  now = new Date(),
): ScalePlan {
  const profile = profileById(profileId);
  const tuning = TUNING[profileId];
  return {
    plan_id: `plan-${profileId}-${seed}`,
    profile_id: profileId,
    seed,
    generated_at: now.toISOString(),
    capacity_state: profile.capacity_state,
    total_records: profile.total_records,
    estimated_raw_bytes: profile.total_records * tuning.bytesPerRecord,
    target_duration_seconds: tuning.targetSeconds,
    concurrency_limit: tuning.concurrency,
    partition_count: tuning.partitions,
    dataset_mix: allocation(profile.total_records),
    stages: STAGES.map((stage) => ({ ...stage })),
    cost: costEstimate(profileId, source),
  };
}

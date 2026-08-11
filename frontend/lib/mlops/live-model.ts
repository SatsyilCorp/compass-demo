export type LiveModelReceipt = {
  model_version?: unknown;
  status?: unknown;
  labels?: unknown;
  metrics?: {
    accuracy?: unknown;
    macro_f1?: unknown;
    training_document_count?: unknown;
    evaluation_document_count?: unknown;
    training_split_seed?: unknown;
  };
  training_digest?: unknown;
  created_at?: unknown;
};

export type LiveModelProjection = {
  version: string;
  status: string;
  accuracy: number;
  macroF1: number;
  classCoverage: number;
  trainingRecords: number;
  splitSeed: string;
  sourceRevision: string;
  createdAt: string;
};

function finiteNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function projectLiveModel(receipt: LiveModelReceipt | null): LiveModelProjection | null {
  const version = typeof receipt?.model_version === "string" ? receipt.model_version.trim() : "";
  if (!receipt || !version) return null;
  const metrics = receipt.metrics ?? {};
  const labels = Array.isArray(receipt.labels)
    ? receipt.labels.filter((label) => typeof label === "string")
    : [];
  const trainingRecords =
    finiteNumber(metrics.training_document_count) + finiteNumber(metrics.evaluation_document_count);
  const digest = typeof receipt.training_digest === "string" ? receipt.training_digest : "";
  return {
    version,
    status: typeof receipt.status === "string" ? receipt.status : "unknown",
    accuracy: finiteNumber(metrics.accuracy),
    macroF1: finiteNumber(metrics.macro_f1),
    classCoverage: labels.length,
    trainingRecords,
    splitSeed: String(metrics.training_split_seed ?? "source controlled"),
    sourceRevision: digest.slice(0, 8) || "source controlled",
    createdAt: typeof receipt.created_at === "string" ? receipt.created_at : "",
  };
}

export function resolvePromotionVersion(
  mode: "live" | "replay",
  replayVersion: string,
  liveModel: LiveModelProjection | null,
): string {
  if (mode === "replay") return replayVersion;
  if (!liveModel) throw new Error("Run live training before approving a model.");
  return liveModel.version;
}

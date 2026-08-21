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
  training_manifest?: unknown;
  training_manifest_uri?: unknown;
  training_manifest_sha256?: unknown;
  artifact_uri?: unknown;
  synthetic_only?: unknown;
  source_revision?: unknown;
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
  trainingManifestUri: string;
  trainingManifestSha256: string;
  artifactUri: string;
};

export type LiveModelEvidenceProjection = {
  state: "verified" | "manifest-required" | "synthetic-excluded" | "incomplete";
  model: LiveModelProjection | null;
  detail: string;
};

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function manifestEvidence(receipt: LiveModelReceipt): { uri: string; sha256: string } {
  const nested = receipt.training_manifest && typeof receipt.training_manifest === "object"
    ? receipt.training_manifest as Record<string, unknown>
    : {};
  return {
    uri: text(receipt.training_manifest_uri) || text(nested.uri),
    sha256:
      text(receipt.training_manifest_sha256)
      || text(nested.sha256)
      || text(nested.digest),
  };
}

export function projectLiveModelEvidence(
  receipt: LiveModelReceipt | null,
): LiveModelEvidenceProjection {
  const version = typeof receipt?.model_version === "string" ? receipt.model_version.trim() : "";
  if (!receipt || !version) {
    return {
      state: "incomplete",
      model: null,
      detail: "No complete registry record was returned by the protected evidence API.",
    };
  }
  if (receipt.synthetic_only === true) {
    return {
      state: "synthetic-excluded",
      model: null,
      detail: `Model ${version} is explicitly marked synthetic and is excluded from live training evidence.`,
    };
  }
  const manifest = manifestEvidence(receipt);
  if (
    receipt.synthetic_only !== false
    || !manifest.uri
    || !/^[a-f0-9]{64}$/i.test(manifest.sha256)
  ) {
    return {
      state: "manifest-required",
      model: null,
      detail: `Model ${version} does not include a verified non-synthetic training manifest URI and SHA-256 digest.`,
    };
  }
  const metrics = receipt.metrics ?? {};
  const labels = Array.isArray(receipt.labels)
    ? receipt.labels.filter((label) => typeof label === "string")
    : [];
  const accuracy = finiteNumber(metrics.accuracy);
  const macroF1 = finiteNumber(metrics.macro_f1);
  const trainingCount = finiteNumber(metrics.training_document_count);
  const evaluationCount = finiteNumber(metrics.evaluation_document_count);
  const artifactUri = text(receipt.artifact_uri);
  const status = text(receipt.status);
  if (
    accuracy === null
    || macroF1 === null
    || trainingCount === null
    || evaluationCount === null
    || labels.length === 0
    || !artifactUri
    || !status
  ) {
    return {
      state: "incomplete",
      model: null,
      detail: `Model ${version} is missing returned artifact, taxonomy, status, or evaluation evidence.`,
    };
  }
  return {
    state: "verified",
    detail: `Model ${version} is bound to a non-synthetic manifest, artifact, taxonomy, and returned evaluation metrics.`,
    model: {
      version,
      status,
      accuracy,
      macroF1,
      classCoverage: labels.length,
      trainingRecords: trainingCount + evaluationCount,
      splitSeed: String(metrics.training_split_seed ?? "not reported"),
      sourceRevision: text(receipt.source_revision) || manifest.sha256.slice(0, 8),
      createdAt: text(receipt.created_at),
      trainingManifestUri: manifest.uri,
      trainingManifestSha256: manifest.sha256.toLowerCase(),
      artifactUri,
    },
  };
}

export function projectLiveModel(receipt: LiveModelReceipt | null): LiveModelProjection | null {
  return projectLiveModelEvidence(receipt).model;
}

export function resolvePromotionVersion(
  mode: "live" | "replay",
  replayVersion: string,
  liveModel: LiveModelProjection | null,
): string {
  if (mode === "replay") return replayVersion;
  if (!liveModel) throw new Error("Verified live model evidence is required before approval.");
  return liveModel.version;
}

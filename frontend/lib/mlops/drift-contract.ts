const DRIFT_CONTRACT = "compass.model-drift-receipt.v1" as const;
const PUBLIC_OPERATIONAL_EVIDENCE = "public-operational" as const;
const SHA256 = /^[a-f0-9]{64}$/;
const DRIFT_ID = /^drift-[a-f0-9]{12}$/;
const MODEL_VERSION = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/;
const DOCUMENT_CLASSES = [
  "grant_abstract",
  "technical_report",
  "publication_summary",
  "patent_summary",
  "investment_brief",
  "financial_execution",
] as const;

export type LiveDriftReceipt = {
  contract: typeof DRIFT_CONTRACT;
  evidence_class: typeof PUBLIC_OPERATIONAL_EVIDENCE;
  drift_id: string;
  model_version: string;
  documents_observed: number;
  tokens_observed: number;
  reference_label_distribution: Record<(typeof DOCUMENT_CLASSES)[number], number>;
  observed_label_distribution: Record<(typeof DOCUMENT_CLASSES)[number], number>;
  population_stability_index: number;
  out_of_vocabulary_rate: number;
  drift_score: number;
  threshold: number;
  drift_detected: boolean;
  recommended_action: "continue-monitoring" | "retrain-and-review";
  evaluation_window_sha256: string;
  baseline_sha256: string;
  receipt_uri: string;
  evaluated_by: string;
  created_at: string;
  updated_at: string;
};

export type LiveDriftExpectation = {
  modelVersion: string;
  documentsObserved: number;
};

export function parseLiveDriftReceipt(
  value: unknown,
  expected: LiveDriftExpectation,
): LiveDriftReceipt | null {
  if (!isRecord(value)) return null;
  const score = value.drift_score;
  const threshold = value.threshold;
  const detected = value.drift_detected;
  const driftId = value.drift_id;
  if (
    value.contract !== DRIFT_CONTRACT
    || value.evidence_class !== PUBLIC_OPERATIONAL_EVIDENCE
    || typeof driftId !== "string"
    || !DRIFT_ID.test(driftId)
    || value.model_version !== expected.modelVersion
    || typeof value.model_version !== "string"
    || !MODEL_VERSION.test(value.model_version)
    || value.documents_observed !== expected.documentsObserved
    || !Number.isInteger(value.documents_observed)
    || value.documents_observed < 5
    || value.documents_observed > 200
    || !Number.isInteger(value.tokens_observed)
    || Number(value.tokens_observed) < 0
    || !isDistribution(value.reference_label_distribution)
    || !isDistribution(value.observed_label_distribution)
    || !isNonNegativeNumber(value.population_stability_index)
    || !isUnitNumber(value.out_of_vocabulary_rate)
    || !isUnitNumber(score)
    || !isThreshold(threshold)
    || typeof detected !== "boolean"
    || detected !== (score >= threshold)
    || value.recommended_action !== (detected ? "retrain-and-review" : "continue-monitoring")
    || typeof value.evaluation_window_sha256 !== "string"
    || !SHA256.test(value.evaluation_window_sha256)
    || typeof value.baseline_sha256 !== "string"
    || !SHA256.test(value.baseline_sha256)
    || value.receipt_uri !== `document-lake://mlops/drift/${driftId}.json`
    || typeof value.evaluated_by !== "string"
    || !/^[^\s][\s\S]{0,159}$/.test(value.evaluated_by)
    || !isIsoTimestamp(value.created_at)
    || !isIsoTimestamp(value.updated_at)
    || Date.parse(value.updated_at) < Date.parse(value.created_at)
  ) {
    return null;
  }
  return value as LiveDriftReceipt;
}

function isDistribution(value: unknown): boolean {
  if (!isRecord(value)) return false;
  if (
    Object.keys(value).length !== DOCUMENT_CLASSES.length
    || DOCUMENT_CLASSES.some((label) => !isUnitNumber(value[label]))
  ) {
    return false;
  }
  const total = DOCUMENT_CLASSES.reduce((sum, label) => sum + Number(value[label]), 0);
  return Math.abs(total - 1) <= 0.001;
}

function isThreshold(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 && value <= 1;
}

function isUnitNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

function isNonNegativeNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isIsoTimestamp(value: unknown): value is string {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

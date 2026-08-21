const DOCUMENT_UPLOAD_PLAN_CONTRACT = "compass.document-upload-plan.v1" as const;
const DOCUMENT_RUN_CONTRACT = "compass.document-intake-run.v1" as const;
const PUBLIC_OPERATIONAL_EVIDENCE = "public-operational" as const;
const MAX_DOCUMENT_BYTES = 15 * 1_024 * 1_024;
const SHA256 = /^[a-f0-9]{64}$/;
const RUN_ID = /^doc-[a-f0-9]{32}$/;
const DOCUMENT_ID = /^[a-f0-9]{32}$/;
const MODEL_VERSION = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/;
const DOCUMENT_CLASSES = new Set([
  "grant_abstract",
  "technical_report",
  "publication_summary",
  "patent_summary",
  "investment_brief",
  "financial_execution",
]);

export type LiveDocumentUploadRequestBinding = {
  fileName: string;
  contentType: string;
  sizeBytes: number;
  sourceSha256: string;
};

export type LiveDocumentBinding = LiveDocumentUploadRequestBinding & {
  runId: string;
  documentId: string;
};

export type LiveDocumentDataBoundary = {
  classification: "public";
  contains_cui: false;
  pii_minimized: true;
};

export type LiveDocumentUploadPlan = {
  contract: typeof DOCUMENT_UPLOAD_PLAN_CONTRACT;
  evidence_class: typeof PUBLIC_OPERATIONAL_EVIDENCE;
  run_id: string;
  document_id: string;
  status: "awaiting-upload";
  stage: "browser-upload";
  filename: string;
  content_type: string;
  expected_bytes: number;
  source: string;
  source_sha256: string;
  synthetic_only: false;
  data_boundary: LiveDocumentDataBoundary;
  created_at: string;
  updated_at: string;
  upload: {
    method: "POST";
    url: string;
    fields: Record<string, string>;
    expires_in_seconds: 900;
    maximum_bytes: typeof MAX_DOCUMENT_BYTES;
  };
};

export type LiveDocumentRunStatus =
  | "awaiting-upload"
  | "running"
  | "completed"
  | "quarantined"
  | "failed";

export type LiveDocumentRunStage =
  | "browser-upload"
  | "bronze-inspected"
  | "quality-gate"
  | "gold-published"
  | "inspect"
  | "quarantine"
  | "workflow-failed";

export type LiveDocumentRun = Record<string, unknown> & {
  contract: typeof DOCUMENT_RUN_CONTRACT;
  evidence_class: typeof PUBLIC_OPERATIONAL_EVIDENCE;
  run_id: string;
  document_id: string;
  status: LiveDocumentRunStatus;
  stage: LiveDocumentRunStage;
  filename: string;
  content_type: string;
  expected_bytes: number;
  source: string;
  source_sha256: string;
  synthetic_only: false;
  data_boundary: LiveDocumentDataBoundary;
  created_at: string;
  updated_at: string;
  document_class?: string;
  confidence?: number;
  review_required?: boolean;
  model_version?: string;
  lineage_receipt_sha256?: string;
};

export function parseLiveDocumentUploadPlan(
  value: unknown,
  expected: LiveDocumentUploadRequestBinding,
): LiveDocumentUploadPlan | null {
  if (!isRecord(value)) return null;
  const filename = safeFilename(expected.fileName);
  if (
    value.contract !== DOCUMENT_UPLOAD_PLAN_CONTRACT
    || value.evidence_class !== PUBLIC_OPERATIONAL_EVIDENCE
    || typeof filename !== "string"
    || !RUN_ID.test(value.run_id as string)
    || !DOCUMENT_ID.test(value.document_id as string)
    || value.document_id !== String(value.run_id).slice(4)
    || value.status !== "awaiting-upload"
    || value.stage !== "browser-upload"
    || value.filename !== filename
    || value.content_type !== expected.contentType
    || value.expected_bytes !== expected.sizeBytes
    || !validRequestedFile(expected)
    || value.source_sha256 !== expected.sourceSha256
    || value.source !== expectedSource(String(value.run_id), filename)
    || value.synthetic_only !== false
    || !isPublicBoundary(value.data_boundary)
    || !isIsoTimestamp(value.created_at)
    || !isIsoTimestamp(value.updated_at)
    || !isUpload(value.upload, value, expected)
  ) {
    return null;
  }
  return value as LiveDocumentUploadPlan;
}

export function bindingFromUploadPlan(plan: LiveDocumentUploadPlan): LiveDocumentBinding {
  return {
    runId: plan.run_id,
    documentId: plan.document_id,
    fileName: plan.filename,
    contentType: plan.content_type,
    sizeBytes: plan.expected_bytes,
    sourceSha256: plan.source_sha256,
  };
}

export function parseLiveDocumentRun(
  value: unknown,
  expected: LiveDocumentBinding,
): LiveDocumentRun | null {
  if (!isRecord(value)) return null;
  const status = value.status;
  const stage = value.stage;
  if (
    value.contract !== DOCUMENT_RUN_CONTRACT
    || value.evidence_class !== PUBLIC_OPERATIONAL_EVIDENCE
    || value.run_id !== expected.runId
    || value.document_id !== expected.documentId
    || value.filename !== expected.fileName
    || value.content_type !== expected.contentType
    || value.expected_bytes !== expected.sizeBytes
    || value.source_sha256 !== expected.sourceSha256
    || value.source !== expectedSource(expected.runId, expected.fileName)
    || value.synthetic_only !== false
    || !isPublicBoundary(value.data_boundary)
    || !isIsoTimestamp(value.created_at)
    || !isIsoTimestamp(value.updated_at)
    || !isSafeState(status, stage)
    || (value.sha256 !== undefined && value.sha256 !== expected.sourceSha256)
    || ((status === "running" || status === "completed") && value.sha256 !== expected.sourceSha256)
    || (status === "completed" && !isCompletedRun(value, expected))
  ) {
    return null;
  }
  return value as LiveDocumentRun;
}

export function parseLiveDocumentRunRecord(value: unknown): LiveDocumentRun | null {
  if (
    !isRecord(value)
    || typeof value.run_id !== "string"
    || !RUN_ID.test(value.run_id)
    || typeof value.document_id !== "string"
    || !DOCUMENT_ID.test(value.document_id)
    || typeof value.filename !== "string"
    || safeFilename(value.filename) !== value.filename
    || typeof value.content_type !== "string"
    || !Number.isInteger(value.expected_bytes)
    || Number(value.expected_bytes) < 1
    || Number(value.expected_bytes) > MAX_DOCUMENT_BYTES
    || typeof value.source_sha256 !== "string"
    || !SHA256.test(value.source_sha256)
  ) {
    return null;
  }
  return parseLiveDocumentRun(value, {
    runId: value.run_id,
    documentId: value.document_id,
    fileName: value.filename,
    contentType: value.content_type,
    sizeBytes: Number(value.expected_bytes),
    sourceSha256: value.source_sha256,
  });
}

function isUpload(
  value: unknown,
  plan: Record<string, unknown>,
  expected: LiveDocumentUploadRequestBinding,
): boolean {
  if (!isRecord(value) || !isRecord(value.fields)) return false;
  let url: URL;
  try {
    url = new URL(String(value.url));
  } catch {
    return false;
  }
  const fields = value.fields;
  return value.method === "POST"
    && url.protocol === "https:"
    && url.username === ""
    && url.password === ""
    && fields["Content-Type"] === expected.contentType
    && fields.key === String(plan.source).replace("document-lake://", "")
    && Object.values(fields).every((item) => typeof item === "string")
    && value.expires_in_seconds === 900
    && value.maximum_bytes === MAX_DOCUMENT_BYTES
    && expected.sizeBytes <= value.maximum_bytes;
}

function isCompletedRun(
  value: Record<string, unknown>,
  expected: LiveDocumentBinding,
): boolean {
  if (
    typeof value.document_class !== "string"
    || !DOCUMENT_CLASSES.has(value.document_class)
    || !isUnitNumber(value.confidence)
    || typeof value.review_required !== "boolean"
    || typeof value.model_version !== "string"
    || !MODEL_VERSION.test(value.model_version)
    || !SHA256.test(String(value.lineage_receipt_sha256 || ""))
    || !isDocumentUri(value.silver_uri, `documents/silver/${expected.runId}/normalized.json`)
    || !isDocumentUri(value.gold_uri, `documents/gold/${expected.runId}/decision-record.json`)
    || !Array.isArray(value.lineage)
    || value.lineage.length !== 5
    || !value.lineage.every((item) => isDocumentUri(item))
    || !isIsoTimestamp(value.completed_at)
  ) {
    return false;
  }
  return value.lineage[0] === expectedSource(expected.runId, expected.fileName)
    && value.lineage[4] === value.gold_uri;
}

function isSafeState(status: unknown, stage: unknown): status is LiveDocumentRunStatus {
  const pairs: Record<LiveDocumentRunStatus, readonly LiveDocumentRunStage[]> = {
    "awaiting-upload": ["browser-upload"],
    running: ["bronze-inspected", "quality-gate"],
    completed: ["gold-published"],
    quarantined: ["inspect", "quality-gate", "quarantine"],
    failed: ["workflow-failed"],
  };
  return typeof status === "string"
    && status in pairs
    && typeof stage === "string"
    && pairs[status as LiveDocumentRunStatus].includes(stage as LiveDocumentRunStage);
}

function validRequestedFile(value: LiveDocumentUploadRequestBinding): boolean {
  return Number.isInteger(value.sizeBytes)
    && value.sizeBytes > 0
    && value.sizeBytes <= MAX_DOCUMENT_BYTES
    && SHA256.test(value.sourceSha256)
    && typeof value.contentType === "string"
    && value.contentType.length > 0;
}

function safeFilename(value: string): string | null {
  const base = value.replaceAll("\\", "/").split("/").at(-1) ?? "";
  const safe = base.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^[.-]+|[.-]+$/g, "").slice(0, 120);
  return safe || null;
}

function expectedSource(runId: string, filename: string): string {
  return `document-lake://documents/incoming/${runId}/${filename}`;
}

function isPublicBoundary(value: unknown): value is LiveDocumentDataBoundary {
  return isRecord(value)
    && value.classification === "public"
    && value.contains_cui === false
    && value.pii_minimized === true;
}

function isIsoTimestamp(value: unknown): value is string {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value));
}

function isDocumentUri(value: unknown, expectedPath?: string): value is string {
  if (typeof value !== "string" || !value.startsWith("document-lake://")) return false;
  return expectedPath === undefined || value === `document-lake://${expectedPath}`;
}

function isUnitNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

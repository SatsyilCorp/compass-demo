import type {
  ContinuousPublicAcquisitionControl,
  PublicAcquisitionList,
  PublicAcquisitionRecord,
  PublicEvidenceThread,
  PublicSourceHealth,
} from "@/lib/api";

type JsonRecord = Record<string, unknown>;

const RUN_STATUSES = new Set(["completed", "failed", "running"]);
const PROFILES = new Set(["quick", "standard", "deep"]);
const HEALTH_STATUSES = new Set(["healthy", "stale", "failed", "awaiting-first-run"]);
const LINK_TYPES = new Set(["exact-identity", "explainable-candidate"]);
const REVIEW_STATUSES = new Set(["verified-key", "analyst-review"]);

const SOURCE_HOSTS: Record<string, Set<string>> = {
  "usaspending-onr-grants": new Set(["api.usaspending.gov"]),
  "grants-gov-onr": new Set(["api.grants.gov"]),
  "federal-register-onr": new Set(["www.federalregister.gov"]),
  "crossref-onr": new Set(["api.crossref.org"]),
};

function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isOptionalText(value: unknown): value is string | null | undefined {
  return value == null || typeof value === "string";
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNonNegativeNumber(value: unknown): value is number {
  return isFiniteNumber(value) && value >= 0;
}

function isProbability(value: unknown): value is number {
  return isFiniteNumber(value) && value >= 0 && value <= 1;
}

function isTimestamp(value: unknown): value is string {
  return isText(value) && Number.isFinite(Date.parse(value));
}

function isOptionalFiniteNumber(value: unknown): value is number | null | undefined {
  return value == null || isNonNegativeNumber(value);
}

function isOptionalBoolean(value: unknown): value is boolean | undefined {
  return value === undefined || typeof value === "boolean";
}

function isHttpsUrl(value: unknown): value is string {
  if (!isText(value)) return false;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && Boolean(parsed.hostname) && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

function isExpectedSourceEndpoint(sourceId: unknown, endpoint: unknown): boolean {
  if (!isText(sourceId) || !isHttpsUrl(endpoint)) return false;
  const allowed = SOURCE_HOSTS[sourceId];
  if (!allowed) return false;
  return allowed.has(new URL(endpoint).hostname.toLowerCase());
}

function hasPublicRunEvidence(value: JsonRecord): boolean {
  return value.status === "completed"
    ? value.evidence_class === "public-observed"
    : value.evidence_class === "public-observed" || value.evidence_class === "public-operational";
}

function isRecordPreview(value: unknown): boolean {
  if (!isRecord(value) || !isText(value.source_record_id)) return false;
  if (value.source_url !== undefined && !isHttpsUrl(value.source_url)) return false;
  if (value.document_url !== undefined && !isHttpsUrl(value.document_url)) return false;
  if (value.award_amount_usd !== undefined && !isFiniteNumber(value.award_amount_usd)) return false;
  if (value.citation_count !== undefined && !isFiniteNumber(value.citation_count)) return false;
  if (value.identity_keys !== undefined && (!Array.isArray(value.identity_keys) || !value.identity_keys.every(isText))) return false;
  return true;
}

function isClassificationSummary(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (!isRecord(value)) return false;
  if (
    value.status !== "completed" ||
    !isText(value.run_id) ||
    !isText(value.model_version) ||
    !isNonNegativeNumber(value.record_count) ||
    !isNonNegativeNumber(value.review_required_count) ||
    !isProbability(value.mean_confidence) ||
    !isText(value.artifact_uri) ||
    !isRecord(value.class_counts) ||
    !Object.values(value.class_counts).every(isFiniteNumber) ||
    !Array.isArray(value.preview)
  ) return false;
  return value.preview.every((item) => isRecord(item)
    && isText(item.source_record_id)
    && isText(item.document_class)
    && isProbability(item.confidence)
    && typeof item.review_required === "boolean");
}

export function parsePublicAcquisitionRecord(value: unknown): PublicAcquisitionRecord | null {
  if (!isRecord(value)) return null;
  if (
    value.contract !== "compass.public-acquisition.v1" ||
    !isText(value.run_id) ||
    !isText(value.source_id) ||
    !RUN_STATUSES.has(String(value.status)) ||
    !isText(value.stage) ||
    !isTimestamp(value.started_at) ||
    !isTimestamp(value.updated_at) ||
    !hasPublicRunEvidence(value)
  ) return null;
  if (value.profile !== undefined && !PROFILES.has(String(value.profile))) return null;
  const numericFields = [
    "record_count", "total_available", "requested_records", "pages_fetched",
    "source_response_bytes", "duration_ms", "added_records", "changed_records",
    "unchanged_records", "not_observed_records", "review_flag_count",
  ];
  if (numericFields.some((field) => !isOptionalFiniteNumber(value[field]))) return null;
  if (!isOptionalBoolean(value.has_more_source_pages)) return null;
  if (value.record_preview !== undefined && (!Array.isArray(value.record_preview) || !value.record_preview.every(isRecordPreview))) return null;
  if (value.review_flags !== undefined && (!Array.isArray(value.review_flags) || !value.review_flags.every((flag) => isRecord(flag) && isText(flag.source_record_id) && Array.isArray(flag.reasons) && flag.reasons.every(isText)))) return null;
  if (!isClassificationSummary(value.classification_summary)) return null;
  return value as PublicAcquisitionRecord;
}

function isSourceHealth(value: unknown): value is PublicSourceHealth {
  if (!isRecord(value)) return false;
  return isText(value.source_id)
    && isText(value.label)
    && isText(value.authority)
    && isExpectedSourceEndpoint(value.source_id, value.endpoint)
    && isNonNegativeNumber(value.cadence_seconds)
    && value.cadence_seconds > 0
    && isText(value.data_kind)
    && isText(value.model_use)
    && HEALTH_STATUSES.has(String(value.status));
}

function isEvidenceThread(value: unknown): value is PublicEvidenceThread {
  if (!isRecord(value)) return false;
  if (
    !isText(value.thread_id) ||
    !LINK_TYPES.has(String(value.match_type)) ||
    !isProbability(value.match_score) ||
    !REVIEW_STATUSES.has(String(value.review_status)) ||
    !isText(value.explanation) ||
    !Array.isArray(value.shared_terms) ||
    !value.shared_terms.every(isText) ||
    !isText(value.owner) ||
    !isText(value.steward) ||
    !Array.isArray(value.facts)
  ) return false;
  return value.facts.every((fact) => isRecord(fact)
    && isText(fact.source_id)
    && isText(fact.source_label)
    && isText(fact.run_id)
    && isText(fact.record_id)
    && isText(fact.record_type)
    && isText(fact.title)
    && (fact.source_url == null || isHttpsUrl(fact.source_url))
    && (fact.document_url == null || isHttpsUrl(fact.document_url)));
}

export function parsePublicAcquisitionList(value: unknown): PublicAcquisitionList | null {
  if (!isRecord(value)) return null;
  if (
    value.contract !== "compass.public-acquisition-list.v1" ||
    value.mode !== "live" ||
    value.evidence_class !== "public-operational" ||
    !isTimestamp(value.generated_at) ||
    !isText(value.schedule) ||
    !isText(value.source_transport) ||
    !Array.isArray(value.acquisitions)
  ) return null;
  const acquisitions = value.acquisitions.map(parsePublicAcquisitionRecord);
  if (acquisitions.some((record) => record === null)) return null;
  if (value.source_health !== undefined && (!Array.isArray(value.source_health) || !value.source_health.every(isSourceHealth))) return null;
  if (value.evidence_threads !== undefined && (!Array.isArray(value.evidence_threads) || !value.evidence_threads.every(isEvidenceThread))) return null;
  return { ...value, acquisitions: acquisitions as PublicAcquisitionRecord[] } as PublicAcquisitionList;
}

export function parseContinuousPublicAcquisitionControl(value: unknown): ContinuousPublicAcquisitionControl | null {
  if (!isRecord(value)) return null;
  if (
    value.contract !== "compass.public-acquisition-continuous-control.v1" ||
    value.mode !== "live" ||
    value.evidence_class !== "public-operational" ||
    !["running", "stopped"].includes(String(value.status)) ||
    typeof value.enabled !== "boolean" ||
    typeof value.defaulted !== "boolean" ||
    typeof value.manual_runs_available !== "boolean" ||
    !isText(value.control_scope) ||
    !isOptionalText(value.updated_at) ||
    !isOptionalText(value.updated_by)
  ) return null;
  if ((value.status === "running") !== value.enabled) return null;
  if (value.updated_at != null && !isTimestamp(value.updated_at)) return null;
  return value as ContinuousPublicAcquisitionControl;
}

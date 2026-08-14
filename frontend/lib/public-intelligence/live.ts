import type {
  IntelligenceSnapshot,
  PublicIntelligenceCitation,
  PublicIntelligenceExplanationResponse,
  PublicIntelligenceModelEvidence,
  PublicIntelligenceRecord,
  PublicIntelligenceSnapshotResponse,
  PublicIntelligenceSnapshotSummary,
  PublicIntelligenceSourceEvidence,
  PublicExplanationEvidenceClass,
  PublicRecordEvidenceClass,
  PublicSource,
} from "./types";

export const PUBLIC_EXPLANATION_MAX_QUESTION_CHARS = 1_200;
export const PUBLIC_EXPLANATION_MAX_RECORD_IDS = 12;
export const PUBLIC_EXPLANATION_MAX_TOP_K = 6;

type JsonObject = Record<string, unknown>;

const PUBLIC_RECORD_EVIDENCE_CLASSES = new Set([
  "observed",
  "derived",
  "predicted",
  "public_observed",
  "public_derived",
  "public_predicted",
]);

const PUBLIC_EXPLANATION_EVIDENCE_CLASSES = new Set([
  ...PUBLIC_RECORD_EVIDENCE_CLASSES,
  "mixed_public_evidence",
]);

function asObject(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : null;
}

function cleanText(value: unknown, maxLength = 2_000): string {
  if (typeof value !== "string") return "";
  return value.replaceAll("\u2014", " - ").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function optionalText(value: unknown, maxLength = 2_000): string | null {
  const text = cleanText(value, maxLength);
  return text.length > 0 ? text : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function nonNegativeNumber(value: unknown): number | null {
  const parsed = finiteNumber(value);
  return parsed !== null && parsed >= 0 ? parsed : null;
}

function sha256(value: unknown): string | null {
  const digest = cleanText(value, 64).toLowerCase();
  return /^[a-f0-9]{64}$/.test(digest) ? digest : null;
}

function publicRecordEvidenceClass(value: unknown): PublicRecordEvidenceClass | null {
  const evidenceClass = cleanText(value, 80).toLowerCase();
  return PUBLIC_RECORD_EVIDENCE_CLASSES.has(evidenceClass)
    ? evidenceClass as PublicRecordEvidenceClass
    : null;
}

function publicExplanationEvidenceClass(value: unknown): PublicExplanationEvidenceClass | null {
  const evidenceClass = cleanText(value, 80).toLowerCase();
  return PUBLIC_EXPLANATION_EVIDENCE_CLASSES.has(evidenceClass)
    ? evidenceClass as PublicExplanationEvidenceClass
    : null;
}

function stringArray(value: unknown, maximum: number): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .slice(0, maximum)
    .map((item) => cleanText(item, 500))
    .filter(Boolean);
}

function parseIdentityScope(value: unknown): { role: string; org_unit: string } {
  const scope = asObject(value);
  return {
    role: cleanText(scope?.role, 80),
    org_unit: cleanText(scope?.org_unit, 120),
  };
}

function parseSource(value: unknown): PublicIntelligenceSourceEvidence | null {
  const source = asObject(value);
  if (!source) return null;
  const sourceId = cleanText(source.source_id ?? source.id, 80);
  if (!sourceId) return null;
  return {
    source_id: sourceId,
    count: nonNegativeNumber(source.count ?? source.record_count),
    state: cleanText(source.state ?? source.status, 120),
    scope: cleanText(source.scope ?? source.use, 1_000),
    url: cleanText(source.url ?? source.source_url, 2_048),
  };
}

function parseModel(value: unknown): PublicIntelligenceModelEvidence | null {
  const model = asObject(value);
  if (!model) return null;
  const modelId = cleanText(model.model_id ?? model.id, 160);
  if (!modelId) return null;
  return {
    model_id: modelId,
    model_run_id: optionalText(model.model_run_id, 160),
    state: cleanText(model.state ?? model.status, 120),
    approved: model.approved === true,
    deployed: model.deployed === true,
  };
}

function parseRecord(value: unknown): PublicIntelligenceRecord | null {
  const record = asObject(value);
  if (!record) return null;
  const recordId = cleanText(record.record_id, 240);
  const sourceId = cleanText(record.source_id, 80);
  const title = cleanText(record.title, 500);
  const sourceUrl = safeHttpsUrl(record.source_url);
  const evidenceClass = publicRecordEvidenceClass(record.evidence_class);
  const snapshotId = cleanText(record.snapshot_id, 160);
  const recordSha256 = sha256(record.record_sha256);
  if (!recordId || !sourceId || !title || !sourceUrl || !evidenceClass || !snapshotId || !recordSha256) return null;
  return {
    record_id: recordId,
    source_id: sourceId,
    title,
    summary: cleanText(record.summary, 500),
    source_url: sourceUrl,
    evidence_class: evidenceClass,
    model_run_id: optionalText(record.model_run_id, 160),
    uncertainty: record.uncertainty ?? null,
    snapshot_id: snapshotId,
    record_sha256: recordSha256,
  };
}

function parseCitation(value: unknown): PublicIntelligenceCitation | null {
  const citation = asObject(value);
  if (!citation) return null;
  const recordId = cleanText(citation.record_id, 240);
  const sourceId = cleanText(citation.source_id, 80);
  const title = cleanText(citation.title, 500);
  const sourceUrl = safeHttpsUrl(citation.source_url);
  const evidenceClass = publicRecordEvidenceClass(citation.evidence_class);
  const snapshotId = cleanText(citation.snapshot_id, 160);
  const recordSha256 = sha256(citation.record_sha256);
  const citationToken = cleanText(citation.citation_token, 180);
  if (!recordId || !sourceId || !title || !sourceUrl || !evidenceClass || !snapshotId || !recordSha256 || !citationToken) return null;
  return {
    record_id: recordId,
    source_id: sourceId,
    title,
    source_url: sourceUrl,
    evidence_class: evidenceClass,
    model_run_id: optionalText(citation.model_run_id, 160),
    uncertainty: citation.uncertainty ?? null,
    snapshot_id: snapshotId,
    record_sha256: recordSha256,
    citation_token: citationToken,
  };
}

export function parsePublicIntelligenceSnapshotResponse(
  value: unknown,
): PublicIntelligenceSnapshotResponse | null {
  const response = asObject(value);
  if (
    response?.contract !== "compass.public-intelligence.snapshot-response.v1" ||
    !cleanText(response.snapshot_id, 160) ||
    !cleanText(response.generated_at, 80) ||
    !cleanText(response.as_of_at, 80)
  ) {
    return null;
  }

  const provenance = asObject(response.provenance);
  const evidenceClass = response.evidence_class === "public_evidence" ? "public_evidence" : null;
  const manifestSha256 = sha256(provenance?.manifest_sha256);
  const indexSha256 = sha256(provenance?.index_sha256);
  const identityScope = parseIdentityScope(response.identity_scope);
  if (!manifestSha256 || !indexSha256 || !identityScope.role || !identityScope.org_unit || !evidenceClass) return null;
  const summary = asObject(response.snapshot) ?? {};
  const sources = Array.isArray(response.sources)
    ? response.sources.map(parseSource).filter((item): item is PublicIntelligenceSourceEvidence => item !== null)
    : [];
  const models = Array.isArray(response.models)
    ? response.models.map(parseModel).filter((item): item is PublicIntelligenceModelEvidence => item !== null)
    : [];
  const rawRecords = Array.isArray(response.records) ? response.records.slice(0, 5_000) : [];
  const records = rawRecords.map(parseRecord).filter((item): item is PublicIntelligenceRecord => item !== null);
  if (records.length !== rawRecords.length) return null;

  return {
    contract: "compass.public-intelligence.snapshot-response.v1",
    snapshot_id: cleanText(response.snapshot_id, 160),
    snapshot_version: finiteNumber(response.snapshot_version) ?? 1,
    generated_at: cleanText(response.generated_at, 80),
    as_of_at: cleanText(response.as_of_at, 80),
    evidence_class: evidenceClass,
    provenance: {
      manifest_sha256: manifestSha256,
      index_sha256: indexSha256,
      manifest_object_version: optionalText(provenance?.manifest_object_version, 200),
      index_object_version: optionalText(provenance?.index_object_version, 200),
    },
    identity_scope: identityScope,
    snapshot: summary as PublicIntelligenceSnapshotSummary,
    sources,
    models,
    record_count: nonNegativeNumber(response.record_count) ?? records.length,
    records,
    disclosure: cleanText(response.disclosure, 1_000),
  };
}

export function parsePublicIntelligenceExplanationResponse(
  value: unknown,
): PublicIntelligenceExplanationResponse | null {
  const response = asObject(value);
  if (response?.contract !== "compass.public-intelligence.explanation.v1") return null;
  const answer = cleanText(response.answer, 10_000);
  const runId = cleanText(response.explanation_run_id, 200);
  const snapshotId = cleanText(response.snapshot_id, 160);
  if (!answer || !runId || !snapshotId) return null;

  const grounded = response.grounded === true;
  const refused = response.refused === true;
  const rawCitations = Array.isArray(response.citations)
    ? response.citations.slice(0, PUBLIC_EXPLANATION_MAX_TOP_K)
    : [];
  const citations = rawCitations.map(parseCitation).filter((item): item is PublicIntelligenceCitation => item !== null);
  if (citations.length !== rawCitations.length) return null;
  if (grounded && citations.length === 0) return null;

  const rawEvidenceClass = cleanText(response.evidence_class, 80).toLowerCase();
  const refusalWithoutEvidence = refused && !grounded && rawEvidenceClass === "none" && citations.length === 0;
  const evidenceClass = refusalWithoutEvidence
    ? "none"
    : publicExplanationEvidenceClass(rawEvidenceClass);
  if (!evidenceClass || (!refusalWithoutEvidence && (refused || !grounded))) return null;
  if (citations.some((citation) => citation.snapshot_id !== snapshotId)) return null;

  const uncertainty = asObject(response.uncertainty);
  const generation = asObject(response.generation);
  const perRecord = Array.isArray(uncertainty?.per_record)
    ? uncertainty.per_record.slice(0, PUBLIC_EXPLANATION_MAX_TOP_K).flatMap((item) => {
        const record = asObject(item);
        const recordId = cleanText(record?.record_id, 240);
        return recordId ? [{ record_id: recordId, value: record?.value ?? null }] : [];
      })
    : [];

  return {
    contract: "compass.public-intelligence.explanation.v1",
    answer,
    grounded,
    refused,
    refusal_code: optionalText(response.refusal_code, 120),
    citations,
    evidence_class: evidenceClass,
    model_run_id: optionalText(response.model_run_id, 160),
    model_run_ids: stringArray(response.model_run_ids, 12),
    explanation_run_id: runId,
    uncertainty: {
      level: cleanText(uncertainty?.level, 120),
      basis: cleanText(uncertainty?.basis, 1_000),
      per_record: perRecord,
      limitations: stringArray(uncertainty?.limitations, 12),
    },
    generation: {
      provider: cleanText(generation?.provider, 120),
      model_id: optionalText(generation?.model_id, 200),
      usage: generation?.usage ?? null,
    },
    snapshot_id: snapshotId,
    identity_scope: parseIdentityScope(response.identity_scope),
  };
}

export function safeHttpsUrl(value: unknown): string | null {
  const text = cleanText(value, 2_048);
  if (!text) return null;
  try {
    const url = new URL(text);
    if (url.protocol !== "https:" || !url.hostname || url.username || url.password) return null;
    return url.href;
  } catch {
    return null;
  }
}

function normalizedSourceId(value: string): string {
  return value.trim().toLowerCase().replaceAll("_", "-");
}

function sourceDisplayName(value: string): string {
  return normalizedSourceId(value)
    .split("-")
    .filter(Boolean)
    .map((part) => part.length <= 4 ? part.toUpperCase() : `${part[0]?.toUpperCase() ?? ""}${part.slice(1)}`)
    .join(" ");
}

function sourceStatus(state: string, fallback: PublicSource["status"]): PublicSource["status"] {
  const normalized = state.toLowerCase();
  if (normalized.includes("persisted") || normalized.includes("complete")) return "persisted";
  if (normalized.includes("gated") || normalized.includes("restricted")) return "gated";
  if (normalized.includes("progress") || normalized.includes("scheduled") || normalized.includes("live")) return "scheduled";
  return fallback;
}

export function mergePublicIntelligenceSnapshot(
  bundled: IntelligenceSnapshot,
  live: PublicIntelligenceSnapshotResponse | null,
): IntelligenceSnapshot {
  if (!live) return bundled;

  const candidate = live.snapshot.candidate_scope;
  const legacyCorpus = asObject(live.snapshot.corpus);
  const awards = nonNegativeNumber(candidate?.grants ?? candidate?.award_records ?? legacyCorpus?.awards);
  const contracts = nonNegativeNumber(candidate?.contracts ?? legacyCorpus?.contracts);
  const candidateAwardValueUsd = nonNegativeNumber(
    candidate?.summed_award_amount_usd ?? legacyCorpus?.candidateAwardValueUsd,
  );
  const asOfDate = cleanText(live.snapshot.as_of_date, 32) || live.as_of_at.slice(0, 10);

  const annual = Array.isArray(live.snapshot.observed_annual_obligations)
    ? live.snapshot.observed_annual_obligations.flatMap((item) => {
        const fiscalYear = finiteNumber(item?.fiscal_year);
        const observedUsd = nonNegativeNumber(item?.observed_obligations_usd);
        if (fiscalYear === null || observedUsd === null) return [];
        return [{
          fiscalYear,
          observedUsd,
          forecastUsd: null,
          lowerUsd: null,
          upperUsd: null,
          isPartial: false,
        }];
      })
    : [];

  const recordCounts = new Map<string, number>();
  live.records.forEach((record) => {
    const sourceId = normalizedSourceId(record.source_id);
    recordCounts.set(sourceId, (recordCounts.get(sourceId) ?? 0) + 1);
  });
  const declaredSourceIds = new Set(live.sources.map((source) => normalizedSourceId(source.source_id)));
  const sources: PublicSource[] = live.sources.map((source) => ({
      id: normalizedSourceId(source.source_id),
      name: sourceDisplayName(source.source_id),
      authority: "Named authority in the verified public manifest",
      recordCount: source.count ?? recordCounts.get(normalizedSourceId(source.source_id)) ?? null,
      recordLabel: source.count !== null ? "records reported by the verified live manifest" : "records in the verified serving projection",
      status: sourceStatus(source.state, "scheduled"),
      lastObserved: asOfDate,
      use: source.scope,
      url: safeHttpsUrl(source.url) ?? "",
    }));
  for (const [sourceId, count] of recordCounts) {
    if (declaredSourceIds.has(sourceId)) continue;
    const first = live.records.find((record) => normalizedSourceId(record.source_id) === sourceId);
    sources.push({
      id: sourceId,
      name: sourceDisplayName(sourceId),
      authority: "Source named by verified serving records",
      recordCount: count,
      recordLabel: "records in the verified serving projection",
      status: "persisted",
      lastObserved: asOfDate,
      use: "Retained public evidence for governed analysis",
      url: safeHttpsUrl(first?.source_url) ?? "",
    });
  }

  const programs = live.records.map((record) => ({
    id: record.record_id,
    title: record.title,
    recipient: sourceDisplayName(record.source_id),
    source: sourceDisplayName(record.source_id),
    sourceUrl: safeHttpsUrl(record.source_url) ?? "",
    awardAmountUsd: null,
    startDate: asOfDate,
    endDate: asOfDate,
    technologyArea: null,
    transitionProbability: null,
    impactPercentile: null,
    confidence: null,
    scopeNote: live.disclosure,
    observedFacts: [
      record.summary || "The source record does not include a compact summary.",
      `Evidence class: ${record.evidence_class.replaceAll("_", " ")}`,
      `Record SHA-256: ${record.record_sha256}`,
    ],
  }));

  const models = live.models.map((model) => ({
    id: model.model_id,
    name: model.model_id,
    objective: "Model declared in the verified public evidence manifest.",
    algorithm: "Reported by retained model evidence",
    target: "Public evidence enrichment and review support",
    status: model.deployed ? "champion" as const : model.approved ? "validated" as const : model.state.toLowerCase().includes("candidate") ? "candidate" as const : "not-trained" as const,
    metric: "Retained model receipt",
    metricValue: null,
    metricLabel: model.model_run_id ?? "No run identifier reported",
    trainingRecords: 0,
    evidenceClass: "derived" as const,
    caveat: "Only state explicitly reported by the verified manifest is shown. No bundled registry fixture is substituted.",
  }));

  return {
    generatedAt: live.generated_at,
    asOfDate,
    corpus: { awards, contracts, candidateAwardValueUsd },
    sources,
    fundingFlow: annual,
    technologyAreas: [],
    programs,
    models,
  };
}

/**
 * Governed export replay. Filters are applied to the same curated portfolio
 * used by catalog and dashboard. Large requests require an unexpired,
 * fingerprint-bound approval that is consumed exactly once.
 */
import type {
  ExportApprovalRequiredBody,
  ExportRequest,
  ExportResponse,
  Role,
} from "@/lib/types";
import { replayActor } from "./actors";
import { effectiveRehearsalIdentity } from "./rehearsal-persona";
import { visibleGrants } from "./grants";
import {
  dynamicPortfolioAggregates,
  recordExportEvidence,
  registerDeniedExport,
  validateAndConsumeApproval,
} from "./scenario-store";

export const MOCK_EXPORT_MAX_ROWS = 8;

export type MockExportApprovalRequiredBody = ExportApprovalRequiredBody & {
  subject_type: "export";
  subject_id: string;
  how_to_clear: string;
};

export class ExportApprovalRequiredError extends Error {
  status = 428 as const;
  body: MockExportApprovalRequiredBody;

  constructor(body: MockExportApprovalRequiredBody) {
    super("approval_required");
    this.body = body;
  }
}

export class ExportAuthorizationError extends Error {
  constructor(code: string) {
    super(code);
    this.name = "ExportAuthorizationError";
  }
}

type NormalizedFilters = {
  program_area?: string;
  fiscal_year?: number;
  org_unit?: string;
  limit?: number;
};

const EXPORTABLE_COLUMNS = new Set([
  "id",
  "grant_no",
  "title",
  "abstract",
  "program_area",
  "fiscal_year",
  "amount_usd",
  "awardee",
  "org_unit",
  "classification_band",
  "batch_id",
  "created_at",
]);

const DEFAULT_COLUMNS = [
  "grant_no",
  "title",
  "program_area",
  "fiscal_year",
  "awardee",
  "org_unit",
  "classification_band",
  "batch_id",
  "created_at",
];

function normalizeFilters(filters: Record<string, unknown> | undefined): NormalizedFilters {
  if (!filters) return {};
  const supported = new Set(["program_area", "fiscal_year", "org_unit", "limit"]);
  const unsupported = Object.keys(filters).find((key) => !supported.has(key));
  if (unsupported) throw new ExportAuthorizationError(`unsupported_filter:${unsupported}`);
  if (
    filters.limit !== undefined &&
    (typeof filters.limit !== "number" ||
      !Number.isInteger(filters.limit) ||
      filters.limit <= 0)
  ) {
    throw new ExportAuthorizationError("limit_must_be_positive_integer");
  }
  return {
    ...(typeof filters.program_area === "string" && filters.program_area
      ? { program_area: filters.program_area }
      : {}),
    ...(typeof filters.fiscal_year === "number" && Number.isInteger(filters.fiscal_year)
      ? { fiscal_year: filters.fiscal_year }
      : {}),
    ...(typeof filters.org_unit === "string" && filters.org_unit ? { org_unit: filters.org_unit } : {}),
    ...(typeof filters.limit === "number" ? { limit: filters.limit } : {}),
  };
}

function normalizeColumns(columns: string[] | undefined, role: Role | null): string[] {
  const requested = columns ?? [
    ...DEFAULT_COLUMNS.slice(0, 4),
    ...(role === "poweruser" ? ["amount_usd"] : []),
    ...DEFAULT_COLUMNS.slice(4),
  ];
  if (!Array.isArray(requested) || requested.length === 0) {
    throw new ExportAuthorizationError("columns_must_be_non_empty_array");
  }
  const normalized: string[] = [];
  for (const value of requested) {
    if (typeof value !== "string" || !EXPORTABLE_COLUMNS.has(value)) {
      throw new ExportAuthorizationError("column_not_exportable");
    }
    if (role === "viewer" && value === "amount_usd") {
      throw new ExportAuthorizationError("column_level_security_amount_usd");
    }
    if (!normalized.includes(value)) normalized.push(value);
  }
  return normalized;
}

function matchesFilters(
  row: { program_area: string; fiscal_year: number; org_unit: string },
  filters: NormalizedFilters,
): boolean {
  if (filters.program_area && row.program_area !== filters.program_area) return false;
  if (filters.fiscal_year && row.fiscal_year !== filters.fiscal_year) return false;
  if (filters.org_unit && row.org_unit !== filters.org_unit) return false;
  return true;
}

function filteredRowCount(
  filters: NormalizedFilters,
  role: Role | null,
  orgUnit: string | null,
): number {
  const baseline = visibleGrants(role, orgUnit).filter((grant) => matchesFilters(grant, filters)).length;
  const replay = dynamicPortfolioAggregates(role, orgUnit)
    .filter((batch) => matchesFilters(batch, filters))
    .reduce((total, batch) => total + batch.grant_count, 0);
  return baseline + replay;
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

function requestFingerprint(
  req: ExportRequest,
  columns: string[],
  filters: NormalizedFilters,
  orgUnit: string | null,
): string {
  return canonical({
    org_unit: orgUnit ?? "none",
    format: req.format,
    columns: [...columns].sort(),
    filters: Object.fromEntries(
      Object.entries(filters)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, value]) => [key, String(value)]),
    ),
  });
}

function shortHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function subjectIdForFingerprint(fingerprint: string): string {
  const reverse = [...fingerprint].reverse().join("");
  return `exp-${shortHash(fingerprint)}${shortHash(reverse)}`;
}

function evidenceDataUrl(evidence: {
  export_id: string;
  row_count: number;
  format: string;
  requested_format: string;
  created_at: string;
  approval_id: number | null;
  fingerprint: string;
  columns: string[];
  filters: NormalizedFilters;
}): { url: string; bytes: number } {
  const manifest = {
    evidence_type: "COMPASS_DETERMINISTIC_REPLAY",
    export_id: evidence.export_id,
    generated_at: evidence.created_at,
    row_count: evidence.row_count,
    requested_format: evidence.requested_format,
    delivered_format: evidence.format,
    approval_id: evidence.approval_id,
    request_fingerprint: shortHash(evidence.fingerprint),
    columns: evidence.columns,
    filters: evidence.filters,
    contains_synthetic_data_only: true,
  };
  const payload = JSON.stringify(manifest, null, 2);
  return {
    url: `data:application/json;charset=utf-8,${encodeURIComponent(payload)}`,
    bytes: new TextEncoder().encode(payload).length,
  };
}

export async function runExport(
  req: ExportRequest,
  role: Role | null,
  orgUnit: string | null,
): Promise<ExportResponse> {
  ({ role, orgUnit } = effectiveRehearsalIdentity(role, orgUnit));
  const filters = normalizeFilters(req.filters);
  const columns = normalizeColumns(req.columns, role);
  const matchedRowCount = filteredRowCount(filters, role, orgUnit);
  const rowCount = filters.limit
    ? Math.min(matchedRowCount, filters.limit)
    : matchedRowCount;
  const actor = replayActor(role);
  const fingerprint = requestFingerprint(req, columns, filters, orgUnit);

  if (matchedRowCount > MOCK_EXPORT_MAX_ROWS && !req.approval_token) {
    const subjectId = subjectIdForFingerprint(fingerprint);
    registerDeniedExport(actor, fingerprint, matchedRowCount, subjectId);
    throw new ExportApprovalRequiredError({
      error: "approval_required",
      row_count: matchedRowCount,
      max_rows: MOCK_EXPORT_MAX_ROWS,
      subject_type: "export",
      subject_id: subjectId,
      how_to_clear: "Request approval for this subject, obtain its apr token from a separate persona, and retry the exact request once.",
    });
  }

  let approvalId: number | null = null;
  if (matchedRowCount > MOCK_EXPORT_MAX_ROWS) {
    if (!req.approval_token) throw new ExportAuthorizationError("approval_token_required");
    try {
      approvalId = (await validateAndConsumeApproval(req.approval_token, fingerprint)).id;
    } catch (error) {
      throw new ExportAuthorizationError(error instanceof Error ? error.message : "approval_token_invalid");
    }
  }

  const evidence = recordExportEvidence(
    actor,
    fingerprint,
    rowCount,
    "json",
    columns,
    filters,
    approvalId,
    req.format,
  );
  const artifact = evidenceDataUrl({ ...evidence, columns, filters });
  return {
    export_id: evidence.export_id,
    row_count: rowCount,
    matched_rows: matchedRowCount,
    format: "json",
    requested_format: req.format,
    download_url: artifact.url,
    delivery: "inline-data-uri",
    bytes: artifact.bytes,
    columns,
    masked_fields: role === "viewer" ? ["amount_usd"] : [],
    filters_applied: filters,
    note:
      "Replay mode delivers a deterministic JSON evidence manifest. The live service materializes the requested governed export format.",
    audited: true,
  };
}

export const exportTestSupport = {
  canonical,
  normalizeColumns,
  normalizeFilters,
  requestFingerprint,
  subjectIdForFingerprint,
};

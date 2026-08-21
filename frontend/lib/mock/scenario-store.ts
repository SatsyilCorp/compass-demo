/**
 * Persistent, deterministic replay state for the frontend demo.
 *
 * Every mock adapter reads this store. Mutations are written to localStorage
 * and broadcast to subscribers, so an ingest action is reflected by the
 * catalog, lineage, dashboard, analytics, export, approvals, and stream views.
 * The fixed logical clock keeps screenshots and rehearsals reproducible.
 */
import type { Approval, IngestBatch, Role, StreamRecord } from "@/lib/types";
import { clearRehearsalPersonaOverride } from "./rehearsal-persona";
import { replayActor } from "./actors";
import { ALL_GRANTS, type MockGrant } from "./grants";
import { buildQualityRows, overallScore } from "./quality";

export const SCENARIO_STORAGE_KEY = "compass:replay-scenario:v2";
export const SCENARIO_VERSION = 2 as const;
export const REPLAY_BASE_TIME = "2026-08-10T13:00:00.000Z";
export const QUALITY_GATE_THRESHOLD = 90;

export type ScenarioProfile = "clean" | "legacy" | "defective";

export type ScenarioBatch = IngestBatch & {
  profile: "baseline" | ScenarioProfile;
  baseline: boolean;
  org_unit: string;
  program_area: string;
  fiscal_year: number;
  classification_band: string;
  amount_usd: number;
  target_rows_raw: number;
  target_rows_curated: number;
};

export type ScenarioAnalysisRun = {
  run_id: string;
  created_at: string;
  status: "completed";
  included_batch_ids: string[];
};

export type ScenarioApproval = Approval & {
  request_fingerprint: string | null;
  expires_at: string;
  consumed_at: string | null;
  capability_hash: string | null;
};

export type ScenarioExportAttempt = {
  attempt_id: string;
  actor: string;
  fingerprint: string;
  row_count: number;
  created_at: string;
  approval_subject_id: string | null;
};

export type ScenarioExportEvidence = {
  export_id: string;
  actor: string;
  fingerprint: string;
  row_count: number;
  format: "csv" | "json" | "parquet";
  requested_format: "csv" | "json" | "parquet";
  columns: string[];
  filters: Record<string, unknown>;
  created_at: string;
  approval_id: number | null;
};

export type ScenarioState = {
  version: typeof SCENARIO_VERSION;
  mode: "replay";
  updated_at: string;
  logical_now: string;
  sequence: number;
  batches: ScenarioBatch[];
  analytics_runs: ScenarioAnalysisRun[];
  approvals: ScenarioApproval[];
  export_attempts: ScenarioExportAttempt[];
  exports: ScenarioExportEvidence[];
  events: StreamRecord[];
};

export type PortfolioAggregate = {
  batch_id: string;
  run_id: string;
  program_area: string;
  org_unit: string;
  fiscal_year: number;
  grant_count: number;
  amount_usd: number;
  created_at: string;
  quality_score: number;
};

const PROFILE_CONFIG: Record<
  ScenarioProfile,
  {
    label: string;
    source: string;
    rowsRaw: number;
    rowsCurated: number;
    amountUsd: number;
    programArea: string;
    orgUnit: string;
    fiscalYear: number;
    classificationBand: string;
  }
> = {
  clean: {
    label: "Clean research portfolio",
    source: "clean-portfolio.jsonl",
    rowsRaw: 48,
    rowsCurated: 48,
    amountUsd: 18_240_000,
    programArea: "Autonomous Systems",
    orgUnit: "Code-30",
    fiscalYear: 2026,
    classificationBand: "CUI-Mock",
  },
  legacy: {
    label: "Legacy finance extract",
    source: "legacy-finance.csv",
    rowsRaw: 62,
    rowsCurated: 58,
    amountUsd: 24_780_000,
    programArea: "Cyber & Information Systems",
    orgUnit: "Code-31",
    fiscalYear: 2025,
    classificationBand: "CUI-Mock",
  },
  defective: {
    label: "Defective vendor drop",
    source: "defective-vendor-drop.csv",
    rowsRaw: 40,
    rowsCurated: 0,
    amountUsd: 0,
    programArea: "Directed Energy",
    orgUnit: "Code-30",
    fiscalYear: 2026,
    classificationBand: "CUI-Mock",
  },
};

let state: ScenarioState = createInitialState();
let hydrated = false;
let storageListening = false;
const listeners = new Set<() => void>();

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function isoAdd(iso: string, seconds: number): string {
  return new Date(new Date(iso).getTime() + seconds * 1000).toISOString();
}

function dominant(rows: MockGrant[], key: "program_area" | "org_unit"): string {
  const counts = new Map<string, number>();
  for (const row of rows) counts.set(row[key], (counts.get(row[key]) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] ?? "Unknown";
}

function baseBatches(): ScenarioBatch[] {
  const grouped = new Map<string, MockGrant[]>();
  for (const grant of ALL_GRANTS) {
    const rows = grouped.get(grant.batch_id) ?? [];
    rows.push(grant);
    grouped.set(grant.batch_id, rows);
  }

  return [...grouped.entries()].map(([batch_id, rows]) => {
    const quality = buildQualityRows(batch_id, rows.length, "baseline");
    const score = overallScore(quality);
    return {
      batch_id,
      run_id: `run-${batch_id}`,
      source_file: `replay://synthetic/${batch_id}/portfolio.jsonl`,
      ingested_at: rows[0]?.created_at ?? REPLAY_BASE_TIME,
      status: "passed",
      rows_raw: rows.length,
      rows_curated: rows.length,
      quality,
      overall_score: score,
      profile: "baseline",
      baseline: true,
      org_unit: dominant(rows, "org_unit"),
      program_area: dominant(rows, "program_area"),
      fiscal_year: rows[0]?.fiscal_year ?? 2026,
      classification_band: rows[0]?.classification_band ?? "CUI-Mock",
      amount_usd: rows.reduce((total, row) => total + row.amount_usd, 0),
      target_rows_raw: rows.length,
      target_rows_curated: rows.length,
    };
  });
}

function baseEvents(): StreamRecord[] {
  const templates: { kind: StreamRecord["kind"]; text: string }[] = [
    { kind: "ingest", text: "Synthetic landing batch accepted" },
    { kind: "quality", text: "Five quality rules passed" },
    { kind: "analytics", text: "Portfolio topic weights refreshed" },
    { kind: "anomaly", text: "Amount outlier queued for review" },
    { kind: "approval", text: "Governance record written" },
    { kind: "export", text: "Scoped evidence export completed" },
  ];
  return ALL_GRANTS.slice(0, 18).map((grant, index) => {
    const template = templates[index % templates.length]!;
    return {
      id: `replay-seed-${String(index + 1).padStart(2, "0")}`,
      at: isoAdd(REPLAY_BASE_TIME, -(index + 1) * 180),
      kind: template.kind,
      message: `${template.text}: ${grant.grant_no}`,
      grant_no: grant.grant_no,
      org_unit: grant.org_unit,
    };
  });
}

function createInitialState(): ScenarioState {
  return {
    version: SCENARIO_VERSION,
    mode: "replay",
    updated_at: REPLAY_BASE_TIME,
    logical_now: REPLAY_BASE_TIME,
    sequence: 0,
    batches: baseBatches(),
    analytics_runs: [],
    approvals: [],
    export_attempts: [],
    exports: [],
    events: baseEvents(),
  };
}

function isStoredState(value: unknown): value is ScenarioState {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ScenarioState>;
  return (
    candidate.version === SCENARIO_VERSION &&
    candidate.mode === "replay" &&
    typeof candidate.logical_now === "string" &&
    typeof candidate.sequence === "number" &&
    Array.isArray(candidate.batches) &&
    Array.isArray(candidate.analytics_runs) &&
    Array.isArray(candidate.approvals) &&
    Array.isArray(candidate.export_attempts) &&
    Array.isArray(candidate.exports) &&
    Array.isArray(candidate.events)
  );
}

function attachStorageListener(): void {
  if (storageListening || typeof window === "undefined") return;
  storageListening = true;
  window.addEventListener("storage", (event) => {
    if (event.key !== SCENARIO_STORAGE_KEY || !event.newValue) return;
    try {
      const parsed = JSON.parse(event.newValue) as unknown;
      if (!isStoredState(parsed)) return;
      state = parsed;
      for (const listener of listeners) listener();
    } catch {
      // Ignore an incomplete cross-tab write and retain the last valid state.
    }
  });
}

function ensureHydrated(): void {
  if (hydrated) return;
  hydrated = true;
  if (typeof window === "undefined") return;
  attachStorageListener();
  try {
    const stored = window.localStorage.getItem(SCENARIO_STORAGE_KEY);
    if (!stored) return;
    const parsed = JSON.parse(stored) as unknown;
    if (isStoredState(parsed)) state = parsed;
  } catch {
    state = createInitialState();
  }
}

function persist(next: ScenarioState): void {
  const errors = scenarioInvariantErrors(next);
  if (errors.length > 0) throw new Error(`invalid_replay_state:${errors.join(",")}`);
  state = next;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(SCENARIO_STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Storage can be unavailable in private browsing. In-memory replay still works.
    }
  }
  for (const listener of listeners) listener();
}

function update(mutator: (draft: ScenarioState) => void, advanceSeconds = 15): ScenarioState {
  ensureHydrated();
  const draft = clone(state);
  draft.logical_now = isoAdd(draft.logical_now, advanceSeconds);
  draft.updated_at = draft.logical_now;
  mutator(draft);
  persist(draft);
  return draft;
}

function nextSequence(draft: ScenarioState): number {
  draft.sequence += 1;
  return draft.sequence;
}

function addEvent(
  draft: ScenarioState,
  kind: StreamRecord["kind"],
  message: string,
  orgUnit?: string,
  grantNo?: string,
): void {
  const sequence = nextSequence(draft);
  draft.events.unshift({
    id: `replay-event-${String(sequence).padStart(4, "0")}`,
    at: draft.logical_now,
    kind,
    message,
    ...(orgUnit ? { org_unit: orgUnit } : {}),
    ...(grantNo ? { grant_no: grantNo } : {}),
  });
  draft.events = draft.events.slice(0, 80);
}

export function getScenarioState(): Readonly<ScenarioState> {
  ensureHydrated();
  return clone(state);
}

export function subscribeScenario(listener: () => void): () => void {
  ensureHydrated();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function resetScenario(): ScenarioState {
  clearRehearsalPersonaOverride();
  hydrated = true;
  const next = createInitialState();
  persist(next);
  return next;
}

export function startScenarioBatch(profile: ScenarioProfile): ScenarioBatch {
  let created: ScenarioBatch | null = null;
  update((draft) => {
    const sequence = nextSequence(draft);
    const suffix = String(sequence).padStart(3, "0");
    const config = PROFILE_CONFIG[profile];
    const batch_id = `batch-replay-${profile}-${suffix}`;
    created = {
      batch_id,
      run_id: `run-${batch_id}`,
      source_file: `replay://synthetic/${profile}/${config.source}`,
      ingested_at: draft.logical_now,
      status: "queued",
      rows_raw: 0,
      rows_curated: 0,
      quality: [],
      overall_score: 0,
      profile,
      baseline: false,
      org_unit: config.orgUnit,
      program_area: config.programArea,
      fiscal_year: config.fiscalYear,
      classification_band: config.classificationBand,
      amount_usd: config.amountUsd,
      target_rows_raw: config.rowsRaw,
      target_rows_curated: config.rowsCurated,
    };
    draft.batches.unshift(created);
    addEvent(draft, "ingest", `${config.label} queued for replay`, config.orgUnit);
  }, 30);
  if (!created) throw new Error("replay_batch_not_created");
  return clone(created);
}

export function markScenarioBatchRunning(batchId: string): ScenarioBatch | null {
  let result: ScenarioBatch | null = null;
  update((draft) => {
    const batch = draft.batches.find((item) => item.batch_id === batchId);
    if (!batch || batch.status !== "queued") return;
    batch.status = "running";
    batch.rows_raw = batch.target_rows_raw;
    result = batch;
    addEvent(draft, "ingest", `Validation started for ${batch.batch_id}`, batch.org_unit);
  }, 12);
  return result ? clone(result) : null;
}

export function completeScenarioBatch(batchId: string): ScenarioBatch | null {
  let result: ScenarioBatch | null = null;
  update((draft) => {
    const batch = draft.batches.find((item) => item.batch_id === batchId);
    if (!batch || (batch.status !== "running" && batch.status !== "queued")) return;
    const profile = batch.profile === "baseline" ? "baseline" : batch.profile;
    const quality = buildQualityRows(batch.batch_id, batch.target_rows_raw, profile);
    const score = overallScore(quality);
    const passed = score >= QUALITY_GATE_THRESHOLD && profile !== "defective";
    batch.status = passed ? "passed" : "failed";
    batch.rows_raw = batch.target_rows_raw;
    batch.rows_curated = passed ? batch.target_rows_curated : 0;
    batch.amount_usd = passed ? batch.amount_usd : 0;
    batch.quality = quality;
    batch.overall_score = score;
    result = batch;
    addEvent(
      draft,
      passed ? "quality" : "anomaly",
      passed
        ? `Quality gate passed at ${score.toFixed(1)} for ${batch.batch_id}`
        : `Quality gate quarantined ${batch.batch_id} at ${score.toFixed(1)}`,
      batch.org_unit,
    );
  }, 18);
  return result ? clone(result) : null;
}

function canSee(role: Role | null, orgUnit: string | null, rowOrgUnit: string): boolean {
  return role === "poweruser" || orgUnit === "ONR-Corporate" || (!!orgUnit && orgUnit === rowOrgUnit);
}

export function visibleScenarioBatches(role: Role | null, orgUnit: string | null): ScenarioBatch[] {
  ensureHydrated();
  const visibleGrantRows =
    role === "poweruser" || orgUnit === "ONR-Corporate"
      ? ALL_GRANTS
      : orgUnit
        ? ALL_GRANTS.filter((grant) => grant.org_unit === orgUnit)
        : [];

  return state.batches
    .flatMap((batch): ScenarioBatch[] => {
      if (!batch.baseline) return canSee(role, orgUnit, batch.org_unit) ? [clone(batch)] : [];
      const scopedRows = visibleGrantRows.filter((grant) => grant.batch_id === batch.batch_id);
      if (scopedRows.length === 0) return [];
      const scopedQuality = buildQualityRows(batch.batch_id, scopedRows.length, "baseline");
      return [
        {
          ...clone(batch),
          rows_raw: scopedRows.length,
          rows_curated: batch.status === "passed" ? scopedRows.length : 0,
          target_rows_raw: scopedRows.length,
          target_rows_curated: batch.status === "passed" ? scopedRows.length : 0,
          quality: scopedQuality,
          overall_score: overallScore(scopedQuality),
          amount_usd: scopedRows.reduce((total, grant) => total + grant.amount_usd, 0),
          org_unit: role === "poweruser" ? "ONR-Corporate" : (orgUnit ?? batch.org_unit),
          program_area: dominant(scopedRows, "program_area"),
          fiscal_year: scopedRows[0]?.fiscal_year ?? batch.fiscal_year,
        },
      ];
    })
    .sort((a, b) => b.ingested_at.localeCompare(a.ingested_at));
}

export function dynamicPortfolioAggregates(role: Role | null, orgUnit: string | null): PortfolioAggregate[] {
  return visibleScenarioBatches(role, orgUnit)
    .filter((batch) => !batch.baseline && batch.status === "passed" && batch.rows_curated > 0)
    .map((batch) => ({
      batch_id: batch.batch_id,
      run_id: batch.run_id,
      program_area: batch.program_area,
      org_unit: batch.org_unit,
      fiscal_year: batch.fiscal_year,
      grant_count: batch.rows_curated,
      amount_usd: batch.amount_usd,
      created_at: batch.ingested_at,
      quality_score: batch.overall_score,
    }));
}

export function recordAnalyticsRun(): ScenarioAnalysisRun {
  let created: ScenarioAnalysisRun | null = null;
  update((draft) => {
    const sequence = nextSequence(draft);
    created = {
      run_id: `analytics-replay-${String(sequence).padStart(4, "0")}`,
      created_at: draft.logical_now,
      status: "completed",
      included_batch_ids: draft.batches
        .filter((batch) => !batch.baseline && batch.status === "passed" && batch.rows_curated > 0)
        .map((batch) => batch.batch_id)
        .sort(),
    };
    draft.analytics_runs.unshift(created);
    draft.analytics_runs = draft.analytics_runs.slice(0, 12);
    addEvent(draft, "analytics", `Topic analysis ${created.run_id} completed`);
  }, 24);
  if (!created) throw new Error("replay_analysis_not_created");
  return clone(created);
}

export function clearAnalyticsRuns(): void {
  update((draft) => {
    draft.analytics_runs = [];
    addEvent(draft, "analytics", "Replay analytics history reset");
  }, 5);
}

export function findAnalyticsRun(runId: string): ScenarioAnalysisRun | null {
  ensureHydrated();
  const run = state.analytics_runs.find((item) => item.run_id === runId);
  return run ? clone(run) : null;
}

export function getAnalyticsHistory(): ScenarioAnalysisRun[] {
  ensureHydrated();
  return clone(state.analytics_runs);
}

export function registerDeniedExport(
  actor: string,
  fingerprint: string,
  rowCount: number,
  subjectId: string,
): void {
  update((draft) => {
    const sequence = nextSequence(draft);
    draft.export_attempts.unshift({
      attempt_id: `export-attempt-${String(sequence).padStart(4, "0")}`,
      actor,
      fingerprint,
      row_count: rowCount,
      created_at: draft.logical_now,
      approval_subject_id: subjectId,
    });
    draft.export_attempts = draft.export_attempts.slice(0, 30);
    addEvent(draft, "export", `Aggregation guard blocked ${rowCount} replay rows`);
  }, 8);
}

export function createOrUpdateScenarioApproval(
  subjectType: string,
  subjectId: string,
  action: "request" | "approve" | "reject",
  actor: string,
  note?: string,
  capabilityHash?: string,
): ScenarioApproval {
  let result: ScenarioApproval | null = null;
  update((draft) => {
    const matching = draft.approvals.filter(
      (approval) => approval.subject_type === subjectType && approval.subject_id === subjectId,
    );
    if (action === "request") {
      const pending = matching.find(
        (approval) =>
          approval.state === "pending" &&
          approval.requested_by === actor &&
          new Date(approval.expires_at).getTime() > new Date(draft.logical_now).getTime(),
      );
      if (pending) {
        result = pending;
        return;
      }
      let fingerprint: string | null = null;
      if (subjectType === "export") {
        const attempt = draft.export_attempts.find(
          (candidate) =>
            candidate.actor === actor && candidate.approval_subject_id === subjectId,
        );
        if (!attempt) throw new Error("export_approval_has_no_blocked_request");
        fingerprint = attempt.fingerprint;
      }
      const sequence = nextSequence(draft);
      const approval: ScenarioApproval = {
        id: 1000 + sequence,
        subject_type: subjectType,
        subject_id: subjectId,
        state: "pending",
        requested_by: actor,
        decided_by: null,
        decided_at: null,
        note: note ?? null,
        created_at: draft.logical_now,
        request_fingerprint: fingerprint,
        expires_at: isoAdd(draft.logical_now, 15 * 60),
        consumed_at: null,
        capability_hash: null,
      };
      draft.approvals.unshift(approval);
      result = approval;
      addEvent(draft, "approval", `Approval ${approval.id} requested for ${subjectType}`);
      return;
    }

    const existing = matching.find((approval) => approval.state === "pending");
    if (!existing) throw new Error("approval_not_found");
    if (new Date(existing.expires_at).getTime() <= new Date(draft.logical_now).getTime()) {
      throw new Error("approval_expired");
    }
    if (existing.requested_by === actor) throw new Error("self_approval_blocked");
    if (existing.state !== "pending") throw new Error("approval_not_pending");
    if (action === "approve" && !capabilityHash) throw new Error("approval_hash_required");
    existing.state = action === "approve" ? "approved" : "rejected";
    existing.decided_by = actor;
    existing.decided_at = draft.logical_now;
    existing.note = note ?? existing.note;
    existing.capability_hash = action === "approve" ? capabilityHash! : null;
    result = existing;
    addEvent(draft, "approval", `Approval ${existing.id} ${existing.state} by a separate persona`);
  }, 10);
  if (!result) throw new Error("replay_approval_not_created");
  return clone(result);
}

export async function validateAndConsumeApproval(
  token: string,
  fingerprint: string,
): Promise<ScenarioApproval> {
  const {
    constantTimeTextEqual,
    parseOpaqueApprovalToken,
    replayCapabilityHash,
  } = await import("./approval-token");
  const parsed = parseOpaqueApprovalToken(token);
  if (!parsed) throw new Error("approval_token_invalid");
  const presentedHash = await replayCapabilityHash(parsed.secret);
  let result: ScenarioApproval | null = null;
  update((draft) => {
    const approval = draft.approvals.find((candidate) => candidate.id === parsed.approvalId);
    if (!approval || approval.subject_type !== "export") throw new Error("approval_token_invalid");
    if (
      !approval.capability_hash ||
      !constantTimeTextEqual(approval.capability_hash, presentedHash)
    ) {
      throw new Error("approval_token_invalid");
    }
    if (approval.state !== "approved") throw new Error("approval_not_approved");
    if (approval.request_fingerprint !== fingerprint) throw new Error("approval_fingerprint_mismatch");
    if (approval.consumed_at) throw new Error("approval_capability_consumed");
    if (new Date(approval.expires_at).getTime() <= new Date(draft.logical_now).getTime()) {
      throw new Error("approval_expired");
    }
    approval.consumed_at = draft.logical_now;
    result = approval;
  }, 2);
  if (!result) throw new Error("approval_token_invalid");
  return clone(result);
}

export function recordExportEvidence(
  actor: string,
  fingerprint: string,
  rowCount: number,
  format: "csv" | "json" | "parquet",
  columns: string[],
  filters: Record<string, unknown>,
  approvalId: number | null,
  requestedFormat: "csv" | "json" | "parquet" = format,
): ScenarioExportEvidence {
  let result: ScenarioExportEvidence | null = null;
  update((draft) => {
    const sequence = nextSequence(draft);
    result = {
      export_id: `export-replay-${String(sequence).padStart(4, "0")}`,
      actor,
      fingerprint,
      row_count: rowCount,
      format,
      requested_format: requestedFormat,
      columns: clone(columns),
      filters: clone(filters),
      created_at: draft.logical_now,
      approval_id: approvalId,
    };
    draft.exports.unshift(result);
    draft.exports = draft.exports.slice(0, 20);
    addEvent(draft, "export", `${rowCount} scoped rows released as ${format.toUpperCase()} evidence`);
  }, 6);
  if (!result) throw new Error("replay_export_not_recorded");
  return clone(result);
}

export function pendingApprovalCount(role?: Role | null): number {
  ensureHydrated();
  const now = new Date(state.logical_now).getTime();
  return state.approvals.filter(
    (approval) =>
      approval.state === "pending" &&
      new Date(approval.expires_at).getTime() > now &&
      (role !== "viewer" || approval.requested_by === replayActor("viewer")),
  ).length;
}

export function scenarioInvariantErrors(candidate: ScenarioState): string[] {
  const errors: string[] = [];
  for (const batch of candidate.batches) {
    if (batch.rows_raw < 0 || batch.rows_curated < 0) errors.push(`${batch.batch_id}:negative_rows`);
    if (batch.rows_curated > batch.rows_raw) errors.push(`${batch.batch_id}:curated_exceeds_raw`);
    if (batch.status === "failed" && batch.rows_curated !== 0) errors.push(`${batch.batch_id}:failed_is_curated`);
    if (batch.overall_score < 0 || batch.overall_score > 100) errors.push(`${batch.batch_id}:invalid_score`);
    for (const quality of batch.quality) {
      if (quality.failed_rows < 0 || quality.passed_rows < 0) errors.push(`${batch.batch_id}:negative_quality_rows`);
      if (quality.failed_rows + quality.passed_rows !== batch.rows_raw) {
        errors.push(`${batch.batch_id}:quality_row_total`);
      }
      if (quality.score < 0 || quality.score > 100) errors.push(`${batch.batch_id}:invalid_quality_score`);
    }
  }
  const approvalIds = new Set<number>();
  for (const approval of candidate.approvals) {
    if (approvalIds.has(approval.id)) errors.push(`approval:${approval.id}:duplicate_id`);
    approvalIds.add(approval.id);
    if (approval.consumed_at && approval.state !== "approved") errors.push(`approval:${approval.id}:consumed_without_approval`);
    if (approval.state === "approved" && !approval.capability_hash) errors.push(`approval:${approval.id}:missing_capability_hash`);
    if (approval.state !== "approved" && approval.capability_hash) errors.push(`approval:${approval.id}:unexpected_capability_hash`);
  }
  return [...new Set(errors)];
}

export function scenarioMetadata(): { mode: "replay"; generated_at: string; storage_key: string } {
  ensureHydrated();
  return {
    mode: "replay",
    generated_at: state.updated_at,
    storage_key: SCENARIO_STORAGE_KEY,
  };
}

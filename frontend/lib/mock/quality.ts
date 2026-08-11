/**
 * Synthetic data-quality gate results, shared by lib/mock/catalog.ts and
 * lib/mock/ingest.ts so a batch's quality numbers agree in both places.
 * Mirrors `grant_quality` in db/migrations/001_schema.sql. The score is
 * always shown WITH the rule that produced it, never a bare number.
 */
import type { QualityRuleResult } from "@/lib/types";

const RULES = [
  "not_null_required_fields",
  "valid_fiscal_year_range",
  "amount_usd_within_bounds",
  "org_unit_recognized",
  "grant_no_unique",
] as const;

/** Cheap deterministic string hash (djb2) so a given batch_id always yields
 * the same synthetic quality numbers across renders/builds. */
function hash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i);
  return h >>> 0;
}

export type QualityProfile = "baseline" | "clean" | "legacy" | "defective";

const FAILURE_RATES: Record<Exclude<QualityProfile, "baseline">, readonly number[]> = {
  clean: [0, 0, 0, 0, 0],
  legacy: [0.03, 0.06, 0.04, 0.02, 0.05],
  defective: [0.35, 0.2, 0.42, 0.28, 0.32],
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function buildQualityRows(
  batchId: string,
  rowCount: number,
  profile: QualityProfile = "baseline",
): QualityRuleResult[] {
  const safeRowCount = Math.max(0, Math.floor(rowCount));
  return RULES.map((rule, index) => {
    let failedRows: number;
    if (profile === "baseline") {
      const maxFailures = Math.floor(safeRowCount * 0.02);
      failedRows = maxFailures === 0 ? 0 : hash(`${batchId}:${rule}`) % (maxFailures + 1);
    } else {
      const rate = FAILURE_RATES[profile][index] ?? 0;
      failedRows = Math.round(safeRowCount * rate);
    }
    const failed_rows = clamp(failedRows, 0, safeRowCount);
    const passed_rows = safeRowCount - failed_rows;
    const score =
      safeRowCount === 0
        ? 100
        : clamp(Math.round((passed_rows / safeRowCount) * 1000) / 10, 0, 100);
    return { rule, passed_rows, failed_rows, score };
  });
}

export function overallScore(rows: QualityRuleResult[]): number {
  if (rows.length === 0) return 100;
  const avg = rows.reduce((acc, r) => acc + r.score, 0) / rows.length;
  return clamp(Math.round(avg * 10) / 10, 0, 100);
}

/**
 * Synthetic data-quality gate results, shared by lib/mock/catalog.ts and
 * lib/mock/ingest.ts so a batch's quality numbers agree in both places.
 * Mirrors `grant_quality` in db/migrations/001_schema.sql — the score is
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

export function buildQualityRows(batchId: string, rowCount: number): QualityRuleResult[] {
  const base = hash(batchId);
  return RULES.map((rule, i) => {
    // Each rule fails a small, deterministic slice of the batch (0-3 rows).
    const failed_rows = Math.min(rowCount, (base >> (i * 3)) % 4);
    const passed_rows = rowCount - failed_rows;
    const score = rowCount === 0 ? 100 : Math.round((passed_rows / rowCount) * 1000) / 10;
    return { rule, passed_rows, failed_rows, score };
  });
}

export function overallScore(rows: QualityRuleResult[]): number {
  if (rows.length === 0) return 100;
  const avg = rows.reduce((acc, r) => acc + r.score, 0) / rows.length;
  return Math.round(avg * 10) / 10;
}

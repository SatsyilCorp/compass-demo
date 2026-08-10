/**
 * GET /catalog — fixture. One entry per ingest batch (the natural "dataset"
 * grain for the S&T portfolio catalog), enriched with quality score +
 * metadata. Element 4 (catalog / quality / lineage / metadata).
 */
import type { CatalogEntry, CatalogResponse, Role } from "@/lib/types";
import { ALL_GRANTS, maskAmount, sum, visibleGrants } from "./grants";
import { buildQualityRows, overallScore } from "./quality";

const SOURCE_FILE_FOR_BATCH: Record<string, string> = {};
for (const g of ALL_GRANTS) {
  if (!SOURCE_FILE_FOR_BATCH[g.batch_id]) {
    SOURCE_FILE_FOR_BATCH[g.batch_id] = `s3://compass-landing/${g.batch_id}/onr_grants_export.jsonl`;
  }
}

export function getCatalog(role: Role | null, orgUnit: string | null): CatalogResponse {
  const visible = visibleGrants(role, orgUnit);
  const batchIds = Array.from(new Set(visible.map((g) => g.batch_id))).sort();

  const datasets: CatalogEntry[] = batchIds.map((batch_id) => {
    const rows = visible.filter((g) => g.batch_id === batch_id);
    const first = rows[0]!;
    const quality_rules = buildQualityRows(batch_id, rows.length);
    const amount = sum(rows.map((r) => maskAmount(role, r.amount_usd)));
    // Program area / org_unit shown on the catalog card: the dominant one
    // in the batch (batches are mixed-program in this synthetic portfolio).
    const programCounts = new Map<string, number>();
    for (const r of rows) programCounts.set(r.program_area, (programCounts.get(r.program_area) ?? 0) + 1);
    const dominantProgram = [...programCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? first.program_area;

    return {
      id: batch_id,
      batch_id,
      run_id: `run-${batch_id}`,
      dataset_name: `grants_curated · ${batch_id}`,
      source_file: SOURCE_FILE_FOR_BATCH[batch_id] ?? `s3://compass-landing/${batch_id}/onr_grants_export.jsonl`,
      program_area: dominantProgram,
      org_unit: role === "poweruser" ? "ONR-Corporate" : (orgUnit ?? first.org_unit),
      fiscal_year: first.fiscal_year,
      row_count: rows.length,
      amount_usd: amount,
      quality_score: overallScore(quality_rules),
      quality_rules,
      classification_band: first.classification_band,
      ingested_at: first.created_at,
      owner: "Compass Ingest Pipeline",
    };
  });

  return { datasets };
}

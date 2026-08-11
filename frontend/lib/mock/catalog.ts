/**
 * Curated dataset catalog derived from the persistent replay store.
 * Quarantined, queued, and running batches are intentionally absent because
 * none of them has produced a curated dataset.
 */
import type { CatalogEntry, CatalogResponse, Role } from "@/lib/types";
import { maskAmount } from "./grants";
import { visibleScenarioBatches } from "./scenario-store";

export function getCatalog(role: Role | null, orgUnit: string | null): CatalogResponse {
  const datasets: CatalogEntry[] = visibleScenarioBatches(role, orgUnit)
    .filter((batch) => batch.status === "passed" && batch.rows_curated > 0)
    .map((batch) => ({
      id: batch.batch_id,
      batch_id: batch.batch_id,
      run_id: batch.run_id,
      dataset_name: `grants_curated | ${batch.batch_id}`,
      source_file: batch.source_file,
      program_area: batch.program_area,
      org_unit: batch.org_unit,
      fiscal_year: batch.fiscal_year,
      row_count: batch.rows_curated,
      amount_usd: maskAmount(role, batch.amount_usd),
      quality_score: batch.overall_score,
      quality_rules: batch.quality,
      classification_band: batch.classification_band,
      ingested_at: batch.ingested_at,
      owner: batch.baseline ? "Compass Synthetic Baseline" : "Compass Replay Engine",
    }));

  return { datasets };
}

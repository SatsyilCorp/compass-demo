/**
 * Curated dataset catalog derived from the persistent replay store.
 * Quarantined, queued, and running batches are intentionally absent because
 * none of them has produced a curated dataset.
 */
import type { CatalogEntry, CatalogResponse, Role } from "@/lib/types";
import { maskAmount } from "./grants";
import { visibleScenarioBatches } from "./scenario-store";

const DATA_DICTIONARY: CatalogEntry["data_dictionary"] = [
  {
    field: "grant_no",
    data_type: "text",
    definition: "Source award or grant identifier used for reconciliation and citations.",
    security: "Visible within the caller's row-level scope.",
  },
  {
    field: "title",
    data_type: "text",
    definition: "Normalized project or award title supplied by the accepted source.",
    security: "Visible within the caller's row-level scope.",
  },
  {
    field: "program_area",
    data_type: "text",
    definition: "Governed portfolio category used for filtering and aggregation.",
    security: "Visible within the caller's row-level scope.",
  },
  {
    field: "amount_usd",
    data_type: "numeric",
    definition: "Normalized obligated or awarded funding amount in US dollars.",
    security: "Column-level security masks this field for non-entitled roles.",
  },
  {
    field: "org_unit",
    data_type: "text",
    definition: "Organization scope that drives the database access policy.",
    security: "PostgreSQL row-level security enforces this boundary.",
  },
  {
    field: "classification_band",
    data_type: "text",
    definition: "Demonstration handling label attached during curation.",
    security: "Mock labels only. Government markings require an authorized policy source.",
  },
];

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
      owner: "Portfolio Data Product Owner (demo role)",
      steward: "Data Quality Steward (demo role)",
      data_dictionary: DATA_DICTIONARY,
    }));

  return { datasets };
}

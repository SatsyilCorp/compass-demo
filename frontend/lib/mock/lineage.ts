/**
 * GET /catalog/{id}/lineage — fixture. `{id}` is a batch_id from
 * lib/mock/catalog.ts. Mirrors `lineage_nodes` / `lineage_edges` in
 * db/migrations/001_schema.sql: source -> stage -> table -> model ->
 * dashboard, the same run-level DAG the real ingest/analysis pipeline
 * would emit. Element 4.
 */
import type { LineageResponse } from "@/lib/types";
import { getCatalog } from "./catalog";
import type { Role } from "@/lib/types";

export function getLineage(id: string, role: Role | null, orgUnit: string | null): LineageResponse | null {
  const { datasets } = getCatalog(role, orgUnit);
  const entry = datasets.find((d) => d.id === id);
  if (!entry) return null;

  const run_id = entry.run_id;

  return {
    run_id,
    nodes: [
      { run_id, node_id: "src-file", kind: "source", label: entry.source_file, meta: { format: "jsonl" } },
      {
        run_id,
        node_id: "raw",
        kind: "table",
        label: "grants_raw",
        meta: { rows: entry.row_count, batch_id: entry.batch_id },
      },
      {
        run_id,
        node_id: "quality-gate",
        kind: "stage",
        label: "Quality gate",
        meta: { overall_score: entry.quality_score, rules: entry.quality_rules.length },
      },
      {
        run_id,
        node_id: "curated",
        kind: "table",
        label: "grants_curated",
        meta: { rows: entry.row_count, org_unit: entry.org_unit, classification_band: entry.classification_band },
      },
      {
        run_id,
        node_id: "topic-model",
        kind: "model",
        label: "Topic model (amazon.nova-lite-v1:0 + titan-embed-text-v2)",
        meta: { program_area: entry.program_area },
      },
      {
        run_id,
        node_id: "exec-dashboard",
        kind: "dashboard",
        label: "Executive dashboard",
        meta: {},
      },
    ],
    edges: [
      { run_id, from_node: "src-file", to_node: "raw" },
      { run_id, from_node: "raw", to_node: "quality-gate" },
      { run_id, from_node: "quality-gate", to_node: "curated" },
      { run_id, from_node: "curated", to_node: "topic-model" },
      { run_id, from_node: "curated", to_node: "exec-dashboard" },
      { run_id, from_node: "topic-model", to_node: "exec-dashboard" },
    ],
  };
}

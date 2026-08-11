/**
 * Run-level lineage from the same batch projection used by ingest and catalog.
 * A failed gate terminates at quarantine and never draws a false curated,
 * model, or dashboard edge.
 */
import type { LineageEdge, LineageNode, LineageResponse, Role } from "@/lib/types";
import { visibleScenarioBatches } from "./scenario-store";

export function getLineage(
  id: string,
  role: Role | null,
  orgUnit: string | null,
): LineageResponse | null {
  const batch = visibleScenarioBatches(role, orgUnit).find((candidate) => candidate.batch_id === id);
  if (!batch) return null;

  const run_id = batch.run_id;
  const nodes: LineageNode[] = [
    {
      run_id,
      node_id: "src-file",
      kind: "source",
      label: batch.source_file,
      meta: { format: batch.source_file.endsWith(".jsonl") ? "jsonl" : "csv", replay: true },
    },
    {
      run_id,
      node_id: "raw",
      kind: "table",
      label: "grants_raw",
      meta: { rows: batch.rows_raw, batch_id: batch.batch_id },
    },
    {
      run_id,
      node_id: "quality-gate",
      kind: "stage",
      label: "Quality gate",
      meta: {
        status: batch.status,
        overall_score: batch.overall_score,
        rules: batch.quality.length,
      },
    },
  ];
  const edges: LineageEdge[] = [
    { run_id, from_node: "src-file", to_node: "raw" },
    { run_id, from_node: "raw", to_node: "quality-gate" },
  ];

  if (batch.status === "failed") {
    nodes.push({
      run_id,
      node_id: "quarantine",
      kind: "stage",
      label: "Quarantine",
      meta: { rows: batch.rows_raw, reason: "quality_threshold_not_met", replay: true },
    });
    edges.push({ run_id, from_node: "quality-gate", to_node: "quarantine" });
    return { run_id, nodes, edges };
  }

  if (batch.status === "queued" || batch.status === "running") {
    return { run_id, nodes, edges };
  }

  nodes.push(
    {
      run_id,
      node_id: "curated",
      kind: "table",
      label: "grants_curated",
      meta: {
        rows: batch.rows_curated,
        org_unit: batch.org_unit,
        classification_band: batch.classification_band,
      },
    },
    {
      run_id,
      node_id: "topic-model",
      kind: "model",
      label: "Governed topic model",
      meta: { program_area: batch.program_area, replay: true },
    },
    {
      run_id,
      node_id: "exec-dashboard",
      kind: "dashboard",
      label: "Executive dashboard",
      meta: { replay: true },
    },
  );
  edges.push(
    { run_id, from_node: "quality-gate", to_node: "curated" },
    { run_id, from_node: "curated", to_node: "topic-model" },
    { run_id, from_node: "curated", to_node: "exec-dashboard" },
    { run_id, from_node: "topic-model", to_node: "exec-dashboard" },
  );
  return { run_id, nodes, edges };
}

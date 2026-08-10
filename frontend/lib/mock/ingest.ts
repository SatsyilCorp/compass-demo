/**
 * GET /ingest/status, POST /ingest/simulate — fixtures. Element 3.
 */
import type { IngestBatch, IngestSimulateResponse, IngestStatusResponse, Role } from "@/lib/types";
import { ALL_GRANTS, BATCH_IDS, visibleGrants } from "./grants";
import { buildQualityRows, overallScore } from "./quality";

export function getIngestStatus(role: Role | null, orgUnit: string | null): IngestStatusResponse {
  const visible = new Set(visibleGrants(role, orgUnit).map((g) => g.batch_id));
  const batches: IngestBatch[] = BATCH_IDS.filter((b) => visible.has(b))
    .map((batch_id) => {
      const rows = ALL_GRANTS.filter((g) => g.batch_id === batch_id && visible.has(g.batch_id));
      const rows_curated = rows.length;
      const quality = buildQualityRows(batch_id, rows_curated);
      const score = overallScore(quality);
      return {
        batch_id,
        run_id: `run-${batch_id}`,
        source_file: `s3://compass-landing/${batch_id}/onr_grants_export.jsonl`,
        ingested_at: rows[0]?.created_at ?? new Date().toISOString(),
        status: score >= 90 ? "passed" : "failed",
        rows_raw: rows_curated + (quality.reduce((a, r) => a + r.failed_rows, 0) > 0 ? 2 : 0),
        rows_curated,
        quality,
        overall_score: score,
      } satisfies IngestBatch;
    })
    .sort((a, b) => b.ingested_at.localeCompare(a.ingested_at));

  return { batches };
}

/** POST /ingest/simulate — a synthesized "just triggered" batch. Demo
 * convenience only; does not mutate the fixture dataset above. */
export function simulateIngest(): IngestSimulateResponse {
  const now = new Date();
  const batch_id = `batch-demo-${now.getTime()}`;
  return {
    batch_id,
    run_id: `run-${batch_id}`,
    source_file: `s3://compass-landing/${batch_id}/onr_grants_export.jsonl`,
    status: "queued",
    triggered_at: now.toISOString(),
  };
}

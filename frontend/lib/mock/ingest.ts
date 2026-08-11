/**
 * Ingest replay adapter. Batch progress is persisted in scenario-store so
 * every mock screen reads the same status, quality result, and curated count.
 */
import type { IngestSimulateResponse, IngestStatusResponse, Role } from "@/lib/types";
import {
  completeScenarioBatch,
  markScenarioBatchRunning,
  resetScenario,
  startScenarioBatch,
  subscribeScenario,
  visibleScenarioBatches,
  type ScenarioProfile,
} from "./scenario-store";

export function getIngestStatus(role: Role | null, orgUnit: string | null): IngestStatusResponse {
  const batches = visibleScenarioBatches(role, orgUnit).map((batch) => ({
    batch_id: batch.batch_id,
    run_id: batch.run_id,
    source_file: batch.source_file,
    ingested_at: batch.ingested_at,
    status: batch.status,
    rows_raw: batch.rows_raw,
    rows_curated: batch.status === "failed" ? 0 : batch.rows_curated,
    quality: batch.quality,
    overall_score: batch.overall_score,
  }));
  return { batches };
}

export function simulateIngest(profile: ScenarioProfile = "clean"): IngestSimulateResponse {
  const batch = startScenarioBatch(profile);
  return {
    batch_id: batch.batch_id,
    run_id: batch.run_id,
    source_file: batch.source_file,
    status: "queued",
    triggered_at: batch.ingested_at,
  };
}

export function advanceSimulatedIngest(batchId: string, stage: "running" | "completed"): void {
  if (stage === "running") {
    markScenarioBatchRunning(batchId);
    return;
  }
  completeScenarioBatch(batchId);
}

export { resetScenario as resetIngestReplay, subscribeScenario as subscribeIngestReplay };
export type { ScenarioProfile };

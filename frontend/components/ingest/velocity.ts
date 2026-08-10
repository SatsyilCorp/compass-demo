/**
 * Ingestion velocity classification — element 3.
 *
 * Compass runs three different cadences over the exact same intake state
 * machine (statemachines/intake.asl.yaml: Fetch -> Validate -> Persist /
 * Quarantine):
 *
 *   batch       a full portfolio export dropped as one file, one batch_id.
 *   interval    a partner feed picked up on a fixed schedule (e.g. every
 *               15 min via EventBridge Scheduler); each pickup is its own
 *               batch.
 *   on-demand   an object landing in the raw bucket fires the
 *               RawObjectCreatedRule immediately — the path
 *               POST /ingest/simulate exercises for this demo.
 *
 * docs/CONTRACTS.md's `IngestBatch` shape carries no velocity field, so the
 * tag shown on a fixture batch is a deterministic, illustrative client-side
 * classification for the demo list — never presented as a value read from
 * the API or database. A batch produced by the "Drop a file" button on
 * /ingest IS genuinely on-demand (that is literally what
 * POST /ingest/simulate is), so it is forced rather than hashed — see
 * `components/ingest/batch-row.tsx`.
 */

export type Velocity = "batch" | "interval" | "on-demand";

export const VELOCITY_META: Record<
  Velocity,
  { label: string; cadence: string; blurb: string }
> = {
  batch: {
    label: "Batch",
    cadence: "bulk · ad hoc",
    blurb:
      "A full portfolio export dropped as one file and processed end to end as a single batch_id.",
  },
  interval: {
    label: "Interval",
    cadence: "scheduled · e.g. every 15 min",
    blurb:
      "A partner feed picked up on a fixed cadence via EventBridge Scheduler — each pickup is its own batch.",
  },
  "on-demand": {
    label: "On-demand",
    cadence: "real-time",
    blurb:
      "An object landing in the raw bucket fires RawObjectCreatedRule immediately. POST /ingest/simulate exercises this same path.",
  },
};

/** Deterministic djb2 string hash — same algorithm lib/mock/quality.ts uses,
 * so demo-only classification derived from it never looks random between
 * renders/builds. */
export function hashStr(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = (h * 33) ^ s.charCodeAt(i);
  return h >>> 0;
}

const ORDER: Velocity[] = ["batch", "interval", "on-demand"];

/** Illustrative-only velocity tag for a fixture batch_id (see module docstring). */
export function velocityForBatch(batchId: string): Velocity {
  return ORDER[hashStr(batchId) % ORDER.length]!;
}

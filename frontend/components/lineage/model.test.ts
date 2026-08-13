import assert from "node:assert/strict";
import test from "node:test";

import type { OperationsLineageStage } from "../../lib/types";
import { isAttentionStatus, lineageProgress, orderedStages, shortDigest } from "./model";

function stage(sequence: number, status: OperationsLineageStage["status"]): OperationsLineageStage {
  return {
    stage_id: `stage-${sequence}`,
    sequence,
    label: `Stage ${sequence}`,
    system: "Test system",
    status,
    updated_at: "2026-08-12T21:00:00.000Z",
    started_at: null,
    completed_at: null,
    duration_ms: null,
    source_sha256: null,
    input_sha256: null,
    output_sha256: null,
    record_count: null,
    artifact_count: null,
    receipt: null,
    attempt: 1,
    actor: null,
    source_revision: null,
    failure_code: null,
    detail: "Test receipt",
  };
}

test("lineage stages are ordered by server sequence", () => {
  const stages = orderedStages([stage(3, "pending"), stage(1, "completed"), stage(2, "running")]);
  assert.deepEqual(stages.map((item) => item.sequence), [1, 2, 3]);
});

test("lineage progress follows receipt states instead of elapsed browser time", () => {
  const progress = lineageProgress([
    stage(1, "completed"),
    stage(2, "running"),
    stage(3, "pending"),
    stage(4, "quarantined"),
  ]);
  assert.deepEqual(progress, { complete: 2, active: 1, pending: 1, total: 4, percentage: 50 });
});

test("digests remain inspectable while cards use a bounded projection", () => {
  const digest = "a".repeat(64);
  assert.equal(shortDigest(digest, 8), `${"a".repeat(8)}...${"a".repeat(8)}`);
  assert.equal(shortDigest(null), "Not recorded");
});

test("failed, quarantined, and expired runs require attention", () => {
  assert.equal(isAttentionStatus("failed"), true);
  assert.equal(isAttentionStatus("quarantined"), true);
  assert.equal(isAttentionStatus("expired"), true);
  assert.equal(isAttentionStatus("completed"), false);
});

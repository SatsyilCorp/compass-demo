import assert from "node:assert/strict";
import test from "node:test";

import type { OperationsLineageStage } from "../../lib/types";
import {
  evidenceClassPresentation,
  isLivePublicOperationsEvidenceClass,
  normalizeOperationsEvidenceClass,
} from "../../lib/operations-evidence";
import { isAttentionStatus, lineageProgress, orderedStages, shortDigest } from "./model";

function stage(sequence: number, status: OperationsLineageStage["status"]): OperationsLineageStage {
  return {
    stage_id: `stage-${sequence}`,
    evidence_class: "unclassified",
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

test("evidence labels distinguish provenance from the deployed adapter", () => {
  assert.equal(normalizeOperationsEvidenceClass("synthetic_demo"), "synthetic-demo");
  assert.equal(evidenceClassPresentation("synthetic-demo").label, "Synthetic demo evidence");
  assert.equal(evidenceClassPresentation("public-observed").label, "Observed public evidence");
  assert.equal(evidenceClassPresentation("public-predicted").label, "Predicted public evidence");
  assert.equal(evidenceClassPresentation("operational-control").label, "Operational control");
  assert.equal(evidenceClassPresentation("unclassified").label, "Unclassified evidence");
});

test("live operations allow only public evidence and operational controls", () => {
  assert.equal(isLivePublicOperationsEvidenceClass("public-observed"), true);
  assert.equal(isLivePublicOperationsEvidenceClass("public"), true);
  assert.equal(isLivePublicOperationsEvidenceClass("operational-control"), true);
  assert.equal(isLivePublicOperationsEvidenceClass("synthetic-demo"), false);
  assert.equal(isLivePublicOperationsEvidenceClass("mixed-evidence"), false);
  assert.equal(isLivePublicOperationsEvidenceClass("unclassified"), false);
});

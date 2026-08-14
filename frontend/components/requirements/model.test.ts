import assert from "node:assert/strict";
import test from "node:test";

import {
  PRESENTER_SEQUENCE,
  REQUIREMENTS,
  STATUS_META,
  TRACE_STATUSES,
  countByStatus,
  resolveOperationalRequirementStates,
} from "./model";
import type { OperationsRunSummary, OperationsSummaryResponse } from "../../lib/types";

const EXACT_DEMO_ASKS = [
  "Governed intake and quality",
  "Catalog and metadata",
  "Lineage",
  "Decision analytics",
  "Real model lifecycle",
  "Drift and monitoring",
  "Alerts and notifications",
  "Continuous multi-source public acquisition",
  "DevSecOps and IaC",
  "Identity and access",
  "Controlled release and API",
  "IL4/IL5 target",
];

test("requirements proof contains exactly the meeting demo asks", () => {
  assert.deepEqual(REQUIREMENTS.map((item) => item.title), EXACT_DEMO_ASKS);
  assert.equal(new Set(REQUIREMENTS.map((item) => item.id)).size, REQUIREMENTS.length);
});

test("every ask contains action, live evidence, implementation locators, differentiator, and caveat", () => {
  for (const item of REQUIREMENTS) {
    assert.ok(item.intent.length > 30, item.id);
    assert.ok(item.userAction.length > 30, item.id);
    assert.ok(item.liveEvidence.length > 0, item.id);
    assert.ok(item.liveEvidence.some((target) => target.kind === "screen" || target.kind === "api"), item.id);
    assert.ok(item.locators.source.length > 0, `${item.id}: source`);
    assert.ok(item.locators.tests.length > 0, `${item.id}: tests`);
    assert.ok(item.locators.iac.length > 0, `${item.id}: iac`);
    assert.ok(item.differentiator.length > 30, item.id);
    assert.ok(item.caveat.length > 30, item.id);
  }
});

test("all five evidence states remain explicit even when no requirement needs every state", () => {
  const totals = countByStatus();
  for (const status of TRACE_STATUSES) {
    assert.ok(STATUS_META[status].label.length > 0, status);
    assert.ok(totals[status] >= 0, status);
  }
  assert.equal(Object.values(totals).reduce((sum, value) => sum + value, 0), REQUIREMENTS.length);
});

test("presenter sequence covers each demo ask exactly once", () => {
  const sequenced = PRESENTER_SEQUENCE.flatMap((step) => step.requirementIds);
  assert.deepEqual([...sequenced].sort(), REQUIREMENTS.map((item) => item.id).sort());
  assert.equal(new Set(sequenced).size, REQUIREMENTS.length);
  assert.deepEqual(PRESENTER_SEQUENCE.map((step) => step.order), [1, 2, 3, 4, 5]);
  for (const step of PRESENTER_SEQUENCE) {
    assert.match(step.href, /^\/.+\/$/);
    assert.ok(step.instruction.length > 30);
  }
});

test("continuous acquisition starts configured and upgrades only from live proof", () => {
  const acquisition = REQUIREMENTS.find((item) => item.id === "continuous-public-acquisition");
  const ilTarget = REQUIREMENTS.find((item) => item.id === "il4-il5-target");

  assert.equal(acquisition?.status, "configured");
  assert.match(acquisition?.caveat ?? "", /responsible cadence/i);
  assert.equal(ilTarget?.status, "target-architecture");
  assert.match(ilTarget?.caveat ?? "", /not IL4 or IL5 authorized/i);
});

test("operational requirements fail closed when evidence is missing or invalid", () => {
  const operationalIds = [
    "governed-intake-quality",
    "catalog-metadata",
    "lineage",
    "decision-analytics",
    "real-model-lifecycle",
    "drift-monitoring",
    "continuous-public-acquisition",
    "controlled-release-api",
  ];
  const withoutEvidence = resolveOperationalRequirementStates(REQUIREMENTS, null);
  for (const id of operationalIds) {
    assert.equal(withoutEvidence.find((item) => item.id === id)?.status, "configured", id);
  }

  const replay = liveOperationsSummary();
  replay.mode = "replay";
  const fromReplay = resolveOperationalRequirementStates(REQUIREMENTS, replay);
  assert.equal(fromReplay.find((item) => item.id === "continuous-public-acquisition")?.status, "configured");

  const invalid = liveOperationsSummary();
  invalid.generated_at = "not-a-timestamp";
  const fromInvalid = resolveOperationalRequirementStates(REQUIREMENTS, invalid);
  assert.equal(fromInvalid.find((item) => item.id === "governed-intake-quality")?.status, "configured");
});

test("only a completed public receipt with matching accepted watermark promotes acquisition proof", () => {
  const operations = liveOperationsSummary();
  let resolved = resolveOperationalRequirementStates(REQUIREMENTS, operations);
  for (const id of ["governed-intake-quality", "lineage", "continuous-public-acquisition"]) {
    assert.equal(resolved.find((item) => item.id === id)?.status, "verified-live", id);
  }
  assert.equal(resolved.find((item) => item.id === "catalog-metadata")?.status, "configured");
  assert.equal(resolved.find((item) => item.id === "decision-analytics")?.status, "configured");
  assert.equal(resolved.find((item) => item.id === "controlled-release-api")?.status, "configured");

  operations.runs[0] = { ...operations.runs[0], evidence_class: "synthetic-demo" };
  resolved = resolveOperationalRequirementStates(REQUIREMENTS, operations);
  assert.equal(resolved.find((item) => item.id === "continuous-public-acquisition")?.status, "configured");

  operations.runs[0] = { ...publicRun(), completed_stages: 3, stage_count: 4 };
  resolved = resolveOperationalRequirementStates(REQUIREMENTS, operations);
  assert.equal(resolved.find((item) => item.id === "lineage")?.status, "configured");
});

test("model and drift asks promote only from completed public run receipts", () => {
  const operations = liveOperationsSummary();
  operations.runs.push(
    publicRun({ run_id: "model-verified", run_kind: "sagemaker-batch-inference" }),
    publicRun({ run_id: "drift-verified", run_kind: "model-drift" }),
  );
  const resolved = resolveOperationalRequirementStates(REQUIREMENTS, operations);
  assert.equal(resolved.find((item) => item.id === "real-model-lifecycle")?.status, "verified-live");
  assert.equal(resolved.find((item) => item.id === "drift-monitoring")?.status, "verified-live");
});

test("live public evidence is primary and rehearsal is explicit", () => {
  const intake = REQUIREMENTS.find((item) => item.id === "governed-intake-quality");
  const decision = REQUIREMENTS.find((item) => item.id === "decision-analytics");
  const firstStop = PRESENTER_SEQUENCE[0];

  assert.equal(firstStop.href, "/admin/acquisition/");
  assert.match(firstStop.instruction, /accepted public run/i);
  assert.match(intake?.caveat ?? "", /separate rehearsal workspace/i);
  assert.match(decision?.caveat ?? "", /explicit selection/i);
});

function publicRun(overrides: Partial<OperationsRunSummary> = {}): OperationsRunSummary {
  return {
    run_id: "acq-usaspending-verified",
    run_kind: "public-acquisition",
    label: "Public acquisition",
    evidence_class: "public-observed",
    status: "completed",
    current_stage: "accepted",
    started_at: "2026-08-13T12:00:00.000Z",
    updated_at: "2026-08-13T12:01:00.000Z",
    completed_at: "2026-08-13T12:01:00.000Z",
    completed_stages: 4,
    stage_count: 4,
    source: {
      id: "https://api.usaspending.gov",
      label: "USAspending API",
      kind: "public_authority",
      sha256: "a".repeat(64),
    },
    model: null,
    consumer: null,
    counts: { input_records: 10, output_records: 10, quarantined_records: 0, artifacts: 2 },
    ...overrides,
  };
}

function liveOperationsSummary(): OperationsSummaryResponse {
  return {
    contract: "compass.operations.summary.v1",
    mode: "live",
    generated_at: "2026-08-13T12:02:00.000Z",
    counts: { runs_total: 1, runs_active: 0, runs_attention: 0, signals_unread: 0 },
    runs: [publicRun()],
    source_watermarks: [{
      source_id: "usaspending",
      label: "USAspending API",
      status: "current",
      last_attempt_at: "2026-08-13T12:00:00.000Z",
      last_accepted_at: "2026-08-13T12:01:00.000Z",
      watermark: "2026-08-13T12:00:00.000Z",
      added_records: 10,
      changed_records: 0,
      unchanged_records: 0,
      not_observed_records: 0,
      run_id: "acq-usaspending-verified",
    }],
    disclosure: "Protected live operational evidence.",
  };
}

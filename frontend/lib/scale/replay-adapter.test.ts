import assert from "node:assert/strict";
import test from "node:test";

import { ScaleAdapterError } from "./errors";
import { replayScaleAdapter, resetScaleReplay } from "./replay-adapter";

test("fixed scale profiles expose bounded capacity states", async () => {
  resetScaleReplay();
  const response = await replayScaleAdapter.getProfiles();
  assert.deepEqual(response.profiles.map((profile) => profile.id), ["1k", "10k", "100k", "1m"]);
  assert.equal(response.profiles.find((profile) => profile.id === "1m")?.capacity_state, "locked");
  assert.ok(response.profiles.filter((profile) => profile.capacity_state === "ready").length >= 3);
});

test("plan binds deterministic dataset totals and a hard cost ceiling", async () => {
  resetScaleReplay();
  const first = await replayScaleAdapter.previewPlan({ profile_id: "10k", seed: 424_242 });
  const second = await replayScaleAdapter.previewPlan({ profile_id: "10k", seed: 424_242 });

  assert.equal(first.plan_id, second.plan_id);
  assert.equal(first.total_records, 10_000);
  assert.equal(first.dataset_mix.reduce((sum, row) => sum + row.records, 0), 10_000);
  assert.deepEqual(
    first.dataset_mix.map(({ domain, percentage }) => [domain, percentage]),
    [
      ["grants", 20],
      ["finance", 30],
      ["milestones", 20],
      ["documents", 10],
      ["licenses", 2],
      ["stream_events", 18],
    ],
  );
  assert.deepEqual(first.stages.slice(0, 3).map((stage) => stage.id), ["plan", "buffer", "generate"]);
  assert.equal(first.dataset_mix.some((row) => row.purpose.toLowerCase().includes("searchable")), false);
  assert.ok(first.cost.estimated_run_usd > 0);
  assert.ok(first.cost.upper_bound_usd > first.cost.estimated_run_usd);
  assert.equal(first.cost.incremental_idle_monthly_usd, 0);
});

test("launch idempotency returns one run and polling completes with evidence", async () => {
  resetScaleReplay();
  const plan = await replayScaleAdapter.previewPlan({ profile_id: "1k", seed: 7 });
  const request = { plan_id: plan.plan_id, idempotency_key: "launch-test-one" };
  const first = await replayScaleAdapter.launchRun(request);
  const repeated = await replayScaleAdapter.launchRun(request);
  assert.equal(first.run_id, repeated.run_id);

  let current = first;
  for (let attempt = 0; attempt < 8 && current.status !== "completed"; attempt += 1) {
    current = await replayScaleAdapter.getRun(first.run_id);
  }
  assert.equal(current.status, "completed");
  assert.equal(current.progress.records_generated, 1_000);
  assert.equal(current.progress.records_curated + current.progress.records_quarantined, 1_000);
  assert.equal(current.evidence.stages.every((stage) => stage.status === "completed"), true);
  assert.match(current.evidence.manifest_sha256, /^[a-f0-9]{64}$/);
});

test("locked capacity fails closed before a run is created", async () => {
  resetScaleReplay();
  const plan = await replayScaleAdapter.previewPlan({ profile_id: "1m", seed: 11 });
  await assert.rejects(
    () => replayScaleAdapter.launchRun({ plan_id: plan.plan_id, idempotency_key: "locked-test" }),
    (error) => error instanceof ScaleAdapterError && error.status === 409 && error.body.error === "capacity_locked",
  );
  assert.equal((await replayScaleAdapter.listRuns()).runs.length, 0);
});

test("cancellation reaches a terminal receipt and governed export is asynchronous", async () => {
  resetScaleReplay();
  const cancelPlan = await replayScaleAdapter.previewPlan({ profile_id: "10k", seed: 13 });
  const cancelRun = await replayScaleAdapter.launchRun({ plan_id: cancelPlan.plan_id, idempotency_key: "cancel-test" });
  const cancelling = await replayScaleAdapter.cancelRun(cancelRun.run_id);
  assert.equal(cancelling.status, "cancelling");
  const cancelled = await replayScaleAdapter.getRun(cancelRun.run_id);
  assert.equal(cancelled.status, "cancelled");

  const exportPlan = await replayScaleAdapter.previewPlan({ profile_id: "1k", seed: 17 });
  const started = await replayScaleAdapter.launchRun({ plan_id: exportPlan.plan_id, idempotency_key: "export-run-test" });
  let completed = started;
  for (let attempt = 0; attempt < 8 && completed.status !== "completed"; attempt += 1) {
    completed = await replayScaleAdapter.getRun(started.run_id);
  }
  const receipt = await replayScaleAdapter.requestExport(completed.run_id, {
    dataset: "curated_portfolio",
    format: "parquet",
    idempotency_key: "export-receipt-test",
  });
  assert.equal(receipt.status, "building");
  assert.ok(receipt.export_id);
  const ready = await replayScaleAdapter.getExport(completed.run_id, receipt.export_id!);
  assert.equal(ready.status, "ready");
  assert.match(ready.sha256!, /^[a-f0-9]{64}$/);
  assert.match(ready.object_uri!, /^lake:\/\/scale-runs\//);
  assert.equal(ready.object_uri!.includes("s3://"), false);
  assert.equal(ready.row_count, completed.progress.records_curated);
});

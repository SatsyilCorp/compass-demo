import assert from "node:assert/strict";
import test from "node:test";

import { getAnalyticsRun, runAnalytics } from "./analytics";
import { REPLAY_ACTORS } from "./actors";
import { createOrAdvanceApproval, listPendingApprovals } from "./approvals";
import { getCatalog } from "./catalog";
import { getDashboard } from "./dashboard";
import {
  ExportApprovalRequiredError,
  ExportAuthorizationError,
  runExport,
} from "./export";
import { getIngestStatus } from "./ingest";
import { getLineage } from "./lineage";
import { buildQualityRows, overallScore } from "./quality";
import {
  completeScenarioBatch,
  getScenarioState,
  markScenarioBatchRunning,
  resetScenario,
  scenarioInvariantErrors,
  startScenarioBatch,
} from "./scenario-store";
import { getStreamRecent } from "./stream";

test("quality profiles stay within valid row and score bounds", () => {
  for (const profile of ["baseline", "clean", "legacy", "defective"] as const) {
    const rows = buildQualityRows("batch-test", 62, profile);
    for (const row of rows) {
      assert.equal(row.passed_rows + row.failed_rows, 62);
      assert.ok(row.failed_rows >= 0);
      assert.ok(row.score >= 0 && row.score <= 100);
    }
  }
  assert.ok(overallScore(buildQualityRows("clean", 62, "clean")) >= 90);
  assert.ok(overallScore(buildQualityRows("legacy", 62, "legacy")) >= 90);
  assert.ok(overallScore(buildQualityRows("defective", 62, "defective")) < 90);
});

test("scenario actions produce one consistent portfolio projection", () => {
  resetScenario();
  const completed = ["clean", "legacy", "defective"].map((profile) => {
    const batch = startScenarioBatch(profile as "clean" | "legacy" | "defective");
    markScenarioBatchRunning(batch.batch_id);
    return completeScenarioBatch(batch.batch_id)!;
  });

  assert.equal(completed[0]?.status, "passed");
  assert.equal(completed[1]?.status, "passed");
  assert.equal(completed[2]?.status, "failed");
  assert.equal(completed[2]?.rows_curated, 0);
  assert.deepEqual(scenarioInvariantErrors(getScenarioState()), []);

  const ingest = getIngestStatus("poweruser", "ONR-Corporate");
  const failed = ingest.batches.find((batch) => batch.batch_id === completed[2]?.batch_id);
  assert.equal(failed?.rows_curated, 0);

  const catalog = getCatalog("poweruser", "ONR-Corporate");
  assert.ok(catalog.datasets.some((dataset) => dataset.batch_id === completed[0]?.batch_id));
  assert.ok(catalog.datasets.some((dataset) => dataset.batch_id === completed[1]?.batch_id));
  assert.ok(!catalog.datasets.some((dataset) => dataset.batch_id === completed[2]?.batch_id));

  const failedLineage = getLineage(completed[2]!.batch_id, "poweruser", "ONR-Corporate");
  assert.ok(failedLineage?.nodes.some((node) => node.node_id === "quarantine"));
  assert.ok(!failedLineage?.nodes.some((node) => node.node_id === "curated"));

  const dashboard = getDashboard("poweruser", "ONR-Corporate");
  assert.equal(dashboard.kpis.total_grants, 28 + 48 + 58);
  const analytics = getAnalyticsRun("analytics-test", "poweruser", "ONR-Corporate");
  assert.equal(
    analytics.topics.reduce((total, topic) => total + topic.grant_count, 0),
    dashboard.kpis.total_grants,
  );

  const stream = getStreamRecent("poweruser", "ONR-Corporate");
  assert.ok(stream.records.some((record) => record.message.includes(completed[2]!.batch_id)));
});

test("export approval is opaque, separate, bound, expiring, and single use", async () => {
  resetScenario();
  const request = {
    format: "csv" as const,
    columns: ["grant_no", "title"],
    filters: {},
  };

  let guard: ExportApprovalRequiredError["body"] | null = null;
  try {
    await runExport(request, "viewer", "Code-30");
  } catch (error) {
    if (error instanceof ExportApprovalRequiredError) guard = error.body;
  }
  assert.ok(guard);
  assert.equal(guard.row_count, 9);
  assert.equal(guard.subject_type, "export");
  assert.match(guard.subject_id, /^exp-[a-f0-9]{16}$/);

  let repeatedSubject = "";
  try {
    await runExport(request, "viewer", "Code-30");
  } catch (error) {
    if (error instanceof ExportApprovalRequiredError) repeatedSubject = error.body.subject_id;
  }
  assert.equal(repeatedSubject, guard.subject_id);

  const pending = (await createOrAdvanceApproval(
    { subject_type: "export", subject_id: guard.subject_id, action: "request" },
    "viewer",
  )).approval;
  const repeated = (await createOrAdvanceApproval(
    { subject_type: "export", subject_id: guard.subject_id, action: "request" },
    "viewer",
  )).approval;
  assert.equal(repeated.id, pending.id);
  assert.equal(pending.requested_by, REPLAY_ACTORS.viewer);
  const viewerInbox = listPendingApprovals("viewer");
  const reviewerInbox = listPendingApprovals("poweruser");
  assert.equal(viewerInbox.approvals.length, 1);
  assert.equal(reviewerInbox.approvals.length, 1);
  assert.equal(viewerInbox.tokens_included, false);
  assert.ok(!JSON.stringify(reviewerInbox).includes("approval_token"));
  await assert.rejects(
    async () =>
      createOrAdvanceApproval(
        { subject_type: "export", subject_id: guard.subject_id, action: "approve" },
        "viewer",
      ),
    /self_approval_blocked/,
  );

  const approvedResponse = await createOrAdvanceApproval(
    { subject_type: "export", subject_id: guard.subject_id, action: "approve" },
    "poweruser",
  );
  const approved = approvedResponse.approval;
  assert.equal(approved.state, "approved");
  assert.equal(approved.decided_by, REPLAY_ACTORS.poweruser);
  assert.match(approvedResponse.approval_token!, /^apr-\d+\.[A-Za-z0-9_-]{43}$/);
  assert.ok(!JSON.stringify(getScenarioState()).includes(approvedResponse.approval_token!));

  await assert.rejects(
    async () =>
      runExport(
        { ...request, format: "json", approval_token: approvedResponse.approval_token! },
        "viewer",
        "Code-30",
      ),
    (error) =>
      error instanceof ExportAuthorizationError && error.message === "approval_fingerprint_mismatch",
  );

  await assert.rejects(
    async () =>
      runExport(
        { ...request, approval_token: `apr-${approved.id}` },
        "viewer",
        "Code-30",
      ),
    (error) =>
      error instanceof ExportAuthorizationError && error.message === "approval_token_invalid",
  );

  const validToken = approvedResponse.approval_token!;
  const wrongSecretToken = `${validToken.slice(0, -1)}${validToken.endsWith("A") ? "B" : "A"}`;
  await assert.rejects(
    async () =>
      runExport(
        { ...request, approval_token: wrongSecretToken },
        "viewer",
        "Code-30",
      ),
    (error) =>
      error instanceof ExportAuthorizationError && error.message === "approval_token_invalid",
  );

  const released = await runExport(
    { ...request, approval_token: approvedResponse.approval_token! },
    "viewer",
    "Code-30",
  );
  assert.equal(released.row_count, 9);
  assert.ok(released.download_url.startsWith("data:application/json"));

  await assert.rejects(
    async () =>
      runExport(
        { ...request, approval_token: approvedResponse.approval_token! },
        "viewer",
        "Code-30",
      ),
    (error) =>
      error instanceof ExportAuthorizationError && error.message === "approval_capability_consumed",
  );
});

test("filtered exports use exact curated scope", async () => {
  resetScenario();
  const result = await runExport(
    {
      format: "json",
      columns: ["grant_no", "program_area"],
      filters: { program_area: "Hypersonics" },
    },
    "poweruser",
    "ONR-Corporate",
  );
  assert.equal(result.row_count, 2);
});

test("viewer requests for the protected amount column fail like live mode", async () => {
  resetScenario();
  await assert.rejects(
    async () =>
      runExport(
        {
          format: "json",
          columns: ["grant_no", "amount_usd", "title"],
          filters: { program_area: "Hypersonics" },
        },
        "viewer",
        "Code-30",
      ),
    (error) =>
      error instanceof ExportAuthorizationError &&
      error.message === "column_level_security_amount_usd",
  );
});

test("replay rejects the old columns-inside-filters wire shape", async () => {
  resetScenario();
  await assert.rejects(
    async () =>
      runExport(
        {
          format: "json",
          filters: { columns: ["grant_no", "title"] },
        },
        "viewer",
        "Code-30",
      ),
    (error) =>
      error instanceof ExportAuthorizationError &&
      error.message === "unsupported_filter:columns",
  );
});

test("released evidence keeps columns top-level and predicates in filters", async () => {
  resetScenario();
  const result = await runExport(
    {
      format: "json",
      columns: ["grant_no", "program_area"],
      filters: { program_area: "Hypersonics" },
    },
    "poweruser",
    "ONR-Corporate",
  );
  const encoded = result.download_url.split(",", 2)[1] ?? "";
  const manifest = JSON.parse(decodeURIComponent(encoded)) as {
    columns: string[];
    filters: Record<string, unknown>;
  };
  assert.deepEqual(manifest.columns, ["grant_no", "program_area"]);
  assert.deepEqual(manifest.filters, { program_area: "Hypersonics" });
  assert.ok(!("columns" in manifest.filters));
});

test("approval decisions fail after the deterministic expiry window", async () => {
  resetScenario();
  let subjectId = "";
  try {
    await runExport({ format: "csv" }, "viewer", "Code-30");
  } catch (error) {
    if (error instanceof ExportApprovalRequiredError) subjectId = error.body.subject_id;
  }
  assert.match(subjectId, /^exp-/);
  await createOrAdvanceApproval(
    { subject_type: "export", subject_id: subjectId, action: "request" },
    "viewer",
  );
  for (let index = 0; index < 31; index += 1) startScenarioBatch("clean");
  await assert.rejects(
    async () =>
      createOrAdvanceApproval(
        { subject_type: "export", subject_id: subjectId, action: "approve" },
        "poweruser",
      ),
    /approval_expired/,
  );
});

test("dashboard filters preserve role scope and return replay filter metadata", () => {
  resetScenario();
  const filtered = getDashboard("poweruser", "ONR-Corporate", { q: "hypersonic" }) as ReturnType<
    typeof getDashboard
  > & { replay: boolean };
  assert.equal(filtered.kpis.total_grants, 3);
  assert.equal(filtered.filters_applied?.q, "hypersonic");
  assert.ok(filtered.filter_options?.program_areas.includes("Hypersonics"));
  assert.equal(filtered.replay, true);

  const viewer = getDashboard("viewer", "Code-30", { org_unit: "Code-31" });
  assert.equal(viewer.kpis.total_grants, 0);
});

test("analytics history keeps the batch set captured by each run", () => {
  resetScenario();
  const clean = startScenarioBatch("clean");
  completeScenarioBatch(clean.batch_id);
  const run = runAnalytics();
  const firstCount = getAnalyticsRun(run.run_id, "poweruser", "ONR-Corporate").topics.reduce(
    (total, topic) => total + topic.grant_count,
    0,
  );

  const legacy = startScenarioBatch("legacy");
  completeScenarioBatch(legacy.batch_id);
  const historicalCount = getAnalyticsRun(run.run_id, "poweruser", "ONR-Corporate").topics.reduce(
    (total, topic) => total + topic.grant_count,
    0,
  );
  assert.equal(firstCount, 28 + 48);
  assert.equal(historicalCount, firstCount);
});

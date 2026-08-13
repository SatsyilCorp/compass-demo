import assert from "node:assert/strict";
import test from "node:test";

import { ARCHITECTURE_STATUSES, BRIEFING_VIEWS } from "./briefing-model";

test("briefing exposes the five required one-look views in presenter order", () => {
  assert.deepEqual(
    BRIEFING_VIEWS.map((view) => view.id),
    ["executive", "il45", "lineage", "devsecops", "mlops"],
  );
});

test("every directed edge names a protocol and retained receipt", () => {
  for (const view of BRIEFING_VIEWS) {
    assert.ok(view.truth.length > 30, view.id);
    assert.ok(view.lanes.length > 0, view.id);

    for (const lane of view.lanes) {
      assert.equal(lane.connectors.length, lane.nodes.length - 1, lane.id);
      for (const edge of lane.connectors) {
        assert.ok(edge.protocol.length > 2, `${lane.id}: protocol`);
        assert.ok(edge.receipt.length > 5, `${lane.id}: receipt`);
      }
      for (const item of lane.nodes) assert.ok(ARCHITECTURE_STATUSES.includes(item.status), item.id);
    }
  }
});

test("IL4 and IL5 view keeps the current CloudFront edge outside the protected boundary", () => {
  const view = BRIEFING_VIEWS.find((candidate) => candidate.id === "il45");
  assert.ok(view);

  const cloudfrontLane = view.lanes.find((lane) => lane.nodes.some((item) => item.id === "cloudfront-outside"));
  assert.equal(cloudfrontLane?.outsideProtectedBoundary, true);
  assert.notEqual(cloudfrontLane?.tone, "protected");

  const protectedNodeIds = view.lanes
    .filter((lane) => lane.tone === "protected")
    .flatMap((lane) => lane.nodes.map((item) => item.id));
  assert.equal(protectedNodeIds.includes("cloudfront-outside"), false);
  assert.match(view.truth, /not IL4\/IL5/i);
  assert.match(view.truth, /does not have an ATO/i);
});

test("target boundary names Government dependencies without claiming deployment", () => {
  const view = BRIEFING_VIEWS.find((candidate) => candidate.id === "il45");
  assert.ok(view);

  const nodes = view.lanes.flatMap((lane) => lane.nodes);
  const required = ["dod-icam", "cap-bcap", "vdss", "vdms", "tccm"];
  for (const id of required) {
    const item = nodes.find((candidate) => candidate.id === id);
    assert.equal(item?.status, "External dependency", id);
  }
});

test("public-source quarantine remains distinct from accepted public evidence", () => {
  const executive = BRIEFING_VIEWS.find((candidate) => candidate.id === "executive");
  const lineage = BRIEFING_VIEWS.find((candidate) => candidate.id === "lineage");
  assert.ok(executive);
  assert.ok(lineage);

  const executiveIds = executive.lanes.flatMap((lane) => lane.nodes.map((item) => item.id));
  assert.ok(executiveIds.includes("public-quarantine"));
  assert.ok(executiveIds.includes("public-snapshot"));

  const publicLane = lineage.lanes.find((lane) => lane.id === "lineage-public");
  assert.ok(publicLane);
  assert.equal(publicLane.nodes.some((item) => item.id === "source-quarantine"), true);
  assert.equal(publicLane.nodes.some((item) => item.id === "accepted-source"), true);
});

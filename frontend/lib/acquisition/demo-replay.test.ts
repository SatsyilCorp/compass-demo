import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAcquisitionDemoReplay,
  buildAcquisitionDemoSignals,
  DEMO_FAILURE_SOURCE_ID,
} from "./demo-replay";

test("demo replay is unmistakably synthetic and never names a live transport", () => {
  const replay = buildAcquisitionDemoReplay();
  assert.equal(replay.mode, "replay");
  assert.match(replay.source_transport, /No external API request/i);
  assert.equal(replay.source_health?.length, 4);
  assert.ok(replay.source_health?.every((source) => source.label.startsWith("DEMO REPLAY")));
  assert.ok(replay.acquisitions.every((run) => run.scope_disclosure?.includes("Synthetic")));
});

test("failure rehearsal keeps the prior accepted snapshot and creates a visible alert", () => {
  const replay = buildAcquisitionDemoReplay(DEMO_FAILURE_SOURCE_ID);
  const signals = buildAcquisitionDemoSignals(DEMO_FAILURE_SOURCE_ID);
  const sourceRuns = replay.acquisitions.filter((run) => run.source_id === DEMO_FAILURE_SOURCE_ID);
  assert.equal(replay.source_health?.find((source) => source.source_id === DEMO_FAILURE_SOURCE_ID)?.status, "failed");
  assert.deepEqual(sourceRuns.map((run) => run.status), ["failed", "completed"]);
  assert.equal(signals.signals[0]?.severity, "critical");
  assert.match(signals.signals[0]?.title ?? "", /DEMO FAILURE/);
  assert.equal(signals.signals[0]?.href, "/admin/acquisition/?mode=demo");
});

test("demo replay contains a verified fixture link and a reviewable candidate", () => {
  const replay = buildAcquisitionDemoReplay();
  assert.deepEqual(
    replay.evidence_threads?.map((thread) => thread.match_type),
    ["exact-identity", "explainable-candidate"],
  );
});

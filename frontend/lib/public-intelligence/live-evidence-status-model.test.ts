import assert from "node:assert/strict";
import test from "node:test";

import { liveEvidenceStatusState } from "./live-evidence-status-model";

test("missing acquisition control remains unknown until a receipt arrives", () => {
  assert.equal(liveEvidenceStatusState(null, null), "verifying");
});

test("running and stopped states require an explicit controller receipt", () => {
  assert.equal(liveEvidenceStatusState({ enabled: true }, null), "running");
  assert.equal(liveEvidenceStatusState({ enabled: false }, null), "stopped");
  assert.equal(liveEvidenceStatusState(null, "Service unavailable"), "attention");
});

import assert from "node:assert/strict";
import test from "node:test";

import { deliveryEvidence } from "./evidence-model";

const REVISION = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const RUN_URL = "https://github.com/SatsyilCorp/compass-demo/actions/runs/123";

test("an exact revision and exact successful Actions receipt are verified", () => {
  const evidence = deliveryEvidence({
    sourceRevision: REVISION,
    qualityStatus: "success",
    qualityRunUrl: RUN_URL,
  });

  assert.equal(evidence.revision, REVISION);
  assert.equal(evidence.revisionLabel, REVISION.slice(0, 12));
  assert.equal(evidence.qualityStatus, "success");
  assert.equal(evidence.qualityLabel, "Verified success");
  assert.equal(evidence.qualityRunUrl, RUN_URL);
  assert.equal(evidence.isCommitBoundSuccess, true);
});

test("an unbound local candidate never becomes verified delivery evidence", () => {
  const evidence = deliveryEvidence({
    sourceRevision: "local candidate",
    qualityStatus: "success",
    qualityRunUrl: RUN_URL,
  });

  assert.equal(evidence.revision, null);
  assert.equal(evidence.revisionLabel, "Not recorded");
  assert.equal(evidence.qualityStatus, "unverified");
  assert.equal(evidence.qualityLabel, "Not verified");
  assert.equal(evidence.qualityRunUrl, null);
  assert.equal(evidence.isCommitBoundSuccess, false);
});

test("a failed exact Actions receipt remains visibly failed", () => {
  const evidence = deliveryEvidence({
    sourceRevision: REVISION,
    qualityStatus: "failure",
    qualityRunUrl: RUN_URL,
  });

  assert.equal(evidence.qualityStatus, "failure");
  assert.equal(evidence.qualityLabel, "Failed");
  assert.equal(evidence.isCommitBoundSuccess, false);
});

test("an Actions URL from another repository is rejected", () => {
  const evidence = deliveryEvidence({
    sourceRevision: REVISION,
    qualityStatus: "success",
    qualityRunUrl: "https://github.com/example/other/actions/runs/123",
  });

  assert.equal(evidence.qualityStatus, "unverified");
  assert.equal(evidence.qualityRunUrl, null);
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  PRESENTER_SEQUENCE,
  REQUIREMENTS,
  STATUS_META,
  TRACE_STATUSES,
  countByStatus,
} from "./model";

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

test("all five evidence states are explicit and represented", () => {
  const totals = countByStatus();
  for (const status of TRACE_STATUSES) {
    assert.ok(STATUS_META[status].label.length > 0, status);
    assert.ok(totals[status] > 0, status);
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

test("continuous acquisition and IL4 or IL5 stay conservative without live proof", () => {
  const acquisition = REQUIREMENTS.find((item) => item.id === "continuous-public-acquisition");
  const ilTarget = REQUIREMENTS.find((item) => item.id === "il4-il5-target");

  assert.equal(acquisition?.status, "not-yet-implemented");
  assert.match(acquisition?.caveat ?? "", /live API.*watermark/i);
  assert.equal(ilTarget?.status, "target-architecture");
  assert.match(ilTarget?.caveat ?? "", /not IL4 or IL5 authorized/i);
});

import assert from "node:assert/strict";
import test from "node:test";

import { presenterStepsForMode } from "./presenter-steps";

test("rehearsal presenter steps use rehearsal routes and claims", () => {
  const steps = presenterStepsForMode("rehearsal");
  assert.equal(steps.find((step) => step.element === "3")?.route, "/rehearsal/ingest/");
  assert.equal(steps.find((step) => step.element === "4")?.route, "/rehearsal/catalog/");
  assert.equal(steps.find((step) => step.element === "6")?.route, "/rehearsal/dashboard/");
  assert.equal(steps.find((step) => step.element === "7")?.route, "/rehearsal/export/");
  for (const step of steps) {
    assert.doesNotMatch(`${step.proof} ${step.narration}`, /live public|real public|live source|live record/i, step.title);
  }
});

test("live presenter steps keep primary public routes and claims", () => {
  const steps = presenterStepsForMode("live");
  assert.equal(steps.find((step) => step.element === "3")?.route, "/ingest/");
  assert.match(steps.find((step) => step.element === "3")?.proof ?? "", /public/i);
  const portablePreview = steps.find((step) => step.element === "7");
  assert.match(portablePreview?.title ?? "", /portable preview/i);
  assert.match(portablePreview?.proof ?? "", /no server approval, delivery, audit record, or release receipt/i);
  assert.match(portablePreview?.narration ?? "", /separate protected API workflow/i);
});

import assert from "node:assert/strict";
import test from "node:test";

import { pipelineStepIndex } from "./run-progress";

test("a display clock older than the click timestamp stays on the first step", () => {
  assert.equal(pipelineStepIndex(999, 1_000, 7), 0);
});

test("run progress advances and wraps without leaving the valid step range", () => {
  assert.equal(pipelineStepIndex(1_000, 1_000, 7), 0);
  assert.equal(pipelineStepIndex(2_100, 1_000, 7), 1);
  assert.equal(pipelineStepIndex(8_700, 1_000, 7), 0);
});

test("invalid timing inputs fail safely on the first step", () => {
  assert.equal(pipelineStepIndex(Number.NaN, 1_000, 7), 0);
  assert.equal(pipelineStepIndex(1_000, 1_000, 0), 0);
  assert.equal(pipelineStepIndex(1_000, 1_000, 7, 0), 0);
});

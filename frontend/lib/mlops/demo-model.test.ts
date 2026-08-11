import assert from "node:assert/strict";
import test from "node:test";

import {
  DOCUMENT_CLASSES,
  MODEL_VERSIONS,
  classifyDocument,
  driftDecision,
  modelPromotionDecision,
} from "./demo-model";

test("shared taxonomy has exactly six portable document classes", () => {
  assert.equal(DOCUMENT_CLASSES.length, 6);
  assert.equal(new Set(DOCUMENT_CLASSES.map((item) => item.id)).size, 6);
});

test("classifier produces an operational label and a review decision", () => {
  const result = classifyDocument(
    "Fiscal budget obligation expenditure forecast variance for the portfolio.",
    "financial-execution.csv",
  );
  assert.equal(result.label, "financial_execution");
  assert.equal(result.reviewRequired, false);
  assert.ok(result.confidence >= 0.62);
});

test("weak evidence routes to human review", () => {
  assert.equal(classifyDocument("generic content").reviewRequired, true);
});

test("promotion and drift gates are deterministic", () => {
  assert.equal(modelPromotionDecision(MODEL_VERSIONS[2]), "approve");
  assert.deepEqual(driftDecision(0.31, 0.7), {
    detected: true,
    action: "retrain-and-review",
  });
});

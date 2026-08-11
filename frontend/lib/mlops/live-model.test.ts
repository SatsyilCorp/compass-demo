import assert from "node:assert/strict";
import test from "node:test";

import { projectLiveModel, resolvePromotionVersion } from "./live-model";

test("live model projection carries the backend version and metrics through promotion", () => {
  const model = projectLiveModel({
    model_version: "doc-nb-f828a29acd1e",
    status: "registered",
    labels: ["grant", "technical", "publication", "patent", "investment", "financial"],
    training_digest: "1234567890abcdef",
    created_at: "2026-08-11T20:00:00Z",
    metrics: {
      accuracy: 1,
      macro_f1: 0.98,
      training_document_count: 30,
      evaluation_document_count: 6,
      training_split_seed: 20260811,
    },
  });

  assert.deepEqual(model, {
    version: "doc-nb-f828a29acd1e",
    status: "registered",
    accuracy: 1,
    macroF1: 0.98,
    classCoverage: 6,
    trainingRecords: 36,
    splitSeed: "20260811",
    sourceRevision: "12345678",
    createdAt: "2026-08-11T20:00:00Z",
  });
  assert.equal(resolvePromotionVersion("live", "3", model), "doc-nb-f828a29acd1e");
});

test("replay keeps its source-controlled version and live promotion fails closed without a receipt", () => {
  assert.equal(resolvePromotionVersion("replay", "3", null), "3");
  assert.throws(
    () => resolvePromotionVersion("live", "3", null),
    /Run live training before approving a model/,
  );
});

import assert from "node:assert/strict";
import test from "node:test";

import { parseLiveDriftReceipt } from "./drift-contract";

const MODEL_VERSION = "nb-docs-a1b2c3d4";
const DRIFT_ID = `drift-${"a".repeat(12)}`;

function receipt(): Record<string, unknown> {
  return {
    contract: "compass.model-drift-receipt.v1",
    evidence_class: "public-operational",
    drift_id: DRIFT_ID,
    model_version: MODEL_VERSION,
    documents_observed: 12,
    tokens_observed: 144,
    reference_label_distribution: {
      grant_abstract: 0.166667,
      technical_report: 0.166667,
      publication_summary: 0.166667,
      patent_summary: 0.166667,
      investment_brief: 0.166666,
      financial_execution: 0.166666,
    },
    observed_label_distribution: {
      grant_abstract: 0.25,
      technical_report: 0.25,
      publication_summary: 0.125,
      patent_summary: 0.125,
      investment_brief: 0.125,
      financial_execution: 0.125,
    },
    population_stability_index: 0.17,
    out_of_vocabulary_rate: 0.12,
    drift_score: 0.155,
    threshold: 0.25,
    drift_detected: false,
    recommended_action: "continue-monitoring",
    evaluation_window_sha256: "b".repeat(64),
    baseline_sha256: "c".repeat(64),
    receipt_uri: `document-lake://mlops/drift/${DRIFT_ID}.json`,
    evaluated_by: "poweruser@compass.demo",
    created_at: "2026-08-13T10:00:00+00:00",
    updated_at: "2026-08-13T10:00:00+00:00",
  };
}

test("live drift parser accepts a complete model and source-bound receipt", () => {
  const parsed = parseLiveDriftReceipt(receipt(), {
    modelVersion: MODEL_VERSION,
    documentsObserved: 12,
  });

  assert.ok(parsed);
  assert.equal(parsed.model_version, MODEL_VERSION);
  assert.equal(parsed.recommended_action, "continue-monitoring");
  assert.equal(parsed.evidence_class, "public-operational");
});

test("live drift parser rejects identity, count, metric, decision, hash, URI, and time drift", () => {
  const invalidReceipts = [
    { ...receipt(), contract: "compass.model-drift-receipt.v0" },
    { ...receipt(), evidence_class: "synthetic-rehearsal" },
    { ...receipt(), model_version: "other-model" },
    { ...receipt(), documents_observed: 11 },
    { ...receipt(), population_stability_index: -1 },
    { ...receipt(), out_of_vocabulary_rate: 1.1 },
    { ...receipt(), drift_score: 0.9, drift_detected: false },
    { ...receipt(), drift_detected: true, recommended_action: "continue-monitoring" },
    { ...receipt(), evaluation_window_sha256: "not-a-hash" },
    { ...receipt(), baseline_sha256: "not-a-hash" },
    { ...receipt(), receipt_uri: "https://example.test/drift.json" },
    { ...receipt(), receipt_uri: "document-lake://mlops/drift/other.json" },
    { ...receipt(), updated_at: "yesterday" },
    { ...receipt(), observed_label_distribution: { grant_abstract: 1 } },
  ];

  for (const value of invalidReceipts) {
    assert.equal(
      parseLiveDriftReceipt(value, {
        modelVersion: MODEL_VERSION,
        documentsObserved: 12,
      }),
      null,
    );
  }
});

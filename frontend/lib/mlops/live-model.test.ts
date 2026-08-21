import assert from "node:assert/strict";
import test from "node:test";

import {
  projectLiveModel,
  projectLiveModelEvidence,
  resolvePromotionVersion,
} from "./live-model";

test("live model projection carries the backend version and metrics through promotion", () => {
  const model = projectLiveModel({
    model_version: "doc-nb-f828a29acd1e",
    status: "registered",
    synthetic_only: false,
    labels: ["grant", "technical", "publication", "patent", "investment", "financial"],
    training_digest: "1234567890abcdef",
    training_manifest_uri: "s3://verified-bucket/training/manifest.json",
    training_manifest_sha256: "a".repeat(64),
    artifact_uri: "s3://verified-bucket/models/document-classifier.tar.gz",
    source_revision: "commit-abc123",
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
    sourceRevision: "commit-abc123",
    createdAt: "2026-08-11T20:00:00Z",
    trainingManifestUri: "s3://verified-bucket/training/manifest.json",
    trainingManifestSha256: "a".repeat(64),
    artifactUri: "s3://verified-bucket/models/document-classifier.tar.gz",
  });
  assert.equal(resolvePromotionVersion("live", "3", model), "doc-nb-f828a29acd1e");
});

test("live projection excludes synthetic and manifest-free training receipts", () => {
  const synthetic = projectLiveModelEvidence({
    model_version: "doc-nb-synthetic",
    status: "registered",
    synthetic_only: true,
  });
  assert.equal(synthetic.state, "synthetic-excluded");
  assert.equal(synthetic.model, null);

  const manifestFree = projectLiveModelEvidence({
    model_version: "doc-nb-unverified",
    status: "registered",
    synthetic_only: false,
    metrics: {
      accuracy: 0.95,
      macro_f1: 0.94,
      training_document_count: 100,
      evaluation_document_count: 20,
    },
    labels: ["technical_report"],
    artifact_uri: "s3://models/unverified.tar.gz",
  });
  assert.equal(manifestFree.state, "manifest-required");
  assert.equal(manifestFree.model, null);
  assert.match(manifestFree.detail, /manifest URI and SHA-256 digest/);
});

test("live projection fails closed when returned evaluation evidence is incomplete", () => {
  const evidence = projectLiveModelEvidence({
    model_version: "doc-nb-incomplete",
    status: "registered",
    synthetic_only: false,
    training_manifest_uri: "s3://verified-bucket/training/manifest.json",
    training_manifest_sha256: "b".repeat(64),
    artifact_uri: "s3://verified-bucket/models/document-classifier.tar.gz",
    labels: ["technical_report"],
    metrics: {
      accuracy: 0.95,
      training_document_count: 100,
      evaluation_document_count: 20,
    },
  });
  assert.equal(evidence.state, "incomplete");
  assert.equal(evidence.model, null);
});

test("replay keeps its source-controlled version and live promotion fails closed without a receipt", () => {
  assert.equal(resolvePromotionVersion("replay", "3", null), "3");
  assert.throws(
    () => resolvePromotionVersion("live", "3", null),
    /Verified live model evidence is required before approval/,
  );
});

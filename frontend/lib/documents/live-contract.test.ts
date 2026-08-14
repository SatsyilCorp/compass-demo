import assert from "node:assert/strict";
import test from "node:test";

import {
  parseLiveDocumentRun,
  parseLiveDocumentUploadPlan,
  type LiveDocumentBinding,
} from "./live-contract";

const SOURCE_SHA256 = "a".repeat(64);
const RUN_ID = `doc-${"b".repeat(32)}`;
const DOCUMENT_ID = "b".repeat(32);
const FILENAME = "public-opportunity.json";
const CONTENT_TYPE = "application/json";
const SIZE_BYTES = 1_024;

const binding: LiveDocumentBinding = {
  runId: RUN_ID,
  documentId: DOCUMENT_ID,
  fileName: FILENAME,
  contentType: CONTENT_TYPE,
  sizeBytes: SIZE_BYTES,
  sourceSha256: SOURCE_SHA256,
};

function uploadPlan(): Record<string, unknown> {
  return {
    contract: "compass.document-upload-plan.v1",
    evidence_class: "public-operational",
    run_id: RUN_ID,
    document_id: DOCUMENT_ID,
    status: "awaiting-upload",
    stage: "browser-upload",
    filename: FILENAME,
    content_type: CONTENT_TYPE,
    expected_bytes: SIZE_BYTES,
    source: `document-lake://documents/incoming/${RUN_ID}/${FILENAME}`,
    source_sha256: SOURCE_SHA256,
    synthetic_only: false,
    data_boundary: {
      classification: "public",
      contains_cui: false,
      pii_minimized: true,
    },
    created_at: "2026-08-13T10:00:00+00:00",
    updated_at: "2026-08-13T10:00:00+00:00",
    upload: {
      method: "POST",
      url: "https://upload.example.test/signed",
      fields: {
        key: `documents/incoming/${RUN_ID}/${FILENAME}`,
        "Content-Type": CONTENT_TYPE,
        policy: "signed-policy",
      },
      expires_in_seconds: 900,
      maximum_bytes: 15 * 1_024 * 1_024,
    },
  };
}

test("live upload plan accepts only a hash-bound public upload contract", () => {
  const parsed = parseLiveDocumentUploadPlan(uploadPlan(), {
    fileName: FILENAME,
    contentType: CONTENT_TYPE,
    sizeBytes: SIZE_BYTES,
    sourceSha256: SOURCE_SHA256,
  });

  assert.ok(parsed);
  assert.equal(parsed.run_id, RUN_ID);
  assert.equal(parsed.source_sha256, SOURCE_SHA256);
  assert.equal(parsed.upload.fields["Content-Type"], CONTENT_TYPE);
});

test("live upload plan rejects contract, boundary, binding, transport, and size drift", () => {
  const invalidPlans = [
    { ...uploadPlan(), contract: "compass.document-upload-plan.v0" },
    { ...uploadPlan(), source_sha256: "c".repeat(64) },
    { ...uploadPlan(), synthetic_only: true },
    { ...uploadPlan(), data_boundary: { classification: "synthetic-demo", contains_cui: false, pii_minimized: true } },
    { ...uploadPlan(), data_boundary: { classification: "public", contains_cui: true, pii_minimized: true } },
    { ...uploadPlan(), data_boundary: { classification: "public", contains_cui: false, pii_minimized: false } },
    { ...uploadPlan(), status: "completed" },
    { ...uploadPlan(), upload: { ...(uploadPlan().upload as object), url: "http://upload.example.test/signed" } },
    { ...uploadPlan(), upload: { ...(uploadPlan().upload as object), maximum_bytes: SIZE_BYTES - 1 } },
    { ...uploadPlan(), upload: { ...(uploadPlan().upload as object), fields: { key: "wrong", "Content-Type": "text/plain" } } },
  ];

  for (const value of invalidPlans) {
    assert.equal(
      parseLiveDocumentUploadPlan(value, {
        fileName: FILENAME,
        contentType: CONTENT_TYPE,
        sizeBytes: SIZE_BYTES,
        sourceSha256: SOURCE_SHA256,
      }),
      null,
    );
  }
});

test("live run accepts a safe terminal receipt bound to the upload plan", () => {
  const parsed = parseLiveDocumentRun({
    ...uploadPlan(),
    upload: undefined,
    contract: "compass.document-intake-run.v1",
    status: "completed",
    stage: "gold-published",
    sha256: SOURCE_SHA256,
    document_class: "technical_report",
    confidence: 0.91,
    review_required: false,
    model_version: "nb-docs-a1b2c3d4",
    silver_uri: `document-lake://documents/silver/${RUN_ID}/normalized.json`,
    gold_uri: `document-lake://documents/gold/${RUN_ID}/decision-record.json`,
    lineage: [
      `document-lake://documents/incoming/${RUN_ID}/${FILENAME}`,
      `document-lake://documents/bronze/${RUN_ID}/document.json`,
      `document-lake://documents/quality/${RUN_ID}.json`,
      `document-lake://documents/silver/${RUN_ID}/normalized.json`,
      `document-lake://documents/gold/${RUN_ID}/decision-record.json`,
    ],
    lineage_receipt_sha256: "d".repeat(64),
    completed_at: "2026-08-13T10:01:00+00:00",
    updated_at: "2026-08-13T10:01:00+00:00",
  }, binding);

  assert.ok(parsed);
  assert.equal(parsed.document_class, "technical_report");
  assert.equal(parsed.source_sha256, SOURCE_SHA256);
});

test("live run rejects unsafe states and any loss of run or source identity", () => {
  const base = {
    ...uploadPlan(),
    upload: undefined,
    contract: "compass.document-intake-run.v1",
    status: "running",
    stage: "bronze-inspected",
    sha256: SOURCE_SHA256,
  };
  const invalidRuns = [
    { ...base, run_id: `doc-${"e".repeat(32)}` },
    { ...base, source_sha256: "f".repeat(64) },
    { ...base, sha256: "f".repeat(64) },
    { ...base, synthetic_only: true },
    { ...base, status: "success" },
    { ...base, stage: "gold-published" },
    { ...base, data_boundary: { classification: "public", contains_cui: true, pii_minimized: true } },
  ];

  for (const value of invalidRuns) {
    assert.equal(parseLiveDocumentRun(value, binding), null);
  }
});

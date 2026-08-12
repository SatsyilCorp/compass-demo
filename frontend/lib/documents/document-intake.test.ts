import assert from "node:assert/strict";
import test from "node:test";

import {
  DOCUMENT_MEDIA_TYPES,
  MAX_DOCUMENT_BYTES,
  buildLocalReceipt,
  liveDocumentStageIndex,
  mediaTypeForFile,
  validateDocument,
} from "./document-intake";

test("media type is extension bound", () => {
  assert.equal(mediaTypeForFile("brief.pdf", "application/pdf"), DOCUMENT_MEDIA_TYPES.pdf);
  assert.equal(mediaTypeForFile("brief.exe", "application/pdf"), null);
  assert.equal(mediaTypeForFile("brief.pdf", "text/plain"), null);
  assert.equal(
    mediaTypeForFile(
      "brief.docx",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    DOCUMENT_MEDIA_TYPES.docx,
  );
  assert.equal(mediaTypeForFile("records.jsonl", "application/json"), DOCUMENT_MEDIA_TYPES.jsonl);
  assert.equal(mediaTypeForFile("records.xml", "application/xml"), DOCUMENT_MEDIA_TYPES.xml);
  assert.equal(mediaTypeForFile("records.xml", "text/xml"), DOCUMENT_MEDIA_TYPES.xml);
});

test("browser validation matches the 15 MiB service contract", () => {
  assert.equal(
    validateDocument({ name: "brief.txt", type: "text/plain", size: MAX_DOCUMENT_BYTES }),
    null,
  );
  assert.match(
    validateDocument({ name: "brief.txt", type: "text/plain", size: MAX_DOCUMENT_BYTES + 1 }) ?? "",
    /15 MiB/,
  );
});

test("live receipt stages map from backend state instead of polling time", () => {
  assert.equal(liveDocumentStageIndex("browser-upload", "awaiting-upload"), 1);
  assert.equal(liveDocumentStageIndex("bronze-inspected", "running"), 4);
  assert.equal(liveDocumentStageIndex("quality-gate", "running"), 5);
  assert.equal(liveDocumentStageIndex("gold-published", "completed"), 7);
  assert.equal(liveDocumentStageIndex("quarantine", "quarantined"), 5);
});

test("receipt reconciles a real selected file to all eight stages", () => {
  const receipt = buildLocalReceipt({
    fileName: "financial-execution.csv",
    mediaType: DOCUMENT_MEDIA_TYPES.csv,
    sizeBytes: 512,
    sha256: "a".repeat(64),
    previewText: "fiscal,budget,obligation,forecast,variance",
  });
  assert.equal(receipt.stages.length, 8);
  assert.equal(receipt.classification.label, "financial_execution");
  assert.equal(receipt.runId, "doc-aaaaaaaaaaaaaaaa");
});

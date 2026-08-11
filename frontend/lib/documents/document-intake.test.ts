import assert from "node:assert/strict";
import test from "node:test";

import { DOCUMENT_MEDIA_TYPES, buildLocalReceipt, mediaTypeForFile } from "./document-intake";

test("media type is extension bound", () => {
  assert.equal(mediaTypeForFile("brief.pdf", "application/pdf"), DOCUMENT_MEDIA_TYPES.pdf);
  assert.equal(mediaTypeForFile("brief.exe", "application/pdf"), null);
  assert.equal(mediaTypeForFile("brief.pdf", "text/plain"), null);
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

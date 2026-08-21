import assert from "node:assert/strict";
import test from "node:test";

import { buildBrowserPortablePreview, portablePreviewCsv } from "./live-public-release-model";

test("live public download is explicitly a browser preview without server release claims", () => {
  const rows = [{ source_record_id: "award-1", title: "Public award" }];
  const manifest = buildBrowserPortablePreview(rows, [{
    source_id: "usaspending",
    run_id: "acq-usaspending-1",
    snapshot_sha256: "a".repeat(64),
  }], "2026-08-13T12:00:00.000Z");

  assert.equal(manifest.contract, "compass.browser-portable-preview.v1");
  assert.equal(manifest.creation_environment, "browser");
  assert.equal(manifest.server_release, false);
  assert.equal(manifest.approval_performed, false);
  assert.equal(manifest.destination_delivery, false);
  assert.equal(manifest.audit_receipt, null);
  assert.equal(manifest.record_count, 1);
  assert.deepEqual(manifest.source_run_ids, ["acq-usaspending-1"]);
});

test("portable preview CSV remains open and escapes browser-visible values", () => {
  assert.equal(
    portablePreviewCsv([{ title: 'Alpha "test"', identity_keys: ["award:1", "uei:2"] }]),
    'title,identity_keys\n"Alpha ""test""","award:1|uei:2"',
  );
});

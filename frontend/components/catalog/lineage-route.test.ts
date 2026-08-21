import assert from "node:assert/strict";
import test from "node:test";

import { catalogLineageHref } from "./lineage-route";

test("routes live batch ids through the static lineage page", () => {
  assert.equal(
    catalogLineageHref("drop-compat-2026-08"),
    "/catalog/lineage/?batch=drop-compat-2026-08",
  );
});

test("encodes batch ids instead of treating them as static path segments", () => {
  assert.equal(
    catalogLineageHref("drop/live evidence #1"),
    "/catalog/lineage/?batch=drop%2Flive%20evidence%20%231",
  );
});

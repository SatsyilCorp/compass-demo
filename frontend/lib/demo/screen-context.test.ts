import assert from "node:assert/strict";
import test from "node:test";

import { screenContextForPath } from "./screen-context";

test("every primary demo screen names its evidence source and update behavior", () => {
  const routes = [
    "/admin/demo/",
    "/admin/delivery/",
    "/ingest/",
    "/catalog/",
    "/admin/mlops/",
    "/dashboard/",
    "/export/",
  ];

  for (const route of routes) {
    const context = screenContextForPath(route);
    assert.notEqual(context.route, "/", route);
    assert.ok(context.source.length > 20, route);
    assert.ok(context.updateBehavior.length > 20, route);
  }
});

test("live public operations and synthetic mission workflows remain separate", () => {
  assert.equal(screenContextForPath("/admin/acquisition/").tone, "public");
  assert.equal(screenContextForPath("/intelligence/").tone, "public");
  assert.equal(screenContextForPath("/catalog/").tone, "synthetic");
  assert.equal(screenContextForPath("/dashboard/").tone, "synthetic");
});

test("the specific catalog lineage route wins over the catalog prefix", () => {
  assert.equal(screenContextForPath("/catalog/lineage/?batch=run-1").screen, "Dataset lineage");
});

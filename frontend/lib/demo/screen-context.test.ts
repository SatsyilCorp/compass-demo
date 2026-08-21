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
    const context = screenContextForPath(route, "rehearsal");
    assert.notEqual(context.route, "/", route);
    assert.ok(context.source.length > 20, route);
    assert.ok(context.updateBehavior.length > 20, route);
  }
});

test("live mode is the default and never silently falls back to synthetic", () => {
  assert.equal(screenContextForPath("/admin/acquisition/").tone, "public");
  assert.equal(screenContextForPath("/intelligence/").tone, "public");

  const catalog = screenContextForPath("/catalog/");
  const dashboard = screenContextForPath("/dashboard/");
  assert.equal(catalog.tone, "public");
  assert.equal(dashboard.tone, "public");
  assert.match(catalog.evidenceLabel, /accepted public source/i);
  assert.match(dashboard.updateBehavior, /accepted snapshot/i);
  assert.equal(screenContextForPath("/ingest/").showSyntheticStream, undefined);
});

test("synthetic workflow context appears only after rehearsal is explicit", () => {
  assert.equal(screenContextForPath("/catalog/", "rehearsal").tone, "synthetic");
  assert.equal(screenContextForPath("/dashboard/", "rehearsal").tone, "synthetic");
  assert.equal(screenContextForPath("/ingest/", "rehearsal").showSyntheticStream, true);

  const publicSource = screenContextForPath("/admin/acquisition/", "rehearsal");
  assert.equal(publicSource.tone, "synthetic");
  assert.match(publicSource.evidenceLabel, /explicit synthetic rehearsal/i);
});

test("rehearsal child routes reuse the matching mission context", () => {
  assert.equal(screenContextForPath("/rehearsal/dashboard/", "rehearsal").screen, "Decision workspace");
  assert.equal(screenContextForPath("/rehearsal/export/", "rehearsal").screen, "Governed release rehearsal");
});

test("live export context names the preview and the governed release path", () => {
  const context = screenContextForPath("/export/", "live");
  assert.equal(context.screen, "Portable preview and governed release");
  assert.match(context.evidenceLabel, /browser-generated/i);
  assert.match(context.updateBehavior, /makes? no server claim/i);
  assert.match(context.updateBehavior, /428/);
  assert.match(context.updateBehavior, /fingerprint-bound approval/i);
});

test("the specific catalog lineage route wins over the catalog prefix", () => {
  assert.equal(screenContextForPath("/catalog/lineage/?batch=run-1", "rehearsal").screen, "Dataset lineage");
});

test("rehearsal has a separate landing route", () => {
  const context = screenContextForPath("/rehearsal/");
  assert.equal(context.screen, "Rehearsal landing");
  assert.match(context.source, /user-selected deterministic synthetic/i);
});

import assert from "node:assert/strict";
import test from "node:test";

import { demoOverviewForMode } from "./overview";

test("rehearsal overview uses isolated synthetic sources and actions", () => {
  const overview = demoOverviewForMode("rehearsal");
  assert.match(overview.heroTitle, /rehearsal/i);
  assert.equal(overview.elements[3].href, "/rehearsal/ingest/");
  for (const element of Object.values(overview.elements)) {
    assert.doesNotMatch(`${element.title} ${element.label} ${element.source} ${element.changes} ${element.action}`, /live public|real public|accepted public/i);
  }
});

test("live overview preserves the public evidence story", () => {
  const overview = demoOverviewForMode("live");
  assert.match(overview.heroTitle, /live public/i);
  assert.match(overview.elements[3].source, /public-source registry/i);
  assert.equal(overview.sourceCountValue, "API");
  assert.match(overview.elements[7].label, /governed release/i);
  assert.match(overview.elements[7].action, /428/);
  assert.match(overview.elements[7].action, /fingerprint-bound/i);
  assert.doesNotMatch(overview.elements[7].action, /request a governed/i);
});

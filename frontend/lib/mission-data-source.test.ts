import assert from "node:assert/strict";
import test from "node:test";

import { curatedEvidenceSourceLabel } from "./mission-data-source";

test("curated evidence source label distinguishes fixture and live serving modes", () => {
  assert.equal(curatedEvidenceSourceLabel(true), "Fixture-backed serving projection");
  assert.equal(curatedEvidenceSourceLabel(false), "Aurora serving projection");
});

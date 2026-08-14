import assert from "node:assert/strict";
import test from "node:test";

import { curatedEvidenceSourceLabel } from "./mission-data-source";

test("curated evidence source label distinguishes explicit rehearsal from live serving", () => {
  assert.equal(curatedEvidenceSourceLabel("rehearsal"), "Explicit fixture-backed rehearsal projection");
  assert.equal(curatedEvidenceSourceLabel("live"), "Protected live public serving projection");
});

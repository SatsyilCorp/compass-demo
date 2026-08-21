import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_EVIDENCE_MODE,
  EVIDENCE_MODE_STORAGE_KEY,
  evidenceModeDisclosure,
  evidenceModeForPath,
  evidenceModeHome,
  parseEvidenceMode,
  persistEvidenceMode,
  readEvidenceMode,
  resolveInitialEvidenceMode,
  setRuntimeEvidenceMode,
  usesRehearsalEvidence,
} from "./evidence-mode";

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

test("live public evidence is the fail-closed default", () => {
  assert.equal(DEFAULT_EVIDENCE_MODE, "live");
  assert.equal(parseEvidenceMode(null), "live");
  assert.equal(parseEvidenceMode("true"), "live");
  assert.equal(parseEvidenceMode("replay"), "live");
  assert.equal(parseEvidenceMode("synthetic"), "live");
  assert.match(evidenceModeDisclosure("live"), /never loads a synthetic substitute/i);
});

test("only an exact rehearsal selection enables rehearsal evidence", () => {
  const storage = new MemoryStorage();
  assert.equal(readEvidenceMode(storage), "live");

  persistEvidenceMode("rehearsal", storage);
  assert.equal(storage.getItem(EVIDENCE_MODE_STORAGE_KEY), "rehearsal");
  assert.equal(readEvidenceMode(storage), "rehearsal");

  setRuntimeEvidenceMode("rehearsal");
  assert.equal(usesRehearsalEvidence(), true);
  setRuntimeEvidenceMode("live");
  assert.equal(usesRehearsalEvidence(), false);
});

test("unavailable browser persistence stays live", () => {
  const unavailableStorage = {
    getItem(): string | null {
      throw new Error("storage unavailable");
    },
  };
  assert.equal(readEvidenceMode(unavailableStorage), "live");
});

test("each evidence mode has a distinct landing destination", () => {
  assert.equal(evidenceModeHome("live"), "/admin/acquisition/");
  assert.equal(evidenceModeHome("rehearsal"), "/rehearsal/");
});

test("the rehearsal namespace activates rehearsal before mission screens mount", () => {
  assert.equal(evidenceModeForPath("/rehearsal/"), "rehearsal");
  assert.equal(evidenceModeForPath("/rehearsal/dashboard/?presenter=1"), "rehearsal");
  assert.equal(evidenceModeForPath("/rehearsal-not-a-route/"), null);
  assert.equal(resolveInitialEvidenceMode("/rehearsal/catalog/", "live"), "rehearsal");
});

test("leaving rehearsal does not force live routes back into rehearsal", () => {
  assert.equal(evidenceModeForPath("/admin/acquisition/"), null);
  assert.equal(resolveInitialEvidenceMode("/admin/acquisition/", "live"), "live");
});

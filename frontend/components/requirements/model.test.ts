import assert from "node:assert/strict";
import test from "node:test";

import { REQUIREMENTS, REQUIREMENT_SECTIONS, countByStatus } from "./model";

test("requirements trace has unique, complete, presenter-ready entries", () => {
  assert.equal(new Set(REQUIREMENTS.map((item) => item.id)).size, REQUIREMENTS.length);
  assert.ok(REQUIREMENTS.length >= 20);

  for (const item of REQUIREMENTS) {
    assert.ok(item.title.length > 3, item.id);
    assert.ok(item.requirement.length > 20, item.id);
    assert.ok(item.capability.length > 20, item.id);
    assert.match(item.demoPath, /^\/.+\/$/, item.id);
    assert.ok(item.workflow.length >= 2, item.id);
    assert.ok(item.proof.length >= 2, item.id);
    assert.ok(item.evidence.length >= 1, item.id);
    assert.ok(item.gap.length > 20, item.id);
  }
});

test("requirements trace covers every selected PWS section and delivery state", () => {
  const sections = new Set(REQUIREMENTS.map((item) => item.section));
  for (const section of REQUIREMENT_SECTIONS) assert.ok(sections.has(section), section);

  const counts = countByStatus();
  assert.ok(counts.demonstrated > 0);
  assert.ok(counts.partial > 0);
  assert.ok(counts.roadmap > 0);
  assert.equal(counts.demonstrated + counts.partial + counts.roadmap, REQUIREMENTS.length);
});

test("production authorization remains roadmap while MLOps evidence stays partial", () => {
  const accreditation = REQUIREMENTS.find((item) => item.id === "fedramp-il5-ato");
  const mlops = REQUIREMENTS.find((item) => item.id === "mlops");
  const compliance = REQUIREMENTS.find((item) => item.id === "compliance-stig-vulnerability");

  assert.equal(accreditation?.status, "roadmap");
  assert.equal(mlops?.status, "partial");
  assert.equal(compliance?.status, "roadmap");
  assert.match(accreditation?.gap ?? "", /not FedRAMP High authorized/i);
  assert.match(mlops?.gap ?? "", /not demonstrated/i);
});

test("source acquisition requirement maps to the explicit evidence boundary", () => {
  const acquisition = REQUIREMENTS.find((item) => item.id === "diverse-st-sources");

  assert.equal(acquisition?.demoPath, "/intelligence/");
  assert.equal(acquisition?.demoLabel, "Source ledger");
  assert.match(acquisition?.capability ?? "", /177,503.*12 public source families/i);
  assert.match(acquisition?.gap ?? "", /Advana, Pulse.*protected opportunity documents/i);
});

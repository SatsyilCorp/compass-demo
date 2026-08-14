import assert from "node:assert/strict";
import test from "node:test";

import { DEMO_ELEMENTS, DEMO_LOGISTICS, STRATEGIC_PROMPTS, totalScenarioMinutes } from "./trace";

test("technical demonstration contains the seven required elements in order", () => {
  assert.deepEqual(DEMO_ELEMENTS.map((element) => element.number), [1, 2, 3, 4, 5, 6, 7]);
  assert.equal(new Set(DEMO_ELEMENTS.map((element) => element.title)).size, 7);
  assert.ok(DEMO_ELEMENTS.every((element) => element.action && element.focus && element.href));
});

test("five mandatory strategic prompts are covered during the sequence", () => {
  assert.equal(STRATEGIC_PROMPTS.length, 5);
  assert.equal(new Set(STRATEGIC_PROMPTS.map((prompt) => prompt.id)).size, 5);
  assert.ok(STRATEGIC_PROMPTS.every((prompt) => prompt.addressDuring.length > 0));
  assert.ok(STRATEGIC_PROMPTS.every((prompt) => prompt.response.length >= 3));
});

test("run of show remains within the fifty minute limit", () => {
  assert.equal(totalScenarioMinutes(), DEMO_LOGISTICS.scenarioMinutes);
  assert.ok(DEMO_LOGISTICS.scenarioMinutes + DEMO_LOGISTICS.promptMinutes + DEMO_LOGISTICS.closeMinutes <= DEMO_LOGISTICS.maximumMinutes);
});

test("live portability element does not overclaim protected release execution", () => {
  const portability = DEMO_ELEMENTS.find((element) => element.number === 7);
  assert.equal(portability?.screen, "Portable browser preview");
  assert.match(portability?.boundary ?? "", /does not call POST \/export/i);
  assert.match(portability?.proof.join(" ") ?? "", /no-server-receipt/i);
});

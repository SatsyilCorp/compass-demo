import assert from "node:assert/strict";
import test from "node:test";

import { COMPONENTS } from "./model";
import {
  GATEWAY_ENDPOINT_COMPONENT_IDS,
  OVERALL_ARCHITECTURE_GROUPS,
  OVERALL_FLOW_STEPS,
  REGIONAL_LAMBDA_COMPONENT_IDS,
  VPC_LAMBDA_COMPONENT_IDS,
  allOverallComponentIds,
  overallGroup,
} from "./overall-model";

test("overall map presents the complete mission flow in order", () => {
  assert.deepEqual(
    OVERALL_FLOW_STEPS.map((step) => step.number),
    [1, 2, 3, 4, 5, 6, 7, 8],
  );
});

test("every overall map tile resolves to one architecture component", () => {
  const componentIds = new Set(COMPONENTS.map((component) => component.id));
  const overallIds = allOverallComponentIds();

  assert.equal(new Set(overallIds).size, overallIds.length, "overall groups must not duplicate components");
  for (const id of overallIds) assert.ok(componentIds.has(id), id);
});

test("all twenty-one Lambda adapters are split by actual VPC attachment", () => {
  const expectedVpc = [
    "intake",
    "quality",
    "catalog",
    "analytics",
    "dashboard",
    "summarize",
    "rag",
    "approvals",
    "license",
    "export",
    "evidence",
    "rmf",
    "migrator",
  ];
  const expectedRegional = [
    "authorizer",
    "document-ml",
    "public-acquisition",
    "operations-api",
    "public-intelligence",
    "scale-control",
    "scale-worker",
    "scale-export",
  ];

  assert.deepEqual([...VPC_LAMBDA_COMPONENT_IDS], expectedVpc);
  assert.deepEqual([...REGIONAL_LAMBDA_COMPONENT_IDS], expectedRegional);
  assert.deepEqual(overallGroup("application").componentIds, expectedVpc);
  assert.deepEqual(overallGroup("regional-compute").componentIds, expectedRegional);

  const modeledLambdaIds = COMPONENTS
    .filter((component) => component.service.includes("Lambda"))
    .map((component) => component.id);
  assert.equal(modeledLambdaIds.length, 21);
  assert.deepEqual(
    new Set(modeledLambdaIds),
    new Set([...expectedVpc, ...expectedRegional]),
  );
});

test("S3 and DynamoDB gateway endpoints are route-table controls, not subnet workloads", () => {
  assert.deepEqual(overallGroup("endpoints").componentIds, GATEWAY_ENDPOINT_COMPONENT_IDS);
  assert.match(overallGroup("endpoints").boundary, /private route table/i);

  for (const id of GATEWAY_ENDPOINT_COMPONENT_IDS) {
    const component = COMPONENTS.find((candidate) => candidate.id === id);
    assert.ok(component, id);
    assert.match(component.service, /gateway endpoint/i);
    assert.match(component.processing, /without creating subnet network interfaces/i);
    assert.equal(overallGroup("application").componentIds.includes(id), false);
  }
});

test("overall groups use distinct stable identifiers", () => {
  const ids = OVERALL_ARCHITECTURE_GROUPS.map((group) => group.id);
  assert.equal(new Set(ids).size, ids.length);
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveRoleFromGroups,
  normalizeCognitoGroups,
  ORG_UNIT_FOR_ROLE,
} from "./identity-contract";

test("maps exact deployed Cognito group claims to application scope", () => {
  assert.equal(deriveRoleFromGroups(["compass-poweruser"]), "poweruser");
  assert.equal(deriveRoleFromGroups(["compass-viewer"]), "viewer");
  assert.equal(ORG_UNIT_FOR_ROLE.poweruser, "ONR-Corporate");
  assert.equal(ORG_UNIT_FOR_ROLE.viewer, "Code-30");
});

test("preserves poweruser precedence for a multi-group token", () => {
  assert.equal(
    deriveRoleFromGroups(["compass-viewer", "compass-poweruser"]),
    "poweruser",
  );
});

test("normalizes Cognito array and serialized claim forms", () => {
  assert.deepEqual(normalizeCognitoGroups(["compass-viewer"]), ["compass-viewer"]);
  assert.deepEqual(normalizeCognitoGroups('["compass-poweruser"]'), [
    "compass-poweruser",
  ]);
  assert.deepEqual(normalizeCognitoGroups("[compass-viewer compass-poweruser]"), [
    "compass-viewer",
    "compass-poweruser",
  ]);
});

test("fails closed for aliases and unknown groups", () => {
  assert.equal(deriveRoleFromGroups(["poweruser"]), null);
  assert.equal(deriveRoleFromGroups(["viewer"]), null);
  assert.equal(deriveRoleFromGroups(["administrators"]), null);
});

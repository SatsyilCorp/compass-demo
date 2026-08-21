import assert from "node:assert/strict";
import test from "node:test";

import {
  PUBLIC_OPERATIONS_AUTH_ERROR,
  publicOperationsAuthState,
} from "./public-operations-auth";

test("public operations waits only while authentication is hydrating", () => {
  assert.equal(publicOperationsAuthState({ isLoading: true, idToken: null }), "waiting");
  assert.equal(publicOperationsAuthState({ isLoading: true, idToken: "token" }), "ready");
});

test("public operations settles unavailable when hydration ends without a token", () => {
  assert.equal(publicOperationsAuthState({ isLoading: false, idToken: null }), "unavailable");
  assert.match(PUBLIC_OPERATIONS_AUTH_ERROR, /authentication/i);
});

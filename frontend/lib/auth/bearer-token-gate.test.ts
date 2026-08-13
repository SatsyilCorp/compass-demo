import assert from "node:assert/strict";
import test from "node:test";

import { BearerTokenGate } from "./bearer-token-gate";

test("returns an already published bearer token immediately", async () => {
  const gate = new BearerTokenGate();
  gate.publish("token-ready");

  assert.equal(await gate.wait(25), "token-ready");
});

test("waits for token publication during the first authenticated render", async () => {
  const gate = new BearerTokenGate();
  const waiting = gate.wait(100);

  queueMicrotask(() => gate.publish("token-after-auth-hydration"));

  assert.equal(await waiting, "token-after-auth-hydration");
});

test("does not reuse a token after the auth context is cleared", async () => {
  const gate = new BearerTokenGate();
  gate.publish("old-token");
  gate.publish(null);

  assert.equal(await gate.wait(5), null);
});

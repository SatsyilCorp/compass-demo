import assert from "node:assert/strict";
import test from "node:test";

import type {
  OperationsSignal,
  OperationsSignalAcknowledgeResponse,
  OperationsSignalsResponse,
} from "../../lib/types";
import { applySignalAcknowledgement, unreadSignalCount } from "./model";

function signal(eventId: string, status: OperationsSignal["status"]): OperationsSignal {
  return {
    event_id: eventId,
    signal_type: "test",
    severity: "info",
    title: "Test signal",
    message: "Test message",
    status,
    occurred_at: "2026-08-12T21:00:00.000Z",
    updated_at: "2026-08-12T21:00:00.000Z",
    run_id: null,
    run_kind: null,
    href: null,
    source: "test",
    deliveries: [],
    acknowledged_at: null,
    acknowledged_by: null,
  };
}

function response(): OperationsSignalsResponse {
  return {
    contract: "compass.operations.signals.v1",
    mode: "replay",
    generated_at: "2026-08-12T21:00:00.000Z",
    unread_count: 2,
    signals: [signal("one", "open"), signal("two", "open"), signal("three", "resolved")],
    disclosure: "Replay fixture.",
  };
}

test("unread badge is derived from retained open signals", () => {
  assert.equal(unreadSignalCount(response()), 2);
});

test("acknowledgement updates only the matching signal and recalculates unread count", () => {
  const receipt: OperationsSignalAcknowledgeResponse = {
    contract: "compass.operations.signal-acknowledgement.v1",
    mode: "replay",
    event_id: "one",
    status: "acknowledged",
    acknowledged_at: "2026-08-12T21:01:00.000Z",
    acknowledged_by: "reviewer@compass.demo",
  };
  const next = applySignalAcknowledgement(response(), receipt);
  assert.equal(next.unread_count, 1);
  assert.equal(next.signals[0].status, "acknowledged");
  assert.equal(next.signals[0].acknowledged_by, "reviewer@compass.demo");
  assert.equal(next.signals[1].status, "open");
});

import assert from "node:assert/strict";
import test from "node:test";

import type {
  OperationsSignal,
  OperationsSignalAcknowledgeResponse,
  OperationsSignalsResponse,
} from "../../lib/types";
import {
  applySignalAcknowledgement,
  buildSignalInbox,
  signalGuidance,
  unreadSignalCount,
} from "./model";

function signal(
  eventId: string,
  status: OperationsSignal["status"],
  overrides: Partial<OperationsSignal> = {},
): OperationsSignal {
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
    ...overrides,
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

test("unread badge counts only open signals that need operator attention", () => {
  const value = response();
  value.signals = [
    signal("routine", "open"),
    signal("warning", "open", { severity: "warning" }),
    signal("delivery", "open", {
      deliveries: [{
        channel: "sns",
        state: "failed",
        attempted_at: "2026-08-12T21:00:00.000Z",
        delivered_at: null,
        detail: "Publish failed.",
      }],
    }),
    signal("resolved", "resolved", { severity: "critical" }),
  ];
  assert.equal(unreadSignalCount(value), 2);
});

test("routine activity is grouped without hiding its latest evidence", () => {
  const value = response();
  value.signals = [
    signal("routine-new", "open", {
      signal_type: "public_acquisition",
      title: "USAspending acquisition completed",
      message: "Accepted 100 bounded public records with 0 added and 0 changed records.",
      occurred_at: "2026-08-12T21:05:00.000Z",
      href: "/admin/lineage/?run=new",
    }),
    signal("routine-old", "open", {
      signal_type: "public_acquisition",
      title: "USAspending acquisition completed",
      message: "Accepted 100 bounded public records with 0 added and 0 changed records.",
      occurred_at: "2026-08-12T21:00:00.000Z",
      href: "/admin/lineage/?run=old",
    }),
    signal("drift", "open", {
      signal_type: "model_drift",
      severity: "warning",
      title: "Model drift threshold crossed",
      occurred_at: "2026-08-12T21:03:00.000Z",
    }),
  ];

  const inbox = buildSignalInbox(value);
  assert.equal(inbox.actionableUnread, 1);
  assert.deepEqual(inbox.attention.map((item) => item.event_id), ["drift"]);
  assert.equal(inbox.activity.length, 1);
  assert.equal(inbox.activity[0].occurrenceCount, 2);
  assert.equal(inbox.activity[0].signal.event_id, "routine-new");
  assert.equal(inbox.activity[0].signal.href, "/admin/lineage/?run=new");
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
  assert.equal(next.unread_count, 0);
  assert.equal(next.signals[0].status, "acknowledged");
  assert.equal(next.signals[0].acknowledged_by, "reviewer@compass.demo");
  assert.equal(next.signals[1].status, "open");
});

test("model drift alert explains impact and next action in plain language", () => {
  const guidance = signalGuidance(signal("drift", "open", {
    signal_type: "model_drift",
    severity: "critical",
    title: "Document classifier drift requires review",
  }));
  assert.match(guidance.whyItMatters, /less reliable/i);
  assert.match(guidance.recommendedAction, /review/i);
});

test("quarantine alert explains that unsafe data did not reach decisions", () => {
  const guidance = signalGuidance(signal("quality", "open", {
    signal_type: "structured-quality",
    severity: "warning",
    title: "Structured intake quarantined",
  }));
  assert.match(guidance.whyItMatters, /did not reach/i);
  assert.match(guidance.recommendedAction, /correct/i);
});

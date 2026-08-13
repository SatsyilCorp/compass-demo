import assert from "node:assert/strict";
import test from "node:test";

import type { LiveDemoStreamResponse } from "../../lib/types";
import { liveDemoStreamProgress, liveDemoStreamReceiptKey } from "./live-demo-stream-model";

function response(emitted: number, total: number | null = 15): LiveDemoStreamResponse {
  return {
    contract: "compass.demo-stream.v1",
    mode: "live",
    generated_at: "2026-08-13T12:00:00.000Z",
    session: {
      session_id: "demo-123",
      status: total !== null && emitted >= total ? "completed" : "running",
      stream_mode: total === null ? "continuous" : "bounded",
      cadence_seconds: 2,
      total_events: total,
      emitted_events: emitted,
      started_at: "2026-08-13T12:00:00.000Z",
      updated_at: "2026-08-13T12:00:02.000Z",
      completed_at: null,
      execution_chunk_number: 1,
    },
    latest_event: emitted > 0 ? {
      sequence: emitted,
      run_id: `run-${emitted}`,
      event_id: `event-${emitted}`,
      occurred_at: "2026-08-13T12:00:02.000Z",
      message: "Synthetic event accepted.",
    } : null,
    disclosure: "Synthetic demo stream.",
  };
}

test("receipt key advances once per persisted synthetic event", () => {
  assert.equal(liveDemoStreamReceiptKey(response(0)), null);
  assert.equal(liveDemoStreamReceiptKey(response(1)), "demo-123:1");
  assert.equal(liveDemoStreamReceiptKey(response(15)), "demo-123:15");
});

test("progress is bounded for empty and completed sessions", () => {
  assert.equal(liveDemoStreamProgress(response(0, 0)), 0);
  assert.equal(liveDemoStreamProgress(response(3, 15)), 20);
  assert.equal(liveDemoStreamProgress(response(15, 15)), 100);
  assert.equal(liveDemoStreamProgress(response(500, null)), null);
});

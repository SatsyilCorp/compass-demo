import type { LiveDemoStreamResponse } from "@/lib/types";

export function liveDemoStreamReceiptKey(
  response: LiveDemoStreamResponse,
): string | null {
  const event = response.latest_event;
  const sessionId = response.session.session_id;
  if (!event || !sessionId || event.sequence < 1) return null;
  return `${sessionId}:${event.sequence}`;
}

export function liveDemoStreamProgress(response: LiveDemoStreamResponse): number | null {
  const { emitted_events: emitted, total_events: total } = response.session;
  if (total === null) return null;
  if (total < 1) return 0;
  return Math.max(0, Math.min(100, Math.round((emitted / total) * 100)));
}

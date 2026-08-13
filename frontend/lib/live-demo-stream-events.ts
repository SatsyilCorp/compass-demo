export const LIVE_DEMO_STREAM_TICK_EVENT = "compass:live-demo-stream-tick";

export type LiveDemoStreamTick = {
  sessionId: string;
  sequence: number;
  runId: string | null;
  occurredAt: string;
};

export function publishLiveDemoStreamTick(detail: LiveDemoStreamTick): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<LiveDemoStreamTick>(LIVE_DEMO_STREAM_TICK_EVENT, { detail }),
  );
}

export function subscribeLiveDemoStreamTick(
  listener: (tick: LiveDemoStreamTick) => void,
): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handle = (event: Event) => {
    listener((event as CustomEvent<LiveDemoStreamTick>).detail);
  };
  window.addEventListener(LIVE_DEMO_STREAM_TICK_EVENT, handle);
  return () => window.removeEventListener(LIVE_DEMO_STREAM_TICK_EVENT, handle);
}

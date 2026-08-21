export function pipelineStepIndex(
  displayTimeMs: number,
  startedAtMs: number,
  stepCount: number,
  stepDurationMs = 1_100,
): number {
  if (!Number.isFinite(displayTimeMs) || !Number.isFinite(startedAtMs)) return 0;
  if (!Number.isInteger(stepCount) || stepCount <= 0) return 0;
  if (!Number.isFinite(stepDurationMs) || stepDurationMs <= 0) return 0;

  const elapsedMs = Math.max(0, displayTimeMs - startedAtMs);
  return Math.floor(elapsedMs / stepDurationMs) % stepCount;
}

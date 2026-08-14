import { usesRehearsalEvidence } from "@/lib/evidence-mode";
import { liveScaleAdapter } from "./live-adapter";
import { replayScaleAdapter } from "./replay-adapter";

export { ScaleAdapterError, scaleErrorMessage } from "./errors";
export { SCALE_PROFILES, buildScalePlan, profileById } from "./profiles";
export { formatBytes, formatCount, formatCurrency, formatDuration, formatPercent } from "./format";
export { isTerminalScaleStatus } from "./types";
export type * from "./types";

export function getScaleAdapter() {
  return usesRehearsalEvidence() ? replayScaleAdapter : liveScaleAdapter;
}

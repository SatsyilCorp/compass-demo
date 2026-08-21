/**
 * Barrel export for deterministic rehearsal fixture modules. API adapters
 * import these only after the user explicitly activates rehearsal evidence.
 */
export { getMe } from "./me";
export { getCatalog } from "./catalog";
export { getLineage } from "./lineage";
export {
  advanceSimulatedIngest,
  getIngestStatus,
  resetIngestReplay,
  simulateIngest,
  subscribeIngestReplay,
} from "./ingest";
export type { ScenarioProfile } from "./ingest";
export { getStreamRecent } from "./stream";
export { runAnalytics, getAnalyticsRun } from "./analytics";
export { getDashboard } from "./dashboard";
export { answerChat } from "./chat";
export { getAnomalies } from "./anomalies";
export { createOrAdvanceApproval, listPendingApprovals } from "./approvals";
export { REPLAY_ACTORS, replayActor } from "./actors";
export { getLicenses } from "./licenses";
export { runExport, ExportApprovalRequiredError, MOCK_EXPORT_MAX_ROWS } from "./export";
export { ALL_GRANTS, ORG_UNITS, ORG_UNIT_LABELS, PROGRAM_AREAS, visibleGrants, maskAmount } from "./grants";
export {
  getScenarioState,
  resetScenario,
  scenarioInvariantErrors,
  scenarioMetadata,
  subscribeScenario,
} from "./scenario-store";
export { replayScaleAdapter, resetScaleReplay } from "../scale/replay-adapter";

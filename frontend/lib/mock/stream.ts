/**
 * Deterministic activity stream from the replay event ledger. Events are
 * linked to scenario actions and retain their original logical timestamps.
 */
import type { Role, StreamRecentResponse } from "@/lib/types";
import { getScenarioState, scenarioMetadata } from "./scenario-store";

export function getStreamRecent(role: Role | null, orgUnit: string | null): StreamRecentResponse {
  const canSeeAll = role === "poweruser" || orgUnit === "ONR-Corporate";
  const records = getScenarioState()
    .events.filter((record) => canSeeAll || !record.org_unit || record.org_unit === orgUnit)
    .slice()
    .sort((a, b) => b.at.localeCompare(a.at))
    .slice(0, 18);
  const response = { records, replay: scenarioMetadata() };
  return response;
}

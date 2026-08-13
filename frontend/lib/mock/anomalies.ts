/**
 * Anomaly projection. A defective replay batch creates a visible quarantine
 * finding, while baseline grant findings retain deterministic timestamps.
 */
import type { Anomaly, AnomaliesResponse, Role } from "@/lib/types";
import { visibleGrants } from "./grants";
import { getScenarioState, visibleScenarioBatches } from "./scenario-store";

const TEMPLATES: { kind: string; severity: Anomaly["severity"]; reason: (grantNo: string) => string }[] = [
  {
    kind: "amount_outlier",
    severity: "high",
    reason: (grantNo) => `Award amount on ${grantNo} is 3.2x the program area median for its fiscal year.`,
  },
  {
    kind: "duplicate_grant_no",
    severity: "critical",
    reason: (grantNo) => `${grantNo} shares a normalized title with another grant number in the same batch.`,
  },
  {
    kind: "missing_abstract",
    severity: "low",
    reason: (grantNo) => `${grantNo} was curated with an empty or truncated abstract.`,
  },
  {
    kind: "org_unit_mismatch",
    severity: "medium",
    reason: (grantNo) => `${grantNo} has an org unit that does not match its submitting office.`,
  },
  {
    kind: "fiscal_year_drift",
    severity: "medium",
    reason: (grantNo) => `${grantNo} has a fiscal year outside the declared appropriation year.`,
  },
];

export function getAnomalies(role: Role | null, orgUnit: string | null): AnomaliesResponse {
  const failedBatches = visibleScenarioBatches(role, orgUnit).filter(
    (batch) => !batch.baseline && batch.status === "failed",
  );
  const replayFindings: Anomaly[] = failedBatches.map((batch, index) => ({
    id: 9000 + index,
    grant_id: null,
    kind: "quality_gate_quarantine",
    severity: "critical",
    reason: `${batch.batch_id} failed the replay quality threshold at ${batch.overall_score.toFixed(1)} and curated zero rows.`,
    status: "open",
    created_at: batch.ingested_at,
  }));

  const visible = visibleGrants(role, orgUnit);
  const count = Math.min(Math.max(0, 9 - replayFindings.length), visible.length);
  const anchor = new Date(getScenarioState().logical_now).getTime();
  const baseline: Anomaly[] = Array.from({ length: count }, (_, index) => {
    const grant = visible[(index * 3) % visible.length]!;
    const template = TEMPLATES[index % TEMPLATES.length]!;
    return {
      id: index + 1,
      grant_id: grant.id,
      grant_no: grant.grant_no,
      title: grant.title,
      program_area: grant.program_area,
      org_unit: grant.org_unit,
      kind: template.kind,
      severity: template.severity,
      reason: template.reason(grant.grant_no),
      status: index % 4 === 0 ? "resolved" : index % 3 === 0 ? "acknowledged" : "open",
      created_at: new Date(anchor - (index + 1) * 86_400_000).toISOString(),
    };
  });

  return { anomalies: [...replayFindings, ...baseline] };
}

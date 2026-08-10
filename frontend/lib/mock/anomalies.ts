/**
 * GET /anomalies — fixture. Element 6. Mirrors `anomalies` in
 * db/migrations/001_schema.sql.
 */
import type { Anomaly, AnomaliesResponse, Role } from "@/lib/types";
import { visibleGrants } from "./grants";

const TEMPLATES: { kind: string; severity: Anomaly["severity"]; reason: (n: string) => string }[] = [
  { kind: "amount_outlier", severity: "high", reason: (n) => `Award amount on ${n} is 3.2x the program-area median for its fiscal year.` },
  { kind: "duplicate_grant_no", severity: "critical", reason: (n) => `${n} shares a normalized title with another grant_no in the same batch.` },
  { kind: "missing_abstract", severity: "low", reason: (n) => `${n} was curated with an empty or truncated abstract.` },
  { kind: "org_unit_mismatch", severity: "medium", reason: (n) => `${n}'s org_unit does not match the submitting program office on the source file.` },
  { kind: "fiscal_year_drift", severity: "medium", reason: (n) => `${n}'s fiscal_year is outside the batch's declared appropriation year.` },
];

export function getAnomalies(role: Role | null, orgUnit: string | null): AnomaliesResponse {
  const visible = visibleGrants(role, orgUnit);
  const n = Math.min(9, visible.length);
  const anomalies: Anomaly[] = Array.from({ length: n }, (_, i) => {
    const g = visible[(i * 3) % visible.length]!;
    const t = TEMPLATES[i % TEMPLATES.length]!;
    return {
      id: i + 1,
      grant_id: g.id,
      grant_no: g.grant_no,
      kind: t.kind,
      severity: t.severity,
      reason: t.reason(g.grant_no),
      status: i % 4 === 0 ? "resolved" : i % 3 === 0 ? "acknowledged" : "open",
      created_at: new Date(Date.now() - i * 86_400_000).toISOString(),
    };
  });
  return { anomalies };
}

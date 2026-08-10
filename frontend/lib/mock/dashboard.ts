/**
 * GET /dashboard — fixture. Element 6. One round-trip: KPIs + every chart
 * series the executive dashboard needs, derived from the same
 * `visibleGrants()` used by lib/mock/catalog.ts so the numbers agree across
 * pages.
 */
import type { DashboardResponse, Role } from "@/lib/types";
import { ALL_GRANTS, PROGRAM_AREAS, maskAmount, sum, visibleGrants } from "./grants";
import { getAnomalies } from "./anomalies";
import { getAnalyticsRun } from "./analytics";

export function getDashboard(role: Role | null, orgUnit: string | null): DashboardResponse {
  const visible = visibleGrants(role, orgUnit);

  const funding_by_program_area = PROGRAM_AREAS.map((program_area) => {
    const rows = visible.filter((g) => g.program_area === program_area);
    return {
      program_area,
      amount_usd: sum(rows.map((g) => maskAmount(role, g.amount_usd))),
      grant_count: rows.length,
    };
  }).filter((r) => r.grant_count > 0);

  const fiscalYears = Array.from(new Set(visible.map((g) => g.fiscal_year))).sort();
  const funding_by_fiscal_year = fiscalYears.map((fiscal_year) => {
    const rows = visible.filter((g) => g.fiscal_year === fiscal_year);
    return { fiscal_year, amount_usd: sum(rows.map((g) => maskAmount(role, g.amount_usd))) };
  });

  const batchIds = Array.from(new Set(visible.map((g) => g.batch_id))).sort();
  const quality_trend = batchIds.map((batch_id, i) => {
    const rows = ALL_GRANTS.filter((g) => g.batch_id === batch_id);
    return {
      run_id: `run-${batch_id}`,
      date: rows[0]?.created_at ?? new Date().toISOString(),
      // Deterministic, gently improving trend line for the demo narrative.
      score: Math.min(99.5, 88 + i * 1.7),
    };
  });

  const { topics } = getAnalyticsRun(`analytics-dashboard`, role, orgUnit);
  const totalTopicGrants = topics.reduce((a, t) => a + t.grant_count, 0) || 1;
  const top_topics = topics
    .slice()
    .sort((a, b) => b.grant_count - a.grant_count)
    .slice(0, 5)
    .map((t) => ({ topic_id: t.topic_id, label: t.label, weight: Math.round((t.grant_count / totalTopicGrants) * 1000) / 1000 }));

  const orgUnits = Array.from(new Set(visible.map((g) => g.org_unit))).sort();
  const org_unit_breakdown = orgUnits.map((unit) => {
    const rows = visible.filter((g) => g.org_unit === unit);
    return {
      org_unit: unit,
      grant_count: rows.length,
      amount_usd: sum(rows.map((g) => maskAmount(role, g.amount_usd))),
    };
  });

  const { anomalies } = getAnomalies(role, orgUnit);

  return {
    kpis: {
      total_grants: visible.length,
      total_funding_usd: sum(visible.map((g) => maskAmount(role, g.amount_usd))),
      active_program_areas: funding_by_program_area.length,
      avg_quality_score:
        quality_trend.length > 0
          ? Math.round((quality_trend.reduce((a, q) => a + q.score, 0) / quality_trend.length) * 10) / 10
          : 100,
      open_anomalies: anomalies.filter((a) => a.status === "open").length,
      pending_approvals: 2,
    },
    funding_by_program_area,
    funding_by_fiscal_year,
    quality_trend,
    top_topics,
    org_unit_breakdown,
  };
}

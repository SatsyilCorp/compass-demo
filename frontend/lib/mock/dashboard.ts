/**
 * Executive dashboard projection over the static synthetic grants plus every
 * successfully curated replay batch. Quality, anomaly, and approval counts
 * come from the same persistent scenario state used by their detail pages.
 */
import type { DashboardFilters, DashboardResponse, Role } from "@/lib/types";
import { ALL_GRANTS, PROGRAM_AREAS, maskAmount, visibleGrants } from "./grants";
import { getAnomalies } from "./anomalies";
import {
  dynamicPortfolioAggregates,
  pendingApprovalCount,
  visibleScenarioBatches,
} from "./scenario-store";

type AggregateRow = {
  batch_id: string;
  program_area: string;
  fiscal_year: number;
  org_unit: string;
  count: number;
  amount_usd: number;
  search_text: string;
};

function portfolioRows(role: Role | null, orgUnit: string | null): AggregateRow[] {
  const grants = visibleGrants(role, orgUnit).map((grant) => ({
    batch_id: grant.batch_id,
    program_area: grant.program_area,
    fiscal_year: grant.fiscal_year,
    org_unit: grant.org_unit,
    count: 1,
    amount_usd: grant.amount_usd,
    search_text: [
      grant.grant_no,
      grant.title,
      grant.abstract,
      grant.program_area,
      grant.awardee,
      grant.org_unit,
    ]
      .join(" ")
      .toLowerCase(),
  }));
  const replay = dynamicPortfolioAggregates(role, orgUnit).map((batch) => ({
    batch_id: batch.batch_id,
    program_area: batch.program_area,
    fiscal_year: batch.fiscal_year,
    org_unit: batch.org_unit,
    count: batch.grant_count,
    amount_usd: batch.amount_usd,
    search_text: [batch.batch_id, batch.program_area, batch.org_unit, "synthetic replay batch"]
      .join(" ")
      .toLowerCase(),
  }));
  return [...grants, ...replay];
}

function normalizeFilters(filters: DashboardFilters): DashboardFilters {
  return {
    ...(filters.program_area ? { program_area: filters.program_area } : {}),
    ...(Number.isInteger(filters.fiscal_year) ? { fiscal_year: filters.fiscal_year } : {}),
    ...(filters.org_unit ? { org_unit: filters.org_unit } : {}),
    ...(filters.q?.trim() ? { q: filters.q.trim() } : {}),
  };
}

function matches(row: AggregateRow, filters: DashboardFilters): boolean {
  if (filters.program_area && row.program_area !== filters.program_area) return false;
  if (filters.fiscal_year && row.fiscal_year !== filters.fiscal_year) return false;
  if (filters.org_unit && row.org_unit !== filters.org_unit) return false;
  if (filters.q && !row.search_text.includes(filters.q.toLowerCase())) return false;
  return true;
}

function visibleAmount(role: Role | null, value: number): number | null {
  return maskAmount(role, value);
}

export function getDashboard(
  role: Role | null,
  orgUnit: string | null,
  requestedFilters: DashboardFilters = {},
): DashboardResponse {
  const allVisibleRows = portfolioRows(role, orgUnit);
  const filters = normalizeFilters(requestedFilters);
  const rows = allVisibleRows.filter((row) => matches(row, filters));
  const filterOptions = {
    program_areas: [...new Set(allVisibleRows.map((row) => row.program_area))].sort(),
    fiscal_years: [...new Set(allVisibleRows.map((row) => row.fiscal_year))].sort((a, b) => b - a),
    org_units: [...new Set(allVisibleRows.map((row) => row.org_unit))].sort(),
  };

  const funding_by_program_area = PROGRAM_AREAS.map((program_area) => {
    const matches = rows.filter((row) => row.program_area === program_area);
    return {
      program_area,
      amount_usd: visibleAmount(
        role,
        matches.reduce((total, row) => total + row.amount_usd, 0),
      ),
      grant_count: matches.reduce((total, row) => total + row.count, 0),
    };
  }).filter((row) => row.grant_count > 0);

  const fiscalYears = [...new Set(rows.map((row) => row.fiscal_year))].sort();
  const funding_by_fiscal_year = fiscalYears.map((fiscal_year) => {
    const matches = rows.filter((row) => row.fiscal_year === fiscal_year);
    return {
      fiscal_year,
      amount_usd: visibleAmount(
        role,
        matches.reduce((total, row) => total + row.amount_usd, 0),
      ),
    };
  });

  const includedBatchIds = new Set(rows.map((row) => row.batch_id));
  const quality_trend = visibleScenarioBatches(role, orgUnit)
    .filter((batch) => batch.status === "passed" || batch.status === "failed")
    .filter((batch) => {
      if (includedBatchIds.has(batch.batch_id)) return true;
      if (!batch.baseline && batch.status === "failed") {
        const failedProjection: AggregateRow = {
          batch_id: batch.batch_id,
          program_area: batch.program_area,
          fiscal_year: batch.fiscal_year,
          org_unit: batch.org_unit,
          count: 0,
          amount_usd: 0,
          search_text: [batch.batch_id, batch.program_area, batch.org_unit, "quarantine"]
            .join(" ")
            .toLowerCase(),
        };
        return matches(failedProjection, filters);
      }
      return Object.keys(filters).length === 0;
    })
    .map((batch) => ({
      run_id: batch.run_id,
      date: batch.ingested_at,
      score: batch.overall_score,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  const totalTopicGrants = rows.reduce((total, row) => total + row.count, 0) || 1;
  const top_topics = funding_by_program_area
    .slice()
    .sort((a, b) => b.grant_count - a.grant_count)
    .slice(0, 5)
    .map((program, index) => ({
      topic_id: index,
      label: program.program_area,
      weight: Math.round((program.grant_count / totalTopicGrants) * 1000) / 1000,
    }));

  const orgUnits = [...new Set(rows.map((row) => row.org_unit))].sort();
  const org_unit_breakdown = orgUnits.map((unit) => {
    const matches = rows.filter((row) => row.org_unit === unit);
    return {
      org_unit: unit,
      grant_count: matches.reduce((total, row) => total + row.count, 0),
      amount_usd: visibleAmount(
        role,
        matches.reduce((total, row) => total + row.amount_usd, 0),
      ),
    };
  });

  const filteredGrantIds = new Set(
    ALL_GRANTS.filter((grant) =>
      rows.some(
        (row) =>
          row.batch_id === grant.batch_id &&
          row.program_area === grant.program_area &&
          row.org_unit === grant.org_unit &&
          row.fiscal_year === grant.fiscal_year,
      ),
    ).map((grant) => grant.id),
  );
  const { anomalies: allAnomalies } = getAnomalies(role, orgUnit);
  const anomalies =
    Object.keys(filters).length === 0
      ? allAnomalies
      : allAnomalies.filter((anomaly) =>
          anomaly.grant_id
            ? filteredGrantIds.has(anomaly.grant_id)
            : rows.some((row) => anomaly.reason.includes(row.batch_id)),
        );
  const totalGrants = rows.reduce((total, row) => total + row.count, 0);
  const totalFunding = rows.reduce((total, row) => total + row.amount_usd, 0);
  const averageQuality =
    quality_trend.length === 0
      ? null
      : Math.round(
          (quality_trend.reduce((total, result) => total + result.score, 0) /
            quality_trend.length) *
            10,
        ) / 10;

  const response = {
    kpis: {
      total_grants: totalGrants,
      total_funding_usd: visibleAmount(role, totalFunding),
      active_program_areas: funding_by_program_area.length,
      avg_quality_score: averageQuality,
      open_anomalies: anomalies.filter((anomaly) => anomaly.status === "open").length,
      pending_approvals: pendingApprovalCount(role),
    },
    funding_by_program_area,
    funding_by_fiscal_year,
    quality_trend,
    top_topics,
    org_unit_breakdown,
    filters_applied: {
      program_area: filters.program_area ?? null,
      fiscal_year: filters.fiscal_year ?? null,
      org_unit: filters.org_unit ?? null,
      q: filters.q ?? null,
    },
    filter_options: filterOptions,
    replay: true,
  };
  return response;
}

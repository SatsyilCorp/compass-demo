/**
 * Topic analytics over the shared replay portfolio. Completed run identifiers
 * and timestamps persist, while role and org filters are evaluated on read.
 */
import type { AnalyticsRunDetail, AnalyticsRunResponse, Role, Topic } from "@/lib/types";
import { maskAmount, visibleGrants } from "./grants";
import {
  REPLAY_BASE_TIME,
  clearAnalyticsRuns,
  dynamicPortfolioAggregates,
  findAnalyticsRun,
  getAnalyticsHistory,
  recordAnalyticsRun,
} from "./scenario-store";

const FISCAL_YEARS = [2022, 2023, 2024, 2025, 2026];

type Contribution = {
  programArea: string;
  fiscalYear: number;
  count: number;
  amountUsd: number;
};

function contributions(
  role: Role | null,
  orgUnit: string | null,
  includedBatchIds?: ReadonlySet<string>,
): Contribution[] {
  const grants = visibleGrants(role, orgUnit).map((grant) => ({
    programArea: grant.program_area,
    fiscalYear: grant.fiscal_year,
    count: 1,
    amountUsd: grant.amount_usd,
  }));
  const replay = dynamicPortfolioAggregates(role, orgUnit)
    .filter((batch) => !includedBatchIds || includedBatchIds.has(batch.batch_id))
    .map((batch) => ({
      programArea: batch.program_area,
      fiscalYear: batch.fiscal_year,
      count: batch.grant_count,
      amountUsd: batch.amount_usd,
    }));
  return [...grants, ...replay];
}

function buildTopics(
  role: Role | null,
  orgUnit: string | null,
  includedBatchIds?: ReadonlySet<string>,
): Topic[] {
  const rows = contributions(role, orgUnit, includedBatchIds);
  const byProgram = new Map<string, Contribution[]>();
  for (const row of rows) {
    const existing = byProgram.get(row.programArea) ?? [];
    existing.push(row);
    byProgram.set(row.programArea, existing);
  }

  return [...byProgram.entries()]
    .sort((a, b) => {
      const countA = a[1].reduce((total, row) => total + row.count, 0);
      const countB = b[1].reduce((total, row) => total + row.count, 0);
      return countB - countA || a[0].localeCompare(b[0]);
    })
    .map(([label, programRows], index) => {
      const terms = label
        .toLowerCase()
        .replace(/&/g, "")
        .split(/\s+/)
        .filter((term) => term.length > 2);
      const grantCount = programRows.reduce((total, row) => total + row.count, 0);
      const amount = programRows.reduce((total, row) => total + row.amountUsd, 0);
      return {
        topic_id: index,
        label,
        top_terms: [...new Set(terms)].slice(0, 6),
        trend: FISCAL_YEARS.map((fiscalYear) => ({
          period: `FY${fiscalYear}`,
          value: programRows
            .filter((row) => row.fiscalYear === fiscalYear)
            .reduce((total, row) => total + row.count, 0),
        })),
        grant_count: grantCount,
        total_funding_usd: maskAmount(role, amount),
      } satisfies Topic;
    });
}

export function runAnalytics(): AnalyticsRunResponse {
  const run = recordAnalyticsRun();
  return { run_id: run.run_id, kind: "topic_model", status: "completed" };
}

export function getAnalyticsRun(
  runId: string,
  role: Role | null,
  orgUnit: string | null,
): AnalyticsRunDetail {
  const stored = findAnalyticsRun(runId);
  const includedBatchIds = stored
    ? new Set(stored.included_batch_ids ?? [])
    : undefined;
  const topics = buildTopics(role, orgUnit, includedBatchIds);
  const total = topics.reduce((count, topic) => count + topic.grant_count, 0);
  const top = topics[0];
  return {
    run_id: runId,
    kind: "topic_model",
    status: "completed",
    params: {
      k: topics.length,
      embedding_model: "amazon.titan-embed-text-v2:0",
      execution_mode: "deterministic_replay",
    },
    metrics: {
      coherence: 0.61,
      grants_scored: total,
      replay: true,
      portfolio_batch_count: includedBatchIds?.size ?? dynamicPortfolioAggregates(role, orgUnit).length,
    },
    recommendation: top
      ? `${top.label} is the largest visible investment concentration with ${top.grant_count} records. Review adjacent program areas that are trending upward before the next planning cycle.`
      : "No curated records are visible to this persona and org unit.",
    topics,
    created_at: stored?.created_at ?? REPLAY_BASE_TIME,
  };
}

export { clearAnalyticsRuns as clearAnalyticsHistory, getAnalyticsHistory };

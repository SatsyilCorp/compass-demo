/**
 * POST /analytics/run, GET /analytics/{run_id} — fixtures. Element 5 (topic
 * model over curated abstracts). Mirrors `topics` / `grant_topics` /
 * `model_runs` in db/migrations/001_schema.sql.
 */
import type { AnalyticsRunDetail, AnalyticsRunResponse, Role, Topic } from "@/lib/types";
import { maskAmount, sum, visibleGrants } from "./grants";

const FISCAL_YEARS = [2022, 2023, 2024, 2025, 2026];

function buildTopics(role: Role | null, orgUnit: string | null): Topic[] {
  const visible = visibleGrants(role, orgUnit);
  const byProgram = new Map<string, typeof visible>();
  for (const g of visible) {
    const arr = byProgram.get(g.program_area) ?? [];
    arr.push(g);
    byProgram.set(g.program_area, arr);
  }
  return [...byProgram.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .map(([label, grants], i) => {
      const terms = label
        .toLowerCase()
        .replace(/&/g, "")
        .split(/\s+/)
        .filter((t) => t.length > 2);
      const trend = FISCAL_YEARS.map((fy) => ({
        period: `FY${fy}`,
        value: grants.filter((g) => g.fiscal_year === fy).length,
      }));
      return {
        topic_id: i,
        label,
        top_terms: [...new Set(terms)].slice(0, 6),
        trend,
        grant_count: grants.length,
        total_funding_usd: sum(grants.map((g) => maskAmount(role, g.amount_usd))),
      } satisfies Topic;
    });
}

export function runAnalytics(): AnalyticsRunResponse {
  const run_id = `analytics-${Date.now()}`;
  return { run_id, kind: "topic_model", status: "completed" };
}

export function getAnalyticsRun(
  runId: string,
  role: Role | null,
  orgUnit: string | null,
): AnalyticsRunDetail {
  const topics = buildTopics(role, orgUnit);
  const total = topics.reduce((a, t) => a + t.grant_count, 0);
  const top = topics[0];
  return {
    run_id: runId,
    kind: "topic_model",
    status: "completed",
    params: { k: topics.length, embedding_model: "amazon.titan-embed-text-v2:0" },
    metrics: { coherence: 0.61, grants_scored: total },
    recommendation: top
      ? `${top.label} is the largest concentration of active S&T investment (${top.grant_count} grants). Consider a portfolio review of adjacent program areas trending upward year-over-year before the next planning cycle.`
      : "No grants are visible to this persona/org_unit to score.",
    topics,
    created_at: new Date().toISOString(),
  };
}

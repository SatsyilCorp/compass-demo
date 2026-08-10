"use client";

import { useState } from "react";
import { Network, Play, RefreshCw, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { TopicList } from "@/components/analytics/topic-list";
import { TopicTrendChart } from "@/components/analytics/topic-trend-chart";
import { AnomalyFlags } from "@/components/analytics/anomaly-flags";
import { RecommendationPanel } from "@/components/analytics/recommendation-panel";
import { getAnalyticsRun, getAnomalies, postAnalyticsRun, ApiError } from "@/lib/api";
import type { AnalyticsRunDetail, Anomaly } from "@/lib/types";

type RunStatus = "idle" | "running" | "completed" | "error";

/**
 * Element 5 — topic-model analytics. "Run analysis" drives the two-step
 * contract flow: POST /analytics/run -> {run_id}, then GET
 * /analytics/{run_id} for the topics/trend/recommendation. Anomaly flags
 * (GET /anomalies, element 6) are pulled alongside so a single "Run
 * analysis" click tells the whole investment-concentration story.
 */
export default function AnalyticsPage() {
  const [status, setStatus] = useState<RunStatus>("idle");
  const [detail, setDetail] = useState<AnalyticsRunDetail | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleRun() {
    setStatus("running");
    setErrorMessage(null);
    try {
      const { run_id } = await postAnalyticsRun();
      const [runDetail, anomaliesRes] = await Promise.all([getAnalyticsRun(run_id), getAnomalies()]);
      setDetail(runDetail);
      setAnomalies(anomaliesRes.anomalies);
      setStatus("completed");
    } catch (e: unknown) {
      setErrorMessage(e instanceof ApiError ? `API error ${e.status}` : e instanceof Error ? e.message : "Analysis run failed");
      setStatus("error");
    }
  }

  const hasRun = status === "completed" && detail !== null;

  return (
    <AppShell>
      <PageHeader
        kicker="Element 5 · Topic analytics"
        icon={<Network className="size-[18px]" aria-hidden />}
        title="Topic Analytics"
        lead="Runs the governed topic model over the curated, RLS-scoped portfolio: investment concentration by topic, emerging trends, open anomalies, and a written decision recommendation."
        actions={
          <button
            type="button"
            onClick={handleRun}
            disabled={status === "running"}
            className="inline-flex items-center gap-2 rounded-md bg-gov-primary px-4 py-2.5 text-sm font-semibold text-white shadow-card transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {status === "running" ? (
              <>
                <RefreshCw className="size-4 animate-spin" aria-hidden />
                Running…
              </>
            ) : hasRun ? (
              <>
                <RefreshCw className="size-4" aria-hidden />
                Re-run analysis
              </>
            ) : (
              <>
                <Play className="size-4" aria-hidden />
                Run analysis
              </>
            )}
          </button>
        }
      />

      <div className="mt-6 space-y-6">
        {status === "error" && (
          <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
            <TriangleAlert className="size-4 shrink-0" aria-hidden />
            {errorMessage}
          </div>
        )}

        {status === "idle" && (
          <div className="rounded-md border border-dashed border-border-strong bg-surface-2/50 p-10 text-center">
            <Network className="mx-auto size-8 text-text-subtle" aria-hidden />
            <p className="mt-3 text-sm font-semibold text-text-strong">No analysis run yet</p>
            <p className="mx-auto mt-1 max-w-md text-xs text-text-muted">
              Click <span className="font-semibold text-text">Run analysis</span> to score the currently visible
              portfolio: topic concentration, emerging trends, anomaly flags, and a decision recommendation.
            </p>
          </div>
        )}

        {status === "running" && <AnalyticsSkeleton />}

        {status === "completed" && detail && (
          <>
            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Topics (top terms)</h2>
              <TopicList topics={detail.topics} />
            </section>

            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Emerging-topic trend</h2>
              <div className="rounded-md border border-border bg-surface p-4">
                <TopicTrendChart topics={detail.topics} />
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Anomaly flags</h2>
              <AnomalyFlags anomalies={anomalies ?? []} />
            </section>

            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Recommendation</h2>
              <RecommendationPanel detail={detail} />
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton h-28 rounded-md" />
        ))}
      </div>
      <div className="skeleton h-[300px] rounded-md" />
      <div className="skeleton h-40 rounded-md" />
    </div>
  );
}

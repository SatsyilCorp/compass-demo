"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Clock3,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  TriangleAlert,
} from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { LivePublicAnalytics } from "@/components/public-intelligence/live-public-analytics";
import { TopicList } from "@/components/analytics/topic-list";
import { TopicTrendChart } from "@/components/analytics/topic-trend-chart";
import { AnomalyFlags } from "@/components/analytics/anomaly-flags";
import { RecommendationPanel } from "@/components/analytics/recommendation-panel";
import {
  ApiError,
  getAnalyticsRun,
  getAnomalies,
  postAnalyticsRun,
} from "@/lib/api";
import {
  clearAnalyticsHistory,
  getAnalyticsHistory,
} from "@/lib/mock/analytics";
import { subscribeScenario, type ScenarioAnalysisRun } from "@/lib/mock/scenario-store";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import type { AnalyticsRunDetail, Anomaly } from "@/lib/types";

type RunStatus = "idle" | "running" | "completed" | "error";

export default function AnalyticsPage() {
  const { mode } = useEvidenceMode();

  if (mode === "rehearsal") return <RehearsalAnalyticsWorkspace />;

  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Live public evidence | Analytics and model signals"
        icon={<Network className="size-[18px]" aria-hidden />}
        title="Analyze source changes, model routes, and review flags"
        lead="Every chart and queue on this screen is calculated from the latest accepted public-source receipts and their real classifier results. No synthetic portfolio is silently substituted."
      />
      <div className="mt-6"><LivePublicAnalytics /></div>
    </AppShell>
  );
}

function RehearsalAnalyticsWorkspace() {
  const auth = useAppAuth();
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  const [status, setStatus] = useState<RunStatus>("idle");
  const [detail, setDetail] = useState<AnalyticsRunDetail | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[] | null>(null);
  const [history, setHistory] = useState<ScenarioAnalysisRun[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadRun = useCallback(async (runId: string) => {
    setStatus("running");
    setErrorMessage(null);
    try {
      const [runDetail, anomaliesResponse] = await Promise.all([
        getAnalyticsRun(runId),
        getAnomalies(),
      ]);
      setDetail(runDetail);
      setAnomalies(anomaliesResponse.anomalies);
      setStatus("completed");
    } catch (error: unknown) {
      setErrorMessage(
        error instanceof ApiError
          ? `API error ${error.status}`
          : error instanceof Error
            ? error.message
            : "Analysis run failed",
      );
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (!rehearsal) return;
    const syncHistory = () => setHistory(getAnalyticsHistory());
    syncHistory();
    const latest = getAnalyticsHistory()[0];
    if (latest) void loadRun(latest.run_id);
    return subscribeScenario(syncHistory);
  }, [loadRun, rehearsal]);

  useEffect(() => {
    if (detail) void loadRun(detail.run_id);
  }, [auth.role, auth.orgUnit]);

  async function handleRun() {
    setStatus("running");
    setErrorMessage(null);
    try {
      const { run_id } = await postAnalyticsRun();
      await loadRun(run_id);
      if (rehearsal) setHistory(getAnalyticsHistory());
    } catch (error: unknown) {
      setErrorMessage(
        error instanceof ApiError
          ? `API error ${error.status}`
          : error instanceof Error
            ? error.message
            : "Analysis run failed",
      );
      setStatus("error");
    }
  }

  function handleClearHistory() {
    clearAnalyticsHistory();
    setHistory([]);
    setDetail(null);
    setAnomalies(null);
    setStatus("idle");
    setErrorMessage(null);
  }

  const hasRun = status === "completed" && detail !== null;

  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Explicit rehearsal | Decision analytics"
        icon={<Network className="size-[18px]" aria-hidden />}
        title="Rehearse the analytics and review workflow"
        lead="Run the deterministic rehearsal analysis, compare synthetic investment concentration, surface fixture topics and anomalies, and practice routing a recommended next action without claiming a live model execution."
        actions={
          <button
            type="button"
            onClick={() => void handleRun()}
            disabled={status === "running"}
            className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 py-2.5 text-sm font-semibold text-white shadow-card transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {status === "running" ? (
              <>
                <RefreshCw className="size-4 animate-spin" aria-hidden />
                Running…
              </>
            ) : hasRun ? (
              <>
                <RefreshCw className="size-4" aria-hidden />
                Run again
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

      {rehearsal ? (
        <section
          aria-label="Replay analysis history"
          className="mt-5 rounded-xl border border-gov-primary/20 bg-gov-primary-lighter/50 p-4 shadow-soft"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-gov-primary px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white">
                  Replay mode
                </span>
                <span className="text-xs font-semibold text-text-strong">
                  {history.length} persisted run{history.length === 1 ? "" : "s"}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 text-text-muted">
                Run history survives navigation and reloads. Each result keeps its captured batch set while applying the current persona scope.
              </p>
            </div>
            {history.length > 0 ? (
              <button
                type="button"
                onClick={handleClearHistory}
                className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-xs font-semibold text-text-muted transition-colors hover:border-border-strong hover:text-text-strong"
              >
                <RotateCcw className="size-3.5" aria-hidden />
                Clear history
              </button>
            ) : null}
          </div>

          {history.length > 0 ? (
            <div className="mt-4 flex gap-2 overflow-x-auto pb-1" role="list">
              {history.map((run) => {
                const selected = detail?.run_id === run.run_id;
                return (
                  <button
                    key={run.run_id}
                    type="button"
                    role="listitem"
                    aria-pressed={selected}
                    onClick={() => void loadRun(run.run_id)}
                    className={`min-h-12 shrink-0 rounded-lg border px-3 py-2 text-left transition-colors ${
                      selected
                        ? "border-gov-primary bg-surface text-gov-primary"
                        : "border-border bg-surface/70 text-text-muted hover:border-border-strong"
                    }`}
                  >
                    <span className="flex items-center gap-1.5 font-mono text-[11px] font-semibold">
                      <Clock3 className="size-3" aria-hidden />
                      {run.run_id}
                    </span>
                    <span className="mt-0.5 block text-[10px] text-text-subtle">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="mt-6 space-y-6">
        {status === "error" ? (
          <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
            <TriangleAlert className="size-4 shrink-0" aria-hidden />
            {errorMessage}
          </div>
        ) : null}

        {status === "idle" ? (
          <div className="rounded-xl border border-dashed border-border-strong bg-surface-2/50 p-10 text-center">
            <Network className="mx-auto size-8 text-text-subtle" aria-hidden />
            <p className="mt-3 text-sm font-semibold text-text-strong">Ready for a governed run</p>
            <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-text-muted">
              Run the analysis to score topic concentration, trends, anomalies, and a decision recommendation against the current curated state.
            </p>
          </div>
        ) : null}

        {status === "running" ? <AnalyticsSkeleton /> : null}

        {status === "completed" && detail ? (
          <>
            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Topics and evidence terms</h2>
              <TopicList topics={detail.topics} />
            </section>

            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Emerging topic trend</h2>
              <div className="rounded-xl border border-border bg-surface p-4 shadow-soft">
                <TopicTrendChart topics={detail.topics} />
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Anomaly flags</h2>
              <AnomalyFlags anomalies={anomalies ?? []} />
            </section>

            <section>
              <h2 className="mb-3 text-sm font-semibold text-text-strong">Recommended next action</h2>
              <RecommendationPanel detail={detail} />
            </section>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6" aria-label="Analysis running" aria-busy="true">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="skeleton h-28 rounded-md" />
        ))}
      </div>
      <div className="skeleton h-[300px] rounded-md" />
      <div className="skeleton h-40 rounded-md" />
    </div>
  );
}

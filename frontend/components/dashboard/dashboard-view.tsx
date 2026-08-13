"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  DollarSign,
  FileStack,
  Gauge,
  Radar,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import { getDashboard } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { useMissionDataContext } from "@/lib/mission-data-context";
import { subscribeLiveDemoStreamTick } from "@/lib/live-demo-stream-events";
import { PageHeader } from "@/components/shell/page-header";
import type { DashboardFilterOptions, DashboardFilters } from "@/lib/types";

import { AnomalyWorkflow } from "./anomaly-workflow";
import { AskCompass } from "./ask-compass";
import { DashboardFiltersBar } from "./dashboard-filters";
import { DecisionBrief } from "./decision-brief";
import { DocumentDecisionEvidence } from "./document-decision-evidence";
import { ExecSummary } from "./exec-summary";
import { KpiCard } from "./kpi-card";
import { BudgetExecutionChart } from "./charts/budget-execution-chart";
import { OrgUnitAwards } from "./charts/org-unit-awards";
import { ProgramFundingBar } from "./charts/program-funding-bar";
import { QualityTrend } from "./charts/quality-trend";
import { TopicConcentration } from "./charts/topic-concentration";
import { ScaleDecisionWorkspace } from "./scale-decision-workspace";
import { useCompassQuery } from "./use-compass-query";
import { num, usd } from "./format";


const EMPTY_OPTIONS: DashboardFilterOptions = {
  program_areas: [],
  fiscal_years: [],
  org_units: [],
};

export function DashboardView() {
  const { hydrated, selection, selectCurated } = useMissionDataContext();

  if (!hydrated) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          kicker="Portfolio command center"
          title="Decision workspace"
          icon={<Radar className="size-5" aria-hidden />}
          lead="Restoring the selected mission data context."
        />
        <LoadingSkeleton />
      </div>
    );
  }

  if (selection.kind === "scale") {
    return <ScaleDecisionWorkspace runId={selection.runId} onUseCurated={selectCurated} />;
  }

  return <CuratedDashboardView />;
}

function CuratedDashboardView() {
  const { role, orgUnit, displayName } = useAppAuth();
  const [filters, setFilters] = useState<DashboardFilters>({});
  const queryKey = useMemo(() => JSON.stringify(filters), [filters]);
  const { data, error, loading, reload } = useCompassQuery(
    () => getDashboard(filters),
    queryKey,
  );

  useEffect(() => subscribeLiveDemoStreamTick(reload), [reload]);

  const masked = data ? data.kpis.total_funding_usd === null : false;
  const scopeLabel =
    role === "poweruser"
      ? "the full ONR Corporate portfolio"
      : `the ${orgUnit ?? "assigned"} portfolio`;
  const filterOptions = data?.filter_options ?? EMPTY_OPTIONS;
  const reviewCount = data ? data.kpis.open_anomalies + data.kpis.pending_approvals : 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Portfolio overview"
        title="What is happening now"
        icon={<Radar className="size-5" aria-hidden />}
        lead="See where the money is going, what changed, and what needs a person to review."
        actions={
          <button
            type="button"
            onClick={reload}
            disabled={loading}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-4 text-sm font-semibold text-text shadow-soft transition-colors hover:bg-surface-2 disabled:cursor-wait disabled:opacity-50"
          >
            <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} aria-hidden />
            Refresh
          </button>
        }
      />

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-danger bg-danger-soft px-4 py-3 text-sm text-danger"
        >
          Could not load the dashboard: {error}
        </div>
      ) : null}

      {loading && !data ? (
        <LoadingSkeleton />
      ) : data ? (
        <>
          <DecisionBrief data={data} />

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Research awards"
              value={data.kpis.total_grants}
              sublabel={`${data.kpis.active_program_areas} program areas in view`}
              Icon={FileStack}
            />
            <KpiCard
              label="Funding in view"
              value={data.kpis.total_funding_usd ?? 0}
              format={(value) => usd(value)}
              masked={data.kpis.total_funding_usd === null}
              maskedReason="Your role does not permit access to award values."
              sublabel="obligated funding in this portfolio"
              Icon={DollarSign}
            />
            <KpiCard
              label="Data confidence"
              value={data.kpis.avg_quality_score ?? "No evidence"}
              format={(value) => value.toFixed(1)}
              sublabel={
                data.kpis.avg_quality_score === null
                  ? "no persisted gate receipt in scope"
                  : `${num(data.quality_trend.length)} governed runs`
              }
              Icon={Gauge}
            />
            <KpiCard
              label="Needs review"
              value={reviewCount}
              sublabel={`${data.kpis.open_anomalies} unusual records | ${data.kpis.pending_approvals} approvals`}
              tone={reviewCount > 0 ? "warn" : "default"}
              Icon={AlertTriangle}
              href="#portfolio-exceptions"
            />
          </div>

          <div id="portfolio-exceptions" className="scroll-mt-24">
            <AnomalyWorkflow />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ProgramFundingBar data={data.funding_by_program_area} />
            <BudgetExecutionChart data={data.funding_by_fiscal_year} />
          </div>

          <details className="group overflow-hidden rounded-lg border border-border bg-white shadow-soft">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-5 py-3 [&::-webkit-details-marker]:hidden">
              <div>
                <p className="text-sm font-bold text-text-strong">Explore supporting analysis</p>
                <p className="mt-0.5 text-xs text-text-muted">Filters, source evidence, AI summary, topics, organizations, and data-quality history.</p>
              </div>
              <span className="rounded-full border border-border bg-surface-2 px-3 py-1 text-[10px] font-bold text-text-muted group-open:hidden">Show details</span>
              <span className="hidden rounded-full border border-border bg-surface-2 px-3 py-1 text-[10px] font-bold text-text-muted group-open:inline">Hide details</span>
            </summary>
            <div className="space-y-5 border-t border-border bg-bg p-5">
              <DashboardFiltersBar
                value={filters}
                options={filterOptions}
                role={role ?? "viewer"}
                orgUnit={orgUnit}
                resultCount={data.kpis.total_grants}
                activeProgramAreas={data.kpis.active_program_areas}
                loading={loading}
                onChange={setFilters}
              />
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-white px-4 py-3 shadow-soft">
                <span className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-text-strong">
                  <ShieldCheck className="size-4 text-success" aria-hidden />
                  {displayName ?? "Assigned portfolio role"}
                </span>
                <span className="text-sm text-text-muted">You are viewing {scopeLabel}.</span>
                <span className={masked ? "rounded-full border border-warn bg-warn-soft px-3 py-1.5 text-xs font-semibold text-warn" : "rounded-full border border-success bg-success-soft px-3 py-1.5 text-xs font-semibold text-success"}>
                  {masked ? "Funding values protected" : "Funding values available"}
                </span>
              </div>
              <DocumentDecisionEvidence />
              <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
                <ExecSummary data={data} />
                <AskCompass scopeLabel={scopeLabel} />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <TopicConcentration data={data.top_topics} />
                <OrgUnitAwards data={data.org_unit_breakdown} />
              </div>
              <QualityTrend data={data.quality_trend} />
            </div>
          </details>
        </>
      ) : null}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading decision workspace">
      <div className="skeleton h-[220px] rounded-lg" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <div key={index} className="skeleton h-[112px] rounded-lg" />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <div className="skeleton h-[240px] rounded-lg" />
        <div className="skeleton h-[240px] rounded-lg" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="skeleton h-[320px] rounded-lg" />
        ))}
      </div>
    </div>
  );
}

export default DashboardView;

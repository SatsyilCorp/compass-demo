"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  DollarSign,
  FileStack,
  Gauge,
  Layers,
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

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Element 6 of 7 | Unified Dashboard and Process Automation"
        title="Decision workspace"
        icon={<Radar className="size-5" aria-hidden />}
        lead="Focus the research portfolio, surface exceptions, and move from evidence to the next decision without leaving the workspace."
        actions={
          <button
            type="button"
            onClick={reload}
            disabled={loading}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-4 text-sm font-semibold text-text shadow-soft transition-colors hover:bg-surface-2 disabled:cursor-wait disabled:opacity-50"
          >
            <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} aria-hidden />
            Refresh intelligence
          </button>
        }
      />

      <DashboardFiltersBar
        value={filters}
        options={filterOptions}
        role={role ?? "viewer"}
        orgUnit={orgUnit}
        resultCount={data?.kpis.total_grants ?? 0}
        activeProgramAreas={data?.kpis.active_program_areas ?? 0}
        loading={loading}
        onChange={setFilters}
      />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-surface px-4 py-3 shadow-soft">
        <span className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-text-strong">
          <ShieldCheck className="size-4 text-success" aria-hidden />
          {displayName ?? "Assigned portfolio role"}
        </span>
        <span className="text-sm text-text-muted">
          Access policy limits results to {scopeLabel}.
        </span>
        <span
          className={
            masked
              ? "rounded-full border border-warn bg-warn-soft px-3 py-1.5 text-xs font-semibold text-warn"
              : "rounded-full border border-success bg-success-soft px-3 py-1.5 text-xs font-semibold text-success"
          }
        >
          {masked ? "Funding values protected" : "Funding values available"}
        </span>
      </div>

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
          <DocumentDecisionEvidence />
          <DecisionBrief data={data} />

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
            <KpiCard
              label="Grants in scope"
              value={data.kpis.total_grants}
              sublabel="governed portfolio records"
              Icon={FileStack}
            />
            <KpiCard
              label="Obligated funding"
              value={data.kpis.total_funding_usd ?? 0}
              format={(value) => usd(value)}
              masked={data.kpis.total_funding_usd === null}
              maskedReason="Your role does not permit access to award values."
              sublabel="live actual obligations"
              Icon={DollarSign}
            />
            <KpiCard
              label="Program areas"
              value={data.kpis.active_program_areas}
              sublabel="represented in this result"
              Icon={Layers}
            />
            <KpiCard
              label="Quality confidence"
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
              label="Open anomalies"
              value={data.kpis.open_anomalies}
              sublabel="awaiting a disposition"
              tone={data.kpis.open_anomalies > 0 ? "warn" : "default"}
              Icon={AlertTriangle}
              href="#portfolio-exceptions"
            />
            <KpiCard
              label="Pending approvals"
              value={data.kpis.pending_approvals}
              sublabel="enterprise workflow queue"
              tone={data.kpis.pending_approvals > 0 ? "warn" : "default"}
              Icon={CheckCircle2}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <ExecSummary data={data} />
            <AskCompass scopeLabel={scopeLabel} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ProgramFundingBar data={data.funding_by_program_area} />
            <BudgetExecutionChart data={data.funding_by_fiscal_year} />
            <TopicConcentration data={data.top_topics} />
            <OrgUnitAwards data={data.org_unit_breakdown} />
          </div>

          <QualityTrend data={data.quality_trend} />

          <div id="portfolio-exceptions" className="scroll-mt-24">
            <AnomalyWorkflow />
          </div>
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

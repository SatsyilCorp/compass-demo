"use client";

import {
  AlertTriangle,
  CheckCircle2,
  DollarSign,
  FileStack,
  Gauge,
  LayoutDashboard,
  Layers,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import { getDashboard } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { PageHeader } from "@/components/shell/page-header";

import { AnomalyWorkflow } from "./anomaly-workflow";
import { AskCompass } from "./ask-compass";
import { ExecSummary } from "./exec-summary";
import { KpiCard } from "./kpi-card";
import { BudgetExecutionChart } from "./charts/budget-execution-chart";
import { OrgUnitAwards } from "./charts/org-unit-awards";
import { ProgramFundingBar } from "./charts/program-funding-bar";
import { QualityTrend } from "./charts/quality-trend";
import { TopicConcentration } from "./charts/topic-concentration";
import { useCompassQuery } from "./use-compass-query";
import { num, usd } from "./format";

/**
 * Element 6 — the executive dashboard.
 *
 * One round-trip to `GET /dashboard` fills the KPI row and every chart, exactly
 * as docs/CONTRACTS.md specifies; the Q&A box, the auto-summary, and the
 * anomaly workflow add `POST /chat`, `GET /anomalies`, and `POST /approvals`.
 *
 * The whole page is persona-scoped: `useCompassQuery` re-runs every call when
 * the signed-in role/org_unit changes, so switching persona visibly re-cuts the
 * portfolio (rows by RLS, dollars by CLS) instead of just relabelling chrome.
 */
export function DashboardView() {
  const { role, orgUnit, displayName } = useAppAuth();
  const { data, error, loading, reload } = useCompassQuery(getDashboard);

  const masked = data ? data.kpis.total_funding_usd === null : false;
  const scopeLabel =
    role === "poweruser"
      ? "the full ONR-Corporate portfolio"
      : `the ${orgUnit ?? "unassigned"} portfolio`;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Element 6 · Executive dashboard"
        title="S&T Portfolio Intelligence"
        icon={<LayoutDashboard className="size-4" aria-hidden />}
        lead="Portfolio health in one round-trip: funding concentration, execution against an even-spend baseline, topic mix, and the findings queue — all scoped to what your role is permitted to read."
        actions={
          <button
            type="button"
            onClick={reload}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded border border-border bg-surface px-3 py-2 text-[12px] font-semibold text-text shadow-soft transition-colors hover:bg-surface-2 disabled:opacity-50"
          >
            <RefreshCw className={loading ? "size-3.5 animate-spin" : "size-3.5"} aria-hidden />
            Refresh
          </button>
        }
      />

      {/* ---- Security scope strip ---------------------------------------- */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border border-border bg-surface px-4 py-3 shadow-soft">
        <span className="inline-flex items-center gap-2 text-[12px] font-semibold text-text-strong">
          <ShieldCheck className="size-4 text-gov-primary" aria-hidden />
          {displayName ?? "Unassigned persona"}
        </span>
        <span className="text-[11.5px] text-text-muted">
          Rows filtered by RLS on{" "}
          <code className="font-mono text-[11px]">compass.grants_curated</code> where{" "}
          <code className="font-mono text-[11px]">org_unit = {orgUnit ?? "—"}</code>
        </span>
        <span
          className={
            masked
              ? "rounded border border-warn bg-warn-soft px-2 py-0.5 text-[11px] font-semibold text-warn"
              : "rounded border border-border bg-surface-2 px-2 py-0.5 text-[11px] font-semibold text-text-muted"
          }
        >
          {masked ? "amount_usd masked by CLS" : "amount_usd readable"}
        </span>
        {data ? (
          <span className="ml-auto text-[11.5px] text-text-muted">
            <span className="font-mono font-semibold text-text-strong">
              {num(data.kpis.total_grants)}
            </span>{" "}
            grants visible in this scope
          </span>
        ) : null}
      </div>

      {error ? (
        <div className="rounded-md border border-danger bg-danger-soft px-4 py-3 text-[12.5px] text-danger">
          Could not load the dashboard — {error}
        </div>
      ) : null}

      {loading && !data ? (
        <LoadingSkeleton />
      ) : data ? (
        <>
          {/* ---- KPI row -------------------------------------------------- */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
            <KpiCard
              label="Grants in scope"
              value={data.kpis.total_grants}
              sublabel="curated rows you can read"
              Icon={FileStack}
            />
            <KpiCard
              label="Obligated funding"
              value={data.kpis.total_funding_usd ?? 0}
              format={(n) => usd(n)}
              masked={data.kpis.total_funding_usd === null}
              maskedReason="SELECT (amount_usd) is revoked for the viewer role."
              sublabel="across visible awards"
              Icon={DollarSign}
            />
            <KpiCard
              label="Program areas"
              value={data.kpis.active_program_areas}
              sublabel="with at least one award"
              Icon={Layers}
            />
            <KpiCard
              label="Avg quality score"
              value={data.kpis.avg_quality_score}
              format={(n) => n.toFixed(1)}
              sublabel={`${num(data.quality_trend.length)} ingest runs`}
              Icon={Gauge}
            />
            <KpiCard
              label="Open anomalies"
              value={data.kpis.open_anomalies}
              sublabel="awaiting triage"
              tone={data.kpis.open_anomalies > 0 ? "warn" : "default"}
              Icon={AlertTriangle}
            />
            <KpiCard
              label="Pending approvals"
              value={data.kpis.pending_approvals}
              sublabel="exports and dispositions"
              tone={data.kpis.pending_approvals > 0 ? "warn" : "default"}
              Icon={CheckCircle2}
            />
          </div>

          {/* ---- Summary + Q&A -------------------------------------------- */}
          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <ExecSummary data={data} />
            <AskCompass scopeLabel={scopeLabel} />
          </div>

          {/* ---- Charts ---------------------------------------------------- */}
          <div className="grid gap-4 lg:grid-cols-2">
            <ProgramFundingBar data={data.funding_by_program_area} />
            <BudgetExecutionChart data={data.funding_by_fiscal_year} />
            <TopicConcentration data={data.top_topics} />
            <OrgUnitAwards data={data.org_unit_breakdown} />
          </div>

          <QualityTrend data={data.quality_trend} />

          {/* ---- Workflow --------------------------------------------------- */}
          <AnomalyWorkflow />
        </>
      ) : null}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="skeleton h-[104px] rounded-md" />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
        <div className="skeleton h-[220px] rounded-md" />
        <div className="skeleton h-[220px] rounded-md" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="skeleton h-[300px] rounded-md" />
        ))}
      </div>
    </div>
  );
}

export default DashboardView;

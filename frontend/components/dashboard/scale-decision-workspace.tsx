"use client";

import Link from "next/link";
import { useEffect, useMemo } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDollarSign,
  DatabaseZap,
  FileSearch,
  Gauge,
  Layers3,
  RefreshCw,
  ShieldCheck,
  TimerReset,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import { KpiCard } from "@/components/dashboard/kpi-card";
import { PageHeader } from "@/components/shell/page-header";
import { buildScaleDecisionProjection, type ScaleDecisionCard } from "@/lib/scale/decision-projection";
import { formatCount, getScaleAdapter, type ScaleRun } from "@/lib/scale";

import { useCompassQuery } from "./use-compass-query";

const ACTIVE_REFRESH_MS = 2_500;

export function ScaleDecisionWorkspace({
  runId,
  onUseCurated,
}: {
  runId: string;
  onUseCurated: () => void;
}) {
  const adapter = useMemo(() => getScaleAdapter(), []);
  const { data: run, error, loading, reload } = useCompassQuery(
    () => adapter.getRun(runId),
    `scale-decision:${runId}`,
  );

  useEffect(() => {
    if (!run || isTerminal(run.status)) return;
    const timer = window.setTimeout(reload, ACTIVE_REFRESH_MS);
    return () => window.clearTimeout(timer);
  }, [reload, run]);

  if (loading && !run) {
    return (
      <ScaleFrame onUseCurated={onUseCurated} runId={runId} reload={reload} loading>
        <ScaleLoading />
      </ScaleFrame>
    );
  }

  if (error || !run) {
    const missing = Boolean(
      error && (
        error.startsWith("HTTP 404") ||
        error === "run_not_found" ||
        error.includes("No scale run exists")
      )
    );
    return (
      <ScaleFrame onUseCurated={onUseCurated} runId={runId} reload={reload} loading={loading}>
        <section
          role="alert"
          className="rounded-xl border border-danger/40 bg-danger-soft p-6 shadow-soft"
        >
          <div className="flex items-start gap-3">
            <XCircle className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
            <div>
              <h2 className="text-base font-bold text-text-strong">
                {missing ? "Scale Run not found" : "Could not load Scale decision context"}
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
                {missing
                  ? "The selected receipt is missing or is no longer retained. Compass will not substitute the curated baseline because that would change the decision context without your approval."
                  : `The selected Scale receipt could not be reached. ${error ?? "No receipt was returned."} Compass will keep this context selected and will not substitute curated data.`}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <button type="button" onClick={reload} className={SECONDARY_BUTTON}>
                  <RefreshCw className="size-4" aria-hidden /> Retry receipt
                </button>
                <button type="button" onClick={onUseCurated} className={PRIMARY_BUTTON}>
                  Use curated baseline
                </button>
              </div>
            </div>
          </div>
        </section>
      </ScaleFrame>
    );
  }

  const projection = buildScaleDecisionProjection(run);
  return (
    <ScaleFrame onUseCurated={onUseCurated} runId={runId} reload={reload} loading={loading}>
      <section className="overflow-hidden rounded-xl border border-gov-primary/25 bg-gov-primary text-white shadow-card">
        <div className="grid gap-5 px-5 py-5 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <RunStatus run={run} />
              <span className="rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/80">
                Aggregate receipt
              </span>
            </div>
            <p className="mt-4 text-3xl font-semibold tracking-tight text-white">
              {projection.recordContext}
            </p>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">
              Plan: {formatCount(run.plan.total_records)} synthetic records. Selected run <span className="font-mono text-white/90">{projection.runId}</span>. This workspace is derived from its public, checksummed Scale receipt.
            </p>
          </div>
          <div className="min-w-44 rounded-lg border border-white/15 bg-white/10 px-4 py-3">
            <p className="text-[10px] font-bold uppercase tracking-wide text-white/55">Recorded progress</p>
            <p className="mt-1 text-2xl font-bold text-white">{projection.progressPercent}%</p>
            <div
              className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/15"
              role="progressbar"
              aria-label="Selected Scale Run progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={projection.progressPercent}
            >
              <div className="h-full rounded-full bg-gold-light" style={{ width: `${projection.progressPercent}%` }} />
            </div>
          </div>
        </div>
      </section>

      <RunStateNotice run={run} />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-7" aria-label="Scale Run decision metrics">
        <KpiCard label="Grants analyzed" value={projection.grantsAnalyzed} sublabel={metricSublabel(projection.grantsAnalyzed, projection.state, "grant corpus measured in receipt", "waiting for intelligence stage")} Icon={FileSearch} />
        <KpiCard label="Quality score" value={formatQualityScore(projection.qualityScore)} sublabel={metricSublabel(projection.qualityScore, projection.state, "synthetic domains measured", "waiting for quality stage")} Icon={Gauge} />
        <KpiCard label="Quarantined" value={projection.quarantinedRecords} sublabel={metricSublabel(projection.quarantinedRecords, projection.state, "records held by quality gates", "waiting for quality stage")} tone={isPositiveMeasure(projection.quarantinedRecords) ? "warn" : "default"} Icon={AlertTriangle} />
        <KpiCard label="Anomaly-linked records" value={projection.anomalyLinkedRecords} sublabel={metricSublabel(projection.anomalyLinkedRecords, projection.state, "aggregate detected findings", "waiting for intelligence stage")} tone={isPositiveMeasure(projection.anomalyLinkedRecords) ? "warn" : "default"} Icon={ShieldCheck} />
        <KpiCard label="Partitions" value={projection.partitions} sublabel={metricSublabel(projection.partitions, projection.state, "reported of planned", "waiting for partition outcomes")} Icon={Layers3} />
        <KpiCard label="Peak throughput" value={projection.peakThroughput} sublabel={metricSublabel(projection.peakThroughput, projection.state, "observed generation rate", "waiting for throughput evidence")} Icon={Activity} />
        <KpiCard label="Accrued estimated cost" value={projection.accruedCost} sublabel={metricSublabel(projection.accruedCost, projection.state, "modeled cost, not billed", "waiting for modeled cost evidence")} Icon={CircleDollarSign} />
      </section>

      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card" aria-labelledby="scale-decision-brief-heading">
        <header className="border-b border-white/15 px-5 py-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gold-light">Decision brief</p>
          <h2 id="scale-decision-brief-heading" className="mt-1 text-xl font-semibold text-white">What deserves attention in this Scale Run</h2>
        </header>
        <div className="grid md:grid-cols-3">
          <DecisionCard card={projection.proof} icon={CheckCircle2} />
          <DecisionCard card={projection.exceptions} icon={AlertTriangle} bordered />
          <DecisionCard card={projection.recommendation} icon={DatabaseZap} bordered />
        </div>
      </section>

      <section className="rounded-xl border border-warn/35 bg-warn-soft px-5 py-4" aria-label="Scale decision disclosure">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />
          <div>
            <h2 className="text-sm font-bold text-text-strong">Aggregate receipt only</h2>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              This Scale context provides corpus totals, quality, partition, throughput, cost, and aggregate intelligence evidence. It does not provide row filters, grant citations, funding charts, or workflow dispositions. Use the curated baseline for those record-level interactions.
            </p>
          </div>
        </div>
      </section>
    </ScaleFrame>
  );
}

function formatQualityScore(value: number | "Pending" | "Unavailable"): string {
  return typeof value === "number" ? `${value.toFixed(2)}%` : value;
}

function isPositiveMeasure(value: number | "Pending" | "Unavailable"): boolean {
  return typeof value === "number" && value > 0;
}

function metricSublabel(
  value: number | string,
  state: "running" | "completed" | "failed" | "cancelled",
  measuredLabel: string,
  pendingLabel: string,
): string {
  if (value === "Pending") return pendingLabel;
  if (value === "Unavailable") return "not produced before the run ended";
  if (state === "running") return `partial ${measuredLabel}`;
  if (state === "failed") return `${measuredLabel}, recorded before failure`;
  if (state === "cancelled") return `${measuredLabel}, recorded before cancellation`;
  return measuredLabel;
}

function ScaleFrame({
  children,
  onUseCurated,
  runId,
  reload,
  loading,
}: {
  children: React.ReactNode;
  onUseCurated: () => void;
  runId: string;
  reload: () => void;
  loading: boolean;
}) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Scale run decision context"
        title="Decision workspace"
        icon={<DatabaseZap className="size-5" aria-hidden />}
        lead="Read the selected production-scale receipt as a bounded decision context without mixing it with the curated baseline."
        actions={(
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onUseCurated} className={SECONDARY_BUTTON}>
              Use curated baseline
            </button>
            <Link href={`/admin/scale/?run=${encodeURIComponent(runId)}`} className={PRIMARY_BUTTON}>
              Open Scale Lab
            </Link>
            <button type="button" onClick={reload} disabled={loading} className={ICON_BUTTON} aria-label="Refresh Scale receipt">
              <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} aria-hidden />
            </button>
          </div>
        )}
      />
      {children}
    </div>
  );
}

function RunStatus({ run }: { run: ScaleRun }) {
  const terminalSuccess = run.status === "completed";
  const failed = run.status === "failed";
  const cancelled = run.status === "cancelled";
  const Icon = terminalSuccess ? CheckCircle2 : failed ? XCircle : cancelled ? AlertTriangle : TimerReset;
  const label = terminalSuccess
    ? "Completed receipt"
    : failed
      ? "Failed run"
      : cancelled
        ? "Cancelled run"
        : "Live run in progress";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/90">
      <Icon className="size-3.5" aria-hidden /> {label}
    </span>
  );
}

function RunStateNotice({ run }: { run: ScaleRun }) {
  if (run.status === "completed") return null;
  if (run.status === "failed") {
    return (
      <div role="alert" className="rounded-lg border border-danger/40 bg-danger-soft px-4 py-3 text-sm text-danger">
        <strong>Scale Run failed.</strong> {run.error?.message ?? "The run ended before it produced terminal evidence."}
        {run.error?.code ? <span className="ml-2 font-mono text-xs">{run.error.code}</span> : null}
      </div>
    );
  }
  if (run.status === "cancelled") {
    return (
      <div role="status" className="rounded-lg border border-warn/40 bg-warn-soft px-4 py-3 text-sm text-warn">
        <strong>Scale Run cancelled.</strong> Partial values remain visible as receipt evidence and are not presented as a decision result.
      </div>
    );
  }
  return (
    <div role="status" className="rounded-lg border border-gov-primary/25 bg-gov-primary-lighter px-4 py-3 text-sm text-gov-primary">
      <strong>Scale Run still in progress.</strong> This context refreshes automatically. Values are partial until the terminal receipt is available.
    </div>
  );
}

function DecisionCard({ card, icon: Icon, bordered = false }: { card: ScaleDecisionCard; icon: LucideIcon; bordered?: boolean }) {
  return (
    <article className={`p-5 ${bordered ? "border-t border-white/15 md:border-l md:border-t-0" : ""}`}>
      <div className="flex items-center gap-2 text-gold-light">
        <Icon className="size-4" aria-hidden />
        <p className="text-[11px] font-bold uppercase tracking-[0.14em]">{card.eyebrow}</p>
      </div>
      <h3 className="mt-2 text-base font-semibold leading-snug text-white">{card.title}</h3>
      <p className="mt-1.5 text-sm leading-6 text-white/75">{card.detail}</p>
    </article>
  );
}

function ScaleLoading() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading selected Scale Run">
      <div className="skeleton h-48 rounded-xl" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-7">
        {Array.from({ length: 7 }, (_, index) => <div key={index} className="skeleton h-28 rounded-lg" />)}
      </div>
      <div className="skeleton h-64 rounded-xl" />
    </div>
  );
}

function isTerminal(status: ScaleRun["status"]): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

const PRIMARY_BUTTON = "inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-gold px-4 text-sm font-bold text-gov-primary-dark transition-colors hover:bg-gold-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gov-primary";
const SECONDARY_BUTTON = "inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-border bg-surface px-4 text-sm font-semibold text-text shadow-soft transition-colors hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gov-primary";
const ICON_BUTTON = "inline-flex size-11 items-center justify-center rounded-md border border-border bg-surface text-text shadow-soft transition-colors hover:bg-surface-2 disabled:cursor-wait disabled:opacity-50";

export default ScaleDecisionWorkspace;

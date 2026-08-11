"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import {
  Activity,
  AlertCircle,
  BarChart3,
  BrainCircuit,
  Check,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Copy,
  Database,
  Download,
  FileCheck2,
  Gauge,
  LayoutDashboard,
  LoaderCircle,
  OctagonX,
  PackageCheck,
  ShieldCheck,
  TimerReset,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import {
  formatBytes,
  formatCount,
  formatCurrency,
  formatDuration,
  formatPercent,
  isTerminalScaleStatus,
  type ScaleRun,
} from "@/lib/scale";

type RunTab = "metrics" | "evidence" | "cost" | "intelligence" | "export";

const TABS: { id: RunTab; label: string; icon: LucideIcon }[] = [
  { id: "metrics", label: "Mission metrics", icon: Activity },
  { id: "evidence", label: "Evidence", icon: ShieldCheck },
  { id: "cost", label: "Cost", icon: CircleDollarSign },
  { id: "intelligence", label: "Intelligence", icon: BrainCircuit },
  { id: "export", label: "Export receipt", icon: Download },
];

const STATUS_LABEL: Record<ScaleRun["status"], string> = {
  queued: "Queued",
  generating: "Generating synthetic data",
  ingesting: "Ingesting partitions",
  quality: "Applying quality gates",
  intelligence: "Building intelligence",
  exporting: "Building release",
  cancelling: "Cancellation requested",
  cancelled: "Cancelled",
  completed: "Completed",
  failed: "Failed",
};

function progressTimingLabel(run: ScaleRun): string {
  if (run.status === "completed") return "Final evidence sealed";
  if (run.status === "failed") return "Run failed before final evidence was sealed";
  if (run.status === "cancelled") return "Run cancelled with partial evidence retained";
  if (run.status === "cancelling") return "Cancellation is being finalized";
  if (run.progress.eta_seconds === null) return "Completion estimate unavailable";
  if (run.progress.eta_seconds <= 0) return "Finalization in progress";
  return `${formatDuration(run.progress.eta_seconds)} estimated remaining`;
}

export function RunConsole({
  run,
  staleMessage,
  lastGoodAt,
  onCancel,
  cancelling,
  onRequestExport,
  exportBusy,
  activeEvidenceSet,
  onUseInDecisionBrief,
}: {
  run: ScaleRun;
  staleMessage: string | null;
  lastGoodAt: string | null;
  onCancel: () => void;
  cancelling: boolean;
  onRequestExport: () => void;
  exportBusy: boolean;
  activeEvidenceSet: boolean;
  onUseInDecisionBrief: () => void;
}) {
  const [tab, setTab] = useState<RunTab>("metrics");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const terminal = isTerminalScaleStatus(run.status);
  const success = run.status === "completed";
  const cancelled = run.status === "cancelled";

  const handleTabKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % TABS.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + TABS.length) % TABS.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = TABS.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    setTab(TABS[nextIndex].id);
    tabRefs.current[nextIndex]?.focus();
  };

  return (
    <section className="mt-6 overflow-hidden rounded-xl border border-border bg-surface shadow-card" aria-labelledby="active-scale-run-heading">
      <header className="border-b border-border-2 bg-gov-primary px-5 py-5 text-white">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-white/90">
                {run.mode === "live" ? <Activity className="size-3" aria-hidden /> : <TimerReset className="size-3" aria-hidden />}
                {run.mode === "live" ? "Live AWS run" : "Deterministic replay"}
              </span>
              <StatusPill status={run.status} />
            </div>
            <h2 id="active-scale-run-heading" className="mt-3 break-all font-mono text-lg font-bold tracking-tight sm:text-xl">{run.run_id}</h2>
            <p className="mt-1 text-xs text-white/65">
              {formatCount(run.plan.total_records)} records · seed {run.plan.seed} · {formatCount(run.plan.partition_count)} partitions
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {activeEvidenceSet ? (
              <span className="inline-flex min-h-11 items-center gap-2 rounded-md border border-emerald-300/35 bg-emerald-300/15 px-3 text-xs font-semibold text-emerald-100" role="status">
                <CheckCircle2 className="size-4" aria-hidden /> Active evidence set
              </span>
            ) : (
              <button
                type="button"
                onClick={onUseInDecisionBrief}
                className="inline-flex min-h-11 items-center gap-2 rounded-md border border-gold-light/45 bg-gold-light/15 px-3 text-xs font-semibold text-gold-light transition-colors hover:bg-gold-light/25"
              >
                <LayoutDashboard className="size-4" aria-hidden /> Use in Decision Brief
              </button>
            )}
            <CopyButton value={run.run_id} />
            {!terminal && (
              <button
                type="button"
                onClick={onCancel}
                disabled={cancelling || run.status === "cancelling"}
                className="inline-flex min-h-11 items-center gap-2 rounded-md border border-white/25 bg-white/10 px-3 text-xs font-semibold text-white hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-55"
              >
                <OctagonX className="size-4" aria-hidden /> {cancelling ? "Requesting" : "Cancel run"}
              </button>
            )}
          </div>
        </div>
        <div className="mt-5">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-white/55">Current operation</p>
              <p className="mt-1 text-sm font-semibold text-white">{STATUS_LABEL[run.status]}</p>
            </div>
            <p className="font-mono text-xl font-bold text-white">{run.progress.percent}%</p>
          </div>
          <div
            className="mt-2 h-2 overflow-hidden rounded-full bg-white/15"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={run.progress.percent}
            aria-label="Scale run progress"
          >
            <div className={`h-full rounded-full transition-[width] duration-500 ${success ? "bg-emerald-300" : cancelled ? "bg-white/45" : "bg-gold-light"}`} style={{ width: `${run.progress.percent}%` }} />
          </div>
          <div className="mt-2 flex flex-wrap justify-between gap-2 text-[10px] text-white/55">
            <span>{formatDuration(run.progress.elapsed_seconds)} elapsed</span>
            <span>{progressTimingLabel(run)}</span>
          </div>
        </div>
      </header>

      {staleMessage && (
        <div className="flex items-start gap-2 border-b border-warn/30 bg-warn-soft px-5 py-3 text-xs text-warn" role="status">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>
            <strong>Live refresh interrupted.</strong> Showing the last good snapshot{lastGoodAt ? ` from ${new Date(lastGoodAt).toLocaleTimeString()}` : ""}. {staleMessage}
          </p>
        </div>
      )}

      {run.error && (
        <div className="flex items-start gap-2 border-b border-danger/30 bg-danger-soft px-5 py-3 text-xs text-danger" role="alert">
          <XCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p><strong>{run.error.code}:</strong> {run.error.message} {run.error.retryable ? "The operation can be retried." : "Manual review is required."}</p>
        </div>
      )}

      <div className="overflow-x-auto border-b border-border bg-surface-2 px-3 pt-2">
        <div role="tablist" aria-label="Scale run evidence views" aria-orientation="horizontal" className="flex min-w-max gap-1">
          {TABS.map((item, index) => {
            const Icon = item.icon;
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                ref={(element) => {
                  tabRefs.current[index] = element;
                }}
                type="button"
                role="tab"
                aria-selected={active}
                aria-controls={`scale-panel-${item.id}`}
                id={`scale-tab-${item.id}`}
                tabIndex={active ? 0 : -1}
                onClick={() => setTab(item.id)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
                className={`inline-flex min-h-11 items-center gap-2 rounded-t-md border-x border-t px-3 text-xs font-semibold ${
                  active ? "border-border bg-white text-text-strong" : "border-transparent text-text-muted hover:bg-white/60"
                }`}
              >
                <Icon className="size-3.5" aria-hidden /> {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {TABS.map((item) => {
        const active = tab === item.id;
        return (
          <div
            key={item.id}
            role="tabpanel"
            id={`scale-panel-${item.id}`}
            aria-labelledby={`scale-tab-${item.id}`}
            hidden={!active}
            tabIndex={active ? 0 : -1}
            className="p-5"
          >
            {active ? (
              <RunTabContent
                tab={item.id}
                run={run}
                onRequestExport={onRequestExport}
                exportBusy={exportBusy}
              />
            ) : null}
          </div>
        );
      })}
    </section>
  );
}

function RunTabContent({
  tab,
  run,
  onRequestExport,
  exportBusy,
}: {
  tab: RunTab;
  run: ScaleRun;
  onRequestExport: () => void;
  exportBusy: boolean;
}) {
  if (tab === "metrics") return <MetricsPanel run={run} />;
  if (tab === "evidence") return <EvidencePanel run={run} />;
  if (tab === "cost") return <CostPanel run={run} />;
  if (tab === "intelligence") return <IntelligencePanel run={run} />;
  return <ExportPanel run={run} onRequest={onRequestExport} busy={exportBusy} />;
}

function MetricsPanel({ run }: { run: ScaleRun }) {
  const metrics = [
    { label: "Generated", value: formatCount(run.progress.records_generated), icon: Database },
    { label: "Ingested", value: formatCount(run.progress.records_ingested), icon: Activity },
    { label: "Curated", value: formatCount(run.progress.records_curated), icon: PackageCheck },
    { label: "Quarantined", value: formatCount(run.progress.records_quarantined), icon: AlertCircle },
    { label: "Current rate", value: `${formatCount(run.progress.current_throughput_rps)} rec/s`, icon: Gauge },
    { label: "Peak rate", value: `${formatCount(run.progress.peak_throughput_rps)} rec/s`, icon: BarChart3 },
  ];
  return (
    <div>
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {metrics.map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-lg border border-border bg-white p-3">
            <dt className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wide text-text-subtle"><Icon className="size-3.5 text-gov-primary" aria-hidden /> {label}</dt>
            <dd className="mt-2 font-mono text-sm font-bold text-text-strong">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xs font-bold text-text-strong">Partition completion</h3>
            <span className="font-mono text-[11px] text-text-muted">{formatCount(run.progress.partitions_completed)} / {formatCount(run.progress.partitions_total)}</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-gov-primary" style={{ width: `${run.progress.partitions_total ? (run.progress.partitions_completed / run.progress.partitions_total) * 100 : 0}%` }} />
          </div>
          <p className="mt-3 text-[10.5px] text-text-subtle">{formatBytes(run.progress.bytes_written)} written across immutable and curated lake zones.</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xs font-bold text-text-strong">Quality posture</h3>
            <span className={`font-mono text-sm font-bold ${run.quality.overall_score >= 95 ? "text-success" : "text-text-subtle"}`}>
              {run.quality.overall_score ? `${run.quality.overall_score.toFixed(1)}%` : "Pending"}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <MiniMetric label="Passed" value={formatCount(run.quality.passed_records)} />
            <MiniMetric label="Failed" value={formatCount(run.quality.failed_records)} />
            <MiniMetric label="Quarantine" value={formatCount(run.quality.quarantined_records)} />
          </div>
        </div>
      </div>
      <div className="mt-5 overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[640px] text-left text-xs">
          <caption className="border-b border-border bg-surface-2 px-4 py-3 text-left text-xs font-bold text-text-strong">Rule-level quality evidence</caption>
          <thead className="bg-white text-[9px] uppercase tracking-wide text-text-subtle">
            <tr><th className="px-4 py-2">Rule</th><th className="px-4 py-2">Score</th><th className="px-4 py-2">Passed</th><th className="px-4 py-2">Failed</th></tr>
          </thead>
          <tbody className="divide-y divide-border-2">
            {run.quality.rules.map((rule) => (
              <tr key={rule.id}>
                <td className="px-4 py-3 font-semibold text-text-strong">{rule.label}</td>
                <td className="px-4 py-3 font-mono text-text-muted">{rule.score.toFixed(1)}%</td>
                <td className="px-4 py-3 font-mono text-text-muted">{formatCount(rule.passed_records)}</td>
                <td className="px-4 py-3 font-mono text-text-muted">{formatCount(rule.failed_records)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EvidencePanel({ run }: { run: ScaleRun }) {
  const rows = [
    ["Correlation ID", run.evidence.correlation_id],
    ["Audit receipt", run.evidence.audit_receipt],
    ["Manifest", run.evidence.manifest_uri],
    ["Manifest SHA-256", run.evidence.manifest_sha256],
    ["Metrics timestamp", run.evidence.metrics_recorded_at],
  ];
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(360px,1.2fr)]">
      <div>
        <h3 className="text-xs font-bold text-text-strong">Correlation chain</h3>
        <dl className="mt-3 divide-y divide-border-2 rounded-lg border border-border">
          {rows.map(([label, value]) => (
            <div key={label} className="px-4 py-3">
              <dt className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</dt>
              <dd className="mt-1 break-all font-mono text-[10.5px] leading-4 text-text-strong">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <MiniMetric label="Recovery depth" value={formatCount(run.evidence.recovery_queue_depth)} />
          <MiniMetric label="Duplicates suppressed" value={formatCount(run.evidence.duplicate_records_suppressed)} />
        </div>
      </div>
      <div>
        <h3 className="text-xs font-bold text-text-strong">Stage receipts</h3>
        <ol className="mt-3 space-y-2">
          {run.evidence.stages.map((stage, index) => (
            <li key={stage.id} className="flex items-start gap-3 rounded-lg border border-border px-3 py-2.5">
              <StageIcon status={stage.status} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold text-text-strong"><span className="mr-1.5 font-mono text-[9px] text-text-subtle">{String(index + 1).padStart(2, "0")}</span>{stage.label}</p>
                  <span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{stage.status}</span>
                </div>
                <p className="mt-1 break-all font-mono text-[9.5px] text-text-subtle">{stage.receipt ?? "Receipt pending"}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function CostPanel({ run }: { run: ScaleRun }) {
  const usedRatio = Math.min(1, run.costs.upper_bound_usd ? run.costs.accrued_usd / run.costs.upper_bound_usd : 0);
  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-3">
        <CostMetric label="Accrued estimate" value={formatCurrency(run.costs.accrued_usd)} tone="primary" />
        <CostMetric label="Expected run" value={formatCurrency(run.costs.estimated_run_usd)} />
        <CostMetric label="Hard ceiling" value={formatCurrency(run.costs.upper_bound_usd)} tone="warn" />
      </div>
      <div className="mt-4 rounded-lg border border-border p-4">
        <div className="flex items-center justify-between gap-3 text-[10px] font-bold uppercase tracking-wide text-text-subtle">
          <span>Cost ceiling utilization</span><span className="font-mono">{formatPercent(usedRatio)}</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2"><div className="h-full rounded-full bg-gold" style={{ width: `${usedRatio * 100}%` }} /></div>
        <p className="mt-3 text-[10.5px] leading-4 text-text-muted">{run.costs.disclaimer}</p>
      </div>
      <div className="mt-4 overflow-hidden rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <caption className="border-b border-border bg-surface-2 px-4 py-3 text-left text-xs font-bold text-text-strong">Modeled line items</caption>
          <tbody className="divide-y divide-border-2">
            {run.costs.line_items.map((item) => (
              <tr key={item.id}>
                <td className="px-4 py-3"><span className="font-semibold text-text-strong">{item.label}</span><span className="mt-0.5 block text-[10px] text-text-subtle">{item.basis}</span></td>
                <td className="px-4 py-3 text-right font-mono font-semibold text-text-strong">{formatCurrency(item.estimated_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[10px] text-text-subtle">Price model date {run.costs.pricing_as_of}. Incremental idle cost {formatCurrency(run.costs.incremental_idle_monthly_usd)} per month.</p>
    </div>
  );
}

function IntelligencePanel({ run }: { run: ScaleRun }) {
  return (
    <div>
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <RunMetric label="Grants analyzed" value={formatCount(run.intelligence.grants_analyzed)} />
        <RunMetric label="Topics" value={formatCount(run.intelligence.topic_count)} />
        <RunMetric label="Anomalies" value={formatCount(run.intelligence.anomalies_detected)} />
        <RunMetric label="Processing time" value={run.intelligence.processing_seconds === null ? "Pending" : formatDuration(run.intelligence.processing_seconds)} />
      </dl>
      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {run.intelligence.top_topics.map((topic) => (
          <article key={topic.label} className="rounded-lg border border-border p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-bold text-text-strong">{topic.label}</p>
              <span className="rounded-full bg-success-soft px-2 py-1 font-mono text-[9px] font-bold text-success">{formatPercent(topic.confidence)}</span>
            </div>
            <p className="mt-3 font-mono text-xl font-bold text-text-strong">{formatCount(topic.record_count)}</p>
            <p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">records</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {topic.terms.map((term) => <span key={term} className="rounded-full bg-surface-2 px-2 py-1 text-[9.5px] text-text-muted">{term}</span>)}
            </div>
          </article>
        ))}
      </div>
      {run.intelligence.model_run_id && <p className="mt-4 break-all font-mono text-[10px] text-text-subtle">Intelligence receipt {run.intelligence.model_run_id}</p>}
    </div>
  );
}

function ExportPanel({ run, onRequest, busy }: { run: ScaleRun; onRequest: () => void; busy: boolean }) {
  const receipt = run.export_receipt;
  const ready = receipt.status === "ready";
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,0.8fr)_minmax(320px,1.2fr)]">
      <div className="rounded-xl border border-gov-primary/20 bg-gov-primary-lighter p-5">
        <span className="grid size-11 place-items-center rounded-lg bg-gov-primary text-white"><FileCheck2 className="size-5" aria-hidden /></span>
        <h3 className="mt-4 text-sm font-bold text-text-strong">Governed Parquet release</h3>
        <p className="mt-2 text-xs leading-5 text-text-muted">Build an asynchronous, checksummed export from the exact curated records associated with this run.</p>
        {receipt.export_id === null ? (
          <button
            type="button"
            onClick={onRequest}
            disabled={run.status !== "completed" || busy}
            className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-md bg-action px-4 text-xs font-bold text-white hover:bg-action-hover disabled:cursor-not-allowed disabled:bg-text-subtle"
          >
            {busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <Download className="size-4" aria-hidden />}
            {busy ? "Requesting export" : "Build governed export"}
          </button>
        ) : ready && receipt.download_url ? (
          <a href={receipt.download_url} download className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-md bg-action px-4 py-3 text-xs font-bold text-white hover:bg-action-hover">
            <Download className="size-4" aria-hidden /> Download release receipt
          </a>
        ) : (
          <p className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-gov-primary"><LoaderCircle className="size-4 animate-spin" aria-hidden /> Export worker is building the release</p>
        )}
        {run.status !== "completed" && <p className="mt-3 text-[10.5px] text-text-subtle">The export interface unlocks after final run evidence is sealed.</p>}
      </div>
      <dl className="divide-y divide-border-2 overflow-hidden rounded-xl border border-border">
        <ReceiptRow label="Status" value={receipt.status} />
        <ReceiptRow label="Export ID" value={receipt.export_id ?? "Not requested"} />
        <ReceiptRow label="Format" value={receipt.format.toUpperCase()} />
        <ReceiptRow label="Rows" value={formatCount(receipt.row_count)} />
        <ReceiptRow label="Bytes" value={formatBytes(receipt.bytes)} />
        <ReceiptRow label="Manifest" value={receipt.object_uri ?? "Manifest location pending"} />
        <ReceiptRow label="SHA-256" value={receipt.sha256 ?? "Checksum pending"} />
        <ReceiptRow label="Link expires" value={receipt.expires_at ? new Date(receipt.expires_at).toLocaleString() : "Not issued"} />
      </dl>
    </div>
  );
}

function StatusPill({ status }: { status: ScaleRun["status"] }) {
  const completed = status === "completed";
  const stopped = status === "failed" || status === "cancelled";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${
      completed ? "border-emerald-300/35 bg-emerald-300/15 text-emerald-100" : stopped ? "border-white/25 bg-white/10 text-white/75" : "border-gold-light/35 bg-gold-light/15 text-gold-light"
    }`}>
      {completed ? <CheckCircle2 className="size-3" aria-hidden /> : stopped ? <XCircle className="size-3" aria-hidden /> : <LoaderCircle className="size-3 animate-spin" aria-hidden />}
      {STATUS_LABEL[status]}
    </span>
  );
}

function StageIcon({ status }: { status: ScaleRun["evidence"]["stages"][number]["status"] }) {
  if (status === "completed") return <span className="grid size-6 shrink-0 place-items-center rounded-full bg-success-soft text-success"><Check className="size-3.5" aria-hidden /></span>;
  if (status === "running") return <span className="grid size-6 shrink-0 place-items-center rounded-full bg-info-soft text-info"><LoaderCircle className="size-3.5 animate-spin" aria-hidden /></span>;
  if (status === "failed") return <span className="grid size-6 shrink-0 place-items-center rounded-full bg-danger-soft text-danger"><XCircle className="size-3.5" aria-hidden /></span>;
  return <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-text-subtle"><Clock3 className="size-3.5" aria-hidden /></span>;
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        await navigator.clipboard?.writeText(value);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1_500);
      }}
      className="inline-flex min-h-11 items-center gap-2 rounded-md border border-white/25 bg-white/10 px-3 text-xs font-semibold text-white hover:bg-white/15"
      aria-label="Copy run identifier"
    >
      {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}{copied ? "Copied" : "Copy ID"}
    </button>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md bg-surface-2 p-2"><p className="font-mono text-xs font-bold text-text-strong">{value}</p><p className="mt-1 text-[8.5px] font-bold uppercase tracking-wide text-text-subtle">{label}</p></div>;
}

function RunMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border p-4"><dt className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</dt><dd className="mt-2 font-mono text-lg font-bold text-text-strong">{value}</dd></div>;
}

function CostMetric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "primary" | "warn" }) {
  const classes = tone === "primary" ? "border-gov-primary/25 bg-gov-primary-lighter" : tone === "warn" ? "border-gold/35 bg-gold-soft" : "border-border bg-white";
  return <div className={`rounded-lg border p-4 ${classes}`}><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-2 font-mono text-xl font-bold text-text-strong">{value}</p></div>;
}

function ReceiptRow({ label, value }: { label: string; value: string }) {
  return <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 px-4 py-3"><dt className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</dt><dd className="break-all font-mono text-[10.5px] text-text-strong">{value}</dd></div>;
}

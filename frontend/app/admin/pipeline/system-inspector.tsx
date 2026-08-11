"use client";

import {
  Activity,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clipboard,
  Database,
  FileClock,
  Fingerprint,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useCompassQuery } from "@/components/dashboard/use-compass-query";
import { getSystemEvidence } from "@/lib/api";
import { subscribeScenario } from "@/lib/mock/scenario-store";
import type { EvidenceRun, SystemEvidenceResponse } from "@/lib/types";
import { PipelineView } from "./pipeline-view";
import { RUNTIME_CONFIG } from "./pipeline-data";

type Tab = "evidence" | "controls" | "architecture";

const TAB_LABELS: Record<Tab, string> = {
  evidence: "Runtime evidence",
  controls: "Control receipts",
  architecture: "Workflow definition",
};

function shortId(value: string): string {
  if (value.length <= 24) return value;
  return `${value.slice(0, 14)}...${value.slice(-7)}`;
}

function timestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

function statusTone(status: string): string {
  if (["completed", "curated", "operational", "enforced", "verified"].includes(status)) {
    return "border-success/30 bg-success-soft text-success";
  }
  if (["quarantined", "configured", "replay", "skipped"].includes(status)) {
    return "border-warn/30 bg-warn-soft text-warn";
  }
  return "border-danger/30 bg-danger-soft text-danger";
}

export function SystemInspector() {
  const query = useCompassQuery(getSystemEvidence);
  const [tab, setTab] = useState<Tab>("evidence");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [copied, setCopied] = useState(false);

  const data = query.data;
  const selectedRun = useMemo(
    () => data?.recent_runs.find((run) => run.run_id === selectedRunId) ?? data?.recent_runs[0] ?? null,
    [data, selectedRunId],
  );

  useEffect(() => {
    if (!autoRefresh) return;
    if (data?.mode === "replay") return subscribeScenario(query.reload);
    if (data?.mode !== "live") return;
    const timer = window.setInterval(query.reload, 5000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, data?.mode, query.reload]);

  const copyCorrelation = async () => {
    if (!data) return;
    await navigator.clipboard.writeText(data.correlation_id);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <section className="mt-6 overflow-hidden rounded-2xl border border-border bg-surface shadow-card">
      <div className="border-b border-border bg-gov-primary px-4 py-4 text-white sm:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 inline-flex size-10 shrink-0 items-center justify-center rounded-lg border border-white/15 bg-white/10">
              <Activity className="size-5" aria-hidden />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold !text-white">Backend evidence stream</h2>
                {data && <ModeBadge mode={data.mode} />}
              </div>
              <p className="mt-1 max-w-3xl text-sm leading-relaxed text-white/75">
                Read-only application projections with explicit source, freshness, policy decision, and trace receipt.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 text-sm font-medium text-white">
              <input
                type="checkbox"
                className="size-4 accent-gold"
                checked={autoRefresh}
                onChange={(event) => setAutoRefresh(event.target.checked)}
              />
              Auto-refresh evidence
            </label>
            <button
              type="button"
              onClick={query.reload}
              disabled={query.loading}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-white px-4 text-sm font-semibold text-gov-primary transition hover:bg-gov-primary-lighter disabled:cursor-wait disabled:opacity-70"
            >
              <RefreshCw className={`size-4 ${query.loading ? "animate-spin" : ""}`} aria-hidden />
              Refresh evidence
            </button>
          </div>
        </div>
      </div>

      <div className="border-b border-border bg-surface-2 px-3 sm:px-6">
        <div className="flex gap-1 overflow-x-auto" role="tablist" aria-label="System Inspector views">
          {(Object.keys(TAB_LABELS) as Tab[]).map((key) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`min-h-12 shrink-0 border-b-2 px-4 text-sm font-semibold transition ${
                tab === key
                  ? "border-gold text-gov-primary-dark"
                  : "border-transparent text-text-muted hover:border-border-strong hover:text-text-strong"
              }`}
            >
              {TAB_LABELS[key]}
            </button>
          ))}
        </div>
      </div>

      {query.error ? <ErrorState message={query.error} onRetry={query.reload} /> : null}
      {query.loading && !data ? <LoadingState /> : null}
      {data && tab === "evidence" ? (
        <RuntimeEvidence
          data={data}
          selectedRun={selectedRun}
          onSelectRun={setSelectedRunId}
          copied={copied}
          onCopyCorrelation={copyCorrelation}
        />
      ) : null}
      {data && tab === "controls" ? <ControlReceipts data={data} /> : null}
      {tab === "architecture" ? <ArchitectureDefinition /> : null}
    </section>
  );
}

function ModeBadge({ mode }: { mode: SystemEvidenceResponse["mode"] }) {
  const isLive = mode === "live";
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-bold uppercase tracking-[0.12em] ${
        isLive ? "border-emerald-300/40 bg-emerald-300/15 text-emerald-100" : "border-amber-200/40 bg-amber-200/15 text-amber-100"
      }`}
    >
      <span className={`size-2 rounded-full ${isLive ? "bg-emerald-300" : "bg-amber-200"}`} aria-hidden />
      {isLive ? "Live service" : "Replay fixture"}
    </span>
  );
}

function RuntimeEvidence({
  data,
  selectedRun,
  onSelectRun,
  copied,
  onCopyCorrelation,
}: {
  data: SystemEvidenceResponse;
  selectedRun: EvidenceRun | null;
  onSelectRun: (runId: string) => void;
  copied: boolean;
  onCopyCorrelation: () => void;
}) {
  const metrics = [
    ["Curated records", data.metrics.curated_records.toLocaleString()],
    ["Curated batches", data.metrics.curated_batches.toLocaleString()],
    ["Open anomalies", data.metrics.open_anomalies.toLocaleString()],
    ["Pending approvals", data.metrics.pending_approvals.toLocaleString()],
    ["Audit receipts", data.metrics.audit_receipts.toLocaleString()],
  ];

  return (
    <div className="p-4 sm:p-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {metrics.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-border bg-surface-2 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-text-subtle">{label}</p>
            <p className="mt-2 font-mono text-2xl font-semibold text-text-strong">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 2xl:grid-cols-[minmax(240px,0.8fr)_minmax(420px,1.55fr)_minmax(280px,0.9fr)]">
        <section className="rounded-xl border border-border bg-surface" aria-labelledby="recent-runs-title">
          <div className="border-b border-border px-4 py-3">
            <h3 id="recent-runs-title" className="flex items-center gap-2 text-sm font-semibold text-text-strong">
              <Workflow className="size-4 text-gov-primary" aria-hidden /> Recent workflow runs
            </h3>
            <p className="mt-1 text-xs text-text-muted">Select a run to inspect its receipts.</p>
          </div>
          <div className="max-h-[430px] overflow-y-auto p-2">
            {data.recent_runs.length ? (
              data.recent_runs.map((run) => {
                const active = selectedRun?.run_id === run.run_id;
                return (
                  <button
                    key={run.run_id}
                    type="button"
                    onClick={() => onSelectRun(run.run_id)}
                    aria-pressed={active}
                    className={`mb-2 flex min-h-20 w-full items-center gap-3 rounded-lg border p-3 text-left transition last:mb-0 ${
                      active
                        ? "border-gov-primary bg-gov-primary-lighter shadow-[inset_3px_0_0_var(--color-gold)]"
                        : "border-border bg-surface hover:bg-surface-2"
                    }`}
                  >
                    <span className={`size-2.5 shrink-0 rounded-full ${run.outcome === "curated" ? "bg-success" : "bg-warn"}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-mono text-xs font-semibold text-text-strong">{shortId(run.run_id)}</span>
                      <span className="mt-1 block text-xs text-text-muted">
                        {timestamp(run.completed_at)} | {run.quality_score.toFixed(1)} quality
                      </span>
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-text-subtle" aria-hidden />
                  </button>
                );
              })
            ) : (
              <p className="p-4 text-sm text-text-muted">No completed quality runs are available yet.</p>
            )}
          </div>
        </section>

        <RunTrace run={selectedRun} />

        <aside className="space-y-4">
          <section className="rounded-xl border border-border bg-surface p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-text-strong">
              <Fingerprint className="size-4 text-gov-primary" aria-hidden /> Request receipt
            </h3>
            <dl className="mt-4 space-y-3 text-sm">
              <ReceiptRow label="Route" value={`${data.request.method} ${data.request.route}`} mono />
              <ReceiptRow label="Status" value={`${data.request.status} | ${data.request.latency_ms} ms`} mono />
              <ReceiptRow label="Revision" value={data.deploy_revision} mono />
              <ReceiptRow label="Generated" value={timestamp(data.generated_at)} />
            </dl>
            <button
              type="button"
              onClick={onCopyCorrelation}
              className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface-2 px-3 text-xs font-semibold text-text-strong transition hover:border-gov-primary"
            >
              {copied ? <Check className="size-4 text-success" aria-hidden /> : <Clipboard className="size-4" aria-hidden />}
              {copied ? "Copied trace ID" : `Copy ${shortId(data.correlation_id)}`}
            </button>
          </section>

          <section className="rounded-xl border border-border bg-gov-primary-lighter p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gov-primary-dark">
              <ShieldCheck className="size-4" aria-hidden /> Policy decision
            </h3>
            <dl className="mt-3 space-y-2 text-xs text-text-muted">
              <ReceiptRow label="Role" value={data.identity_decision.role} />
              <ReceiptRow label="Scope" value={data.identity_decision.scope} />
              <ReceiptRow label="Row policy" value={data.identity_decision.row_policy} />
              <ReceiptRow label="Column policy" value={data.identity_decision.column_policy} />
            </dl>
          </section>

          <section className="rounded-xl border border-border bg-surface p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-text-strong">
              <Database className="size-4 text-gov-primary" aria-hidden /> Latest analytics receipt
            </h3>
            {data.latest_model_run ? (
              <div className="mt-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-mono text-xs font-semibold text-text-strong">
                    {shortId(data.latest_model_run.run_id)}
                  </p>
                  <span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-wide ${statusTone(data.latest_model_run.status)}`}>
                    {data.latest_model_run.status}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-muted">
                  {data.latest_model_run.kind} | {timestamp(data.latest_model_run.created_at)}
                </p>
                {Object.keys(data.latest_model_run.metrics).length ? (
                  <dl className="mt-3 grid grid-cols-2 gap-2">
                    {Object.entries(data.latest_model_run.metrics).map(([key, value]) => (
                      <div key={key} className="rounded border border-border bg-surface-2 p-2">
                        <dt className="text-[9px] font-semibold uppercase tracking-wide text-text-subtle">
                          {key.replaceAll("_", " ")}
                        </dt>
                        <dd className="mt-1 font-mono text-xs font-semibold text-text-strong">
                          {String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="mt-3 text-xs text-text-muted">No allowlisted model metrics are available.</p>
                )}
              </div>
            ) : (
              <p className="mt-3 text-xs text-text-muted">Run analytics to create a model receipt.</p>
            )}
          </section>
        </aside>
      </div>

      <p className="mt-4 rounded-lg border border-border bg-surface-2 px-4 py-3 text-xs leading-relaxed text-text-muted">
        {data.disclosure}
      </p>
    </div>
  );
}

function RunTrace({ run }: { run: EvidenceRun | null }) {
  if (!run) {
    return (
      <section className="flex min-h-72 items-center justify-center rounded-xl border border-dashed border-border p-8 text-center text-sm text-text-muted">
        Run an intake scenario to populate this evidence trace.
      </section>
    );
  }
  return (
    <section className="rounded-xl border border-border bg-surface" aria-labelledby="trace-title">
      <div className="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 id="trace-title" className="text-sm font-semibold text-text-strong">Decision trace</h3>
          <p className="mt-1 font-mono text-xs text-text-muted">{shortId(run.batch_id)}</p>
        </div>
        <span className={`inline-flex min-h-8 w-fit items-center rounded-full border px-3 text-xs font-bold capitalize ${statusTone(run.outcome)}`}>
          {run.outcome} | {run.curated_rows} rows
        </span>
      </div>
      <ol className="p-4 sm:p-5">
        {run.stages.map((stage, index) => (
          <li key={stage.id} className="relative flex gap-3 pb-5 last:pb-0">
            {index < run.stages.length - 1 ? (
              <span className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-border-strong" aria-hidden />
            ) : null}
            <span className={`relative z-10 inline-flex size-8 shrink-0 items-center justify-center rounded-full border ${statusTone(stage.status)}`}>
              {stage.status === "completed" ? <CheckCircle2 className="size-4" aria-hidden /> : <CircleDot className="size-4" aria-hidden />}
            </span>
            <div className="min-w-0 pt-0.5">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-text-strong">{stage.label}</p>
                <span className="font-mono text-[11px] uppercase tracking-wide text-text-subtle">{stage.status}</span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-text-muted">{stage.receipt}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function ControlReceipts({ data }: { data: SystemEvidenceResponse }) {
  return (
    <div className="p-4 sm:p-6">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.controls.map((control) => (
          <article key={control.id} className="rounded-xl border border-border bg-surface p-4 shadow-card">
            <div className="flex items-start justify-between gap-3">
              <ShieldCheck className="size-5 shrink-0 text-gov-primary" aria-hidden />
              <span className={`rounded-full border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${statusTone(control.status)}`}>
                {control.status}
              </span>
            </div>
            <h3 className="mt-4 text-sm font-semibold text-text-strong">{control.label}</h3>
            <p className="mt-2 text-xs leading-relaxed text-text-muted">{control.evidence}</p>
          </article>
        ))}
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <section className="rounded-xl border border-border bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text-strong">
            <ServerCog className="size-4 text-gov-primary" aria-hidden /> Service posture
          </h3>
          <ul className="mt-3 divide-y divide-border-2">
            {data.services.map((service) => (
              <li key={service.id} className="flex min-h-16 items-center gap-3 py-3">
                <span className={`size-2.5 shrink-0 rounded-full ${service.status === "operational" ? "bg-success" : "bg-warn"}`} />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-text-strong">{service.label}</span>
                  <span className="mt-0.5 block text-xs text-text-muted">{service.purpose}</span>
                </span>
                <span className="text-xs font-semibold capitalize text-text-subtle">{service.status}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-border bg-surface p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text-strong">
            <FileClock className="size-4 text-gov-primary" aria-hidden /> Sanitized audit readback
          </h3>
          <div className="mt-3 space-y-2">
            {data.recent_audit.length ? data.recent_audit.map((event) => (
              <article key={event.event_id} className="rounded-lg border border-border bg-surface-2 p-3">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <p className="font-mono text-xs font-semibold text-text-strong">{event.action}</p>
                  <time className="text-xs text-text-subtle">{timestamp(event.at)}</time>
                </div>
                <p className="mt-1 text-xs text-text-muted">{event.category}</p>
                {Object.keys(event.detail).length ? (
                  <dl className="mt-2 flex flex-wrap gap-2">
                    {Object.entries(event.detail).map(([key, value]) => (
                      <div key={key} className="rounded border border-border bg-surface px-2 py-1 text-[11px]">
                        <dt className="inline font-semibold text-text-subtle">{key}: </dt>
                        <dd className="inline font-mono text-text-strong">{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
              </article>
            )) : <p className="py-6 text-center text-sm text-text-muted">No audit receipts are available yet.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}

function ArchitectureDefinition() {
  return (
    <div className="p-4 sm:p-6">
      <div className="rounded-xl border border-info/25 bg-info-soft p-4 text-sm leading-relaxed text-text-muted">
        <p className="flex items-center gap-2 font-semibold text-text-strong">
          <Database className="size-4 text-info" aria-hidden /> Definition view
        </p>
        <p className="mt-1">
          This tab explains the versioned workflow definition. Use Runtime evidence for proof that a specific run occurred.
        </p>
      </div>
      <PipelineView />
      <section className="mt-5 rounded-xl border border-border bg-surface p-4">
        <h3 className="text-sm font-semibold text-text-strong">Runtime policy levers</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {RUNTIME_CONFIG.map((item) => (
            <article key={item.key} className="rounded-lg border border-border bg-surface-2 p-3">
              <code className="text-xs font-semibold text-gov-primary-dark">{item.key}</code>
              <p className="mt-2 font-mono text-xs text-text-strong">{item.value}</p>
              <p className="mt-2 text-xs leading-relaxed text-text-muted">{item.note}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function ReceiptRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-text-subtle">{label}</dt>
      <dd className={`max-w-[65%] break-words text-right text-text-strong ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="grid gap-4 p-6 lg:grid-cols-3" role="status" aria-label="Loading backend evidence">
      {[0, 1, 2].map((item) => <div key={item} className="skeleton h-64 rounded-xl" />)}
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="m-4 flex flex-col gap-3 rounded-xl border border-danger bg-danger-soft p-4 sm:m-6 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-semibold text-danger">Evidence stream unavailable</p>
        <p className="mt-1 text-xs text-text-muted">{message}</p>
      </div>
      <button type="button" onClick={onRetry} className="min-h-11 rounded-lg bg-gov-primary px-4 text-sm font-semibold text-white">
        Retry
      </button>
    </div>
  );
}

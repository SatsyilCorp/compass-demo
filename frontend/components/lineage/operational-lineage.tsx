"use client";

import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  CircleDot,
  Clock3,
  Database,
  Fingerprint,
  FileInput,
  Gauge,
  GitCommitHorizontal,
  Loader2,
  PackageCheck,
  RefreshCcw,
  Route,
  ServerCog,
  ShieldAlert,
  TimerReset,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getOperationsLineage,
  getOperationsSummary,
  setAuthContext,
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { subscribeLiveDemoStreamTick } from "@/lib/live-demo-stream-events";
import { EvidenceClassBadge } from "@/components/evidence/evidence-class-badge";
import type {
  OperationsLineageResponse,
  OperationsLineageStage,
  OperationsResourceRef,
  OperationsRunStatus,
  OperationsRunSummary,
  OperationsSummaryResponse,
} from "@/lib/types";
import {
  isAttentionStatus,
  lineageProgress,
  orderedStages,
  shortDigest,
  TERMINAL_RUN_STATUSES,
} from "./model";

const SUMMARY_POLL_MS = 8_000;
const ACTIVE_LINEAGE_POLL_MS = 2_000;
const TERMINAL_LINEAGE_POLL_MS = 10_000;

const RUN_STATUS_STYLE: Record<OperationsRunStatus, string> = {
  queued: "border-border bg-surface-2 text-text-muted",
  running: "border-info/30 bg-info-soft text-info",
  completed: "border-success/30 bg-success-soft text-success",
  quarantined: "border-warn/35 bg-warn-soft text-warn",
  failed: "border-danger/30 bg-danger-soft text-danger",
  expired: "border-danger/30 bg-danger-soft text-danger",
  cancelled: "border-border bg-surface-2 text-text-muted",
};

const STAGE_STYLE: Record<OperationsLineageStage["status"], {
  card: string;
  rail: string;
  icon: string;
}> = {
  pending: { card: "border-border bg-white/65", rail: "bg-border", icon: "bg-surface-3 text-text-subtle" },
  running: { card: "border-info bg-info-soft/45 shadow-card", rail: "bg-info", icon: "bg-info text-white" },
  completed: { card: "border-success/35 bg-success-soft/35", rail: "bg-success", icon: "bg-success text-white" },
  quarantined: { card: "border-warn/40 bg-warn-soft", rail: "bg-warn", icon: "bg-warn text-white" },
  failed: { card: "border-danger/40 bg-danger-soft", rail: "bg-danger", icon: "bg-danger text-white" },
  skipped: { card: "border-border bg-surface-2", rail: "bg-text-subtle", icon: "bg-surface-3 text-text-muted" },
};

export function OperationalLineage() {
  const auth = useAppAuth();
  const [summary, setSummary] = useState<OperationsSummaryResponse | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [lineage, setLineage] = useState<OperationsLineageResponse | null>(null);
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [lineageLoading, setLineageLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [lineageError, setLineageError] = useState<string | null>(null);

  const publishAuth = useCallback(() => {
    setAuthContext({ bearerToken: auth.idToken, role: auth.role, orgUnit: auth.orgUnit });
  }, [auth.idToken, auth.orgUnit, auth.role]);

  const loadSummary = useCallback(async (initial = false, followLatest = false) => {
    if (auth.isLoading) return;
    publishAuth();
    if (initial) setSummaryLoading(true);
    try {
      const response = await getOperationsSummary();
      setSummary(response);
      setSummaryError(null);
      setSelectedRunId((current) => {
        if (followLatest) return response.runs[0]?.run_id ?? current;
        if (current && response.runs.some((run) => run.run_id === current)) return current;
        const requested = requestedRunId();
        if (requested && response.runs.some((run) => run.run_id === requested)) return requested;
        return response.runs[0]?.run_id ?? null;
      });
    } catch (cause) {
      setSummaryError(cause instanceof Error ? cause.message : "The operations summary is unavailable.");
    } finally {
      if (initial) setSummaryLoading(false);
    }
  }, [auth.isLoading, publishAuth]);

  useEffect(() => {
    if (auth.isLoading) return;
    void loadSummary(true);
    const timer = window.setInterval(() => void loadSummary(false), SUMMARY_POLL_MS);
    const unsubscribe = subscribeLiveDemoStreamTick(() => void loadSummary(false, true));
    return () => {
      window.clearInterval(timer);
      unsubscribe();
    };
  }, [auth.isLoading, loadSummary]);

  useEffect(() => {
    if (!selectedRunId || auth.isLoading) {
      setLineage(null);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    setLineageLoading(true);
    setLineage(null);
    setSelectedStageId(null);

    const poll = async () => {
      publishAuth();
      try {
        const response = await getOperationsLineage(selectedRunId);
        if (cancelled) return;
        setLineage(response);
        setLineageError(null);
        setLineageLoading(false);
        setSelectedStageId((current) => current && response.stages.some((stage) => stage.stage_id === current)
          ? current
          : response.stages.find((stage) => stage.status === "running")?.stage_id
            ?? orderedStages(response.stages).at(-1)?.stage_id
            ?? null);
        const delay = TERMINAL_RUN_STATUSES.has(response.run.status)
          ? TERMINAL_LINEAGE_POLL_MS
          : ACTIVE_LINEAGE_POLL_MS;
        timer = setTimeout(() => void poll(), delay);
      } catch (cause) {
        if (cancelled) return;
        setLineageError(cause instanceof Error ? cause.message : "Lineage evidence is unavailable.");
        setLineageLoading(false);
        timer = setTimeout(() => void poll(), SUMMARY_POLL_MS);
      }
    };
    void poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [auth.isLoading, publishAuth, selectedRunId]);

  const stages = useMemo(() => orderedStages(lineage?.stages ?? []), [lineage?.stages]);
  const selectedStage = stages.find((stage) => stage.stage_id === selectedStageId) ?? stages.at(-1) ?? null;
  const progress = lineageProgress(stages);

  const selectRun = (runId: string) => {
    setSelectedRunId(runId);
    const url = new URL(window.location.href);
    url.searchParams.set("run", runId);
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  };

  return (
    <div className="mt-6 space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card">
        <div className="grid gap-5 px-5 py-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)] lg:px-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-gold-light">Unified operations</span>
              {summary ? <ModeBadge mode={summary.mode} /> : null}
            </div>
            <h2 className="mt-3 text-xl font-bold">One run, every authoritative receipt</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">Follow source intake, quality, transformation, model execution, publication, and consumption without inferring progress from a browser timer. Stage animation changes only when the protected operations API reports a new state.</p>
          </div>
          <div className="rounded-lg border border-white/15 bg-white/[0.07] p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-light">Evidence rule</p>
            <p className="mt-2 text-xs leading-5 text-white/70">Every stage retains a run identifier, source digest, input and output digest, status, timing, count, actor, source revision, and receipt locator when available.</p>
          </div>
        </div>
        <div className="grid border-t border-white/12 bg-black/10 sm:grid-cols-4">
          <HeroMetric label="Retained runs" value={summary?.counts.runs_total ?? 0} />
          <HeroMetric label="Active now" value={summary?.counts.runs_active ?? 0} />
          <HeroMetric label="Need attention" value={summary?.counts.runs_attention ?? 0} />
          <HeroMetric label="Unread signals" value={summary?.counts.signals_unread ?? 0} />
        </div>
      </section>

      {summaryError ? <ErrorNotice message={summaryError} stale={Boolean(summary)} onRetry={() => void loadSummary(false)} /> : null}

      <section className="grid overflow-hidden rounded-xl border border-border bg-surface shadow-card xl:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="border-b border-border bg-white xl:border-b-0 xl:border-r" aria-label="Operations runs">
          <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-4">
            <div><p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">Run index</p><h3 className="mt-1 text-sm font-bold text-text-strong">Recent evidence runs</h3></div>
            <button type="button" onClick={() => void loadSummary(false)} aria-label="Refresh runs" className="grid size-10 place-items-center rounded-md border border-border text-text-muted hover:bg-surface-2"><RefreshCcw className="size-4" aria-hidden /></button>
          </div>
          <div className="max-h-[680px] overflow-y-auto p-3">
            {summaryLoading && !summary ? <LoadingBlock label="Loading operations runs" /> : summary?.runs.length ? (
              <div className="space-y-2">
                {summary.runs.map((run) => <RunButton key={run.run_id} run={run} active={run.run_id === selectedRunId} onSelect={selectRun} />)}
              </div>
            ) : <EmptyBlock title="No retained runs" detail="Ingestion, acquisition, model, and release runs will appear here." />}
          </div>
        </aside>

        <div className="min-w-0">
          {lineageLoading && !lineage ? <div className="grid min-h-[520px] place-items-center"><LoadingBlock label="Loading run lineage" /></div> : lineage ? (
            <div aria-live="polite" data-run-status={lineage.run.status}>
              <RunHeader lineage={lineage} progress={progress} />
              {lineageError ? <div className="px-5 pt-4"><ErrorNotice message={lineageError} stale onRetry={() => selectRun(lineage.run.run_id)} /></div> : null}
              <div className="p-4 sm:p-5">
                <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wide text-gold-ink"><Route className="size-3.5" aria-hidden /> Directed stage evidence</h3>
                <p className="mt-1 text-[10.5px] leading-5 text-text-muted">Select a stage to inspect its hashes, counts, timing, actor, implementation revision, and retained receipt.</p>
                <div className="mt-4 overflow-x-auto pb-2">
                  <div className="flex min-w-max flex-col gap-2 md:flex-row md:items-stretch" role="list" aria-label="Directed lineage stages">
                    {stages.map((stage, index) => (
                      <div key={stage.stage_id} className="flex flex-col items-center gap-2 md:flex-row" role="listitem">
                        {index > 0 ? <ArrowRight className="size-5 shrink-0 rotate-90 text-text-subtle md:rotate-0" aria-label={edgeLabel(lineage, stages[index - 1].stage_id, stage.stage_id)} /> : null}
                        <StageCard stage={stage} selected={selectedStage?.stage_id === stage.stage_id} onSelect={setSelectedStageId} />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-5 grid gap-4 2xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
                  {selectedStage ? <StageInspector stage={selectedStage} /> : <EmptyBlock title="No stage evidence" detail="The run has not published a stage projection yet." />}
                  <div className="space-y-3">
                    <ResourceCard title="Source" icon={FileInput} resource={lineage.run.source} />
                    <ResourceCard title="Model" icon={ServerCog} resource={lineage.run.model} empty="No model participates in this run." />
                    <ResourceCard title="Consumer" icon={PackageCheck} resource={lineage.run.consumer} empty="No downstream consumer has been published." />
                  </div>
                </div>
              </div>
              <div className="border-t border-border bg-white px-5 py-3 text-[9.5px] leading-4 text-text-subtle">{lineage.disclosure}</div>
            </div>
          ) : lineageError ? <div className="p-5"><ErrorNotice message={lineageError} stale={false} onRetry={() => selectedRunId && selectRun(selectedRunId)} /></div> : <div className="grid min-h-[520px] place-items-center"><EmptyBlock title="Select a run" detail="Choose a retained run to view its directed evidence path." /></div>}
        </div>
      </section>

      {summary?.source_watermarks.length ? <SourceWatermarks summary={summary} onSelect={selectRun} /> : null}
    </div>
  );
}

function RunButton({ run, active, onSelect }: { run: OperationsRunSummary; active: boolean; onSelect: (id: string) => void }) {
  return (
    <button type="button" onClick={() => onSelect(run.run_id)} aria-pressed={active} className={`w-full rounded-lg border p-3 text-left transition-colors ${active ? "border-gov-primary bg-gov-primary-lighter shadow-soft" : "border-border bg-white hover:border-gov-primary/30 hover:bg-surface-2"}`}>
      <div className="flex items-start justify-between gap-2"><span className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">{humanize(run.run_kind)}</span><StatusChip status={run.status} /></div>
      <p className="mt-2 text-xs font-bold leading-5 text-text-strong">{run.label}</p>
      <div className="mt-2"><EvidenceClassBadge evidenceClass={run.evidence_class} compact /></div>
      <p className="mt-1 truncate font-mono text-[9px] text-text-subtle">{run.run_id}</p>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/80 pt-2 text-[9px] text-text-muted"><span>{run.completed_stages}/{run.stage_count} stages</span><span>{formatTimestamp(run.updated_at)}</span></div>
    </button>
  );
}

function RunHeader({ lineage, progress }: { lineage: OperationsLineageResponse; progress: ReturnType<typeof lineageProgress> }) {
  const run = lineage.run;
  return (
    <div className="border-b border-border bg-white p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><StatusChip status={run.status} /><ModeBadge mode={lineage.mode} /><EvidenceClassBadge evidenceClass={run.evidence_class} /><span className="font-mono text-[9px] text-text-subtle">{run.run_id}</span></div><h2 className="mt-2 text-lg font-bold text-text-strong">{run.label}</h2><p className="mt-1 text-xs text-text-muted">Current stage: <span className="font-semibold text-text-strong">{humanize(run.current_stage)}</span> | Updated {formatTimestamp(run.updated_at)}</p></div>
        <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[440px]">
          <SmallMetric label="Input" value={formatCount(run.counts.input_records)} />
          <SmallMetric label="Output" value={formatCount(run.counts.output_records)} />
          <SmallMetric label="Quarantine" value={formatCount(run.counts.quarantined_records)} alert={(run.counts.quarantined_records ?? 0) > 0} />
          <SmallMetric label="Artifacts" value={formatCount(run.counts.artifacts)} />
        </div>
      </div>
      <div className="mt-4">
        <div className="flex items-center justify-between text-[9px] font-bold uppercase tracking-wide text-text-subtle"><span>{progress.complete} of {progress.total} terminal stages</span><span>{progress.percentage}%</span></div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3"><div className={`h-full rounded-full transition-[width] duration-700 ${isAttentionStatus(run.status) ? "bg-warn" : "bg-success"}`} style={{ width: `${progress.percentage}%` }} /></div>
      </div>
    </div>
  );
}

function StageCard({ stage, selected, onSelect }: { stage: OperationsLineageStage; selected: boolean; onSelect: (id: string) => void }) {
  const style = STAGE_STYLE[stage.status];
  return (
    <button type="button" onClick={() => onSelect(stage.stage_id)} aria-pressed={selected} data-stage-state={stage.status} className={`relative w-[218px] overflow-hidden rounded-xl border p-3 text-left transition-all ${style.card} ${selected ? "ring-4 ring-gold-light/45" : ""}`}>
      <span className={`absolute inset-y-0 left-0 w-1 ${style.rail}`} aria-hidden />
      <div className="flex items-start gap-2.5">
        <span className={`grid size-8 shrink-0 place-items-center rounded-md ${style.icon}`}>{stage.status === "running" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : stage.status === "completed" ? <CheckCircle2 className="size-4" aria-hidden /> : stage.status === "failed" || stage.status === "quarantined" ? <AlertTriangle className="size-4" aria-hidden /> : <CircleDot className="size-4" aria-hidden />}</span>
        <span className="min-w-0"><span className="block text-[8px] font-bold uppercase tracking-wide text-text-subtle">Stage {stage.sequence} | {stage.status}</span><span className="mt-1 block text-[11px] font-bold leading-4 text-text-strong">{stage.label}</span><span className="mt-1 block text-[9px] leading-4 text-text-muted">{stage.system}</span></span>
      </div>
      <div className="mt-2"><EvidenceClassBadge evidenceClass={stage.evidence_class} compact /></div>
      <div className="mt-3 border-t border-current/10 pt-2"><p className="truncate font-mono text-[8px] text-text-subtle" title={stage.output_sha256 ?? stage.input_sha256 ?? undefined}>{shortDigest(stage.output_sha256 ?? stage.input_sha256, 8)}</p><p className="mt-1 text-[8.5px] text-text-muted">{stage.record_count === null ? "Count pending" : `${stage.record_count.toLocaleString("en-US")} records`} | attempt {stage.attempt}</p></div>
    </button>
  );
}

function StageInspector({ stage }: { stage: OperationsLineageStage }) {
  const fields: { label: string; value: string; icon: typeof Clock3; mono?: boolean }[] = [
    { label: "Status", value: stage.status, icon: Gauge },
    { label: "Last receipt", value: formatTimestamp(stage.updated_at), icon: Clock3 },
    { label: "Started", value: formatTimestamp(stage.started_at), icon: Clock3 },
    { label: "Completed", value: formatTimestamp(stage.completed_at), icon: CheckCircle2 },
    { label: "Duration", value: stage.duration_ms === null ? "Not recorded" : `${stage.duration_ms.toLocaleString("en-US")} ms`, icon: TimerReset },
    { label: "Records", value: stage.record_count === null ? "Not recorded" : stage.record_count.toLocaleString("en-US"), icon: Database },
    { label: "Artifacts", value: stage.artifact_count === null ? "Not recorded" : stage.artifact_count.toLocaleString("en-US"), icon: Boxes },
    { label: "Actor", value: stage.actor ?? "System", icon: ShieldAlert },
    { label: "Source revision", value: stage.source_revision ?? "Not recorded", icon: GitCommitHorizontal, mono: true },
  ];
  return (
    <article className="overflow-hidden rounded-xl border border-border bg-white">
      <div className="border-b border-border bg-surface-2 px-4 py-4"><div className="flex flex-wrap items-center gap-2"><p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">Selected stage receipt</p><EvidenceClassBadge evidenceClass={stage.evidence_class} compact /></div><h3 className="mt-1 text-sm font-bold text-text-strong">{stage.label}</h3><p className="mt-1 text-[10.5px] leading-5 text-text-muted">{stage.detail}</p></div>
      <div className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-4">{fields.map(({ label, value, icon: Icon, mono }) => <div key={label} className="bg-white p-3"><p className="flex items-center gap-1.5 text-[8px] font-bold uppercase tracking-wide text-text-subtle"><Icon className="size-3" aria-hidden /> {label}</p><p className={`mt-1 break-all text-[10px] text-text-strong ${mono ? "font-mono" : "font-semibold"}`}>{value}</p></div>)}</div>
      <div className="space-y-2 border-t border-border p-4">
        <DigestRow label="Source SHA-256" value={stage.source_sha256} />
        <DigestRow label="Input SHA-256" value={stage.input_sha256} />
        <DigestRow label="Output SHA-256" value={stage.output_sha256} />
        <DigestRow label="Receipt" value={stage.receipt} />
        {stage.failure_code ? <div className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft p-3 text-[10px] text-danger"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden /><span>Failure code: <code>{stage.failure_code}</code></span></div> : null}
      </div>
    </article>
  );
}

function ResourceCard({ title, icon: Icon, resource, empty }: { title: string; icon: typeof FileInput; resource: OperationsResourceRef | null; empty?: string }) {
  return <article className="rounded-xl border border-border bg-white p-4"><div className="flex items-center gap-2"><span className="grid size-8 place-items-center rounded-md bg-gov-primary-lighter text-gov-primary"><Icon className="size-4" aria-hidden /></span><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{title}</p></div>{resource ? <div className="mt-3"><p className="text-xs font-bold text-text-strong">{resource.label}</p><p className="mt-1 text-[9px] text-text-muted">{humanize(resource.kind)} | {resource.version ?? "unversioned"}</p>{resource.sha256 ? <p className="mt-2 truncate font-mono text-[8.5px] text-text-subtle" title={resource.sha256}>{shortDigest(resource.sha256)}</p> : null}{resource.uri ? <p className="mt-1 truncate font-mono text-[8.5px] text-text-subtle" title={resource.uri}>{resource.uri}</p> : null}</div> : <p className="mt-3 text-[10px] leading-5 text-text-muted">{empty}</p>}</article>;
}

function SourceWatermarks({ summary, onSelect }: { summary: OperationsSummaryResponse; onSelect: (runId: string) => void }) {
  return <section className="rounded-xl border border-border bg-surface p-5 shadow-card"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">External source continuity</p><h2 className="mt-1 text-lg font-bold text-text-strong">Acquisition watermarks and change sets</h2><p className="mt-1 text-xs leading-5 text-text-muted">This is the scheduled source acquisition state. It is separate from the faster internal activity ticker.</p></div><div className="mt-4 grid gap-3 lg:grid-cols-2">{summary.source_watermarks.map((source) => <article key={source.source_id} className="rounded-lg border border-border bg-white p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-bold text-text-strong">{source.label}</p><p className="mt-1 font-mono text-[9px] text-text-subtle">Watermark {source.watermark ?? "not established"}</p></div><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${source.status === "current" ? "border-success/30 bg-success-soft text-success" : source.status === "running" ? "border-info/30 bg-info-soft text-info" : "border-danger/30 bg-danger-soft text-danger"}`}>{source.status}</span></div><div className="mt-4 grid grid-cols-4 gap-2"><SmallMetric label="Added" value={source.added_records.toLocaleString("en-US")} /><SmallMetric label="Changed" value={source.changed_records.toLocaleString("en-US")} /><SmallMetric label="Same" value={source.unchanged_records.toLocaleString("en-US")} /><SmallMetric label="Not in page" value={source.not_observed_records.toLocaleString("en-US")} /></div>{source.run_id ? <button type="button" onClick={() => onSelect(source.run_id!)} className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 px-3 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter"><Route className="size-3.5" aria-hidden /> Open acquisition lineage</button> : null}</article>)}</div></section>;
}

function DigestRow({ label, value }: { label: string; value: string | null }) {
  return <div className="grid gap-1 rounded-md border border-border bg-surface-2 p-3 sm:grid-cols-[130px_minmax(0,1fr)] sm:items-center"><p className="flex items-center gap-1.5 text-[8px] font-bold uppercase tracking-wide text-text-subtle"><Fingerprint className="size-3" aria-hidden /> {label}</p><code className="break-all text-[9px] text-text-muted">{value ?? "Not recorded"}</code></div>;
}

function StatusChip({ status }: { status: OperationsRunStatus }) {
  return <span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase tracking-wide ${RUN_STATUS_STYLE[status]}`}>{status}</span>;
}

function ModeBadge({ mode }: { mode: OperationsSummaryResponse["mode"] }) {
  return <span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase tracking-wide ${mode === "live" ? "border-success/30 bg-success/10 text-emerald-100" : "border-warn/35 bg-warn/10 text-amber-100"}`}>{mode === "live" ? "Deployed AWS adapter" : "Replay adapter"}</span>;
}

function HeroMetric({ label, value }: { label: string; value: number }) {
  return <div className="border-white/10 px-5 py-4 sm:border-r last:border-r-0"><p className="font-mono text-xl font-bold text-white">{value.toLocaleString("en-US")}</p><p className="mt-1 text-[9px] font-bold uppercase tracking-wide text-white/55">{label}</p></div>;
}

function SmallMetric({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return <div className="rounded-md border border-border bg-surface-2 px-2.5 py-2"><p className="text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className={`mt-1 font-mono text-xs font-bold ${alert ? "text-warn" : "text-text-strong"}`}>{value}</p></div>;
}

function LoadingBlock({ label }: { label: string }) {
  return <div className="p-8 text-center text-text-muted"><Loader2 className="mx-auto size-6 animate-spin text-gov-primary" aria-hidden /><p className="mt-3 text-xs">{label}</p></div>;
}

function EmptyBlock({ title, detail }: { title: string; detail: string }) {
  return <div className="rounded-xl border border-dashed border-border bg-white p-8 text-center"><Route className="mx-auto size-7 text-text-subtle" aria-hidden /><p className="mt-3 text-sm font-bold text-text-strong">{title}</p><p className="mt-1 text-xs text-text-muted">{detail}</p></div>;
}

function ErrorNotice({ message, stale, onRetry }: { message: string; stale: boolean; onRetry: () => void }) {
  return <div role="alert" className="flex flex-col gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-danger sm:flex-row sm:items-center"><AlertTriangle className="size-4 shrink-0" aria-hidden /><p className="min-w-0 flex-1 text-xs leading-5">{message}{stale ? " The last good evidence remains visible." : ""}</p><button type="button" onClick={onRetry} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-danger/30 bg-white px-3 text-[10px] font-bold"><RefreshCcw className="size-3" aria-hidden /> Retry</button></div>;
}

function requestedRunId(): string | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("run")?.trim();
  return value || null;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function formatCount(value: number | null): string {
  return value === null ? "Not recorded" : value.toLocaleString("en-US");
}

function edgeLabel(lineage: OperationsLineageResponse, from: string, to: string): string {
  return lineage.edges.find((edge) => edge.from_stage === from && edge.to_stage === to)?.label ?? "directed transition";
}

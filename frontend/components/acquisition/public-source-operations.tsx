"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { SINGLE_LIVE_MODE } from "@/lib/evidence-mode";
import {
  AlertCircle,
  ArrowRight,
  BellRing,
  CheckCircle2,
  Clock3,
  Cloud,
  Database,
  ExternalLink,
  FileSearch,
  Loader2,
  RadioTower,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import {
  postPublicAcquisitionRunApi,
  postPublicSourceRunApi,
  type PublicAcquisitionRecord,
  type PublicSourceHealth,
} from "@/lib/api";
import { LiveEvidenceStatus } from "@/components/public-intelligence/live-evidence-status";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";

type Profile = "quick" | "standard" | "deep";

const PROFILE_LABELS: Record<Profile, string> = {
  quick: "Quick bounded page",
  standard: "Standard bounded page",
  deep: "Deep bounded page",
};

type RunSummary = {
  successful: number;
  failed: number;
  completedAt: string;
};

export function PublicSourceOperations() {
  const operations = usePublicOperations(5_000);
  const [profile, setProfile] = useState<Profile>("standard");
  const [busySource, setBusySource] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [oldDemoLink, setOldDemoLink] = useState(false);

  useEffect(() => {
    setOldDemoLink(!SINGLE_LIVE_MODE && new URLSearchParams(window.location.search).get("mode") === "demo");
  }, []);

  const runSource = useCallback(async (sourceId: string) => {
    setBusySource(sourceId);
    setSummary(null);
    setActionError(null);
    try {
      if (sourceId === "usaspending-onr-grants") await postPublicAcquisitionRunApi(profile);
      else await postPublicSourceRunApi(sourceId, profile);
      await operations.refresh(true);
      setSummary({ successful: 1, failed: 0, completedAt: new Date().toISOString() });
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "The public source run failed.");
      setSummary({ successful: 0, failed: 1, completedAt: new Date().toISOString() });
    } finally {
      setBusySource(null);
    }
  }, [operations, profile]);

  const runAll = useCallback(async () => {
    const sourceIds = operations.data?.source_health?.map((source) => source.source_id) ?? [];
    if (sourceIds.length === 0) {
      setActionError("No verified public source registry is available. Refresh the controller receipt before running sources.");
      return;
    }
    setBusySource("all");
    setSummary(null);
    setActionError(null);
    try {
      const results = await Promise.allSettled(sourceIds.map((sourceId) =>
        sourceId === "usaspending-onr-grants"
          ? postPublicAcquisitionRunApi(profile)
          : postPublicSourceRunApi(sourceId, profile),
      ));
      await operations.refresh(true);
      const failed = results.filter((result) => result.status === "rejected").length;
      setSummary({ successful: results.length - failed, failed, completedAt: new Date().toISOString() });
      if (failed > 0) {
        setActionError(`${failed} source request${failed === 1 ? "" : "s"} failed. Each prior accepted snapshot remains active.`);
      }
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "The public source run could not complete.");
    } finally {
      setBusySource(null);
    }
  }, [operations, profile]);

  const data = operations.data;
  const latest = useMemo(() => latestAcceptedBySource(data?.acquisitions ?? []), [data]);
  const sources = data?.source_health ?? [];
  const healthy = sources.filter((source) => source.status === "healthy").length;
  const latestRun = data?.acquisitions.find((run) => run.status === "completed") ?? null;
  const error = actionError ?? operations.error;
  const controllerLabel = operations.error
    ? "Live service unavailable"
    : operations.control?.enabled
      ? "Continuous acquisition running"
      : operations.control?.status === "stopped"
        ? "Continuous acquisition stopped"
        : "Controller verifying";
  const controllerDetail = operations.control?.enabled
    ? "The AWS controller is enabled and invokes each authority only at its responsible cadence until an operator stops it."
    : operations.control?.status === "stopped"
      ? "The AWS controller is stopped. Retained accepted snapshots stay available, and an operator can restart acquisition or run one source now."
      : "Compass is verifying the protected controller receipt. No active schedule is claimed until that receipt is available.";

  return (
    <div className="mt-6 space-y-5">
      {oldDemoLink ? (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warn/35 bg-warn-soft p-4 shadow-soft">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />
            <div><p className="text-sm font-bold text-text-strong">Synthetic rehearsal now has its own boundary</p><p className="mt-1 text-xs leading-5 text-text-muted">This page is reserved for real public APIs. Enter rehearsal explicitly for prepared synthetic files and deterministic stages.</p></div>
          </div>
          <Link href="/rehearsal/" className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-xs font-bold text-white hover:bg-gov-primary-dark">Open rehearsal selection <ArrowRight className="size-3.5" aria-hidden /></Link>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-success/25 bg-white shadow-card">
        <div className="grid gap-5 bg-gov-primary p-5 text-white lg:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)] lg:p-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/35 bg-emerald-300/10 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wide text-emerald-100"><span className="size-2 rounded-full bg-emerald-300" /> {controllerLabel}</span>
              <span className="rounded-full border border-white/20 bg-white/8 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wide text-white/75">{sources.length ? `${sources.length} configured authorities` : "Registry verifying"}</span>
            </div>
            <h2 className="mt-3 text-2xl font-bold tracking-tight">Public acquisition control with exact source proof</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/72">{controllerDetail} Each accepted response retains hashes, governance outcome, model receipt, and snapshot identity for intelligence.</p>
            <p className="mt-3 rounded-lg border border-white/12 bg-white/[0.06] p-3 text-xs leading-5 text-white/78"><strong className="text-white">Live behavior:</strong> the browser refreshes retained receipts every five seconds. It does not manufacture source events or call public APIs every second.</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Metric label="Healthy connectors" value={sources.length ? `${healthy}/${sources.length}` : "Verifying"} />
            <Metric label="Accepted snapshots" value={latest.size.toLocaleString("en-US")} />
            <Metric label="Latest records" value={(latestRun?.record_count ?? 0).toLocaleString("en-US")} />
            <Metric label="Screen receipt refresh" value="5 sec" />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-2 p-4">
          <div className="flex flex-wrap items-center gap-2 text-[10px] text-text-muted">
            <Clock3 className="size-3.5 text-gov-primary" aria-hidden />
            <span>Last receipt refresh: <strong className="text-text-strong">{operations.lastRefreshedAt ? new Date(operations.lastRefreshedAt).toLocaleTimeString() : "verifying"}</strong></span>
            <span className="text-border-strong" aria-hidden>|</span>
            <span>Configured schedules remain visible on each source card.</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select value={profile} onChange={(event) => setProfile(event.target.value as Profile)} disabled={busySource !== null} className="min-h-11 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-strong" aria-label="Bounded pull size">
              {(Object.keys(PROFILE_LABELS) as Profile[]).map((value) => <option key={value} value={value}>{PROFILE_LABELS[value]}</option>)}
            </select>
            <button type="button" onClick={() => void operations.refresh()} disabled={busySource !== null || operations.refreshing} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-muted hover:bg-surface-2 disabled:opacity-50"><RefreshCw className={`size-4 ${operations.refreshing ? "animate-spin" : ""}`} aria-hidden /> Refresh receipts</button>
            <button type="button" onClick={() => void runAll()} disabled={busySource !== null || sources.length === 0} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-success px-4 text-xs font-bold text-white hover:brightness-95 disabled:opacity-55">{busySource === "all" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Cloud className="size-4" aria-hidden />}{busySource === "all" ? `Pulling ${sources.length} sources` : `Pull all ${sources.length || "verified"} now`}</button>
          </div>
        </div>
      </section>

      <LiveEvidenceStatus
        control={operations.control}
        healthySources={operations.summary.healthySources}
        sourceCount={sources.length}
        lastRefreshedAt={operations.lastRefreshedAt}
        refreshing={operations.refreshing}
        controlling={operations.controlling}
        error={operations.error}
        onRefresh={() => void operations.refresh()}
        onSetContinuous={(enabled) => void operations.setContinuous(enabled)}
      />

      {summary ? <RunResult summary={summary} /> : null}
      {error ? <div role="alert" className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger-soft p-4 text-xs leading-5 text-danger"><AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden /><div><p className="font-bold">The requested pull needs attention</p><p className="mt-1">{error}</p><p className="mt-1 text-[10px]">The last accepted snapshot remains available. Open Alerts for retained operator evidence.</p></div></div> : null}

      <section className="rounded-xl border border-border bg-white p-5 shadow-card" aria-labelledby="receipt-path-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Actual accepted receipt</p><h2 id="receipt-path-heading" className="mt-1 text-lg font-bold text-text-strong">What the latest completed pull proves</h2><p className="mt-1 text-xs leading-5 text-text-muted">This is a receipt summary, not a time-based animation.</p></div>
          {latestRun ? <Link href={`/admin/lineage/?run=${encodeURIComponent(latestRun.run_id)}`} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 px-3 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Open exact lineage <Route className="size-3.5" aria-hidden /></Link> : null}
        </div>
        {latestRun ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <ReceiptProof icon={Cloud} title="1. Source called" value={latestRun.source_label ?? latestRun.source_id} detail={`${latestRun.pages_fetched ?? 1} bounded page${latestRun.pages_fetched === 1 ? "" : "s"}`} />
            <ReceiptProof icon={Database} title="2. Response retained" value={`${(latestRun.source_response_bytes ?? 0).toLocaleString("en-US")} bytes`} detail={shortHash(latestRun.snapshot_sha256)} />
            <ReceiptProof icon={ShieldCheck} title="3. Quality governed" value={`${(latestRun.record_count ?? 0).toLocaleString("en-US")} accepted`} detail={`${latestRun.review_flag_count ?? 0} review flags`} />
            <ReceiptProof icon={Sparkles} title="4. Model applied" value={latestRun.classification_status ?? "not configured"} detail={latestRun.classification_summary?.model_version ?? "No model receipt"} />
            <ReceiptProof icon={CheckCircle2} title="5. Snapshot published" value={latestRun.stage.replaceAll("_", " ")} detail={latestRun.run_id} />
          </div>
        ) : <EmptyState title="No accepted public receipt is available yet" detail="Pull one source to create a traceable accepted snapshot." />}
      </section>

      <section aria-labelledby="source-cards-heading">
        <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Exact inputs</p><h2 id="source-cards-heading" className="mt-1 text-lg font-bold text-text-strong">Named public sources</h2><p className="mt-1 text-xs text-text-muted">Every card shows authority, endpoint, schedule, last accepted receipt, and model state.</p></div><span className="inline-flex items-center gap-2 rounded-full border border-info/25 bg-info-soft px-3 py-1.5 text-[9px] font-bold uppercase text-info"><BellRing className="size-3.5" aria-hidden /> Failures appear in Alerts</span></div>
        <div className="mt-3 grid gap-3 xl:grid-cols-2">
          {sources.map((source) => <SourceCard key={source.source_id} source={source} latest={latest.get(source.source_id) ?? null} busy={busySource === source.source_id || busySource === "all"} onRun={() => void runSource(source.source_id)} />)}
          {sources.length === 0 && operations.loading ? <EmptyState title="Loading the protected source registry" detail="Compass is verifying connector health and retained receipts." /> : null}
          {sources.length === 0 && !operations.loading && operations.error ? <EmptyState title="Public source registry is unavailable" detail="No source activity or synthetic substitute is shown. Refresh after the protected service recovers." /> : null}
          {sources.length === 0 && !operations.loading && !operations.error ? <EmptyState title="No configured public source is available" detail="The protected registry returned no source contracts. Configure and verify a source before starting acquisition." /> : null}
        </div>
      </section>

      <section className="rounded-xl border border-gov-primary/20 bg-gov-primary-lighter/35 p-5 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Next decision step</p><h2 className="mt-1 text-lg font-bold text-text-strong">Use accepted snapshots across the primary product</h2><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">The catalog, analytics, decision, model, release, and intelligence screens all project these accepted public receipts. Source links, capture times, exact identities, relationship candidates, model versions, and citations remain attached.</p></div>
          <Link href="/intelligence/" className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white hover:bg-gov-primary-dark">Open accepted public intelligence <ArrowRight className="size-4" aria-hidden /></Link>
        </div>
      </section>
    </div>
  );
}

function SourceCard({ source, latest, busy, onRun }: { source: PublicSourceHealth; latest: PublicAcquisitionRecord | null; busy: boolean; onRun: () => void }) {
  const healthy = source.status === "healthy";
  return (
    <article className="rounded-xl border border-border bg-white p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${healthy ? "border-success/30 bg-success-soft text-success" : source.status === "failed" ? "border-danger/30 bg-danger-soft text-danger" : "border-info/25 bg-info-soft text-info"}`}>{source.status.replaceAll("-", " ")}</span><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${latest ? "border-success/25 bg-success-soft text-success" : "border-info/25 bg-info-soft text-info"}`}>{latest ? "Accepted public receipt" : "Configured public source"}</span></div><h3 className="mt-2 text-sm font-bold text-text-strong">{source.label}</h3><p className="mt-1 text-[10px] text-text-muted">Authority: {source.authority}</p></div>
        <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-gov-primary-lighter text-gov-primary"><RadioTower className="size-4.5" aria-hidden /></span>
      </div>
      <a href={source.endpoint} target="_blank" rel="noreferrer" className="mt-3 flex min-h-10 items-center gap-2 rounded-md border border-border bg-surface-2 px-3 font-mono text-[8.5px] text-gov-primary hover:bg-white"><span className="min-w-0 flex-1 truncate">{source.endpoint}</span><ExternalLink className="size-3.5 shrink-0" aria-hidden /></a>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-[9px]">
        <SourceFact label="Responsible schedule" value={formatCadence(source.cadence_seconds)} />
        <SourceFact label="Last accepted" value={formatTimestamp(source.last_accepted_at)} />
        <SourceFact label="Latest records" value={(latest?.record_count ?? source.latest_record_count ?? 0).toLocaleString("en-US")} />
        <SourceFact label="Added / changed" value={`${latest?.added_records ?? source.latest_added_records ?? 0} / ${latest?.changed_records ?? source.latest_changed_records ?? 0}`} />
        <SourceFact label="Model" value={latest?.classification_summary?.model_version ?? source.model_version ?? "not configured"} />
        <SourceFact label="Run" value={latest?.run_id ?? source.latest_run_id ?? "awaiting first run"} mono />
      </dl>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={onRun} disabled={busy} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-[10px] font-bold text-white hover:bg-gov-primary-dark disabled:opacity-50">{busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Cloud className="size-3.5" aria-hidden />}{busy ? "Pulling source" : "Pull this source now"}</button>
        {latest ? <Link href={`/admin/lineage/?run=${encodeURIComponent(latest.run_id)}`} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-[10px] font-bold text-gov-primary hover:bg-surface-2">Lineage <Route className="size-3.5" aria-hidden /></Link> : null}
        {latest?.record_preview?.[0]?.source_url ? <a href={latest.record_preview[0].source_url} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-[10px] font-bold text-gov-primary hover:bg-surface-2">Example source record <FileSearch className="size-3.5" aria-hidden /></a> : null}
      </div>
    </article>
  );
}

function RunResult({ summary }: { summary: RunSummary }) {
  const success = summary.failed === 0;
  return <section aria-live="polite" className={`flex items-start gap-3 rounded-xl border p-4 shadow-soft ${success ? "border-success/30 bg-success-soft" : "border-warn/35 bg-warn-soft"}`}>{success ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden /> : <AlertCircle className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />}<div><p className="text-sm font-bold text-text-strong">Public source request completed</p><p className="mt-1 text-xs text-text-muted">{summary.successful} succeeded, {summary.failed} failed. Completed at {formatTimestamp(summary.completedAt)}. Only accepted snapshots were published.</p></div></section>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-white/12 bg-white/[0.07] p-3"><p className="font-mono text-lg font-bold text-gold-light">{value}</p><p className="mt-1 text-[8px] font-bold uppercase tracking-wide text-white/70">{label}</p></div>;
}

function ReceiptProof({ icon: Icon, title, value, detail }: { icon: typeof Cloud; title: string; value: string; detail: string }) {
  return <article className="rounded-lg border border-border bg-surface-2 p-3"><span className="grid size-8 place-items-center rounded-md bg-success text-white"><Icon className="size-4" aria-hidden /></span><p className="mt-3 text-[9px] font-bold uppercase tracking-wide text-success">{title}</p><p className="mt-1 truncate text-xs font-bold text-text-strong" title={value}>{value}</p><p className="mt-1 truncate font-mono text-[8px] text-text-muted" title={detail}>{detail}</p></article>;
}

function SourceFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="min-w-0 rounded-md border border-border bg-surface-2 p-2"><dt className="font-bold uppercase tracking-wide text-text-subtle">{label}</dt><dd className={`mt-1 truncate text-text-strong ${mono ? "font-mono text-[8px]" : "font-semibold"}`} title={value}>{value}</dd></div>;
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="rounded-xl border border-dashed border-border bg-white p-5 text-center"><Database className="mx-auto size-5 text-text-subtle" aria-hidden /><p className="mt-2 text-sm font-bold text-text-strong">{title}</p><p className="mt-1 text-xs text-text-muted">{detail}</p></div>;
}

function latestAcceptedBySource(acquisitions: PublicAcquisitionRecord[]): Map<string, PublicAcquisitionRecord> {
  const latest = new Map<string, PublicAcquisitionRecord>();
  for (const run of acquisitions) {
    if (run.status === "completed" && !latest.has(run.source_id)) latest.set(run.source_id, run);
  }
  return latest;
}

function formatCadence(seconds: number): string {
  if (seconds >= 3_600 && seconds % 3_600 === 0) return `Every ${seconds / 3_600} hour${seconds === 3_600 ? "" : "s"}`;
  if (seconds >= 60 && seconds % 60 === 0) return `Every ${seconds / 60} minute${seconds === 60 ? "" : "s"}`;
  return `Every ${seconds} seconds`;
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "Awaiting first run";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function shortHash(value?: string): string {
  if (!value) return "Hash retained in run receipt";
  return `SHA-256 ${value.slice(0, 12)}...`;
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  BellRing,
  Bot,
  CheckCircle2,
  Cloud,
  Database,
  ExternalLink,
  FileSearch,
  FlaskConical,
  GitBranch,
  Layers3,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Route,
  ShieldCheck,
  TimerReset,
} from "lucide-react";

import {
  getPublicAcquisitionsApi,
  getOperationsSignals,
  postPublicAcquisitionRunApi,
  postPublicSourceRunApi,
  type PublicAcquisitionList,
  type PublicAcquisitionRecord,
  type PublicEvidenceThread,
  type PublicSourceHealth,
} from "@/lib/api";
import {
  buildAcquisitionDemoReplay,
  buildAcquisitionDemoSignals,
  DEMO_FAILURE_SOURCE_ID,
} from "@/lib/acquisition/demo-replay";
import type { OperationsSignalsResponse } from "@/lib/types";

type Profile = "quick" | "standard" | "deep";
type EvidenceMode = "live" | "demo";

const ALL_SOURCES = "all-live-sources";
const SOURCE_IDS = [
  "usaspending-onr-grants",
  "grants-gov-onr",
  "federal-register-onr",
  "crossref-onr",
] as const;

const PIPELINE_STEPS = [
  { label: "Acquire", detail: "Official HTTPS API", service: "Public Acquisition Lambda", icon: Activity },
  { label: "Retain", detail: "Immutable raw receipt", service: "Versioned S3 raw zone", icon: Database },
  { label: "Govern", detail: "Canonical quality gate", service: "Owner and steward policy", icon: ShieldCheck },
  { label: "Detect", detail: "Stable hash comparison", service: "SHA-256 delta function", icon: GitBranch },
  { label: "Classify", detail: "Champion model", service: "Document classifier Lambda", icon: Bot },
  { label: "Link", detail: "Evidence identity keys", service: "DynamoDB evidence index", icon: Route },
  { label: "Decide", detail: "Analyst review surface", service: "Compass decision API", icon: FileSearch },
] as const;

const PROFILE_LABELS: Record<Profile, string> = {
  quick: "Quick sample",
  standard: "Standard sample",
  deep: "Deep bounded sample",
};

export function AcquisitionOperationsDashboard() {
  const [liveData, setLiveData] = useState<PublicAcquisitionList | null>(null);
  const [liveSignals, setLiveSignals] = useState<OperationsSignalsResponse | null>(null);
  const [mode, setMode] = useState<EvidenceMode>("live");
  const [modeReady, setModeReady] = useState(false);
  const [demoFailureSource, setDemoFailureSource] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busySource, setBusySource] = useState<string | null>(null);
  const [profile, setProfile] = useState<Profile>("standard");
  const [now, setNow] = useState(() => new Date());
  const [busyStartedAt, setBusyStartedAt] = useState<number | null>(null);
  const [playbackTick, setPlaybackTick] = useState(0);
  const [playbackRunning, setPlaybackRunning] = useState(true);

  const refreshLive = useCallback(async () => {
    try {
      const response = await getPublicAcquisitionsApi();
      setLiveData(response);
      void getOperationsSignals().then(setLiveSignals).catch(() => undefined);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Live source operations are unavailable.");
    }
  }, []);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    setMode(query.get("mode") === "demo" ? "demo" : "live");
    setModeReady(true);
  }, []);

  useEffect(() => {
    const displayTimer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(displayTimer);
  }, []);

  useEffect(() => {
    if (!modeReady || mode !== "live") return;
    void refreshLive();
    const sourceTimer = window.setInterval(() => void refreshLive(), 1_000);
    return () => window.clearInterval(sourceTimer);
  }, [mode, modeReady, refreshLive]);

  useEffect(() => {
    if (!modeReady || !playbackRunning) return;
    const playbackTimer = window.setInterval(() => setPlaybackTick((value) => value + 1), 1_000);
    return () => window.clearInterval(playbackTimer);
  }, [modeReady, playbackRunning]);

  const selectMode = useCallback((nextMode: EvidenceMode) => {
    setMode(nextMode);
    setDemoFailureSource(null);
    setError(null);
    setPlaybackTick(0);
    const url = new URL(window.location.href);
    if (nextMode === "demo") url.searchParams.set("mode", "demo");
    else url.searchParams.delete("mode");
    window.history.replaceState({}, "", url);
  }, []);

  const runSource = useCallback(async (sourceId: string) => {
    setBusySource(sourceId);
    setBusyStartedAt(Date.now());
    setError(null);
    try {
      if (mode === "demo") {
        await new Promise<void>((resolve) => window.setTimeout(resolve, 3_500));
        setPlaybackTick(0);
      } else {
        if (sourceId === "usaspending-onr-grants") await postPublicAcquisitionRunApi(profile);
        else await postPublicSourceRunApi(sourceId, profile);
        await refreshLive();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The requested source run failed.");
    } finally {
      setBusySource(null);
      setBusyStartedAt(null);
    }
  }, [mode, profile, refreshLive]);

  const runAllSources = useCallback(async () => {
    setBusySource(ALL_SOURCES);
    setBusyStartedAt(Date.now());
    setError(null);
    try {
      if (mode === "demo") {
        await new Promise<void>((resolve) => window.setTimeout(resolve, 4_000));
        setPlaybackTick(0);
        return;
      }
      const results = await Promise.allSettled([
        postPublicAcquisitionRunApi(profile),
        ...SOURCE_IDS.slice(1).map((sourceId) => postPublicSourceRunApi(sourceId, profile)),
      ]);
      await refreshLive();
      const failures = results.filter((result) => result.status === "rejected").length;
      if (failures) setError(`${failures} live source request${failures === 1 ? "" : "s"} failed. Prior accepted snapshots remain active.`);
    } finally {
      setBusySource(null);
      setBusyStartedAt(null);
    }
  }, [mode, profile, refreshLive]);

  const demoData = useMemo(() => buildAcquisitionDemoReplay(demoFailureSource), [demoFailureSource]);
  const demoSignals = useMemo(() => buildAcquisitionDemoSignals(demoFailureSource), [demoFailureSource]);
  const data = mode === "demo" ? demoData : liveData;
  const signals = mode === "demo" ? demoSignals : liveSignals;
  const sourceHealth = data?.source_health ?? [];
  const latestBySource = useMemo(() => latestAcceptedBySource(data?.acquisitions ?? []), [data]);
  const evidenceThreads = data?.evidence_threads ?? [];
  const decision = useMemo(() => buildDecisionSummary(latestBySource), [latestBySource]);
  const healthy = sourceHealth.filter((source) => source.status === "healthy").length;
  const latestRun = data?.acquisitions[0] ?? null;
  const busyStep = busyStartedAt === null ? null : Math.floor((now.getTime() - busyStartedAt) / 1_100) % PIPELINE_STEPS.length;

  return (
    <div className="space-y-5">
      <EvidenceModeControl
        mode={mode}
        ready={modeReady}
        failureActive={Boolean(demoFailureSource)}
        busy={busySource !== null}
        onModeChange={selectMode}
        onRunAll={() => void runAllSources()}
        onRehearseFailure={() => setDemoFailureSource(DEMO_FAILURE_SOURCE_ID)}
        onClearFailure={() => setDemoFailureSource(null)}
      />
      <section className="overflow-hidden rounded-xl border border-gov-primary/25 bg-white shadow-card">
        <div className="grid gap-5 bg-gov-primary px-5 py-5 text-white xl:grid-cols-[1.2fr_0.8fr] xl:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/35 bg-emerald-300/10 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wide text-emerald-100">
                <span className="size-2 animate-pulse rounded-full bg-emerald-300" /> One-second operations view
              </span>
              <span className="rounded-full border border-white/20 bg-white/8 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wide text-white/75">
                {mode === "live" ? "Real public source records" : "Synthetic demo records"}
              </span>
            </div>
            <h2 className="mt-3 text-2xl font-bold tracking-tight">Multi-source ingestion command center</h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-white/72">
              {mode === "live" ? "Run all four official sources concurrently, then watch accepted evidence move through every governed function once per second." : "Replay four unmistakably synthetic sources through every layer once per second, including a safe failure scenario."}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-2">
            <HeroMetric label="Source health" value={`${healthy}/${sourceHealth.length || 4}`} detail="healthy connectors" />
            <HeroMetric label="Display clock" value={now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })} detail="local monitoring time" />
            <HeroMetric label="Latest records" value={(latestRun?.record_count ?? 0).toLocaleString("en-US")} detail={latestRun?.source_label ?? latestRun?.source_id ?? "waiting for receipt"} />
            <HeroMetric label="Review flags" value={decision.reviewFlags.toLocaleString("en-US")} detail="transparent analyst rules" />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gov-primary/15 bg-gov-primary-lighter/35 px-5 py-3">
          <p className="text-[10px] leading-4 text-text-muted">
            {mode === "live" ? "The one-second animation replays retained live receipts. Public APIs are called on demand or at their responsible schedules, not once per second." : "DEMO DATA ACTIVE. Every record, relationship, model result, and failure on this screen is synthetic. No external API is called."}
          </p>
          <div className="flex items-center gap-2">
            <select value={profile} onChange={(event) => setProfile(event.target.value as Profile)} className="min-h-10 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-strong" aria-label="Run size">
              {(Object.keys(PROFILE_LABELS) as Profile[]).map((value) => <option key={value} value={value}>{PROFILE_LABELS[value]}</option>)}
            </select>
            <button type="button" onClick={() => mode === "live" ? void refreshLive() : setPlaybackTick(0)} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-muted hover:bg-surface-2">
              <RefreshCw className="size-3.5" aria-hidden /> {mode === "live" ? "Refresh receipts" : "Restart replay"}
            </button>
          </div>
        </div>
      </section>

      {error ? <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft p-3 text-xs leading-5 text-danger"><span className="flex items-start gap-2"><AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden /> {error}</span>{mode === "live" ? <button type="button" onClick={() => selectMode("demo")} className="min-h-9 rounded-md border border-danger/30 bg-white px-3 text-[10px] font-bold text-danger">Open safe demo replay</button> : null}</div> : null}

      <EvidenceFlowTheater
        mode={mode}
        activeStep={busyStep ?? playbackTick % PIPELINE_STEPS.length}
        activelyCalling={busySource !== null}
        sourceHealth={sourceHealth}
        latest={latestBySource}
        running={playbackRunning}
        onToggle={() => setPlaybackRunning((value) => !value)}
      />

      <section aria-labelledby="source-health-heading">
        <SectionHeading kicker="Acquisition layer" title="Independent source health" detail="Every card names the exact input authority, endpoint, evidence mode, cadence, last receipt, and model version." />
        <div className="mt-3 grid gap-3 xl:grid-cols-2">
          {sourceHealth.map((source) => (
            <SourceHealthCard
              key={source.source_id}
              source={source}
              latest={latestBySource.get(source.source_id) ?? null}
              mode={mode}
              busy={busySource === source.source_id || busySource === ALL_SOURCES}
              onRun={() => void runSource(source.source_id)}
            />
          ))}
          {sourceHealth.length === 0 ? <EmptyPanel title="Loading source registry" detail="The protected acquisition endpoint is loading live source health." /> : null}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-xl border border-border bg-white p-5 shadow-card">
          <SectionHeading kicker="Intelligence layer" title="Cross-source evidence threads" detail="Exact governed keys are verified first. Explainable candidates are separately scored, owned, and held for analyst review." />
          <div className="mt-4 space-y-3">
            {evidenceThreads.length ? evidenceThreads.slice(0, 8).map((thread) => <EvidenceThreadCard key={thread.thread_id} thread={thread} />) : (
              <EmptyPanel title="No cross-source relationship in the current bounded pages" detail="Exact identities and reviewable candidate relationships are recalculated whenever a source page is accepted. The larger governed corpus remains available in Public Portfolio Intelligence." actionHref="/intelligence/" actionLabel="Open governed intelligence" />
            )}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-white p-5 shadow-card">
          <SectionHeading kicker="Decision layer" title="What changed and what needs review" detail="These are evidence-backed triage signals, not automated mission verdicts." />
          <div className="mt-4 grid grid-cols-2 gap-2">
            <DecisionMetric label="Observed funding" value={formatCurrency(decision.observedFunding)} detail="bounded USAspending page" />
            <DecisionMetric label="Open opportunities" value={decision.openOpportunities.toLocaleString("en-US")} detail="current Grants.gov page" />
            <DecisionMetric label="Publications" value={decision.publications.toLocaleString("en-US")} detail="exact ONR funder page" />
            <DecisionMetric label="Notices" value={decision.notices.toLocaleString("en-US")} detail="ONR phrase matches" />
          </div>
          <div className="mt-4 rounded-lg border border-gov-primary/20 bg-gov-primary-lighter/35 p-4">
            <p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">Analyst next step</p>
            <p className="mt-2 text-sm font-bold text-text-strong">{decision.reviewFlags ? `Review ${decision.reviewFlags} flagged records` : "No transparent review rule is currently open"}</p>
            <p className="mt-1 text-xs leading-5 text-text-muted">Open the record, verify its source evidence and model classification, then decide whether it belongs in a governed portfolio view.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link href="/intelligence/" className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-xs font-bold text-white hover:bg-gov-primary-dark">Open intelligence <ArrowRight className="size-3.5" aria-hidden /></Link>
              <Link href="/dashboard/" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 bg-white px-3 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Open decision workspace <ArrowRight className="size-3.5" aria-hidden /></Link>
            </div>
          </div>
        </div>
      </section>

      <RecordExplorer latest={latestBySource} mode={mode} />

      <OperatorSignals signals={signals} mode={mode} />

      <section className="grid gap-4 xl:grid-cols-2">
        <ReviewQueue acquisitions={data?.acquisitions ?? []} mode={mode} />
        <ModelEvidence acquisitions={data?.acquisitions ?? []} mode={mode} />
      </section>

      <RunHistory acquisitions={data?.acquisitions ?? []} mode={mode} />
    </div>
  );
}

function EvidenceModeControl({
  mode,
  ready,
  failureActive,
  busy,
  onModeChange,
  onRunAll,
  onRehearseFailure,
  onClearFailure,
}: {
  mode: EvidenceMode;
  ready: boolean;
  failureActive: boolean;
  busy: boolean;
  onModeChange: (mode: EvidenceMode) => void;
  onRunAll: () => void;
  onRehearseFailure: () => void;
  onClearFailure: () => void;
}) {
  const live = mode === "live";
  return (
    <section className={`rounded-xl border p-4 shadow-card ${live ? "border-success/30 bg-success-soft/35" : "border-warn/40 bg-warn-soft/45"}`} aria-label="Evidence mode">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className={`grid size-11 shrink-0 place-items-center rounded-lg ${live ? "bg-success text-white" : "bg-warn text-white"}`}>
            {live ? <Cloud className="size-5" aria-hidden /> : <FlaskConical className="size-5" aria-hidden />}
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${live ? "border-success/35 bg-white text-success" : "border-warn/35 bg-white text-warn"}`}>
                {live ? "Live public APIs" : "Demo replay | synthetic"}
              </span>
              <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-text-muted">One-second visual flow</span>
            </div>
            <p className="mt-2 text-sm font-bold text-text-strong">{live ? "Real evidence mode is active" : "Safe presentation mode is active"}</p>
            <p className="mt-1 max-w-4xl text-[10px] leading-5 text-text-muted">
              {live
                ? "Run all four official endpoints concurrently. The newest accepted receipts refresh on screen every second and advance through the governed path once per second."
                : "Every record and event is a deterministic synthetic fixture. No external API, production record, model endpoint, or email delivery is used."}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-border bg-white p-1" aria-label="Choose evidence mode">
            <button type="button" onClick={() => onModeChange("live")} disabled={!ready} className={`min-h-9 rounded-md px-3 text-[10px] font-bold ${live ? "bg-gov-primary text-white" : "text-text-muted hover:bg-surface-2"}`}>Live APIs</button>
            <button type="button" onClick={() => onModeChange("demo")} disabled={!ready} className={`min-h-9 rounded-md px-3 text-[10px] font-bold ${!live ? "bg-warn text-white" : "text-text-muted hover:bg-surface-2"}`}>Demo replay</button>
          </div>
          <button type="button" onClick={onRunAll} disabled={busy || !ready} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white hover:bg-gov-primary-dark disabled:opacity-55">
            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : live ? <Cloud className="size-4" aria-hidden /> : <TimerReset className="size-4" aria-hidden />}
            {busy ? "Processing all sources" : live ? "Run all live sources now" : "Replay all demo sources"}
          </button>
          {!live ? (
            <button type="button" onClick={failureActive ? onClearFailure : onRehearseFailure} className={`inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-xs font-bold ${failureActive ? "border-success/30 bg-white text-success" : "border-danger/30 bg-danger-soft text-danger"}`}>
              {failureActive ? <CheckCircle2 className="size-4" aria-hidden /> : <AlertCircle className="size-4" aria-hidden />}
              {failureActive ? "Clear failure rehearsal" : "Rehearse source failure"}
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function OperatorSignals({ signals, mode }: { signals: OperationsSignalsResponse | null; mode: EvidenceMode }) {
  const relevant = (signals?.signals ?? [])
    .filter((signal) => signal.run_kind === "public_acquisition" || signal.signal_type.includes("acquisition"))
    .slice(0, 8);
  const live = mode === "live";
  return <section className="rounded-xl border border-border bg-white p-5 shadow-card"><div className="flex flex-wrap items-start justify-between gap-3"><SectionHeading kicker="Notification and response layer" title={live ? "Live operator signals" : "Synthetic notification rehearsal"} detail={live ? "Accepted changes, classification degradation, source failures, and review events produce retained signals linked to the affected live run." : "These clearly marked demo signals show how acceptance and failure alerts behave without sending email or changing external systems."} /><div className="flex flex-wrap gap-2"><span className={`rounded-full border px-3 py-1.5 text-[9px] font-bold uppercase ${live ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>{live ? "Live operations" : "Demo signals"}</span><span className="inline-flex items-center gap-2 rounded-full border border-warn/30 bg-warn-soft px-3 py-1.5 text-[9px] font-bold uppercase text-warn"><BellRing className="size-3.5" aria-hidden /> {signals?.unread_count ?? 0} unread</span></div></div><div className="mt-4 grid gap-2 lg:grid-cols-2">{relevant.length ? relevant.map((signal) => <article key={signal.event_id} className={`rounded-lg border p-3 ${signal.severity === "critical" ? "border-danger/30 bg-danger-soft" : signal.severity === "warning" ? "border-warn/30 bg-warn-soft/50" : "border-info/25 bg-info-soft/45"}`}><div className="flex items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><p className="text-xs font-bold text-text-strong">{signal.title}</p><span className={`rounded border px-1.5 py-0.5 text-[7px] font-bold uppercase ${live ? "border-success/25 bg-white text-success" : "border-warn/25 bg-white text-warn"}`}>{live ? "Live" : "Synthetic"}</span></div><p className="mt-1 text-[9px] leading-4 text-text-muted">{signal.message}</p><p className="mt-2 font-mono text-[8px] text-text-subtle">{signal.occurred_at}</p></div>{signal.href ? <Link href={signal.href} className="grid size-9 shrink-0 place-items-center rounded-md border border-border bg-white text-gov-primary" aria-label={`Open signal ${signal.title}`}><ArrowRight className="size-3.5" aria-hidden /></Link> : null}</div></article>) : <div className="lg:col-span-2"><EmptyPanel title="No current source signals" detail="Run a source to create an accepted-change signal. Failures and degraded classifications create higher-severity alerts without replacing the prior accepted snapshot." /></div>}</div><p className="mt-3 text-[9px] leading-4 text-text-subtle">{signals?.disclosure ?? "The notification feed loads from the protected operations API."}</p></section>;
}

function RecordExplorer({ latest, mode }: { latest: Map<string, PublicAcquisitionRecord>; mode: EvidenceMode }) {
  const [query, setQuery] = useState("");
  const records = useMemo(() => {
    const output = [];
    for (const run of latest.values()) {
      const predictions = new Map((run.classification_summary?.preview ?? []).map((item) => [item.source_record_id, item]));
      for (const record of run.record_preview ?? []) {
        output.push({ run, record, prediction: predictions.get(record.source_record_id) });
      }
    }
    const needle = query.trim().toLowerCase();
    return output.filter(({ run, record }) => !needle || [run.source_label, run.source_id, record.source_record_id, record.title, record.description, record.recipient_name, ...(record.award_ids ?? []), ...(record.topics ?? [])].some((value) => String(value ?? "").toLowerCase().includes(needle))).slice(0, 60);
  }, [latest, query]);
  return <section className="overflow-hidden rounded-xl border border-border bg-white shadow-card"><div className="flex flex-wrap items-end justify-between gap-3 p-5"><div><SectionHeading kicker="Data and governance layer" title="Inspect every accepted evidence point" detail="Each row exposes the source identity, exact link keys, accountable owner and steward, model route, analyst disposition, source link, and run lineage." /><span className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-[8px] font-bold uppercase ${mode === "live" ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>{mode === "live" ? "Live public evidence" : "Demo synthetic evidence"}</span></div><label className="block min-w-[260px]"><span className="sr-only">Search accepted evidence</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search source, award, DOI, title, topic..." className="min-h-11 w-full rounded-md border border-border bg-white px-3 text-xs text-text-strong placeholder:text-text-subtle" /></label></div><div className="overflow-x-auto"><table className="min-w-full text-left"><thead className="border-y border-border bg-surface-2 text-[9px] uppercase tracking-wide text-text-subtle"><tr><th className="px-4 py-3">Evidence point</th><th className="px-4 py-3">Source and governance</th><th className="px-4 py-3">Exact identity</th><th className="px-4 py-3">ML route</th><th className="px-4 py-3">Disposition</th><th className="px-4 py-3">Open</th></tr></thead><tbody className="divide-y divide-border">{records.map(({ run, record, prediction }) => { const flagged = (run.review_flags ?? []).some((flag) => flag.source_record_id === record.source_record_id); const classifiedInArtifact = Boolean(run.classification_summary); return <tr key={`${run.source_id}-${record.source_record_id}`} className="align-top text-xs"><td className="max-w-md px-4 py-3"><p className="font-bold text-text-strong">{record.title ?? record.recipient_name ?? record.source_record_id}</p><p className="mt-1 line-clamp-2 text-[9px] leading-4 text-text-muted">{record.description ?? record.record_type?.replaceAll("_", " ") ?? "Public source record"}</p><p className="mt-1 font-mono text-[8px] text-text-subtle">{record.source_record_id}</p></td><td className="px-4 py-3"><p className="font-bold text-gov-primary">{run.source_label ?? run.source_id}</p><p className="mt-1 text-[8px] text-text-muted">Owner: {run.identity_summary?.governance_owner ?? "Portfolio Data Product Owner"}</p><p className="mt-1 text-[8px] text-text-muted">Steward: {run.identity_summary?.governance_steward ?? "Public Evidence Data Steward"}</p><div className="mt-1 flex flex-wrap gap-1"><span className={`inline-flex rounded border px-1.5 py-0.5 text-[7px] font-bold ${mode === "live" ? "border-success/25 bg-success-soft text-success" : "border-warn/25 bg-warn-soft text-warn"}`}>{mode === "live" ? "LIVE PUBLIC" : "DEMO SYNTHETIC"}</span><span className="inline-flex rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[7px] font-bold text-text-subtle">{run.identity_summary?.classification ?? (mode === "live" ? "PUBLIC" : "SYNTHETIC")}</span></div></td><td className="px-4 py-3"><div className="flex max-w-xs flex-wrap gap-1">{(record.identity_keys ?? []).length ? record.identity_keys!.map((key) => <span key={key} className="rounded border border-success/25 bg-success-soft px-1.5 py-1 font-mono text-[7.5px] text-success">{key}</span>) : <span className="text-[9px] text-text-subtle">Source key only</span>}</div></td><td className="px-4 py-3"><p className="font-bold text-text-strong">{prediction?.document_class.replaceAll("_", " ") ?? (classifiedInArtifact ? "Classified in full artifact" : "Not classified")}</p>{prediction ? <p className="mt-1 text-[8px] text-text-muted">{Math.round(prediction.confidence * 100)}% confidence | {run.classification_summary?.model_version}</p> : classifiedInArtifact ? <p className="mt-1 text-[8px] text-text-muted">{run.classification_summary?.model_version}</p> : null}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${flagged || prediction?.review_required ? "border-warn/30 bg-warn-soft text-warn" : "border-success/30 bg-success-soft text-success"}`}>{flagged || prediction?.review_required ? "Analyst review" : "Evidence current"}</span></td><td className="px-4 py-3"><div className="flex gap-1">{record.source_url && mode === "live" ? <a href={record.source_url} target="_blank" rel="noreferrer" className="grid size-9 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Open source record ${record.source_record_id}`} title="Open source record"><ExternalLink className="size-3.5" aria-hidden /></a> : null}{record.document_url && mode === "live" ? <a href={record.document_url} target="_blank" rel="noreferrer" className="grid size-9 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Open source document ${record.source_record_id}`} title={record.document_title ?? "Open source document"}><FileSearch className="size-3.5" aria-hidden /></a> : null}{mode === "live" ? <Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="grid size-9 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Open lineage for ${record.source_record_id}`} title="Open run lineage"><Route className="size-3.5" aria-hidden /></Link> : <span className="grid size-9 place-items-center rounded-md border border-warn/25 bg-warn-soft text-warn" title="Synthetic flow is shown above"><Route className="size-3.5" aria-hidden /></span>}</div></td></tr>; })}</tbody></table>{records.length === 0 ? <div className="p-5"><EmptyPanel title="No accepted records match" detail="Run a connector or change the search to inspect the latest bounded source pages." /></div> : null}</div></section>;
}

function EvidenceFlowTheater({ mode, activeStep, activelyCalling, sourceHealth, latest, running, onToggle }: { mode: EvidenceMode; activeStep: number; activelyCalling: boolean; sourceHealth: PublicSourceHealth[]; latest: Map<string, PublicAcquisitionRecord>; running: boolean; onToggle: () => void }) {
  const live = mode === "live";
  const activeStage = PIPELINE_STEPS[activeStep];
  return (
    <section className="overflow-hidden rounded-xl border border-gov-primary/25 bg-white shadow-card" aria-label="One-second multi-source evidence flow">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-gov-primary-lighter/35 p-4">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">Visible multi-source processing</p>
          <h2 className="mt-1 text-lg font-bold text-text-strong">Four sources move through seven governed functions</h2>
          <p className="mt-1 text-[10px] leading-5 text-text-muted">{live ? "The newest accepted live receipt from each authority advances one stage every second. Use Run all live sources now to request fresh evidence." : "Four synthetic fixture events advance one stage every second. No external request is made."}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[9px] font-bold uppercase ${live ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}><span className={`size-2 rounded-full ${running ? "animate-pulse" : ""} ${live ? "bg-success" : "bg-warn"}`} /> {live ? "Live receipt playback" : "Synthetic event playback"}</span>
          {activelyCalling ? <span className="inline-flex items-center gap-2 rounded-full border border-info/30 bg-info-soft px-3 py-1.5 text-[9px] font-bold uppercase text-info"><Loader2 className="size-3.5 animate-spin" aria-hidden /> {live ? "Calling official endpoints" : "Running replay"}</span> : null}
          <button type="button" onClick={onToggle} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-muted hover:bg-surface-2">{running ? <Pause className="size-3.5" aria-hidden /> : <Play className="size-3.5" aria-hidden />}{running ? "Pause flow" : "Resume flow"}</button>
        </div>
      </div>
      <div className="grid gap-2 border-y border-border bg-white p-4 sm:grid-cols-2 lg:grid-cols-7">
        {PIPELINE_STEPS.map((step, index) => {
          const Icon = step.icon;
          const active = activeStep === index;
          const complete = index < activeStep;
          return <div key={step.label} className={`relative rounded-lg border p-3 transition-all duration-500 ${active ? "scale-[1.02] border-info bg-info-soft shadow-sm" : complete ? "border-success/25 bg-success-soft/35" : "border-border bg-surface-2"}`}><div className="flex items-center gap-2"><span className={`grid size-8 place-items-center rounded-md ${active ? "bg-info text-white" : complete ? "bg-success text-white" : "bg-white text-gov-primary"}`}>{active ? <Loader2 className="size-4 animate-spin" aria-hidden /> : complete ? <CheckCircle2 className="size-4" aria-hidden /> : <Icon className="size-4" aria-hidden />}</span><span className="text-[8px] font-bold text-text-subtle">{index + 1}</span></div><p className="mt-2 text-xs font-bold text-text-strong">{step.label}</p><p className="mt-1 text-[9px] leading-4 text-text-muted">{step.detail}</p><p className="mt-2 text-[7.5px] font-bold uppercase tracking-wide text-gov-primary">{step.service}</p></div>;
        })}
      </div>
      <div className="space-y-2 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Current function: {activeStage.service}</p><p className="text-[9px] text-text-muted">Stage {activeStep + 1} of {PIPELINE_STEPS.length} | changes every second</p></div>
        {sourceHealth.map((source) => {
          const run = latest.get(source.source_id) ?? null;
          const record = run?.record_preview?.[0] ?? null;
          const failed = source.status === "failed";
          return <article key={source.source_id} className={`grid gap-3 rounded-lg border p-3 transition-colors duration-500 lg:grid-cols-[1.1fr_1.25fr_1fr_0.8fr] lg:items-center ${failed ? "border-danger/35 bg-danger-soft/45" : "border-border bg-surface-2"}`}>
            <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className={`rounded border px-1.5 py-0.5 text-[7px] font-bold uppercase ${live ? "border-success/25 bg-success-soft text-success" : "border-warn/25 bg-warn-soft text-warn"}`}>{live ? "Live public input" : "Demo synthetic input"}</span>{failed ? <span className="rounded border border-danger/30 bg-white px-1.5 py-0.5 text-[7px] font-bold uppercase text-danger">Failure retained</span> : null}</div><p className="mt-1 truncate text-xs font-bold text-text-strong">{source.label}</p><p className="mt-1 truncate font-mono text-[7.5px] text-text-subtle" title={live ? source.endpoint : "Local deterministic fixture"}>{live ? source.endpoint : "Local deterministic fixture"}</p></div>
            <div className="min-w-0"><p className="text-[7.5px] font-bold uppercase tracking-wide text-text-subtle">Accepted evidence point</p><p className="mt-1 truncate text-[10px] font-bold text-text-strong" title={record?.title ?? record?.source_record_id ?? "Awaiting receipt"}>{record?.title ?? record?.source_record_id ?? "Awaiting accepted receipt"}</p><p className="mt-1 truncate font-mono text-[7.5px] text-text-muted">{record?.source_record_id ?? source.latest_run_id ?? "No receipt"}</p></div>
            <div><p className="text-[7.5px] font-bold uppercase tracking-wide text-text-subtle">Now passing through</p><div className="mt-1 flex items-center gap-2"><span className={`grid size-8 place-items-center rounded-md ${failed ? "bg-danger text-white" : "bg-info text-white"}`}>{failed ? <AlertCircle className="size-4" aria-hidden /> : <Loader2 className="size-4 animate-spin" aria-hidden />}</span><div><p className="text-[10px] font-bold text-text-strong">{failed ? "Prior snapshot active" : activeStage.label}</p><p className="text-[8px] text-text-muted">{failed ? "Failure signal and recovery path" : activeStage.service}</p></div></div></div>
            <div><div className="flex justify-between text-[7.5px] font-bold uppercase text-text-subtle"><span>Layer progress</span><span>{activeStep + 1}/7</span></div><div className="mt-2 flex gap-1">{PIPELINE_STEPS.map((step, index) => <span key={step.label} className={`h-2 flex-1 rounded-full transition-colors duration-500 ${index < activeStep ? "bg-success" : index === activeStep ? failed ? "bg-danger" : "bg-info" : "bg-border"}`} />)}</div><p className="mt-2 truncate font-mono text-[7.5px] text-text-muted">{run?.run_id ?? "receipt pending"}</p></div>
          </article>;
        })}
        {sourceHealth.length === 0 ? <EmptyPanel title="Loading source lanes" detail="Accepted receipts from the four governed source connectors are loading." /> : null}
      </div>
    </section>
  );
}

function SourceHealthCard({ source, latest, mode, busy, onRun }: { source: PublicSourceHealth; latest: PublicAcquisitionRecord | null; mode: EvidenceMode; busy: boolean; onRun: () => void }) {
  const statusClass = source.status === "healthy" ? "border-success/30 bg-success-soft text-success" : source.status === "awaiting-first-run" ? "border-info/30 bg-info-soft text-info" : "border-danger/30 bg-danger-soft text-danger";
  const live = mode === "live";
  return (
    <article className="rounded-xl border border-border bg-white p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0"><span className={`rounded border px-1.5 py-0.5 text-[7px] font-bold uppercase ${live ? "border-success/25 bg-success-soft text-success" : "border-warn/25 bg-warn-soft text-warn"}`}>{live ? "Live API input" : "Demo fixture input"}</span><p className="mt-2 text-sm font-bold text-text-strong">{source.label}</p><p className="mt-1 text-[10px] text-text-muted">{live ? `${source.authority} | source poll every ${formatCadence(source.cadence_seconds)} | receipt screen every 1 sec` : `${source.authority} | visual event every 1 sec`}</p></div>
        <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[8px] font-bold uppercase ${statusClass}`}>{source.status.replaceAll("-", " ")}</span>
      </div>
      <p className="mt-3 text-xs leading-5 text-text-muted">{source.data_kind}</p>
      <div className={`mt-3 rounded-lg border p-3 ${live ? "border-success/20 bg-success-soft/25" : "border-warn/25 bg-warn-soft/35"}`}><p className="text-[8px] font-bold uppercase tracking-wide text-text-subtle">Input endpoint</p><p className="mt-1 break-all font-mono text-[8px] leading-4 text-text-strong">{live ? source.endpoint : "Local deterministic fixture | no external API"}</p></div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <MiniMetric label="Latest page" value={(source.latest_record_count ?? 0).toLocaleString("en-US")} />
        <MiniMetric label="Latency" value={source.average_duration_ms == null ? "Pending" : `${(source.average_duration_ms / 1000).toFixed(1)}s`} />
        <MiniMetric label="Last seen" value={formatAge(source.age_seconds)} />
      </div>
      <div className="mt-3 rounded-lg border border-border bg-surface-2 p-3">
        <div className="flex items-center justify-between gap-3"><span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Governed model</span><span className="text-[9px] font-bold text-text-strong">{source.model_version ?? source.classification_status ?? "Awaiting run"}</span></div>
        <p className="mt-1 text-[9px] leading-4 text-text-muted">{source.model_use}</p>
        {source.has_more_source_pages ? <p className="mt-2 flex items-center gap-1 text-[9px] font-bold text-warn"><AlertCircle className="size-3" aria-hidden /> More source pages exist beyond this bounded operational sample.</p> : null}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={onRun} disabled={busy} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-xs font-bold text-white hover:bg-gov-primary-dark disabled:opacity-55">{busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Play className="size-3.5" aria-hidden />} {live ? "Run source now" : "Replay source"}</button>
        {latest && live ? <Link href={`/admin/lineage/?run=${encodeURIComponent(latest.run_id)}`} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 px-3 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter"><Route className="size-3.5" aria-hidden /> Lineage</Link> : null}
        {latest && !live ? <span className="inline-flex min-h-10 items-center gap-2 rounded-md border border-warn/25 bg-warn-soft px-3 text-xs font-bold text-warn"><Route className="size-3.5" aria-hidden /> Flow shown above</span> : null}
        {live ? <a href={source.endpoint} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border px-3 text-xs font-bold text-text-muted hover:bg-surface-2">Open authority <ExternalLink className="size-3.5" aria-hidden /></a> : null}
      </div>
    </article>
  );
}

function ReviewQueue({ acquisitions, mode }: { acquisitions: PublicAcquisitionRecord[]; mode: EvidenceMode }) {
  const flags = acquisitions.flatMap((run) => (run.review_flags ?? []).map((flag) => ({ ...flag, source: run.source_label ?? run.source_id, runId: run.run_id }))).slice(0, 12);
  return <section className="rounded-xl border border-border bg-white p-5 shadow-card"><div className="flex flex-wrap items-start justify-between gap-2"><SectionHeading kicker="Governance queue" title={mode === "live" ? "Flagged live records" : "Synthetic review rehearsal"} detail="Flags are visible rules such as a changed source record, high award value, or missing narrative." /><span className={`rounded-full border px-2.5 py-1 text-[8px] font-bold uppercase ${mode === "live" ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>{mode === "live" ? "Live public" : "Demo synthetic"}</span></div><div className="mt-4 space-y-2">{flags.length ? flags.map((flag, index) => <article key={`${flag.runId}-${flag.source_record_id}-${index}`} className="rounded-lg border border-warn/25 bg-warn-soft/40 p-3"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold text-text-strong">{flag.source_record_id}</p><p className="mt-1 text-[9px] text-text-muted">{flag.source}{flag.recipient_name ? ` | ${flag.recipient_name}` : ""}</p></div>{flag.source_url && mode === "live" ? <a href={flag.source_url} target="_blank" rel="noreferrer" className="grid size-9 place-items-center rounded-md border border-border bg-white text-gov-primary"><ExternalLink className="size-3.5" aria-hidden /></a> : null}</div><div className="mt-2 flex flex-wrap gap-1">{flag.reasons.map((reason) => <span key={reason} className="rounded-full border border-warn/25 bg-white px-2 py-1 text-[8px] font-bold text-warn">{reason}</span>)}</div></article>) : <EmptyPanel title="No current review flags" detail="Accepted source records did not trigger the transparent review rules in the current pages." />}</div></section>;
}

function ModelEvidence({ acquisitions, mode }: { acquisitions: PublicAcquisitionRecord[]; mode: EvidenceMode }) {
  const runs = acquisitions.filter((run) => run.classification_summary).slice(0, 8);
  return <section className="rounded-xl border border-border bg-white p-5 shadow-card"><div className="flex flex-wrap items-start justify-between gap-2"><SectionHeading kicker="ML evidence" title="Champion classifications" detail="Each result retains the model version, input receipt, confidence summary, and review count." /><span className={`rounded-full border px-2.5 py-1 text-[8px] font-bold uppercase ${mode === "live" ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>{mode === "live" ? "Model executed" : "Classifier replay"}</span></div><div className="mt-4 space-y-2">{runs.length ? runs.map((run) => { const model = run.classification_summary!; return <article key={run.run_id} className="rounded-lg border border-border bg-surface-2 p-3"><div className="flex items-center justify-between gap-3"><div><p className="text-xs font-bold text-text-strong">{run.source_label ?? run.source_id}</p><p className="mt-1 font-mono text-[8px] text-text-muted">{model.model_version}</p></div><span className={`rounded-full border px-2 py-1 text-[8px] font-bold ${model.review_required_count ? "border-warn/30 bg-warn-soft text-warn" : "border-success/30 bg-success-soft text-success"}`}>{model.review_required_count} review</span></div><div className="mt-3 grid grid-cols-3 gap-2"><MiniMetric label="Classified" value={model.record_count.toLocaleString("en-US")} /><MiniMetric label="Mean confidence" value={`${Math.round(model.mean_confidence * 100)}%`} /><MiniMetric label="Classes" value={Object.keys(model.class_counts).length.toString()} /></div><div className="mt-2 flex flex-wrap gap-1">{Object.entries(model.class_counts).slice(0, 6).map(([label, count]) => <span key={label} className="rounded-full border border-border bg-white px-2 py-1 text-[8px] text-text-muted">{label.replaceAll("_", " ")} {count}</span>)}</div></article>; }) : <EmptyPanel title="Awaiting governed classification" detail="Run a source after the champion classifier connection is deployed to create model evidence." />}</div></section>;
}

function RunHistory({ acquisitions, mode }: { acquisitions: PublicAcquisitionRecord[]; mode: EvidenceMode }) {
  return <section className="overflow-hidden rounded-xl border border-border bg-white shadow-card"><div className="flex flex-wrap items-start justify-between gap-2 p-5"><SectionHeading kicker="Operations ledger" title="Recent acquisition receipts" detail="Every row is a retained source attempt. A failure leaves the prior accepted snapshot active." /><span className={`rounded-full border px-2.5 py-1 text-[8px] font-bold uppercase ${mode === "live" ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>{mode === "live" ? "Live receipts" : "Demo receipts"}</span></div><div className="overflow-x-auto"><table className="min-w-full text-left"><thead className="border-y border-border bg-surface-2 text-[9px] uppercase tracking-wide text-text-subtle"><tr><th className="px-4 py-3">Source</th><th className="px-4 py-3">State</th><th className="px-4 py-3">Records</th><th className="px-4 py-3">Change</th><th className="px-4 py-3">Pages</th><th className="px-4 py-3">Latency</th><th className="px-4 py-3">Model</th><th className="px-4 py-3">Evidence</th></tr></thead><tbody className="divide-y divide-border">{acquisitions.slice(0, 24).map((run) => <tr key={run.run_id} className="text-xs"><td className="px-4 py-3"><p className="font-bold text-text-strong">{run.source_label ?? run.source_id}</p><p className="mt-1 font-mono text-[8px] text-text-muted">{run.updated_at}</p></td><td className="px-4 py-3"><div className="flex flex-wrap gap-1"><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${run.status === "completed" ? "border-success/30 bg-success-soft text-success" : "border-danger/30 bg-danger-soft text-danger"}`}>{run.status}</span><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${mode === "live" ? "border-success/20 bg-white text-success" : "border-warn/20 bg-white text-warn"}`}>{mode === "live" ? "Live" : "Synthetic"}</span></div></td><td className="px-4 py-3 font-bold text-text-strong">{(run.record_count ?? 0).toLocaleString("en-US")}</td><td className="px-4 py-3 text-text-muted">+{run.added_records ?? 0} | {run.changed_records ?? 0} changed</td><td className="px-4 py-3 text-text-muted">{run.pages_fetched ?? 1}{run.has_more_source_pages ? "+" : ""}</td><td className="px-4 py-3 text-text-muted">{run.duration_ms == null ? "Pending" : `${(run.duration_ms / 1000).toFixed(1)}s`}</td><td className="px-4 py-3 text-text-muted">{run.classification_summary?.model_version ?? run.classification_status ?? "Not run"}</td><td className="px-4 py-3">{mode === "live" ? <Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="inline-flex min-h-9 items-center gap-1 rounded-md border border-border px-2 font-bold text-gov-primary hover:bg-gov-primary-lighter">Trace <ArrowRight className="size-3" aria-hidden /></Link> : <span className="inline-flex min-h-9 items-center gap-1 rounded-md border border-warn/25 bg-warn-soft px-2 font-bold text-warn">Flow above <Route className="size-3" aria-hidden /></span>}</td></tr>)}</tbody></table></div></section>;
}

function EvidenceThreadCard({ thread }: { thread: PublicEvidenceThread }) {
  const exact = thread.match_type === "exact-identity";
  return <article className={`rounded-lg border p-3 ${exact ? "border-success/25 bg-success-soft/35" : "border-info/25 bg-info-soft/35"}`}><div className="flex items-start justify-between gap-3"><div><p className={`text-[9px] font-bold uppercase tracking-wide ${exact ? "text-success" : "text-info"}`}>{exact ? "Verified exact identity" : "Explainable candidate link"}</p><p className="mt-1 font-mono text-xs font-bold text-text-strong">{thread.identity_key ?? thread.thread_id}</p><p className="mt-1 text-[9px] leading-4 text-text-muted">{thread.explanation}</p></div><span className={`shrink-0 rounded-full border bg-white px-2 py-1 text-[8px] font-bold ${exact ? "border-success/25 text-success" : "border-info/25 text-info"}`}>{exact ? "100% key match" : `${Math.round(thread.match_score * 100)}% term overlap`}</span></div>{thread.shared_terms.length ? <div className="mt-2 flex flex-wrap gap-1">{thread.shared_terms.map((term) => <span key={term} className="rounded-full border border-info/20 bg-white px-2 py-1 text-[8px] font-bold text-info">{term}</span>)}</div> : null}<div className="mt-3 space-y-2">{thread.facts.map((record) => <div key={`${record.source_id}-${record.record_id}`} className="flex items-start justify-between gap-3 rounded-md border border-border bg-white p-2"><div><p className="text-[9px] font-bold text-gov-primary">{record.source_label} | {record.record_type.replaceAll("_", " ")}</p><p className="mt-1 text-[10px] leading-4 text-text-muted">{record.title}</p><p className="mt-1 text-[8px] text-text-subtle">{record.document_class?.replaceAll("_", " ") ?? "Full artifact classification"} | {record.model_version ?? "model receipt pending"}</p></div>{record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer" className="grid size-8 shrink-0 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Open linked source ${record.record_id}`}><ExternalLink className="size-3" aria-hidden /></a> : null}</div>)}</div><div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2 text-[8px] text-text-muted"><span>Owner: {thread.owner} | Steward: {thread.steward}</span><span className="font-bold uppercase">{exact ? "Verified key" : "Analyst review required"}</span></div></article>;
}

function latestAcceptedBySource(acquisitions: PublicAcquisitionRecord[]): Map<string, PublicAcquisitionRecord> { const map = new Map<string, PublicAcquisitionRecord>(); for (const run of acquisitions) if (run.status === "completed" && !map.has(run.source_id)) map.set(run.source_id, run); return map; }
function buildDecisionSummary(latest: Map<string, PublicAcquisitionRecord>) { const records = [...latest.values()]; const previews = records.flatMap((run) => run.record_preview ?? []); return { observedFunding: previews.reduce((sum, record) => sum + (record.award_amount_usd ?? 0), 0), openOpportunities: previews.filter((record) => record.record_type === "funding_opportunity" && record.status === "posted").length, publications: previews.filter((record) => record.record_type === "publication").length, notices: previews.filter((record) => record.record_type === "regulatory_notice").length, reviewFlags: records.reduce((sum, run) => sum + (run.review_flag_count ?? 0), 0) }; }
function formatCurrency(value: number): string { if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`; if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`; if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`; return `$${Math.round(value).toLocaleString("en-US")}`; }
function formatCadence(seconds: number): string { if (seconds >= 3600) return `${seconds / 3600} hour`; if (seconds >= 60) return `${seconds / 60} min`; return `${seconds} sec`; }
function formatAge(seconds: number | null | undefined): string { if (seconds == null) return "Pending"; if (seconds < 60) return `${seconds}s`; if (seconds < 3600) return `${Math.floor(seconds / 60)}m`; return `${Math.floor(seconds / 3600)}h`; }
function HeroMetric({ label, value, detail }: { label: string; value: string; detail: string }) { return <div className="rounded-lg border border-white/15 bg-white/8 p-3"><p className="text-[8px] font-bold uppercase tracking-wide text-white/55">{label}</p><p className="mt-1 text-lg font-bold text-white">{value}</p><p className="mt-1 truncate text-[8px] text-white/55">{detail}</p></div>; }
function MiniMetric({ label, value }: { label: string; value: string }) { return <div className="rounded-md border border-border bg-white p-2"><p className="text-[7.5px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 truncate text-[10px] font-bold text-text-strong" title={value}>{value}</p></div>; }
function DecisionMetric({ label, value, detail }: { label: string; value: string; detail: string }) { return <div className="rounded-lg border border-border bg-surface-2 p-3"><p className="text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 text-lg font-bold text-text-strong">{value}</p><p className="mt-1 text-[8px] text-text-muted">{detail}</p></div>; }
function SectionHeading({ kicker, title, detail }: { kicker: string; title: string; detail: string }) { return <div><p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">{kicker}</p><h2 className="mt-1 text-lg font-bold text-text-strong">{title}</h2><p className="mt-1 text-xs leading-5 text-text-muted">{detail}</p></div>; }
function EmptyPanel({ title, detail, actionHref, actionLabel }: { title: string; detail: string; actionHref?: string; actionLabel?: string }) { return <div className="rounded-lg border border-dashed border-border bg-surface-2 p-4 text-center"><Layers3 className="mx-auto size-5 text-text-subtle" aria-hidden /><p className="mt-2 text-xs font-bold text-text-strong">{title}</p><p className="mx-auto mt-1 max-w-lg text-[10px] leading-4 text-text-muted">{detail}</p>{actionHref && actionLabel ? <Link href={actionHref} className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 bg-white px-3 text-xs font-bold text-gov-primary">{actionLabel} <ArrowRight className="size-3.5" aria-hidden /></Link> : null}</div>; }

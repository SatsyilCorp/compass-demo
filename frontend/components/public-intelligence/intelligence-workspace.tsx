"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Activity,
  ArrowUpRight,
  BadgeCheck,
  BrainCircuit,
  CheckCircle2,
  DatabaseZap,
  ExternalLink,
  FileSearch,
  Fingerprint,
  Landmark,
  Loader2,
  LockKeyhole,
  Network,
  Orbit,
  Quote,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Wifi,
  WifiOff,
} from "lucide-react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/shell/page-header";
import {
  getPublicModelExecutionsApi,
  getPublicAcquisitionsApi,
  getPublicIntelligenceSnapshotApi,
  postPublicAcquisitionRunApi,
  postPublicIntelligenceExplainApi,
  USE_MOCK,
  type PublicAcquisitionList,
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import type { PublicModelExecutionReceipt } from "@/lib/mlops/model-execution";
import { PUBLIC_INTELLIGENCE_SNAPSHOT } from "@/lib/public-intelligence/demo-snapshot";
import {
  mergePublicIntelligenceSnapshot,
  PUBLIC_EXPLANATION_MAX_QUESTION_CHARS,
  PUBLIC_EXPLANATION_MAX_TOP_K,
  safeHttpsUrl,
} from "@/lib/public-intelligence/live";
import { SOURCE_ACQUISITION_GROUPS } from "@/lib/public-intelligence/source-acquisition";
import type { SourceAcquisitionState } from "@/lib/public-intelligence/source-acquisition";
import type {
  EvidenceClass,
  IntelligenceSnapshot,
  PublicIntelligenceExplanationResponse,
  PublicIntelligenceSnapshotResponse,
} from "@/lib/public-intelligence/types";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});
const number = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const exactNumber = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 });

type View = "portfolio" | "programs" | "explain" | "models" | "sources";
type SnapshotState = "loading" | "live" | "fallback";
type ModelSignalState = "loading" | "live" | "unavailable";

export function IntelligenceWorkspace() {
  const auth = useAppAuth();
  const [view, setView] = useState<View>("portfolio");
  const [selectedProgram, setSelectedProgram] = useState(PUBLIC_INTELLIGENCE_SNAPSHOT.programs[0]?.id ?? "");
  const [liveSnapshot, setLiveSnapshot] = useState<PublicIntelligenceSnapshotResponse | null>(null);
  const [snapshotState, setSnapshotState] = useState<SnapshotState>(USE_MOCK ? "fallback" : "loading");
  const [snapshotMessage, setSnapshotMessage] = useState(
    USE_MOCK
      ? "Local replay mode uses the bundled, last-known public snapshot."
      : "Verifying the protected public evidence manifest and index.",
  );
  const [refreshing, setRefreshing] = useState(false);
  const [latestModelExecution, setLatestModelExecution] = useState<PublicModelExecutionReceipt | null>(null);
  const [modelSignalState, setModelSignalState] = useState<ModelSignalState>(USE_MOCK ? "unavailable" : "loading");
  const [modelSignalMessage, setModelSignalMessage] = useState(
    USE_MOCK
      ? "Live SageMaker execution receipts require the deployed AWS environment."
      : "Loading governed SageMaker prediction receipts.",
  );
  const [modelSignalsRefreshing, setModelSignalsRefreshing] = useState(false);
  const requestSequence = useRef(0);
  const modelRequestSequence = useRef(0);
  const latestModelExecutionRef = useRef<PublicModelExecutionReceipt | null>(null);
  const liveSnapshotRef = useRef<PublicIntelligenceSnapshotResponse | null>(null);
  const snapshot = useMemo(
    () => mergePublicIntelligenceSnapshot(PUBLIC_INTELLIGENCE_SNAPSHOT, liveSnapshot),
    [liveSnapshot],
  );
  const program = snapshot.programs.find((item) => item.id === selectedProgram) ?? snapshot.programs[0];

  const loadSnapshot = useCallback(async () => {
    const requestId = ++requestSequence.current;
    if (USE_MOCK) {
      setSnapshotState("fallback");
      setSnapshotMessage("Local replay mode uses the bundled, last-known public snapshot.");
      return;
    }
    if (!auth.idToken) {
      setSnapshotState("fallback");
      setSnapshotMessage("The protected session is not ready, so the bundled last-known snapshot remains visible.");
      return;
    }

    setRefreshing(true);
    if (!liveSnapshotRef.current) {
      setSnapshotState("loading");
      setSnapshotMessage("Verifying the protected public evidence manifest and index.");
    }
    try {
      const response = await getPublicIntelligenceSnapshotApi();
      if (requestId !== requestSequence.current) return;
      liveSnapshotRef.current = response;
      setLiveSnapshot(response);
      setSnapshotState("live");
      setSnapshotMessage("Checksummed public evidence loaded from the protected AWS API.");
    } catch {
      if (requestId !== requestSequence.current) return;
      if (liveSnapshotRef.current) {
        setSnapshotState("live");
        setSnapshotMessage("The last verified live response remains visible because revalidation did not complete.");
      } else {
        setSnapshotState("fallback");
        setSnapshotMessage("Live verification is unavailable, so the bundled last-known snapshot remains visible.");
      }
    } finally {
      if (requestId === requestSequence.current) setRefreshing(false);
    }
  }, [auth.idToken]);

  const loadModelSignals = useCallback(async () => {
    const requestId = ++modelRequestSequence.current;
    if (USE_MOCK || !auth.idToken) {
      setModelSignalState("unavailable");
      setModelSignalMessage(
        USE_MOCK
          ? "Live SageMaker execution receipts require the deployed AWS environment."
          : "A verified signed-in session is required to read model execution receipts.",
      );
      return;
    }
    setModelSignalsRefreshing(true);
    if (!latestModelExecutionRef.current) setModelSignalState("loading");
    try {
      const history = await getPublicModelExecutionsApi();
      if (requestId !== modelRequestSequence.current) return;
      const completed = history.executions.find((item) => item.status === "COMPLETED") ?? null;
      latestModelExecutionRef.current = completed;
      setLatestModelExecution(completed);
      if (completed) {
        setModelSignalState("live");
        setModelSignalMessage("Latest completed SageMaker Batch Transform receipt verified through the protected AWS API.");
      } else {
        setModelSignalState("unavailable");
        setModelSignalMessage("No completed governed prediction receipt is available yet.");
      }
    } catch {
      if (requestId !== modelRequestSequence.current) return;
      setModelSignalState(latestModelExecutionRef.current ? "live" : "unavailable");
      setModelSignalMessage(
        latestModelExecutionRef.current
          ? "The last verified prediction receipt remains visible because revalidation did not complete."
          : "The protected model execution history is currently unavailable.",
      );
    } finally {
      if (requestId === modelRequestSequence.current) setModelSignalsRefreshing(false);
    }
  }, [auth.idToken]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadSnapshot(), 0);
    return () => window.clearTimeout(timer);
  }, [loadSnapshot]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadModelSignals(), 0);
    return () => window.clearTimeout(timer);
  }, [loadModelSignals]);

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Public evidence intelligence | Multi-source governed snapshot"
        title="ONR portfolio intelligence"
        icon={<Orbit className="size-5" aria-hidden />}
        lead="The accepted evidence package contains public award, opportunity, SBIR, publication, dataset, and technical-report snapshots with source-level provenance. One funding model is registered as a review-only candidate, while unvalidated program-level predictions remain hidden."
        actions={
          <div className="flex items-center gap-2 rounded-md border border-success/30 bg-success-soft px-3 py-2 text-xs font-bold text-success">
            <ShieldCheck className="size-4" aria-hidden />
            Public data only
          </div>
        }
      />

      <SnapshotConnection
        state={snapshotState}
        message={snapshotMessage}
        live={liveSnapshot}
        refreshing={refreshing}
        onRefresh={() => void loadSnapshot()}
      />

      <EvidenceBoundary snapshot={snapshot} />

      <div className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-surface p-1 shadow-soft" role="tablist" aria-label="Intelligence workspace views">
        {([
          ["portfolio", "Portfolio signal"],
          ["programs", "Program explorer"],
          ["explain", "Cited explainer"],
          ["models", "Model evidence"],
          ["sources", "Source ledger"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={view === id}
            onClick={() => setView(id)}
            className={`min-h-11 shrink-0 rounded-md px-4 text-xs font-bold transition-colors ${view === id ? "bg-gov-primary text-white" : "text-text-muted hover:bg-surface-2 hover:text-text-strong"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {view === "portfolio" ? <PortfolioView snapshot={snapshot} /> : null}
      {view === "programs" ? <ProgramsView snapshot={snapshot} selected={selectedProgram} onSelect={setSelectedProgram} program={program} /> : null}
      {view === "explain" ? <CitedExplainer canCallLive={!USE_MOCK && Boolean(auth.idToken)} snapshotState={snapshotState} liveSnapshotId={liveSnapshot?.snapshot_id ?? null} /> : null}
      {view === "models" ? (
        <ModelsView
          snapshot={snapshot}
          execution={latestModelExecution}
          signalState={modelSignalState}
          signalMessage={modelSignalMessage}
          refreshing={modelSignalsRefreshing}
          onRefresh={() => void loadModelSignals()}
        />
      ) : null}
      {view === "sources" ? <SourcesView snapshot={snapshot} /> : null}
    </div>
  );
}

function SnapshotConnection({
  state,
  message,
  live,
  refreshing,
  onRefresh,
}: {
  state: SnapshotState;
  message: string;
  live: PublicIntelligenceSnapshotResponse | null;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const liveState = state === "live";
  const loading = state === "loading";
  const Icon = liveState ? Wifi : loading ? Loader2 : WifiOff;
  const style = liveState
    ? "border-success/30 bg-success-soft text-success"
    : loading
      ? "border-info/30 bg-info-soft text-info"
      : "border-warn/30 bg-warn-soft text-warn";
  const label = liveState
    ? "Live backend verified"
    : loading
      ? "Verifying protected snapshot"
      : "Bundled last-known snapshot";

  return (
    <section className={`rounded-lg border px-4 py-3 ${style}`} aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Icon className={`mt-0.5 size-4 shrink-0 ${loading ? "animate-spin" : ""}`} aria-hidden />
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em]">{label}</p>
            <p className="mt-1 text-xs leading-5 text-current/80">{message}</p>
            {live ? (
              <p className="mt-1 break-words font-mono text-[10px] text-current/75">
                {live.snapshot_id} | {exactNumber.format(live.record_count)} bounded serving projection records | {live.identity_scope.role} / {live.identity_scope.org_unit}
              </p>
            ) : null}
          </div>
        </div>
        {!USE_MOCK ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-current/25 bg-white/70 px-3 text-xs font-bold text-current hover:bg-white disabled:cursor-wait disabled:opacity-60"
          >
            <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} aria-hidden />
            Revalidate
          </button>
        ) : null}
      </div>
    </section>
  );
}

function EvidenceBoundary({ snapshot }: { snapshot: IntelligenceSnapshot }) {
  const persistedSourceCount = snapshot.sources.filter((source) => source.status === "persisted").length;
  return (
    <section className="grid gap-px overflow-hidden rounded-xl border border-border bg-border shadow-card lg:grid-cols-[1.3fr_repeat(4,1fr)]">
      <div className="bg-gov-primary px-5 py-4 text-white">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-gold-light">Evidence boundary</p>
        <p className="mt-2 text-sm font-bold">Public ONR-related candidate evidence</p>
        <p className="mt-1 text-[11px] leading-5 text-white/65">Not an ONR internal system and not a confirmed internal performance record.</p>
      </div>
      <Metric label="Grants" value={number.format(snapshot.corpus.awards)} detail="retrieved candidate records" Icon={FileSearch} />
      <Metric label="Contracts" value={number.format(snapshot.corpus.contracts)} detail="retrieved candidate records" Icon={Landmark} />
      <Metric label="Candidate award value" value={money.format(snapshot.corpus.candidateAwardValueUsd)} detail="summed award amounts" Icon={Network} />
      <Metric label="Sources" value={String(persistedSourceCount)} detail="persisted public source families" Icon={DatabaseZap} />
    </section>
  );
}

function Metric({ label, value, detail, Icon }: { label: string; value: string; detail: string; Icon: typeof FileSearch }) {
  return (
    <div className="bg-surface px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">{label}</p>
        <Icon className="size-4 text-gold-ink" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-bold text-text-strong">{value}</p>
      <p className="mt-1 text-[10px] text-text-muted">{detail}</p>
    </div>
  );
}

function PortfolioView({ snapshot }: { snapshot: IntelligenceSnapshot }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
      <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Capital flow</p>
            <h2 className="mt-1 text-lg font-bold text-text-strong">Observed candidate-scope obligations</h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">Values are from the persisted USAspending spending-over-time response for Department of the Navy plus keyword N00014 candidate scope. They are not an authoritative inventory of every ONR obligation.</p>
          </div>
          <EvidencePill kind="observed" />
        </div>
        <div className="mt-5 h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={snapshot.fundingFlow} margin={{ top: 12, right: 16, bottom: 4, left: 6 }}>
              <CartesianGrid stroke="#e8edf1" vertical={false} />
              <XAxis dataKey="fiscalYear" tick={{ fontSize: 11, fill: "#52626f" }} axisLine={{ stroke: "#b8c3cd" }} tickLine={false} />
              <YAxis tickFormatter={(value) => money.format(value)} tick={{ fontSize: 11, fill: "#52626f" }} axisLine={false} tickLine={false} width={62} />
              <Tooltip formatter={(value) => [money.format(Number(value)), "Funding"]} contentStyle={{ border: "1px solid #d9e0e6", borderRadius: 6, fontSize: 12 }} />
              <Line type="monotone" dataKey="observedUsd" stroke="#10496f" strokeWidth={3} dot={{ r: 3, fill: "#10496f" }} connectNulls={false} name="Observed" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-2 flex flex-wrap gap-4 text-[10px] text-text-muted">
          <span className="inline-flex items-center gap-2"><span className="h-0.5 w-5 bg-gov-primary-vivid" /> Observed source value</span>
          <span>FY2026 is partial; the USAspending cutoff is 2026-08-11</span>
          <span className="font-bold text-warn">Candidate model trained. No forecast is published until approval.</span>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Technology taxonomy</p>
            <h2 className="mt-1 text-lg font-bold text-text-strong">Classification evidence</h2>
          </div>
          <Sparkles className="size-5 text-gold-ink" aria-hidden />
        </div>
        {snapshot.technologyAreas.length > 0 ? <div className="mt-5 space-y-3">
          {snapshot.technologyAreas.map((area, index) => (
            <article key={area.id} className="rounded-lg border border-border bg-surface-2/50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-md bg-gov-primary text-xs font-bold text-white">{index + 1}</span>
                  <div className="min-w-0">
                    <h3 className="truncate text-xs font-bold text-text-strong">{area.label}</h3>
                    <p className="mt-1 text-[10px] text-text-muted">{formatCount(area.awards)} awards | {formatCount(area.publications)} works</p>
                  </div>
                </div>
                <span className="shrink-0 rounded-full border border-success/25 bg-success-soft px-2 py-1 text-[10px] font-bold text-success">{formatNullablePercent(area.velocityPct === null ? null : area.velocityPct / 100)}</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-[10px]">
                <span className="rounded-md bg-white px-2 py-1.5 text-text-muted">Funding <strong className="text-text-strong">{formatMoney(area.fundingUsd)}</strong></span>
                <span className="rounded-md bg-white px-2 py-1.5 text-text-muted">Transition <strong className="text-text-strong">{formatNullablePercent(area.transitionProbability)}</strong></span>
              </div>
            </article>
          ))}
        </div> : <div className="mt-5 rounded-lg border border-warn/25 bg-warn-soft p-4">
          <div className="flex gap-3">
            <AlertCircle className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />
            <div>
              <p className="text-xs font-bold text-text-strong">Technology-area results are unavailable</p>
              <p className="mt-1 text-xs leading-5 text-text-muted">No reviewed taxonomy classifier has been trained on the persisted evidence. Funding, velocity, and transition values remain hidden until classification and validation complete.</p>
            </div>
          </div>
        </div>}
      </section>

      <section className="rounded-xl border border-border bg-gov-primary p-5 text-white shadow-card xl:col-span-2">
        <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr] lg:items-center">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-gold-light">Decision story</p>
            <h2 className="mt-2 text-xl font-bold">Production decision contract</h2>
            <p className="mt-2 text-xs leading-5 text-white/65">Compass is designed to link awards, organizations, topics, publications, phases, and time. Validated models may rank evidence only after training and review. Analysts retain the decision.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-4">
            {["Source records", "Resolved entities", "Model signals", "Cited decision"].map((label, index) => (
              <div key={label} className="relative rounded-lg border border-white/10 bg-white/[0.06] px-3 py-4 text-center">
                <p className="font-mono text-[10px] text-gold-light">0{index + 1}</p>
                <p className="mt-2 text-xs font-bold">{label}</p>
                {index < 3 ? <ArrowUpRight className="absolute -right-2 top-1/2 hidden size-4 -translate-y-1/2 text-gold-light sm:block" aria-hidden /> : null}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function ProgramsView({
  snapshot,
  selected,
  onSelect,
  program,
}: {
  snapshot: IntelligenceSnapshot;
  selected: string;
  onSelect: (id: string) => void;
  program: IntelligenceSnapshot["programs"][number] | undefined;
}) {
  if (!program) return null;
  return (
    <div className="grid gap-5 xl:grid-cols-[0.9fr_1.4fr]">
      <section className="rounded-xl border border-border bg-surface p-4 shadow-card">
        <p className="px-1 text-[10px] font-bold uppercase tracking-wide text-gold-ink">Persisted candidate records</p>
        <div className="mt-3 space-y-2">
          {snapshot.programs.map((item) => (
            <button key={item.id} type="button" onClick={() => onSelect(item.id)} className={`w-full rounded-lg border p-3 text-left transition-colors ${selected === item.id ? "border-gov-primary bg-gov-primary-lighter" : "border-border bg-white hover:bg-surface-2"}`}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[10px] font-bold text-gold-ink">{item.id}</span>
                <span className="text-[10px] font-bold text-text-muted">{money.format(item.awardAmountUsd)}</span>
              </div>
              <p className="mt-2 line-clamp-2 text-xs font-bold leading-5 text-text-strong">{item.title}</p>
              <p className="mt-1 truncate text-[10px] text-text-muted">{item.recipient}</p>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[11px] font-bold text-gold-ink">{program.id}</p>
            <h2 className="mt-2 max-w-3xl text-xl font-bold leading-7 text-text-strong">{program.title}</h2>
            <p className="mt-2 text-sm text-text-muted">{program.recipient}</p>
          </div>
          <a href={program.sourceUrl} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Open source record <ExternalLink className="size-3.5" aria-hidden /></a>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <ProgramMetric label="Observed award value" value={money.format(program.awardAmountUsd)} kind="observed" />
          <ProgramMetric label="Transition indicator" value={formatNullablePercent(program.transitionProbability)} kind="predicted" />
          <ProgramMetric label="Impact percentile" value={formatPercentile(program.impactPercentile)} kind="predicted" />
          <ProgramMetric label="Model confidence" value={formatNullablePercent(program.confidence)} kind="predicted" />
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface-2/55 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">Observed record</p>
            <dl className="mt-3 space-y-3 text-xs">
              <Row label="Source" value={program.source} />
              <Row label="Period" value={`${program.startDate} to ${program.endDate}`} />
              <Row label="Technology area" value={program.technologyArea ?? "Not classified"} />
              <Row label="Candidate scope" value={program.scopeNote} />
            </dl>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/55 p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">Observed facts available for analysis</p>
            <ul className="mt-3 space-y-2">
              {program.observedFacts.map((fact) => <li key={fact} className="flex gap-2 text-xs leading-5 text-text-muted"><CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />{fact}</li>)}
            </ul>
          </div>
        </div>

        <div className="mt-5 rounded-lg border border-info/25 bg-info-soft p-4">
          <div className="flex gap-3">
            <BrainCircuit className="mt-0.5 size-5 shrink-0 text-info" aria-hidden />
            <div>
              <p className="text-xs font-bold text-text-strong">Grounded explanation contract</p>
              <p className="mt-1 text-xs leading-5 text-text-muted">No model score is available yet. A future assistant may explain a validated score only by using retrieved source passages and model features, attaching record-level citations, stating uncertainty, and refusing unsupported claims.</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

const EXPLANATION_SUGGESTIONS = [
  "What public records describe autonomous or underwater research?",
  "Where is funding represented in this public candidate scope?",
  "What evidence is available for SBIR transition analysis?",
];

function CitedExplainer({
  canCallLive,
  snapshotState,
  liveSnapshotId,
}: {
  canCallLive: boolean;
  snapshotState: SnapshotState;
  liveSnapshotId: string | null;
}) {
  const [draft, setDraft] = useState("");
  const [topK, setTopK] = useState(5);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PublicIntelligenceExplanationResponse | null>(null);

  async function ask(question: string) {
    const normalized = question.replace(/\s+/g, " ").trim();
    if (pending) return;
    if (!normalized) {
      setError("Enter a question about the governed public evidence.");
      return;
    }
    if (normalized.length > PUBLIC_EXPLANATION_MAX_QUESTION_CHARS) {
      setError(`Questions are limited to ${PUBLIC_EXPLANATION_MAX_QUESTION_CHARS.toLocaleString()} characters.`);
      return;
    }
    if (!canCallLive) {
      setError("The cited explanation service requires a verified signed-in live session.");
      return;
    }

    setPending(true);
    setError(null);
    setResult(null);
    try {
      const response = await postPublicIntelligenceExplainApi({
        question: normalized,
        top_k: Math.min(PUBLIC_EXPLANATION_MAX_TOP_K, Math.max(1, topK)),
      });
      setResult(response);
      setDraft(normalized);
    } catch {
      setError("The protected explanation service did not return a valid response. The public evidence display remains available.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.8fr_1.4fr]">
      <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Bounded retrieval</p>
            <h2 className="mt-1 text-lg font-bold text-text-strong">Ask public evidence</h2>
          </div>
          <BrainCircuit className="size-5 text-gold-ink" aria-hidden />
        </div>
        <p className="mt-2 text-xs leading-5 text-text-muted">
          The protected service retrieves at most {PUBLIC_EXPLANATION_MAX_TOP_K} records from the checksummed serving index. It returns a refusal when the evidence cannot support an answer.
        </p>

        <div className={`mt-4 flex gap-2 rounded-md border p-3 text-[10px] leading-5 ${canCallLive ? "border-success/25 bg-success-soft text-success" : "border-warn/25 bg-warn-soft text-warn"}`}>
          {canCallLive ? <Wifi className="mt-0.5 size-3.5 shrink-0" aria-hidden /> : <LockKeyhole className="mt-0.5 size-3.5 shrink-0" aria-hidden />}
          {canCallLive
            ? `Protected explanation route ready${liveSnapshotId ? ` for ${liveSnapshotId}` : ""}.`
            : snapshotState === "loading"
              ? "Waiting for the protected session and live snapshot verification."
              : "Bundled evidence is read-only. Sign in to the live backend to generate a cited explanation."}
        </div>

        <div className="mt-5 space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">Suggested questions</p>
          {EXPLANATION_SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={pending}
              onClick={() => {
                setDraft(suggestion);
                void ask(suggestion);
              }}
              className="flex min-h-11 w-full items-start gap-2 rounded-md border border-border bg-white px-3 py-2 text-left text-xs leading-5 text-text-muted transition-colors hover:border-border-strong hover:bg-surface-2 disabled:opacity-50"
            >
              <Sparkles className="mt-0.5 size-3.5 shrink-0 text-gold-ink" aria-hidden />
              {suggestion}
            </button>
          ))}
        </div>

        <form
          className="mt-5 border-t border-border pt-4"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(draft);
          }}
        >
          <label htmlFor="public-evidence-question" className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">
            Question
          </label>
          <textarea
            id="public-evidence-question"
            rows={5}
            maxLength={PUBLIC_EXPLANATION_MAX_QUESTION_CHARS}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask about a topic, public award, opportunity, or research output."
            className="mt-2 w-full resize-y rounded-md border border-border bg-white px-3 py-2 text-sm leading-6 text-text-strong placeholder:text-text-subtle focus:border-gov-primary focus:outline-none"
          />
          <div className="mt-2 flex items-center justify-between gap-3 text-[10px] text-text-subtle">
            <span>{draft.length.toLocaleString()} / {PUBLIC_EXPLANATION_MAX_QUESTION_CHARS.toLocaleString()} characters</span>
            <label className="inline-flex items-center gap-2 font-bold">
              Evidence limit
              <select
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value))}
                className="min-h-9 rounded border border-border bg-white px-2 text-xs text-text-strong"
                aria-label="Maximum evidence records"
              >
                {[3, 5, 6].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
          </div>
          <button
            type="submit"
            disabled={pending || draft.trim().length === 0}
            className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:opacity-45"
          >
            {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
            {pending ? "Retrieving and grounding" : "Generate cited explanation"}
          </button>
        </form>
      </section>

      <section className="min-h-[520px] rounded-xl border border-border bg-surface p-5 shadow-card" aria-live="polite">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Explanation receipt</p>
            <h2 className="mt-1 text-lg font-bold text-text-strong">Answer, citations, and uncertainty</h2>
          </div>
          {result ? (
            <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${result.grounded ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>
              {result.grounded ? "Grounded" : "Refused safely"}
            </span>
          ) : null}
        </div>

        {pending ? (
          <div className="grid min-h-[360px] place-items-center text-center">
            <div>
              <Loader2 className="mx-auto size-7 animate-spin text-gov-primary" aria-hidden />
              <p className="mt-3 text-sm font-bold text-text-strong">Searching governed public evidence</p>
              <p className="mt-1 text-xs text-text-muted">The request is bounded and will return citations or a refusal.</p>
            </div>
          </div>
        ) : error ? (
          <div className="mt-5 flex gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-danger" role="alert">
            <AlertCircle className="mt-0.5 size-5 shrink-0" aria-hidden />
            <div>
              <p className="text-xs font-bold">Explanation unavailable</p>
              <p className="mt-1 text-xs leading-5">{error}</p>
            </div>
          </div>
        ) : result ? (
          <ExplanationResult result={result} />
        ) : (
          <div className="grid min-h-[360px] place-items-center text-center">
            <div className="max-w-md">
              <Quote className="mx-auto size-7 text-gold-ink" aria-hidden />
              <p className="mt-3 text-sm font-bold text-text-strong">No explanation requested yet</p>
              <p className="mt-1 text-xs leading-5 text-text-muted">Ask a supported public-evidence question to see the answer, source records, model path, uncertainty, and run receipt together.</p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function ExplanationResult({ result }: { result: PublicIntelligenceExplanationResponse }) {
  return (
    <div className="mt-5 space-y-5">
      <div className={`rounded-lg border p-4 ${result.refused ? "border-warn/30 bg-warn-soft" : "border-info/25 bg-info-soft"}`}>
        <div className="flex gap-3">
          {result.refused ? <LockKeyhole className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden /> : <BrainCircuit className="mt-0.5 size-5 shrink-0 text-info" aria-hidden />}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">
              {result.refused ? result.refusal_code ?? "Unsupported request" : "Grounded response"}
            </p>
            <p className="mt-2 text-sm leading-6 text-text-strong">{result.answer}</p>
          </div>
        </div>
      </div>

      {result.citations.length > 0 ? (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">Record citations</p>
          <ol className="mt-3 grid gap-3 lg:grid-cols-2">
            {result.citations.map((citation) => {
              const sourceUrl = safeHttpsUrl(citation.source_url);
              return (
                <li key={`${citation.record_id}:${citation.record_sha256}`} className="rounded-lg border border-border bg-surface-2/55 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-mono text-[10px] font-bold text-gold-ink">{citation.citation_token}</p>
                      <h3 className="mt-2 text-xs font-bold leading-5 text-text-strong">{citation.title}</h3>
                    </div>
                    {sourceUrl ? (
                      <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Open cited public record ${citation.record_id}`}
                        className="grid size-11 shrink-0 place-items-center rounded-md border border-border bg-white text-gov-primary hover:bg-surface-2"
                      >
                        <ExternalLink className="size-4" aria-hidden />
                      </a>
                    ) : (
                      <span className="grid size-11 shrink-0 place-items-center rounded-md border border-border bg-white text-text-subtle" title="Source URL did not pass the HTTPS safety check">
                        <LockKeyhole className="size-4" aria-hidden />
                      </span>
                    )}
                  </div>
                  <dl className="mt-3 grid gap-2 text-[10px] text-text-muted sm:grid-cols-2">
                    <Row label="Record" value={citation.record_id} />
                    <Row label="Source" value={citation.source_id} />
                    <Row label="Evidence" value={citation.evidence_class.replaceAll("_", " ")} />
                    <Row label="Snapshot" value={citation.snapshot_id} />
                  </dl>
                </li>
              );
            })}
          </ol>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border p-4 text-xs text-text-muted">
          No record citations were returned. The service refused to generate an unsupported answer.
        </div>
      )}

      <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
        <ModelFact label="Generation" value={result.generation.model_id ?? result.generation.provider ?? "none"} />
        <ModelFact label="Evidence class" value={result.evidence_class.replaceAll("_", " ")} />
        <ModelFact label="Uncertainty" value={result.uncertainty.level || "not reported"} />
        <ModelFact label="Run receipt" value={result.explanation_run_id} />
      </div>
      <div className="rounded-lg border border-border bg-surface-2/55 p-4">
        <p className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">Uncertainty and limits</p>
        <p className="mt-2 text-xs leading-5 text-text-muted">{result.uncertainty.basis}</p>
        {result.uncertainty.limitations.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {result.uncertainty.limitations.map((limitation) => (
              <li key={limitation} className="flex gap-2 text-xs leading-5 text-text-muted">
                <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-warn" aria-hidden />
                {limitation}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

function ModelsView({
  snapshot,
  execution,
  signalState,
  signalMessage,
  refreshing,
  onRefresh,
}: {
  snapshot: IntelligenceSnapshot;
  execution: PublicModelExecutionReceipt | null;
  signalState: ModelSignalState;
  signalMessage: string;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-4">
      <TransitionSignalsPanel
        execution={execution}
        state={signalState}
        message={signalMessage}
        refreshing={refreshing}
        onRefresh={onRefresh}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        {snapshot.models.map((model) => (
          <article key={model.id} className="rounded-xl border border-border bg-surface p-5 shadow-card">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2"><EvidencePill kind={model.evidenceClass} /><span className="rounded-full border border-border bg-surface-2 px-2 py-1 text-[9px] font-bold uppercase text-text-muted">{model.status.replaceAll("-", " ")}</span></div>
                <h2 className="mt-3 text-lg font-bold text-text-strong">{model.name}</h2>
              </div>
              <BrainCircuit className="size-5 text-gold-ink" aria-hidden />
            </div>
            <p className="mt-2 text-xs leading-5 text-text-muted">{model.objective}</p>
            <dl className="mt-4 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2">
              <ModelFact label="Algorithm" value={model.algorithm} />
              <ModelFact label="Authentic target" value={model.target} />
              <ModelFact label="Evaluation" value={model.metric} />
              <ModelFact label="Evidence" value={model.metricLabel} />
            </dl>
            <div className="mt-4 flex gap-2 rounded-md border border-warn/25 bg-warn-soft p-3 text-[10px] leading-5 text-warn"><AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />{model.caveat}</div>
          </article>
        ))}
      </div>
    </div>
  );
}

function TransitionSignalsPanel({
  execution,
  state,
  message,
  refreshing,
  onRefresh,
}: {
  execution: PublicModelExecutionReceipt | null;
  state: ModelSignalState;
  message: string;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const predictions = execution?.output?.predictions ?? [];
  const positiveCount = predictions.filter((item) => item.candidateLabel === 1).length;
  const highest = predictions.reduce(
    (current, item) => item.observedPublicTransitionProbability > current ? item.observedPublicTransitionProbability : current,
    0,
  );
  const inputByRecord = new Map(
    (execution?.input.records ?? []).map((item) => [item.recordId, item]),
  );
  const live = state === "live" && Boolean(execution);

  return (
    <section className="overflow-hidden rounded-xl border border-gov-primary/25 bg-surface shadow-card">
      <div className="bg-gov-primary px-5 py-5 text-white">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-gold-light">Live SageMaker signals</span>
              <span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-white/75">Human review required</span>
            </div>
            <h2 className="mt-3 text-xl font-bold">Governed public transition predictions</h2>
            <p className="mt-2 text-xs leading-5 text-white/70">A registered SageMaker candidate scores newer, label-excluded public Navy Phase I records. The result is a public transition proxy, not mission success, source-selection advice, or an automated decision.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={onRefresh} disabled={refreshing} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-white/20 bg-white/10 px-3 text-xs font-bold text-white hover:bg-white/15 disabled:opacity-60">
              <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} aria-hidden />
              Revalidate
            </button>
            <a href="/admin/mlops/" className="inline-flex min-h-11 items-center gap-2 rounded-md bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">
              <Activity className="size-3.5" aria-hidden /> Run governed scoring
            </a>
          </div>
        </div>
      </div>

      <div className={`border-b px-5 py-3 text-xs ${live ? "border-success/25 bg-success-soft text-success" : state === "loading" ? "border-info/25 bg-info-soft text-info" : "border-warn/25 bg-warn-soft text-warn"}`}>
        <div className="flex items-start gap-2">
          {state === "loading" ? <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin" aria-hidden /> : live ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden /> : <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />}
          <span>{message}</span>
        </div>
      </div>

      {execution && execution.output ? (
        <div className="p-5">
          <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 xl:grid-cols-4">
            <ModelFact label="Current public records" value={String(execution.output.predictionCount)} />
            <ModelFact label="Positive proxy signals" value={String(positiveCount)} />
            <ModelFact label="Highest probability" value={percent.format(highest)} />
            <ModelFact label="Registry state" value={`${execution.model.approvalStatus} | v${execution.model.packageVersion}`} />
          </div>

          <div className="mt-4 overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[860px] border-collapse text-left">
              <thead className="bg-surface-2 text-[9px] font-bold uppercase tracking-wide text-text-subtle">
                <tr>
                  <th className="px-4 py-3">Public Navy award</th>
                  <th className="px-4 py-3">Phase I event</th>
                  <th className="px-4 py-3">Transition probability</th>
                  <th className="px-4 py-3">Candidate signal</th>
                  <th className="px-4 py-3">Disposition</th>
                </tr>
              </thead>
              <tbody>
                {execution.output.predictions.map((prediction) => {
                  const input = inputByRecord.get(prediction.recordId);
                  return (
                    <tr key={prediction.recordId} className="border-t border-border bg-white text-xs">
                      <td className="px-4 py-3">
                        <p className="font-mono text-[10px] font-bold text-gov-primary">{input?.sourceRecordIds[0] ?? prediction.recordId}</p>
                        <p className="mt-1 font-mono text-[9px] text-text-subtle">{prediction.recordId}</p>
                      </td>
                      <td className="px-4 py-3 text-text-muted">{formatDateTime(input?.eventTime)}</td>
                      <td className="px-4 py-3">
                        <p className="font-bold text-text-strong">{percent.format(prediction.observedPublicTransitionProbability)}</p>
                        <div className="mt-2 h-1.5 w-28 overflow-hidden rounded-full bg-surface-3"><div className="h-full rounded-full bg-gov-primary" style={{ width: `${Math.round(prediction.observedPublicTransitionProbability * 100)}%` }} /></div>
                      </td>
                      <td className="px-4 py-3 font-semibold text-text-strong">{prediction.candidateLabel === 1 ? "Positive proxy" : "No positive proxy"}</td>
                      <td className="px-4 py-3"><span className="rounded-full border border-warn/30 bg-warn-soft px-2 py-1 text-[9px] font-bold uppercase text-warn">Review required</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            <SignalEvidence icon={BadgeCheck} label="Execution" value={execution.executionId} />
            <SignalEvidence icon={Fingerprint} label="Output SHA-256" value={execution.output.sha256} />
            <SignalEvidence icon={DatabaseZap} label="Source snapshot" value={execution.provenance?.sourceDataset?.snapshotId ?? "Recorded in receipt"} />
          </div>
          <div className="mt-4 flex gap-3 rounded-lg border border-warn/30 bg-warn-soft p-4 text-warn">
            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="text-[10.5px] leading-5">{execution.disclosure}</p>
          </div>
        </div>
      ) : (
        <div className="grid min-h-56 place-items-center p-6 text-center">
          <div className="max-w-lg">
            <BrainCircuit className="mx-auto size-7 text-gold-ink" aria-hidden />
            <p className="mt-3 text-sm font-bold text-text-strong">No verified completed prediction receipt</p>
            <p className="mt-2 text-xs leading-5 text-text-muted">Use the governed scoring control to submit a bounded current public cohort, then return here to review the actual SageMaker results.</p>
          </div>
        </div>
      )}
    </section>
  );
}

function SignalEvidence({ icon: Icon, label, value }: { icon: typeof BadgeCheck; label: string; value: string }) {
  return <div className="rounded-lg border border-border bg-surface-2 p-3"><Icon className="size-4 text-gov-primary" aria-hidden /><p className="mt-2 text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 break-all font-mono text-[9px] leading-4 text-text-muted">{value}</p></div>;
}

function SourcesView({ snapshot }: { snapshot: IntelligenceSnapshot }) {
  const persistedRecords = snapshot.sources.reduce(
    (total, source) => total + (source.status === "persisted" ? source.recordCount ?? 0 : 0),
    0,
  );
  return (
    <div className="space-y-4">
      <LiveAcquisitionPanel />
      <SourceAcquisitionInventory persistedRecords={persistedRecords} />
      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
      <div className="border-b border-border px-5 py-4">
        <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Provenance ledger</p>
        <h2 className="mt-1 text-lg font-bold text-text-strong">Public sources and activation state</h2>
        <p className="mt-1 text-xs leading-5 text-text-muted">Accepted public corpus: {persistedRecords.toLocaleString("en-US")} canonical records across {snapshot.sources.filter((source) => source.status === "persisted").length} persisted public source families. The protected API status above reports the smaller bounded Serving Projection separately. Every persisted record carries retrieval time, source URL, record digest, schema version, and collection state. Gated sources remain visibly separate.</p>
      </div>
      <div className="divide-y divide-border">
        {snapshot.sources.map((source) => (
          <article key={source.id} className="grid gap-3 px-5 py-4 md:grid-cols-[1fr_0.7fr_1.5fr_auto] md:items-center">
            <div><p className="text-sm font-bold text-text-strong">{source.name}</p><p className="mt-1 text-[10px] text-text-muted">{source.authority}</p></div>
            <div><p className="text-sm font-bold text-text-strong">{formatExactCount(source.recordCount)}</p><p className="mt-1 text-[10px] text-text-muted">{source.recordLabel}</p></div>
            <p className="text-xs leading-5 text-text-muted">{source.use}</p>
            <div className="flex items-center justify-between gap-3 md:justify-end"><SourceStatus status={source.status} /><a href={source.url} target="_blank" rel="noreferrer" aria-label={`Open ${source.name} source`} className="grid size-11 place-items-center rounded-md border border-border text-gov-primary hover:bg-surface-2"><ExternalLink className="size-4" aria-hidden /></a></div>
          </article>
        ))}
      </div>
      </section>
    </div>
  );
}

function LiveAcquisitionPanel() {
  const [data, setData] = useState<PublicAcquisitionList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const next = await getPublicAcquisitionsApi();
      setData(next);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The public acquisition receipt is unavailable.");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const runNow = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await postPublicAcquisitionRunApi();
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The public acquisition run failed.");
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const latest = data?.acquisitions[0] ?? null;
  const completed = latest?.status === "completed";
  return (
    <section className="overflow-hidden rounded-xl border border-gov-primary/25 bg-surface shadow-card" aria-labelledby="live-acquisition-title">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border bg-gov-primary-lighter/45 px-5 py-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${data?.mode === "live" ? "border-success/30 bg-success-soft text-success" : "border-info/30 bg-info-soft text-info"}`}>{data?.mode === "live" ? "Live scheduled acquisition" : "Replay only"}</span>
            <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-text-muted">{data?.schedule ?? "Loading schedule"}</span>
          </div>
          <h2 id="live-acquisition-title" className="mt-2 text-lg font-bold text-text-strong">USAspending change acquisition</h2>
          <p className="mt-1 max-w-4xl text-xs leading-5 text-text-muted">Compass polls the official public API as a bounded micro-batch. It versions the raw response, canonicalizes a PII-minimized projection, compares stable record hashes, advances an accepted watermark, and emits one PII-minimized Kinesis envelope for each added or changed record. Unchanged records emit no event.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => void refresh()} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-muted hover:bg-surface-2"><RefreshCw className="size-3.5" aria-hidden /> Refresh receipt</button>
          <button type="button" onClick={() => void runNow()} disabled={busy || data?.mode !== "live"} className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-xs font-bold text-white hover:bg-gov-primary-dark disabled:cursor-not-allowed disabled:opacity-50">{busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Activity className="size-3.5" aria-hidden />} Run bounded poll</button>
        </div>
      </div>
      {error ? <div role="alert" className="m-4 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft p-3 text-xs leading-5 text-danger"><AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden /> {error}</div> : null}
      {latest ? (
        <div className="p-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <AcquisitionMetric label="State" value={latest.status} tone={completed ? "success" : "attention"} />
            <AcquisitionMetric label="Records" value={String(latest.record_count ?? 0)} />
            <AcquisitionMetric label="Added" value={String(latest.added_records ?? 0)} />
            <AcquisitionMetric label="Changed" value={String(latest.changed_records ?? 0)} />
            <AcquisitionMetric label="Unchanged" value={String(latest.unchanged_records ?? 0)} />
            <AcquisitionMetric label="Watermark" value={latest.watermark || "No source date"} />
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
            <div className="min-w-0 rounded-lg border border-border bg-surface-2 p-3">
              <p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Latest immutable receipt</p>
              <p className="mt-1 text-xs font-bold text-text-strong">{latest.run_id}</p>
              <code className="mt-1 block truncate text-[9px] text-text-muted" title={latest.snapshot_sha256}>{latest.snapshot_sha256 ?? "Snapshot digest unavailable for this receipt"}</code>
              <p className="mt-2 text-[10px] leading-4 text-text-muted">{latest.scope_disclosure}</p>
            </div>
            <a href="/admin/lineage/" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-gov-primary px-4 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Open stage lineage <ArrowUpRight className="size-3.5" aria-hidden /></a>
          </div>
        </div>
      ) : (
        <div className="grid min-h-36 place-items-center p-5 text-center">
          <div><Wifi className="mx-auto size-6 text-text-subtle" aria-hidden /><p className="mt-2 text-xs font-bold text-text-strong">No accepted live acquisition receipt yet</p><p className="mt-1 text-[10px] text-text-muted">A scheduled or manual run will create the first immutable watermark.</p></div>
        </div>
      )}
    </section>
  );
}

function AcquisitionMetric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "success" | "attention" }) {
  const color = tone === "success" ? "text-success" : tone === "attention" ? "text-warn" : "text-text-strong";
  return <div className="rounded-lg border border-border bg-white p-3"><p className="text-[8.5px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className={`mt-2 truncate text-sm font-bold ${color}`} title={value}>{value}</p></div>;
}

function SourceAcquisitionInventory({ persistedRecords }: { persistedRecords: number }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Source acquisition boundary</p>
          <h2 className="mt-1 text-lg font-bold text-text-strong">What is collected, gated, or excluded</h2>
          <p className="mt-1 max-w-4xl text-xs leading-5 text-text-muted">This registry separates evidence already in Compass from data that requires a license or Government authorization. A declared category is not a live connection.</p>
        </div>
        <div className="rounded-md border border-success/30 bg-success-soft px-3 py-2 text-xs font-bold text-success">
          12 public families | {persistedRecords.toLocaleString("en-US")} records
        </div>
      </div>
      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        {SOURCE_ACQUISITION_GROUPS.map((group) => (
          <article key={group.id} className="rounded-lg border border-border bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold text-text-strong">{group.label}</h3>
                <p className="mt-1 text-[11px] leading-5 text-text-muted">{group.summary}</p>
              </div>
              <AcquisitionStatus state={group.state} label={group.statusLabel} />
            </div>
            <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={`${group.label} sources`}>
              {group.items.map((item) => (
                <li key={item} className="rounded border border-border bg-surface-2 px-2 py-1 text-[10px] font-semibold text-text-strong">{item}</li>
              ))}
            </ul>
            <div className="mt-3 space-y-2 border-t border-border pt-3 text-[10px] leading-5">
              <p className="text-text-muted"><span className="font-bold text-text-strong">Activation:</span> {group.activation}</p>
              <p className="text-text-muted"><span className="font-bold text-text-strong">Boundary:</span> {group.boundary}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function AcquisitionStatus({ state, label }: { state: SourceAcquisitionState; label: string }) {
  const style = state === "collected_public"
    ? "border-success/30 bg-success-soft text-success"
    : state === "gated_government"
      ? "border-info/30 bg-info-soft text-info"
      : state === "gated_commercial"
        ? "border-warn/30 bg-warn-soft text-warn"
        : "border-danger/30 bg-danger-soft text-danger";
  return <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${style}`}>{label}</span>;
}

function formatCount(value: number | null) {
  return value === null ? "Unavailable" : number.format(value);
}

function formatExactCount(value: number | null) {
  return value === null ? "Unavailable" : exactNumber.format(value);
}

function formatDateTime(value: string | undefined) {
  if (!value) return "Recorded in receipt";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function formatMoney(value: number | null) {
  return value === null ? "Unavailable" : money.format(value);
}

function formatNullablePercent(value: number | null) {
  return value === null ? "Not trained" : percent.format(value);
}

function formatPercentile(value: number | null) {
  if (value === null) return "Not trained";
  const remainder = value % 100;
  const suffix = remainder >= 11 && remainder <= 13 ? "th" : value % 10 === 1 ? "st" : value % 10 === 2 ? "nd" : value % 10 === 3 ? "rd" : "th";
  return `${value}${suffix}`;
}

function EvidencePill({ kind }: { kind: EvidenceClass }) {
  const classes = kind === "observed" ? "border-success/30 bg-success-soft text-success" : kind === "derived" ? "border-info/30 bg-info-soft text-info" : "border-gold/30 bg-gold-soft text-gold-ink";
  return <span className={`rounded-full border px-2 py-1 text-[9px] font-bold uppercase tracking-wide ${classes}`}>{kind}</span>;
}

function ProgramMetric({ label, value, kind }: { label: string; value: string; kind: EvidenceClass }) {
  return <div className="rounded-lg border border-border bg-white p-3"><div className="flex items-center justify-between gap-2"><p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><EvidencePill kind={kind} /></div><p className="mt-3 text-xl font-bold text-text-strong">{value}</p></div>;
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex items-start justify-between gap-4"><dt className="text-text-subtle">{label}</dt><dd className="text-right font-bold text-text-strong">{value}</dd></div>;
}

function ModelFact({ label, value }: { label: string; value: string }) {
  return <div className="bg-white p-3"><dt className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</dt><dd className="mt-1 text-[11px] font-semibold leading-5 text-text-strong">{value}</dd></div>;
}

function SourceStatus({ status }: { status: IntelligenceSnapshot["sources"][number]["status"] }) {
  const style = status === "persisted" ? "border-success/30 bg-success-soft text-success" : status === "scheduled" ? "border-info/30 bg-info-soft text-info" : "border-warn/30 bg-warn-soft text-warn";
  return <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${style}`}>{status}</span>;
}

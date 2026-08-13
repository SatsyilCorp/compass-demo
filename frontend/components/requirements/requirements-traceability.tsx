"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  ClipboardCheck,
  CloudCog,
  Code2,
  Database,
  ExternalLink,
  FileCode2,
  FileSearch,
  Filter,
  Loader2,
  MapPinned,
  PlayCircle,
  RefreshCcw,
  Search,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  TestTube2,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { getOperationsSummary, setAuthContext } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import type { OperationsSummaryResponse } from "@/lib/types";

import {
  PRESENTER_SEQUENCE,
  REQUIREMENTS,
  STATUS_META,
  TRACE_STATUSES,
  countByStatus,
  type RequirementTrace,
  type TraceStatus,
} from "./model";

type StatusFilter = "all" | TraceStatus;
type OperationsState = {
  loading: boolean;
  data: OperationsSummaryResponse | null;
  error: boolean;
};

const STATUS_STYLE: Record<TraceStatus, {
  chip: string;
  rail: string;
  panel: string;
  icon: LucideIcon;
}> = {
  "verified-live": {
    chip: "border-success/30 bg-success-soft text-success",
    rail: "border-l-success",
    panel: "border-success/20 bg-success-soft/45",
    icon: CheckCircle2,
  },
  configured: {
    chip: "border-info/30 bg-info-soft text-info",
    rail: "border-l-info",
    panel: "border-info/20 bg-info-soft/45",
    icon: Settings2,
  },
  "target-architecture": {
    chip: "border-gold/40 bg-gold-soft text-gold-ink",
    rail: "border-l-gold",
    panel: "border-gold/25 bg-gold-soft/45",
    icon: MapPinned,
  },
  "external-dependency": {
    chip: "border-warn/35 bg-warn-soft text-warn",
    rail: "border-l-warn",
    panel: "border-warn/25 bg-warn-soft/45",
    icon: ExternalLink,
  },
  "not-yet-implemented": {
    chip: "border-danger/30 bg-danger-soft text-danger",
    rail: "border-l-danger",
    panel: "border-danger/20 bg-danger-soft/45",
    icon: XCircle,
  },
};

export function RequirementsTraceability() {
  const auth = useAppAuth();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [operations, setOperations] = useState<OperationsState>({
    loading: true,
    data: null,
    error: false,
  });

  const loadOperations = useCallback(async () => {
    if (auth.isLoading) return;
    setAuthContext({ bearerToken: auth.idToken, role: auth.role, orgUnit: auth.orgUnit });
    setOperations((current) => ({ ...current, loading: true }));
    try {
      const data = await getOperationsSummary();
      setOperations({ loading: false, data, error: false });
    } catch {
      setOperations({ loading: false, data: null, error: true });
    }
  }, [auth.idToken, auth.isLoading, auth.orgUnit, auth.role]);

  useEffect(() => {
    if (auth.isLoading) return;
    void loadOperations();
    const timer = window.setInterval(() => void loadOperations(), 30_000);
    return () => window.clearInterval(timer);
  }, [auth.isLoading, loadOperations]);

  const effectiveRequirements = useMemo(
    () => REQUIREMENTS.map((item) => resolveLiveState(item, operations.data)),
    [operations.data],
  );
  const totals = useMemo(() => countByStatus(effectiveRequirements), [effectiveRequirements]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return effectiveRequirements.filter((item) => {
      if (status !== "all" && item.status !== status) return false;
      if (!normalized) return true;
      return [
        item.title,
        item.intent,
        item.userAction,
        item.differentiator,
        item.caveat,
        ...item.tags,
        ...item.liveEvidence.flatMap((target) => [target.label, target.locator]),
        ...item.locators.source,
        ...item.locators.tests,
        ...item.locators.iac,
      ].join(" ").toLowerCase().includes(normalized);
    });
  }, [effectiveRequirements, query, status]);

  const requirementById = useMemo(
    () => new Map(effectiveRequirements.map((item) => [item.id, item])),
    [effectiveRequirements],
  );

  return (
    <div className="space-y-6">
      <ExecutiveProofHeader totals={totals} />

      <OperationsProof
        state={operations}
        onRefresh={() => void loadOperations()}
      />

      <section className="rounded-xl border border-border bg-surface shadow-card" aria-labelledby="presenter-sequence-title">
        <div className="flex flex-col gap-2 border-b border-border px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-gold-ink">
              <PlayCircle className="size-3.5" aria-hidden /> Presenter sequence
            </p>
            <h2 id="presenter-sequence-title" className="mt-1 text-lg font-bold text-text-strong">Tell one evidence chain in 18 minutes</h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">Open the linked screen, perform the stated action, then return here only if the team asks for source or control evidence.</p>
          </div>
          <span className="rounded-full border border-border bg-white px-3 py-1.5 font-mono text-[10px] font-bold text-text-muted">5 stops | 12 asks</span>
        </div>
        <div className="grid gap-3 p-4 lg:grid-cols-5">
          {PRESENTER_SEQUENCE.map((step) => (
            <article key={step.order} className="flex min-h-full flex-col rounded-lg border border-border bg-white p-4 shadow-soft">
              <div className="flex items-center justify-between gap-2">
                <span className="grid size-8 place-items-center rounded-full bg-gov-primary font-mono text-xs font-bold text-white">{step.order}</span>
                <span className="font-mono text-[9px] font-bold uppercase text-text-subtle">{step.duration}</span>
              </div>
              <h3 className="mt-3 text-sm font-bold text-text-strong">{step.title}</h3>
              <p className="mt-2 flex-1 text-[10.5px] leading-5 text-text-muted">{step.instruction}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {step.requirementIds.map((id) => (
                  <span key={id} className="rounded-full bg-surface-2 px-2 py-1 text-[8.5px] font-semibold text-text-subtle">
                    {requirementById.get(id)?.title ?? id}
                  </span>
                ))}
              </div>
              <Link href={step.href} className="mt-4 inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter/70">
                Open this stop <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface shadow-card" aria-labelledby="requirement-proof-title">
        <div className="border-b border-border px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-gold-ink">
                <ClipboardCheck className="size-3.5" aria-hidden /> Requirement proof
              </p>
              <h2 id="requirement-proof-title" className="mt-1 text-lg font-bold text-text-strong">Action, evidence, implementation, differentiator, boundary</h2>
              <p className="mt-1 text-xs leading-5 text-text-muted">Every row states exactly what can be shown and what must not be claimed.</p>
            </div>
            <span className="rounded-full border border-border bg-white px-3 py-1.5 font-mono text-[10px] font-bold text-text-muted" aria-live="polite">
              {filtered.length} of {effectiveRequirements.length} shown
            </span>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(260px,1fr)_260px_auto]">
            <label className="relative block">
              <span className="sr-only">Search demo requirements</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-subtle" aria-hidden />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search an ask, screen, API, source, or caveat"
                className="min-h-11 w-full rounded-md border border-border bg-white pl-10 pr-10 text-sm text-text-strong outline-none placeholder:text-text-subtle focus:border-gov-primary"
              />
              {query ? (
                <button type="button" onClick={() => setQuery("")} aria-label="Clear requirement search" className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded text-text-subtle hover:bg-surface-2">
                  <X className="size-4" aria-hidden />
                </button>
              ) : null}
            </label>
            <label>
              <span className="sr-only">Evidence state</span>
              <select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)} aria-label="Evidence state" className="min-h-11 w-full rounded-md border border-border bg-white px-3 text-sm font-semibold text-text-strong outline-none focus:border-gov-primary">
                <option value="all">All evidence states</option>
                {TRACE_STATUSES.map((item) => <option key={item} value={item}>{STATUS_META[item].label}</option>)}
              </select>
            </label>
            {query || status !== "all" ? (
              <button type="button" onClick={() => { setQuery(""); setStatus("all"); }} className="min-h-11 rounded-md border border-border bg-white px-4 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Clear filters</button>
            ) : (
              <span className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-white px-4 text-xs font-semibold text-text-muted"><Filter className="size-3.5" aria-hidden /> Evidence filters</span>
            )}
          </div>
        </div>

        <div className="space-y-4 p-3 sm:p-5" aria-live="polite">
          {filtered.length > 0 ? filtered.map((item, index) => (
            <RequirementCard key={item.id} item={item} ordinal={index + 1} />
          )) : (
            <div className="rounded-lg border border-dashed border-border bg-white px-5 py-12 text-center">
              <FileSearch className="mx-auto size-8 text-text-subtle" aria-hidden />
              <h3 className="mt-3 text-sm font-bold text-text-strong">No matching demo ask</h3>
              <p className="mt-1 text-xs text-text-muted">Clear the search or evidence-state filter.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function ExecutiveProofHeader({ totals }: { totals: Record<TraceStatus, number> }) {
  return (
    <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card" aria-labelledby="proof-summary-title">
      <div className="grid gap-5 px-5 py-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(330px,0.75fr)] lg:px-6">
        <div>
          <div className="flex items-center gap-2 text-gold-light">
            <BadgeCheck className="size-4" aria-hidden />
            <p className="text-[10px] font-bold uppercase tracking-[0.16em]">Executive evidence scorecard</p>
          </div>
          <h2 id="proof-summary-title" className="mt-2 text-xl font-bold">What the demo proves, without accreditation overclaim</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-white/72">
            Compass is a production-scale proving prototype for synthetic and public data. A live label means a protected screen or API returned deployment evidence. It does not mean production authorization.
          </p>
        </div>
        <div className="rounded-lg border border-white/15 bg-white/[0.07] p-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 size-5 shrink-0 text-gold-light" aria-hidden />
            <div>
              <p className="text-xs font-bold">Hard boundary</p>
              <p className="mt-1 text-[11px] leading-5 text-white/67">
                No CUI or direct PII. No IL4, IL5, ATO, FedRAMP, or operational-performance claim. Target controls remain labeled until the Government boundary and authorization evidence exist.
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="grid border-t border-white/12 bg-black/10 sm:grid-cols-5">
        {TRACE_STATUSES.map((status) => (
          <TruthMetric key={status} value={String(totals[status])} label={STATUS_META[status].label} />
        ))}
      </div>
    </section>
  );
}

function OperationsProof({ state, onRefresh }: { state: OperationsState; onRefresh: () => void }) {
  const watermark = state.data?.source_watermarks.find((item) => item.source_id.toLowerCase().includes("usaspending"));
  const isLive = state.data?.mode === "live";

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-white shadow-card" aria-labelledby="operations-proof-title">
      <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="operations-proof-title" className="flex items-center gap-2 text-base font-bold text-text-strong"><Activity className="size-4 text-gov-primary" aria-hidden /> Live operations proof</h2>
            {state.loading ? <StatePill icon={Loader2} label="Checking" className="border-border bg-surface-2 text-text-muted" spin /> : null}
            {!state.loading && state.data ? <StatePill icon={isLive ? CheckCircle2 : PlayCircle} label={isLive ? "Live API" : "Replay fixture"} className={isLive ? "border-success/30 bg-success-soft text-success" : "border-info/30 bg-info-soft text-info"} /> : null}
            {!state.loading && state.error ? <StatePill icon={AlertTriangle} label="No current receipt" className="border-warn/35 bg-warn-soft text-warn" /> : null}
          </div>
          <p className="mt-1 text-[10.5px] leading-5 text-text-muted">Protected adapter: <code className="font-mono text-gov-primary">GET /operations/summary</code>. Replay data is visibly labeled and never upgrades a requirement to live.</p>
        </div>
        <button type="button" onClick={onRefresh} disabled={state.loading} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-md border border-border bg-surface px-3 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter disabled:cursor-not-allowed disabled:opacity-50">
          <RefreshCcw className={`size-3.5 ${state.loading ? "animate-spin" : ""}`} aria-hidden /> Refresh proof
        </button>
      </div>

      {state.data ? (
        <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(340px,0.75fr)]">
          <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
            <OperationMetric label="Runs retained" value={state.data.counts.runs_total} />
            <OperationMetric label="Runs active" value={state.data.counts.runs_active} />
            <OperationMetric label="Need attention" value={state.data.counts.runs_attention} />
            <OperationMetric label="Unread signals" value={state.data.counts.signals_unread} />
          </div>
          <div className="border-t border-border bg-surface-2 p-4 lg:border-l lg:border-t-0">
            {watermark ? (
              <div className="flex items-start gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-md bg-gov-primary text-white"><Database className="size-4" aria-hidden /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-bold text-text-strong">{watermark.label}</p>
                    <span className="rounded-full border border-border bg-white px-2 py-1 text-[8.5px] font-bold uppercase text-text-muted">{watermark.status}</span>
                  </div>
                  <p className="mt-1 break-all font-mono text-[9px] text-text-subtle">Watermark {watermark.watermark ?? "not accepted"}</p>
                  <p className="mt-2 text-[10px] text-text-muted">+{watermark.added_records} added | {watermark.changed_records} changed | {watermark.unchanged_records} unchanged | {watermark.not_observed_records} not in bounded page</p>
                  <p className="mt-1 truncate font-mono text-[9px] text-text-subtle" title={watermark.run_id ?? undefined}>Run {watermark.run_id ?? "no accepted run"}</p>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3">
                <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
                <div>
                  <p className="text-xs font-bold text-text-strong">No accepted live source receipt</p>
                  <p className="mt-1 text-[10px] leading-4 text-text-muted">The proof stays unverified until the protected live API returns an accepted public-source run.</p>
                </div>
              </div>
            )}
          </div>
          <div className="border-t border-border px-4 py-3 text-[9.5px] leading-4 text-text-subtle lg:col-span-2">
            Generated {formatTimestamp(state.data.generated_at)} | {state.data.disclosure}
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3 px-5 py-5">
          <ShieldCheck className="mt-0.5 size-5 shrink-0 text-gov-primary" aria-hidden />
          <div>
            <p className="text-sm font-bold text-text-strong">Claims remain conservative</p>
            <p className="mt-1 text-xs leading-5 text-text-muted">The operations API did not return a current accepted contract. No requirement was upgraded from its source-reviewed state.</p>
          </div>
        </div>
      )}
    </section>
  );
}

function RequirementCard({ item, ordinal }: { item: RequirementTrace; ordinal: number }) {
  const style = STATUS_STYLE[item.status];
  return (
    <article className={`overflow-hidden rounded-lg border border-border border-l-4 bg-white shadow-soft ${style.rail}`}>
      <div className="grid gap-5 p-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] sm:p-5">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[9px] font-bold uppercase tracking-[0.14em] text-text-subtle">Ask {String(ordinal).padStart(2, "0")}</span>
            <StatusChip status={item.status} />
          </div>
          <h3 className="mt-2 text-lg font-bold text-text-strong">{item.title}</h3>
          <p className="mt-1 text-xs leading-5 text-text-muted">{item.intent}</p>

          <div className="mt-4 rounded-lg border border-gov-primary/20 bg-gov-primary-lighter/40 p-3">
            <p className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-[0.13em] text-gov-primary"><PlayCircle className="size-3.5" aria-hidden /> User action</p>
            <p className="mt-2 text-[11px] leading-5 text-text-strong">{item.userAction}</p>
          </div>

          <div className="mt-3">
            <p className="text-[9px] font-bold uppercase tracking-[0.13em] text-text-subtle">Live evidence endpoint or screen</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {item.liveEvidence.map((target) => target.href ? (
                <Link key={`${target.kind}-${target.locator}`} href={target.href} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-surface px-3 text-[10px] font-bold text-gov-primary hover:border-gov-primary/30 hover:bg-gov-primary-lighter">
                  {target.kind === "screen" ? <ExternalLink className="size-3.5" aria-hidden /> : <Code2 className="size-3.5" aria-hidden />}
                  <span>{target.label}</span>
                  <code className="font-mono text-[8.5px] text-text-subtle">{target.locator}</code>
                </Link>
              ) : (
                <span key={`${target.kind}-${target.locator}`} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-surface px-3 text-[10px] font-bold text-text-muted">
                  <Code2 className="size-3.5 text-gov-primary" aria-hidden />
                  <span>{target.label}</span>
                  <code className="font-mono text-[8.5px] text-text-subtle">{target.locator}</code>
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <ProofNote icon={BadgeCheck} title="Visible differentiator" className="border-success/20 bg-success-soft/40">
            {item.differentiator}
          </ProofNote>
          <ProofNote icon={ShieldAlert} title="Caveat to say out loud" className={style.panel}>
            {item.caveat}
          </ProofNote>
          <div className="rounded-lg border border-border bg-surface p-3">
            <p className="text-[9px] font-bold uppercase tracking-[0.13em] text-text-subtle">State rule</p>
            <p className="mt-1 text-[10px] leading-4 text-text-muted"><span className="font-bold text-text-strong">{STATUS_META[item.status].label}.</span> {STATUS_META[item.status].description}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-px border-t border-border bg-border lg:grid-cols-3">
        <LocatorGroup icon={FileCode2} label="Source" values={item.locators.source} />
        <LocatorGroup icon={TestTube2} label="Tests" values={item.locators.tests} />
        <LocatorGroup icon={CloudCog} label="IaC" values={item.locators.iac} />
      </div>
    </article>
  );
}

function LocatorGroup({ icon: Icon, label, values }: { icon: LucideIcon; label: string; values: string[] }) {
  return (
    <div className="bg-surface-2 p-3">
      <p className="flex items-center gap-2 text-[8.5px] font-bold uppercase tracking-[0.13em] text-text-subtle"><Icon className="size-3" aria-hidden /> {label}</p>
      <ul className="mt-2 space-y-1.5">
        {values.map((value) => <li key={value} className="break-all font-mono text-[8.5px] leading-4 text-text-muted">{value}</li>)}
      </ul>
    </div>
  );
}

function ProofNote({ icon: Icon, title, className, children }: { icon: LucideIcon; title: string; className: string; children: ReactNode }) {
  return (
    <div className={`rounded-lg border p-3 ${className}`}>
      <p className="flex items-center gap-2 text-[9px] font-bold uppercase tracking-[0.13em] text-text-subtle"><Icon className="size-3.5" aria-hidden /> {title}</p>
      <p className="mt-2 text-[10.5px] leading-5 text-text-muted">{children}</p>
    </div>
  );
}

function StatusChip({ status }: { status: TraceStatus }) {
  const style = STATUS_STYLE[status];
  const Icon = style.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${style.chip}`}>
      <Icon className="size-3" aria-hidden /> {STATUS_META[status].label}
    </span>
  );
}

function StatePill({ icon: Icon, label, className, spin = false }: { icon: LucideIcon; label: string; className: string; spin?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${className}`}>
      <Icon className={`size-3 ${spin ? "animate-spin" : ""}`} aria-hidden /> {label}
    </span>
  );
}

function OperationMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white px-4 py-5">
      <p className="font-mono text-xl font-bold text-text-strong">{value.toLocaleString()}</p>
      <p className="mt-1 text-[8.5px] font-bold uppercase tracking-[0.12em] text-text-subtle">{label}</p>
    </div>
  );
}

function TruthMetric({ value, label }: { value: string; label: string }) {
  return (
    <div className="border-white/10 px-5 py-4 sm:border-r last:border-r-0">
      <p className="font-mono text-xl font-bold text-white">{value}</p>
      <p className="mt-1 text-[8.5px] font-bold uppercase tracking-[0.12em] text-white/55">{label}</p>
    </div>
  );
}

function resolveLiveState(item: RequirementTrace, operations: OperationsSummaryResponse | null): RequirementTrace {
  if (!operations || operations.mode !== "live") return item;

  if (item.id === "continuous-public-acquisition") {
    const watermark = operations.source_watermarks.find((source) => source.source_id.toLowerCase().includes("usaspending"));
    if (watermark?.last_accepted_at && watermark.run_id) {
      return {
        ...item,
        status: "verified-live",
        caveat: `The live API reports an accepted public-data watermark for run ${watermark.run_id}. This proves a bounded public acquisition, not access to protected ONR systems.`,
      };
    }
  }

  if (item.id === "drift-monitoring") {
    const acceptedRun = operations.runs.find((run) => run.run_kind.toLowerCase().includes("drift") && run.status === "completed");
    if (acceptedRun) {
      return {
        ...item,
        status: "verified-live",
        caveat: `The live API reports completed drift run ${acceptedRun.run_id}. A representative Government baseline and approved operating thresholds are still required for production monitoring.`,
      };
    }
  }

  return item;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(parsed);
}

"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  ExternalLink,
  FileCheck2,
  Filter,
  MapPinned,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from "lucide-react";

import {
  REQUIREMENTS,
  REQUIREMENT_SECTIONS,
  STATUS_META,
  countByStatus,
  type RequirementSection,
  type RequirementTrace,
  type TraceStatus,
} from "./model";

type SectionFilter = "all" | RequirementSection;
type StatusFilter = "all" | TraceStatus;

const STATUS_STYLE: Record<TraceStatus, { chip: string; rail: string; icon: typeof CheckCircle2 }> = {
  demonstrated: {
    chip: "border-success/30 bg-success-soft text-success",
    rail: "border-l-success",
    icon: CheckCircle2,
  },
  partial: {
    chip: "border-gold/40 bg-gold-soft text-gold-ink",
    rail: "border-l-gold",
    icon: AlertTriangle,
  },
  roadmap: {
    chip: "border-border bg-surface-2 text-text-muted",
    rail: "border-l-text-subtle",
    icon: MapPinned,
  },
};

export function RequirementsTraceability() {
  const [query, setQuery] = useState("");
  const [section, setSection] = useState<SectionFilter>("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [demoOnly, setDemoOnly] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set([REQUIREMENTS[0].id]));
  const totals = countByStatus();

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return REQUIREMENTS.filter((item) => {
      if (section !== "all" && item.section !== section) return false;
      if (status !== "all" && item.status !== status) return false;
      if (demoOnly && item.status !== "demonstrated") return false;
      if (!normalized) return true;
      return [
        item.title,
        item.requirement,
        item.capability,
        item.gap,
        item.demoLabel,
        item.section,
        ...item.tags,
        ...item.evidence,
      ].join(" ").toLowerCase().includes(normalized);
    });
  }, [demoOnly, query, section, status]);

  const allVisibleExpanded = filtered.length > 0 && filtered.every((item) => expanded.has(item.id));
  const hasFilters = query !== "" || section !== "all" || status !== "all" || demoOnly;

  const toggle = (id: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleVisible = () => {
    setExpanded((current) => {
      const next = new Set(current);
      if (allVisibleExpanded) filtered.forEach((item) => next.delete(item.id));
      else filtered.forEach((item) => next.add(item.id));
      return next;
    });
  };

  const clearFilters = () => {
    setQuery("");
    setSection("all");
    setStatus("all");
    setDemoOnly(false);
  };

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card" aria-labelledby="trace-truth-heading">
        <div className="grid gap-5 px-5 py-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)] lg:px-6">
          <div>
            <div className="flex items-center gap-2 text-gold-light">
              <ClipboardCheck className="size-4" aria-hidden />
              <p className="text-[10px] font-bold uppercase tracking-[0.16em]">Evidence-led scope statement</p>
            </div>
            <h2 id="trace-truth-heading" className="mt-2 text-xl font-bold">Production-scale proving prototype</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/72">
              Compass demonstrates a deployed AWS-native architecture, governed synthetic workflows, bounded scale acceptance, and retained proof. It is not a production authorization claim.
            </p>
          </div>
          <div className="rounded-lg border border-white/15 bg-white/[0.07] p-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 size-5 shrink-0 text-gold-light" aria-hidden />
              <div>
                <p className="text-xs font-bold">Not production-ready or accredited</p>
                <p className="mt-1 text-[11px] leading-5 text-white/67">
                  FedRAMP High, IL5, ATO, Government environment access, full MLOps, STIG automation, and zero-touch vulnerability management remain explicit roadmap work.
                </p>
              </div>
            </div>
          </div>
        </div>
        <div className="grid border-t border-white/12 bg-black/10 sm:grid-cols-4">
          <TruthMetric value={String(REQUIREMENTS.length)} label="requirements traced" />
          <TruthMetric value={String(totals.demonstrated)} label="demonstrated" />
          <TruthMetric value={String(totals.partial)} label="proof incomplete" />
          <TruthMetric value={String(totals.roadmap)} label="production roadmap" />
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface shadow-card" aria-labelledby="trace-controls-heading">
        <div className="border-b border-border px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">
                <SlidersHorizontal className="size-3.5" aria-hidden /> Presenter controls
              </p>
              <h2 id="trace-controls-heading" className="mt-1 text-lg font-bold text-text-strong">Find the requirement, then show the proof</h2>
              <p className="mt-1 text-xs leading-5 text-text-muted">Filter by PWS section or delivery state. Expand a row for a simple talk track, exact screen, evidence, and honest boundary.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-border bg-white px-3 py-1.5 font-mono text-[10px] font-bold text-text-muted" aria-live="polite">
                {filtered.length} of {REQUIREMENTS.length} shown
              </span>
              <button type="button" onClick={toggleVisible} disabled={filtered.length === 0} className="min-h-10 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50">
                {allVisibleExpanded ? "Collapse visible" : "Expand visible"}
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(240px,1fr)_220px_220px_auto]">
            <label className="relative block">
              <span className="sr-only">Search requirements</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-subtle" aria-hidden />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search requirements, controls, or evidence"
                className="min-h-11 w-full rounded-md border border-border bg-white pl-10 pr-10 text-sm text-text-strong outline-none placeholder:text-text-subtle focus:border-gov-primary"
              />
              {query ? (
                <button type="button" onClick={() => setQuery("")} aria-label="Clear requirements search" className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded text-text-subtle hover:bg-surface-2">
                  <X className="size-4" aria-hidden />
                </button>
              ) : null}
            </label>
            <label>
              <span className="sr-only">PWS section</span>
              <select value={section} onChange={(event) => setSection(event.target.value as SectionFilter)} aria-label="PWS section" className="min-h-11 w-full rounded-md border border-border bg-white px-3 text-sm font-semibold text-text-strong outline-none focus:border-gov-primary">
                <option value="all">All PWS sections</option>
                {REQUIREMENT_SECTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label>
              <span className="sr-only">Delivery status</span>
              <select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)} aria-label="Delivery status" className="min-h-11 w-full rounded-md border border-border bg-white px-3 text-sm font-semibold text-text-strong outline-none focus:border-gov-primary">
                <option value="all">All delivery states</option>
                {(Object.keys(STATUS_META) as TraceStatus[]).map((item) => <option key={item} value={item}>{STATUS_META[item].label}</option>)}
              </select>
            </label>
            <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-muted hover:bg-surface-2">
              <input type="checkbox" checked={demoOnly} onChange={(event) => setDemoOnly(event.target.checked)} className="size-4 accent-gov-primary" />
              Demo-ready only
            </label>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Status legend">
            <Filter className="size-3.5 text-text-subtle" aria-hidden />
            {(Object.keys(STATUS_META) as TraceStatus[]).map((item) => <StatusChip key={item} status={item} />)}
            {hasFilters ? (
              <button type="button" onClick={clearFilters} className="ml-auto min-h-10 rounded-md px-3 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Clear filters</button>
            ) : null}
          </div>
        </div>

        <div className="space-y-3 p-3 sm:p-5" aria-live="polite">
          {filtered.length > 0 ? filtered.map((item) => (
            <RequirementCard key={item.id} item={item} open={expanded.has(item.id)} onToggle={() => toggle(item.id)} />
          )) : (
            <div className="rounded-lg border border-dashed border-border bg-white px-5 py-12 text-center">
              <Search className="mx-auto size-8 text-text-subtle" aria-hidden />
              <h3 className="mt-3 text-sm font-bold text-text-strong">No matching requirements</h3>
              <p className="mt-1 text-xs text-text-muted">Clear one or more filters to return to the complete trace.</p>
              <button type="button" onClick={clearFilters} className="mt-4 min-h-11 rounded-md bg-gov-primary px-4 text-xs font-bold text-white hover:bg-gov-primary-dark">Clear filters</button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function RequirementCard({ item, open, onToggle }: { item: RequirementTrace; open: boolean; onToggle: () => void }) {
  const style = STATUS_STYLE[item.status];
  const StatusIcon = style.icon;
  const panelId = `requirement-${item.id}`;

  return (
    <article className={`overflow-hidden rounded-lg border border-border border-l-4 bg-white shadow-soft ${style.rail}`}>
      <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={panelId} className="flex min-h-20 w-full items-start gap-3 p-4 text-left hover:bg-surface-2 sm:items-center">
        <span className="grid size-9 shrink-0 place-items-center rounded-md bg-gov-primary-lighter text-gov-primary">
          <FileCheck2 className="size-4" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wide text-gold-ink">{item.section} | page {item.sourcePage}</span>
            <StatusChip status={item.status} compact />
          </span>
          <span className="mt-1 block text-sm font-bold text-text-strong">{item.title}</span>
          <span className="mt-1 line-clamp-2 block text-[11px] leading-5 text-text-muted">{item.requirement}</span>
        </span>
        <ChevronDown className={`mt-1 size-5 shrink-0 text-text-subtle transition-transform sm:mt-0 ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>

      {open ? (
        <div id={panelId} className="border-t border-border bg-surface px-4 py-5 sm:px-5">
          <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-4">
            <TraceDetail title="Implemented capability" icon={CheckCircle2}>
              <p>{item.capability}</p>
            </TraceDetail>
            <TraceDetail title="Demo workflow" icon={MapPinned}>
              <ol className="space-y-2">
                {item.workflow.map((step, index) => (
                  <li key={step} className="flex gap-2"><span className="font-mono font-bold text-gov-primary">{index + 1}</span><span>{step}</span></li>
                ))}
              </ol>
              <Link href={item.demoPath} className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 bg-white px-3 font-bold text-gov-primary hover:bg-gov-primary-lighter">
                Open {item.demoLabel} <ExternalLink className="size-3.5" aria-hidden />
              </Link>
            </TraceDetail>
            <TraceDetail title="Evidence to show" icon={FileCheck2}>
              <ul className="space-y-2">
                {item.proof.map((proof) => <li key={proof} className="flex gap-2"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-success" /><span>{proof}</span></li>)}
              </ul>
              <div className="mt-3 rounded-md border border-border bg-white p-3">
                <p className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Source evidence</p>
                <ul className="mt-2 space-y-1">
                  {item.evidence.map((file) => <li key={file} className="break-all font-mono text-[9px] text-text-muted">{file}</li>)}
                </ul>
              </div>
            </TraceDetail>
            <TraceDetail title="Honest boundary" icon={AlertTriangle}>
              <p>{item.gap}</p>
              <div className="mt-3 flex items-start gap-2 rounded-md border border-border bg-white p-3">
                <StatusIcon className="mt-0.5 size-4 shrink-0 text-text-subtle" aria-hidden />
                <p><span className="font-bold text-text-strong">{STATUS_META[item.status].label}.</span> {STATUS_META[item.status].description}</p>
              </div>
            </TraceDetail>
          </div>
          <div className="mt-4 flex flex-wrap gap-1.5 border-t border-border pt-3">
            {item.tags.map((tag) => <span key={tag} className="rounded-full border border-border bg-white px-2 py-1 text-[9px] font-semibold text-text-subtle">{tag}</span>)}
          </div>
        </div>
      ) : null}
    </article>
  );
}

function StatusChip({ status, compact = false }: { status: TraceStatus; compact?: boolean }) {
  const style = STATUS_STYLE[status];
  const Icon = style.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-bold ${style.chip} ${compact ? "px-2 py-0.5 text-[9px]" : "px-2.5 py-1 text-[10px]"}`}>
      <Icon className="size-3" aria-hidden /> {compact ? STATUS_META[status].shortLabel : STATUS_META[status].label}
    </span>
  );
}

function TraceDetail({ title, icon: Icon, children }: { title: string; icon: typeof CheckCircle2; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.13em] text-text-subtle"><Icon className="size-3.5" aria-hidden /> {title}</h3>
      <div className="mt-2 text-[10.5px] leading-5 text-text-muted">{children}</div>
    </section>
  );
}

function TruthMetric({ value, label }: { value: string; label: string }) {
  return (
    <div className="border-white/10 px-5 py-4 sm:border-r last:border-r-0">
      <p className="font-mono text-xl font-bold text-white">{value}</p>
      <p className="mt-1 text-[9px] font-bold uppercase tracking-[0.12em] text-white/55">{label}</p>
    </div>
  );
}

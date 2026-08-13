"use client";

import { useState } from "react";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Database,
  GitBranch,
  Info,
  Layers3,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import {
  ARCHITECTURE_STATUSES,
  BRIEFING_VIEWS,
  briefingView,
  type ArchitectureStatus,
  type BriefingLane,
  type BriefingNode,
  type BriefingViewId,
} from "./briefing-model";

const VIEW_ICONS: Record<BriefingViewId, LucideIcon> = {
  executive: Layers3,
  il45: ShieldCheck,
  lineage: Database,
  devsecops: GitBranch,
  mlops: BrainCircuit,
};

const STATUS_STYLES: Record<ArchitectureStatus, string> = {
  "Running now": "border-success/30 bg-success-soft text-success",
  Configured: "border-info/30 bg-info-soft text-info",
  "Target control": "border-gold/40 bg-gold-soft text-gold-ink",
  "External dependency": "border-border bg-surface-2 text-text-muted",
};

const STATUS_DOTS: Record<ArchitectureStatus, string> = {
  "Running now": "bg-success",
  Configured: "bg-info",
  "Target control": "bg-gold",
  "External dependency": "bg-text-subtle",
};

const LANE_STYLES: Record<BriefingLane["tone"], string> = {
  commercial: "border-gov-primary/25 bg-gov-primary-lighter/35",
  protected: "border-danger/35 bg-danger-soft/25",
  external: "border-border bg-surface-2/70",
  evidence: "border-success/25 bg-success-soft/25",
};

export function ArchitectureBriefing() {
  const [activeId, setActiveId] = useState<BriefingViewId>("executive");
  const active = briefingView(activeId);

  return (
    <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-white shadow-card" aria-labelledby="architecture-briefing-title">
      <div className="border-b border-white/10 bg-gov-primary px-5 py-5 text-white sm:px-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.17em] text-gold-light">Architecture at a glance</p>
            <h2 id="architecture-briefing-title" className="mt-2 text-xl font-bold sm:text-2xl">Five views. One accountable system.</h2>
            <p className="mt-2 max-w-4xl text-xs leading-5 text-white/72 sm:text-sm sm:leading-6">
              Start with the mission flow, then inspect the target security boundary, record lineage, software delivery, and governed model lifecycle. Every arrow names both its transport and the evidence it leaves behind.
            </p>
          </div>
          <div className="max-w-md rounded-lg border border-gold-light/30 bg-black/15 p-4">
            <p className="flex items-center gap-2 text-xs font-bold text-gold-light"><Info className="size-4" aria-hidden /> Authorization truth</p>
            <p className="mt-1 text-[10.5px] leading-4 text-white/70">
              The running prototype is in commercial AWS. The IL4/IL5 view is a target architecture and does not represent an ATO, FedRAMP High authorization, or completed Government integration.
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2" aria-label="Architecture status legend">
          {ARCHITECTURE_STATUSES.map((status) => (
            <span key={status} className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-white/80">
              <span className={`size-1.5 rounded-full ${STATUS_DOTS[status]}`} /> {status}
            </span>
          ))}
        </div>
      </div>

      <div className="grid border-b border-border bg-surface-2 sm:grid-cols-2 xl:grid-cols-5" role="tablist" aria-label="Architecture briefing views">
        {BRIEFING_VIEWS.map((view, index) => {
          const Icon = VIEW_ICONS[view.id];
          const selected = view.id === activeId;
          return (
            <button
              key={view.id}
              type="button"
              role="tab"
              id={`architecture-tab-${view.id}`}
              aria-controls={`architecture-panel-${view.id}`}
              aria-selected={selected}
              onClick={() => setActiveId(view.id)}
              className={`group flex min-h-20 items-center gap-3 border-b border-border px-4 py-3 text-left transition-colors last:border-b-0 sm:border-r xl:border-b-0 ${selected ? "bg-white text-gov-primary shadow-[inset_0_-3px_0_#0b3a5b]" : "bg-surface-2 text-text-muted hover:bg-white hover:text-text-strong"}`}
            >
              <span className={`grid size-9 shrink-0 place-items-center rounded-md border ${selected ? "border-gov-primary/25 bg-gov-primary-lighter" : "border-border bg-white"}`}>
                <Icon className="size-4" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block font-mono text-[9px] font-bold text-text-subtle">0{index + 1}</span>
                <span className="mt-0.5 block text-[11px] font-bold leading-4">{view.label}</span>
              </span>
            </button>
          );
        })}
      </div>

      <div
        id={`architecture-panel-${active.id}`}
        role="tabpanel"
        aria-labelledby={`architecture-tab-${active.id}`}
        className="p-4 sm:p-5 lg:p-6"
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">{active.eyebrow}</p>
            <h3 className="mt-1 text-lg font-bold text-text-strong sm:text-xl">{active.title}</h3>
            <p className="mt-2 max-w-4xl text-xs leading-5 text-text-muted">{active.summary}</p>
          </div>
          <div className="max-w-xl rounded-lg border border-border bg-surface-2 px-4 py-3">
            <p className="text-[9px] font-bold uppercase tracking-[0.13em] text-text-subtle">Status boundary</p>
            <p className="mt-1 text-[10.5px] leading-4 text-text-muted">{active.truth}</p>
          </div>
        </div>

        <div className="mt-5 space-y-4">
          {active.lanes.map((lane) => <ArchitectureLaneView key={lane.id} lane={lane} />)}
        </div>

        <div className="mt-5 grid gap-2 lg:grid-cols-3" aria-label={`${active.label} architecture notes`}>
          {active.callouts.map((callout) => (
            <div key={callout} className="flex items-start gap-2 rounded-lg border border-border bg-white px-3 py-3">
              <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" aria-hidden />
              <p className="text-[10px] leading-4 text-text-muted">{callout}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ArchitectureLaneView({ lane }: { lane: BriefingLane }) {
  return (
    <section className={`rounded-xl border-2 p-3 sm:p-4 ${LANE_STYLES[lane.tone]} ${lane.tone === "protected" ? "border-dashed" : ""}`} aria-label={`${lane.label}: ${lane.boundary}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-current/10 pb-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-strong">{lane.label}</p>
          <p className="mt-0.5 text-[9.5px] text-text-muted">Boundary: {lane.boundary}</p>
        </div>
        {lane.outsideProtectedBoundary ? (
          <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[8.5px] font-bold uppercase tracking-wide text-text-muted">Outside protected boundary</span>
        ) : lane.tone === "protected" ? (
          <span className="rounded-full border border-danger/30 bg-white px-2.5 py-1 text-[8.5px] font-bold uppercase tracking-wide text-danger">Target protected boundary</span>
        ) : null}
      </div>

      <div
        className="mt-3 overflow-x-auto pb-2"
        role="region"
        aria-label={`${lane.label} architecture flow`}
        tabIndex={0}
      >
        <div className="flex min-w-max items-stretch">
          {lane.nodes.map((item, index) => (
            <div key={item.id} className="contents">
              <ArchitectureNodeCard item={item} />
              {lane.connectors[index] ? <DirectedConnector protocol={lane.connectors[index].protocol} receipt={lane.connectors[index].receipt} /> : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ArchitectureNodeCard({ item }: { item: BriefingNode }) {
  return (
    <article className="flex w-[176px] shrink-0 flex-col rounded-lg border border-border bg-white p-3 shadow-soft">
      <span className={`self-start rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase tracking-wide ${STATUS_STYLES[item.status]}`}>{item.status}</span>
      <h4 className="mt-3 text-[11px] font-bold leading-4 text-text-strong">{item.label}</h4>
      <p className="mt-1 font-mono text-[8.5px] leading-3.5 text-gov-primary">{item.service}</p>
      <p className="mt-2 text-[9.5px] leading-4 text-text-muted">{item.detail}</p>
    </article>
  );
}

function DirectedConnector({ protocol, receipt }: { protocol: string; receipt: string }) {
  return (
    <div className="flex w-[122px] shrink-0 flex-col items-center justify-center px-2 text-center" aria-label={`${protocol}; evidence: ${receipt}`}>
      <span className="text-[8px] font-bold uppercase tracking-wide text-gov-primary">{protocol}</span>
      <span className="my-2 flex w-full items-center" aria-hidden>
        <span className="h-px flex-1 bg-gov-primary/50" />
        <ArrowRight className="-ml-px size-4 text-gov-primary" />
      </span>
      <span className="text-[8px] leading-3 text-text-subtle">Receipt: {receipt}</span>
    </div>
  );
}

export default ArchitectureBriefing;

"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  Code2,
  ExternalLink,
  FileCheck2,
  Gauge,
  Play,
  RotateCcw,
  ShieldCheck,
  Target,
  Users,
} from "lucide-react";

import {
  DEMO_ELEMENTS,
  DEMO_EVIDENCE_META,
  DEMO_LOGISTICS,
  STRATEGIC_PROMPTS,
  totalScenarioMinutes,
  type DemoEvidenceState,
} from "@/lib/demonstration/trace";

const STATE_STYLE: Record<DemoEvidenceState, string> = {
  live: "border-success/35 bg-success-soft text-success",
  working: "border-info/30 bg-info-soft text-info",
  planned: "border-warn/35 bg-warn-soft text-warn",
};

export function DemoCommandCenter() {
  const [activeNumber, setActiveNumber] = useState(1);
  const [ready, setReady] = useState<Set<number>>(() => new Set());
  const [activePrompt, setActivePrompt] = useState(STRATEGIC_PROMPTS[0].id);
  const active = DEMO_ELEMENTS.find((element) => element.number === activeNumber) ?? DEMO_ELEMENTS[0];
  const prompt = STRATEGIC_PROMPTS.find((item) => item.id === activePrompt) ?? STRATEGIC_PROMPTS[0];
  const readyPercent = Math.round((ready.size / DEMO_ELEMENTS.length) * 100);
  const sequenceMinutes = useMemo(() => totalScenarioMinutes(), []);

  const markReady = () => {
    setReady((current) => {
      const next = new Set(current);
      if (next.has(active.number)) next.delete(active.number);
      else next.add(active.number);
      return next;
    });
  };

  const move = (direction: -1 | 1) => {
    setActiveNumber((current) => Math.min(7, Math.max(1, current + direction)));
  };

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card" aria-labelledby="demo-readiness-heading">
        <div className="compass-grid-overlay grid gap-6 px-5 py-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(340px,0.7fr)] lg:px-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-gold-light">Factor 3</span>
              <span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white/72">AWS-native path</span>
              <span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white/72">Synthetic only</span>
            </div>
            <h2 id="demo-readiness-heading" className="mt-4 text-2xl font-bold">One uninterrupted, evidence-led demonstration</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/72">
              Execute all seven scored elements in order, answer all five strategic prompts, show the live cloud and source, and keep every claim inside the evidence actually produced by this prototype.
            </p>
            <div className="mt-5 grid gap-2 sm:grid-cols-3">
              <Constraint icon={Clock3} label="Timebox" value={`At most ${DEMO_LOGISTICS.maximumMinutes} minutes`} />
              <Constraint icon={ShieldCheck} label="Data" value="No CUI, PII, or classified data" />
              <Constraint icon={Users} label="Narration" value="Led by proposed Key Personnel" />
            </div>
          </div>
          <div className="rounded-xl border border-white/15 bg-black/10 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/55">Presenter readiness</p>
                <p className="mt-1 text-3xl font-bold">{ready.size} / 7</p>
              </div>
              <div className="grid size-14 place-items-center rounded-full border border-gold-light/35 bg-gold-light/10 font-mono text-sm font-bold text-gold-light">{readyPercent}%</div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gold-light transition-all" style={{ width: `${readyPercent}%` }} /></div>
            <div className="mt-5 grid grid-cols-3 gap-2 text-center">
              <Metric value={`${sequenceMinutes}m`} label="elements" />
              <Metric value={`${DEMO_LOGISTICS.promptMinutes}m`} label="prompts" />
              <Metric value={`${DEMO_LOGISTICS.closeMinutes}m`} label="close" />
            </div>
            <button type="button" onClick={() => setReady(new Set())} disabled={ready.size === 0} className="mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-white/15 text-xs font-bold text-white/72 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40">
              <RotateCcw className="size-3.5" aria-hidden /> Reset readiness
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface shadow-card" aria-labelledby="sequence-heading">
        <div className="border-b border-border bg-white px-4 py-4 sm:px-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">Required sequence</p>
          <div className="mt-1 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 id="sequence-heading" className="text-lg font-bold text-text-strong">Seven demonstration elements</h2>
              <p className="mt-1 text-xs text-text-muted">Select an element for its exact action, focus, live screen, code evidence, talk track, and honest boundary.</p>
            </div>
            <span className="font-mono text-[10px] font-bold text-text-subtle">Solicitation 11.3 | PDF page 68</span>
          </div>
        </div>

        <div className="grid gap-2 border-b border-border p-3 sm:grid-cols-2 lg:grid-cols-7" role="tablist" aria-label="Technical demonstration elements">
          {DEMO_ELEMENTS.map((element) => {
            const selected = element.number === active.number;
            const isReady = ready.has(element.number);
            return (
              <button
                key={element.number}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setActiveNumber(element.number)}
                className={`min-h-20 rounded-lg border p-3 text-left transition-all ${selected ? "border-gov-primary bg-gov-primary text-white shadow-soft" : "border-border bg-white text-text-muted hover:-translate-y-0.5 hover:border-gov-primary/40"}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className={`font-mono text-[10px] font-bold uppercase tracking-wide ${selected ? "text-gold-light" : "text-gold-ink"}`}>Element {element.number}</span>
                  {isReady ? <CheckCircle2 className={`size-4 ${selected ? "text-gold-light" : "text-success"}`} aria-label="Ready" /> : <CircleDot className={`size-3.5 ${selected ? "text-white/45" : "text-text-subtle"}`} aria-hidden />}
                </span>
                <span className="mt-2 block text-xs font-bold leading-4">{element.shortTitle}</span>
                <span className={`mt-1 block text-[9px] ${selected ? "text-white/55" : "text-text-subtle"}`}>{element.durationMinutes} minutes</span>
              </button>
            );
          })}
        </div>

        <div className="p-4 sm:p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-gov-primary px-2.5 py-1 font-mono text-[10px] font-bold text-white">{active.number} of 7</span>
                <EvidenceChip state={active.state} />
                <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[10px] font-bold text-text-muted">{active.presenter}</span>
              </div>
              <h3 className="mt-3 text-xl font-bold text-text-strong">{active.title}</h3>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-text-muted"><strong className="text-text-strong">Action:</strong> {active.action}</p>
              <p className="mt-1 max-w-4xl text-sm leading-6 text-text-muted"><strong className="text-text-strong">Focus:</strong> {active.focus}</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <button type="button" onClick={() => move(-1)} disabled={active.number === 1} aria-label="Previous element" className="grid size-11 place-items-center rounded-md border border-border bg-white text-gov-primary hover:bg-surface-2 disabled:opacity-35"><ArrowLeft className="size-4" aria-hidden /></button>
              <Link href={active.href} className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white hover:bg-gov-primary-dark"><Play className="size-4" aria-hidden /> Open {active.screen}</Link>
              <button type="button" onClick={markReady} className={`inline-flex min-h-11 items-center gap-2 rounded-md border px-4 text-xs font-bold ${ready.has(active.number) ? "border-success/35 bg-success-soft text-success" : "border-gov-primary/25 bg-white text-gov-primary hover:bg-gov-primary-lighter"}`}>
                <Check className="size-4" aria-hidden /> {ready.has(active.number) ? "Marked ready" : "Mark ready"}
              </button>
              <button type="button" onClick={() => move(1)} disabled={active.number === 7} aria-label="Next element" className="grid size-11 place-items-center rounded-md border border-border bg-white text-gov-primary hover:bg-surface-2 disabled:opacity-35"><ArrowRight className="size-4" aria-hidden /></button>
            </div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
            <Detail title="Business value" icon={Gauge}><p>{active.value}</p></Detail>
            <Detail title="Evidence to show" icon={FileCheck2}>
              <ul className="space-y-2">{active.proof.map((item) => <Bullet key={item}>{item}</Bullet>)}</ul>
            </Detail>
            <Detail title="Open the implementation" icon={Code2}>
              <ul className="space-y-2">{active.source.map((item) => <li key={item} className="rounded border border-border bg-white px-2.5 py-2 font-mono text-[9px] text-text-muted">{item}</li>)}</ul>
            </Detail>
            <Detail title="Honest boundary" icon={AlertTriangle}>
              <p>{active.boundary}</p>
              <p className="mt-3 rounded-md border border-border bg-white p-3 text-[9.5px]"><strong className="text-text-strong">Evidence rule:</strong> {DEMO_EVIDENCE_META[active.state].description}</p>
            </Detail>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface shadow-card" aria-labelledby="prompts-heading">
        <div className="border-b border-border bg-white px-4 py-4 sm:px-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">Narrated address</p>
          <div className="mt-1 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 id="prompts-heading" className="text-lg font-bold text-text-strong">Five mandatory strategic prompts</h2>
              <p className="mt-1 text-xs text-text-muted">Narrate these answers during the linked elements. Each response states the approach without claiming knowledge or evidence the team does not have.</p>
            </div>
            <span className="font-mono text-[10px] font-bold text-text-subtle">Solicitation 11.4 | PDF pages 68 to 69</span>
          </div>
        </div>
        <div className="grid lg:grid-cols-[320px_minmax(0,1fr)]">
          <div className="border-b border-border p-3 lg:border-b-0 lg:border-r">
            {STRATEGIC_PROMPTS.map((item, index) => {
              const selected = item.id === prompt.id;
              return (
                <button key={item.id} type="button" onClick={() => setActivePrompt(item.id)} className={`mb-2 flex min-h-14 w-full items-center gap-3 rounded-lg border px-3 text-left last:mb-0 ${selected ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2"}`}>
                  <span className={`grid size-8 shrink-0 place-items-center rounded-md font-mono text-xs font-bold ${selected ? "bg-white/10 text-gold-light" : "bg-gov-primary-lighter text-gov-primary"}`}>{String.fromCharCode(97 + index)}</span>
                  <span className="min-w-0 flex-1 text-[11px] font-bold leading-4">{item.title}</span>
                  <ChevronDown className={`size-4 shrink-0 -rotate-90 ${selected ? "text-white/60" : "text-text-subtle"}`} aria-hidden />
                </button>
              );
            })}
          </div>
          <div className="p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-gold/40 bg-gold-soft px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-gold-ink">Strategic prompt</span>
              {prompt.addressDuring.map((number) => <button key={number} type="button" onClick={() => setActiveNumber(number)} className="rounded-full border border-border bg-white px-2.5 py-1 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter">Address in Element {number}</button>)}
            </div>
            <h3 className="mt-3 text-lg font-bold text-text-strong">{prompt.title}</h3>
            <p className="mt-2 text-sm leading-6 text-text-muted">{prompt.requirement}</p>
            <ol className="mt-5 space-y-3">
              {prompt.response.map((line, index) => <li key={line} className="flex gap-3 rounded-lg border border-border bg-white p-3 text-xs leading-5 text-text-muted"><span className="grid size-6 shrink-0 place-items-center rounded-full bg-gov-primary-lighter font-mono text-[10px] font-bold text-gov-primary">{index + 1}</span><span>{line}</span></li>)}
            </ol>
            <div className="mt-4 flex flex-wrap gap-2">{prompt.evidence.map((item) => <span key={item} className="inline-flex items-center gap-1.5 rounded-full border border-success/25 bg-success-soft px-2.5 py-1 text-[10px] font-bold text-success"><BadgeCheck className="size-3" aria-hidden /> {item}</span>)}</div>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-warn/30 bg-warn-soft p-4 shadow-soft" aria-label="Demonstration constraints">
        <div className="flex items-start gap-3">
          <Target className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden />
          <div>
            <p className="text-xs font-bold text-text-strong">Recording guardrails</p>
            <p className="mt-1 text-xs leading-5 text-text-muted">{DEMO_LOGISTICS.dataConstraint} {DEMO_LOGISTICS.environmentConstraint} {DEMO_LOGISTICS.presenterConstraint}</p>
          </div>
          <a href="https://github.com/SatsyilCorp/compass-demo" target="_blank" rel="noreferrer" className="ml-auto hidden min-h-10 shrink-0 items-center gap-2 rounded-md border border-warn/30 bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2 sm:inline-flex">Live repository <ExternalLink className="size-3.5" aria-hidden /></a>
        </div>
      </section>
    </div>
  );
}

function EvidenceChip({ state }: { state: DemoEvidenceState }) {
  return <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${STATE_STYLE[state]}`}>{DEMO_EVIDENCE_META[state].label}</span>;
}

function Constraint({ icon: Icon, label, value }: { icon: typeof Clock3; label: string; value: string }) {
  return <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3"><Icon className="size-4 text-gold-light" aria-hidden /><p className="mt-2 text-[9px] font-bold uppercase tracking-wide text-white/45">{label}</p><p className="mt-1 text-[10.5px] font-semibold leading-4 text-white/80">{value}</p></div>;
}

function Metric({ value, label }: { value: string; label: string }) {
  return <div className="rounded-md border border-white/10 bg-white/[0.05] p-2"><p className="font-mono text-sm font-bold text-gold-light">{value}</p><p className="mt-0.5 text-[8px] font-bold uppercase tracking-wide text-white/45">{label}</p></div>;
}

function Detail({ title, icon: Icon, children }: { title: string; icon: typeof Gauge; children: React.ReactNode }) {
  return <section className="rounded-lg border border-border bg-surface-2 p-4"><h4 className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.13em] text-text-subtle"><Icon className="size-3.5" aria-hidden /> {title}</h4><div className="mt-3 text-[10.5px] leading-5 text-text-muted">{children}</div></section>;
}

function Bullet({ children }: { children: React.ReactNode }) {
  return <li className="flex gap-2"><span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-success" /><span>{children}</span></li>;
}


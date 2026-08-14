"use client";

import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  FileInput,
  FlaskConical,
  GitBranch,
  LockKeyhole,
  RadioTower,
} from "lucide-react";

import { DEMO_ELEMENTS } from "@/lib/demonstration/trace";
import { demoOverviewForMode, type DemoOverviewElement } from "@/lib/demonstration/overview";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { useMissionDataContext } from "@/lib/mission-data-context";

const ELEMENT_VISUAL: Record<DemoOverviewElement["evidence"], { icon: typeof LockKeyhole; tone: string }> = {
  identity: { icon: LockKeyhole, tone: "border-info/25 bg-info-soft text-info" },
  control: { icon: GitBranch, tone: "border-info/25 bg-info-soft text-info" },
  public: { icon: RadioTower, tone: "border-success/30 bg-success-soft text-success" },
  rehearsal: { icon: FlaskConical, tone: "border-warn/30 bg-warn-soft text-warn" },
};

export function DemoOverview() {
  const { mode, selectMode } = useEvidenceMode();
  const { selectCurated } = useMissionDataContext();
  const overview = demoOverviewForMode(mode);
  const rehearsal = mode === "rehearsal";
  return (
    <div className="mt-6 space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)] lg:p-6">
          <div>
            <span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-gold-light">Start here</span>
            <h2 className="mt-3 text-2xl font-bold">{overview.heroTitle}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/72">
              {overview.heroBody}
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
            <GuideRule value="7" label="Scored elements" />
            <GuideRule value="1" label="Active screen at a time" />
            <GuideRule value={overview.sourceCountValue} label={overview.sourceCountLabel} />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-white p-4 shadow-card sm:p-5" aria-labelledby="scored-path-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className={`text-[10px] font-bold uppercase tracking-wide ${rehearsal ? "text-warn" : "text-success"}`}>{overview.pathKicker}</p>
            <h2 id="scored-path-heading" className="mt-1 text-xl font-bold text-text-strong">{overview.pathTitle}</h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">{overview.pathLead}</p>
          </div>
          <span className={`rounded-full border px-3 py-1.5 text-[9px] font-bold uppercase ${rehearsal ? "border-warn/30 bg-warn-soft text-warn" : "border-success/30 bg-success-soft text-success"}`}>{overview.pathBadge}</span>
        </div>

        <ol className="mt-5 grid gap-3 lg:grid-cols-2">
          {DEMO_ELEMENTS.map((element) => {
            const source = overview.elements[element.number];
            const visual = ELEMENT_VISUAL[source.evidence];
            const Icon = visual.icon;
            return (
              <li key={element.number} className="rounded-xl border border-border bg-surface-2 p-4">
                <div className="flex items-start gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-gov-primary font-mono text-sm font-bold text-white">{element.number}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-bold text-text-strong">{source.title}</h3>
                      <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${visual.tone}`}><Icon className="size-3" aria-hidden /> {source.label}</span>
                    </div>
                    <p className="mt-2 text-[10.5px] leading-5 text-text-muted"><strong className="text-text-strong">Source:</strong> {source.source}</p>
                    <p className="mt-1 text-[10.5px] leading-5 text-text-muted"><strong className="text-text-strong">Changes:</strong> {source.changes}</p>
                    <p className="mt-2 text-xs font-semibold text-gov-primary">Show: {source.action}</p>
                    {element.number === 1 ? (
                      <span className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-md border border-success/25 bg-success-soft px-3 text-[10px] font-bold text-success"><BadgeCheck className="size-3.5" aria-hidden /> Already shown by this signed-in session</span>
                    ) : (
                      <Link href={source.href} className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-[10px] font-bold text-white hover:bg-gov-primary-dark">Open Element {element.number} <ArrowRight className="size-3.5" aria-hidden /></Link>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="rounded-xl border border-warn/25 bg-warn-soft/35 p-4 shadow-card sm:p-5" aria-labelledby="public-path-heading">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-warn text-white"><FileInput className="size-5" aria-hidden /></span>
          <div className="min-w-0 flex-1">
            <span className="rounded-full border border-warn/30 bg-white px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-warn">{overview.boundaryKicker}</span>
            <h2 id="public-path-heading" className="mt-2 text-lg font-bold text-text-strong">{overview.boundaryTitle}</h2>
            <p className="mt-1 max-w-4xl text-xs leading-5 text-text-muted">
              {overview.boundaryBody}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {rehearsal ? <Link href="/rehearsal/ingest/" className="inline-flex min-h-10 items-center gap-2 rounded-md bg-warn px-3 text-[10px] font-bold text-white hover:brightness-95">Continue rehearsal <ArrowRight className="size-3.5" aria-hidden /></Link> : <Link href="/admin/acquisition/" className="inline-flex min-h-10 items-center gap-2 rounded-md bg-success px-3 text-[10px] font-bold text-white hover:brightness-95">Stay on live public evidence <ArrowRight className="size-3.5" aria-hidden /></Link>}
              <Link href={rehearsal ? "/admin/acquisition/" : "/rehearsal/"} onClick={rehearsal ? () => { selectMode("live"); selectCurated(); } : undefined} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-warn/30 bg-white px-3 text-[10px] font-bold text-warn hover:bg-warn-soft">{rehearsal ? "Return to live selection" : "Explicitly enter rehearsal"} <ArrowRight className="size-3.5" aria-hidden /></Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function GuideRule({ value, label }: { value: string; label: string }) {
  return <div className="rounded-lg border border-white/12 bg-white/[0.07] p-3"><p className="font-mono text-xl font-bold text-gold-light">{value}</p><p className="mt-1 text-[9px] font-bold uppercase tracking-wide text-white/55">{label}</p></div>;
}

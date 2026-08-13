import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  Cloud,
  Database,
  FileInput,
  FlaskConical,
  GitBranch,
  LockKeyhole,
  RadioTower,
} from "lucide-react";

import { DEMO_ELEMENTS } from "@/lib/demonstration/trace";

const ELEMENT_SOURCE: Record<number, {
  label: string;
  source: string;
  changes: string;
  icon: typeof LockKeyhole;
  tone: string;
}> = {
  1: {
    label: "Identity evidence",
    source: "The signed-in Cognito identity and role mapping",
    changes: "Only when a user signs in or their approved role changes",
    icon: LockKeyhole,
    tone: "border-info/25 bg-info-soft text-info",
  },
  2: {
    label: "Control evidence",
    source: "GitHub, Terraform, SAM, policy checks, and retained CI/CD artifacts",
    changes: "Only when a reviewed commit moves through the delivery path",
    icon: GitBranch,
    tone: "border-info/25 bg-info-soft text-info",
  },
  3: {
    label: "User-selected input",
    source: "One sanitized file or a clearly labeled prepared sample",
    changes: "Only after the presenter submits a file or starts synthetic updates",
    icon: FileInput,
    tone: "border-gold/30 bg-gold-soft text-gold-ink",
  },
  4: {
    label: "Synthetic mission data",
    source: "The exact accepted Element 3 batch and its processing receipts",
    changes: "After a successful demo ingestion event",
    icon: Database,
    tone: "border-warn/30 bg-warn-soft text-warn",
  },
  5: {
    label: "Sanitized model evidence",
    source: "Sanitized training documents, model artifacts, and AWS run receipts",
    changes: "Only after an explicit model lifecycle action",
    icon: FlaskConical,
    tone: "border-warn/30 bg-warn-soft text-warn",
  },
  6: {
    label: "Synthetic mission data",
    source: "The active curated demo portfolio and linked model results",
    changes: "After accepted ingestion, analysis, or evidence-set selection",
    icon: Database,
    tone: "border-warn/30 bg-warn-soft text-warn",
  },
  7: {
    label: "Synthetic governed export",
    source: "The active demo portfolio filtered by the signed-in user's scope",
    changes: "Only after an export request and required approval",
    icon: Cloud,
    tone: "border-warn/30 bg-warn-soft text-warn",
  },
};

export function DemoOverview() {
  return (
    <div className="mt-6 space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)] lg:p-6">
          <div>
            <span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-gold-light">Start here</span>
            <h2 className="mt-3 text-2xl font-bold">One scored story, with public evidence kept separate</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/72">
              Present Elements 1 through 7 in order. The scored mission workflow uses sanitized or synthetic data. Use the optional public evidence lane only when you want to show real records from named public APIs.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
            <GuideRule value="7" label="Scored elements" />
            <GuideRule value="1" label="Active screen at a time" />
            <GuideRule value="2" label="Separated evidence lanes" />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-white p-4 shadow-card sm:p-5" aria-labelledby="scored-path-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Primary presentation path</p>
            <h2 id="scored-path-heading" className="mt-1 text-xl font-bold text-text-strong">Scored seven-element demonstration</h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">Each step below names the exact source before you open it.</p>
          </div>
          <span className="rounded-full border border-warn/30 bg-warn-soft px-3 py-1.5 text-[9px] font-bold uppercase text-warn">Sanitized and synthetic mission workflow</span>
        </div>

        <ol className="mt-5 grid gap-3 lg:grid-cols-2">
          {DEMO_ELEMENTS.map((element) => {
            const source = ELEMENT_SOURCE[element.number];
            const Icon = source.icon;
            return (
              <li key={element.number} className="rounded-xl border border-border bg-surface-2 p-4">
                <div className="flex items-start gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-gov-primary font-mono text-sm font-bold text-white">{element.number}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-bold text-text-strong">{element.shortTitle}</h3>
                      <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${source.tone}`}><Icon className="size-3" aria-hidden /> {source.label}</span>
                    </div>
                    <p className="mt-2 text-[10.5px] leading-5 text-text-muted"><strong className="text-text-strong">Source:</strong> {source.source}</p>
                    <p className="mt-1 text-[10.5px] leading-5 text-text-muted"><strong className="text-text-strong">Changes:</strong> {source.changes}</p>
                    <p className="mt-2 text-xs font-semibold text-gov-primary">Show: {element.action}</p>
                    {element.number === 1 ? (
                      <span className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-md border border-success/25 bg-success-soft px-3 text-[10px] font-bold text-success"><BadgeCheck className="size-3.5" aria-hidden /> Already shown by this signed-in session</span>
                    ) : (
                      <Link href={element.href} className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-[10px] font-bold text-white hover:bg-gov-primary-dark">Open Element {element.number} <ArrowRight className="size-3.5" aria-hidden /></Link>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="rounded-xl border border-success/25 bg-success-soft/35 p-4 shadow-card sm:p-5" aria-labelledby="public-path-heading">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-success text-white"><RadioTower className="size-5" aria-hidden /></span>
          <div className="min-w-0 flex-1">
            <span className="rounded-full border border-success/30 bg-white px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-success">Optional live public evidence</span>
            <h2 id="public-path-heading" className="mt-2 text-lg font-bold text-text-strong">Real source operations and cross-source intelligence</h2>
            <p className="mt-1 max-w-4xl text-xs leading-5 text-text-muted">
              This lane is not the synthetic mission workflow. It pulls bounded records from named public authorities on demand or on responsible schedules, retains the source receipt, and publishes only accepted snapshots.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href="/admin/acquisition/" className="inline-flex min-h-10 items-center gap-2 rounded-md bg-success px-3 text-[10px] font-bold text-white hover:brightness-95">1. Pull named public sources <ArrowRight className="size-3.5" aria-hidden /></Link>
              <Link href="/intelligence/" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-success/30 bg-white px-3 text-[10px] font-bold text-success hover:bg-success-soft">2. Inspect accepted public evidence <ArrowRight className="size-3.5" aria-hidden /></Link>
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

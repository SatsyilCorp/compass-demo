"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CheckCircle2,
  Database,
  FlaskConical,
  RadioTower,
  ShieldCheck,
} from "lucide-react";

import { CompassWordmark } from "@/components/shell/brand";
import { GovBanner } from "@/components/shell/gov-banner";
import { SkipNav } from "@/components/shell/skip-nav";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { useMissionDataContext } from "@/lib/mission-data-context";

const REHEARSAL_RULES = [
  {
    icon: Database,
    title: "Deterministic synthetic records",
    detail: "Every fixture is non-authoritative and remains visibly labeled throughout the workflow.",
  },
  {
    icon: ShieldCheck,
    title: "No live substitution",
    detail: "Public APIs and operational records are not represented by synthetic results while rehearsal is active.",
  },
  {
    icon: CheckCircle2,
    title: "Repeatable presentation path",
    detail: "Known inputs and receipts make quality, lineage, model, approval, and export behavior reproducible.",
  },
] as const;

export default function RehearsalLandingPage() {
  const router = useRouter();
  const { hydrated, mode, selectMode } = useEvidenceMode();
  const { selectCurated } = useMissionDataContext();
  const active = mode === "rehearsal";

  const startRehearsal = () => {
    selectMode("rehearsal");
    selectCurated();
    router.push("/admin/demo/");
  };

  const returnToLive = () => {
    selectMode("live");
    selectCurated();
    router.push("/admin/acquisition/");
  };

  return (
    <>
      <SkipNav />
      <GovBanner />
      <div className="min-h-screen bg-bg">
        <header className="border-b border-border bg-white" role="banner">
          <div className="mx-auto flex min-h-20 max-w-[1200px] items-center justify-between gap-4 px-4 sm:px-6">
            <Link href="/" aria-label="Compass home" className="rounded-md focus-visible:outline-offset-4">
              <CompassWordmark tone="navy" />
            </Link>
            <button type="button" disabled={!hydrated} onClick={returnToLive} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-success/30 bg-success-soft px-4 text-xs font-bold text-success hover:bg-white disabled:cursor-wait disabled:opacity-60">
              <RadioTower className="size-4" aria-hidden /> Live public evidence
            </button>
          </div>
        </header>

        <main id="main-content" tabIndex={-1}>
          <section className="bg-gov-primary-dark text-white">
            <div className="mx-auto grid max-w-[1200px] gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)] lg:items-center lg:py-20">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-gold-light">Separate evidence boundary</p>
                <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">Rehearse the product without confusing fixtures for live evidence.</h1>
                <p className="mt-5 max-w-2xl text-base leading-7 text-white/70">
                  This route is the explicit entry point for deterministic synthetic data. Rehearsal is persistent in this browser until you choose Live public evidence again.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={!hydrated}
                    onClick={startRehearsal}
                    className="inline-flex min-h-12 items-center gap-2 rounded-md bg-gold-light px-5 text-sm font-bold text-gov-primary-darker shadow-elevated hover:bg-white disabled:cursor-wait disabled:opacity-60"
                  >
                    <FlaskConical className="size-4" aria-hidden /> {active ? "Continue rehearsal" : "Activate rehearsal"} <ArrowRight className="size-4" aria-hidden />
                  </button>
                  <button
                    type="button"
                    disabled={!hydrated}
                    onClick={returnToLive}
                    className="inline-flex min-h-12 items-center gap-2 rounded-md border border-white/25 px-5 text-sm font-bold text-white hover:bg-white/10 disabled:cursor-wait disabled:opacity-60"
                  >
                    <RadioTower className="size-4" aria-hidden /> Use live public evidence
                  </button>
                </div>
              </div>

              <aside className={`rounded-xl border p-6 ${active ? "border-gold-light/40 bg-gold-light/10" : "border-white/15 bg-white/[0.06]"}`} aria-label="Current evidence mode">
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-white/55">Current persistent mode</p>
                <div className="mt-4 flex items-center gap-3">
                  <span className={`grid size-11 place-items-center rounded-lg ${active ? "bg-gold-light text-gov-primary-darker" : "bg-success text-white"}`}>
                    {active ? <FlaskConical className="size-5" aria-hidden /> : <RadioTower className="size-5" aria-hidden />}
                  </span>
                  <div>
                    <p className="text-lg font-bold">{active ? "Rehearsal active" : "Live public evidence active"}</p>
                    <p className="mt-1 text-xs text-white/60">{active ? "Synthetic adapters may run" : "Synthetic adapters remain disabled"}</p>
                  </div>
                </div>
              </aside>
            </div>
          </section>

          <section className="mx-auto max-w-[1200px] px-4 py-14 sm:px-6">
            <div className="grid gap-4 md:grid-cols-3">
              {REHEARSAL_RULES.map(({ icon: Icon, title, detail }) => (
                <article key={title} className="rounded-xl border border-border bg-white p-5 shadow-card">
                  <span className="grid size-10 place-items-center rounded-lg bg-warn-soft text-warn"><Icon className="size-5" aria-hidden /></span>
                  <h2 className="mt-4 text-base font-bold text-text-strong">{title}</h2>
                  <p className="mt-2 text-sm leading-6 text-text-muted">{detail}</p>
                </article>
              ))}
            </div>
            <p className="mt-8 rounded-lg border border-warn/25 bg-warn-soft px-4 py-3 text-xs leading-5 text-warn">
              Rehearsal is a presentation and interface-validation mode. It does not prove current external-source availability, operational decisions, accreditation, or Government production use.
            </p>
          </section>
        </main>
      </div>
    </>
  );
}

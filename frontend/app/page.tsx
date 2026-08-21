"use client";

import Link from "next/link";
import { SINGLE_LIVE_MODE } from "@/lib/evidence-mode";
import {
  ArrowRight,
  BarChart3,
  Braces,
  CheckCircle2,
  Database,
  FileCheck2,
  Network,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { CompassWordmark, TrustIndicator } from "@/components/shell/brand";
import { SkipNav } from "@/components/shell/skip-nav";
import { useEvidenceMode } from "@/lib/evidence-mode-context";

const missionFlow = [
  { number: "01", label: "Acquire", detail: "Continuously collect bounded pages from named public authorities, or accept one sanitized public file." },
  { number: "02", label: "Govern", detail: "Retain hashes, quality outcomes, identities, owners, stewards, and exact processing lineage." },
  { number: "03", label: "Classify", detail: "Run the champion classifier on accepted public narratives and retain its versioned receipts." },
  { number: "04", label: "Decide", detail: "Connect source changes, model signals, citations, and review flags in one live workspace." },
  { number: "05", label: "Release", detail: "Create a portable package with source, model, review, and lineage fields intact." },
];

const rehearsalMissionFlow = [
  { number: "01", label: "Select", detail: "Choose an isolated synthetic fixture or explicitly upload a rehearsal file." },
  { number: "02", label: "Govern", detail: "Exercise hashes, quality outcomes, identities, owners, stewards, and processing lineage." },
  { number: "03", label: "Classify", detail: "Run deterministic rehearsal model contracts without claiming a live cloud execution." },
  { number: "04", label: "Review", detail: "Practice the decision workflow with synthetic labels visible on every surface." },
  { number: "05", label: "Exit", detail: "Return to live public evidence without allowing rehearsal records into the live catalog." },
];

const capabilities = [
  {
    Icon: Database,
    title: "A governed data foundation",
    body: "Named public authorities, quality gates, role-aware access, and end-to-end receipts make every visible record explainable.",
  },
  {
    Icon: BarChart3,
    title: "Decision-ready intelligence",
    body: "Observed source changes, real classifier outputs, transparent review rules, and citations focus attention without claiming portfolio completeness.",
  },
  {
    Icon: ShieldCheck,
    title: "Evidence in every action",
    body: SINGLE_LIVE_MODE
      ? "Model runs, source snapshots, decisions, and releases carry traceable evidence, and synthetic demonstration content is always labeled."
      : "Model runs, source snapshots, decisions, and releases carry traceable evidence. Synthetic data is available only after explicit rehearsal selection.",
  },
];

/**
 * Design decision: use the editorial authority of the prototype's Variant C,
 * the operational proof panel from Variant B, and the five-step flow from
 * Variant A. This synthesis reads as mission software, not a marketing site.
 */
export default function LandingPage() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  const workspaceHref = rehearsal ? "/rehearsal/" : "/login/";
  const steps = rehearsal ? rehearsalMissionFlow : missionFlow;
  return (
    <>
      <SkipNav />
      <main id="main-content" tabIndex={-1} className="min-h-screen bg-surface">
        <header className="relative z-20 border-b border-border bg-white" role="banner">
          <div aria-hidden className="h-1 bg-gradient-to-r from-gov-primary via-gov-primary to-gold" />
          <div className="mx-auto flex min-h-20 max-w-[1440px] items-center gap-4 px-5 sm:px-8 lg:px-12">
            <Link
              href="/"
              aria-label="Compass home"
              className="rounded-md focus-visible:outline-offset-4"
            >
              <CompassWordmark tone="navy" />
            </Link>
            <nav aria-label="Landing page" className="ml-auto flex items-center gap-2 sm:gap-4">
              <a
                href="#capabilities"
                className="hidden min-h-11 items-center rounded-md px-3 text-sm font-semibold text-text-muted transition-colors hover:bg-surface-2 hover:text-text-strong md:inline-flex"
              >
                Mission capabilities
              </a>
              <Link
                href={workspaceHref}
                className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-sm font-semibold text-white shadow-soft transition-colors hover:bg-gov-primary-vivid sm:px-5"
              >
                {rehearsal ? "Open rehearsal" : "Enter Compass"}
                <ArrowRight className="size-4" aria-hidden />
              </Link>
            </nav>
          </div>
        </header>

        <section className="relative isolate overflow-hidden bg-gov-primary-dark text-white">
          <div className="compass-radar pointer-events-none absolute inset-0" aria-hidden />
          <div className="pointer-events-none absolute inset-y-0 right-0 hidden w-1/2 bg-gradient-to-l from-black/20 to-transparent lg:block" aria-hidden />
          <div className="relative mx-auto grid min-h-[680px] max-w-[1440px] gap-12 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[minmax(0,1.12fr)_minmax(22rem,0.62fr)] lg:items-center lg:px-12 lg:py-24">
            <div className="max-w-4xl compass-rise">
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-gold-light">
                  {rehearsal ? "Explicit synthetic rehearsal" : "Live public S&T evidence intelligence"}
                </p>
                <span aria-hidden className="h-px w-10 bg-gold-light/60" />
                <p className="text-xs font-semibold text-white/60">Technical demonstration</p>
              </div>
              <h1 className="mt-7 max-w-4xl font-display text-[clamp(2.8rem,7vw,6.25rem)] font-semibold leading-[0.94] tracking-[-0.045em] text-white">
                See the decision.
                <span className="mt-1 block text-gold-light">Prove the path.</span>
              </h1>
              <p className="mt-8 max-w-2xl text-base leading-7 text-white/72 sm:text-xl sm:leading-8">
                {rehearsal
                  ? "Compass is currently isolated in rehearsal mode. Synthetic fixtures remain visibly labeled and never substitute for unavailable live evidence."
                  : "Compass continuously turns bounded public research evidence into governed records, real model receipts, cited intelligence, and review-ready decisions."}
              </p>
              <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Link
                  href={workspaceHref}
                  className="inline-flex min-h-12 items-center justify-center gap-3 rounded-md bg-gold-light px-6 text-sm font-bold text-gov-primary-darker shadow-elevated transition-transform hover:-translate-y-0.5"
                >
                  {rehearsal ? "Open rehearsal workspace" : "Launch mission workspace"}
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
                <a
                  href="#mission-flow"
                  className="inline-flex min-h-12 items-center justify-center rounded-md border border-white/25 px-6 text-sm font-semibold text-white transition-colors hover:border-white/50 hover:bg-white/5"
                >
                  Explore the evidence flow
                </a>
              </div>
              <div className="mt-10">
                <TrustIndicator tone="dark" />
              </div>
            </div>

            <aside
              aria-label="Operational proof preview"
              className="compass-proof-panel relative overflow-hidden rounded-xl border border-white/15 bg-white/[0.065] p-5 shadow-2xl backdrop-blur-sm sm:p-7"
            >
              <div className="flex items-start justify-between gap-4 border-b border-white/12 pb-5">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-white/45">
                    Decision evidence
                  </p>
                  <h2 className="mt-2 text-lg font-semibold text-white">
                    {rehearsal ? "Isolated rehearsal path" : "Live evidence path"}
                  </h2>
                </div>
                <span className="grid size-11 shrink-0 place-items-center rounded-full bg-success/15 text-emerald-200">
                  <CheckCircle2 className="size-5" aria-hidden />
                </span>
              </div>

              <div className="divide-y divide-white/10">
                <ProofRow Icon={FileCheck2} label={rehearsal ? "Fixture source" : "Public sources"} value={rehearsal ? "Synthetic" : "Named"} />
                <ProofRow Icon={Network} label="Source lineage" value={rehearsal ? "Isolated" : "Receipt bound"} />
                <ProofRow Icon={Sparkles} label="Model evidence" value={rehearsal ? "Rehearsed" : "Versioned"} />
                {SINGLE_LIVE_MODE ? null : <ProofRow Icon={Braces} label="Evidence mode" value={rehearsal ? "Rehearsal" : "Live only"} />}
              </div>

              <div className="mt-5 rounded-lg border border-white/10 bg-black/15 p-4">
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-gold-light">
                  Recommended next action
                </p>
                <p className="mt-2 text-sm font-semibold leading-6 text-white">
                  {rehearsal
                    ? "Practice the full path, inspect every synthetic label, then return to the live evidence boundary."
                    : "Inspect what changed at each authority, review the model route and source record, then release a provenance-bound evidence package."}
                </p>
              </div>
            </aside>
          </div>
        </section>

        <section id="mission-flow" aria-labelledby="mission-flow-title" className="border-b border-border bg-bg scroll-mt-20">
          <div className="mx-auto max-w-[1440px] px-5 py-16 sm:px-8 lg:px-12 lg:py-20">
            <div className="max-w-2xl">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-gold-ink">One controlled path</p>
              <h2 id="mission-flow-title" className="mt-3 text-3xl font-bold text-text-strong sm:text-4xl">
                {rehearsal ? "An isolated path for a deterministic rehearsal" : "From named public authority to cited decision"}
              </h2>
              <p className="mt-4 text-base leading-7 text-text-muted">
                {rehearsal
                  ? "Every stage retains the rehearsal label so a presenter can never confuse a fixture with current public evidence."
                  : "Every stage carries its own proof, with the context preserved for the next person in the decision chain."}
              </p>
            </div>
            <ol className="mt-10 grid border-y border-border sm:grid-cols-2 lg:grid-cols-5">
              {steps.map((step, index) => (
                <li
                  key={step.label}
                  className="group relative min-h-52 border-b border-border p-5 last:border-b-0 sm:border-r sm:[&:nth-child(even)]:border-r-0 lg:border-b-0 lg:[&:nth-child(even)]:border-r lg:last:border-r-0"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-gold-ink">{step.number}</span>
                    {index < steps.length - 1 && (
                      <ArrowRight className="hidden size-4 text-border-strong lg:block" aria-hidden />
                    )}
                  </div>
                  <h3 className="mt-8 text-xl font-bold text-text-strong">{step.label}</h3>
                  <p className="mt-3 text-sm leading-6 text-text-muted">{step.detail}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="capabilities" aria-labelledby="capabilities-title" className="scroll-mt-20 bg-white">
          <div className="mx-auto max-w-[1440px] px-5 py-16 sm:px-8 lg:px-12 lg:py-24">
            <div className="grid gap-8 lg:grid-cols-[0.7fr_1.3fr] lg:gap-16">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-gold-ink">Built for scrutiny</p>
                <h2 id="capabilities-title" className="mt-3 text-3xl font-bold text-text-strong sm:text-4xl">
                  Mission clarity with technical depth on demand
                </h2>
                <p className="mt-4 text-base leading-7 text-text-muted">
                  Leaders see the brief first. Analysts can drill into quality, lineage, model,
                  and audit evidence without leaving the workflow.
                </p>
              </div>
              <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border md:grid-cols-3">
                {capabilities.map(({ Icon, title, body }) => (
                  <article key={title} className="bg-surface p-6 lg:p-7">
                    <span className="grid size-11 place-items-center rounded-md bg-gov-primary-lighter text-gov-primary">
                      <Icon className="size-5" aria-hidden />
                    </span>
                    <h3 className="mt-6 text-lg font-bold text-text-strong">{title}</h3>
                    <p className="mt-3 text-sm leading-6 text-text-muted">{body}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="bg-gov-primary text-white">
          <div className="mx-auto flex max-w-[1440px] flex-col gap-8 px-5 py-14 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-12">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-gold-light">{rehearsal ? "Ready to rehearse" : "Ready for the mission brief"}</p>
              <h2 className="mt-3 max-w-2xl text-3xl font-bold text-white">{rehearsal ? "Practice the full path without mixing synthetic and live evidence." : "Walk the full evidence path in one working prototype."}</h2>
            </div>
            <Link href={workspaceHref} className="inline-flex min-h-12 shrink-0 items-center justify-center gap-3 rounded-md bg-white px-6 text-sm font-bold text-gov-primary shadow-soft transition-transform hover:-translate-y-0.5">
              {rehearsal ? "Open rehearsal" : "Enter Compass"}
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </section>

        <footer className="border-t border-border bg-white" role="contentinfo">
          <div className="mx-auto flex max-w-[1440px] flex-col gap-4 px-5 py-8 text-sm text-text-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
            <CompassWordmark tone="navy" />
            <p>Built by Satsyil Corp for technical evaluation. Not an official U.S. Navy or ONR system.</p>
          </div>
        </footer>
      </main>
    </>
  );
}

function ProofRow({ Icon, label, value }: { Icon: typeof Database; label: string; value: string }) {
  return (
    <div className="flex min-h-16 items-center gap-3 py-3">
      <Icon className="size-4 shrink-0 text-gold-light" aria-hidden />
      <span className="text-sm text-white/60">{label}</span>
      <strong className="ml-auto text-right text-sm font-semibold text-white">{value}</strong>
    </div>
  );
}

import Link from "next/link";
import { ShieldCheck, Network, Gauge } from "lucide-react";
import { CompassMark, CompassWordmark, PrototypePill } from "@/components/shell/brand";
import { SkipNav } from "@/components/shell/skip-nav";

/**
 * Public landing page. Static (no auth check) — introduces Compass and
 * routes into the app via /login/ (built by the identity/element-1 page).
 */
export default function LandingPage() {
  return (
    <>
      <SkipNav />
      <main id="main-content" tabIndex={-1} className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
        {/* LEFT — Navy brand panel */}
        <section className="compass-aurora relative hidden overflow-hidden lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">
          <div aria-hidden className="compass-grid-overlay absolute inset-0 opacity-60" />
          <div className="relative compass-rise">
            <CompassWordmark tone="light" />
          </div>

          <div className="relative max-w-md">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gold">
              Technical Demonstration
            </p>
            <h1 className="mt-3 font-display text-4xl leading-[1.1] text-white xl:text-5xl">
              S&amp;T portfolio intelligence,
              <br />
              from raw file to <span className="italic text-gold">decision</span>.
            </h1>
            <p className="mt-4 text-[15px] leading-relaxed text-white/70">
              Ingest &rarr; quality gate &rarr; curated catalog &rarr; lineage &rarr; topic-model
              analytics &rarr; executive dashboard &rarr; governed export, end to end over a
              research-grant portfolio.
            </p>

            <ul className="mt-8 space-y-3">
              <Feature
                Icon={Network}
                title="Catalog &amp; lineage"
                body="Every curated table traced back to its source file and quality gate run."
              />
              <Feature
                Icon={Gauge}
                title="Topic-model analytics"
                body="A governed model surfaces investment concentration and a portfolio recommendation."
              />
              <Feature
                Icon={ShieldCheck}
                title="Governed by design"
                body="Row- and column-level security enforced end to end; every export is audited."
              />
            </ul>
          </div>

          <div className="relative flex items-center gap-3">
            <PrototypePill />
            <span className="text-[11px] text-white/45">All data shown is synthetic.</span>
          </div>
        </section>

        {/* RIGHT — entry point */}
        <section className="flex items-center justify-center bg-bg px-6 py-12">
          <div className="w-full max-w-sm compass-rise">
            <div className="mb-8 flex flex-col items-center gap-3 lg:hidden">
              <CompassMark tone="navy" className="h-12 w-12" />
              <CompassWordmark tone="navy" />
            </div>

            <h2 className="font-display text-2xl text-text-strong">Enter the demo</h2>
            <p className="mt-1.5 text-sm text-text-muted">
              Compass — a Navy/ONR S&amp;T Portfolio Intelligence prototype built by Satsyil Corp
              for a competitive proposal technical evaluation. Not an official U.S. Navy or ONR
              system.
            </p>

            <Link
              href="/login/"
              className="mt-7 inline-flex w-full items-center justify-center gap-2 rounded-md bg-gov-primary px-4 py-3 text-sm font-semibold text-white shadow-card transition-colors hover:bg-action-hover"
            >
              Continue to sign in
            </Link>

            <div className="mt-10 border-t border-border pt-5">
              <p className="text-center text-[11px] text-text-subtle">
                Built by Satsyil Corp · Synthetic data only
              </p>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}

function Feature({
  Icon,
  title,
  body,
}: {
  Icon: typeof ShieldCheck;
  title: string;
  body: string;
}) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md border border-white/15 bg-white/5 text-gold">
        <Icon className="size-4" aria-hidden />
      </span>
      <span>
        <span className="block text-[13px] font-semibold text-white">{title}</span>
        <span className="block text-[12.5px] leading-snug text-white/60">{body}</span>
      </span>
    </li>
  );
}

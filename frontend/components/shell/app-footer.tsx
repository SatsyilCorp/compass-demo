import { CompassMark, PrototypePill } from "./brand";

/**
 * Compass footer — a quiet Navy keyline strip with the mark, the prototype
 * disclosure, and a repeat of the "synthetic data only" note so it reads on
 * every page regardless of scroll position at the top.
 */
export function AppFooter() {
  return (
    <footer className="mt-16 border-t border-white/10 bg-gov-primary text-white" role="contentinfo">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="flex items-center gap-3">
          <CompassMark tone="light" className="h-7 w-7" />
          <div className="text-xs leading-tight">
            <p className="font-semibold">Compass — S&amp;T Portfolio Intelligence</p>
            <p className="text-white/60">Technical demonstration prototype · Satsyil Corp</p>
          </div>
        </div>
        <PrototypePill />
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-[1400px] px-6 py-3 text-[11px] text-white/50">
          Synthetic data only. Nothing shown here reflects a real U.S. Navy or ONR program, award,
          or funding decision.
        </p>
      </div>
    </footer>
  );
}

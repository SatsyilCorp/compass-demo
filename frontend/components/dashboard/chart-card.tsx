"use client";

import clsx from "clsx";
import { Info } from "lucide-react";

/**
 * Chart frame. Adapted from a prior dashboard chart-card block
 * (framer-motion → the `compass-rise` CSS animation, its design tokens →
 * Compass tokens), plus a `provenance` slot.
 *
 * `provenance` is the honesty affordance: every chart on the Compass dashboard
 * states which field of `GET /dashboard` it is drawn from, and any figure that
 * is *derived* in the browser rather than returned by the API says so. An
 * evaluator should never have to guess whether a number came from the data or
 * from the demo.
 */
type Props = {
  title: string;
  hint?: string;
  provenance?: string;
  className?: string;
  action?: React.ReactNode;
  empty?: boolean;
  emptyText?: string;
  children: React.ReactNode;
};

export function ChartCard({
  title,
  hint,
  provenance,
  className,
  action,
  empty,
  emptyText,
  children,
}: Props) {
  return (
    <section
      className={clsx(
        "compass-rise flex h-full flex-col rounded-md border border-border bg-surface p-4 shadow-soft",
        className,
      )}
    >
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[14.5px] font-semibold text-text-strong">{title}</h3>
          {hint ? <p className="mt-0.5 text-[11.5px] leading-snug text-text-muted">{hint}</p> : null}
        </div>
        {action}
      </header>

      <div className="min-h-0 flex-1">
        {empty ? (
          <div className="flex h-full min-h-[140px] items-center justify-center rounded border border-dashed border-border px-4 text-center text-[12px] text-text-subtle">
            {emptyText ?? "No data in this scope."}
          </div>
        ) : (
          children
        )}
      </div>

      {provenance ? (
        <p className="mt-3 flex items-start gap-1.5 border-t border-border-2 pt-2.5 text-[10.5px] leading-snug text-text-subtle">
          <Info className="mt-[1px] size-3 shrink-0" aria-hidden />
          <span>{provenance}</span>
        </p>
      ) : null}
    </section>
  );
}

export default ChartCard;

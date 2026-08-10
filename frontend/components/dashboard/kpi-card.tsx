"use client";

import Link from "next/link";
import clsx from "clsx";
import { EyeOff, Lock } from "lucide-react";

import { NumberTick } from "./number-tick";

/**
 * KPI tile. Adapted from a prior dashboard kpi-card block,
 * re-tokenized to the Compass (USWDS/Navy) palette, with framer-motion swapped
 * for the `compass-rise` CSS animation (motion is not a dependency here) and
 * one addition Compass needs:
 *
 *   `masked` — the value is not zero and not missing, it is withheld by
 *   column-level security (viewer persona has `SELECT (amount_usd)` revoked).
 *   Rendering that as "$0" would be a lie, so the tile states it plainly.
 */
type Props = {
  label: string;
  /** Numeric value (animated) or a pre-formatted string. Ignored when masked. */
  value: number | string;
  /** Formatter applied to a numeric value while it animates. */
  format?: (n: number) => string;
  sublabel?: string;
  /** Withheld by CLS — renders the masked treatment instead of the value. */
  masked?: boolean;
  /** Why it is masked (shown under the masked value). */
  maskedReason?: string;
  href?: string;
  Icon?: React.ComponentType<{ className?: string }>;
  /** Draws attention to a tile that needs action (open anomalies, expiries). */
  tone?: "default" | "warn" | "danger";
};

const TONE_RING: Record<NonNullable<Props["tone"]>, string> = {
  default: "border-border",
  warn: "border-warn",
  danger: "border-danger",
};

export function KpiCard({
  label,
  value,
  format,
  sublabel,
  masked,
  maskedReason,
  href,
  Icon,
  tone = "default",
}: Props) {
  const body = (
    <>
      <header className="flex items-start justify-between gap-2">
        <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
          {label}
        </p>
        {Icon ? <Icon className="size-4 text-text-subtle" /> : null}
      </header>

      {masked ? (
        <div className="mt-2">
          <span className="inline-flex items-center gap-1.5 rounded bg-surface-2 px-2 py-1 text-[13px] font-semibold text-text-muted">
            <EyeOff className="size-3.5" aria-hidden />
            Masked
          </span>
          <p className="mt-1.5 flex items-start gap-1 text-[11px] leading-snug text-text-subtle">
            <Lock className="mt-[1px] size-3 shrink-0" aria-hidden />
            <span>{maskedReason ?? "Column-level security withholds this figure from your role."}</span>
          </p>
        </div>
      ) : (
        <>
          <div className="mt-2 text-[28px] font-semibold leading-none tracking-tight text-text-strong">
            {typeof value === "number" ? <NumberTick value={value} format={format} /> : value}
          </div>
          {sublabel ? <p className="mt-1.5 text-[11px] text-text-muted">{sublabel}</p> : null}
        </>
      )}
    </>
  );

  return (
    <div
      className={clsx(
        "compass-rise rounded-md border bg-surface p-4 shadow-soft transition-shadow",
        TONE_RING[tone],
        href && "hover:shadow-card",
      )}
    >
      {href ? (
        <Link href={href} className="block focus:outline-none">
          {body}
        </Link>
      ) : (
        body
      )}
    </div>
  );
}

export default KpiCard;

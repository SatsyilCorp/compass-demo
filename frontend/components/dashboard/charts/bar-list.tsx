"use client";

import clsx from "clsx";

import { SERIES_PRIMARY } from "../chart-theme";

/**
 * Ranked horizontal bars in plain HTML/CSS.
 *
 * Why not Recharts here: these categories have long names (program areas, org
 * units, topic labels). A ranked list of long-named categories is the one form
 * where an SVG chart reliably goes wrong — tick labels get truncated and
 * value labels at the bar tip get clipped by the plot area. HTML bars measure
 * themselves, wrap nothing, clip nothing, and stay readable at any width.
 * Recharts is still used for the two time-series charts, where an axis is
 * genuinely doing work.
 *
 * Form rules held here (see the dataviz method):
 *   - one series → one color for every bar; length carries magnitude. No
 *     value-ramp across nominal categories.
 *   - direct value label at the tip; a secondary figure appears on hover/focus
 *     so the resting state stays quiet.
 *   - a real table underneath (`<table>` semantics via role) so the numbers are
 *     never gated behind color or hover.
 */
export type BarListItem = {
  key: string;
  label: string;
  /** Numeric magnitude driving bar length. */
  value: number;
  /** Pre-formatted primary value shown at the bar tip. */
  valueLabel: string;
  /** Optional secondary figure, revealed on hover/focus. */
  secondaryLabel?: string;
};

export function BarList({
  items,
  color = SERIES_PRIMARY,
  maxItems = 8,
  valueName,
}: {
  items: BarListItem[];
  color?: string;
  maxItems?: number;
  /** Screen-reader name for the measure, e.g. "obligated funding". */
  valueName: string;
}) {
  const shown = items.slice(0, maxItems);
  const max = Math.max(...shown.map((d) => d.value), 1);

  return (
    <ul className="flex flex-col gap-2.5">
      {shown.map((d) => {
        const widthPct = Math.max(1.5, (d.value / max) * 100);
        return (
          <li key={d.key} className="group">
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-[12px] text-text" title={d.label}>
                {d.label}
              </span>
              <span className="flex shrink-0 items-baseline gap-2">
                {d.secondaryLabel ? (
                  <span className="text-[10.5px] text-text-subtle opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                    {d.secondaryLabel}
                  </span>
                ) : null}
                <span className="font-mono text-[12px] font-semibold tabular-nums text-text-strong">
                  {d.valueLabel}
                </span>
              </span>
            </div>
            <div
              className="mt-1 h-2.5 w-full overflow-hidden rounded-[2px] bg-surface-2"
              role="img"
              aria-label={`${d.label}: ${d.valueLabel} ${valueName}`}
            >
              <div
                className={clsx("h-full rounded-r-[4px] transition-[width] duration-500 ease-out")}
                style={{ width: `${widthPct}%`, background: color }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default BarList;

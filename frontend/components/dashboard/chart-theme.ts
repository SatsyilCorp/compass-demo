/**
 * Chart theme — the small set of parameters every Compass chart draws from.
 *
 * Why literal hex and not `var(--color-…)`: these values are handed to Recharts
 * as SVG *presentation attributes* (`fill`, `stroke`), where `var()` support is
 * inconsistent across browsers. The literals below are the same values defined
 * in app/globals.css; the two chart series colors are the one exception and are
 * explained next.
 *
 * SERIES COLORS — validated, not eyeballed.
 * The brand Navy (#0a2540) is deliberately NOT used as a chart fill: at that
 * lightness/chroma it reads as near-black in a mark and fails both the
 * lightness-band and chroma-floor checks. The chart step of the same hue
 * family (#2a6496) plus the brass accent (#a8842f) were run through the
 * palette validator (light mode, #ffffff surface) and pass all six checks:
 *
 *   Lightness band  PASS (both inside L 0.43–0.77)
 *   Chroma floor    PASS (both >= 0.1)
 *   CVD separation  PASS (worst adjacent ΔE 21.9 protan / 21.5 tritan)
 *   Normal vision   PASS (ΔE 25.2)
 *   Contrast        PASS (both >= 3:1 vs surface)
 *
 * Rules the charts in this folder hold to:
 *   - One series → one color for every bar (never a value-ramp on nominal
 *     categories like program areas or org units).
 *   - Two series → both colors + a legend + a second encoding (bar vs. dashed
 *     line), never color alone.
 *   - Never a second y-axis.
 *   - Text (labels, values, axis ticks) wears text tokens, never the series
 *     color.
 */

/** Primary data hue — the chart step of the Navy family. */
export const SERIES_PRIMARY = "#2a6496";
/** Secondary data hue — the brass accent, used for baselines/targets. */
export const SERIES_ACCENT = "#a8842f";

/** Sequential ramp of the primary hue (light → dark), for meters/tracks. */
export const RAMP_PRIMARY = ["#dce7f1", "#a9c4dd", "#6f9cc4", "#4780ae", SERIES_PRIMARY, "#1e4a70"];

/** Chrome — one step off surface, hairline, solid, recessive. */
export const GRID_STROKE = "#e6e9ed";
export const AXIS_STROKE = "#c3cad2";
export const AXIS_TICK_FILL = "#6b7684";
export const SURFACE = "#ffffff";

/** Status ramp (reserved for state, never reused as a data series). */
export const STATUS = {
  ok: "#16794f",
  warn: "#9a6a12",
  serious: "#b5541f",
  critical: "#a3312a",
} as const;

/** Shared Recharts tooltip container style. */
export const TOOLTIP_STYLE: React.CSSProperties = {
  background: SURFACE,
  border: "1px solid #dfe3e8",
  borderRadius: 5,
  boxShadow: "0 6px 16px -4px rgba(10, 37, 64, 0.22)",
  fontSize: 12,
  padding: "8px 10px",
  color: "#1b2430",
};

export const AXIS_TICK: { fontSize: number; fill: string } = {
  fontSize: 11,
  fill: AXIS_TICK_FILL,
};

/** Bar geometry — thin marks, 4px rounded data-end, square at the baseline. */
export const BAR_SIZE = 16;
export const BAR_RADIUS_VERTICAL: [number, number, number, number] = [4, 4, 0, 0];

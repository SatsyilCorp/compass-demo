/**
 * Formatting helpers shared by the element 6/7 surfaces (dashboard, export,
 * licenses).
 *
 * `amount_usd` is `number | null` across the whole API contract. `null` is not
 * "zero" or "unknown", it is *column-level security*: the viewer persona has
 * `SELECT (amount_usd)` revoked (db/migrations/002_rls.sql), so the API returns
 * null. Everything that renders money goes through `usd()` / `MASKED_LABEL` so
 * a masked cell always reads as masked rather than silently as `$0`.
 */

export const MASKED_LABEL = "Masked";

const compactUsd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

const fullUsd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

/** Compact money for tiles/axes: $4.2M. Returns MASKED_LABEL for null (CLS). */
export function usd(n: number | null | undefined): string {
  if (n === null || n === undefined) return MASKED_LABEL;
  return compactUsd.format(n);
}

/** Exact money for tooltips/tables: $4,231,000. */
export function usdFull(n: number | null | undefined): string {
  if (n === null || n === undefined) return MASKED_LABEL;
  return fullUsd.format(n);
}

export function num(n: number | null | undefined): string {
  if (n === null || n === undefined) return "Not available";
  return n.toLocaleString("en-US");
}

export function pct(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * Parse an API date. `renews_on` is a Postgres DATE and arrives as a bare
 * `YYYY-MM-DD`, which `new Date()` reads as UTC midnight. A viewer west of
 * UTC sees the previous day ("2026-09-15" rendering as "Sep 14"). Date-only
 * strings are therefore built as local dates; full timestamps are left alone.
 */
export function parseApiDate(iso: string): Date {
  const m = DATE_ONLY.exec(iso);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return new Date(iso);
}

/** 2026-08-10 → "Aug 10, 2026" */
export function dateShort(iso: string): string {
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { day: "2-digit", month: "short", year: "numeric" });
}

/** 2026-08-10T14:03:22Z → "Aug 10, 2026, 14:03" */
export function dateTimeShort(iso: string): string {
  const d = parseApiDate(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${dateShort(iso)}, ${d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
}

/** Whole days from now until `iso` (negative = already past). */
export function daysUntil(iso: string, now: Date = new Date()): number {
  const then = parseApiDate(iso);
  if (Number.isNaN(then.getTime())) return Number.NaN;
  const ms = then.getTime() - now.getTime();
  return Math.ceil(ms / 86_400_000);
}

export function relativeDays(days: number): string {
  if (Number.isNaN(days)) return "Not available";
  if (days < 0) return `${Math.abs(days).toLocaleString("en-US")} days ago`;
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days > 3650) return "no fixed renewal";
  return `in ${days.toLocaleString("en-US")} days`;
}

/** True when every value in the series is masked. Used to switch a chart into
 *  its explicit "masked by CLS" state instead of plotting an empty axis. */
export function allMasked(values: (number | null)[]): boolean {
  return values.length > 0 && values.every((v) => v === null);
}

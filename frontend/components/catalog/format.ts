/**
 * Small formatting helpers shared by the catalog table + quality panel.
 * Kept local to components/catalog (not lib/) — this module's build owns
 * only frontend/app/catalog*, frontend/app/analytics, and
 * frontend/components/{catalog,analytics}.
 */

export function formatUsd(n: number | null): string {
  if (n === null) return "—"; // em dash — masked by CLS for this role
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);
}

export function formatInt(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

/** Turns `not_null_required_fields` into `Not null required fields`. */
export function humanizeRule(rule: string): string {
  const words = rule.split("_");
  return words.map((w, i) => (i === 0 ? w[0]!.toUpperCase() + w.slice(1) : w)).join(" ");
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Freshness label used by both the table cell and the quality panel. */
export function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1 day ago";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months > 1 ? "s" : ""} ago`;
  const years = Math.floor(months / 12);
  return `${years} year${years > 1 ? "s" : ""} ago`;
}

export type FreshnessTone = "success" | "warn" | "danger";

export function freshnessTone(iso: string): FreshnessTone {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 7) return "success";
  if (days <= 30) return "warn";
  return "danger";
}

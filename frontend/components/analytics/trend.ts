import type { Topic } from "@/lib/types";

/** An "emerging" topic: its most recent period grew over the one before it. */
export function isEmerging(topic: Topic): boolean {
  const t = topic.trend;
  if (t.length < 2) return false;
  return t[t.length - 1]!.value > t[t.length - 2]!.value;
}

/** Most-recent-period delta, used for the emerging-topic sort/badge. */
export function latestDelta(topic: Topic): number {
  const t = topic.trend;
  if (t.length < 2) return 0;
  return t[t.length - 1]!.value - t[t.length - 2]!.value;
}

export function formatUsd(n: number | null): string {
  if (n === null) return "—";
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

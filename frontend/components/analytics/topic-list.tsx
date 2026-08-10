import { TrendingUp } from "lucide-react";
import type { Topic } from "@/lib/types";
import { seriesColor } from "./colors";
import { formatInt, formatUsd, isEmerging } from "./trend";

/**
 * Topics (top terms) — one card per topic_model output topic, colored to
 * match its line in <TopicTrendChart> so the reader can connect the two
 * without relying on the legend alone.
 */
export function TopicList({ topics }: { topics: Topic[] }) {
  if (topics.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface-2/60 p-6 text-center text-xs text-text-muted">
        No grants are visible to this persona/org_unit to score.
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {topics.map((topic, i) => {
        const color = seriesColor(i);
        const emerging = isEmerging(topic);
        return (
          <div key={topic.topic_id} className="rounded-md border border-border bg-surface p-4 shadow-soft">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} aria-hidden />
                <p className="truncate text-[13px] font-semibold text-text-strong" title={topic.label}>
                  {topic.label}
                </p>
              </div>
              {emerging && (
                <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-success/40 bg-success-soft px-1.5 py-0.5 text-[10px] font-semibold text-success">
                  <TrendingUp className="size-3" aria-hidden />
                  Emerging
                </span>
              )}
            </div>

            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {topic.top_terms.map((term) => (
                <span
                  key={term}
                  className="rounded-full border border-border-2 bg-surface-2 px-2 py-0.5 text-[10.5px] font-medium text-text-muted"
                >
                  {term}
                </span>
              ))}
            </div>

            <dl className="mt-3 flex items-center justify-between border-t border-border-2 pt-2.5 text-[11px]">
              <div>
                <dt className="text-text-subtle">Grants</dt>
                <dd className="font-semibold tabular-nums text-text">{formatInt(topic.grant_count)}</dd>
              </div>
              <div className="text-right">
                <dt className="text-text-subtle">Funding</dt>
                <dd className="font-semibold tabular-nums text-text">{formatUsd(topic.total_funding_usd)}</dd>
              </div>
            </dl>
          </div>
        );
      })}
    </div>
  );
}

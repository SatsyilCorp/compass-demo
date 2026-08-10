"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import type { DashboardResponse } from "@/lib/types";

import { ChartCard } from "../chart-card";
import { BarList, type BarListItem } from "./bar-list";
import { pct } from "../format";

/**
 * Topic mix — `GET /dashboard` → `top_topics`.
 *
 * `/dashboard` carries each topic's share of the scored portfolio (`weight`),
 * not a time series; the per-topic year-over-year trend lines belong to the
 * topic-model run itself (`GET /analytics/{run_id}` → `topics[].trend`, element
 * 5). So this card shows concentration and links to the run rather than
 * drawing a trend the endpoint never returned.
 */
export function TopicConcentration({ data }: { data: DashboardResponse["top_topics"] }) {
  const items: BarListItem[] = data
    .slice()
    .sort((a, b) => b.weight - a.weight)
    .map((t) => ({
      key: String(t.topic_id),
      label: t.label,
      value: t.weight,
      valueLabel: pct(t.weight, 1),
      secondaryLabel: `topic_id ${t.topic_id}`,
    }));

  return (
    <ChartCard
      title="Topic concentration"
      hint="Share of scored grants carried by each topic in the latest topic-model run."
      provenance="GET /dashboard → top_topics (weights produced by the element 5 topic model). Per-topic trend lines live on the run detail."
      empty={items.length === 0}
      emptyText="No topics scored for the portfolio visible to you."
      action={
        <Link
          href="/analytics/"
          className="inline-flex shrink-0 items-center gap-1 rounded border border-border px-2 py-1 text-[11px] font-semibold text-link transition-colors hover:bg-surface-2"
        >
          Topic analytics
          <ArrowUpRight className="size-3" aria-hidden />
        </Link>
      }
    >
      <BarList items={items} valueName="share of scored grants" maxItems={6} />
    </ChartCard>
  );
}

export default TopicConcentration;

"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Topic } from "@/lib/types";
import { seriesColor } from "./colors";

const TOOLTIP_STYLE = {
  background: "var(--color-surface)",
  border: "1px solid var(--color-border-strong)",
  borderRadius: 6,
  fontSize: 12,
  padding: "8px 10px",
} as const;

/**
 * Emerging-topic trend chart — grant count per topic across fiscal years.
 * One line per topic, colored by the same fixed slot order as
 * <TopicList>'s dots so identity carries across both views (never re-cycled
 * per filter). A legend is always present for ≥2 series per the dataviz
 * skill; the individual topic cards carry the "Emerging" callout so the
 * chart itself stays uncluttered.
 */
export function TopicTrendChart({ topics }: { topics: Topic[] }) {
  if (topics.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-md border border-border bg-surface text-xs text-text-muted">
        No topics to trend for this persona/org_unit.
      </div>
    );
  }

  const periods = topics[0]!.trend.map((t) => t.period);
  const data = periods.map((period, i) => {
    const row: Record<string, string | number> = { period };
    for (const t of topics) row[t.label] = t.trend[i]?.value ?? 0;
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 20, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
        <XAxis dataKey="period" stroke="var(--color-text-subtle)" tick={{ fontSize: 11 }} tickLine={false} />
        <YAxis stroke="var(--color-text-subtle)" tick={{ fontSize: 11 }} allowDecimals={false} width={30} tickLine={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        {topics.length >= 2 && <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />}
        {topics.map((t, i) => (
          <Line
            key={t.topic_id}
            type="monotone"
            dataKey={t.label}
            stroke={seriesColor(i)}
            strokeWidth={2}
            dot={{ r: 4, fill: seriesColor(i), strokeWidth: 0 }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: "var(--color-surface)" }}
            isAnimationActive
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

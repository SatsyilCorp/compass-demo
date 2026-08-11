"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardResponse } from "@/lib/types";

import { ChartCard } from "../chart-card";
import { ChartValuesTable } from "./chart-values-table";
import {
  AXIS_STROKE,
  AXIS_TICK,
  GRID_STROKE,
  SERIES_PRIMARY,
  SURFACE,
  TOOLTIP_STYLE,
} from "../chart-theme";
import { dateShort } from "../format";

/**
 * Data-quality score across ingest runs: `GET /dashboard` to `quality_trend`.
 *
 * One series, so no legend box (the title names it) and no number on every
 * point: the latest score is called out above the plot and the rest live in
 * the axis and the hover tooltip.
 */
type Row = { run_id: string; date: string; score: number; label: string };

export function QualityTrend({ data }: { data: DashboardResponse["quality_trend"] }) {
  const rows: Row[] = data
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((d) => ({ ...d, label: dateShort(d.date) }));

  const latest = rows.at(-1);
  const first = rows[0];
  const delta = latest && first ? latest.score - first.score : 0;

  return (
    <ChartCard
      title="Data-quality score across ingest runs"
      hint="Composite pass rate of the quality gate for each curated batch, oldest to newest."
      provenance="GET /dashboard → quality_trend (one point per ingest run_id)."
      empty={rows.length === 0}
      emptyText="No completed ingest runs are visible in this scope."
      action={
        latest ? (
          <div className="shrink-0 text-right">
            <p className="font-mono text-[18px] font-semibold leading-none text-text-strong">
              {latest.score.toFixed(1)}
            </p>
            <p className="mt-0.5 text-[10.5px] text-text-subtle">
              latest{" "}
              {rows.length > 1 ? (
                <span className={delta >= 0 ? "text-success" : "text-danger"}>
                  {delta >= 0 ? "+" : ""}
                  {delta.toFixed(1)} since first run
                </span>
              ) : null}
            </p>
          </div>
        ) : null
      }
    >
      <ResponsiveContainer width="100%" height={190}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="label" stroke={AXIS_STROKE} tick={AXIS_TICK} tickLine={false} minTickGap={24} />
          <YAxis
            stroke={AXIS_STROKE}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={34}
            domain={[
              (min: number) => Math.max(0, Math.floor((min - 4) / 5) * 5),
              (max: number) => Math.min(100, Math.ceil((max + 2) / 5) * 5),
            ]}
          />
          <Tooltip contentStyle={TOOLTIP_STYLE} content={<QualityTooltip />} />
          <Line
            type="monotone"
            dataKey="score"
            name="Quality score"
            stroke={SERIES_PRIMARY}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            dot={{ r: 4, fill: SERIES_PRIMARY, stroke: SURFACE, strokeWidth: 2 }}
            activeDot={{ r: 5, fill: SERIES_PRIMARY, stroke: SURFACE, strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>

      <ChartValuesTable
        caption="Show values"
        columns={["Run", "Date", "Score"]}
        rows={rows.map((r) => [r.run_id, r.label, r.score.toFixed(1)])}
      />
    </ChartCard>
  );
}

function QualityTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]!.payload;
  return (
    <div style={TOOLTIP_STYLE}>
      <p className="font-semibold text-text-strong">{row.label}</p>
      <p className="mt-1 text-text">
        Quality score <span className="font-mono font-semibold">{row.score.toFixed(1)}</span>
      </p>
      <p className="font-mono text-[10.5px] text-text-subtle">{row.run_id}</p>
    </div>
  );
}

export default QualityTrend;

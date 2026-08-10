"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EyeOff } from "lucide-react";

import type { DashboardResponse } from "@/lib/types";

import { ChartCard } from "../chart-card";
import { ChartValuesTable } from "./chart-values-table";
import {
  AXIS_STROKE,
  AXIS_TICK,
  AXIS_TICK_FILL,
  BAR_RADIUS_VERTICAL,
  BAR_SIZE,
  GRID_STROKE,
  SERIES_ACCENT,
  SERIES_PRIMARY,
  TOOLTIP_STYLE,
} from "../chart-theme";
import { allMasked, usd, usdFull } from "../format";

/**
 * Budget vs. execution by fiscal year — `GET /dashboard` →
 * `funding_by_fiscal_year`.
 *
 * Honest framing, stated on the card: the bars are *execution* — money actually
 * obligated on awards in `grants_curated` for that fiscal year. Compass does
 * not ingest an appropriation/PB feed, so there is no authoritative budget
 * authority line to plot against it. Rather than invent one, the comparison
 * baseline is computed and labelled as computed: the even-spend line (mean
 * execution across the visible fiscal years). Years above it drew more than
 * their even share of the portfolio; years below drew less.
 *
 * One y-axis, two marks with different geometry (solid bars vs. a dashed
 * line) plus a legend — identity never rests on color alone.
 */
type Row = {
  fiscal_year: number;
  label: string;
  executed: number;
  baseline: number;
  variance: number;
};

export function BudgetExecutionChart({
  data,
}: {
  data: DashboardResponse["funding_by_fiscal_year"];
}) {
  const masked = allMasked(data.map((d) => d.amount_usd));

  if (masked) {
    return (
      <ChartCard
        title="Budget vs. execution by fiscal year"
        hint="Execution is measured in dollars, and dollars are withheld from your role."
        provenance="GET /dashboard → funding_by_fiscal_year (all values null under column-level security)."
      >
        <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 rounded border border-dashed border-border px-6 text-center">
          <EyeOff className="size-5 text-text-subtle" aria-hidden />
          <p className="text-[13px] font-semibold text-text-strong">Masked by column-level security</p>
          <p className="max-w-sm text-[12px] leading-relaxed text-text-muted">
            The viewer role has <code className="font-mono text-[11px]">SELECT (amount_usd)</code>{" "}
            revoked on <code className="font-mono text-[11px]">compass.grants_curated</code>, so the
            API returns null for every fiscal-year total. Switch to the power-user persona to see the
            execution curve.
          </p>
        </div>
      </ChartCard>
    );
  }

  const present = data.filter((d): d is { fiscal_year: number; amount_usd: number } =>
    typeof d.amount_usd === "number",
  );
  const baseline =
    present.length > 0 ? present.reduce((a, d) => a + d.amount_usd, 0) / present.length : 0;

  const rows: Row[] = present
    .slice()
    .sort((a, b) => a.fiscal_year - b.fiscal_year)
    .map((d) => ({
      fiscal_year: d.fiscal_year,
      label: `FY${String(d.fiscal_year).slice(-2)}`,
      executed: d.amount_usd,
      baseline,
      variance: baseline > 0 ? d.amount_usd / baseline - 1 : 0,
    }));

  return (
    <ChartCard
      title="Budget vs. execution by fiscal year"
      hint="Bars are executed obligations. The dashed line is the even-spend baseline — the mean across the fiscal years visible to you."
      provenance="GET /dashboard → funding_by_fiscal_year. The baseline is computed in the browser from those same values; Compass ingests no appropriation feed, so no budget-authority line is claimed."
      empty={rows.length === 0}
      emptyText="No fiscal years are visible under your current row-level security scope."
    >
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="label" stroke={AXIS_STROKE} tick={AXIS_TICK} tickLine={false} />
          <YAxis
            stroke={AXIS_STROKE}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={58}
            tickFormatter={(v: number) => usd(v)}
          />
          <Tooltip
            cursor={{ fill: "rgba(42, 100, 150, 0.06)" }}
            contentStyle={TOOLTIP_STYLE}
            content={<ExecutionTooltip />}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 6 }}
            iconType="plainline"
            iconSize={14}
            // Recharts tints legend text with the series color by default; the
            // colored key beside the label carries identity, the text stays in
            // a text token so it is legible at any hue.
            formatter={(value: string) => (
              <span style={{ color: AXIS_TICK_FILL }}>{value}</span>
            )}
          />
          <Bar
            dataKey="executed"
            name="Executed obligations"
            fill={SERIES_PRIMARY}
            barSize={BAR_SIZE}
            radius={BAR_RADIUS_VERTICAL}
            isAnimationActive
          />
          <Line
            dataKey="baseline"
            name="Even-spend baseline (computed)"
            stroke={SERIES_ACCENT}
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            activeDot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <ChartValuesTable
        caption="Show values"
        columns={["Fiscal year", "Executed", "Baseline", "Variance"]}
        rows={rows.map((r) => [
          `FY${r.fiscal_year}`,
          usdFull(r.executed),
          usdFull(r.baseline),
          `${r.variance >= 0 ? "+" : ""}${(r.variance * 100).toFixed(1)}%`,
        ])}
      />
    </ChartCard>
  );
}

type TooltipPayload = { payload: Row };

function ExecutionTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]!.payload;
  const above = row.variance >= 0;
  return (
    <div style={TOOLTIP_STYLE}>
      <p className="font-semibold text-text-strong">FY{row.fiscal_year}</p>
      <p className="mt-1 text-text">
        Executed <span className="font-mono font-semibold">{usdFull(row.executed)}</span>
      </p>
      <p className="text-text-muted">
        Baseline <span className="font-mono">{usdFull(row.baseline)}</span>
      </p>
      <p className={above ? "mt-1 text-success" : "mt-1 text-warn"}>
        {above ? "+" : ""}
        {(row.variance * 100).toFixed(1)}% vs. even spend
      </p>
    </div>
  );
}

export default BudgetExecutionChart;

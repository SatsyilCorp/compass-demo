"use client";

import {
  Bar,
  CartesianGrid,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ShieldCheck } from "lucide-react";

import type { DashboardResponse } from "@/lib/types";

import { ChartCard } from "../chart-card";
import { ChartValuesTable } from "./chart-values-table";
import {
  AXIS_STROKE,
  AXIS_TICK,
  BAR_RADIUS_VERTICAL,
  BAR_SIZE,
  GRID_STROKE,
  SERIES_PRIMARY,
  TOOLTIP_STYLE,
} from "../chart-theme";
import { num, usdFull } from "../format";

/**
 * Awards by org unit — `GET /dashboard` → `org_unit_breakdown`.
 *
 * Counts, not dollars: the count is the measure both personas can see, so the
 * chart keeps its shape when column-level security masks money (the exact
 * dollar figure rides in the tooltip and reads "Masked" when withheld).
 *
 * When row-level security scopes the caller to a single org unit there is
 * nothing to compare, so the card degrades to a stat tile — a one-bar bar
 * chart is never the right form — and names the reason.
 */
type Row = { org_unit: string; grant_count: number; amount_usd: number | null };

export function OrgUnitAwards({ data }: { data: DashboardResponse["org_unit_breakdown"] }) {
  const rows: Row[] = data.slice().sort((a, b) => b.grant_count - a.grant_count);

  if (rows.length === 1) {
    const only = rows[0]!;
    return (
      <ChartCard
        title="Awards by org unit"
        hint="Your row-level security scope covers a single org unit."
        provenance="GET /dashboard → org_unit_breakdown. Scoped by the RLS policy on compass.grants_curated."
      >
        <div className="flex h-full min-h-[220px] flex-col justify-center gap-3">
          <div>
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
              {only.org_unit}
            </p>
            <p className="mt-1 text-[34px] font-semibold leading-none tracking-tight text-text-strong">
              {num(only.grant_count)}
            </p>
            <p className="mt-1 text-[12px] text-text-muted">
              awards visible ·{" "}
              {only.amount_usd === null
                ? "obligated total masked by column-level security"
                : `${usdFull(only.amount_usd)} obligated`}
            </p>
          </div>
          <p className="flex items-start gap-2 rounded border border-border bg-surface-2 px-3 py-2 text-[11.5px] leading-snug text-text-muted">
            <ShieldCheck className="mt-[1px] size-3.5 shrink-0 text-gov-primary" aria-hidden />
            <span>
              The RLS policy <code className="font-mono text-[11px]">grants_rls_read</code> returns
              only rows whose <code className="font-mono text-[11px]">org_unit</code> matches your
              session claim, so no other unit is comparable from this session. The corporate persona
              sees all units.
            </span>
          </p>
        </div>
      </ChartCard>
    );
  }

  return (
    <ChartCard
      title="Awards by org unit"
      hint="Count of curated awards per ONR code. Hover a column for the obligated total."
      provenance="GET /dashboard → org_unit_breakdown. Row visibility is enforced by the RLS policy, not by this page."
      empty={rows.length === 0}
      emptyText="No org units are visible under your current row-level security scope."
    >
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="org_unit" stroke={AXIS_STROKE} tick={AXIS_TICK} tickLine={false} />
          <YAxis
            stroke={AXIS_STROKE}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={34}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(42, 100, 150, 0.06)" }}
            contentStyle={TOOLTIP_STYLE}
            content={<OrgTooltip />}
          />
          <Bar
            dataKey="grant_count"
            name="Awards"
            fill={SERIES_PRIMARY}
            barSize={BAR_SIZE}
            radius={BAR_RADIUS_VERTICAL}
          />
        </BarChart>
      </ResponsiveContainer>

      <ChartValuesTable
        caption="Show values"
        columns={["Org unit", "Awards", "Obligated"]}
        rows={rows.map((r) => [r.org_unit, num(r.grant_count), usdFull(r.amount_usd)])}
      />
    </ChartCard>
  );
}

function OrgTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]!.payload;
  return (
    <div style={TOOLTIP_STYLE}>
      <p className="font-semibold text-text-strong">{row.org_unit}</p>
      <p className="mt-1 text-text">
        <span className="font-mono font-semibold">{num(row.grant_count)}</span> awards
      </p>
      <p className="text-text-muted">
        <span className="font-mono">{usdFull(row.amount_usd)}</span> obligated
      </p>
    </div>
  );
}

export default OrgUnitAwards;

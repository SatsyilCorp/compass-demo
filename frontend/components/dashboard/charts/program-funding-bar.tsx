"use client";

import type { DashboardResponse } from "@/lib/types";

import { ChartCard } from "../chart-card";
import { BarList, type BarListItem } from "./bar-list";
import { allMasked, num, usd, usdFull } from "../format";

/**
 * Portfolio by program area — `GET /dashboard` → `funding_by_program_area`.
 *
 * When the caller's role has `amount_usd` revoked (viewer/CLS) every amount
 * comes back null. The chart then plots grant counts and says so, rather than
 * plotting a row of zeros.
 */
export function ProgramFundingBar({
  data,
}: {
  data: DashboardResponse["funding_by_program_area"];
}) {
  const masked = allMasked(data.map((d) => d.amount_usd));

  const items: BarListItem[] = data
    .map((d) => ({
      key: d.program_area,
      label: d.program_area,
      value: masked ? d.grant_count : (d.amount_usd ?? 0),
      valueLabel: masked ? num(d.grant_count) : usd(d.amount_usd),
      secondaryLabel: masked
        ? undefined
        : `${num(d.grant_count)} grants · ${usdFull(d.amount_usd)}`,
    }))
    .sort((a, b) => b.value - a.value);

  return (
    <ChartCard
      title={masked ? "Portfolio by program area — grant count" : "Portfolio by program area"}
      hint={
        masked
          ? "Award amounts are withheld from your role by column-level security, so this ranks program areas by grant count."
          : "Obligated award value per program area across the portfolio visible to you. Hover a row for the grant count and exact figure."
      }
      provenance="GET /dashboard → funding_by_program_area. Ranked in the browser; the values are the API's."
      empty={items.length === 0}
      emptyText="No program areas are visible under your current row-level security scope."
    >
      <BarList items={items} valueName={masked ? "grants" : "obligated funding"} />
    </ChartCard>
  );
}

export default ProgramFundingBar;

"use client";

import { useState } from "react";
import { EyeOff, FlaskConical, Lightbulb, SlidersHorizontal } from "lucide-react";

import type { DashboardResponse } from "@/lib/types";

import { ChartCard } from "../chart-card";
import { allMasked, usd, usdFull } from "../format";


type ScenarioMetricProps = {
  label: string;
  value: number;
  maximum: number;
  color: string;
  note: string;
};

export function BudgetExecutionChart({
  data,
}: {
  data: DashboardResponse["funding_by_fiscal_year"];
}) {
  const [planUplift, setPlanUplift] = useState(12);
  const [gapCapture, setGapCapture] = useState(65);
  const masked = allMasked(data.map((row) => row.amount_usd));

  if (masked) {
    return (
      <ChartCard
        title="Funding planning sandbox"
        hint="A planning scenario needs an actual obligations starting point, which your role cannot read."
        provenance="Live funding values remain protected for this role. No synthetic plan is calculated from hidden values."
        action={<ScenarioBadge />}
      >
        <div className="flex min-h-[260px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 text-center">
          <EyeOff className="size-6 text-text-subtle" aria-hidden />
          <p className="text-base font-semibold text-text-strong">Funding values are protected</p>
          <p className="max-w-sm text-sm leading-6 text-text-muted">
            The portfolio remains visible by grant count, but this role cannot use award values in a planning calculation.
          </p>
        </div>
      </ChartCard>
    );
  }

  const latest = data
    .filter((row): row is { fiscal_year: number; amount_usd: number } => row.amount_usd !== null)
    .slice()
    .sort((a, b) => a.fiscal_year - b.fiscal_year)
    .at(-1);

  if (!latest) {
    return (
      <ChartCard
        title="Funding planning sandbox"
        hint="No actual obligations are visible in the current result."
        provenance="No planning values are calculated without a live actual starting point."
        action={<ScenarioBadge />}
        empty
        emptyText="Adjust the portfolio filters to include a fiscal year with obligations."
      >
        <span />
      </ChartCard>
    );
  }

  const actual = latest.amount_usd;
  const plan = actual * (1 + planUplift / 100);
  const forecast = actual + (plan - actual) * (gapCapture / 100);
  const variance = forecast - plan;
  const varianceRate = plan > 0 ? variance / plan : 0;
  const maximum = Math.max(plan, actual, forecast, 1);

  return (
    <ChartCard
      title="Funding planning sandbox"
      hint="Live actual obligations anchor an adjustable, clearly synthetic planning scenario."
      provenance={`Actual obligations come from GET /dashboard for FY${latest.fiscal_year}. Plan, forecast, variance, and recommendation are browser-computed synthetic assumptions.`}
      action={<ScenarioBadge />}
    >
      <div className="rounded-lg border border-border bg-surface-2 p-4">
        <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-text-subtle">
          Live actuals
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-text-strong">FY{latest.fiscal_year} obligated awards</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-text-strong">
              {usd(actual)}
            </p>
          </div>
          <p className="max-w-xs text-right text-xs leading-5 text-text-muted">
            This is the only authoritative finance value used below.
          </p>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-gold/30 bg-gold-soft/45 p-4">
        <div className="flex items-start gap-2">
          <SlidersHorizontal className="mt-0.5 size-4 shrink-0 text-gold-ink" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-text-strong">Synthetic planning assumptions</p>
            <p className="mt-0.5 text-xs leading-5 text-text-muted">
              Adjust the scenario live. These controls do not write to the portfolio or represent budget authority.
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <ScenarioControl
            label="Plan above current obligations"
            value={planUplift}
            min={2}
            max={30}
            suffix="%"
            onChange={setPlanUplift}
          />
          <ScenarioControl
            label="Expected capture of remaining gap"
            value={gapCapture}
            min={0}
            max={100}
            suffix="%"
            onChange={setGapCapture}
          />
        </div>
      </div>

      <div className="mt-4 space-y-3" aria-label="Synthetic plan, actual, and forecast comparison">
        <ScenarioMetric
          label="Synthetic plan"
          value={plan}
          maximum={maximum}
          color="bg-gold"
          note={`${planUplift}% above current obligations`}
        />
        <ScenarioMetric
          label="Live actual obligations"
          value={actual}
          maximum={maximum}
          color="bg-gov-primary"
          note={`FY${latest.fiscal_year} governed actual`}
        />
        <ScenarioMetric
          label="Synthetic forecast"
          value={forecast}
          maximum={maximum}
          color="bg-info"
          note={`${gapCapture}% of the synthetic remaining gap captured`}
        />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-[160px_1fr]">
        <div className="rounded-lg border border-border bg-surface-2 p-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-text-subtle">
            Forecast variance
          </p>
          <p className={`mt-1 font-mono text-lg font-semibold ${variance < 0 ? "text-warn" : "text-success"}`}>
            {variance >= 0 ? "+" : ""}{usdFull(variance)}
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
            {varianceRate >= 0 ? "+" : ""}{(varianceRate * 100).toFixed(1)}% vs synthetic plan
          </p>
        </div>
        <div className="rounded-lg border border-info/25 bg-info-soft p-3">
          <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.12em] text-info">
            <Lightbulb className="size-3.5" aria-hidden />
            Scenario recommendation
          </p>
          <p className="mt-1.5 text-sm leading-6 text-text">
            {variance < 0
              ? `Validate whether the projected ${usdFull(Math.abs(variance))} gap should be accelerated, rephased, or released before treating this scenario as a plan.`
              : "The synthetic forecast meets the synthetic plan. Validate source assumptions before using it in a funding decision."}
          </p>
        </div>
      </div>
    </ChartCard>
  );
}

function ScenarioBadge() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-gold/30 bg-gold-soft px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.1em] text-gold-ink">
      <FlaskConical className="size-3.5" aria-hidden />
      Synthetic scenario
    </span>
  );
}

function ScenarioControl({
  label,
  value,
  min,
  max,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  suffix: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-xs font-semibold text-text-strong">
      <span className="flex items-center justify-between gap-3">
        <span>{label}</span>
        <output className="font-mono text-sm font-semibold text-gov-primary">
          {value}{suffix}
        </output>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 min-h-11 w-full cursor-pointer accent-gov-primary"
      />
    </label>
  );
}

function ScenarioMetric({ label, value, maximum, color, note }: ScenarioMetricProps) {
  const width = `${Math.max(2, (value / maximum) * 100)}%`;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text-strong">{label}</p>
          <p className="text-xs text-text-muted">{note}</p>
        </div>
        <p className="shrink-0 font-mono text-sm font-semibold text-text-strong">{usdFull(value)}</p>
      </div>
      <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full rounded-full ${color} motion-safe:transition-[width] motion-safe:duration-300`}
          style={{ width }}
        />
      </div>
    </div>
  );
}

export default BudgetExecutionChart;

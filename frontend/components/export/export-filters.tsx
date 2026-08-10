"use client";

import clsx from "clsx";
import { Lock } from "lucide-react";

import type { DashboardResponse, ExportRequest } from "@/lib/types";

/**
 * Filter controls for `POST /export` (element 7).
 *
 * Option lists are not hard-coded: they are read from `GET /dashboard`, so the
 * only program areas, fiscal years, and org units a user can pick are the ones
 * their row-level security scope actually contains. A viewer scoped to a single
 * org unit therefore sees a locked control rather than a dropdown of units they
 * cannot query — the restriction is visible instead of failing at submit time.
 */
export type ExportFilterState = {
  format: ExportRequest["format"];
  program_area: string;
  fiscal_year: string;
  org_unit: string;
  include_abstract: boolean;
  include_amount: boolean;
};

export const DEFAULT_FILTERS: ExportFilterState = {
  format: "csv",
  program_area: "",
  fiscal_year: "",
  org_unit: "",
  include_abstract: false,
  include_amount: true,
};

const FORMATS: { value: ExportRequest["format"]; label: string; note: string }[] = [
  { value: "csv", label: "CSV", note: "flat, opens anywhere" },
  { value: "json", label: "JSON", note: "nested, API-shaped" },
  { value: "parquet", label: "Parquet", note: "columnar, analytics" },
];

/** Columns the export will contain, given the toggles + CLS state. */
export function selectedColumns(f: ExportFilterState, amountMasked: boolean): string[] {
  const cols = ["grant_no", "title", "program_area", "fiscal_year", "awardee", "org_unit"];
  if (f.include_abstract) cols.push("abstract");
  if (f.include_amount && !amountMasked) cols.push("amount_usd");
  return cols;
}

/** The `filters` object sent on the wire — mirrors grants_curated columns. */
export function toRequestFilters(f: ExportFilterState, amountMasked: boolean): Record<string, unknown> {
  const filters: Record<string, unknown> = { columns: selectedColumns(f, amountMasked) };
  if (f.program_area) filters.program_area = f.program_area;
  if (f.fiscal_year) filters.fiscal_year = Number(f.fiscal_year);
  if (f.org_unit) filters.org_unit = f.org_unit;
  return filters;
}

export function ExportFilters({
  value,
  onChange,
  dashboard,
  amountMasked,
  disabled,
}: {
  value: ExportFilterState;
  onChange: (next: ExportFilterState) => void;
  dashboard: DashboardResponse | null;
  amountMasked: boolean;
  disabled?: boolean;
}) {
  const set = <K extends keyof ExportFilterState>(key: K, v: ExportFilterState[K]) =>
    onChange({ ...value, [key]: v });

  const programAreas = dashboard?.funding_by_program_area.map((p) => p.program_area) ?? [];
  const fiscalYears =
    dashboard?.funding_by_fiscal_year
      .map((y) => y.fiscal_year)
      .slice()
      .sort((a, b) => b - a) ?? [];
  const orgUnits = dashboard?.org_unit_breakdown.map((o) => o.org_unit) ?? [];
  const orgLocked = orgUnits.length <= 1;

  return (
    <div className="flex flex-col gap-5">
      {/* ---- Format ---------------------------------------------------- */}
      <fieldset disabled={disabled}>
        <legend className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
          Format
        </legend>
        <div className="mt-2 grid grid-cols-3 gap-2">
          {FORMATS.map((f) => (
            <label
              key={f.value}
              className={clsx(
                "cursor-pointer rounded border px-3 py-2 transition-colors",
                value.format === f.value
                  ? "border-gov-primary bg-gov-primary-lighter"
                  : "border-border bg-surface hover:bg-surface-2",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <input
                type="radio"
                name="export-format"
                className="sr-only"
                checked={value.format === f.value}
                onChange={() => set("format", f.value)}
              />
              <span className="block text-[12.5px] font-semibold text-text-strong">{f.label}</span>
              <span className="block text-[10.5px] text-text-subtle">{f.note}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* ---- Row filters ------------------------------------------------ */}
      <div className="grid gap-3 sm:grid-cols-3">
        <Select
          id="filter-program-area"
          label="Program area"
          value={value.program_area}
          onChange={(v) => set("program_area", v)}
          disabled={disabled}
          options={[{ value: "", label: "All visible" }, ...programAreas.map((p) => ({ value: p, label: p }))]}
        />
        <Select
          id="filter-fiscal-year"
          label="Fiscal year"
          value={value.fiscal_year}
          onChange={(v) => set("fiscal_year", v)}
          disabled={disabled}
          options={[
            { value: "", label: "All visible" },
            ...fiscalYears.map((y) => ({ value: String(y), label: `FY${y}` })),
          ]}
        />
        {orgLocked ? (
          <div>
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
              Org unit
            </p>
            <p className="mt-2 flex items-center gap-1.5 rounded border border-border bg-surface-2 px-2.5 py-2 text-[12px] text-text-muted">
              <Lock className="size-3.5 shrink-0" aria-hidden />
              <span className="truncate" title="Fixed by the row-level security policy">
                {orgUnits[0] ?? "—"} · RLS-fixed
              </span>
            </p>
          </div>
        ) : (
          <Select
            id="filter-org-unit"
            label="Org unit"
            value={value.org_unit}
            onChange={(v) => set("org_unit", v)}
            disabled={disabled}
            options={[{ value: "", label: "All visible" }, ...orgUnits.map((o) => ({ value: o, label: o }))]}
          />
        )}
      </div>

      {/* ---- Column selection ------------------------------------------- */}
      <fieldset disabled={disabled}>
        <legend className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
          Columns
        </legend>
        <div className="mt-2 flex flex-wrap items-center gap-4">
          <Toggle
            id="col-abstract"
            label="Include abstract"
            checked={value.include_abstract}
            onChange={(v) => set("include_abstract", v)}
          />
          <Toggle
            id="col-amount"
            label="Include amount_usd"
            checked={value.include_amount && !amountMasked}
            onChange={(v) => set("include_amount", v)}
            disabled={amountMasked}
            hint={
              amountMasked
                ? "Unavailable — column-level security revokes SELECT (amount_usd) for your role, so the API will not emit it."
                : undefined
            }
          />
        </div>
      </fieldset>
    </div>
  );
}

function Select({
  id,
  label,
  value,
  onChange,
  options,
  disabled,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle"
      >
        {label}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full rounded border border-border bg-surface px-2.5 py-2 text-[12.5px] text-text focus:border-gov-primary focus:outline-none disabled:opacity-60"
      >
        {options.map((o) => (
          <option key={o.value || "__all"} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function Toggle({
  id,
  label,
  checked,
  onChange,
  disabled,
  hint,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <div className="min-w-0">
      <label
        htmlFor={id}
        className={clsx(
          "flex items-center gap-2 text-[12.5px] text-text",
          disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
        )}
      >
        <input
          id={id}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
          className="size-4 accent-[color:var(--color-gov-primary)]"
        />
        {label}
      </label>
      {hint ? (
        <p className="mt-1 flex items-start gap-1 text-[10.5px] leading-snug text-text-subtle">
          <Lock className="mt-[1px] size-3 shrink-0" aria-hidden />
          <span>{hint}</span>
        </p>
      ) : null}
    </div>
  );
}

export default ExportFilters;

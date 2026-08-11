"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import {
  ArrowUpRight,
  LockKeyhole,
  RotateCcw,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";

import type {
  DashboardFilterOptions,
  DashboardFilters,
  Role,
} from "@/lib/types";


type Props = {
  value: DashboardFilters;
  options: DashboardFilterOptions;
  role: Role;
  orgUnit: string | null;
  resultCount: number;
  activeProgramAreas: number;
  loading: boolean;
  onChange: (filters: DashboardFilters) => void;
};

const EMPTY_OPTIONS: DashboardFilterOptions = {
  program_areas: [],
  fiscal_years: [],
  org_units: [],
};

function clean(filters: DashboardFilters): DashboardFilters {
  return {
    ...(filters.q?.trim() ? { q: filters.q.trim() } : {}),
    ...(filters.program_area ? { program_area: filters.program_area } : {}),
    ...(filters.fiscal_year !== undefined ? { fiscal_year: filters.fiscal_year } : {}),
    ...(filters.org_unit ? { org_unit: filters.org_unit } : {}),
  };
}

export function DashboardFiltersBar({
  value,
  options = EMPTY_OPTIONS,
  role,
  orgUnit,
  resultCount,
  activeProgramAreas,
  loading,
  onChange,
}: Props) {
  const searchId = useId();
  const programId = useId();
  const yearId = useId();
  const orgId = useId();
  const [draft, setDraft] = useState<DashboardFilters>(value);

  useEffect(() => setDraft(value), [value]);

  const active = [
    value.q ? { key: "q", label: `Search: ${value.q}` } : null,
    value.program_area
      ? { key: "program_area", label: `Program: ${value.program_area}` }
      : null,
    value.fiscal_year
      ? { key: "fiscal_year", label: `Fiscal year: ${value.fiscal_year}` }
      : null,
    value.org_unit ? { key: "org_unit", label: `Organization: ${value.org_unit}` } : null,
  ].filter((item): item is { key: keyof DashboardFilters; label: string } => item !== null);

  function removeFilter(key: keyof DashboardFilters) {
    const next = { ...value };
    delete next[key];
    onChange(next);
  }

  return (
    <section
      aria-label="Portfolio filters"
      className="rounded-lg border border-border bg-surface shadow-soft"
    >
      <form
        className="grid gap-3 p-4 xl:grid-cols-[minmax(240px,1.5fr)_minmax(170px,1fr)_150px_minmax(170px,1fr)_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          onChange(clean(draft));
        }}
      >
        <div>
          <label
            htmlFor={searchId}
            className="mb-1.5 block text-xs font-semibold text-text-strong"
          >
            Search portfolio
          </label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-subtle"
              aria-hidden
            />
            <input
              id={searchId}
              type="search"
              value={draft.q ?? ""}
              maxLength={160}
              onChange={(event) => setDraft((current) => ({ ...current, q: event.target.value }))}
              placeholder="Award, title, abstract, or recipient"
              className="min-h-11 w-full rounded-md border border-border bg-surface pl-10 pr-3 text-sm text-text-strong outline-none transition-colors placeholder:text-text-subtle focus:border-gov-primary focus:ring-2 focus:ring-gov-primary/20"
            />
          </div>
        </div>

        <FilterSelect
          id={programId}
          label="Program area"
          value={draft.program_area ?? ""}
          onChange={(next) =>
            setDraft((current) => ({ ...current, program_area: next || undefined }))
          }
          options={options.program_areas.map((item) => ({ value: item, label: item }))}
          emptyLabel="All programs"
        />

        <FilterSelect
          id={yearId}
          label="Fiscal year"
          value={draft.fiscal_year === undefined ? "" : String(draft.fiscal_year)}
          onChange={(next) =>
            setDraft((current) => ({
              ...current,
              fiscal_year: next ? Number(next) : undefined,
            }))
          }
          options={options.fiscal_years.map((item) => ({ value: String(item), label: String(item) }))}
          emptyLabel="All years"
        />

        {role === "poweruser" ? (
          <FilterSelect
            id={orgId}
            label="Organization"
            value={draft.org_unit ?? ""}
            onChange={(next) =>
              setDraft((current) => ({ ...current, org_unit: next || undefined }))
            }
            options={options.org_units.map((item) => ({ value: item, label: item }))}
            emptyLabel="All organizations"
          />
        ) : (
          <div>
            <label htmlFor={orgId} className="mb-1.5 block text-xs font-semibold text-text-strong">
              Organization
            </label>
            <div className="relative">
              <LockKeyhole
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-subtle"
                aria-hidden
              />
              <input
                id={orgId}
                value={orgUnit ?? "Not assigned"}
                disabled
                aria-describedby={`${orgId}-hint`}
                className="min-h-11 w-full rounded-md border border-border bg-surface-2 pl-10 pr-3 text-sm font-medium text-text-muted"
              />
            </div>
            <span id={`${orgId}-hint`} className="sr-only">
              Your row-level access policy locks this organization scope.
            </span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-[22px] inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-gov-primary px-4 text-sm font-semibold text-white transition-colors hover:bg-action-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gov-primary disabled:cursor-wait disabled:opacity-60"
        >
          <SlidersHorizontal className="size-4" aria-hidden />
          {loading ? "Applying" : "Apply view"}
        </button>
      </form>

      <div className="flex flex-col gap-3 border-t border-border-2 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text-strong" aria-live="polite">
            {resultCount.toLocaleString("en-US")} grants across {activeProgramAreas.toLocaleString("en-US")} program areas
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
            Results reflect your access scope and every active portfolio filter.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {active.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => removeFilter(item.key)}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-gov-primary/30 bg-info-soft px-3 text-xs font-semibold text-gov-primary transition-colors hover:border-gov-primary hover:bg-surface-2"
              aria-label={`Remove ${item.label}`}
            >
              {item.label}
              <X className="size-3.5" aria-hidden />
            </button>
          ))}
          {active.length > 0 ? (
            <button
              type="button"
              onClick={() => onChange({})}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-md px-3 text-xs font-semibold text-text-muted transition-colors hover:bg-surface-2 hover:text-text-strong"
            >
              <RotateCcw className="size-3.5" aria-hidden />
              Clear all
            </button>
          ) : null}
          <Link
            href="/catalog/"
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border px-3 text-xs font-semibold text-link transition-colors hover:bg-surface-2"
          >
            Open governed catalog
            <ArrowUpRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      </div>
    </section>
  );
}

function FilterSelect({
  id,
  label,
  value,
  onChange,
  options,
  emptyLabel,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  emptyLabel: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs font-semibold text-text-strong">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-text-strong outline-none transition-colors focus:border-gov-primary focus:ring-2 focus:ring-gov-primary/20"
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export default DashboardFiltersBar;

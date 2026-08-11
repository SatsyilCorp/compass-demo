"use client";

import { Fragment, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, ChevronsUpDown, Lock, Search, ArrowUpRight } from "lucide-react";
import type { CatalogEntry } from "@/lib/types";
import { ScoreChip } from "./score-chip";
import { QualityPanel } from "./quality-panel";
import { formatInt, formatUsd, timeAgo } from "./format";

/**
 * Dataset catalog table: the crm-datatable pattern (declarative columns,
 * clickable sortable headers, a toolbar search) from
 * satsyil-blocks/code/web/crm_datatable, hand-adapted to plain React state
 * instead of that block's zustand-backed view-prefs store (this build adds
 * no new runtime dependency). Every row expands into <QualityPanel>.
 */

type SortDir = "asc" | "desc";
type SortState = { key: string; dir: SortDir } | null;

type Column = {
  id: string;
  header: string;
  align?: "left" | "right";
  sortValue?: (r: CatalogEntry) => string | number | null;
  render: (r: CatalogEntry) => React.ReactNode;
  /** Hide on narrow viewports to keep the table legible without a column picker. */
  hideBelow?: "sm" | "md" | "lg";
};

const CLASSIFICATION_TONE: Record<string, string> = {
  "CUI-Mock": "border-warn/40 bg-warn-soft text-warn",
  "Public-Mock": "border-success/40 bg-success-soft text-success",
};

const COLUMNS: Column[] = [
  {
    id: "dataset_name",
    header: "Dataset",
    sortValue: (r) => r.dataset_name,
    render: (r) => (
      <div className="min-w-0">
        <p className="truncate text-[13px] font-semibold text-text-strong">{r.dataset_name}</p>
        <p className="truncate font-mono text-[11px] text-text-subtle" title={r.source_file}>
          {r.source_file}
        </p>
      </div>
    ),
  },
  {
    id: "program_area",
    header: "Program area",
    sortValue: (r) => r.program_area,
    render: (r) => <span className="text-text">{r.program_area}</span>,
    hideBelow: "md",
  },
  {
    id: "org_unit",
    header: "Org unit",
    sortValue: (r) => r.org_unit,
    render: (r) => <span className="font-mono text-[11.5px] text-text-muted">{r.org_unit}</span>,
    hideBelow: "lg",
  },
  {
    id: "fiscal_year",
    header: "FY",
    align: "right",
    sortValue: (r) => r.fiscal_year,
    render: (r) => <span className="tabular-nums text-text">{r.fiscal_year}</span>,
    hideBelow: "sm",
  },
  {
    id: "row_count",
    header: "Rows",
    align: "right",
    sortValue: (r) => r.row_count,
    render: (r) => <span className="tabular-nums text-text">{formatInt(r.row_count)}</span>,
  },
  {
    id: "amount_usd",
    header: "Funding",
    align: "right",
    sortValue: (r) => r.amount_usd,
    render: (r) =>
      r.amount_usd === null ? (
        <span
          className="inline-flex items-center gap-1 text-text-subtle"
          title="Column-level security masks amount_usd for this role"
        >
          <Lock className="size-3" aria-hidden />
          masked
        </span>
      ) : (
        <span className="tabular-nums text-text">{formatUsd(r.amount_usd)}</span>
      ),
  },
  {
    id: "quality_score",
    header: "Quality",
    align: "right",
    sortValue: (r) => r.quality_score,
    render: (r) => <ScoreChip score={r.quality_score} />,
  },
  {
    id: "classification_band",
    header: "Classification",
    sortValue: (r) => r.classification_band,
    render: (r) => (
      <span
        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10.5px] font-semibold ${
          CLASSIFICATION_TONE[r.classification_band] ?? "border-border-strong bg-surface-2 text-text-muted"
        }`}
      >
        {r.classification_band}
      </span>
    ),
    hideBelow: "lg",
  },
  {
    id: "ingested_at",
    header: "Ingested",
    sortValue: (r) => new Date(r.ingested_at).getTime(),
    render: (r) => <span className="text-text-muted">{timeAgo(r.ingested_at)}</span>,
    hideBelow: "md",
  },
];

const HIDE_CLASSES: Record<NonNullable<Column["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
};

export function CatalogTable({ rows }: { rows: CatalogEntry[] }) {
  const [search, setSearch] = useState("");
  const [programFilter, setProgramFilter] = useState("all");
  const [sort, setSort] = useState<SortState>({ key: "quality_score", dir: "asc" });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const programAreas = useMemo(
    () => Array.from(new Set(rows.map((r) => r.program_area))).sort(),
    [rows],
  );

  const filtered = useMemo(() => {
    let out = rows;
    if (programFilter !== "all") out = out.filter((r) => r.program_area === programFilter);
    const q = search.trim().toLowerCase();
    if (q) {
      out = out.filter(
        (r) =>
          r.dataset_name.toLowerCase().includes(q) ||
          r.source_file.toLowerCase().includes(q) ||
          r.program_area.toLowerCase().includes(q) ||
          r.org_unit.toLowerCase().includes(q) ||
          r.batch_id.toLowerCase().includes(q),
      );
    }
    return out;
  }, [rows, search, programFilter]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const col = COLUMNS.find((c) => c.id === sort.key);
    if (!col?.sortValue) return filtered;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    });
  }, [filtered, sort]);

  function toggleSort(colId: string) {
    setSort((prev) => {
      if (!prev || prev.key !== colId) return { key: colId, dir: "asc" };
      if (prev.dir === "asc") return { key: colId, dir: "desc" };
      return null;
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-text-subtle" aria-hidden />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search datasets, source file, org unit…"
            className="w-full rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-xs text-text placeholder:text-text-subtle focus:border-gov-primary focus:outline-none"
            aria-label="Search catalog"
          />
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="program-filter" className="text-[11px] font-medium text-text-muted">
            Program area
          </label>
          <select
            id="program-filter"
            value={programFilter}
            onChange={(e) => setProgramFilter(e.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-xs text-text focus:border-gov-primary focus:outline-none"
          >
            <option value="all">All ({rows.length})</option>
            {programAreas.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="bg-surface-2">
            <tr>
              <th className="w-9 px-2 py-2" />
              {COLUMNS.map((c) => (
                <th
                  key={c.id}
                  className={`px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-text-muted ${
                    c.align === "right" ? "text-right" : ""
                  } ${c.hideBelow ? HIDE_CLASSES[c.hideBelow] : ""}`}
                >
                  <button
                    type="button"
                    onClick={() => (c.sortValue ? toggleSort(c.id) : undefined)}
                    className={`inline-flex items-center gap-1 ${c.sortValue ? "cursor-pointer hover:text-text" : "cursor-default"} ${
                      c.align === "right" ? "flex-row-reverse" : ""
                    }`}
                    disabled={!c.sortValue}
                  >
                    <span>{c.header}</span>
                    {c.sortValue &&
                      (sort?.key === c.id ? (
                        sort.dir === "asc" ? (
                          <ChevronDown className="size-3" aria-hidden />
                        ) : (
                          <ChevronDown className="size-3 rotate-180" aria-hidden />
                        )
                      ) : (
                        <ChevronsUpDown className="size-3 opacity-40" aria-hidden />
                      ))}
                  </button>
                </th>
              ))}
              <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Lineage
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length + 2} className="p-8 text-center text-xs text-text-muted">
                  No datasets match the current filters.
                </td>
              </tr>
            ) : (
              sorted.map((row) => {
                const isExpanded = expandedId === row.id;
                return (
                  <Fragment key={row.id}>
                    <tr
                      className={`group border-t border-border cursor-pointer transition-colors hover:bg-surface-2/60 ${
                        isExpanded ? "bg-surface-2/60" : ""
                      }`}
                      onClick={() => setExpandedId(isExpanded ? null : row.id)}
                    >
                      <td className="px-2 py-2.5">
                        <button
                          type="button"
                          className="inline-flex size-6 items-center justify-center rounded text-text-subtle transition-colors hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gov-primary focus-visible:ring-offset-1"
                          aria-label={isExpanded ? "Collapse quality detail" : "Expand quality detail"}
                          aria-expanded={isExpanded}
                          aria-controls={`quality-detail-${row.id}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            setExpandedId(isExpanded ? null : row.id);
                          }}
                        >
                          {isExpanded ? (
                            <ChevronDown className="size-4" aria-hidden />
                          ) : (
                            <ChevronRight className="size-4" aria-hidden />
                          )}
                        </button>
                      </td>
                      {COLUMNS.map((c) => (
                        <td
                          key={c.id}
                          className={`px-3 py-2.5 ${c.align === "right" ? "text-right" : ""} ${
                            c.hideBelow ? HIDE_CLASSES[c.hideBelow] : ""
                          }`}
                        >
                          {c.render(row)}
                        </td>
                      ))}
                      <td className="px-3 py-2.5 text-right">
                        <Link
                          href={`/catalog/lineage/?batch=${encodeURIComponent(row.id)}`}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] font-semibold text-gov-primary hover:underline"
                        >
                          View
                          <ArrowUpRight className="size-3" aria-hidden />
                        </Link>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr
                        id={`quality-detail-${row.id}`}
                        className="border-t border-border-2 bg-surface"
                      >
                        <td colSpan={COLUMNS.length + 2} className="p-3 sm:p-4">
                          <QualityPanel entry={row} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <p className="text-[11px] text-text-subtle">
        Showing {formatInt(sorted.length)} of {formatInt(rows.length)} datasets.
      </p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { Database, FlaskConical, RadioTower, RotateCcw } from "lucide-react";

import { USE_MOCK } from "@/lib/api";
import { useMissionDataContext } from "@/lib/mission-data-context";
import { curatedEvidenceSourceLabel } from "@/lib/mission-data-source";

export function EvidenceSetBar() {
  const { hydrated, selection, selectCurated } = useMissionDataContext();

  if (!hydrated) {
    return (
      <div
        className="border-b border-border bg-surface px-4 py-3 sm:px-6 xl:px-8"
        aria-label="Loading active evidence set"
        aria-busy="true"
      >
        <div className="mx-auto h-10 w-full max-w-[1480px] animate-pulse rounded-md bg-surface-2" />
      </div>
    );
  }

  const scaleSelected = selection.kind === "scale";
  const scaleHref = scaleSelected
    ? `/admin/scale/?run=${encodeURIComponent(selection.runId)}`
    : "/admin/scale/";

  return (
    <section
      className="border-b border-border bg-surface px-4 py-3 shadow-soft sm:px-6 xl:px-8"
      aria-label="Active evidence set"
      aria-live="polite"
    >
      <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-3 sm:flex-row sm:items-center">
        <span
          className={`grid size-9 shrink-0 place-items-center rounded-lg ${
            scaleSelected
              ? "bg-gov-primary text-white"
              : "bg-gov-primary-lighter text-gov-primary"
          }`}
          aria-hidden
        >
          {scaleSelected ? <RadioTower className="size-4" /> : <Database className="size-4" />}
        </span>

        <div className="min-w-0 flex-1">
          <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-text-subtle">
            Active evidence set
          </p>
          <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <p className="min-w-0 truncate text-xs font-bold text-text-strong">
              {scaleSelected ? "Selected Scale Run" : "Curated demo"}
            </p>
            {scaleSelected ? (
              <code className="max-w-full truncate font-mono text-[10px] text-text-muted" title={selection.runId}>
                {selection.runId}
              </code>
            ) : (
              <span className="text-[10.5px] text-text-muted">
                {curatedEvidenceSourceLabel(USE_MOCK)}
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-success/35 bg-success-soft px-2.5 text-[9px] font-bold uppercase tracking-[0.1em] text-success">
            <FlaskConical className="size-3" aria-hidden />
            Synthetic only
          </span>
          {scaleSelected ? (
            <button
              type="button"
              onClick={selectCurated}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-md border border-border bg-white px-3 text-[10px] font-bold text-text-muted transition-colors hover:bg-surface-2 hover:text-text-strong"
            >
              <RotateCcw className="size-3.5" aria-hidden />
              Use curated baseline
            </button>
          ) : null}
          <Link
            href={scaleHref}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-md border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold text-gov-primary transition-colors hover:bg-gov-primary hover:text-white"
          >
            <RadioTower className="size-3.5" aria-hidden />
            Open Scale Lab
          </Link>
        </div>
      </div>
    </section>
  );
}

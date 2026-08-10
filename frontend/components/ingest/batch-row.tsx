"use client";

import { useState } from "react";
import { ChevronDown, Loader2, CheckCircle2, ShieldAlert, Clock, type LucideIcon } from "lucide-react";
import type { IngestBatch } from "@/lib/types";
import { QualityGatePanel } from "./quality-gate-panel";
import { VelocityBadge } from "./velocity-badge";
import type { Velocity } from "./velocity";

const STATUS_ICON: Record<IngestBatch["status"], LucideIcon> = {
  queued: Clock,
  running: Loader2,
  passed: CheckCircle2,
  failed: ShieldAlert,
};

const STATUS_TONE: Record<IngestBatch["status"], string> = {
  queued: "text-text-subtle",
  running: "text-info",
  passed: "text-success",
  failed: "text-danger",
};

/** One row of the live batch status list — expands to the quality-gate
 * breakdown. Element 3. */
export function BatchRow({
  batch,
  velocity,
  isNew = false,
  defaultOpen = false,
}: {
  batch: IngestBatch;
  /** Force the velocity tag (e.g. "on-demand" for a simulate-triggered batch). */
  velocity?: Velocity;
  /** Highlights the row as freshly triggered by this session's "Drop a file". */
  isNew?: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const Icon = STATUS_ICON[batch.status];

  return (
    <li className={`rounded-lg border shadow-card ${isNew ? "border-gold/50 bg-gold-soft/30" : "border-border bg-surface"}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-3 px-4 py-3 text-left"
      >
        <Icon className={`size-4 shrink-0 ${STATUS_TONE[batch.status]} ${batch.status === "running" ? "animate-spin" : ""}`} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="truncate font-mono text-[12.5px] font-semibold text-text-strong">{batch.batch_id}</span>
            <VelocityBadge batchId={batch.batch_id} forced={velocity} />
            {isNew && (
              <span className="rounded-full bg-gov-secondary px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-white">
                just triggered
              </span>
            )}
          </span>
          <span className="mt-0.5 block truncate font-mono text-[10.5px] text-text-subtle">{batch.source_file}</span>
        </span>
        <span className="shrink-0 text-right text-[11px] text-text-muted">
          <span className="block font-mono font-semibold text-text-strong">
            {batch.status === "passed" || batch.status === "failed" ? batch.overall_score.toFixed(1) : "—"}
          </span>
          <span className="block">{new Date(batch.ingested_at).toLocaleString()}</span>
        </span>
        <ChevronDown className={`size-4 shrink-0 text-text-subtle transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && (
        <div className="border-t border-border-2 px-4 py-3">
          <QualityGatePanel
            quality={batch.quality}
            overallScore={batch.overall_score}
            status={batch.status}
            rowsRaw={batch.rows_raw}
            rowsCurated={batch.rows_curated}
          />
        </div>
      )}
    </li>
  );
}

"use client";

import Link from "next/link";
import { ArrowRight, FileInput, RadioTower, ShieldCheck } from "lucide-react";

import { PublicSourceOperations } from "@/components/acquisition/public-source-operations";
import { DocumentDropZone } from "@/components/documents/document-drop-zone";
import { LiveEvidenceStatus } from "@/components/public-intelligence/live-evidence-status";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";

export function LiveIngestionWorkspace() {
  const operations = usePublicOperations();
  const health = operations.data?.source_health ?? [];
  return (
    <div className="space-y-6">
      <LiveEvidenceStatus
        control={operations.control}
        healthySources={operations.summary.healthySources}
        sourceCount={health.length}
        lastRefreshedAt={operations.lastRefreshedAt}
        refreshing={operations.refreshing}
        controlling={operations.controlling}
        error={operations.error}
        onRefresh={() => void operations.refresh()}
        onSetContinuous={(enabled) => void operations.setContinuous(enabled)}
      />

      <section className="grid gap-3 lg:grid-cols-2" aria-label="Live ingestion choices">
        <a href="#automatic-public-sources" className="group rounded-xl border border-success/30 bg-success-soft/35 p-5 shadow-soft hover:border-success">
          <span className="grid size-10 place-items-center rounded-lg bg-success text-white"><RadioTower className="size-5" aria-hidden /></span>
          <p className="mt-3 text-[9px] font-bold uppercase tracking-wide text-success">Primary live path</p>
          <h2 className="mt-1 text-lg font-bold text-text-strong">Automatic named public sources</h2>
          <p className="mt-2 text-xs leading-5 text-text-muted">AWS pulls every currently deployed public connector at its responsible source-specific cadence. The registry below names the exact authorities, endpoints, and health state. Each accepted page is hashed, classified, linked, and published.</p>
          <span className="mt-3 inline-flex min-h-10 items-center gap-2 text-xs font-bold text-success">Inspect live connectors <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" aria-hidden /></span>
        </a>
        <a href="#public-file-intake" className="group rounded-xl border border-info/25 bg-info-soft/35 p-5 shadow-soft hover:border-info">
          <span className="grid size-10 place-items-center rounded-lg bg-info text-white"><FileInput className="size-5" aria-hidden /></span>
          <p className="mt-3 text-[9px] font-bold uppercase tracking-wide text-info">Operator input</p>
          <h2 className="mt-1 text-lg font-bold text-text-strong">Upload one sanitized public file</h2>
          <p className="mt-2 text-xs leading-5 text-text-muted">Submit a public, PII-minimized document or structured file through the live S3, EventBridge, quality, model, catalog, and lineage path.</p>
          <span className="mt-3 inline-flex min-h-10 items-center gap-2 text-xs font-bold text-info">Open file intake <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-1" aria-hidden /></span>
        </a>
      </section>

      <div id="automatic-public-sources" className="scroll-mt-24">
        <PublicSourceOperations />
      </div>

      <section id="public-file-intake" className="scroll-mt-24 rounded-xl border border-info/20 bg-info-soft/20 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-[9px] font-bold uppercase tracking-wide text-info">Optional live file intake</p><h2 className="mt-1 text-lg font-bold text-text-strong">Send public bytes through the same governed path</h2><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">This input accepts public, PII-minimized content only. Synthetic fixtures are isolated in the rehearsal workspace and never appear here.</p></div>
          <Link href="/rehearsal/" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-warn/30 bg-white px-3 text-[10px] font-bold text-warn hover:bg-warn-soft"><ShieldCheck className="size-3.5" aria-hidden /> Open synthetic rehearsal</Link>
        </div>
        <DocumentDropZone mode="live-public" />
      </section>
    </div>
  );
}

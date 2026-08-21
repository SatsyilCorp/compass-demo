"use client";

import Link from "next/link";
import { ArrowRight, FlaskConical, RadioTower } from "lucide-react";

import { PublicSourceOperations } from "@/components/acquisition/public-source-operations";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { useEvidenceMode } from "@/lib/evidence-mode-context";

export default function AcquisitionOperationsPage() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker={rehearsal ? "Explicit rehearsal | Live sources paused in this workspace" : "Live public evidence | Source operations"}
        title={rehearsal ? "Return to live evidence to operate public connectors" : "Named public source operations"}
        lead={rehearsal ? "Rehearsal never calls or represents public authorities. Continue with isolated synthetic ingestion, or return to the primary live layer to inspect and control the deployed source schedules." : "AWS continuously pulls bounded records from the deployed public-source registry at responsible cadences. Inspect exact endpoints, health, accepted receipts, real classifier results, and cross-source lineage, or run a source immediately."}
        icon={<RadioTower className="size-5" aria-hidden />}
      />
      {rehearsal ? <section className="mt-6 grid place-items-center rounded-xl border border-warn/30 bg-warn-soft/40 p-9 text-center"><FlaskConical className="size-8 text-warn" aria-hidden /><h2 className="mt-3 text-lg font-bold text-text-strong">Public connector actions are disabled in rehearsal</h2><p className="mt-2 max-w-2xl text-xs leading-5 text-text-muted">This prevents a synthetic presentation run from being mistaken for a public-source pull.</p><div className="mt-5 flex flex-wrap justify-center gap-2"><Link href="/rehearsal/ingest/" className="inline-flex min-h-11 items-center gap-2 rounded-md border border-warn/30 bg-white px-4 text-xs font-bold text-warn">Open rehearsal ingestion <ArrowRight className="size-4" aria-hidden /></Link><Link href="/rehearsal/" className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white">Return to mode selection <ArrowRight className="size-4" aria-hidden /></Link></div></section> : <PublicSourceOperations />}
    </AppShell>
  );
}

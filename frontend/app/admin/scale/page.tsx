"use client";

import Link from "next/link";
import { Activity, ArrowRight, FlaskConical, RadioTower } from "lucide-react";
import { ScaleLab } from "@/components/scale/scale-lab";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { SINGLE_LIVE_MODE } from "@/lib/evidence-mode";

export default function ScaleLabPage() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="System view | Explicit workload rehearsal"
        title={rehearsal ? "Scale Lab" : "Scale evidence is isolated from live public data"}
        lead={rehearsal ? "Launch a deterministic, cost-bounded workload rehearsal across synthetic generation, buffered ingestion, quality, intelligence, governed export, and operational evidence." : SINGLE_LIVE_MODE ? "Scale Lab generates synthetic capacity records and is not part of this presentation. Live source volumes and health remain available from the public evidence workspace." : "Scale Lab intentionally uses generated records, so it remains locked until the operator selects rehearsal. Live source volumes and health remain available from the public evidence workspace."}
        icon={<RadioTower className="size-5" aria-hidden />}
        actions={(
          <span className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3 text-[10px] font-bold uppercase tracking-wide ${rehearsal ? "border-warn/35 bg-warn-soft text-warn" : "border-info/35 bg-info-soft text-info"}`}>
            <Activity className="size-3.5" aria-hidden /> {rehearsal ? "Rehearsal control" : "Live data protected"}
          </span>
        )}
      />
      {rehearsal ? <ScaleLab /> : SINGLE_LIVE_MODE ? <section className="mt-6 grid place-items-center rounded-xl border border-dashed border-info/40 bg-info-soft/35 p-10 text-center"><FlaskConical className="size-9 text-info" aria-hidden /><h2 className="mt-4 text-lg font-bold text-text-strong">Scale evidence is kept apart from this presentation</h2><p className="mt-2 max-w-2xl text-xs leading-5 text-text-muted">This separation prevents a 1,000 to 1,000,000 record capacity run from appearing anywhere as live public evidence.</p><Link href="/admin/acquisition/" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white hover:bg-gov-primary-dark">Open live source operations <ArrowRight className="size-4" aria-hidden /></Link></section> : <section className="mt-6 grid place-items-center rounded-xl border border-dashed border-warn/40 bg-warn-soft/35 p-10 text-center"><FlaskConical className="size-9 text-warn" aria-hidden /><h2 className="mt-4 text-lg font-bold text-text-strong">Activate rehearsal before generating scale records</h2><p className="mt-2 max-w-2xl text-xs leading-5 text-text-muted">This separation prevents a 1,000 to 1,000,000 record capacity run from appearing anywhere as live public evidence.</p><Link href="/rehearsal/" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white hover:bg-gov-primary-dark">Open rehearsal boundary <ArrowRight className="size-4" aria-hidden /></Link></section>}
    </AppShell>
  );
}

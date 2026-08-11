"use client";

import { Activity, RadioTower } from "lucide-react";
import { ScaleLab } from "@/components/scale/scale-lab";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { USE_MOCK } from "@/lib/api";

export default function ScaleLabPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="System view | Capacity proof"
        title="Scale Lab"
        lead="Launch a deterministic, cost-bounded production rehearsal across synthetic generation, buffered ingestion, quality, intelligence, governed export, and operational evidence."
        icon={<RadioTower className="size-5" aria-hidden />}
        actions={(
          <span className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-3 text-[10px] font-bold uppercase tracking-wide ${USE_MOCK ? "border-warn/35 bg-warn-soft text-warn" : "border-success/35 bg-success-soft text-success"}`}>
            <Activity className="size-3.5" aria-hidden /> {USE_MOCK ? "Replay control" : "Live AWS control"}
          </span>
        )}
      />
      <ScaleLab />
    </AppShell>
  );
}

"use client";

import { ServerCog } from "lucide-react";

import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { SystemInspector } from "./system-inspector";

/** Protected product proof surface for the live service and deterministic replay. */
export default function MissionControlPage() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker={rehearsal ? "Explicit rehearsal | Isolated operational replay" : "Live public evidence | Backend control plane"}
        title={rehearsal ? "Rehearsal mission and model control" : "Live mission and model control"}
        lead={rehearsal ? "Inspect deterministic rehearsal adapters without presenting their runs, notifications, or model outputs as live AWS evidence." : "Trace each live decision from authenticated request to source identity, data policy, document workflow, model receipt, delivery evidence, and append-only audit state. Every returned operation declares its evidence class."}
        icon={<ServerCog className="size-5" aria-hidden />}
      />
      <SystemInspector />
    </AppShell>
  );
}

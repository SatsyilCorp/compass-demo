"use client";

import { ServerCog } from "lucide-react";

import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { SystemInspector } from "./system-inspector";

/** Protected product proof surface for the live service and deterministic replay. */
export default function MissionControlPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Operations evidence | Live backend control plane"
        title="Mission and model control"
        lead="Trace each decision from authenticated request to data policy, document workflow, model receipt, delivery evidence, and append-only audit state. Sensitive infrastructure and record content stay outside this view."
        icon={<ServerCog className="size-5" aria-hidden />}
      />
      <SystemInspector />
    </AppShell>
  );
}

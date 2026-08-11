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
        kicker="System view"
        title="Mission control"
        lead="Trace each decision from authenticated request to data policy, workflow receipt, and append-only audit evidence. Sensitive infrastructure and record content stay outside this view."
        icon={<ServerCog className="size-5" aria-hidden />}
      />
      <SystemInspector />
    </AppShell>
  );
}

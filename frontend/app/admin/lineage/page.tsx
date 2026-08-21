"use client";

import { Route } from "lucide-react";

import { OperationalLineage } from "@/components/lineage/operational-lineage";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { useEvidenceMode } from "@/lib/evidence-mode-context";

export default function OperationalLineagePage() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker={rehearsal ? "Explicit rehearsal | Synthetic stage progression" : "Live public evidence | Server-backed stage progression"}
        title={rehearsal ? "Rehearsal operational lineage" : "Live operational lineage"}
        lead={rehearsal ? "Trace only synthetic rehearsal runs and keep their evidence class visible at every stage." : "Trace live file intake, public acquisition, data quality, model execution, publication, and downstream use through one protected evidence contract. Every stage exposes its evidence class, status, timing, counts, digests, implementation revision, and receipt locator when available."}
        icon={<Route className="size-5" aria-hidden />}
      />
      <OperationalLineage />
    </AppShell>
  );
}

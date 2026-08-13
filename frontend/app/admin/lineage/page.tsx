import { Route } from "lucide-react";

import { OperationalLineage } from "@/components/lineage/operational-lineage";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function OperationalLineagePage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Operations evidence | Server-backed stage progression"
        title="Operational lineage"
        lead="Trace document intake, public acquisition, data quality, model execution, publication, and downstream use through one protected evidence contract. Every stage exposes its status, timing, counts, source digest, artifact digest, implementation revision, and receipt locator when available."
        icon={<Route className="size-5" aria-hidden />}
      />
      <OperationalLineage />
    </AppShell>
  );
}

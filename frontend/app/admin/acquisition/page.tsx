import { RadioTower } from "lucide-react";

import { AcquisitionOperationsDashboard } from "@/components/acquisition/acquisition-operations-dashboard";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function AcquisitionOperationsPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Element 3 of 7 | Multi-source DataOps"
        title="Multi-source ingestion operations"
        lead="Choose live public APIs or a clearly labeled synthetic replay. See every source record advance through acquisition, retention, governance, change detection, ML classification, evidence linking, and decision support once per second."
        icon={<RadioTower className="size-5" aria-hidden />}
      />
      <AcquisitionOperationsDashboard />
    </AppShell>
  );
}

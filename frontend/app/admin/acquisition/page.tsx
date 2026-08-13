import { RadioTower } from "lucide-react";

import { AcquisitionOperationsDashboard } from "@/components/acquisition/acquisition-operations-dashboard";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function AcquisitionOperationsPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Element 3 of 7 | Real multi-source DataOps"
        title="Live source operations"
        lead="Watch independent public-source connectors acquire, retain, govern, classify, link, and publish decision evidence. The display updates every second while each official source follows its responsible request cadence."
        icon={<RadioTower className="size-5" aria-hidden />}
      />
      <AcquisitionOperationsDashboard />
    </AppShell>
  );
}

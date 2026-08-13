import { RadioTower } from "lucide-react";

import { PublicSourceOperations } from "@/components/acquisition/public-source-operations";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function AcquisitionOperationsPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Live public evidence | Separate from the scored synthetic workflow"
        title="Named public source operations"
        lead="Pull bounded records from four named public authorities, inspect the exact endpoint and accepted receipt, and follow the result into cross-source intelligence. Use Element 3 for the guaranteed synthetic file demonstration."
        icon={<RadioTower className="size-5" aria-hidden />}
      />
      <PublicSourceOperations />
    </AppShell>
  );
}

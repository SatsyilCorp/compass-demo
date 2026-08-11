import { BrainCircuit } from "lucide-react";

import { ModelOperations } from "@/components/mlops/model-operations";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function ModelOperationsPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Element 5 of 7 | Decision Analytics and MLOps"
        title="Model operations and decision evidence"
        lead="Classify dropped documents with a governed classical model and prove its complete lifecycle: immutable training data, evaluation gates, registry version, human promotion, deployment, monitoring, drift, and conditional retraining."
        icon={<BrainCircuit className="size-5" aria-hidden />}
      />
      <ModelOperations />
    </AppShell>
  );
}

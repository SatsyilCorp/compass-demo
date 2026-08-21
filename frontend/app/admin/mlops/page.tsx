"use client";

import { BrainCircuit } from "lucide-react";

import { ModelOperations } from "@/components/mlops/model-operations";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { useEvidenceMode } from "@/lib/evidence-mode-context";

export default function ModelOperationsPage() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker={rehearsal ? "Element 5 of 7 | Explicit model rehearsal" : "Element 5 of 7 | Live decision analytics and MLOps"}
        title={rehearsal ? "Rehearse the governed model lifecycle" : "Model operations on accepted public evidence"}
        lead={rehearsal ? "Exercise deterministic training, evaluation, registry, promotion, monitoring, and drift contracts without claiming a cloud execution." : "Inspect the champion classifier receipts created from live public narratives, execute the registered SageMaker funding candidate on a bounded current cohort, and manage training, promotion, monitoring, drift, and retraining without silent replay fallback."}
        icon={<BrainCircuit className="size-5" aria-hidden />}
      />
      <ModelOperations />
    </AppShell>
  );
}

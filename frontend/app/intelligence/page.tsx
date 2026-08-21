import type { Metadata } from "next";

import { IntelligenceWorkspace } from "@/components/public-intelligence/intelligence-workspace";
import { AppShell } from "@/components/shell/app-shell";

export const metadata: Metadata = {
  title: "Public ONR Portfolio Intelligence",
  description: "Real public award and research evidence, purpose-built predictive models, provenance, uncertainty, and cited decision support.",
};

export default function PublicIntelligencePage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <IntelligenceWorkspace />
    </AppShell>
  );
}

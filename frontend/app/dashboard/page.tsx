import type { Metadata } from "next";

import { LivePublicDecisionWorkspace } from "@/components/public-intelligence/live-decision-workspace";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import { AppShell } from "@/components/shell/app-shell";
import { EvidenceModeDashboard } from "./view";

/**
 * /dashboard - element 6.
 *
 * A server component only so the route can carry static metadata; every byte of
 * data on the page is fetched client-side from the protected HttpApi in live
 * mode. Explicit rehearsal routes use their isolated fixtures. The signed-in
 * persona's token is required because the export is static
 * (`output: "export"`) and there is no server-side session to fetch with.
 */
export const metadata: Metadata = {
  title: "Live Public Decision Workspace",
  description:
    "Accepted public-source changes, model receipts, analyst review flags, provenance, and cited decision support.",
};

export default function DashboardPage() {
  return (
    <AppShell>
      <EvidenceModeDashboard live={<LivePublicDecisionWorkspace />} rehearsal={<DashboardView />} />
    </AppShell>
  );
}

import type { Metadata } from "next";

import { AppShell } from "@/components/shell/app-shell";
import { DashboardView } from "@/components/dashboard/dashboard-view";

/**
 * /dashboard - element 6.
 *
 * A server component only so the route can carry static metadata; every byte of
 * data on the page is fetched client-side from the HttpApi (or the mock
 * fixtures) with the signed-in persona's token, because the export is static
 * (`output: "export"`) and there is no server-side session to fetch with.
 */
export const metadata: Metadata = {
  title: "Executive Dashboard",
  description:
    "Portfolio KPIs, funding concentration, execution trend, topic mix, natural-language Q&A with citations, and the anomaly → summary → approval workflow.",
};

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardView />
    </AppShell>
  );
}

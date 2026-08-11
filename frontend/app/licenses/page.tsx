import type { Metadata } from "next";

import { AppShell } from "@/components/shell/app-shell";
import { LicensesView } from "@/components/dashboard/licenses-view";

/**
 * /licenses - element 6 (license lifecycle). Server component for metadata
 * only; `GET /licenses` is called client-side with the persona's token.
 */
export const metadata: Metadata = {
  title: "Licenses",
  description:
    "Data-license lifecycle: entitlements, seat utilization, dataset linkage, and computed renewal alerts for every feed Compass depends on.",
};

export default function LicensesPage() {
  return (
    <AppShell>
      <LicensesView />
    </AppShell>
  );
}

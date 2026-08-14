import type { Metadata } from "next";

import { AppShell } from "@/components/shell/app-shell";
import { LicensesView } from "@/components/dashboard/licenses-view";
import { LiveSourceGovernance } from "@/components/governance/live-source-governance";
import { EvidenceModeLicenses } from "./view";

/**
 * /licenses - element 6 (license lifecycle). Server component for metadata
 * only; `GET /licenses` is called client-side with the persona's token.
 */
export const metadata: Metadata = {
  title: "Source Governance",
  description:
    "Authority, access basis, ownership, cadence, health, and downstream use for every live public connector.",
};

export default function LicensesPage() {
  return (
    <AppShell>
      <EvidenceModeLicenses live={<LiveSourceGovernance />} rehearsal={<LicensesView />} />
    </AppShell>
  );
}

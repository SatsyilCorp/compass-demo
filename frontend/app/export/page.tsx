import type { Metadata } from "next";

import { AppShell } from "@/components/shell/app-shell";
import { ExportView } from "@/components/export/export-view";

/**
 * /export - element 7. Server component for metadata only; the request itself
 * runs client-side against POST /export with the persona's token (static
 * export, no server session).
 */
export const metadata: Metadata = {
  title: "Export",
  description:
    "Filtered CSV/JSON/Parquet export of the curated portfolio, with row- and column-level security, the aggregation guard and its approval path, and the audit trail.",
};

export default function ExportPage() {
  return (
    <AppShell>
      <ExportView />
    </AppShell>
  );
}

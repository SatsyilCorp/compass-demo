import type { Metadata } from "next";

import { AppShell } from "@/components/shell/app-shell";
import { ExportView } from "@/components/export/export-view";
import { LivePublicRelease } from "@/components/export/live-public-release";
import { EvidenceModeExport } from "./view";

/**
 * /export - element 7. Server component for metadata only; the request itself
 * runs client-side against POST /export with the persona's token (static
 * export, no server session).
 */
export const metadata: Metadata = {
  title: "Public Evidence Portable Preview",
  description:
    "Browser-generated JSON and CSV preview of accepted public evidence with source, model, review, and lineage references.",
};

export default function ExportPage() {
  return (
    <AppShell>
      <EvidenceModeExport live={<LivePublicRelease />} rehearsal={<ExportView />} />
    </AppShell>
  );
}

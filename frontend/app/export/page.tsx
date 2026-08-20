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

function LiveExportPlane() {
  return (
    <>
      <LivePublicRelease />
      <section
        aria-label="Governed synthetic portfolio release"
        className="mt-8 border-t border-border pt-6"
      >
        <p className="mb-3 inline-flex items-center gap-2 rounded-md border border-warn/40 bg-warn-soft px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-warn">
          Governed demonstration portfolio - synthetic, labeled - released through the protected export service
        </p>
        <ExportView />
      </section>
    </>
  );
}

export default function ExportPage() {
  return (
    <AppShell>
      <EvidenceModeExport live={<LiveExportPlane />} rehearsal={<ExportView />} />
    </AppShell>
  );
}

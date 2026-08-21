import { Database } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { LivePublicCatalog } from "@/components/catalog/live-public-catalog";
import { RehearsalCatalog } from "@/components/catalog/rehearsal-catalog";
import { EvidenceModeCatalog } from "./view";

/**
 * Element 4 - Data catalog. GET /catalog: every curated dataset (grain =
 * ingest batch), its quality/health score, and metadata. Each row expands
 * into the score formula + rule breakdown; "View" opens the static lineage
 * page with the live batch identifier in its query string.
 */
export default function CatalogPage() {
  return (
    <AppShell>
      <EvidenceModeCatalog
        live={<><PageHeader kicker="Live public evidence | Governance, quality, and catalog" icon={<Database className="size-[18px]" aria-hidden />} title="Governed public evidence catalog" lead="Every row comes from an accepted public-source receipt. Open a source product to see capture time, hash, model version, identity keys, accountable owner and steward, individual source links, and exact run lineage." /><div className="mt-6"><LivePublicCatalog /></div></>}
        rehearsal={<><PageHeader kicker="Explicit rehearsal | Governance and catalog" icon={<Database className="size-[18px]" aria-hidden />} title="Synthetic rehearsal catalog" lead="These deterministic mission batches are isolated from the live public evidence catalog and remain labeled as rehearsal throughout lineage and release." /><div className="mt-6"><RehearsalCatalog /></div></>}
      />
    </AppShell>
  );
}

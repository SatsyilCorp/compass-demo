import { Suspense } from "react";
import { BATCH_IDS } from "@/lib/mock/grants";
import { LineageView } from "@/components/catalog/lineage-view";

export async function generateStaticParams() {
  // This legacy dynamic route belongs only to explicit synthetic rehearsal.
  // Live public records use /admin/lineage/?run= so a static build never
  // contacts a protected API or mixes rehearsal IDs into the live catalog.
  return BATCH_IDS.map((id) => ({ id }));
}

// `output: 'export'` (next.config.ts) forbids on-demand server rendering, so
// dynamicParams must be false: any id not in generateStaticParams gets an
// S3/CloudFront-level 404. Same static-export/dynamic-route pattern as
// a prior static-export app's dynamic-route pattern.
export const dynamicParams = false;

export default function CatalogLineagePage() {
  // LineageView reads useSearchParams() (the ?batch= route), which Next
  // requires to sit under a Suspense boundary when prerendering.
  return (
    <Suspense fallback={null}>
      <LineageView />
    </Suspense>
  );
}

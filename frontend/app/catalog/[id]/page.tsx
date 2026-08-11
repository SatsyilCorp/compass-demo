import { Suspense } from "react";
import { BATCH_IDS } from "@/lib/mock/grants";
import { LineageView } from "@/components/catalog/lineage-view";

/**
 * Server-only helper for generateStaticParams below. Mirrors
 * the build-params pattern from a prior static-export app: prefer real
 * IDs from the deployed API when building against a live backend, and fall
 * back to the mock fixture's batch_ids (identical to GET /catalog `id`
 * values in mock mode) so a build never blocks on a transient API outage.
 */
async function listCatalogIdsForBuild(): Promise<string[]> {
  const useMock = process.env.NEXT_PUBLIC_USE_MOCK !== "false";
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

  if (!useMock && apiBaseUrl) {
    try {
      const res = await fetch(`${apiBaseUrl}/catalog`);
      if (res.ok) {
        const json = (await res.json()) as { datasets: { id: string }[] };
        if (json.datasets?.length) return json.datasets.map((d) => d.id);
      }
    } catch {
      // Network/auth failure at build time - fall through to the mock ids.
    }
  }

  return [...BATCH_IDS];
}

export async function generateStaticParams() {
  const ids = await listCatalogIdsForBuild();
  return ids.map((id) => ({ id }));
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

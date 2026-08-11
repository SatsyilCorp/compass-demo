import { Suspense } from "react";
import { LineageView } from "@/components/catalog/lineage-view";

/**
 * Element 4 - lineage for ANY batch, addressed as /catalog/lineage/?batch=<id>.
 *
 * Why this exists alongside app/catalog/[id]/page.tsx: `output: 'export'`
 * pre-renders dynamic segments from generateStaticParams at BUILD time, and
 * /catalog requires a JWT, so a build cannot enumerate live batch ids. Any
 * batch ingested after the build (every live demo drop) would 404 under
 * /catalog/<id>/. A single static page + query param has no such limit - the
 * id is read in the browser, so a batch created seconds ago resolves fine.
 *
 * useSearchParams() requires a Suspense boundary during prerender.
 */
export default function CatalogLineageQueryPage() {
  return (
    <Suspense fallback={null}>
      <LineageView />
    </Suspense>
  );
}

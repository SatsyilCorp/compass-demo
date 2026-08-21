/**
 * The static export cannot add `/catalog/<batch>/` pages for batches created
 * after build time. Keep every catalog entry on the static query route so a
 * newly ingested batch can be opened immediately.
 */
export function catalogLineageHref(batchId: string): string {
  return `/catalog/lineage/?batch=${encodeURIComponent(batchId)}`;
}

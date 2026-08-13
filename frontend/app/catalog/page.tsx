"use client";

import { useCallback, useEffect, useState } from "react";
import { Database, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { CatalogTable } from "@/components/catalog/catalog-table";
import { getCatalog, ApiError } from "@/lib/api";
import { subscribeLiveDemoStreamTick } from "@/lib/live-demo-stream-events";
import type { CatalogResponse } from "@/lib/types";

/**
 * Element 4 - Data catalog. GET /catalog: every curated dataset (grain =
 * ingest batch), its quality/health score, and metadata. Each row expands
 * into the score formula + rule breakdown; "View" opens the static lineage
 * page with the live batch identifier in its query string.
 */
export default function CatalogPage() {
  const [data, setData] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await getCatalog();
      setData(response);
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? `API error ${cause.status}` : cause instanceof Error ? cause.message : "Failed to load catalog");
    }
  }, []);

  useEffect(() => {
    void load();
    return subscribeLiveDemoStreamTick(() => void load());
  }, [load]);

  return (
    <AppShell>
      <PageHeader
        kicker="Element 4 of 7 | Governance, Quality, and Catalog"
        icon={<Database className="size-[18px]" aria-hidden />}
        title="Governed data and document catalog"
        lead="Every curated dataset in the S&T portfolio, with its data-quality gate result, freshness, and originating pipeline run. Expand a row for the score formula and rule-by-rule breakdown, or open the full lineage graph."
      />

      <div className="mt-6">
        {error && (
          <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
            <TriangleAlert className="size-4 shrink-0" aria-hidden />
            {error}
          </div>
        )}
        {!error && !data && <CatalogSkeleton />}
        {!error && data && <CatalogTable rows={data.datasets} />}
      </div>
    </AppShell>
  );
}

function CatalogSkeleton() {
  return (
    <div className="space-y-3">
      <div className="skeleton h-9 w-full max-w-xs rounded-md" />
      <div className="overflow-hidden rounded-md border border-border">
        <div className="skeleton h-9 w-full" />
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton mt-px h-11 w-full" />
        ))}
      </div>
    </div>
  );
}

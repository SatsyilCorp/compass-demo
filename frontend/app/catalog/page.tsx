"use client";

import { useEffect, useState } from "react";
import { Database, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { CatalogTable } from "@/components/catalog/catalog-table";
import { getCatalog, ApiError } from "@/lib/api";
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

  useEffect(() => {
    let cancelled = false;
    getCatalog()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? `API error ${e.status}` : e instanceof Error ? e.message : "Failed to load catalog");
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

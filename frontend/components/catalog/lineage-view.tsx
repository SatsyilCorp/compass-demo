"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, GitBranch, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { getCatalog, getCatalogLineage, ApiError } from "@/lib/api";
import type { CatalogEntry, LineageResponse } from "@/lib/types";
import { ScoreChip } from "./score-chip";
import { LineageGraph } from "./lineage-graph";
import { formatInt } from "./format";

/**
 * Element 4 - end-to-end lineage graph for one dataset (batch).
 *
 * Batch id resolution order:
 *   1. `?batch=<id>` query param  - served by the STATIC /catalog/lineage/ page.
 *      This is the path the catalog table links to, and the only one that works
 *      for a batch ingested AFTER the frontend was built (e.g. a live demo
 *      drop): `output: 'export'` pre-renders a fixed set of dynamic segments,
 *      so a brand-new id under /catalog/<id>/ would 404 at CloudFront.
 *   2. `/catalog/<id>/` path segment - retained for the pre-rendered batches
 *      and any existing bookmarks.
 */
export function LineageView() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const id = searchParams?.get("batch") || params?.id || "";

  const [entry, setEntry] = useState<CatalogEntry | null>(null);
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "not_found" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setStatus("loading");
    setEntry(null);
    setLineage(null);

    Promise.all([getCatalog(), getCatalogLineage(id)])
      .then(([catalogRes, lineageRes]) => {
        if (cancelled) return;
        setEntry(catalogRes.datasets.find((d) => d.id === id) ?? null);
        setLineage(lineageRes);
        setStatus("ready");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setStatus("not_found");
        } else {
          setErrorMessage(e instanceof Error ? e.message : "Failed to load lineage");
          setStatus("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <AppShell>
      <Link
        href="/catalog/"
        className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-text-muted hover:text-gov-primary"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Back to catalog
      </Link>

      <PageHeader
        kicker="Mission flow | Trace"
        icon={<GitBranch className="size-[18px]" aria-hidden />}
        title={entry ? entry.dataset_name : "Dataset lineage"}
        lead={
          entry
            ? `End-to-end trace for run ${entry.run_id} - source file → quality gate → curated table → topic model → executive dashboard.`
            : "Source file → quality gate → curated table → topic model → executive dashboard."
        }
        actions={
          entry ? (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <ScoreChip score={entry.quality_score} />
              <span>{formatInt(entry.row_count)} rows</span>
            </div>
          ) : undefined
        }
      />

      <div className="mt-6">
        {status === "loading" && <LineageSkeleton />}

        {status === "not_found" && (
          <div className="rounded-md border border-border bg-surface-2/60 p-8 text-center">
            <p className="text-sm font-semibold text-text-strong">Dataset not found</p>
            <p className="mt-1 text-xs text-text-muted">
              <code className="font-mono">{id}</code> has no lineage visible to this persona, or does not exist.
            </p>
            <Link href="/catalog/" className="mt-4 inline-block text-xs font-semibold text-gov-primary hover:underline">
              Return to the catalog
            </Link>
          </div>
        )}

        {status === "error" && (
          <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
            <TriangleAlert className="size-4 shrink-0" aria-hidden />
            {errorMessage}
          </div>
        )}

        {status === "ready" && lineage && <LineageGraph nodes={lineage.nodes} edges={lineage.edges} />}
      </div>
    </AppShell>
  );
}

function LineageSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
      <div className="skeleton h-[560px] rounded-md" />
      <div className="skeleton h-[560px] rounded-md" />
    </div>
  );
}

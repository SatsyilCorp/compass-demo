"use client";

import { useCallback, useEffect, useState } from "react";
import { TriangleAlert } from "lucide-react";

import { CatalogTable } from "@/components/catalog/catalog-table";
import { ApiError, getCatalog } from "@/lib/api";
import { subscribeLiveDemoStreamTick } from "@/lib/live-demo-stream-events";
import type { CatalogResponse } from "@/lib/types";

export function RehearsalCatalog() {
  const [data, setData] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setData(await getCatalog());
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? `API error ${cause.status}` : cause instanceof Error ? cause.message : "Failed to load rehearsal catalog");
    }
  }, []);
  useEffect(() => {
    void load();
    return subscribeLiveDemoStreamTick(() => void load());
  }, [load]);
  if (error) return <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger"><TriangleAlert className="size-4" aria-hidden />{error}</div>;
  if (!data) return <div className="skeleton h-96 rounded-xl" aria-label="Loading rehearsal catalog" />;
  return <CatalogTable rows={data.datasets} />;
}

"use client";

import { useState } from "react";
import { ExternalLink, FileJson, Loader2 } from "lucide-react";

import { USE_MOCK, getOpenApiSpec } from "@/lib/api";

import { useCompassAction } from "@/components/dashboard/use-compass-query";

/**
 * `GET /openapi.json` (element 7) — the served contract.
 *
 * In mock mode there is no deployed API to serve the document, and the client
 * says so rather than rendering a fabricated spec: `lib/api.ts` returns a stub
 * carrying a `note` field explaining where the real document lives. That stub
 * is printed verbatim.
 */
const API_BASE_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) || "";

export function OpenApiPanel() {
  const [spec, setSpec] = useState<string | null>(null);
  const { run, pending, error } = useCompassAction(getOpenApiSpec);

  async function fetchSpec() {
    try {
      const doc = await run();
      setSpec(JSON.stringify(doc, null, 2));
    } catch {
      /* surfaced via error */
    }
  }

  return (
    <section className="rounded-md border border-border bg-surface p-4 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded bg-gov-primary text-white">
            <FileJson className="size-4" aria-hidden />
          </span>
          <div>
            <h2 className="text-[14.5px] font-semibold text-text-strong">Served API contract</h2>
            <p className="mt-0.5 max-w-xl text-[11.5px] leading-snug text-text-muted">
              The API serves its own OpenAPI 3.1 document at{" "}
              <code className="font-mono text-[11px]">/openapi.json</code> — the same contract this
              page is built against, including the 428 response the aggregation guard returns.
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => void fetchSpec()}
            disabled={pending}
            className="inline-flex items-center gap-1.5 rounded border border-border px-3 py-2 text-[12px] font-semibold text-text transition-colors hover:bg-surface-2 disabled:opacity-50"
          >
            {pending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
            Fetch contract
          </button>
          {API_BASE_URL ? (
            <a
              href={`${API_BASE_URL}/openapi.json`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded bg-gov-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover"
            >
              Open /openapi.json
              <ExternalLink className="size-3.5" aria-hidden />
            </a>
          ) : null}
        </div>
      </div>

      {!API_BASE_URL ? (
        <p className="mt-3 rounded border border-border bg-surface-2 px-3 py-2 text-[11.5px] text-text-muted">
          No <code className="font-mono text-[11px]">NEXT_PUBLIC_API_BASE_URL</code> is configured in
          this build{USE_MOCK ? " (mock mode)" : ""}, so there is no live document to link to. Fetch
          the contract to see exactly what the client receives here.
        </p>
      ) : null}

      {error ? (
        <p className="mt-3 rounded border border-danger bg-danger-soft px-3 py-2 text-[11.5px] text-danger">
          {error}
        </p>
      ) : null}

      {spec ? (
        <pre className="mt-3 max-h-64 overflow-auto rounded border border-border bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-text">
          {spec}
        </pre>
      ) : null}
    </section>
  );
}

export default OpenApiPanel;

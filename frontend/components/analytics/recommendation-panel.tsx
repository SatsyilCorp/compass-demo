import { Sparkles } from "lucide-react";
import type { AnalyticsRunDetail } from "@/lib/types";
import { formatInt } from "./trend";

/**
 * The written decision recommendation the topic-model routine produces,
 * plus enough run provenance (params/metrics) that an evaluator can see
 * where the recommendation came from — not just trust it.
 */
export function RecommendationPanel({ detail }: { detail: AnalyticsRunDetail }) {
  const embeddingModel = typeof detail.params.embedding_model === "string" ? detail.params.embedding_model : null;
  const k = typeof detail.params.k === "number" ? detail.params.k : null;
  const coherence = typeof detail.metrics.coherence === "number" ? detail.metrics.coherence : null;
  const grantsScored = typeof detail.metrics.grants_scored === "number" ? detail.metrics.grants_scored : null;

  return (
    <div className="rounded-md border border-gov-primary/25 bg-accent-soft p-5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-gov-primary text-white">
          <Sparkles className="size-4" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-gov-primary">
            Decision recommendation
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-text-strong">{detail.recommendation}</p>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-gov-primary/15 pt-3 text-[11px] sm:grid-cols-4">
        <div>
          <dt className="text-text-subtle">Run ID</dt>
          <dd className="truncate font-mono text-text" title={detail.run_id}>
            {detail.run_id}
          </dd>
        </div>
        <div>
          <dt className="text-text-subtle">Grants scored</dt>
          <dd className="font-medium tabular-nums text-text">{grantsScored !== null ? formatInt(grantsScored) : "—"}</dd>
        </div>
        <div>
          <dt className="text-text-subtle">Coherence</dt>
          <dd className="font-medium tabular-nums text-text">{coherence !== null ? coherence.toFixed(2) : "—"}</dd>
        </div>
        <div>
          <dt className="text-text-subtle">Topics (k)</dt>
          <dd className="font-medium tabular-nums text-text">{k ?? "—"}</dd>
        </div>
      </dl>
      {embeddingModel && (
        <p className="mt-2 text-[10.5px] text-text-subtle">
          Embeddings via <span className="font-mono">{embeddingModel}</span> (Bedrock, in-boundary).
        </p>
      )}
    </div>
  );
}

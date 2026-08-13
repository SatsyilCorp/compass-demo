import Link from "next/link";
import { ArrowUpRight, GitBranch } from "lucide-react";
import type { CatalogEntry } from "@/lib/types";
import { ScoreChip, scoreTone } from "./score-chip";
import { formatDateTime, formatInt, freshnessTone, humanizeRule, timeAgo } from "./format";

const FRESHNESS_CLASSES: Record<string, string> = {
  success: "text-success",
  warn: "text-warn",
  danger: "text-danger",
};

const RULE_BAR_CLASSES: Record<string, string> = {
  success: "bg-success",
  warn: "bg-warn",
  danger: "bg-danger",
};

/**
 * The expandable panel every catalog row opens into: the score formula
 * (spelled out, not just a bare number), a rule-by-rule breakdown with
 * rejected-row counts, freshness, curated-schema version, and the
 * originating pipeline run_id - linking through to the lineage graph.
 */
export function QualityPanel({ entry }: { entry: CatalogEntry }) {
  const totalRejected = entry.quality_rules.reduce((acc, r) => acc + r.failed_rows, 0);
  const fresh = freshnessTone(entry.ingested_at);

  return (
    <div className="grid gap-5 rounded-md border border-border-2 bg-surface-2/60 p-4 sm:p-5 lg:grid-cols-[1.3fr_1fr]">
      {/* Score formula + rule-by-rule breakdown */}
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <ScoreChip score={entry.quality_score} size="lg" />
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
              Overall quality score
            </p>
            <p className="text-xs leading-snug text-text-muted">
              Average of each rule&apos;s pass rate - <code className="font-mono text-[11px]">passed_rows ÷ (passed_rows + failed_rows) × 100</code>,
              rounded to 1 decimal across all {entry.quality_rules.length} rules.
            </p>
          </div>
        </div>

        <table className="mt-4 w-full text-xs">
          <thead>
            <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-wide text-text-subtle">
              <th className="py-1.5 pr-2 font-semibold">Rule</th>
              <th className="py-1.5 pr-2 text-right font-semibold">Passed</th>
              <th className="py-1.5 pr-2 text-right font-semibold">Rejected</th>
              <th className="py-1.5 pr-2 text-right font-semibold">Score</th>
              <th className="py-1.5 font-semibold">Pass rate</th>
            </tr>
          </thead>
          <tbody>
            {entry.quality_rules.map((r) => {
              const tone = scoreTone(r.score);
              return (
                <tr key={r.rule} className="border-b border-border-2 last:border-0">
                  <td className="py-1.5 pr-2 font-medium text-text">{humanizeRule(r.rule)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-text-muted">{formatInt(r.passed_rows)}</td>
                  <td className={`py-1.5 pr-2 text-right tabular-nums ${r.failed_rows > 0 ? "font-semibold text-danger" : "text-text-muted"}`}>
                    {formatInt(r.failed_rows)}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-text-muted">{r.score.toFixed(1)}</td>
                  <td className="w-28 py-1.5">
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2" aria-hidden>
                      <div className={`h-full rounded-full ${RULE_BAR_CLASSES[tone]}`} style={{ width: `${r.score}%` }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <p className="mt-3 text-xs text-text-muted">
          <span className="font-semibold text-text">{formatInt(totalRejected)}</span> row
          {totalRejected === 1 ? "" : "s"} rejected across {formatInt(entry.row_count)} curated in this batch.
        </p>
      </div>

      {/* Metadata: freshness, schema version, run_id */}
      <div className="space-y-3 lg:border-l lg:border-border-2 lg:pl-5">
        <dl className="space-y-2.5 text-xs">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-text-subtle">Freshness</dt>
            <dd className={`text-right font-medium ${FRESHNESS_CLASSES[fresh]}`}>
              {timeAgo(entry.ingested_at)}
              <span className="ml-1.5 font-normal text-text-subtle">({formatDateTime(entry.ingested_at)})</span>
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-text-subtle">Schema version</dt>
            <dd className="text-right font-mono text-text">grants_curated · v1 (001_schema.sql)</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-text-subtle">Batch ID</dt>
            <dd className="text-right font-mono text-text">{entry.batch_id}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-text-subtle">Originating run</dt>
            <dd className="text-right font-mono text-text">{entry.run_id}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-text-subtle">Classification band</dt>
            <dd className="text-right font-medium text-text">{entry.classification_band}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-text-subtle">Business owner</dt>
            <dd className="text-right text-text">{entry.owner}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-text-subtle">Data steward</dt>
            <dd className="text-right text-text">{entry.steward}</dd>
          </div>
        </dl>

        <p className="rounded border border-warn/30 bg-warn-soft px-2.5 py-2 text-[11px] leading-relaxed text-text-muted">
          These are representative governance roles. Government data owners and stewards must be assigned before operational use.
        </p>

        <Link
          href={`/catalog/${encodeURIComponent(entry.id)}/`}
          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-gov-primary/30 bg-accent-soft px-3 py-1.5 text-xs font-semibold text-gov-primary transition-colors hover:bg-gov-primary hover:text-white"
        >
          <GitBranch className="size-3.5" aria-hidden />
          View end-to-end lineage
          <ArrowUpRight className="size-3.5" aria-hidden />
        </Link>
      </div>

      <details className="rounded-md border border-border bg-surface lg:col-span-2">
        <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-text-strong">
          Open governed data dictionary ({entry.data_dictionary.length} fields)
        </summary>
        <div className="overflow-x-auto border-t border-border">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="bg-surface-2 text-[10.5px] uppercase tracking-wide text-text-subtle">
              <tr>
                <th className="px-3 py-2 font-semibold">Field</th>
                <th className="px-3 py-2 font-semibold">Type</th>
                <th className="px-3 py-2 font-semibold">Business definition</th>
                <th className="px-3 py-2 font-semibold">Access control</th>
              </tr>
            </thead>
            <tbody>
              {entry.data_dictionary.map((field) => (
                <tr key={field.field} className="border-t border-border-2 align-top">
                  <td className="px-3 py-2 font-mono font-semibold text-text">{field.field}</td>
                  <td className="px-3 py-2 font-mono text-text-muted">{field.data_type}</td>
                  <td className="px-3 py-2 text-text-muted">{field.definition}</td>
                  <td className="px-3 py-2 text-text-muted">{field.security}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

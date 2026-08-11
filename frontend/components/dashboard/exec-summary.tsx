"use client";

import { Loader2, RefreshCw, ScrollText, Sigma, Sparkles } from "lucide-react";

import { postChat } from "@/lib/api";
import type { DashboardResponse } from "@/lib/types";

import { useCompassQuery } from "./use-compass-query";
import { num, pct, usd } from "./format";

/**
 * Executive auto-summary (element 6).
 *
 * The panel is deliberately split in two, and labelled as such:
 *
 *   COMPUTED   arithmetic over the `GET /dashboard` payload, done in the
 *              browser. Deterministic, reproducible, and safe to read aloud in
 *              a briefing. No model is involved.
 *   NARRATIVE  a Bedrock generation (`POST /chat`) over the same portfolio,
 *              with its citations and the model id shown.
 *
 * Fusing the two into one anonymous paragraph is the standard way an
 * "AI summary" ends up unfalsifiable. Keeping the seam visible means an
 * evaluator can check the numbers themselves and judge the prose separately.
 */
const SUMMARY_PROMPT =
  "Give a short executive summary of the S&T research portfolio I can see: where investment is " +
  "concentrated, what is trending, and what a program officer should look at next. Two or three " +
  "sentences.";

export function ExecSummary({ data }: { data: DashboardResponse }) {
  const narrative = useCompassQuery(() => postChat({ message: SUMMARY_PROMPT }));

  const facts = computeFacts(data);

  return (
    <section className="compass-rise flex h-full flex-col rounded-md border border-border bg-surface shadow-soft">
      <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded bg-gov-primary text-white">
            <ScrollText className="size-4" aria-hidden />
          </span>
          <div>
            <h2 className="text-[14.5px] font-semibold text-text-strong">Executive summary</h2>
            <p className="mt-0.5 text-[11.5px] leading-snug text-text-muted">
              Regenerated for whichever persona is signed in. The summary can only describe rows
              that persona may read.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={narrative.reload}
          disabled={narrative.loading}
          className="inline-flex shrink-0 items-center gap-1.5 rounded border border-border px-2.5 py-1.5 text-[11px] font-semibold text-text transition-colors hover:bg-surface-2 disabled:opacity-50"
        >
          <RefreshCw className={narrative.loading ? "size-3 animate-spin" : "size-3"} aria-hidden />
          Regenerate
        </button>
      </header>

      <div className="grid flex-1 gap-4 p-4 lg:grid-cols-2">
        {/* ---- Computed half ------------------------------------------- */}
        <div>
          <p className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
            <Sigma className="size-3.5" aria-hidden />
            Computed from GET /dashboard
          </p>
          <ul className="mt-2.5 flex flex-col gap-2">
            {facts.map((f) => (
              <li key={f.label} className="flex items-baseline justify-between gap-3">
                <span className="text-[12px] text-text-muted">{f.label}</span>
                <span className="shrink-0 text-right">
                  <span className="font-mono text-[12.5px] font-semibold tabular-nums text-text-strong">
                    {f.value}
                  </span>
                  {f.note ? (
                    <span className="ml-1.5 text-[10.5px] text-text-subtle">{f.note}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* ---- Narrative half ------------------------------------------ */}
        <div className="lg:border-l lg:border-border-2 lg:pl-4">
          <p className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
            <Sparkles className="size-3.5" aria-hidden />
            Narrative: generated
          </p>

          {narrative.loading ? (
            <div className="mt-2.5 flex flex-col gap-2" aria-busy>
              <span className="skeleton block h-3 w-full rounded" />
              <span className="skeleton block h-3 w-[92%] rounded" />
              <span className="skeleton block h-3 w-[70%] rounded" />
              <p className="mt-1 flex items-center gap-1.5 text-[11px] text-text-subtle">
                <Loader2 className="size-3 animate-spin" aria-hidden />
                Generating over the visible portfolio…
              </p>
            </div>
          ) : narrative.error ? (
            <p className="mt-2.5 rounded border border-danger bg-danger-soft px-2.5 py-2 text-[11.5px] text-danger">
              Summary unavailable: {narrative.error}. The computed figures on the left are
              unaffected.
            </p>
          ) : narrative.data ? (
            <>
              <p className="mt-2.5 text-[12.5px] leading-relaxed text-text">
                {narrative.data.answer}
              </p>
              {narrative.data.citations.length > 0 ? (
                <ul className="mt-2.5 flex flex-wrap gap-1.5">
                  {narrative.data.citations.map((c) => (
                    <li
                      key={c.grant_no}
                      title={c.title}
                      className="rounded border border-border-2 bg-surface-2 px-2 py-1 font-mono text-[10.5px] text-gov-primary"
                    >
                      {c.grant_no}
                    </li>
                  ))}
                </ul>
              ) : null}
              <p className="mt-2 font-mono text-[10px] text-text-subtle">
                model: {narrative.data.model}
              </p>
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}

type Fact = { label: string; value: string; note?: string };

function computeFacts(d: DashboardResponse): Fact[] {
  const facts: Fact[] = [
    {
      label: "Grants in scope",
      value: num(d.kpis.total_grants),
      note: `${num(d.kpis.active_program_areas)} program areas`,
    },
    {
      label: "Obligated funding",
      value: usd(d.kpis.total_funding_usd),
      note: d.kpis.total_funding_usd === null ? "column-level security" : undefined,
    },
  ];

  const ranked = d.funding_by_program_area
    .slice()
    .sort((a, b) => (b.amount_usd ?? b.grant_count) - (a.amount_usd ?? a.grant_count));
  const top = ranked[0];
  if (top) {
    const denominator =
      top.amount_usd !== null
        ? d.funding_by_program_area.reduce((a, r) => a + (r.amount_usd ?? 0), 0)
        : d.funding_by_program_area.reduce((a, r) => a + r.grant_count, 0);
    const numerator = top.amount_usd !== null ? top.amount_usd : top.grant_count;
    facts.push({
      label: "Largest concentration",
      value: top.program_area,
      note: denominator > 0 ? `${pct(numerator / denominator, 0)} of portfolio` : undefined,
    });
  }

  const years = d.funding_by_fiscal_year.filter(
    (y): y is { fiscal_year: number; amount_usd: number } => typeof y.amount_usd === "number",
  );
  if (years.length >= 2) {
    const sorted = years.slice().sort((a, b) => a.fiscal_year - b.fiscal_year);
    const last = sorted.at(-1)!;
    const prior = sorted.at(-2)!;
    const change = prior.amount_usd > 0 ? last.amount_usd / prior.amount_usd - 1 : 0;
    facts.push({
      label: `FY${last.fiscal_year} vs FY${prior.fiscal_year}`,
      value: `${change >= 0 ? "+" : ""}${(change * 100).toFixed(1)}%`,
      note: "obligated",
    });
  }

  facts.push(
    {
      label: "Average quality score",
      value: d.kpis.avg_quality_score?.toFixed(1) ?? "No evidence",
      note: d.kpis.avg_quality_score === null
        ? "no persisted gate receipt"
        : `${num(d.quality_trend.length)} runs`,
    },
    {
      label: "Needs attention",
      value: `${num(d.kpis.open_anomalies)} anomalies`,
      note: `${num(d.kpis.pending_approvals)} approvals pending`,
    },
  );

  return facts;
}

export default ExecSummary;

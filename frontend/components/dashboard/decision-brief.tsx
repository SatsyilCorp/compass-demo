"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import type { DashboardResponse } from "@/lib/types";

import { pct, usd } from "./format";


type BriefItem = {
  eyebrow: string;
  title: string;
  detail: string;
  tone: "info" | "warn" | "success";
  icon: typeof TrendingUp;
};

export function DecisionBrief({ data }: { data: DashboardResponse }) {
  const items = buildBrief(data);
  const needsAction = data.kpis.open_anomalies > 0 || data.kpis.pending_approvals > 0;

  return (
    <section className="overflow-hidden rounded-lg border border-gov-primary/20 bg-gov-primary text-white shadow-card">
      <header className="flex flex-col gap-3 border-b border-white/15 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gold-light">
            Decision brief
          </p>
          <h2 className="mt-1 text-xl font-semibold text-white">What deserves attention now</h2>
        </div>
        <Link
          href={needsAction ? "/dashboard/#portfolio-exceptions" : "/catalog/"}
          className="inline-flex min-h-11 items-center justify-center gap-2 self-start rounded-md border border-white/25 bg-white/10 px-4 text-sm font-semibold text-white transition-colors hover:bg-white/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        >
          {needsAction ? "Review exceptions" : "Explore portfolio"}
          <ArrowRight className="size-4" aria-hidden />
        </Link>
      </header>

      <div className="grid md:grid-cols-3">
        {items.map((item, index) => {
          const Icon = item.icon;
          return (
            <article
              key={item.eyebrow}
              className={`p-5 ${index > 0 ? "border-t border-white/15 md:border-l md:border-t-0" : ""}`}
            >
              <div className="flex items-center gap-2 text-gold-light">
                <Icon className="size-4" aria-hidden />
                <p className="text-[11px] font-bold uppercase tracking-[0.14em]">{item.eyebrow}</p>
              </div>
              <h3 className="mt-2 text-base font-semibold leading-snug text-white">{item.title}</h3>
              <p className="mt-1.5 text-sm leading-6 text-white/75">{item.detail}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function buildBrief(data: DashboardResponse): BriefItem[] {
  const years = data.funding_by_fiscal_year
    .filter((row): row is { fiscal_year: number; amount_usd: number } => row.amount_usd !== null)
    .slice()
    .sort((a, b) => a.fiscal_year - b.fiscal_year);
  const latest = years.at(-1);
  const prior = years.at(-2);
  const change = latest && prior && prior.amount_usd > 0
    ? latest.amount_usd / prior.amount_usd - 1
    : null;

  const quality = data.quality_trend.slice().sort((a, b) => a.date.localeCompare(b.date));
  const latestQuality = quality.at(-1);
  const priorQuality = quality.at(-2);
  const qualityChange = latestQuality && priorQuality ? latestQuality.score - priorQuality.score : 0;

  const changed: BriefItem = change !== null
    ? {
        eyebrow: "What changed",
        title: `${change >= 0 ? "Up" : "Down"} ${pct(Math.abs(change), 1)} in FY${latest!.fiscal_year} obligations`,
        detail: `${usd(latest!.amount_usd)} is visible in the current scope, compared with ${usd(prior!.amount_usd)} in FY${prior!.fiscal_year}.`,
        tone: change >= 0 ? "success" : "warn",
        icon: change >= 0 ? TrendingUp : TrendingDown,
      }
    : {
        eyebrow: "What changed",
        title: `${qualityChange >= 0 ? "+" : ""}${qualityChange.toFixed(1)} points in latest quality run`,
        detail: latestQuality
          ? `The most recent governed ingest scored ${latestQuality.score.toFixed(1)}.`
          : "No completed quality runs are visible in this scope.",
        tone: qualityChange >= 0 ? "success" : "warn",
        icon: qualityChange >= 0 ? TrendingUp : TrendingDown,
      };

  const exceptionCount = data.kpis.open_anomalies + data.kpis.pending_approvals;
  const exceptions: BriefItem = {
    eyebrow: "Exceptions",
    title: exceptionCount > 0 ? `${exceptionCount} items need review` : "No open decision blockers",
    detail: `${data.kpis.open_anomalies} open anomalies and ${data.kpis.pending_approvals} pending approvals are in the current queue.`,
    tone: exceptionCount > 0 ? "warn" : "success",
    icon: exceptionCount > 0 ? CircleAlert : CheckCircle2,
  };

  let recommendation = "Use the governed catalog to review the portfolio behind these measures.";
  if (data.kpis.open_anomalies > 0) {
    recommendation = "Triage the highest-severity anomaly, capture a disposition, then refresh this brief.";
  } else if (data.kpis.pending_approvals > 0) {
    recommendation = "Review the oldest pending approval and verify its evidence before release.";
  } else if (
    data.kpis.avg_quality_score !== null &&
    data.kpis.avg_quality_score < 95
  ) {
    recommendation = "Inspect the latest quality run and address the rule with the largest failure count.";
  }

  return [
    changed,
    exceptions,
    {
      eyebrow: "Recommended next action",
      title: data.kpis.open_anomalies > 0 ? "Resolve the leading exception" : "Validate the current investment mix",
      detail: recommendation,
      tone: "info",
      icon: Sparkles,
    },
  ];
}

export default DecisionBrief;

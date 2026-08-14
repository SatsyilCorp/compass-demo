"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Bot,
  CheckCircle2,
  Database,
  DollarSign,
  ExternalLink,
  FileSearch,
  GitBranch,
  Network,
  RadioTower,
  Radar,
  RefreshCw,
} from "lucide-react";

import { PageHeader } from "@/components/shell/page-header";
import { LiveEvidenceStatus } from "./live-evidence-status";
import {
  formatPublicMoney,
  publicRecordTitle,
  publicSourceLabel,
} from "@/lib/public-intelligence/operations";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";

export function LivePublicDecisionWorkspace() {
  const operations = usePublicOperations();
  const { data, summary } = operations;
  const health = data?.source_health ?? [];
  const failedSources = health.filter((source) => source.status === "failed" || source.status === "stale");
  const changedRuns = summary.latest.filter(
    (run) => (run.added_records ?? 0) + (run.changed_records ?? 0) > 0,
  );
  const records = summary.records.slice(0, 12);
  const emptyRecordDetail = operations.error
    ? "The protected public evidence service is unavailable. No synthetic records were substituted. Refresh after the service recovers."
    : operations.control?.enabled
      ? "Continuous acquisition is running. A power user can also run a named source immediately from Ingestion."
      : operations.control?.status === "stopped"
        ? "Continuous acquisition is stopped. Start it here or run a named source immediately from Ingestion."
        : "Controller state is still being verified. No source activity is claimed until its protected receipt is available.";

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Live public intelligence | Decision workspace"
        title="See what changed, where the evidence came from, and what needs review"
        icon={<Radar className="size-5" aria-hidden />}
        lead="This workspace is built from the latest accepted public-source receipts. Funding is observed in the bounded USAspending page, opportunities come from Grants.gov, notices come from the Federal Register, publications come from Crossref, and every model result carries its real run and version."
        actions={(
          <div className="flex flex-wrap gap-2">
            <Link href="/intelligence/" className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white hover:bg-gov-primary-dark">
              Ask with citations <FileSearch className="size-4" aria-hidden />
            </Link>
            <button type="button" onClick={() => void operations.refresh()} disabled={operations.refreshing} className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-white px-4 text-xs font-bold text-text-muted hover:bg-surface-2 disabled:opacity-50">
              <RefreshCw className={`size-4 ${operations.refreshing ? "animate-spin" : ""}`} aria-hidden /> Refresh
            </button>
          </div>
        )}
      />

      <LiveEvidenceStatus
        control={operations.control}
        healthySources={summary.healthySources}
        sourceCount={health.length}
        lastRefreshedAt={operations.lastRefreshedAt}
        refreshing={operations.refreshing}
        controlling={operations.controlling}
        error={operations.error}
        onRefresh={() => void operations.refresh()}
        onSetContinuous={(enabled) => void operations.setContinuous(enabled)}
      />

      {operations.loading && !data ? <DashboardSkeleton /> : null}

      {data ? (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Current public evidence indicators">
            <DecisionMetric icon={Database} label="Accepted records" value={summary.acceptedRecords.toLocaleString("en-US")} detail={`Latest accepted page from ${summary.latest.length} named authorities`} />
            <DecisionMetric icon={DollarSign} label="Observed funding" value={formatPublicMoney(summary.observedFunding)} detail="Amounts in the current retained record previews" />
            <DecisionMetric icon={GitBranch} label="New or changed" value={summary.changedRecords.toLocaleString("en-US")} detail={`${changedRuns.length} source receipts contain a current delta`} tone={summary.changedRecords > 0 ? "info" : "default"} />
            <DecisionMetric icon={AlertTriangle} label="Needs analyst review" value={summary.reviewFlags.toLocaleString("en-US")} detail={`${failedSources.length} source health issue${failedSources.length === 1 ? "" : "s"}`} tone={summary.reviewFlags > 0 || failedSources.length > 0 ? "warn" : "default"} />
          </section>

          <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-xl border border-border bg-white p-5 shadow-card">
              <SectionHeading kicker="What changed" title="Latest accepted source receipts" detail="These numbers come directly from retained acquisition receipts. A failed pull never replaces the prior accepted snapshot." />
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {summary.latest.map((run) => (
                  <article key={run.run_id} className="rounded-lg border border-border bg-surface-2 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold text-text-strong">{publicSourceLabel(run)}</p>
                        <p className="mt-1 font-mono text-[8px] text-text-subtle">{run.run_id}</p>
                      </div>
                      <span className="rounded-full border border-success/30 bg-success-soft px-2 py-1 text-[8px] font-bold uppercase text-success">Accepted</span>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      <MiniMetric label="Records" value={(run.record_count ?? 0).toLocaleString("en-US")} />
                      <MiniMetric label="Added" value={(run.added_records ?? 0).toLocaleString("en-US")} />
                      <MiniMetric label="Changed" value={(run.changed_records ?? 0).toLocaleString("en-US")} />
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-gov-primary/25 bg-white px-2.5 text-[9px] font-bold text-gov-primary hover:bg-gov-primary-lighter">Trace run <ArrowRight className="size-3" aria-hidden /></Link>
                      {run.record_preview?.[0]?.source_url ? <a href={run.record_preview[0].source_url} target="_blank" rel="noreferrer" className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-border bg-white px-2.5 text-[9px] font-bold text-text-muted hover:bg-surface-2">Open source <ExternalLink className="size-3" aria-hidden /></a> : null}
                    </div>
                  </article>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-white p-5 shadow-card">
              <SectionHeading kicker="Real model execution" title="Classifier receipts on live records" detail="Each accepted source page is sent to the deployed champion document classifier. The receipt binds the model version, input artifact, output digest, confidence, and review count." />
              <div className="mt-4 space-y-3">
                {summary.classificationReceipts.map((run) => {
                  const receipt = run.classification_summary!;
                  return (
                    <article key={run.run_id} className="rounded-lg border border-success/25 bg-success-soft/35 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-bold text-text-strong">{publicSourceLabel(run)}</p>
                          <p className="mt-1 font-mono text-[8px] text-text-muted">{receipt.model_version}</p>
                        </div>
                        <span className="inline-flex items-center gap-1 rounded-full border border-success/25 bg-white px-2 py-1 text-[8px] font-bold uppercase text-success"><BadgeCheck className="size-3" aria-hidden /> Executed</span>
                      </div>
                      <div className="mt-3 grid grid-cols-3 gap-2">
                        <MiniMetric label="Classified" value={receipt.record_count.toLocaleString("en-US")} />
                        <MiniMetric label="Confidence" value={`${Math.round(receipt.mean_confidence * 100)}%`} />
                        <MiniMetric label="Review" value={receipt.review_required_count.toLocaleString("en-US")} />
                      </div>
                    </article>
                  );
                })}
                {summary.classificationReceipts.length === 0 ? <EmptyEvidence icon={Bot} title="No live classifier receipt yet" detail="The next accepted source run will invoke the configured champion model and retain its receipt." /> : null}
              </div>
              <Link href="/admin/mlops/" className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-xs font-bold text-white hover:bg-gov-primary-dark">Open model operations <ArrowRight className="size-3.5" aria-hidden /></Link>
            </div>
          </section>

          <section className="rounded-xl border border-border bg-white shadow-card">
            <div className="flex flex-wrap items-end justify-between gap-3 p-5">
              <SectionHeading kicker="Decision evidence" title="Current live records" detail="Open the authority record or its exact Compass run. Values are not mixed with a synthetic portfolio." />
              <Link href="/catalog/" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 px-3 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Open full catalog <ArrowRight className="size-3.5" aria-hidden /></Link>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left">
                <thead className="border-y border-border bg-surface-2 text-[9px] font-bold uppercase tracking-wide text-text-subtle">
                  <tr><th className="px-4 py-3">Evidence point</th><th className="px-4 py-3">Source</th><th className="px-4 py-3">Observed value</th><th className="px-4 py-3">Model route</th><th className="px-4 py-3">Disposition</th><th className="px-4 py-3">Proof</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {records.map(({ run, record, prediction, flagged }) => (
                    <tr key={`${run.source_id}-${record.source_record_id}`} className="align-top text-xs">
                      <td className="max-w-md px-4 py-3"><p className="font-bold text-text-strong">{publicRecordTitle(record)}</p><p className="mt-1 line-clamp-2 text-[9px] leading-4 text-text-muted">{record.description ?? record.record_type?.replaceAll("_", " ") ?? "Public evidence record"}</p><p className="mt-1 font-mono text-[8px] text-text-subtle">{record.source_record_id}</p></td>
                      <td className="px-4 py-3"><p className="font-bold text-gov-primary">{publicSourceLabel(run)}</p><p className="mt-1 text-[8px] text-text-muted">Captured {new Date(run.updated_at).toLocaleString()}</p></td>
                      <td className="px-4 py-3 font-bold text-text-strong">{record.award_amount_usd == null ? record.status ?? record.published_date ?? "Source fact" : formatPublicMoney(record.award_amount_usd)}</td>
                      <td className="px-4 py-3"><p className="font-bold text-text-strong">{prediction?.document_class.replaceAll("_", " ") ?? (run.classification_summary ? "Classified in retained artifact" : "No model receipt")}</p>{prediction ? <p className="mt-1 text-[8px] text-text-muted">{Math.round(prediction.confidence * 100)}% | {run.classification_summary?.model_version}</p> : null}</td>
                      <td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${flagged ? "border-warn/30 bg-warn-soft text-warn" : "border-success/30 bg-success-soft text-success"}`}>{flagged ? "Analyst review" : "Evidence current"}</span></td>
                      <td className="px-4 py-3"><div className="flex gap-1">{record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer" className="grid size-9 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Open public record ${record.source_record_id}`}><ExternalLink className="size-3.5" aria-hidden /></a> : null}<Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="grid size-9 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Trace ${record.source_record_id}`}><Network className="size-3.5" aria-hidden /></Link></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {records.length === 0 ? <div className="p-5"><EmptyEvidence icon={RadioTower} title="Awaiting accepted public records" detail={emptyRecordDetail} /></div> : null}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function DecisionMetric({ icon: Icon, label, value, detail, tone = "default" }: { icon: typeof Database; label: string; value: string; detail: string; tone?: "default" | "info" | "warn" }) {
  const style = tone === "warn" ? "border-warn/35 bg-warn-soft" : tone === "info" ? "border-info/25 bg-info-soft/45" : "border-border bg-white";
  return <article className={`rounded-xl border p-4 shadow-soft ${style}`}><Icon className={`size-5 ${tone === "warn" ? "text-warn" : "text-gov-primary"}`} aria-hidden /><p className="mt-3 text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 font-mono text-2xl font-bold text-text-strong">{value}</p><p className="mt-1 text-[9px] leading-4 text-text-muted">{detail}</p></article>;
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md border border-border bg-white p-2"><p className="text-[7px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 truncate text-[10px] font-bold text-text-strong" title={value}>{value}</p></div>;
}

function SectionHeading({ kicker, title, detail }: { kicker: string; title: string; detail: string }) {
  return <div><p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">{kicker}</p><h2 className="mt-1 text-lg font-bold text-text-strong">{title}</h2><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">{detail}</p></div>;
}

function EmptyEvidence({ icon: Icon, title, detail }: { icon: typeof Bot; title: string; detail: string }) {
  return <div className="rounded-lg border border-dashed border-border bg-surface-2 p-5 text-center"><Icon className="mx-auto size-5 text-text-subtle" aria-hidden /><p className="mt-2 text-xs font-bold text-text-strong">{title}</p><p className="mx-auto mt-1 max-w-lg text-[10px] leading-4 text-text-muted">{detail}</p></div>;
}

function DashboardSkeleton() {
  return <div className="space-y-4" aria-busy="true"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="skeleton h-32 rounded-xl" />)}</div><div className="grid gap-4 xl:grid-cols-2"><div className="skeleton h-80 rounded-xl" /><div className="skeleton h-80 rounded-xl" /></div></div>;
}

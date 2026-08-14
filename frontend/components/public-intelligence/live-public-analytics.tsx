"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle2,
  ExternalLink,
  GitBranch,
  Network,
  RadioTower,
  ShieldAlert,
} from "lucide-react";

import { LiveEvidenceStatus } from "./live-evidence-status";
import {
  publicRecordTitle,
  publicSourceLabel,
} from "@/lib/public-intelligence/operations";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";

export function LivePublicAnalytics() {
  const operations = usePublicOperations();
  const health = operations.data?.source_health ?? [];
  const classCounts = new Map<string, number>();
  for (const run of operations.summary.classificationReceipts) {
    for (const [label, count] of Object.entries(run.classification_summary?.class_counts ?? {})) {
      classCounts.set(label, (classCounts.get(label) ?? 0) + count);
    }
  }
  const classes = [...classCounts.entries()].sort((left, right) => right[1] - left[1]);
  const maxClass = Math.max(1, ...classes.map((item) => item[1]));
  const anomalies = operations.summary.latest.flatMap((run) =>
    (run.review_flags ?? []).map((flag) => ({ run, flag })),
  );

  return (
    <div className="space-y-5">
      <LiveEvidenceStatus
        control={operations.control}
        healthySources={operations.summary.healthySources}
        sourceCount={health.length}
        lastRefreshedAt={operations.lastRefreshedAt}
        refreshing={operations.refreshing}
        controlling={operations.controlling}
        error={operations.error}
        onRefresh={() => void operations.refresh()}
        onSetContinuous={(enabled) => void operations.setContinuous(enabled)}
      />

      <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-xl border border-border bg-white p-5 shadow-card">
          <SectionHeading icon={BarChart3} kicker="Observed source mix" title="What the current public pages contain" detail="Counts come from the latest accepted receipt per authority. They are bounded source pages, not estimates of the complete ONR portfolio." />
          <div className="mt-5 space-y-3">
            {operations.summary.latest.map((run) => {
              const percentage = operations.summary.acceptedRecords > 0 ? ((run.record_count ?? 0) / operations.summary.acceptedRecords) * 100 : 0;
              return <div key={run.run_id}><div className="flex items-end justify-between gap-3"><div><p className="text-xs font-bold text-text-strong">{publicSourceLabel(run)}</p><p className="mt-0.5 text-[8px] text-text-muted">{run.scope_disclosure}</p></div><p className="font-mono text-xs font-bold text-gov-primary">{(run.record_count ?? 0).toLocaleString("en-US")}</p></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3"><div className="h-full rounded-full bg-gov-primary" style={{ width: `${Math.max(2, percentage)}%` }} /></div></div>;
            })}
            {!operations.loading && operations.summary.latest.length === 0 ? <Empty title="No source analytics are available yet" detail="Wait for the first scheduled receipt or run a source from Ingestion." /> : null}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-white p-5 shadow-card">
          <SectionHeading icon={Bot} kicker="Model-derived routing" title="Live classifier distribution" detail="The deployed champion classifier routes public narratives into operational document classes. Confidence and review thresholds remain attached to each prediction." />
          <div className="mt-5 space-y-3">
            {classes.map(([label, count]) => <div key={label}><div className="flex justify-between gap-3 text-xs"><span className="font-bold text-text-strong">{label.replaceAll("_", " ")}</span><span className="font-mono font-bold text-gov-primary">{count.toLocaleString("en-US")}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3"><div className="h-full rounded-full bg-success" style={{ width: `${Math.max(3, (count / maxClass) * 100)}%` }} /></div></div>)}
            {classes.length === 0 ? <Empty title="Awaiting a classifier receipt" detail="A configured source run invokes the real champion model and records the class distribution here." /> : null}
          </div>
          {operations.summary.classificationReceipts[0]?.classification_summary ? <div className="mt-4 rounded-lg border border-success/25 bg-success-soft/35 p-3"><p className="flex items-center gap-2 text-xs font-bold text-success"><CheckCircle2 className="size-4" aria-hidden /> Model executed on accepted evidence</p><p className="mt-1 font-mono text-[8px] text-text-muted">{operations.summary.classificationReceipts[0].classification_summary?.model_version}</p></div> : null}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-border bg-white p-5 shadow-card">
          <SectionHeading icon={GitBranch} kicker="Change intelligence" title="Source deltas that deserve attention" detail="Stable record hashes separate added, changed, unchanged, and not-observed records. Not observed does not mean deleted because each source pull is bounded." />
          <div className="mt-4 space-y-2">
            {operations.summary.latest.map((run) => <article key={run.run_id} className="rounded-lg border border-border bg-surface-2 p-3"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold text-text-strong">{publicSourceLabel(run)}</p><p className="mt-1 font-mono text-[8px] text-text-subtle">{run.run_id}</p></div><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${((run.added_records ?? 0) + (run.changed_records ?? 0)) > 0 ? "border-info/30 bg-info-soft text-info" : "border-success/30 bg-success-soft text-success"}`}>{((run.added_records ?? 0) + (run.changed_records ?? 0)) > 0 ? "Delta observed" : "No delta"}</span></div><div className="mt-3 grid grid-cols-4 gap-2"><Metric label="Added" value={run.added_records ?? 0} /><Metric label="Changed" value={run.changed_records ?? 0} /><Metric label="Unchanged" value={run.unchanged_records ?? 0} /><Metric label="Not observed" value={run.not_observed_records ?? 0} /></div><Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="mt-3 inline-flex min-h-9 items-center gap-1.5 text-[9px] font-bold text-gov-primary hover:underline">Trace exact change receipt <ArrowRight className="size-3" aria-hidden /></Link></article>)}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-white p-5 shadow-card">
          <SectionHeading icon={ShieldAlert} kicker="Transparent anomaly rules" title="Records in the analyst review queue" detail="These are observable rules such as a changed source record, high award value, or missing narrative. They are not autonomous fraud or mission-success conclusions." />
          <div className="mt-4 space-y-2">
            {anomalies.slice(0, 12).map(({ run, flag }) => {
              const projected = operations.summary.records.find((item) => item.run.run_id === run.run_id && item.record.source_record_id === flag.source_record_id);
              return <article key={`${run.run_id}-${flag.source_record_id}`} className="rounded-lg border border-warn/30 bg-warn-soft/45 p-3"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold text-text-strong">{projected ? publicRecordTitle(projected.record) : flag.source_record_id}</p><p className="mt-1 text-[8px] text-text-muted">{publicSourceLabel(run)} | {flag.source_record_id}</p></div><AlertTriangle className="size-4 shrink-0 text-warn" aria-hidden /></div><div className="mt-2 flex flex-wrap gap-1">{flag.reasons.map((reason) => <span key={reason} className="rounded-full border border-warn/25 bg-white px-2 py-1 text-[8px] font-bold text-warn">{reason}</span>)}</div><div className="mt-3 flex gap-2">{flag.source_url ? <a href={flag.source_url} target="_blank" rel="noreferrer" className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-border bg-white px-2.5 text-[9px] font-bold text-gov-primary">Open source <ExternalLink className="size-3" aria-hidden /></a> : null}<Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-border bg-white px-2.5 text-[9px] font-bold text-gov-primary">Lineage <Network className="size-3" aria-hidden /></Link></div></article>;
            })}
            {anomalies.length === 0 ? <Empty title="No current review rule is open" detail="The accepted source pages did not trigger the transparent anomaly rules." /> : null}
          </div>
        </div>
      </section>
    </div>
  );
}

function SectionHeading({ icon: Icon, kicker, title, detail }: { icon: typeof BarChart3; kicker: string; title: string; detail: string }) { return <div className="flex items-start gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-lg bg-gov-primary-lighter text-gov-primary"><Icon className="size-4.5" aria-hidden /></span><div><p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">{kicker}</p><h2 className="mt-1 text-lg font-bold text-text-strong">{title}</h2><p className="mt-1 text-xs leading-5 text-text-muted">{detail}</p></div></div>; }
function Metric({ label, value }: { label: string; value: number }) { return <div className="rounded-md border border-border bg-white p-2 text-center"><p className="text-[7px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 font-mono text-xs font-bold text-text-strong">{value.toLocaleString("en-US")}</p></div>; }
function Empty({ title, detail }: { title: string; detail: string }) { return <div className="rounded-lg border border-dashed border-border bg-surface-2 p-4 text-center"><RadioTower className="mx-auto size-5 text-text-subtle" aria-hidden /><p className="mt-2 text-xs font-bold text-text-strong">{title}</p><p className="mt-1 text-[10px] leading-4 text-text-muted">{detail}</p></div>; }

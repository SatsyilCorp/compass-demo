"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  ExternalLink,
  KeyRound,
  RadioTower,
  ShieldCheck,
} from "lucide-react";

import { LiveEvidenceStatus } from "@/components/public-intelligence/live-evidence-status";
import { PageHeader } from "@/components/shell/page-header";
import { publicSourceLabel } from "@/lib/public-intelligence/operations";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";

export function LiveSourceGovernance() {
  const operations = usePublicOperations();
  const health = operations.data?.source_health ?? [];
  const latestBySource = new Map(operations.summary.latest.map((run) => [run.source_id, run]));
  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Live public evidence | Source governance"
        title="Know the authority, access basis, owner, cadence, and downstream use"
        lead="These are the actual source contracts behind the live product. Public access does not remove governance: each connector records the authority, endpoint, responsible cadence, current health, accepted receipt, owner, steward, and model route."
        icon={<KeyRound className="size-5" aria-hidden />}
      />
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
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <GovernanceMetric icon={RadioTower} label="Named authorities" value={String(health.length)} detail="Verified by the operations API" />
        <GovernanceMetric icon={CheckCircle2} label="Healthy" value={health.length ? `${operations.summary.healthySources}/${health.length}` : "Not verified"} detail="Latest operational health" />
        <GovernanceMetric icon={Database} label="Accepted products" value={String(operations.summary.latest.length)} detail="Latest retained source pages" />
        <GovernanceMetric icon={ShieldCheck} label="Commercial seats" value="0" detail="For these public connectors" />
      </section>
      <section className="space-y-3" aria-label="Public source contracts">
        {!operations.refreshing && !operations.error && health.length === 0 ? (
          <div className="rounded-xl border border-warn/35 bg-warn-soft p-5 text-xs leading-5 text-warn">
            No source contracts were returned by the live operations API. Compass is not
            substituting a configured or rehearsal source list.
          </div>
        ) : null}
        {health.map((source) => {
          const run = latestBySource.get(source.source_id);
          return <article key={source.source_id} className="rounded-xl border border-border bg-white p-5 shadow-card"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${source.status === "healthy" ? "border-success/30 bg-success-soft text-success" : source.status === "failed" ? "border-danger/30 bg-danger-soft text-danger" : "border-warn/30 bg-warn-soft text-warn"}`}>{source.status.replaceAll("-", " ")}</span><span className="rounded-full border border-info/25 bg-info-soft px-2 py-1 text-[8px] font-bold uppercase text-info">Public access basis</span></div><h2 className="mt-2 text-base font-bold text-text-strong">{source.label}</h2><p className="mt-1 text-xs text-text-muted">Authority: {source.authority}</p></div><a href={source.endpoint} target="_blank" rel="noreferrer" className="inline-flex min-h-10 max-w-full items-center gap-2 rounded-md border border-border bg-surface-2 px-3 font-mono text-[8px] text-gov-primary hover:bg-white"><span className="truncate">Open authority endpoint</span><ExternalLink className="size-3.5 shrink-0" aria-hidden /></a></div><div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"><Fact icon={KeyRound} label="Access and lifecycle" value="Public authority endpoint; monitor terms, schema, availability, and deprecation. No Compass commercial seat is asserted." /><Fact icon={Clock3} label="Responsible cadence" value={formatCadence(source.cadence_seconds)} /><Fact icon={ShieldCheck} label="Accountability" value={`${run?.identity_summary?.governance_owner ?? "Portfolio Data Product Owner"} | ${run?.identity_summary?.governance_steward ?? "Public Evidence Data Steward"}`} /><Fact icon={Database} label="Downstream use" value={`${source.data_kind}. ${source.model_use}`} /></div><div className="mt-4 flex flex-wrap items-center gap-2 text-[9px] text-text-muted"><span>Latest accepted: <strong className="text-text-strong">{source.last_accepted_at ? new Date(source.last_accepted_at).toLocaleString() : "Awaiting first run"}</strong></span><span>|</span><span>Run: <code className="font-mono text-text-strong">{run?.run_id ?? source.latest_run_id ?? "not available"}</code></span>{run ? <Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="ml-auto inline-flex min-h-9 items-center gap-1.5 font-bold text-gov-primary hover:underline">Trace source product <ArrowRight className="size-3" aria-hidden /></Link> : null}</div></article>;
        })}
      </section>
      <p className="rounded-lg border border-info/25 bg-info-soft/35 p-4 text-xs leading-5 text-text-muted">A Government deployment must validate each authority's terms, approved network path, retention policy, records schedule, accessibility, schema-change process, and mission owner before operational use. This page proves the product contract and deployed public-source health, not legal approval for an operational environment.</p>
    </div>
  );
}

function GovernanceMetric({ icon: Icon, label, value, detail }: { icon: typeof RadioTower; label: string; value: string; detail: string }) { return <article className="rounded-xl border border-border bg-white p-4 shadow-soft"><Icon className="size-5 text-gov-primary" aria-hidden /><p className="mt-3 text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 font-mono text-2xl font-bold text-text-strong">{value}</p><p className="mt-1 text-[9px] text-text-muted">{detail}</p></article>; }
function Fact({ icon: Icon, label, value }: { icon: typeof KeyRound; label: string; value: string }) { return <div className="rounded-lg border border-border bg-surface-2 p-3"><Icon className="size-4 text-gov-primary" aria-hidden /><p className="mt-2 text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 text-[9px] leading-4 text-text-muted">{value}</p></div>; }
function formatCadence(seconds: number): string { if (seconds >= 3600 && seconds % 3600 === 0) return `Every ${seconds / 3600} hour${seconds === 3600 ? "" : "s"}`; if (seconds >= 60 && seconds % 60 === 0) return `Every ${seconds / 60} minute${seconds === 60 ? "" : "s"}`; return `Every ${seconds} seconds`; }

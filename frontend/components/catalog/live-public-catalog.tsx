"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Database,
  ExternalLink,
  FileSearch,
  Fingerprint,
  Search,
} from "lucide-react";

import { LiveEvidenceStatus } from "@/components/public-intelligence/live-evidence-status";
import {
  publicRecordTitle,
  publicSourceLabel,
} from "@/lib/public-intelligence/operations";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";

export function LivePublicCatalog() {
  const operations = usePublicOperations();
  const [query, setQuery] = useState("");
  const [sourceId, setSourceId] = useState("all");
  const health = operations.data?.source_health ?? [];
  const records = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return operations.summary.records.filter(({ run, record, prediction }) => {
      if (sourceId !== "all" && run.source_id !== sourceId) return false;
      if (!needle) return true;
      return [
        run.source_label,
        run.source_id,
        record.source_record_id,
        record.title,
        record.description,
        record.recipient_name,
        record.record_type,
        prediction?.document_class,
        ...(record.topics ?? []),
        ...(record.award_ids ?? []),
      ].some((value) => String(value ?? "").toLowerCase().includes(needle));
    });
  }, [operations.summary.records, query, sourceId]);

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

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Catalog summary">
        <CatalogMetric label="Accepted source datasets" value={operations.summary.latest.length} detail="Latest immutable page per authority" />
        <CatalogMetric label="Accepted records" value={operations.summary.acceptedRecords} detail="Counted from current source receipts" />
        <CatalogMetric label="Identity-linked previews" value={operations.summary.records.filter((item) => (item.record.identity_keys ?? []).length > 0).length} detail="Exact award, DOI, or recipient keys" />
        <CatalogMetric label="Model-classified records" value={operations.summary.classifiedRecords} detail="Real champion classifier receipts" />
      </section>

      <section className="rounded-xl border border-border bg-white shadow-card">
        <div className="border-b border-border p-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">Governed source products</p>
              <h2 className="mt-1 text-lg font-bold text-text-strong">Latest accepted snapshot from each authority with a receipt</h2>
              <p className="mt-1 text-xs leading-5 text-text-muted">Expand a source to see its raw and canonical receipt hashes, model version, change set, owner, steward, and exact records.</p>
            </div>
            <Link href="/admin/lineage/" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-gov-primary/25 px-3 text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter">Open lineage explorer <ArrowRight className="size-3.5" aria-hidden /></Link>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-[minmax(0,1fr)_280px]">
            <label className="relative block"><span className="sr-only">Search public catalog</span><Search className="pointer-events-none absolute left-3 top-3.5 size-4 text-text-subtle" aria-hidden /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search record, award, DOI, recipient, class..." className="min-h-11 w-full rounded-md border border-border bg-white pl-10 pr-3 text-xs text-text-strong" /></label>
            <label><span className="sr-only">Filter by source</span><select value={sourceId} onChange={(event) => setSourceId(event.target.value)} className="min-h-11 w-full rounded-md border border-border bg-white px-3 text-xs font-bold text-text-strong"><option value="all">All named authorities</option>{operations.summary.latest.map((run) => <option key={run.source_id} value={run.source_id}>{publicSourceLabel(run)}</option>)}</select></label>
          </div>
        </div>

        <div className="space-y-3 bg-bg p-4">
          {operations.summary.latest.map((run) => {
            const sourceRecords = records.filter((item) => item.run.run_id === run.run_id);
            if (sourceId !== "all" && run.source_id !== sourceId) return null;
            if (query.trim() && sourceRecords.length === 0) return null;
            return (
              <details key={run.run_id} className="group overflow-hidden rounded-xl border border-border bg-white shadow-soft" open={operations.summary.latest.length <= 2}>
                <summary className="flex min-h-16 cursor-pointer list-none flex-wrap items-center gap-4 px-4 py-3 [&::-webkit-details-marker]:hidden">
                  <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-gov-primary text-white"><Database className="size-4.5" aria-hidden /></span>
                  <div className="min-w-[220px] flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-bold text-text-strong">{publicSourceLabel(run)}</h3><span className="rounded-full border border-success/30 bg-success-soft px-2 py-1 text-[8px] font-bold uppercase text-success">Live public</span></div><p className="mt-1 font-mono text-[8px] text-text-subtle">{run.run_id}</p></div>
                  <div className="grid grid-cols-3 gap-2 text-center"><HeaderFact label="Rows" value={(run.record_count ?? 0).toLocaleString("en-US")} /><HeaderFact label="Changed" value={((run.added_records ?? 0) + (run.changed_records ?? 0)).toLocaleString("en-US")} /><HeaderFact label="Review" value={(run.review_flag_count ?? 0).toLocaleString("en-US")} /></div>
                  <span className="rounded-full border border-border bg-surface-2 px-3 py-1.5 text-[9px] font-bold text-text-muted group-open:hidden">Open evidence</span><span className="hidden rounded-full border border-border bg-surface-2 px-3 py-1.5 text-[9px] font-bold text-text-muted group-open:inline">Close evidence</span>
                </summary>
                <div className="border-t border-border bg-surface-2 p-4">
                  <div className="grid gap-3 lg:grid-cols-3">
                    <EvidenceFact icon={Fingerprint} label="Snapshot SHA-256" value={run.snapshot_sha256 ?? "Retained in run receipt"} mono />
                    <EvidenceFact icon={BadgeCheck} label="Model execution" value={run.classification_summary ? `${run.classification_summary.model_version} | ${Math.round(run.classification_summary.mean_confidence * 100)}% mean confidence` : run.classification_status ?? "Not configured"} />
                    <EvidenceFact icon={Database} label="Governance" value={`${run.identity_summary?.governance_owner ?? "Portfolio Data Product Owner"} | ${run.identity_summary?.governance_steward ?? "Public Evidence Data Steward"}`} />
                  </div>
                  <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-white">
                    <table className="min-w-full text-left"><thead className="border-b border-border bg-surface-2 text-[8px] font-bold uppercase tracking-wide text-text-subtle"><tr><th className="px-3 py-2.5">Record</th><th className="px-3 py-2.5">Identity</th><th className="px-3 py-2.5">Model class</th><th className="px-3 py-2.5">State</th><th className="px-3 py-2.5">Proof</th></tr></thead><tbody className="divide-y divide-border">{sourceRecords.map(({ record, prediction, flagged }) => <tr key={record.source_record_id} className="align-top text-[10px]"><td className="max-w-md px-3 py-3"><p className="font-bold text-text-strong">{publicRecordTitle(record)}</p><p className="mt-1 line-clamp-2 text-[8.5px] leading-4 text-text-muted">{record.description ?? record.record_type?.replaceAll("_", " ")}</p><p className="mt-1 font-mono text-[8px] text-text-subtle">{record.source_record_id}</p></td><td className="px-3 py-3"><div className="flex max-w-xs flex-wrap gap-1">{(record.identity_keys ?? []).map((key) => <span key={key} className="rounded border border-success/25 bg-success-soft px-1.5 py-1 font-mono text-[7px] text-success">{key}</span>)}{(record.identity_keys ?? []).length === 0 ? <span className="text-text-subtle">Source key only</span> : null}</div></td><td className="px-3 py-3"><p className="font-bold text-text-strong">{prediction?.document_class.replaceAll("_", " ") ?? (run.classification_summary ? "Full artifact result" : "Not classified")}</p>{prediction ? <p className="mt-1 text-[8px] text-text-muted">{Math.round(prediction.confidence * 100)}% confidence</p> : null}</td><td className="px-3 py-3"><span className={`rounded-full border px-2 py-1 text-[7px] font-bold uppercase ${flagged ? "border-warn/30 bg-warn-soft text-warn" : "border-success/30 bg-success-soft text-success"}`}>{flagged ? "Review" : "Current"}</span></td><td className="px-3 py-3"><div className="flex gap-1">{record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer" className="grid size-8 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Open source ${record.source_record_id}`}><ExternalLink className="size-3" aria-hidden /></a> : null}{record.document_url ? <a href={record.document_url} target="_blank" rel="noreferrer" className="grid size-8 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Open document ${record.source_record_id}`}><FileSearch className="size-3" aria-hidden /></a> : null}<Link href={`/admin/lineage/?run=${encodeURIComponent(run.run_id)}`} className="grid size-8 place-items-center rounded-md border border-border text-gov-primary" aria-label={`Trace ${record.source_record_id}`}><ArrowRight className="size-3" aria-hidden /></Link></div></td></tr>)}</tbody></table>
                    {sourceRecords.length === 0 ? <div className="p-4 text-center text-xs text-text-muted">No retained preview record matches the current filter.</div> : null}
                  </div>
                </div>
              </details>
            );
          })}
          {!operations.loading && operations.summary.latest.length === 0 ? <div className="rounded-xl border border-dashed border-border bg-white p-8 text-center"><AlertTriangle className="mx-auto size-6 text-warn" aria-hidden /><p className="mt-3 text-sm font-bold text-text-strong">No accepted public snapshot is available</p><p className="mt-1 text-xs text-text-muted">Open Ingestion to inspect continuous source health or run a named source now.</p></div> : null}
        </div>
      </section>
    </div>
  );
}

function CatalogMetric({ label, value, detail }: { label: string; value: number; detail: string }) { return <article className="rounded-xl border border-border bg-white p-4 shadow-soft"><p className="text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 font-mono text-2xl font-bold text-text-strong">{value.toLocaleString("en-US")}</p><p className="mt-1 text-[9px] leading-4 text-text-muted">{detail}</p></article>; }
function HeaderFact({ label, value }: { label: string; value: string }) { return <div className="min-w-16"><p className="text-[7px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 text-xs font-bold text-text-strong">{value}</p></div>; }
function EvidenceFact({ icon: Icon, label, value, mono = false }: { icon: typeof Database; label: string; value: string; mono?: boolean }) { return <div className="rounded-lg border border-border bg-white p-3"><Icon className="size-4 text-gov-primary" aria-hidden /><p className="mt-2 text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className={`mt-1 break-all text-[9px] leading-4 text-text-strong ${mono ? "font-mono" : "font-semibold"}`}>{value}</p></div>; }

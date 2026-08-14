"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  Database,
  Download,
  FileJson2,
  FileSpreadsheet,
  GitBranch,
  ShieldCheck,
} from "lucide-react";

import { LiveEvidenceStatus } from "@/components/public-intelligence/live-evidence-status";
import { PageHeader } from "@/components/shell/page-header";
import {
  publicRecordTitle,
  publicSourceLabel,
} from "@/lib/public-intelligence/operations";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";
import {
  buildBrowserPortablePreview,
  portablePreviewCsv,
} from "./live-public-release-model";

type ReleaseFormat = "json" | "csv";

export function LivePublicRelease() {
  const operations = usePublicOperations();
  const [format, setFormat] = useState<ReleaseFormat>("json");
  const [preview, setPreview] = useState<{ file: string; sha256: string; rows: number } | null>(null);
  const rows = useMemo(() => operations.summary.records.map(({ run, record, prediction, flagged }) => ({
    source_id: run.source_id,
    source_label: publicSourceLabel(run),
    acquisition_run_id: run.run_id,
    acquisition_snapshot_sha256: run.snapshot_sha256 ?? null,
    captured_at: run.updated_at,
    source_record_id: record.source_record_id,
    record_type: record.record_type ?? null,
    title: publicRecordTitle(record),
    description: record.description ?? null,
    recipient_name: record.recipient_name ?? null,
    award_amount_usd: record.award_amount_usd ?? null,
    published_date: record.published_date ?? null,
    source_url: record.source_url ?? null,
    identity_keys: record.identity_keys ?? [],
    model_run_id: run.classification_summary?.run_id ?? null,
    model_version: run.classification_summary?.model_version ?? null,
    document_class: prediction?.document_class ?? null,
    confidence: prediction?.confidence ?? null,
    analyst_review_required: flagged,
  })), [operations.summary.records]);

  async function createPreview() {
    const generatedAt = new Date().toISOString();
    const manifest = buildBrowserPortablePreview(rows, operations.summary.latest, generatedAt);
    const body = format === "json" ? JSON.stringify(manifest, null, 2) : portablePreviewCsv(rows);
    const digest = await sha256(body);
    const stamp = generatedAt.replaceAll(":", "-").replaceAll(".", "-");
    const file = `compass-public-preview-${stamp}.${format}`;
    const blob = new Blob([body], { type: format === "json" ? "application/json" : "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = file;
    anchor.click();
    URL.revokeObjectURL(url);
    setPreview({ file, sha256: digest, rows: rows.length });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Live public evidence | Portable browser preview"
        title="Create a browser-generated portable preview"
        lead="Package the accepted public record previews already loaded on this screen as JSON or CSV. The browser computes the file and checksum locally. This action does not call the protected export API, make an approval decision, deliver a server object, or create an audit receipt."
        icon={<Download className="size-5" aria-hidden />}
      />

      <LiveEvidenceStatus
        control={operations.control}
        healthySources={operations.summary.healthySources}
        sourceCount={operations.data?.source_health?.length ?? 0}
        lastRefreshedAt={operations.lastRefreshedAt}
        refreshing={operations.refreshing}
        controlling={operations.controlling}
        error={operations.error}
        onRefresh={() => void operations.refresh()}
        onSetContinuous={(enabled) => void operations.setContinuous(enabled)}
      />

      <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-xl border border-border bg-white p-5 shadow-card">
          <p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">Current browser preview scope</p>
          <h2 className="mt-1 text-lg font-bold text-text-strong">What the browser will package</h2>
          <p className="mt-2 text-xs leading-5 text-text-muted">The file contains only the accepted bounded records currently visible from each authority. It includes portable origin and model-handling fields, but it is not a governed release object.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Metric icon={Database} label="Records" value={rows.length.toLocaleString("en-US")} />
            <Metric icon={GitBranch} label="Source runs" value={operations.summary.latest.length.toLocaleString("en-US")} />
            <Metric icon={ShieldCheck} label="Review flags" value={operations.summary.reviewFlags.toLocaleString("en-US")} />
          </div>
          <div className="mt-4 rounded-lg border border-info/25 bg-info-soft/40 p-4">
            <p className="text-xs font-bold text-text-strong">Browser preview contract</p>
            <ul className="mt-2 space-y-1 text-[10px] leading-5 text-text-muted">
              <li>Source record IDs and authority URLs remain intact.</li>
              <li>Acquisition run IDs and source snapshot SHA-256 values remain attached.</li>
              <li>Classifier run, version, class, confidence, and review requirement remain attached.</li>
              <li>No server policy, approval, delivery, audit, portfolio-completeness, or mission-success claim is added.</li>
            </ul>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-surface-2 p-5 shadow-card">
          <p className="text-[9px] font-bold uppercase tracking-wide text-gold-ink">Portable format</p>
          <h2 className="mt-1 text-lg font-bold text-text-strong">Create a local preview file</h2>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <FormatButton active={format === "json"} icon={FileJson2} label="JSON manifest" onClick={() => setFormat("json")} />
            <FormatButton active={format === "csv"} icon={FileSpreadsheet} label="CSV table" onClick={() => setFormat("csv")} />
          </div>
          <button type="button" onClick={() => void createPreview()} disabled={rows.length === 0} className="mt-4 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-gov-primary px-4 text-sm font-bold text-white hover:bg-gov-primary-dark disabled:cursor-not-allowed disabled:opacity-50"><Download className="size-4" aria-hidden /> Download browser preview</button>
          {preview ? <div className="mt-4 rounded-lg border border-success/30 bg-success-soft p-4"><p className="flex items-center gap-2 text-xs font-bold text-success"><CheckCircle2 className="size-4" aria-hidden /> Browser preview created</p><p className="mt-2 break-all font-mono text-[8px] text-text-muted">{preview.file}</p><p className="mt-1 break-all font-mono text-[8px] text-text-muted">Local SHA-256 {preview.sha256}</p><p className="mt-1 text-[9px] text-text-muted">{preview.rows.toLocaleString("en-US")} records | No server receipt</p></div> : null}
          <p className="mt-3 rounded-lg border border-warn/30 bg-warn-soft p-3 text-[10px] leading-5 text-warn">For a governed release, the protected export service must separately verify caller scope, apply approval policy, write audit evidence, deliver the object, and return a server receipt. None of those actions occur on this screen.</p>
          <Link href="/admin/lineage/" className="mt-4 inline-flex min-h-10 items-center gap-2 text-xs font-bold text-gov-primary hover:underline">Inspect operational lineage <ArrowRight className="size-3.5" aria-hidden /></Link>
        </div>
      </section>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Database; label: string; value: string }) {
  return <div className="rounded-lg border border-border bg-surface-2 p-3"><Icon className="size-4 text-gov-primary" aria-hidden /><p className="mt-2 text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 font-mono text-xl font-bold text-text-strong">{value}</p></div>;
}

function FormatButton({ active, icon: Icon, label, onClick }: { active: boolean; icon: typeof FileJson2; label: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} aria-pressed={active} className={`flex min-h-20 flex-col items-center justify-center gap-2 rounded-lg border text-xs font-bold ${active ? "border-gov-primary bg-gov-primary-lighter text-gov-primary" : "border-border bg-white text-text-muted hover:bg-surface-2"}`}><Icon className="size-5" aria-hidden /> {label}</button>;
}

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

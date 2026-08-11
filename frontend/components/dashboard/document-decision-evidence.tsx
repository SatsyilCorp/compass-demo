"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BadgeCheck,
  FileSearch,
  Fingerprint,
  Network,
  UserCheck,
} from "lucide-react";

import {
  readDocumentEvidence,
  subscribeDocumentEvidence,
} from "@/lib/documents/document-evidence-store";
import type { LocalDocumentReceipt } from "@/lib/documents/document-intake";

export function DocumentDecisionEvidence() {
  const [receipt, setReceipt] = useState<LocalDocumentReceipt | null>(null);

  useEffect(() => {
    const load = () => setReceipt(readDocumentEvidence());
    load();
    return subscribeDocumentEvidence(load);
  }, []);

  if (!receipt) return null;
  const classification = receipt.classification;

  return (
    <section className="overflow-hidden rounded-lg border border-info/25 bg-surface shadow-card" aria-labelledby="document-evidence-title">
      <header className="flex flex-col gap-3 border-b border-border bg-info-soft/65 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-info">Active dropped-document evidence</p>
          <h2 id="document-evidence-title" className="mt-1 text-lg font-bold text-text-strong">{receipt.fileName}</h2>
        </div>
        <Link href="/ingest/" className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-info/25 bg-white px-3 text-xs font-bold text-info hover:bg-info-soft">Open intake lineage <ArrowRight className="size-3.5" aria-hidden /></Link>
      </header>
      <div className="grid md:grid-cols-4">
        <EvidenceCell icon={FileSearch} label="Classification" value={classification.displayLabel} detail="Champion model operational label" />
        <EvidenceCell icon={BadgeCheck} label="Confidence" value={`${Math.round(classification.confidence * 100)}%`} detail={classification.reviewRequired ? "Below auto-accept threshold" : "Meets auto-accept threshold"} />
        <EvidenceCell icon={UserCheck} label="Disposition" value={classification.reviewRequired ? "Human review" : "Auto accepted"} detail="Policy-controlled workflow state" />
        <EvidenceCell icon={Network} label="Lineage" value="8 stages" detail="Source through governed Gold output" />
      </div>
      <div className="flex min-w-0 items-center gap-2 border-t border-border bg-surface-2 px-5 py-3"><Fingerprint className="size-3.5 shrink-0 text-gov-primary" aria-hidden /><span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">Source SHA-256</span><code className="min-w-0 truncate text-[9px] text-text-muted" title={receipt.sha256}>{receipt.sha256}</code></div>
    </section>
  );
}

function EvidenceCell({ icon: Icon, label, value, detail }: { icon: typeof FileSearch; label: string; value: string; detail: string }) {
  return <article className="border-t border-border p-4 first:border-t-0 md:border-l md:border-t-0 md:first:border-l-0"><Icon className="size-4 text-gov-primary" aria-hidden /><p className="mt-3 text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 text-sm font-bold text-text-strong">{value}</p><p className="mt-1 text-[10px] leading-4 text-text-muted">{detail}</p></article>;
}

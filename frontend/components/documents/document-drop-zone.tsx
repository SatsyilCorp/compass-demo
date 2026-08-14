"use client";

import { useCallback, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  FileArchive,
  FileSearch,
  FileSpreadsheet,
  FileText,
  Fingerprint,
  Loader2,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  type LucideIcon,
} from "lucide-react";

import {
  getDocumentRunApi,
  postDocumentUploadApi,
  putDocumentBytesApi,
  type DocumentRunRecord,
} from "@/lib/api";
import {
  DOCUMENT_MEDIA_TYPES,
  buildLiveFileIdentityReceipt,
  buildLocalReceipt,
  liveDocumentStageIndex,
  mediaTypeForFile,
  previewTextForBytes,
  sha256Hex,
  validateDocument,
  type DocumentIdentityReceipt,
  type LocalDocumentReceipt,
} from "@/lib/documents/document-intake";
import { saveDocumentEvidence } from "@/lib/documents/document-evidence-store";
import {
  bindingFromUploadPlan,
  type LiveDocumentBinding,
} from "@/lib/documents/live-contract";

const ACCEPT = ".pdf,.docx,.txt,.md,.csv,.json,.jsonl,.xlsx,.xml";
const TERMINAL = new Set(["completed", "curated", "quarantined", "failed"]);

const SAMPLE_DOCUMENTS = [
  { fileName: "onr-public-opportunity.json", label: "Public ONR opportunity", contentType: DOCUMENT_MEDIA_TYPES.json, boundary: "public" },
  { fileName: "technical-report.txt", label: "Technical report", contentType: DOCUMENT_MEDIA_TYPES.txt, boundary: "synthetic-demo" },
  { fileName: "grant-abstract.json", label: "Grant abstract", contentType: DOCUMENT_MEDIA_TYPES.json, boundary: "synthetic-demo" },
  { fileName: "financial-execution.csv", label: "Financial CSV", contentType: DOCUMENT_MEDIA_TYPES.csv, boundary: "synthetic-demo" },
  { fileName: "patent-summary.md", label: "Patent summary", contentType: DOCUMENT_MEDIA_TYPES.md, boundary: "synthetic-demo" },
  { fileName: "investment-brief.txt", label: "Investment brief", contentType: DOCUMENT_MEDIA_TYPES.txt, boundary: "synthetic-demo" },
  { fileName: "publication-summary.json", label: "Publication summary", contentType: DOCUMENT_MEDIA_TYPES.json, boundary: "synthetic-demo" },
  { fileName: "quarantine-short.txt", label: "Quarantine case", contentType: DOCUMENT_MEDIA_TYPES.txt, boundary: "synthetic-demo" },
] as const;

type WorkState = "idle" | "reading" | "running" | "complete" | "quarantined" | "failed";
type InputBoundary = "synthetic-demo" | "public";

export function DocumentDropZone({ mode = "live-public" }: { mode?: "live-public" | "rehearsal" }) {
  const rehearsal = mode === "rehearsal";
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<WorkState>("idle");
  const [receipt, setReceipt] = useState<DocumentIdentityReceipt | null>(null);
  const [activeStage, setActiveStage] = useState(-1);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [liveRun, setLiveRun] = useState<DocumentRunRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sampleLoading, setSampleLoading] = useState<string | null>(null);
  const [boundary, setBoundary] = useState<InputBoundary>(mode === "rehearsal" ? "synthetic-demo" : "public");
  const availableSamples = SAMPLE_DOCUMENTS.filter((sample) => (
    mode === "rehearsal" ? sample.boundary === "synthetic-demo" : sample.boundary === "public"
  ));

  const reset = useCallback(() => {
    if (pollRef.current) clearTimeout(pollRef.current);
    pollRef.current = null;
    if (inputRef.current) inputRef.current.value = "";
    setReceipt(null);
    setActiveStage(-1);
    setLiveStatus(null);
    setLiveRun(null);
    setError(null);
    setState("idle");
  }, []);

  const animateReplay = useCallback((nextReceipt: LocalDocumentReceipt) => {
    setState("running");
    let index = 0;
    setActiveStage(0);
    const tick = () => {
      index += 1;
      if (index >= nextReceipt.stages.length) {
        setActiveStage(nextReceipt.stages.length - 1);
        setState("complete");
        return;
      }
      setActiveStage(index);
      pollRef.current = setTimeout(tick, 260);
    };
    pollRef.current = setTimeout(tick, 260);
  }, []);

  const pollLiveRun = useCallback(async (
    runId: string,
    binding: LiveDocumentBinding,
    attempt = 0,
  ) => {
    try {
      const run = await getDocumentRunApi(runId, binding);
      setLiveRun(run);
      setLiveStatus(`${run.status} | ${run.stage}`);
      setActiveStage(liveDocumentStageIndex(run.stage, run.status));
      if (TERMINAL.has(run.status)) {
        setState(run.status === "failed" ? "failed" : run.status === "quarantined" ? "quarantined" : "complete");
        return;
      }
      if (attempt < 24) pollRef.current = setTimeout(() => void pollLiveRun(runId, binding, attempt + 1), 1_500);
      else {
        setState("failed");
        setError("The upload succeeded, but the processing receipt did not reach a terminal state within the demo polling window.");
      }
    } catch {
      if (attempt < 4) pollRef.current = setTimeout(() => void pollLiveRun(runId, binding, attempt + 1), 1_500);
      else {
        setState("failed");
        setError("The protected run receipt could not be retrieved. The uploaded object remains hash-bound and can be reconciled from Mission Control.");
      }
    }
  }, []);

  const processFile = useCallback(async (file: File, requestedBoundary: InputBoundary = boundary) => {
    reset();
    const validation = validateDocument(file);
    if (validation) {
      setError(validation);
      setState("failed");
      return;
    }
    const mediaType = mediaTypeForFile(file.name, file.type);
    if (!mediaType) return;
    setState("reading");
    try {
      const bytes = await file.arrayBuffer();
      const sha256 = await sha256Hex(bytes);
      if (rehearsal) {
        const nextReceipt = buildLocalReceipt({
          fileName: file.name,
          mediaType,
          sizeBytes: file.size,
          sha256,
          previewText: previewTextForBytes(mediaType, bytes),
        });
        setReceipt(nextReceipt);
        saveDocumentEvidence(nextReceipt);
        animateReplay(nextReceipt);
        return;
      }

      setReceipt(buildLiveFileIdentityReceipt({
        fileName: file.name,
        mediaType,
        sizeBytes: file.size,
        sha256,
      }));

      setState("running");
      setActiveStage(0);
      const plan = await postDocumentUploadApi({
        filename: file.name,
        content_type: mediaType,
        size_bytes: file.size,
        source_sha256: sha256,
        synthetic_only: requestedBoundary === "synthetic-demo",
        data_classification: requestedBoundary,
        contains_cui: false,
        pii_minimized: requestedBoundary === "public",
      });
      setLiveStatus(`${plan.status} | ${plan.stage}`);
      setActiveStage(1);
      await putDocumentBytesApi(plan, bytes);
      setActiveStage(2);
      await pollLiveRun(plan.run_id, bindingFromUploadPlan(plan));
    } catch (cause) {
      setState("failed");
      setError(cause instanceof Error ? cause.message : "Document intake failed before a terminal receipt was created.");
    }
  }, [animateReplay, boundary, pollLiveRun, rehearsal, reset]);

  const loadSample = useCallback(async (sample: (typeof SAMPLE_DOCUMENTS)[number]) => {
    setSampleLoading(sample.fileName);
    setError(null);
    try {
      const response = await fetch(`/demo-documents/${sample.fileName}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`Prepared sample could not be loaded (${response.status}).`);
      const bytes = await response.arrayBuffer();
      setBoundary(sample.boundary);
      await processFile(new File([bytes], sample.fileName, { type: sample.contentType }), sample.boundary);
    } catch (cause) {
      setState("failed");
      setError(cause instanceof Error ? cause.message : "The prepared sample could not be loaded.");
    } finally {
      setSampleLoading(null);
    }
  }, [processFile]);

  const choose = () => inputRef.current?.click();
  const onFiles = (files: FileList | null) => {
    const selected = files?.item(0);
    if (selected) void processFile(selected, boundary);
  };

  return (
    <section className="mt-5 overflow-hidden rounded-xl border border-gov-primary/25 bg-surface shadow-card" aria-labelledby="document-intake-title">
      <div className="grid lg:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)]">
        <div className="border-b border-border p-5 lg:border-b-0 lg:border-r sm:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-gov-primary px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white">Element 3 of 7</span>
            <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${rehearsal ? "border-warn/30 bg-warn-soft text-warn" : "border-success/30 bg-success-soft text-success"}`}>
              {rehearsal ? "Explicit browser rehearsal" : "Live AWS event path"}
            </span>
          </div>
          <h2 id="document-intake-title" className="mt-3 text-xl font-bold text-text-strong">Drop a governed document</h2>
          <p className="mt-2 text-xs leading-5 text-text-muted">{mode === "rehearsal" ? "Select an explicitly synthetic file. Compass validates the boundary, computes its hash, lands the original, applies quality rules, classifies it, and publishes isolated rehearsal evidence." : "Select a PII-minimized public file from your computer. Compass validates the boundary, computes its hash, lands the original, applies quality rules, classifies it, and publishes governed public evidence."}</p>

          {mode === "rehearsal" ? <div className="mt-4 grid grid-cols-2 gap-2" aria-label="Document data boundary">
            {(["synthetic-demo", "public"] as const).map((value) => (
              <button key={value} type="button" onClick={() => setBoundary(value)} disabled={value === "public"} className={`min-h-11 rounded-md border px-3 text-xs font-bold ${boundary === value ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40"}`}>
                {value === "public" ? "Public, PII-minimized" : "Synthetic demo"}
              </button>
            ))}
          </div> : <div className="mt-4 flex items-start gap-2 rounded-lg border border-success/30 bg-success-soft p-3"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden /><div><p className="text-xs font-bold text-success">Public, PII-minimized boundary is active</p><p className="mt-1 text-[9px] leading-4 text-text-muted">Synthetic samples are available only from the separate rehearsal workspace.</p></div></div>}

          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            aria-label="Choose sanitized documents"
            className="sr-only"
            onChange={(event) => onFiles(event.currentTarget.files)}
          />
          <button
            type="button"
            onClick={choose}
            onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); setDragging(false); onFiles(event.dataTransfer.files); }}
            className={`mt-5 flex min-h-48 w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-5 py-8 text-center transition-all ${dragging ? "border-gold bg-gold-soft" : "border-gov-primary/30 bg-gov-primary-lighter/45 hover:border-gov-primary hover:bg-gov-primary-lighter"}`}
          >
            <span className="grid size-12 place-items-center rounded-xl bg-gov-primary text-white shadow-soft"><UploadCloud className="size-6" aria-hidden /></span>
            <span className="mt-4 text-sm font-bold text-text-strong">Drop one file here or browse</span>
            <span className="mt-1 text-[10.5px] leading-5 text-text-muted">PDF, DOCX, TXT, Markdown, CSV, JSON, JSONL, XLSX, or XML | 15 MiB maximum</span>
            <span className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-success/25 bg-success-soft px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-success"><ShieldCheck className="size-3" aria-hidden /> No CUI, no direct PII</span>
          </button>

          <div className="mt-4 rounded-lg border border-border bg-white p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">{mode === "rehearsal" ? "Prepared synthetic samples" : "Prepared public sample"}</p>
                <p className="mt-1 text-[10px] leading-4 text-text-muted">{mode === "rehearsal" ? "Select a clearly labeled synthetic fixture to rehearse the event path without mixing it into live public evidence." : "Send one PII-minimized public ONR opportunity record through the live AWS event path."}</p>
              </div>
              <FileText className="size-4 shrink-0 text-gov-primary" aria-hidden />
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {availableSamples.map((sample) => {
                const loading = sampleLoading === sample.fileName;
                return (
                  <button
                    key={sample.fileName}
                    type="button"
                    onClick={() => void loadSample(sample)}
                    disabled={sampleLoading !== null || state === "reading" || state === "running"}
                    className="inline-flex min-h-10 items-center justify-between gap-2 rounded-md border border-border bg-surface-2 px-3 text-left text-[10px] font-bold text-text-muted hover:border-gov-primary hover:bg-gov-primary-lighter hover:text-gov-primary disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span>{sample.label}</span>
                    {loading ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <ArrowRight className="size-3.5" aria-hidden />}
                  </button>
                );
              })}
            </div>
          </div>

          {error ? <div role="alert" className="mt-4 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft p-3 text-xs leading-5 text-danger"><AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /> {error}</div> : null}
          {receipt ? <ReceiptSummary receipt={receipt} liveStatus={liveStatus} liveRun={liveRun} rehearsal={rehearsal} /> : null}
          {state !== "idle" ? <button type="button" onClick={reset} className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-muted hover:bg-surface-2"><RotateCcw className="size-3.5" aria-hidden /> Reset intake</button> : null}
        </div>

        <div className="bg-surface-2 p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Visible processing evidence</p><h3 className="mt-1 text-lg font-bold text-text-strong">Source to governed intelligence</h3></div>
            <StatePill state={state} />
          </div>
          <div className="mt-5 space-y-2">
            {(rehearsal && receipt?.mode === "bounded_browser_replay" ? receipt.stages : PLACEHOLDER_STAGES).map((stage, index) => {
              const Icon = STAGE_ICONS[index] ?? FileSearch;
              const done = receipt && (index < activeStage || (state === "complete" && index === activeStage));
              const quarantined = receipt && index === activeStage && state === "quarantined";
              const active = receipt && index === activeStage && state !== "complete" && state !== "quarantined" && state !== "failed";
              return (
                <div key={stage.id} className={`relative flex gap-3 rounded-lg border p-3 transition-all ${quarantined ? "border-warn/35 bg-warn-soft" : active ? "border-gov-primary bg-white shadow-soft" : done ? "border-success/25 bg-success-soft/45" : "border-border bg-white/60"}`}>
                  <span className={`grid size-9 shrink-0 place-items-center rounded-md ${quarantined ? "bg-warn text-white" : done ? "bg-success text-white" : active ? "bg-gov-primary text-white" : "bg-surface-3 text-text-subtle"}`}>{quarantined ? <AlertTriangle className="size-4" aria-hidden /> : done ? <CheckCircle2 className="size-4" aria-hidden /> : active ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Icon className="size-4" aria-hidden />}</span>
                  <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold text-text-strong">{index + 1}. {stage.label}</p><span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{stage.system}</span></div><p className="mt-1 text-[10px] leading-4 text-text-muted">{stage.detail}</p></div>
                  {index < 7 ? <ArrowRight className="absolute -bottom-2.5 left-[27px] z-10 size-3 text-border-strong" aria-hidden /> : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

const PLACEHOLDER_STAGES = [
  { id: "hash", label: "Validate and hash", system: "Compass browser", detail: "Select a file to produce a SHA-256 bound receipt." },
  { id: "upload", label: "Land source", system: "S3 incoming", detail: "The original bytes remain immutable and replayable." },
  { id: "detect", label: "Detect event", system: "EventBridge", detail: "A source event starts the processing workflow." },
  { id: "bronze", label: "Retain Bronze", system: "S3 Bronze", detail: "Raw source and metadata are retained." },
  { id: "extract", label: "Extract and infer", system: "Document adapter", detail: "Text, fields, sheets, and schema variations are detected." },
  { id: "quality", label: "Apply quality gate", system: "Step Functions", detail: "Blocking failures quarantine the document." },
  { id: "classify", label: "Classify document", system: "Champion model", detail: "A registered classical model creates an operational label." },
  { id: "gold", label: "Publish Gold", system: "Governed catalog", detail: "Lineage, confidence, and review state become queryable." },
] as const;

const STAGE_ICONS: LucideIcon[] = [Fingerprint, UploadCloud, Sparkles, FileArchive, FileSearch, BadgeCheck, FileText, FileSpreadsheet];

function ReceiptSummary({ receipt, liveStatus, liveRun, rehearsal }: { receipt: DocumentIdentityReceipt; liveStatus: string | null; liveRun: DocumentRunRecord | null; rehearsal: boolean }) {
  const localResult = rehearsal && receipt.mode === "bounded_browser_replay" ? receipt.classification : null;
  const terminalLiveResult = !rehearsal && liveRun?.status === "completed" && typeof liveRun.document_class === "string";
  const displayClass = localResult ? localResult.displayLabel : terminalLiveResult ? String(liveRun.document_class).replaceAll("_", " ") : "Awaiting server result";
  const confidence = localResult ? localResult.confidence : terminalLiveResult && typeof liveRun.confidence === "number" ? liveRun.confidence : null;
  const reviewRequired = localResult ? localResult.reviewRequired : terminalLiveResult ? Boolean(liveRun.review_required) : true;
  return <div className="mt-4 rounded-lg border border-border bg-white p-3"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-xs font-bold text-text-strong">{receipt.fileName}</p><p className="mt-1 text-[9.5px] text-text-muted">{formatBytes(receipt.sizeBytes)} | {receipt.shape}</p></div><span className={`rounded-full border px-2 py-1 text-[9px] font-bold uppercase ${(terminalLiveResult || rehearsal) && !reviewRequired ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>{terminalLiveResult || rehearsal ? reviewRequired ? "Human review" : "Auto accepted" : "Processing"}</span></div><div className="mt-3 grid gap-2 sm:grid-cols-2"><Metric label="Predicted class" value={displayClass} /><Metric label="Confidence" value={confidence === null ? "Pending" : `${Math.round(confidence * 100)}%`} /></div><div className="mt-3 flex items-center gap-2 rounded-md bg-surface-2 px-2.5 py-2"><Fingerprint className="size-3.5 shrink-0 text-gov-primary" aria-hidden /><code className="truncate text-[9px] text-text-muted" title={receipt.sha256}>{receipt.sha256}</code></div>{liveStatus ? <p className="mt-2 text-[9.5px] font-semibold text-info">Live receipt: {liveStatus}</p> : null}{liveRun?.model_version ? <p className="mt-1 text-[9.5px] text-text-muted">Model version: <span className="font-mono">{liveRun.model_version}</span></p> : null}{liveRun?.run_id ? <a href={`/admin/lineage/?run=${encodeURIComponent(liveRun.run_id)}`} className="mt-2 inline-flex min-h-9 items-center gap-1 text-[10px] font-bold text-gov-primary hover:underline">Open authoritative stage lineage <ArrowRight className="size-3" aria-hidden /></a> : null}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md bg-surface-2 p-2"><p className="text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 text-[10px] font-bold text-text-strong">{value}</p></div>;
}

function StatePill({ state }: { state: WorkState }) {
  if (state === "complete") return <span className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success-soft px-2.5 py-1 text-[9px] font-bold uppercase text-success"><CheckCircle2 className="size-3" aria-hidden /> Complete</span>;
  if (state === "quarantined") return <span className="inline-flex items-center gap-1 rounded-full border border-warn/35 bg-warn-soft px-2.5 py-1 text-[9px] font-bold uppercase text-warn"><AlertTriangle className="size-3" aria-hidden /> Quarantined</span>;
  if (state === "failed") return <span className="rounded-full border border-danger/30 bg-danger-soft px-2.5 py-1 text-[9px] font-bold uppercase text-danger">Attention</span>;
  if (state === "reading" || state === "running") return <span className="inline-flex items-center gap-1 rounded-full border border-info/30 bg-info-soft px-2.5 py-1 text-[9px] font-bold uppercase text-info"><Loader2 className="size-3 animate-spin" aria-hidden /> Processing</span>;
  return <span className="rounded-full border border-border bg-white px-2.5 py-1 text-[9px] font-bold uppercase text-text-subtle">Ready</span>;
}

function formatBytes(value: number): string {
  if (value < 1_024) return `${value} B`;
  if (value < 1_048_576) return `${(value / 1_024).toFixed(1)} KiB`;
  return `${(value / 1_048_576).toFixed(1)} MiB`;
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  BadgeCheck,
  CheckCircle2,
  Clock3,
  CloudCog,
  Database,
  FileCheck2,
  Fingerprint,
  Loader2,
  LockKeyhole,
  Play,
  ReceiptText,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import {
  ApiError,
  getPublicModelExecutionApi,
  getPublicModelExecutionsApi,
  postPublicModelExecutionApi,
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import {
  isTerminalModelExecutionStatus,
  type PublicModelExecutionReceipt,
} from "@/lib/mlops/model-execution";

const POLL_INTERVAL_MS = 5_000;
const SAMPLE_SIZES = [4, 8, 16, 25] as const;

type RequestPhase = "idle" | "submitting" | "polling" | "terminal";

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError) {
    const body = cause.body;
    if (body && typeof body === "object") {
      const message = (body as { message?: unknown; error?: unknown }).message;
      const error = (body as { message?: unknown; error?: unknown }).error;
      if (typeof message === "string" && message.trim()) return message;
      if (typeof error === "string" && error.trim()) return error;
    }
    if (cause.message && !cause.message.startsWith("api_error_")) return cause.message;
    return `Protected execution request failed with HTTP ${cause.status}.`;
  }
  return cause instanceof Error ? cause.message : "The protected execution request failed.";
}

function activeExecutionId(cause: unknown): string | null {
  if (!(cause instanceof ApiError) || cause.status !== 409 || !cause.body || typeof cause.body !== "object") return null;
  const value = (cause.body as { executionId?: unknown }).executionId;
  return typeof value === "string" && value.trim() ? value : null;
}

function statusStyle(status: PublicModelExecutionReceipt["status"]): string {
  if (status === "COMPLETED") return "border-success/30 bg-success-soft text-success";
  if (status === "FAILED" || status === "STOPPED") return "border-danger/30 bg-danger-soft text-danger";
  return "border-info/30 bg-info-soft text-info";
}

export function ModelExecutionControl() {
  const auth = useAppAuth();
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  const [sampleSize, setSampleSize] = useState<number>(8);
  const [phase, setPhase] = useState<RequestPhase>("idle");
  const [receipt, setReceipt] = useState<PublicModelExecutionReceipt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sequenceRef = useRef(0);
  const hydratedRef = useRef(false);

  const clearPoll = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  useEffect(() => () => {
    sequenceRef.current += 1;
    clearPoll();
  }, [clearPoll]);

  const acceptReceipt = useCallback((next: PublicModelExecutionReceipt) => {
    setReceipt(next);
    setLastCheckedAt(new Date().toISOString());
    setPhase(isTerminalModelExecutionStatus(next.status) ? "terminal" : "polling");
  }, []);

  const pollExecution = useCallback(async function poll(
    executionId: string,
    sequence: number,
  ): Promise<void> {
    try {
      const next = await getPublicModelExecutionApi(executionId);
      if (sequence !== sequenceRef.current) return;
      acceptReceipt(next);
      setError(null);
      if (!isTerminalModelExecutionStatus(next.status)) {
        timerRef.current = setTimeout(() => void poll(executionId, sequence), POLL_INTERVAL_MS);
      }
    } catch (cause) {
      if (sequence !== sequenceRef.current) return;
      setError(`${errorMessage(cause)} The accepted receipt remains visible and can be rechecked.`);
      setPhase("terminal");
    }
  }, [acceptReceipt]);

  useEffect(() => {
    if (rehearsal || !auth.idToken || hydratedRef.current) return;
    hydratedRef.current = true;
    const sequence = ++sequenceRef.current;
    setPhase("polling");
    void getPublicModelExecutionsApi()
      .then((history) => {
        if (sequence !== sequenceRef.current) return;
        const latest = history.executions[0] ?? null;
        if (!latest) {
          setPhase("idle");
          return;
        }
        acceptReceipt(latest);
        if (!isTerminalModelExecutionStatus(latest.status)) {
          timerRef.current = setTimeout(
            () => void pollExecution(latest.executionId, sequence),
            POLL_INTERVAL_MS,
          );
        }
      })
      .catch((cause) => {
        if (sequence !== sequenceRef.current) return;
        setError(`${errorMessage(cause)} Durable execution history could not be loaded.`);
        setPhase("idle");
      });
  }, [acceptReceipt, auth.idToken, pollExecution, rehearsal]);

  const launch = useCallback(async () => {
    if (rehearsal || !auth.idToken || phase === "submitting" || phase === "polling") return;
    clearPoll();
    const sequence = ++sequenceRef.current;
    setReceipt(null);
    setError(null);
    setLastCheckedAt(null);
    setPhase("submitting");
    try {
      const next = await postPublicModelExecutionApi(sampleSize);
      if (sequence !== sequenceRef.current) return;
      acceptReceipt(next);
      if (!isTerminalModelExecutionStatus(next.status)) {
        timerRef.current = setTimeout(
          () => void pollExecution(next.executionId, sequence),
          POLL_INTERVAL_MS,
        );
      }
    } catch (cause) {
      if (sequence !== sequenceRef.current) return;
      const existingExecutionId = activeExecutionId(cause);
      if (existingExecutionId) {
        setError("Another bounded execution is already active. Compass is attaching to its observed receipt.");
        setPhase("polling");
        void pollExecution(existingExecutionId, sequence);
        return;
      }
      setError(errorMessage(cause));
      setPhase("idle");
    }
  }, [acceptReceipt, auth.idToken, clearPoll, phase, pollExecution, rehearsal, sampleSize]);

  const recheck = useCallback(() => {
    if (!receipt || rehearsal) return;
    clearPoll();
    const sequence = ++sequenceRef.current;
    setError(null);
    setPhase("polling");
    void pollExecution(receipt.executionId, sequence);
  }, [clearPoll, pollExecution, receipt, rehearsal]);

  const liveReady = !rehearsal && Boolean(auth.idToken) && auth.role === "poweruser";
  const canReadLive = !rehearsal && Boolean(auth.idToken);
  const active = phase === "submitting" || phase === "polling";

  return (
    <section className="overflow-hidden rounded-xl border border-gov-primary/25 bg-surface shadow-card" aria-labelledby="model-execution-title">
      <div className="border-b border-border bg-gov-primary px-5 py-5 text-white sm:px-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-gold-light">Real execution path</span>
              <span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-white/75">Current public cohort</span>
            </div>
            <h2 id="model-execution-title" className="mt-3 text-xl font-bold">Execute the registered candidate</h2>
            <p className="mt-2 text-xs leading-5 text-white/70">Start a protected SageMaker Batch Transform run over newer, label-excluded public Navy Phase I records that occur after the model evaluation cutoff. Follow the observed backend state through a hash-bound output and cost receipt. Predictions remain review-only and create no automatic approval decision.</p>
          </div>
          <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-[10px] leading-4 ${liveReady ? "border-success/30 bg-success/10 text-emerald-100" : "border-warn/30 bg-warn/10 text-amber-100"}`}>
            {liveReady ? <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden /> : <LockKeyhole className="mt-0.5 size-4 shrink-0" aria-hidden />}
            <span>{liveReady ? "Protected AWS execution API ready" : rehearsal ? "Rehearsal cannot claim cloud execution" : canReadLive ? "Viewer can inspect receipts but cannot start execution" : "Waiting for the protected session"}</span>
          </div>
        </div>
      </div>

      <div className="grid xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="border-b border-border p-5 xl:border-b-0 xl:border-r">
          <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Execution input</p>
          <h3 className="mt-1 text-base font-bold text-text-strong">Select a bounded sample</h3>
          <p className="mt-2 text-[11px] leading-5 text-text-muted">Only 1 to 25 records are accepted. Inputs are copied from a PII-minimized, label-excluded current public cohort and sealed before execution.</p>

          <fieldset className="mt-4">
            <legend className="sr-only">Public smoke-scoring sample size</legend>
            <div className="grid grid-cols-4 gap-2">
              {SAMPLE_SIZES.map((size) => (
                <label key={size} className={`grid min-h-11 cursor-pointer place-items-center rounded-md border text-xs font-bold ${sampleSize === size ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2"}`}>
                  <input
                    type="radio"
                    name="model-execution-sample-size"
                    value={size}
                    checked={sampleSize === size}
                    disabled={active}
                    onChange={() => setSampleSize(size)}
                    className="sr-only"
                  />
                  {size}
                </label>
              ))}
            </div>
          </fieldset>

          <button
            type="button"
            onClick={() => void launch()}
            disabled={!liveReady || active}
            className="mt-4 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white shadow-soft hover:bg-gov-primary-dark disabled:cursor-not-allowed disabled:opacity-45"
          >
            {active ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
            {phase === "submitting" ? "Submitting execution" : phase === "polling" ? "Following backend state" : "Execute candidate now"}
          </button>

          {!liveReady ? (
            <div className="mt-4 flex gap-2 rounded-md border border-warn/30 bg-warn-soft p-3 text-[10px] leading-5 text-warn">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>{rehearsal ? "The explicit rehearsal demonstrates UI behavior only. Select live public evidence to create an actual execution receipt." : canReadLive ? "Starting a bounded model execution requires the corporate poweruser role. Durable receipts remain readable here." : "Authentication must finish before this control can mutate AWS state."}</span>
            </div>
          ) : null}

          <div className="mt-4 rounded-lg border border-border bg-surface-2 p-3">
            <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wide text-text-subtle"><Database className="size-3.5" aria-hidden /> Candidate context</p>
            <p className="mt-2 text-xs font-bold text-text-strong">Registry evidence is not execution evidence</p>
            <p className="mt-1 text-[10px] leading-5 text-text-muted">A training job or registered package never changes this panel to executed. Only the protected execution contract can create the receipt shown here.</p>
          </div>
        </div>

        <div className="min-w-0 p-5 sm:p-6" aria-live="polite">
          {!receipt ? (
            <EmptyReceipt phase={phase} />
          ) : (
            <ExecutionReceipt
              receipt={receipt}
              polling={phase === "polling"}
              lastCheckedAt={lastCheckedAt}
              onRecheck={recheck}
            />
          )}
          {error ? (
            <div className="mt-4 flex gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-danger" role="alert">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              <p className="text-xs leading-5">{error}</p>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function EmptyReceipt({ phase }: { phase: RequestPhase }) {
  return (
    <div className="grid min-h-[300px] place-items-center rounded-lg border border-dashed border-border bg-surface-2/40 p-6 text-center">
      <div className="max-w-lg">
        {phase === "submitting" ? <Loader2 className="mx-auto size-8 animate-spin text-gov-primary" aria-hidden /> : <ReceiptText className="mx-auto size-8 text-gold-ink" aria-hidden />}
        <p className="mt-3 text-sm font-bold text-text-strong">{phase === "submitting" ? "Requesting a real execution" : "No execution receipt in this session"}</p>
        <p className="mt-2 text-xs leading-5 text-text-muted">{phase === "submitting" ? "Compass is waiting for the protected backend to accept or reject the request. No result is shown until its receipt passes contract validation." : "Choose a bounded sample and execute the candidate. Training, registry, replay, and architecture evidence are not counted as a model execution."}</p>
      </div>
    </div>
  );
}

function ExecutionReceipt({ receipt, polling, lastCheckedAt, onRecheck }: { receipt: PublicModelExecutionReceipt; polling: boolean; lastCheckedAt: string | null; onRecheck: () => void }) {
  const completed = receipt.status === "COMPLETED";
  return (
    <div>
      <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Observed backend receipt</p>
          <h3 className="mt-1 break-all font-mono text-sm font-bold text-text-strong">{receipt.executionId}</h3>
          <p className="mt-1 text-[10px] text-text-muted">Updated {formatDate(receipt.updatedAt)}{lastCheckedAt ? ` | checked ${formatDate(lastCheckedAt)}` : ""}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${statusStyle(receipt.status)}`}>{receipt.status.replaceAll("_", " ")}</span>
          {!polling ? <button type="button" onClick={onRecheck} className="grid size-11 place-items-center rounded-md border border-border bg-white text-gov-primary hover:bg-surface-2" aria-label="Recheck execution receipt"><RefreshCw className="size-4" aria-hidden /></button> : null}
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <Stage label="Request accepted" detail={formatDate(receipt.createdAt)} state="complete" />
        <Stage label="Batch transform" detail={receipt.execution.transformJobName ?? "Assignment pending"} state={receipt.status === "SUBMITTED" || receipt.status === "IN_PROGRESS" ? "active" : receipt.status === "FAILED" || receipt.status === "STOPPED" ? "failed" : "complete"} />
        <Stage label="Output sealed" detail={completed ? `${receipt.output?.predictionCount ?? 0} predictions` : receipt.status === "FAILED" || receipt.status === "STOPPED" ? "No completed output" : "Waiting for terminal receipt"} state={completed ? "complete" : receipt.status === "FAILED" || receipt.status === "STOPPED" ? "failed" : "pending"} />
      </div>

      <dl className="mt-4 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 xl:grid-cols-4">
        <ReceiptFact label="Mode" value="SageMaker Batch Transform" icon={CloudCog} />
        <ReceiptFact label="Input" value={`${receipt.input.recordCount} public records`} icon={FileCheck2} />
        <ReceiptFact label="Compute" value={`${receipt.execution.instanceCount} x ${receipt.execution.instanceType}`} icon={Clock3} />
        <ReceiptFact label="Network isolation" value={receipt.execution.networkIsolation ? "Enabled" : "Not reported enabled"} icon={ShieldCheck} />
      </dl>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <EvidenceBlock title="Model evidence" icon={BadgeCheck} rows={[
          ["Candidate", receipt.model.name],
          ["Package version", receipt.model.packageVersion],
          ["Approval", receipt.model.approvalStatus],
          ["Candidate only", receipt.model.candidateOnly ? "Yes" : "No"],
          ["Package ARN", receipt.model.packageArn],
          ["Training job ARN", receipt.model.trainingJobArn],
        ]} />
        <EvidenceBlock title="Execution provenance" icon={Fingerprint} rows={[
          ["Transform job ARN", receipt.execution.transformJobArn ?? "Not assigned yet"],
          ["Input SHA-256", receipt.input.sha256],
          ["Training-recorded artifact SHA-256", receipt.model.modelArtifactSha256],
          ["Runtime-verified bundle SHA-256", receipt.model.modelBundleSha256 ?? "Legacy receipt did not retain this field"],
          ["Model card SHA-256", receipt.model.modelCardSha256],
          ["Inference image digest", receipt.model.imageDigest],
          ["Pinned model object version", receipt.model.modelArtifactSourceVersionId ?? "Legacy receipt did not retain this field"],
          ["Per-run model object version", receipt.provenance?.executionModelVersionId ?? "Legacy receipt did not retain this field"],
          ["Temporary model cleanup", receipt.execution.temporaryModelCleanupStatus],
          ["Reconciliation guard", receipt.execution.reconciliationSchedule ?? "Legacy receipt did not retain this field"],
          ["Output SHA-256", receipt.output?.sha256 ?? "Not available until completion"],
          ["Receipt SHA-256", receipt.provenance?.receiptSha256 ?? "Not available until completion"],
        ]} />
      </div>

      {receipt.output ? <PredictionTable receipt={receipt} /> : null}

      {receipt.cost ? (
        <div className="mt-4 grid gap-3 rounded-lg border border-border bg-surface-2 p-4 sm:grid-cols-[1fr_auto_auto] sm:items-center">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Execution cost receipt</p>
            <p className="mt-1 text-[10px] leading-5 text-text-muted">Compute estimate from observed duration. It is not a billed AWS amount.</p>
          </div>
          <div><p className="text-[9px] font-bold uppercase text-text-subtle">Observed duration</p><p className="mt-1 text-sm font-bold text-text-strong">{receipt.cost.observedDurationSeconds === null ? "Unavailable" : `${receipt.cost.observedDurationSeconds.toFixed(1)} seconds`}</p></div>
          <div><p className="text-[9px] font-bold uppercase text-text-subtle">Estimated compute</p><p className="mt-1 text-sm font-bold text-text-strong">{receipt.cost.estimatedComputeUsd === null ? "Unavailable" : `$${receipt.cost.estimatedComputeUsd.toFixed(6)}`}</p></div>
        </div>
      ) : null}

      {receipt.failure ? (
        <div className="mt-4 flex gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-danger" role="alert">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div><p className="text-xs font-bold">{receipt.failure.code.replaceAll("_", " ")}</p><p className="mt-1 text-[10px] leading-5">{receipt.failure.message}</p></div>
        </div>
      ) : null}

      <div className="mt-4 flex gap-3 rounded-lg border border-warn/30 bg-warn-soft p-4 text-warn">
        <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <div>
          <p className="text-xs font-bold">Candidate output requires human review</p>
          <p className="mt-1 text-[10px] leading-5">{receipt.disclosure}</p>
        </div>
      </div>
    </div>
  );
}

function Stage({ label, detail, state }: { label: string; detail: string; state: "pending" | "active" | "complete" | "failed" }) {
  const Icon = state === "complete" ? CheckCircle2 : state === "active" ? Loader2 : state === "failed" ? AlertCircle : Clock3;
  const style = state === "complete" ? "border-success/25 bg-success-soft text-success" : state === "active" ? "border-info/25 bg-info-soft text-info" : state === "failed" ? "border-danger/25 bg-danger-soft text-danger" : "border-border bg-surface-2 text-text-muted";
  return <div className={`rounded-lg border p-3 ${style}`}><Icon className={`size-4 ${state === "active" ? "animate-spin" : ""}`} aria-hidden /><p className="mt-2 text-[10px] font-bold uppercase tracking-wide">{label}</p><p className="mt-1 truncate text-[10px] opacity-80" title={detail}>{detail}</p></div>;
}

function ReceiptFact({ label, value, icon: Icon }: { label: string; value: string; icon: typeof CloudCog }) {
  return <div className="bg-white p-3"><Icon className="size-4 text-gov-primary" aria-hidden /><dt className="mt-2 text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</dt><dd className="mt-1 break-words text-xs font-bold text-text-strong">{value}</dd></div>;
}

function EvidenceBlock({ title, icon: Icon, rows }: { title: string; icon: typeof BadgeCheck; rows: [string, string][] }) {
  return <section className="min-w-0 rounded-lg border border-border bg-white p-4"><div className="flex items-center gap-2"><Icon className="size-4 text-gov-primary" aria-hidden /><h4 className="text-xs font-bold text-text-strong">{title}</h4></div><dl className="mt-3 space-y-2">{rows.map(([label, value]) => <div key={label} className="grid gap-1 border-t border-border pt-2 first:border-t-0 first:pt-0 sm:grid-cols-[120px_minmax(0,1fr)]"><dt className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</dt><dd className="break-all font-mono text-[9px] leading-4 text-text-muted">{value}</dd></div>)}</dl></section>;
}

function PredictionTable({ receipt }: { receipt: PublicModelExecutionReceipt }) {
  const predictions = receipt.output?.predictions ?? [];
  const inputByRecord = new Map(receipt.input.records.map((item) => [item.recordId, item]));
  return <section className="mt-4 overflow-hidden rounded-lg border border-border"><div className="border-b border-border bg-surface-2 px-4 py-3"><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Observed candidate predictions</p><p className="mt-1 text-[10px] text-text-muted">Public transition proxy probabilities only. Every row remains review required.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] border-collapse text-left"><thead className="bg-white text-[9px] font-bold uppercase tracking-wide text-text-subtle"><tr><th className="px-4 py-3">Public award</th><th className="px-4 py-3">Phase I event</th><th className="px-4 py-3">Public transition probability</th><th className="px-4 py-3">Candidate label</th><th className="px-4 py-3">Review</th></tr></thead><tbody>{predictions.map((prediction) => { const input = inputByRecord.get(prediction.recordId); return <tr key={prediction.recordId} className="border-t border-border bg-white text-xs"><td className="px-4 py-3"><p className="font-mono text-[10px] font-bold text-gov-primary">{input?.sourceRecordIds[0] ?? prediction.recordId}</p><p className="mt-1 font-mono text-[9px] text-text-subtle">{prediction.recordId}</p></td><td className="px-4 py-3 text-[10px] text-text-muted">{input?.eventTime ? formatDate(input.eventTime) : "Recorded in receipt"}</td><td className="px-4 py-3 font-bold text-text-strong">{Math.round(prediction.observedPublicTransitionProbability * 100)}%</td><td className="px-4 py-3"><p className="font-bold text-text-strong">{prediction.candidateLabel === 1 ? "Positive proxy signal" : "No positive proxy signal"}</p><p className="mt-1 text-[9px] text-text-muted">{prediction.semantics}</p></td><td className="px-4 py-3"><span className="rounded-full border border-warn/30 bg-warn-soft px-2 py-1 text-[9px] font-bold uppercase text-warn">Required</span></td></tr>; })}</tbody></table></div></section>;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "medium" });
}

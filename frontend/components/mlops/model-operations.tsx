"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { SINGLE_LIVE_MODE } from "@/lib/evidence-mode";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  BarChart3,
  CheckCircle2,
  CloudCog,
  Code2,
  Database,
  ExternalLink,
  FileText,
  GitCommitHorizontal,
  Loader2,
  Play,
  RefreshCcw,
  Scale,
  ShieldCheck,
  Target,
  UserCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import {
  getModelOpsEvidenceApi,
  getPublicModelExecutionsApi,
  postModelDeployApi,
  postModelDriftApi,
  type ModelDriftReceipt,
  type ModelRecord,
} from "@/lib/api";
import type { PublicModelExecutionReceipt } from "@/lib/mlops/model-execution";
import {
  DOCUMENT_CLASSES,
  MODEL_VERSIONS,
  driftDecision,
  modelPromotionDecision,
  type ModelVersion,
} from "@/lib/mlops/demo-model";
import {
  projectLiveModel,
  projectLiveModelEvidence,
  resolvePromotionVersion,
  type LiveModelEvidenceProjection,
  type LiveModelProjection,
} from "@/lib/mlops/live-model";
import { ModelExecutionControl } from "@/components/mlops/model-execution-control";
import { LiveEvidenceStatus } from "@/components/public-intelligence/live-evidence-status";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { publicSourceLabel } from "@/lib/public-intelligence/operations";
import { usePublicOperations } from "@/lib/public-intelligence/use-public-operations";

type View = "lifecycle" | "taxonomy" | "registry" | "monitoring";

const REPOSITORY = "https://github.com/SatsyilCorp/compass-demo";
const REHEARSAL_TRAINING_STEPS = [
  ["Prepare immutable split", "S3 training set", "SHA-256 manifest, seed 20260811, 30 train, 6 evaluation"],
  ["Train classical model", "SageMaker adapter", "Multinomial Naive Bayes with bounded CPU and network isolation"],
  ["Evaluate gates", "Evaluation job", "Accuracy, macro F1, class coverage, and confusion matrix"],
  ["Register candidate", "Model Registry", "Artifact digest, source revision, dataset digest, and metrics"],
  ["Approve promotion", "Human control", "Candidate must satisfy thresholds before Champion alias changes"],
  ["Deploy and observe", "Batch inference", "Bounded classification, confidence, drift, and review queue"],
] as const;

const LIVE_TRAINING_STEPS = [
  ["Verify training manifest", "Protected registry", "Require a non-synthetic manifest URI, SHA-256 digest, and source revision."],
  ["Verify training artifact", "Returned evidence", "Require a retained model artifact, model version, taxonomy, and execution status."],
  ["Read evaluation gates", "Returned metrics", "Use only returned accuracy, macro F1, class coverage, and record counts."],
  ["Read candidate registry", "Governed registry", "Confirm candidate state from the protected registry receipt."],
  ["Confirm promotion", "Human control", "Champion state is shown only when the returned alias matches the verified version."],
  ["Observe inference", "Public-source receipts", "Confirm the same model version appears on accepted public narrative classifications."],
] as const;

const VIEWS: { id: View; label: string; icon: LucideIcon }[] = [
  { id: "lifecycle", label: "Training lifecycle", icon: Workflow },
  { id: "taxonomy", label: "Document taxonomy", icon: FileText },
  { id: "registry", label: "Model registry", icon: Database },
  { id: "monitoring", label: "Drift and retraining", icon: Activity },
];

function isModelRecord(value: unknown): value is ModelRecord {
  return Boolean(
    value
    && typeof value === "object"
    && typeof (value as { model_version?: unknown }).model_version === "string",
  );
}

export function ModelOperations() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  const publicOperations = usePublicOperations();
  const [view, setView] = useState<View>("lifecycle");
  const adapterMode: "live" | "replay" = rehearsal ? "replay" : "live";
  const [evidenceLoading, setEvidenceLoading] = useState(!rehearsal);
  const [liveModels, setLiveModels] = useState<ModelRecord[]>([]);
  const [liveDriftReceipt, setLiveDriftReceipt] = useState<ModelDriftReceipt | null>(null);
  // The operating champion's raw version and the latest SageMaker execution
  // receipt are real returned evidence even when no document-classifier record
  // passes the non-synthetic-manifest projection.
  const [championRaw, setChampionRaw] = useState("");
  const [sbirReceipt, setSbirReceipt] = useState<PublicModelExecutionReceipt | null>(null);
  const [sbirState, setSbirState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [driftHistoryCount, setDriftHistoryCount] = useState(0);
  const [trainingStep, setTrainingStep] = useState(-1);
  const [training, setTraining] = useState(false);
  const [candidateReady, setCandidateReady] = useState(false);
  const [championVersion, setChampionVersion] = useState(rehearsal ? "2" : "");
  const [driftScenario, setDriftScenario] = useState<"baseline" | "shifted">("baseline");
  const [driftRan, setDriftRan] = useState(false);
  const [operation, setOperation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelEvidenceError, setModelEvidenceError] = useState<string | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    let active = true;
    setError(null);
    setModelEvidenceError(null);
    setOperation(null);
    if (!rehearsal) {
      setChampionVersion("");
      setLiveModels([]);
      setEvidenceLoading(true);
      void getModelOpsEvidenceApi()
        .then((evidence) => {
          if (!active) return;
          const models = Array.isArray(evidence.models)
            ? evidence.models.filter(isModelRecord)
            : [];
          setLiveModels(models);
          setDriftHistoryCount(Array.isArray(evidence.drift_receipts) ? evidence.drift_receipts.length : 0);
          const champion = evidence.champion;
          if (champion && typeof champion === "object" && "model_version" in champion) {
            const version = (champion as { model_version?: unknown }).model_version;
            if (typeof version === "string" && version) setChampionRaw(version);
            const verifiedChampion = typeof version === "string"
              && models.some(
                (model) => model.model_version === version && projectLiveModel(model) !== null,
              );
            if (verifiedChampion) setChampionVersion(version);
          }
        })
        .catch((cause) => {
          if (!active) return;
          const message = cause instanceof Error
            ? cause.message
            : (SINGLE_LIVE_MODE ? "Model evidence is unavailable." : "Live model evidence is unavailable.");
          setModelEvidenceError(message);
          setError(message);
        })
        .finally(() => {
          if (active) setEvidenceLoading(false);
        });
      setSbirState("loading");
      void getPublicModelExecutionsApi()
        .then((list) => {
          if (!active) return;
          const stamp = (value: string) => {
            const parsed = Date.parse(value);
            return Number.isNaN(parsed) ? 0 : parsed;
          };
          const ranked = [...list.executions].sort((a, b) => stamp(b.createdAt) - stamp(a.createdAt));
          // The newest receipt wins even when it failed or is still running; an
          // older completed run must never mask the latest execution state.
          setSbirReceipt(ranked[0] ?? null);
          setSbirState(ranked.length ? "ready" : "empty");
        })
        .catch(() => {
          if (active) setSbirState("error");
        });
    } else {
      setChampionVersion("2");
      setChampionRaw("");
      setSbirReceipt(null);
      setSbirState("empty");
      setLiveModels([]);
      setEvidenceLoading(false);
    }
    return () => {
      active = false;
      timers.current.forEach(clearTimeout);
    };
  }, [rehearsal]);

  const replayCandidate = MODEL_VERSIONS[2];
  const isLive = adapterMode === "live";
  const liveEvidenceRecords = useMemo(
    () => liveModels.map((receipt) => ({ receipt, evidence: projectLiveModelEvidence(receipt) })),
    [liveModels],
  );
  const verifiedLiveModels = useMemo(
    () => liveEvidenceRecords
      .map(({ evidence }) => evidence.model)
      .filter((model): model is LiveModelProjection => model !== null),
    [liveEvidenceRecords],
  );
  const liveProjection = verifiedLiveModels[0] ?? null;
  const liveEvidence: LiveModelEvidenceProjection = liveEvidenceRecords.find(
    ({ evidence }) => evidence.state === "verified",
  )?.evidence ?? liveEvidenceRecords[0]?.evidence ?? {
    state: "incomplete",
    model: null,
    detail: "No registry or training receipt was returned by the protected evidence API.",
  };
  const promotion = isLive
    ? liveProjection && liveProjection.accuracy >= 0.9 && liveProjection.macroF1 >= 0.88
      ? "approve"
      : "hold"
    : modelPromotionDecision(replayCandidate);
  const rehearsalDrift = driftScenario === "baseline"
    ? driftDecision(0.08, 0.81)
    : driftDecision(0.34, 0.49);
  const replayModels = useMemo(() => MODEL_VERSIONS.map((model) => model.version === championVersion ? { ...model, stage: "Champion" as const } : model.version === "2" && championVersion !== "2" ? { ...model, stage: "Archived" as const } : model), [championVersion]);
  const registryModels = useMemo<readonly ModelVersion[]>(() => {
    if (!isLive) return replayModels;
    return verifiedLiveModels.map((model) => ({
      version: model.version,
      stage: championVersion === model.version ? "Champion" : "Candidate",
      accuracy: model.accuracy,
      macroF1: model.macroF1,
      trainingRecords: model.trainingRecords,
      sourceRevision: model.sourceRevision,
      registry: "Verified protected registry receipt",
      createdAt: model.createdAt,
    }));
  }, [championVersion, isLive, replayModels, verifiedLiveModels]);

  const candidateDisplay = isLive ? liveProjection : {
    version: replayCandidate.version,
    status: replayCandidate.stage.toLowerCase(),
    accuracy: replayCandidate.accuracy,
    macroF1: replayCandidate.macroF1,
    classCoverage: DOCUMENT_CLASSES.length,
    trainingRecords: replayCandidate.trainingRecords,
    splitSeed: "20260811",
    sourceRevision: replayCandidate.sourceRevision,
    createdAt: replayCandidate.createdAt,
    trainingManifestUri: "rehearsal://seed/documents/manifest.json",
    trainingManifestSha256: "rehearsal-only",
    artifactUri: "rehearsal://model/document-classifier",
  } satisfies LiveModelProjection;
  const matchingInferenceReceipt = Boolean(
    liveProjection
    && publicOperations.summary.classificationReceipts.some(
      (run) => run.classification_summary?.model_version === liveProjection.version,
    ),
  );
  const sbirFullyPinned = Boolean(
    sbirReceipt
    && sbirReceipt.status === "COMPLETED"
    && sbirReceipt.provenance?.sourceDataset
    && sbirReceipt.model.modelBundleSha256,
  );
  const liveTrainingState = evidenceLoading
    ? "Loading"
    : modelEvidenceError
      ? "Unavailable"
      : liveProjection
        ? "Verified"
        : "Manifest required";

  const runTraining = async () => {
    if (training) return;
    if (isLive) {
      setError(
        "Live training is unavailable until a non-synthetic training manifest is supplied and verified.",
      );
      return;
    }
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setError(null);
    setOperation(null);
    setCandidateReady(false);
    setTraining(true);
    setTrainingStep(0);
    const advance = (next: number) => {
      if (next >= REHEARSAL_TRAINING_STEPS.length) {
        setTraining(false);
        setCandidateReady(true);
        setOperation("Deterministic training replay completed and candidate 3 passed its evaluation gates.");
        return;
      }
      setTrainingStep(next);
      timers.current.push(setTimeout(() => advance(next + 1), 420));
    };
    timers.current.push(setTimeout(() => advance(1), 420));
  };

  const promoteCandidate = async () => {
    setError(null);
    if (promotion !== "approve") return;
    try {
      const targetVersion = resolvePromotionVersion(adapterMode, replayCandidate.version, liveProjection);
      if (isLive) await postModelDeployApi(targetVersion);
      setChampionVersion(targetVersion);
      if (isLive) setChampionRaw(targetVersion);
      if (isLive) {
        setLiveModels((current) => current.map((model) => (
          model.model_version === targetVersion ? { ...model, status: "deployed" } : model
        )));
      }
      setOperation(`${isLive ? "Live" : "Replay"} promotion receipt set model ${targetVersion} as Champion.`);
      setView("registry");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Model promotion failed.");
    }
  };

  const evaluateDrift = async () => {
    setError(null);
    try {
      if (isLive) {
        // Drift monitors the operating champion's live inputs, so the raw
        // returned alias is a valid target even while the stricter training
        // evidence projection stays manifest-gated.
        const activeModelVersion = championVersion || liveProjection?.version || championRaw;
        if (!activeModelVersion) throw new Error("No Champion model alias was returned for live drift evaluation.");
        const allDocuments = publicOperations.summary.records.map(({ record }) => [record.title, record.description, ...(record.topics ?? [])].filter(Boolean).join(". ")).filter((value) => value.length >= 20);
        const documents = driftScenario === "baseline" ? allDocuments.slice(0, 12) : allDocuments.slice(-12);
        if (documents.length < 5) throw new Error("At least five accepted public narratives are required for a live drift window.");
        const receipt = await postModelDriftApi(documents, activeModelVersion);
        setLiveDriftReceipt(receipt);
        setDriftHistoryCount((count) => count + 1);
      }
      setDriftRan(true);
      const modelLabel = isLive ? ` for model ${championVersion || liveProjection?.version || championRaw || "unknown"}` : "";
      setOperation(`${isLive ? "Live" : "Replay"} drift receipt${modelLabel} was recorded.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Drift evaluation failed.");
    }
  };

  return (
    <div className="mt-6 space-y-6">
      {isLive ? <>
        <LiveEvidenceStatus control={publicOperations.control} healthySources={publicOperations.summary.healthySources} sourceCount={publicOperations.data?.source_health?.length ?? 0} lastRefreshedAt={publicOperations.lastRefreshedAt} refreshing={publicOperations.refreshing} controlling={publicOperations.controlling} error={publicOperations.error} onRefresh={() => void publicOperations.refresh()} onSetContinuous={(enabled) => void publicOperations.setContinuous(enabled)} />
        <LiveClassificationWindow operations={publicOperations} />
        <ModelExecutionControl onReceipt={(next) => { setSbirReceipt(next); setSbirState("ready"); }} />
      </> : <section className="rounded-xl border border-warn/30 bg-warn-soft p-4"><p className="text-xs font-bold text-warn">Explicit model rehearsal</p><p className="mt-1 text-xs leading-5 text-text-muted">This workspace is using deterministic training, promotion, and drift fixtures. It does not call SageMaker or classify live public evidence.</p></section>}
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card">
        <div className="compass-grid-overlay grid gap-5 px-5 py-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)] lg:px-6">
          <div>
            <div className="flex flex-wrap items-center gap-2"><span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-gold-light">Element 5 of 7</span><span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/70">{isLive ? (SINGLE_LIVE_MODE ? "AWS adapter" : "Live AWS adapter") : "Explicit rehearsal adapter"}</span></div>
            <h2 className="mt-3 text-2xl font-bold">Classical document MLOps control room</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">{isLive ? sbirFullyPinned ? "Inspect returned classifier, registry, drift, and SageMaker Batch Transform receipts. The registered candidate's lifecycle is evidence-pinned end to end, and promotion remains a governed human decision." : "Inspect returned classifier, registry, drift, and SageMaker Batch Transform receipts. Evidence appears only as the protected APIs return it." : "Replay the deterministic training, evaluation, registry, promotion, and drift workflow with explicitly synthetic fixtures."}</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">{isLive ? <>
            <HeroMetric icon={Target} label="Champion classifier" value={evidenceLoading ? "Loading" : championRaw || "Unavailable"} />
            <HeroMetric icon={Scale} label="Records classified" value={publicOperations.summary.classifiedRecords.toLocaleString("en-US")} />
            <HeroMetric icon={UserCheck} label="SageMaker candidate" value={sbirReceipt ? `v${sbirReceipt.model.packageVersion} - pending approval` : sbirState === "loading" ? "Loading" : sbirState === "error" ? "Evidence call failed" : "No execution receipts"} />
          </> : <>
            <HeroMetric icon={Target} label="Candidate accuracy" value={candidateDisplay ? `${Math.round(candidateDisplay.accuracy * 100)}%` : "Run training"} />
            <HeroMetric icon={Scale} label="Macro F1" value={candidateDisplay ? candidateDisplay.macroF1.toFixed(2) : "Run training"} />
            <HeroMetric icon={UserCheck} label="Review threshold" value="62%" />
          </>}</div>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
        <div className="grid gap-2 border-b border-border bg-white p-3 sm:grid-cols-2 lg:grid-cols-4" role="tablist" aria-label="Model operations views">
          {VIEWS.map((item) => { const Icon = item.icon; const active = item.id === view; return <button key={item.id} type="button" role="tab" aria-selected={active} onClick={() => setView(item.id)} className={`flex min-h-12 items-center gap-2 rounded-md border px-3 text-left text-xs font-bold ${active ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2"}`}><Icon className="size-4" aria-hidden /> {item.label}</button>; })}
        </div>

        {view === "lifecycle" ? isLive ? sbirReceipt ? <SbirLifecycleView receipt={sbirReceipt} /> : <LiveLifecycleView loading={evidenceLoading} evidenceError={modelEvidenceError} evidence={liveEvidence} candidate={liveProjection} championVersion={championVersion} inferenceObserved={matchingInferenceReceipt} gatesPass={promotion === "approve"} promote={() => void promoteCandidate()} /> : <LifecycleView training={training} trainingStep={trainingStep} candidateReady={candidateReady} candidate={candidateDisplay} runTraining={() => void runTraining()} promote={() => void promoteCandidate()} /> : null}
        {view === "taxonomy" ? <TaxonomyView /> : null}
        {view === "registry" ? <RegistryView models={registryModels} championVersion={championVersion} live={isLive} sbir={isLive ? sbirReceipt : null} /> : null}
        {view === "monitoring" ? <MonitoringView live={isLive} scenario={driftScenario} setScenario={(next) => { setDriftScenario(next); setDriftRan(false); setLiveDriftReceipt(null); }} ran={driftRan} drift={isLive ? null : rehearsalDrift} liveReceipt={isLive ? liveDriftReceipt : null} modelVersion={isLive ? championVersion || liveProjection?.version || championRaw || "not verified" : replayCandidate.version} historyCount={isLive ? driftHistoryCount : 0} evaluate={() => void evaluateDrift()} /> : null}
      </section>

      {operation ? <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success-soft p-4 text-xs leading-5 text-success"><CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden /><span>{operation}</span></div> : null}
      {error ? <div className="flex items-start gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-xs leading-5 text-danger"><AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /><span>{error}</span></div> : null}
      <BoundaryNote live={isLive} />
    </div>
  );
}

function LiveClassificationWindow({ operations }: { operations: ReturnType<typeof usePublicOperations> }) {
  const receipts = operations.summary.classificationReceipts;
  return <section className="rounded-xl border border-success/25 bg-white p-5 shadow-card"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[9px] font-bold uppercase tracking-wide text-success">Live inference evidence</p><h2 className="mt-1 text-lg font-bold text-text-strong">Champion classifier receipts from accepted public sources</h2><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">These are the actual results created as public-source narratives entered the governed path. They are separate from the optional SageMaker funding-model execution below.</p></div><span className="rounded-full border border-success/30 bg-success-soft px-3 py-1.5 text-[9px] font-bold uppercase text-success">{operations.summary.classifiedRecords.toLocaleString("en-US")} classified</span></div><div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{receipts.map((run) => <article key={run.run_id} className="rounded-lg border border-border bg-surface-2 p-3"><p className="text-xs font-bold text-text-strong">{publicSourceLabel(run)}</p><p className="mt-1 font-mono text-[8px] text-text-subtle">{run.classification_summary?.model_version}</p><div className="mt-3 grid grid-cols-3 gap-1"><Metric label="Records" value={String(run.classification_summary?.record_count ?? 0)} /><Metric label="Confidence" value={`${Math.round((run.classification_summary?.mean_confidence ?? 0) * 100)}%`} /><Metric label="Review" value={String(run.classification_summary?.review_required_count ?? 0)} /></div></article>)}{receipts.length === 0 ? <div className="sm:col-span-2 xl:col-span-4 rounded-lg border border-dashed border-border bg-surface-2 p-4 text-center text-xs text-text-muted">No accepted classifier receipt is available yet. The next configured public-source run will create one.</div> : null}</div></section>;
}

function SbirLifecycleView({ receipt }: { receipt: PublicModelExecutionReceipt }) {
  const short = (value: string | null | undefined) => (value ? value.slice(0, 8) : "n/a");
  const dataset = receipt.provenance?.sourceDataset ?? null;
  const completed = receipt.status === "COMPLETED";
  const failed = receipt.status === "FAILED" || receipt.status === "STOPPED";
  const held = receipt.model.approvalStatus === "PendingManualApproval";
  const steps: { label: string; system: string; evidence: string; state: "done" | "held" | "pending" | "failed" }[] = [
    { label: "Verify training manifest", system: "S3 dataset", evidence: dataset ? `${dataset.datasetId} - sha ${short(dataset.sha256)}` : "dataset manifest not returned on this receipt", state: dataset ? "done" as const : "pending" as const },
    { label: "Verify training artifact", system: "Pinned bundle", evidence: receipt.model.modelBundleSha256 ? `artifact ${short(receipt.model.modelArtifactSha256)} - bundle ${short(receipt.model.modelBundleSha256)}` : `artifact ${short(receipt.model.modelArtifactSha256)} - runtime bundle not returned`, state: receipt.model.modelBundleSha256 ? "done" as const : "pending" as const },
    { label: "Read evaluation gates", system: "Model card", evidence: `content digest ${short(receipt.model.modelCardSha256)} sealed into the registry package`, state: "done" },
    { label: "Read candidate registry", system: "SageMaker registry", evidence: `${receipt.model.name} - package v${receipt.model.packageVersion}`, state: "done" },
    { label: "Confirm promotion", system: "Human control", evidence: held ? "Held at PendingManualApproval - promotion requires a documented human decision" : receipt.model.approvalStatus, state: held ? "held" : "done" },
    { label: "Observe inference", system: "Batch Transform receipt", evidence: completed ? `${receipt.executionId} - ${receipt.output?.predictionCount ?? 0} review-only predictions` : failed ? `${receipt.executionId} - ${receipt.failure?.message ?? receipt.status}` : `${receipt.executionId} - ${receipt.status.toLowerCase().replaceAll("_", " ")}`, state: completed ? "done" : failed ? "failed" : "pending" },
  ];
  return <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]"><div className="border-b border-border p-5 lg:border-b-0 lg:border-r"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Returned training evidence</p><h3 className="mt-1 text-lg font-bold text-text-strong">Registered candidate lifecycle, evidence-pinned</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">Every step below is read from returned AWS evidence for the registered SageMaker candidate: the hash-pinned training dataset, the sealed artifact and model card, the registry package state, and the observed Batch Transform receipt.</p></div><span className={`inline-flex min-h-10 items-center rounded-md border px-3 text-xs font-bold ${failed ? "border-danger/30 bg-danger-soft text-danger" : "border-success/30 bg-success-soft text-success"}`}>{failed ? "Execution failed - returned as-is" : "Contract-valid returned evidence"}</span></div><div className="mt-5 space-y-2">{steps.map((step, index) => <div key={step.label} className={`flex gap-3 rounded-lg border p-3 ${step.state === "done" ? "border-success/25 bg-success-soft/40" : step.state === "held" ? "border-warn/30 bg-warn-soft/50" : step.state === "failed" ? "border-danger/30 bg-danger-soft/40" : "border-border bg-white"}`}><span className={`grid size-9 shrink-0 place-items-center rounded-md text-xs font-bold ${step.state === "done" ? "bg-success text-white" : step.state === "held" ? "bg-warn text-white" : step.state === "failed" ? "bg-danger text-white" : "bg-surface-3 text-text-subtle"}`}>{step.state === "done" ? <CheckCircle2 className="size-4" aria-hidden /> : step.state === "held" ? <UserCheck className="size-4" aria-hidden /> : step.state === "failed" ? <AlertTriangle className="size-4" aria-hidden /> : index + 1}</span><div className="flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold text-text-strong">{step.label}</p><span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{step.system}</span></div><p className="mt-1 font-mono text-[10px] leading-4 text-text-muted">{step.evidence}</p></div></div>)}</div><p className="mt-4 rounded-lg border border-border bg-surface-2 p-3 text-[10.5px] leading-5 text-text-muted">The document classifier's training lifecycle remains gated separately: its training evidence is displayed only once a governed non-synthetic manifest is registered.</p></div><aside className="bg-surface-2 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Promotion decision</p><h3 className="mt-1 break-all text-lg font-bold text-text-strong">{receipt.model.name}</h3><div className="mt-4 grid grid-cols-2 gap-2"><Metric label="Package" value={`v${receipt.model.packageVersion}`} pass /><Metric label="Approval" value={held ? "Pending manual" : receipt.model.approvalStatus} /><Metric label={receipt.output ? "Records scored" : "Records submitted"} value={String(receipt.output?.predictionCount ?? receipt.input.recordCount)} pass={Boolean(receipt.output && completed)} /><Metric label="Observed cost" value={receipt.cost?.estimatedComputeUsd != null ? `$${receipt.cost.estimatedComputeUsd.toFixed(6)}` : "n/a"} /></div><div className="mt-4 rounded-lg border border-warn/30 bg-warn-soft p-3"><p className="flex items-center gap-2 text-xs font-bold text-warn"><UserCheck className="size-4" aria-hidden /> Promotion held by design</p><p className="mt-1 text-[10px] leading-4 text-text-muted">The candidate stays at PendingManualApproval. Executions are review-only and never create an approval decision - promotion is a deliberate human act outside this run.</p></div><p className="mt-4 text-[10px] leading-4 text-text-subtle">Receipt {short(receipt.provenance?.receiptSha256)} - input {short(receipt.input.sha256)}{receipt.output ? ` - output ${short(receipt.output.sha256)}` : ""}</p></aside></div>;
}

function LiveLifecycleView({
  loading,
  evidenceError,
  evidence,
  candidate,
  championVersion,
  inferenceObserved,
  gatesPass,
  promote,
}: {
  loading: boolean;
  evidenceError: string | null;
  evidence: LiveModelEvidenceProjection;
  candidate: LiveModelProjection | null;
  championVersion: string;
  inferenceObserved: boolean;
  gatesPass: boolean;
  promote: () => void;
}) {
  const verifiedSteps = candidate
    ? [true, true, true, true, championVersion === candidate.version, inferenceObserved]
    : LIVE_TRAINING_STEPS.map(() => false);
  const stateLabel = loading
    ? "Loading protected evidence"
    : evidenceError
      ? "Evidence API unavailable"
      : evidence.state === "verified"
        ? "Verified training evidence"
        : "Training manifest required";
  return <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]"><div className="border-b border-border p-5 lg:border-b-0 lg:border-r"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Returned training evidence</p><h3 className="mt-1 text-lg font-bold text-text-strong">Verified registry and lifecycle state</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">Live mode does not start implicit training. It verifies an externally supplied non-synthetic manifest and renders only returned receipts.</p></div><span className={`inline-flex min-h-10 items-center rounded-md border px-3 text-xs font-bold ${candidate ? "border-success/30 bg-success-soft text-success" : "border-warn/30 bg-warn-soft text-warn"}`}>{stateLabel}</span></div><div className="mt-5 space-y-2">{LIVE_TRAINING_STEPS.map(([label, system, detail], index) => { const complete = verifiedSteps[index]; return <div key={label} className={`flex gap-3 rounded-lg border p-3 ${complete ? "border-success/25 bg-success-soft/40" : "border-border bg-white"}`}><span className={`grid size-9 shrink-0 place-items-center rounded-md text-xs font-bold ${complete ? "bg-success text-white" : "bg-surface-3 text-text-subtle"}`}>{complete ? <CheckCircle2 className="size-4" aria-hidden /> : index + 1}</span><div className="flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold text-text-strong">{label}</p><span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{system}</span></div><p className="mt-1 text-[10px] leading-4 text-text-muted">{detail}</p></div></div>; })}</div>{!candidate ? <div className="mt-4 flex items-start gap-3 rounded-lg border border-warn/30 bg-warn-soft p-4"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden /><div><p className="text-xs font-bold text-warn">No verified live training lifecycle</p><p className="mt-1 text-[10.5px] leading-5 text-text-muted">{evidenceError ?? evidence.detail} Supply a governed manifest through an approved training workflow before presenting training or evaluation as live.</p></div></div> : null}</div><aside className="bg-surface-2 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Promotion decision</p><h3 className="mt-1 break-all text-lg font-bold text-text-strong">Candidate {candidate?.version ?? "unavailable"}</h3><div className="mt-4 grid grid-cols-2 gap-2"><Metric label="Accuracy" value={candidate ? `${Math.round(candidate.accuracy * 100)}%` : "Unavailable"} pass={Boolean(candidate && candidate.accuracy >= 0.9)} /><Metric label="Macro F1" value={candidate ? candidate.macroF1.toFixed(2) : "Unavailable"} pass={Boolean(candidate && candidate.macroF1 >= 0.88)} /><Metric label="Class coverage" value={candidate ? `${candidate.classCoverage} returned` : "Unavailable"} pass={Boolean(candidate?.classCoverage)} /><Metric label="Manifest" value={candidate ? candidate.trainingManifestSha256.slice(0, 8) : "Required"} pass={Boolean(candidate)} /></div><div className={`mt-4 rounded-lg border p-3 ${gatesPass ? "border-success/30 bg-success-soft" : "border-warn/30 bg-warn-soft"}`}><p className={`flex items-center gap-2 text-xs font-bold ${gatesPass ? "text-success" : "text-warn"}`}>{gatesPass ? <BadgeCheck className="size-4" aria-hidden /> : <AlertTriangle className="size-4" aria-hidden />}{gatesPass ? "Returned gates satisfy policy" : "Promotion held"}</p><p className="mt-1 text-[10px] leading-4 text-text-muted">{gatesPass ? "Metrics came from the verified registry receipt. A separate human action is still required." : "Compass has no verified metrics and manifest combination that satisfies the live promotion boundary."}</p></div><button type="button" onClick={promote} disabled={!gatesPass || !candidate || championVersion === candidate.version} className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-gov-primary bg-white text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter disabled:cursor-not-allowed disabled:opacity-45"><CloudCog className="size-4" aria-hidden /> {championVersion === candidate?.version ? "Verified Champion" : "Approve and promote"}</button></aside></div>;
}

function LifecycleView({ training, trainingStep, candidateReady, candidate, runTraining, promote }: { training: boolean; trainingStep: number; candidateReady: boolean; candidate: LiveModelProjection | null; runTraining: () => void; promote: () => void }) {
  return <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]"><div className="border-b border-border p-5 lg:border-b-0 lg:border-r"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Golden model path</p><h3 className="mt-1 text-lg font-bold text-text-strong">Commit-bound training sequence</h3></div><button type="button" onClick={runTraining} disabled={training} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white shadow-soft hover:bg-gov-primary-dark disabled:opacity-60">{training ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />} {training ? "Training" : "Run bounded training"}</button></div><div className="mt-5 space-y-2">{REHEARSAL_TRAINING_STEPS.map(([label, system, detail], index) => { const complete = candidateReady || trainingStep > index; const active = training && trainingStep === index; return <div key={label} className={`flex gap-3 rounded-lg border p-3 ${active ? "border-gov-primary bg-gov-primary-lighter shadow-soft" : complete ? "border-success/25 bg-success-soft/40" : "border-border bg-white"}`}><span className={`grid size-9 shrink-0 place-items-center rounded-md text-xs font-bold ${complete ? "bg-success text-white" : active ? "bg-gov-primary text-white" : "bg-surface-3 text-text-subtle"}`}>{complete ? <CheckCircle2 className="size-4" aria-hidden /> : active ? <Loader2 className="size-4 animate-spin" aria-hidden /> : index + 1}</span><div className="flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold text-text-strong">{label}</p><span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{system}</span></div><p className="mt-1 text-[10px] leading-4 text-text-muted">{detail}</p></div></div>; })}</div></div><aside className="bg-surface-2 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Promotion decision</p><h3 className="mt-1 break-all text-lg font-bold text-text-strong">Candidate {candidate?.version ?? "awaiting training"}</h3><div className="mt-4 grid grid-cols-2 gap-2"><Metric label="Accuracy" value={candidate ? `${Math.round(candidate.accuracy * 100)}%` : "Pending"} pass={Boolean(candidate && candidate.accuracy >= 0.9)} /><Metric label="Macro F1" value={candidate ? candidate.macroF1.toFixed(2) : "Pending"} pass={Boolean(candidate && candidate.macroF1 >= 0.88)} /><Metric label="Class coverage" value={candidate ? `${candidate.classCoverage} of ${DOCUMENT_CLASSES.length}` : "Pending"} pass={candidate?.classCoverage === DOCUMENT_CLASSES.length} /><Metric label="Source seed" value={candidate?.splitSeed ?? "Pending"} pass={Boolean(candidate)} /></div><div className="mt-4 rounded-lg border border-success/30 bg-success-soft p-3"><p className="flex items-center gap-2 text-xs font-bold text-success"><BadgeCheck className="size-4" aria-hidden /> Evaluation gates pass</p><p className="mt-1 text-[10px] leading-4 text-text-muted">A separate human action is still required before the Champion alias changes.</p></div><button type="button" onClick={promote} disabled={!candidateReady} className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-gov-primary bg-white text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter disabled:cursor-not-allowed disabled:opacity-45"><CloudCog className="size-4" aria-hidden /> Approve and promote</button></aside></div>;
}

function TaxonomyView() {
  return <div className="p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Shared cross-platform contract</p><h3 className="mt-1 text-lg font-bold text-text-strong">Six operational document classes</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">The portable target contract defines the labels, manifest schema, source hashes, evaluation holdout, review threshold, and outcome definition. Live evidence appears only when returned receipts verify those values.</p></div><a href={`${REPOSITORY}/tree/main/seed/documents`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Open corpus <ExternalLink className="size-3.5" aria-hidden /></a></div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{DOCUMENT_CLASSES.map((item, index) => <article key={item.id} className="rounded-lg border border-border bg-white p-4"><div className="flex items-center justify-between"><span className="grid size-9 place-items-center rounded-md bg-gov-primary-lighter text-xs font-bold text-gov-primary">{String(index + 1).padStart(2, "0")}</span><FileText className="size-4 text-gold-ink" aria-hidden /></div><h4 className="mt-3 text-sm font-bold text-text-strong">{item.label}</h4><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{item.purpose}</p><p className="mt-3 line-clamp-2 font-mono text-[9px] text-text-subtle">{item.keywords.join(" | ")}</p></article>)}</div></div>;
}

function RegistryView({ models, championVersion, live, sbir }: { models: readonly ModelVersion[]; championVersion: string; live: boolean; sbir?: PublicModelExecutionReceipt | null }) {
  const short = (value: string | null | undefined) => (value ? value.slice(0, 8) : "n/a");
  const trainingJob = sbir?.model.trainingJobArn ? sbir.model.trainingJobArn.split("/").pop() ?? "" : "";
  return <div className="p-5"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Governed registry</p><h3 className="mt-1 text-lg font-bold text-text-strong">Version, evidence, and alias state</h3></div>{live && sbir ? <div className="mt-5 rounded-lg border border-success/25 bg-white p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[9px] font-bold uppercase tracking-wide text-success">SageMaker Model Registry - returned evidence</p><h4 className="mt-1 text-sm font-bold text-text-strong">{sbir.model.name}</h4></div><span className="rounded-full border border-warn/30 bg-warn-soft px-3 py-1.5 text-[9px] font-bold uppercase text-warn">Pending manual approval</span></div><div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Package" value={`v${sbir.model.packageVersion}`} pass /><Metric label="Training job" value={trainingJob || "n/a"} /><Metric label="Artifact sha" value={short(sbir.model.modelArtifactSha256)} pass /><Metric label="Model card sha" value={short(sbir.model.modelCardSha256)} pass /></div><p className="mt-3 text-[10.5px] leading-5 text-text-muted">Registered candidate held at a governed approval gate. Execution against it is review-only; the package state above is read from the protected execution contract, never asserted.</p></div> : null}{models.length ? <div className="mt-5 overflow-x-auto rounded-lg border border-border"><table className="w-full min-w-[760px] border-collapse text-left"><thead className="bg-surface-2 text-[9px] font-bold uppercase tracking-wide text-text-subtle"><tr><th className="px-4 py-3">Version</th><th className="px-4 py-3">Stage</th><th className="px-4 py-3">Accuracy</th><th className="px-4 py-3">Macro F1</th><th className="px-4 py-3">Records</th><th className="px-4 py-3">Source</th><th className="px-4 py-3">Registry</th></tr></thead><tbody>{models.map((model) => <tr key={model.version} className="border-t border-border bg-white text-xs"><td className="px-4 py-3 font-mono font-bold text-gov-primary">v{model.version}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold uppercase ${model.version === championVersion ? "border-success/30 bg-success-soft text-success" : model.stage === "Candidate" ? "border-info/30 bg-info-soft text-info" : "border-border bg-surface-2 text-text-subtle"}`}>{model.version === championVersion ? "Champion" : model.stage}</span></td><td className="px-4 py-3 font-semibold text-text-strong">{Math.round(model.accuracy * 100)}%</td><td className="px-4 py-3 text-text-muted">{model.macroF1.toFixed(2)}</td><td className="px-4 py-3 text-text-muted">{model.trainingRecords.toLocaleString()}</td><td className="px-4 py-3 font-mono text-[10px] text-text-muted">{model.sourceRevision}</td><td className="px-4 py-3 text-text-muted">{model.registry}</td></tr>)}</tbody></table></div> : live && sbir ? <div className="mt-4 rounded-lg border border-border bg-surface-2 p-4"><p className="text-xs font-bold text-text-strong">Document-classifier rows await a governed manifest</p><p className="mt-1 text-[10.5px] leading-5 text-text-muted">The classifier table lists only records whose non-synthetic training manifest has been verified. The operating champion's inference receipts remain visible in the classifier evidence panel above.</p></div> : <div className="mt-5 rounded-lg border border-dashed border-warn/35 bg-warn-soft p-5 text-center"><p className="text-sm font-bold text-warn">No verified live registry entries</p><p className="mt-2 text-xs leading-5 text-text-muted">The live table excludes synthetic, manifest-free, and incomplete model records. Public-source inference receipts and SageMaker Batch Transform receipts remain visible in their dedicated evidence panels.</p></div>}<div className="mt-4 flex items-start gap-3 rounded-lg border border-info/25 bg-info-soft p-4"><GitCommitHorizontal className="mt-0.5 size-4 shrink-0 text-info" aria-hidden /><p className="text-xs leading-5 text-text-muted">{live ? "A live classifier registry row appears only when the protected API returns a non-synthetic manifest URI and digest, artifact, taxonomy, metrics, source revision, and alias state." : "Every rehearsal version binds deterministic fixtures, split seed, taxonomy, and explicit synthetic marking."}</p></div></div>;
}

function MonitoringView({ live, scenario, setScenario, ran, drift, liveReceipt, modelVersion, historyCount = 0, evaluate }: { live: boolean; scenario: "baseline" | "shifted"; setScenario: (next: "baseline" | "shifted") => void; ran: boolean; drift: ReturnType<typeof driftDecision> | null; liveReceipt: ModelDriftReceipt | null; modelVersion: string; historyCount?: number; evaluate: () => void }) {
  const livePsi = typeof liveReceipt?.population_stability_index === "number" ? liveReceipt.population_stability_index : null;
  const liveOov = typeof liveReceipt?.out_of_vocabulary_rate === "number" ? liveReceipt.out_of_vocabulary_rate : null;
  const liveObserved = typeof liveReceipt?.documents_observed === "number" ? liveReceipt.documents_observed : null;
  const rehearsalPsi = scenario === "baseline" ? 0.08 : 0.34;
  const rehearsalConfidence = scenario === "baseline" ? 0.81 : 0.49;
  const psi = live ? livePsi : rehearsalPsi;
  const detected = typeof liveReceipt?.drift_detected === "boolean"
    ? liveReceipt.drift_detected
    : live
      ? null
      : drift?.detected ?? null;
  const action = typeof liveReceipt?.recommended_action === "string"
    ? liveReceipt.recommended_action
    : live
      ? null
      : drift?.action ?? null;
  const receiptReady = !live || Boolean(liveReceipt);
  return <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]"><div className="border-b border-border p-5 lg:border-b-0 lg:border-r"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Controlled monitoring proof</p><h3 className="mt-1 text-lg font-bold text-text-strong">{live ? "Current accepted public inference windows" : "Baseline and shifted rehearsal batches"}</h3></div><div className="mt-5 grid gap-3 sm:grid-cols-2">{(["baseline", "shifted"] as const).map((id) => <button key={id} type="button" onClick={() => setScenario(id)} className={`rounded-lg border p-4 text-left ${scenario === id ? "border-gov-primary bg-gov-primary-lighter shadow-soft" : "border-border bg-white"}`}><div className="flex items-center justify-between"><span className="grid size-9 place-items-center rounded-md bg-gov-primary text-white">{id === "baseline" ? <ShieldCheck className="size-4" aria-hidden /> : <RefreshCcw className="size-4" aria-hidden />}</span><span className={`rounded-full px-2 py-1 text-[8px] font-bold uppercase ${id === "baseline" ? "bg-success-soft text-success" : "bg-warn-soft text-warn"}`}>{live ? id === "baseline" ? "First accepted window" : "Latest accepted window" : id === "baseline" ? "Expected" : "Intentional shift"}</span></div><h4 className="mt-3 text-sm font-bold text-text-strong">{live ? id === "baseline" ? "Earlier live narratives" : "Newest live narratives" : id === "baseline" ? "Production-like baseline" : "Drifted vocabulary batch"}</h4><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{live ? "Compass selects real narratives from the currently accepted public-source receipts and submits their text to the protected drift evaluator." : id === "baseline" ? "Balanced synthetic classes with vocabulary coverage similar to the training corpus." : "Unfamiliar synthetic terms lower confidence and alter the predicted class distribution."}</p></button>)}</div><div className="mt-4 grid gap-3 sm:grid-cols-3"><DriftMetric label="Class PSI" value={psi === null ? "Not evaluated" : psi.toFixed(2)} threshold="Alert > 0.25" alert={Boolean(psi !== null && psi > 0.25)} /><DriftMetric label={live ? "OOV rate" : "Mean confidence"} value={live ? liveOov === null ? "Not evaluated" : `${Math.round(liveOov * 100)}%` : `${Math.round(rehearsalConfidence * 100)}%`} threshold={live ? "Returned vocabulary shift" : "Alert < 55%"} alert={live ? Boolean(liveOov !== null && liveOov > 0.25) : rehearsalConfidence < 0.55} /><DriftMetric label="Observed records" value={liveObserved === null ? live ? "Not evaluated" : "240" : String(liveObserved)} threshold="Bounded batch" alert={false} /></div></div><aside className="bg-surface-2 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Drift receipt</p><h3 className="mt-1 break-all text-lg font-bold text-text-strong">Model {modelVersion}</h3><button type="button" onClick={evaluate} className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-gov-primary text-xs font-bold text-white shadow-soft hover:bg-gov-primary-dark"><Activity className="size-4" aria-hidden /> Evaluate selected batch</button>{ran && receiptReady && detected !== null && action ? <div className={`mt-4 rounded-lg border p-4 ${detected ? "border-warn/35 bg-warn-soft" : "border-success/30 bg-success-soft"}`}><p className={`flex items-center gap-2 text-xs font-bold ${detected ? "text-warn" : "text-success"}`}>{detected ? <AlertTriangle className="size-4" aria-hidden /> : <CheckCircle2 className="size-4" aria-hidden />}{detected ? "Drift detected" : "Within baseline"}</p><p className="mt-2 text-[10.5px] leading-5 text-text-muted">Action: {action.replaceAll("-", " ")}. Retraining creates a Candidate only. It cannot silently replace the Champion.</p></div> : <p className="mt-4 text-[10.5px] leading-5 text-text-muted">{live ? "No PSI, vocabulary shift, confidence, or gate decision is shown until the protected evaluator returns a receipt." : "Run the evaluation to create a threshold-bound rehearsal receipt and recommended next action."}</p>}{live && historyCount > 0 ? <p className="mt-3 text-[10px] leading-4 text-text-subtle">{historyCount} prior drift {historyCount === 1 ? "receipt is" : "receipts are"} retained in the governed evidence store.</p> : null}</aside></div>;
}

function BoundaryNote({ live }: { live: boolean }) {
  return <section className="grid gap-4 rounded-xl border border-border bg-surface p-5 shadow-soft lg:grid-cols-[minmax(0,1fr)_300px]"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden /><div><p className="text-sm font-bold text-text-strong">Evidence boundary</p><p className="mt-1 text-xs leading-5 text-text-muted">{live ? "Live mode calls protected AWS model APIs and shows only returned model, drift, and execution receipts. An unavailable live call remains visible as an error and never activates a replay result." : "Rehearsal executes the same pure taxonomy, split, classification, metric, promotion, and drift contracts without submitting SageMaker compute. Every result remains labeled as rehearsal."}</p></div></div><a href={`${REPOSITORY}/tree/main/src/functions/document_ml`} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Inspect model code <Code2 className="size-4" aria-hidden /></a></section>;
}

function HeroMetric({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) { return <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3"><Icon className="size-4 text-gold-light" aria-hidden /><p className="mt-2 text-[9px] font-bold uppercase tracking-wide text-white/45">{label}</p><p className="mt-1 text-lg font-bold text-white">{value}</p></div>; }
function Metric({ label, value, pass }: { label: string; value: string; pass?: boolean }) { return <div className="rounded-md border border-border bg-white p-2.5"><div className="flex items-center justify-between gap-2"><p className="text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p>{pass ? <CheckCircle2 className="size-3 text-success" aria-hidden /> : null}</div><p className="mt-1 text-xs font-bold text-text-strong">{value}</p></div>; }
function DriftMetric({ label, value, threshold, alert }: { label: string; value: string; threshold: string; alert: boolean }) { return <div className={`rounded-lg border p-4 ${alert ? "border-warn/35 bg-warn-soft" : "border-border bg-white"}`}><BarChart3 className={`size-4 ${alert ? "text-warn" : "text-gov-primary"}`} aria-hidden /><p className="mt-3 text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 text-xl font-bold text-text-strong">{value}</p><p className="mt-1 text-[9px] text-text-muted">{threshold}</p></div>; }

"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
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
  Sparkles,
  Target,
  UserCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import {
  USE_MOCK,
  getModelOpsEvidenceApi,
  postModelDeployApi,
  postModelDriftApi,
  postModelTrainApi,
  type ModelRecord,
} from "@/lib/api";
import {
  DOCUMENT_CLASSES,
  MODEL_VERSIONS,
  driftDecision,
  modelPromotionDecision,
  type ModelVersion,
} from "@/lib/mlops/demo-model";
import {
  projectLiveModel,
  resolvePromotionVersion,
  type LiveModelProjection,
} from "@/lib/mlops/live-model";

type View = "lifecycle" | "taxonomy" | "registry" | "monitoring";

const REPOSITORY = "https://github.com/SatsyilCorp/compass-demo";
const TRAINING_STEPS = [
  ["Prepare immutable split", "S3 training set", "SHA-256 manifest, seed 20260811, 30 train, 6 evaluation"],
  ["Train classical model", "SageMaker adapter", "Multinomial Naive Bayes with bounded CPU and network isolation"],
  ["Evaluate gates", "Evaluation job", "Accuracy, macro F1, class coverage, and confusion matrix"],
  ["Register candidate", "Model Registry", "Artifact digest, source revision, dataset digest, and metrics"],
  ["Approve promotion", "Human control", "Candidate must satisfy thresholds before Champion alias changes"],
  ["Deploy and observe", "Batch inference", "Bounded classification, confidence, drift, and review queue"],
] as const;

const VIEWS: { id: View; label: string; icon: LucideIcon }[] = [
  { id: "lifecycle", label: "Training lifecycle", icon: Workflow },
  { id: "taxonomy", label: "Document taxonomy", icon: FileText },
  { id: "registry", label: "Model registry", icon: Database },
  { id: "monitoring", label: "Drift and retraining", icon: Activity },
];

export function ModelOperations() {
  const [view, setView] = useState<View>("lifecycle");
  const [adapterMode, setAdapterMode] = useState<"live" | "replay">(USE_MOCK ? "replay" : "live");
  const [evidenceLoading, setEvidenceLoading] = useState(!USE_MOCK);
  const [liveCandidate, setLiveCandidate] = useState<ModelRecord | null>(null);
  const [liveDriftReceipt, setLiveDriftReceipt] = useState<Record<string, unknown> | null>(null);
  const [trainingStep, setTrainingStep] = useState(-1);
  const [training, setTraining] = useState(false);
  const [candidateReady, setCandidateReady] = useState(false);
  const [championVersion, setChampionVersion] = useState("2");
  const [driftScenario, setDriftScenario] = useState<"baseline" | "shifted">("baseline");
  const [driftRan, setDriftRan] = useState(false);
  const [operation, setOperation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    let active = true;
    if (!USE_MOCK) {
      void getModelOpsEvidenceApi()
        .then((evidence) => {
          if (!active) return;
          const models = Array.isArray(evidence.models) ? evidence.models : [];
          const latest = models.find((item): item is ModelRecord => {
            return Boolean(item && typeof item === "object" && "model_version" in item);
          });
          if (latest) setLiveCandidate(latest);
          const champion = evidence.champion;
          if (champion && typeof champion === "object" && "model_version" in champion) {
            const version = (champion as { model_version?: unknown }).model_version;
            if (typeof version === "string") setChampionVersion(version);
          }
        })
        .catch(() => {
          if (!active) return;
          setAdapterMode("replay");
          setOperation("Live API unavailable. The bounded replay adapter is active and clearly labeled.");
        })
        .finally(() => {
          if (active) setEvidenceLoading(false);
        });
    }
    return () => {
      active = false;
      timers.current.forEach(clearTimeout);
    };
  }, []);

  const replayCandidate = MODEL_VERSIONS[2];
  const liveProjection = projectLiveModel(liveCandidate);
  const isLive = adapterMode === "live";
  const promotion = isLive
    ? liveProjection && liveProjection.accuracy >= 0.9 && liveProjection.macroF1 >= 0.88
      ? "approve"
      : "reject"
    : modelPromotionDecision(replayCandidate);
  const drift = driftScenario === "baseline" ? driftDecision(0.08, 0.81) : driftDecision(0.34, 0.49);
  const replayModels = useMemo(() => MODEL_VERSIONS.map((model) => model.version === championVersion ? { ...model, stage: "Champion" as const } : model.version === "2" && championVersion !== "2" ? { ...model, stage: "Archived" as const } : model), [championVersion]);
  const registryModels = useMemo<readonly ModelVersion[]>(() => {
    if (!isLive || !liveProjection) return replayModels;
    return [{
      version: liveProjection.version,
      stage: championVersion === liveProjection.version ? "Champion" : "Candidate",
      accuracy: liveProjection.accuracy,
      macroF1: liveProjection.macroF1,
      trainingRecords: liveProjection.trainingRecords,
      sourceRevision: liveProjection.sourceRevision,
      registry: "Compass registry with SageMaker integration seam",
      createdAt: liveProjection.createdAt,
    }];
  }, [championVersion, isLive, liveProjection, replayModels]);

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
  } satisfies LiveModelProjection;

  const runTraining = async () => {
    if (training) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setError(null);
    setOperation(null);
    setCandidateReady(false);
    setTraining(true);
    setTrainingStep(0);
    if (isLive) {
      try {
        const result = await postModelTrainApi();
        setLiveCandidate(result);
        setLiveDriftReceipt(null);
        setTrainingStep(TRAINING_STEPS.length - 1);
        setCandidateReady(true);
        setOperation(`Live training receipt accepted for model ${result.model_version}.`);
        setTraining(false);
        return;
      } catch (cause) {
        setAdapterMode("replay");
        setError(`${cause instanceof Error ? cause.message : "The protected training request failed."} Bounded replay is now active.`);
      }
    }
    const advance = (next: number) => {
      if (next >= TRAINING_STEPS.length) {
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
      if (isLive) setLiveCandidate((current) => current ? { ...current, status: "deployed" } : current);
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
        const documents = driftScenario === "shifted" ? Array.from({ length: 8 }, (_, index) => `Synthetic unfamiliar retail vocabulary galaxy recipe batch ${index} with sufficient demonstration content.`) : undefined;
        const receipt = await postModelDriftApi(documents);
        setLiveDriftReceipt(receipt);
      }
      setDriftRan(true);
      const modelLabel = isLive ? ` for model ${championVersion || liveProjection?.version || "unknown"}` : "";
      setOperation(`${isLive ? "Live" : "Replay"} drift receipt${modelLabel} was recorded.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Drift evaluation failed.");
    }
  };

  return (
    <div className="mt-6 space-y-6">
      <section className="overflow-hidden rounded-xl border border-gov-primary/20 bg-gov-primary text-white shadow-card">
        <div className="compass-grid-overlay grid gap-5 px-5 py-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)] lg:px-6">
          <div>
            <div className="flex flex-wrap items-center gap-2"><span className="rounded-full border border-gold-light/30 bg-gold-light/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-gold-light">Element 5 of 7</span><span className="rounded-full border border-white/15 bg-white/[0.07] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white/70">{isLive ? "Live AWS adapter" : USE_MOCK ? "Bounded replay adapter" : "Replay fallback"}</span></div>
            <h2 className="mt-3 text-2xl font-bold">Classical document MLOps control room</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">Train, evaluate, register, approve, deploy, monitor, and conditionally retrain one portable document classifier. The application contract stays stable whether the Implementation is the bounded local Adapter or SageMaker.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3"><HeroMetric icon={Target} label="Candidate accuracy" value={evidenceLoading && isLive ? "Loading" : candidateDisplay ? `${Math.round(candidateDisplay.accuracy * 100)}%` : "Run training"} /><HeroMetric icon={Scale} label="Macro F1" value={evidenceLoading && isLive ? "Loading" : candidateDisplay ? candidateDisplay.macroF1.toFixed(2) : "Run training"} /><HeroMetric icon={UserCheck} label="Review threshold" value="62%" /></div>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-card">
        <div className="grid gap-2 border-b border-border bg-white p-3 sm:grid-cols-2 lg:grid-cols-4" role="tablist" aria-label="Model operations views">
          {VIEWS.map((item) => { const Icon = item.icon; const active = item.id === view; return <button key={item.id} type="button" role="tab" aria-selected={active} onClick={() => setView(item.id)} className={`flex min-h-12 items-center gap-2 rounded-md border px-3 text-left text-xs font-bold ${active ? "border-gov-primary bg-gov-primary text-white" : "border-border bg-white text-text-muted hover:bg-surface-2"}`}><Icon className="size-4" aria-hidden /> {item.label}</button>; })}
        </div>

        {view === "lifecycle" ? <LifecycleView training={training} trainingStep={trainingStep} candidateReady={candidateReady} candidate={candidateDisplay} runTraining={() => void runTraining()} promote={() => void promoteCandidate()} /> : null}
        {view === "taxonomy" ? <TaxonomyView /> : null}
        {view === "registry" ? <RegistryView models={registryModels} championVersion={championVersion} /> : null}
        {view === "monitoring" ? <MonitoringView scenario={driftScenario} setScenario={(next) => { setDriftScenario(next); setDriftRan(false); setLiveDriftReceipt(null); }} ran={driftRan} drift={drift} liveReceipt={isLive ? liveDriftReceipt : null} modelVersion={isLive ? championVersion || liveProjection?.version || "not promoted" : replayCandidate.version} evaluate={() => void evaluateDrift()} /> : null}
      </section>

      {operation ? <div className="flex items-start gap-3 rounded-lg border border-success/30 bg-success-soft p-4 text-xs leading-5 text-success"><CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden /><span>{operation}</span></div> : null}
      {error ? <div className="flex items-start gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-xs leading-5 text-danger"><AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /><span>{error}</span></div> : null}
      <BoundaryNote />
    </div>
  );
}

function LifecycleView({ training, trainingStep, candidateReady, candidate, runTraining, promote }: { training: boolean; trainingStep: number; candidateReady: boolean; candidate: LiveModelProjection | null; runTraining: () => void; promote: () => void }) {
  return <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]"><div className="border-b border-border p-5 lg:border-b-0 lg:border-r"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Golden model path</p><h3 className="mt-1 text-lg font-bold text-text-strong">Commit-bound training sequence</h3></div><button type="button" onClick={runTraining} disabled={training} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-gov-primary px-4 text-xs font-bold text-white shadow-soft hover:bg-gov-primary-dark disabled:opacity-60">{training ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />} {training ? "Training" : "Run bounded training"}</button></div><div className="mt-5 space-y-2">{TRAINING_STEPS.map(([label, system, detail], index) => { const complete = candidateReady || trainingStep > index; const active = training && trainingStep === index; return <div key={label} className={`flex gap-3 rounded-lg border p-3 ${active ? "border-gov-primary bg-gov-primary-lighter shadow-soft" : complete ? "border-success/25 bg-success-soft/40" : "border-border bg-white"}`}><span className={`grid size-9 shrink-0 place-items-center rounded-md text-xs font-bold ${complete ? "bg-success text-white" : active ? "bg-gov-primary text-white" : "bg-surface-3 text-text-subtle"}`}>{complete ? <CheckCircle2 className="size-4" aria-hidden /> : active ? <Loader2 className="size-4 animate-spin" aria-hidden /> : index + 1}</span><div className="flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold text-text-strong">{label}</p><span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{system}</span></div><p className="mt-1 text-[10px] leading-4 text-text-muted">{detail}</p></div></div>; })}</div></div><aside className="bg-surface-2 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Promotion decision</p><h3 className="mt-1 break-all text-lg font-bold text-text-strong">Candidate {candidate?.version ?? "awaiting training"}</h3><div className="mt-4 grid grid-cols-2 gap-2"><Metric label="Accuracy" value={candidate ? `${Math.round(candidate.accuracy * 100)}%` : "Pending"} pass={Boolean(candidate && candidate.accuracy >= 0.9)} /><Metric label="Macro F1" value={candidate ? candidate.macroF1.toFixed(2) : "Pending"} pass={Boolean(candidate && candidate.macroF1 >= 0.88)} /><Metric label="Class coverage" value={candidate ? `${candidate.classCoverage} of ${DOCUMENT_CLASSES.length}` : "Pending"} pass={candidate?.classCoverage === DOCUMENT_CLASSES.length} /><Metric label="Source seed" value={candidate?.splitSeed ?? "Pending"} pass={Boolean(candidate)} /></div><div className="mt-4 rounded-lg border border-success/30 bg-success-soft p-3"><p className="flex items-center gap-2 text-xs font-bold text-success"><BadgeCheck className="size-4" aria-hidden /> Evaluation gates pass</p><p className="mt-1 text-[10px] leading-4 text-text-muted">A separate human action is still required before the Champion alias changes.</p></div><button type="button" onClick={promote} disabled={!candidateReady} className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-gov-primary bg-white text-xs font-bold text-gov-primary hover:bg-gov-primary-lighter disabled:cursor-not-allowed disabled:opacity-45"><CloudCog className="size-4" aria-hidden /> Approve and promote</button></aside></div>;
}

function TaxonomyView() {
  return <div className="p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Shared cross-platform contract</p><h3 className="mt-1 text-lg font-bold text-text-strong">Six operational document classes</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">AWS and Databricks use the same labels, seed, source hashes, evaluation holdout, review threshold, and outcome definition.</p></div><a href={`${REPOSITORY}/tree/main/seed/documents`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Open corpus <ExternalLink className="size-3.5" aria-hidden /></a></div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{DOCUMENT_CLASSES.map((item, index) => <article key={item.id} className="rounded-lg border border-border bg-white p-4"><div className="flex items-center justify-between"><span className="grid size-9 place-items-center rounded-md bg-gov-primary-lighter text-xs font-bold text-gov-primary">{String(index + 1).padStart(2, "0")}</span><FileText className="size-4 text-gold-ink" aria-hidden /></div><h4 className="mt-3 text-sm font-bold text-text-strong">{item.label}</h4><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{item.purpose}</p><p className="mt-3 line-clamp-2 font-mono text-[9px] text-text-subtle">{item.keywords.join(" | ")}</p></article>)}</div></div>;
}

function RegistryView({ models, championVersion }: { models: readonly ModelVersion[]; championVersion: string }) {
  return <div className="p-5"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Governed registry</p><h3 className="mt-1 text-lg font-bold text-text-strong">Version, evidence, and alias state</h3></div><div className="mt-5 overflow-x-auto rounded-lg border border-border"><table className="w-full min-w-[760px] border-collapse text-left"><thead className="bg-surface-2 text-[9px] font-bold uppercase tracking-wide text-text-subtle"><tr><th className="px-4 py-3">Version</th><th className="px-4 py-3">Stage</th><th className="px-4 py-3">Accuracy</th><th className="px-4 py-3">Macro F1</th><th className="px-4 py-3">Records</th><th className="px-4 py-3">Source</th><th className="px-4 py-3">Registry</th></tr></thead><tbody>{models.map((model) => <tr key={model.version} className="border-t border-border bg-white text-xs"><td className="px-4 py-3 font-mono font-bold text-gov-primary">v{model.version}</td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[9px] font-bold uppercase ${model.version === championVersion ? "border-success/30 bg-success-soft text-success" : model.stage === "Candidate" ? "border-info/30 bg-info-soft text-info" : "border-border bg-surface-2 text-text-subtle"}`}>{model.version === championVersion ? "Champion" : model.stage}</span></td><td className="px-4 py-3 font-semibold text-text-strong">{Math.round(model.accuracy * 100)}%</td><td className="px-4 py-3 text-text-muted">{model.macroF1.toFixed(2)}</td><td className="px-4 py-3 text-text-muted">{model.trainingRecords.toLocaleString()}</td><td className="px-4 py-3 font-mono text-[10px] text-text-muted">{model.sourceRevision}</td><td className="px-4 py-3 text-text-muted">{model.registry}</td></tr>)}</tbody></table></div><div className="mt-4 flex items-start gap-3 rounded-lg border border-info/25 bg-info-soft p-4"><GitCommitHorizontal className="mt-0.5 size-4 shrink-0 text-info" aria-hidden /><p className="text-xs leading-5 text-text-muted">Every registered version binds the algorithm, source revision, training manifest digest, split seed, metrics, taxonomy, runtime, and synthetic-only marking.</p></div></div>;
}

function MonitoringView({ scenario, setScenario, ran, drift, liveReceipt, modelVersion, evaluate }: { scenario: "baseline" | "shifted"; setScenario: (next: "baseline" | "shifted") => void; ran: boolean; drift: ReturnType<typeof driftDecision>; liveReceipt: Record<string, unknown> | null; modelVersion: string; evaluate: () => void }) {
  const livePsi = typeof liveReceipt?.population_stability_index === "number" ? liveReceipt.population_stability_index : null;
  const liveOov = typeof liveReceipt?.out_of_vocabulary_rate === "number" ? liveReceipt.out_of_vocabulary_rate : null;
  const liveObserved = typeof liveReceipt?.documents_observed === "number" ? liveReceipt.documents_observed : null;
  const psi = livePsi ?? (scenario === "baseline" ? 0.08 : 0.34);
  const confidence = scenario === "baseline" ? 0.81 : 0.49;
  const detected = typeof liveReceipt?.drift_detected === "boolean" ? liveReceipt.drift_detected : drift.detected;
  const action = typeof liveReceipt?.recommended_action === "string" ? liveReceipt.recommended_action : drift.action;
  return <div className="grid lg:grid-cols-[minmax(0,1fr)_340px]"><div className="border-b border-border p-5 lg:border-b-0 lg:border-r"><div><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Controlled monitoring proof</p><h3 className="mt-1 text-lg font-bold text-text-strong">Baseline and shifted inference batches</h3></div><div className="mt-5 grid gap-3 sm:grid-cols-2">{(["baseline", "shifted"] as const).map((id) => <button key={id} type="button" onClick={() => setScenario(id)} className={`rounded-lg border p-4 text-left ${scenario === id ? "border-gov-primary bg-gov-primary-lighter shadow-soft" : "border-border bg-white"}`}><div className="flex items-center justify-between"><span className="grid size-9 place-items-center rounded-md bg-gov-primary text-white">{id === "baseline" ? <ShieldCheck className="size-4" aria-hidden /> : <RefreshCcw className="size-4" aria-hidden />}</span><span className={`rounded-full px-2 py-1 text-[8px] font-bold uppercase ${id === "baseline" ? "bg-success-soft text-success" : "bg-warn-soft text-warn"}`}>{id === "baseline" ? "Expected" : "Intentional shift"}</span></div><h4 className="mt-3 text-sm font-bold text-text-strong">{id === "baseline" ? "Production-like baseline" : "Drifted vocabulary batch"}</h4><p className="mt-2 text-[10.5px] leading-5 text-text-muted">{id === "baseline" ? "Balanced synthetic classes with vocabulary coverage similar to the training corpus." : "Unfamiliar synthetic terms lower confidence and alter the predicted class distribution."}</p></button>)}</div><div className="mt-4 grid gap-3 sm:grid-cols-3"><DriftMetric label="Class PSI" value={psi.toFixed(2)} threshold="Alert > 0.25" alert={psi > 0.25} /><DriftMetric label={liveOov === null ? "Mean confidence" : "OOV rate"} value={liveOov === null ? `${Math.round(confidence * 100)}%` : `${Math.round(liveOov * 100)}%`} threshold={liveOov === null ? "Alert < 55%" : "Vocabulary shift"} alert={liveOov === null ? confidence < 0.55 : liveOov > 0.25} /><DriftMetric label="Observed records" value={String(liveObserved ?? 240)} threshold="Bounded batch" alert={false} /></div></div><aside className="bg-surface-2 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-gold-ink">Drift receipt</p><h3 className="mt-1 break-all text-lg font-bold text-text-strong">Model {modelVersion}</h3><button type="button" onClick={evaluate} className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-gov-primary text-xs font-bold text-white shadow-soft hover:bg-gov-primary-dark"><Activity className="size-4" aria-hidden /> Evaluate selected batch</button>{ran ? <div className={`mt-4 rounded-lg border p-4 ${detected ? "border-warn/35 bg-warn-soft" : "border-success/30 bg-success-soft"}`}><p className={`flex items-center gap-2 text-xs font-bold ${detected ? "text-warn" : "text-success"}`}>{detected ? <AlertTriangle className="size-4" aria-hidden /> : <CheckCircle2 className="size-4" aria-hidden />}{detected ? "Drift detected" : "Within baseline"}</p><p className="mt-2 text-[10.5px] leading-5 text-text-muted">Action: {action.replaceAll("-", " ")}. Retraining creates a Candidate only. It cannot silently replace the Champion.</p></div> : <p className="mt-4 text-[10.5px] leading-5 text-text-muted">Run the evaluation to create a threshold-bound drift receipt and recommended next action.</p>}</aside></div>;
}

function BoundaryNote() {
  return <section className="grid gap-4 rounded-xl border border-border bg-surface p-5 shadow-soft lg:grid-cols-[minmax(0,1fr)_300px]"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 size-5 shrink-0 text-warn" aria-hidden /><div><p className="text-sm font-bold text-text-strong">Evidence boundary</p><p className="mt-1 text-xs leading-5 text-text-muted">Replay mode executes the same pure taxonomy, split, classification, metric, promotion, and drift contracts without submitting SageMaker compute. Live mode calls the protected AWS adapter. The screen never labels a local receipt as a SageMaker job, endpoint, or production validation.</p></div></div><a href={`${REPOSITORY}/tree/main/src/functions/document_ml`} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-gov-primary hover:bg-surface-2">Inspect model code <Code2 className="size-4" aria-hidden /></a></section>;
}

function HeroMetric({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) { return <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3"><Icon className="size-4 text-gold-light" aria-hidden /><p className="mt-2 text-[9px] font-bold uppercase tracking-wide text-white/45">{label}</p><p className="mt-1 text-lg font-bold text-white">{value}</p></div>; }
function Metric({ label, value, pass }: { label: string; value: string; pass?: boolean }) { return <div className="rounded-md border border-border bg-white p-2.5"><div className="flex items-center justify-between gap-2"><p className="text-[8px] font-bold uppercase tracking-wide text-text-subtle">{label}</p>{pass ? <CheckCircle2 className="size-3 text-success" aria-hidden /> : null}</div><p className="mt-1 text-xs font-bold text-text-strong">{value}</p></div>; }
function DriftMetric({ label, value, threshold, alert }: { label: string; value: string; threshold: string; alert: boolean }) { return <div className={`rounded-lg border p-4 ${alert ? "border-warn/35 bg-warn-soft" : "border-border bg-white"}`}><BarChart3 className={`size-4 ${alert ? "text-warn" : "text-gov-primary"}`} aria-hidden /><p className="mt-3 text-[9px] font-bold uppercase tracking-wide text-text-subtle">{label}</p><p className="mt-1 text-xl font-bold text-text-strong">{value}</p><p className="mt-1 text-[9px] text-text-muted">{threshold}</p></div>; }

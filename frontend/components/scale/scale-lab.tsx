"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Boxes,
  Braces,
  CircleDollarSign,
  DatabaseZap,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  getScaleAdapter,
  isTerminalScaleStatus,
  SCALE_PROFILES,
  scaleErrorMessage,
  type ScalePlan,
  type ScaleProfile,
  type ScaleProfileId,
  type ScaleRun,
} from "@/lib/scale";
import {
  SCALE_RUN_ID_PATTERN,
  useMissionDataContext,
} from "@/lib/mission-data-context";
import { ProfileSelector } from "./profile-selector";
import { PlanPreview } from "./plan-preview";
import { RunConsole } from "./run-console";
import { RunHistory } from "./run-history";
import { ArchitectureDiagram } from "./architecture-diagram";

const DEFAULT_SEED = "20260811";
const POLL_MS = 1_250;

function idempotencyKey(prefix: string): string {
  const suffix = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

export function ScaleLab() {
  const adapter = useMemo(() => getScaleAdapter(), []);
  const { selection, selectScaleRun } = useMissionDataContext();
  const [profiles, setProfiles] = useState<ScaleProfile[]>([...SCALE_PROFILES]);
  const [selectedProfile, setSelectedProfile] = useState<ScaleProfileId>("10k");
  const [seed, setSeed] = useState(DEFAULT_SEED);
  const [plan, setPlan] = useState<ScalePlan | null>(null);
  const [planLoading, setPlanLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [run, setRun] = useState<ScaleRun | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runs, setRuns] = useState<ScaleRun[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [staleMessage, setStaleMessage] = useState<string | null>(null);
  const [lastGoodAt, setLastGoodAt] = useState<string | null>(null);

  const updateRunList = useCallback((nextRun: ScaleRun) => {
    setRuns((current) => {
      const next = [nextRun, ...current.filter((candidate) => candidate.run_id !== nextRun.run_id)];
      return next.sort((left, right) => right.created_at.localeCompare(left.created_at)).slice(0, 12);
    });
  }, []);

  const setRunInUrl = useCallback((runId: string | null) => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (runId) url.searchParams.set("run", runId);
    else url.searchParams.delete("run");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const previewPlan = useCallback(async (profileId = selectedProfile, seedText = seed) => {
    const parsedSeed = Number(seedText);
    if (!Number.isInteger(parsedSeed) || parsedSeed < 1) {
      setActionError("Enter a deterministic seed greater than zero before previewing the plan.");
      setPlan(null);
      return;
    }
    setPlanLoading(true);
    setActionError(null);
    try {
      const nextPlan = await adapter.previewPlan({ profile_id: profileId, seed: parsedSeed });
      setPlan(nextPlan);
    } catch (error) {
      setPlan(null);
      setActionError(scaleErrorMessage(error));
    } finally {
      setPlanLoading(false);
    }
  }, [adapter, seed, selectedProfile]);

  useEffect(() => {
    let active = true;
    const queryRun = new URLSearchParams(window.location.search).get("run");
    if (queryRun && SCALE_RUN_ID_PATTERN.test(queryRun)) {
      setActiveRunId(queryRun);
      selectScaleRun(queryRun);
    }
    const load = async () => {
      const results = await Promise.allSettled([adapter.getProfiles(), adapter.listRuns()]);
      if (!active) return;
      if (results[0].status === "fulfilled") setProfiles(results[0].value.profiles);
      if (results[1].status === "fulfilled") setRuns(results[1].value.runs.slice(0, 12));
    };
    void load();
    return () => { active = false; };
  }, [adapter, selectScaleRun]);

  useEffect(() => {
    void previewPlan(selectedProfile, seed);
    // A profile selection is a new plan intent. Seed changes require the explicit Preview action.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile]);

  useEffect(() => {
    if (!activeRunId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const nextRun = await adapter.getRun(activeRunId);
        if (stopped) return;
        setRun(nextRun);
        updateRunList(nextRun);
        setStaleMessage(null);
        setLastGoodAt(new Date().toISOString());
        if (!isTerminalScaleStatus(nextRun.status)) timer = setTimeout(() => void poll(), POLL_MS);
      } catch (error) {
        if (stopped) return;
        setStaleMessage(scaleErrorMessage(error));
        timer = setTimeout(() => void poll(), POLL_MS * 2);
      }
    };

    void poll();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeRunId, adapter, updateRunList]);

  useEffect(() => {
    const exportId = run?.export_receipt.export_id;
    if (!run || !exportId || run.export_receipt.status !== "building") return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const pollExport = async () => {
      try {
        const receipt = await adapter.getExport(run.run_id, exportId);
        if (stopped) return;
        setRun((current) => current && current.run_id === run.run_id ? { ...current, export_receipt: receipt } : current);
        setRuns((current) => current.map((candidate) => candidate.run_id === run.run_id ? { ...candidate, export_receipt: receipt } : candidate));
        setExportBusy(receipt.status === "building");
        if (receipt.status === "building") timer = setTimeout(() => void pollExport(), POLL_MS);
      } catch (error) {
        if (stopped) return;
        setActionError(scaleErrorMessage(error));
        setExportBusy(false);
      }
    };
    timer = setTimeout(() => void pollExport(), 500);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [adapter, run?.export_receipt.export_id, run?.export_receipt.status, run?.run_id]);

  const launch = async () => {
    if (!plan) return;
    setLaunching(true);
    setActionError(null);
    try {
      const nextRun = await adapter.launchRun({
        plan_id: plan.plan_id,
        idempotency_key: idempotencyKey(`launch-${plan.plan_id}`),
      });
      setRun(nextRun);
      setActiveRunId(nextRun.run_id);
      setRunInUrl(nextRun.run_id);
      selectScaleRun(nextRun.run_id);
      updateRunList(nextRun);
    } catch (error) {
      setActionError(scaleErrorMessage(error));
    } finally {
      setLaunching(false);
    }
  };

  const cancel = async () => {
    if (!run) return;
    setCancelling(true);
    setActionError(null);
    try {
      const nextRun = await adapter.cancelRun(run.run_id);
      setRun(nextRun);
      updateRunList(nextRun);
    } catch (error) {
      setActionError(scaleErrorMessage(error));
    } finally {
      setCancelling(false);
    }
  };

  const requestExport = async () => {
    if (!run) return;
    setExportBusy(true);
    setActionError(null);
    try {
      const receipt = await adapter.requestExport(run.run_id, {
        dataset: "curated_portfolio",
        format: "parquet",
        idempotency_key: idempotencyKey(`export-${run.run_id}`),
      });
      const nextRun = { ...run, export_receipt: receipt };
      setRun(nextRun);
      updateRunList(nextRun);
    } catch (error) {
      setActionError(scaleErrorMessage(error));
      setExportBusy(false);
    }
  };

  const openRun = (runId: string) => {
    const cached = runs.find((candidate) => candidate.run_id === runId) ?? null;
    setRun(cached);
    setActiveRunId(runId);
    setRunInUrl(runId);
    selectScaleRun(runId);
    setStaleMessage(null);
  };

  const runActive = Boolean(run && !isTerminalScaleStatus(run.status));
  const selectedEvidenceRunId = selection.kind === "scale" ? selection.runId : null;

  return (
    <div>
      <section className="mt-6 grid gap-3 md:grid-cols-3" aria-label="Scale Lab production proof">
        <ProofCard icon={Braces} label="Deterministic" detail="One seed reproduces every synthetic record and manifest checksum." />
        <ProofCard icon={DatabaseZap} label="Production-shaped" detail="Partitions, backpressure, quarantine, intelligence, and export run as bounded work." />
        <ProofCard icon={CircleDollarSign} label="Cost-gated" detail="The exact plan and hard cost ceiling are visible before any live resource starts." />
      </section>

      <section className="mt-6 rounded-xl border border-border bg-surface p-5 shadow-card">
        <ProfileSelector
          profiles={profiles}
          selected={selectedProfile}
          onSelect={(profileId) => {
            setSelectedProfile(profileId);
            setPlan(null);
            setActionError(null);
          }}
          disabled={launching}
        />
      </section>

      <PlanPreview
        plan={plan}
        loading={planLoading}
        seed={seed}
        onSeedChange={(value) => {
          setSeed(value);
          setPlan(null);
          setActionError(null);
        }}
        onRefresh={() => void previewPlan()}
        onLaunch={() => void launch()}
        launching={launching}
        runActive={runActive}
      />

      {actionError && (
        <div className="mt-4 flex items-start justify-between gap-3 rounded-lg border border-danger/35 bg-danger-soft px-4 py-3 text-xs text-danger" role="alert">
          <span className="flex items-start gap-2"><AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /><span><strong>Scale command failed.</strong> {actionError}</span></span>
          <button type="button" onClick={() => setActionError(null)} className="min-h-8 shrink-0 rounded-md px-2 text-[10px] font-bold hover:bg-white/45">Dismiss</button>
        </div>
      )}

      {run ? (
        <RunConsole
          run={run}
          staleMessage={staleMessage}
          lastGoodAt={lastGoodAt}
          onCancel={() => void cancel()}
          cancelling={cancelling}
          onRequestExport={() => void requestExport()}
          exportBusy={exportBusy}
          activeEvidenceSet={selectedEvidenceRunId === run.run_id}
          onUseInDecisionBrief={() => selectScaleRun(run.run_id)}
        />
      ) : (
        <section className="mt-6 rounded-xl border border-dashed border-border-strong bg-surface px-5 py-10 text-center" aria-label="No active scale run">
          <span className="mx-auto grid size-12 place-items-center rounded-full bg-gov-primary-lighter text-gov-primary"><Boxes className="size-5" aria-hidden /></span>
          <h2 className="mt-3 text-sm font-bold text-text-strong">Ready for a bounded production rehearsal</h2>
          <p className="mx-auto mt-2 max-w-xl text-xs leading-5 text-text-muted">Preview and launch a ready profile. This surface will retain the last good snapshot if live polling is interrupted.</p>
        </section>
      )}

      <RunHistory runs={runs} activeRunId={activeRunId} onSelect={openRun} />
      <ArchitectureDiagram />
    </div>
  );
}

function ProofCard({ icon: Icon, label, detail }: { icon: typeof Braces; label: string; detail: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-surface p-4 shadow-soft">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-gov-primary-lighter text-gov-primary"><Icon className="size-4" aria-hidden /></span>
      <div><p className="text-xs font-bold text-text-strong">{label}</p><p className="mt-1 text-[10.5px] leading-4 text-text-muted">{detail}</p></div>
    </div>
  );
}

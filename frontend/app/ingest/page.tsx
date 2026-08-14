"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  FileCheck2,
  FileWarning,
  Loader2,
  RefreshCw,
  RotateCcw,
  UploadCloud,
} from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { RoleGate } from "@/components/shell/role-gate";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { getIngestStatus } from "@/lib/api";
import {
  advanceSimulatedIngest,
  resetIngestReplay,
  simulateIngest,
  subscribeIngestReplay,
  type ScenarioProfile,
} from "@/lib/mock/ingest";
import type { IngestBatch } from "@/lib/types";
import { BatchRow } from "@/components/ingest/batch-row";
import { VelocityLegend } from "@/components/ingest/velocity-legend";
import { StreamTicker } from "@/components/ingest/stream-ticker";
import { DocumentDropZone } from "@/components/documents/document-drop-zone";
import { LiveIngestionWorkspace } from "@/components/ingest/live-ingestion-workspace";
import { useEvidenceMode } from "@/lib/evidence-mode-context";

const REPLAY_ACTIONS: {
  profile: ScenarioProfile;
  label: string;
  title: string;
  icon: typeof FileCheck2;
  tone: string;
}[] = [
  {
    profile: "clean",
    label: "Clean batch",
    title: "Replay a clean JSONL drop that passes every rule",
    icon: FileCheck2,
    tone: "border-success/40 bg-success-soft text-success hover:border-success",
  },
  {
    profile: "legacy",
    label: "Legacy JSON",
    title: "Replay a legacy JSON export that is normalized and passes with warnings",
    icon: UploadCloud,
    tone: "border-gold/50 bg-gold-soft text-gold-ink hover:border-gold",
  },
  {
    profile: "defective",
    label: "Defective batch",
    title: "Replay a defective drop that is quarantined with zero curated rows",
    icon: FileWarning,
    tone: "border-danger/40 bg-danger-soft text-danger hover:border-danger",
  },
];

export default function IngestPage() {
  const { mode } = useEvidenceMode();

  if (mode === "rehearsal") return <RehearsalIngestWorkspace />;

  return (
    <AppShell>
      <PageHeader
        kicker="Live public evidence | Ingestion and DataOps"
        title="Bring live public evidence into one governed path"
        lead="Continuous AWS schedules collect the verified public source registry without depending on an open browser. You can also upload one public, PII-minimized file and watch its exact hash-bound path into quality, classification, catalog, lineage, and decision support."
        icon={<UploadCloud className="size-4" aria-hidden />}
      />
      <div className="mt-6"><LiveIngestionWorkspace /></div>
    </AppShell>
  );
}

function RehearsalIngestWorkspace() {
  const auth = useAppAuth();
  const [batches, setBatches] = useState<IngestBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pendingProfile, setPendingProfile] = useState<ScenarioProfile | null>(null);
  const [newBatchIds, setNewBatchIds] = useState<string[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const pendingTimeouts = useRef<ReturnType<typeof setTimeout>[]>([]);

  const refresh = useCallback(async (opts: { silent?: boolean } = {}) => {
    if (!opts.silent) setRefreshing(true);
    try {
      const response = await getIngestStatus();
      setBatches(response.batches);
      setLastRefreshed(new Date());
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [auth.role, auth.orgUnit, refresh]);

  useEffect(() => {
    return subscribeIngestReplay(() => void refresh({ silent: true }));
  }, [refresh]);

  useEffect(() => {
    const timeouts = pendingTimeouts.current;
    return () => timeouts.forEach(clearTimeout);
  }, []);

  const handleSimulate = useCallback(
    async (profile: ScenarioProfile = "clean") => {
      setPendingProfile(profile);
      setActionError(null);
      try {
        const response = simulateIngest(profile);
        setNewBatchIds((current) => [response.batch_id, ...current].slice(0, 8));
        await refresh({ silent: true });

        const runningTimer = setTimeout(
          () => advanceSimulatedIngest(response.batch_id, "running"),
          650,
        );
        const completeTimer = setTimeout(
          () => advanceSimulatedIngest(response.batch_id, "completed"),
          1_850,
        );
        pendingTimeouts.current.push(runningTimer, completeTimer);
      } catch {
        setActionError("The rehearsal fixture could not be started. Reset the isolated rehearsal state and try again.");
      } finally {
        setPendingProfile(null);
      }
    },
    [refresh],
  );

  const handleReset = useCallback(async () => {
    pendingTimeouts.current.forEach(clearTimeout);
    pendingTimeouts.current = [];
    resetIngestReplay();
    setNewBatchIds([]);
    await refresh({ silent: true });
  }, [refresh]);

  const recentIds = new Set(newBatchIds);

  return (
    <AppShell>
      <PageHeader
        kicker="Explicit rehearsal | Ingestion, DataOps, and streaming"
        title="Rehearse a dropped document workflow"
        lead="Select a synthetic fixture or upload a rehearsal file, then follow its hash-bound local contract through event detection, extraction, schema inference, quality, classification, and publication. Every result remains labeled as rehearsal and is not presented as a live AWS run."
        icon={<UploadCloud className="size-4" aria-hidden />}
        actions={
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={refreshing}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-xs font-semibold text-text-muted transition-colors hover:border-border-strong hover:text-text-strong disabled:opacity-50"
          >
            <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} aria-hidden />
            Refresh
          </button>
        }
      />

      <RoleGate
        allow={["poweruser"]}
        fallback={
          <p className="mt-5 rounded-lg border border-border bg-surface-2 px-4 py-4 text-sm text-text-muted">
            Rehearsal document upload requires the corporate poweruser role. This scoped session can review existing rehearsal evidence without creating a new run.
          </p>
        }
      >
        <DocumentDropZone mode="rehearsal" />
      </RoleGate>

      <section
        aria-label="Deterministic replay controls"
        className="mt-5 rounded-xl border border-gov-primary/20 bg-gov-primary-lighter/50 p-4 shadow-soft"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-gov-primary px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white">
                Replay mode
              </span>
              <span className="text-xs font-semibold text-text-strong">Persistent synthetic scenario</span>
            </div>
            <p className="mt-2 max-w-2xl text-xs leading-5 text-text-muted">
              Actions are deterministic and saved in this browser. A failed gate always curates zero rows, and a reset restores the rehearsal baseline.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleReset()}
            disabled={pendingProfile !== null}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-xs font-semibold text-text-muted transition-colors hover:border-border-strong hover:text-text-strong disabled:opacity-50"
          >
            <RotateCcw className="size-3.5" aria-hidden />
            Reset replay
          </button>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          {REPLAY_ACTIONS.map((action) => {
            const Icon = action.icon;
            const pending = pendingProfile === action.profile;
            return (
              <button
                key={action.profile}
                type="button"
                title={action.title}
                onClick={() => void handleSimulate(action.profile)}
                disabled={pendingProfile !== null}
                className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-bold transition-all hover:-translate-y-0.5 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 ${action.tone}`}
              >
                {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Icon className="size-4" aria-hidden />}
                {action.label}
              </button>
            );
          })}
        </div>
      </section>

      {actionError ? (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-xs font-medium text-danger"
        >
          {actionError}
        </p>
      ) : null}

      <RoleGate allow={["poweruser"]}>
        <p className="mt-3 text-xs text-text-muted">
          Inspect every deployed stage, Lambda, retry, and evidence record in{" "}
          <Link
            href="/admin/pipeline/"
            className="inline-flex min-h-11 items-center gap-1 font-semibold text-gov-primary hover:underline"
          >
            Mission Control <ArrowUpRight className="size-3" aria-hidden />
          </Link>
          .
        </p>
      </RoleGate>

      <div className="mt-6 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <VelocityLegend />

          <section aria-label="Batch status">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-text-strong">Replay batch status</h2>
              {lastRefreshed ? (
                <span className="text-xs text-text-muted">Replay state synced</span>
              ) : null}
            </div>
            {loading ? (
              <div className="mt-3 space-y-2">
                {[0, 1, 2].map((index) => (
                  <div key={index} className="skeleton h-16 rounded-lg" />
                ))}
              </div>
            ) : batches.length === 0 ? (
              <p className="mt-3 rounded-lg border border-dashed border-border-strong bg-surface-2 px-4 py-6 text-center text-sm text-text-muted">
                No batches are visible for this org unit.
              </p>
            ) : (
              <ul className="mt-3 space-y-2" aria-live="polite">
                {batches.map((batch) => {
                  const isNew = recentIds.has(batch.batch_id);
                  return (
                    <BatchRow
                      key={batch.batch_id}
                      batch={batch}
                      velocity={isNew ? "on-demand" : undefined}
                      isNew={isNew}
                      defaultOpen={isNew}
                    />
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <div className="space-y-5">
          <StreamTicker />
        </div>
      </div>
    </AppShell>
  );
}

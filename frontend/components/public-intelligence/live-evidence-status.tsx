"use client";

import {
  CheckCircle2,
  Loader2,
  Pause,
  Play,
  RadioTower,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";

import type { ContinuousPublicAcquisitionControl } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { liveEvidenceStatusState } from "@/lib/public-intelligence/live-evidence-status-model";

export function LiveEvidenceStatus({
  control,
  healthySources,
  sourceCount,
  lastRefreshedAt,
  refreshing,
  controlling,
  error,
  onRefresh,
  onSetContinuous,
}: {
  control: ContinuousPublicAcquisitionControl | null;
  healthySources: number;
  sourceCount: number;
  lastRefreshedAt: string | null;
  refreshing: boolean;
  controlling: boolean;
  error: string | null;
  onRefresh: () => void;
  onSetContinuous: (enabled: boolean) => void;
}) {
  const auth = useAppAuth();
  const state = liveEvidenceStatusState(control, error);
  const running = state === "running";
  const stopped = state === "stopped";
  const verifying = state === "verifying";
  return (
    <section
      className={`overflow-hidden rounded-xl border shadow-card ${
        state === "attention" ? "border-danger/30 bg-danger-soft" : running ? "border-success/30 bg-success-soft/35" : stopped ? "border-warn/35 bg-warn-soft/45" : "border-info/25 bg-info-soft/35"
      }`}
      aria-label="Live public evidence status"
    >
      <div className="flex flex-wrap items-center justify-between gap-4 p-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className={`grid size-11 shrink-0 place-items-center rounded-lg text-white ${state === "attention" ? "bg-danger" : running ? "bg-success" : stopped ? "bg-warn" : "bg-info"}`}>
            {state === "attention" ? <TriangleAlert className="size-5" aria-hidden /> : running ? <RadioTower className="size-5" aria-hidden /> : stopped ? <Pause className="size-5" aria-hidden /> : <Loader2 className="size-5 animate-spin" aria-hidden />}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border bg-white px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${state === "attention" ? "border-danger/30 text-danger" : running ? "border-success/30 text-success" : stopped ? "border-warn/30 text-warn" : "border-info/30 text-info"}`}>
                {state === "attention" ? "Live service needs attention" : running ? "Continuous public acquisition running" : stopped ? "Continuous public acquisition stopped" : "Verifying acquisition control"}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-text-muted">
                {sourceCount > 0 ? <><CheckCircle2 className="size-3 text-success" aria-hidden /> {healthySources}/{sourceCount} sources healthy</> : verifying ? <><Loader2 className="size-3 animate-spin text-info" aria-hidden /> Source health verifying</> : <><TriangleAlert className="size-3 text-warn" aria-hidden /> Source health unknown</>}
              </span>
            </div>
            <p className="mt-2 text-xs leading-5 text-text-muted">
              {state === "attention"
                ? error
                : running
                  ? "AWS schedules pull each named authority at its responsible cadence. This screen refreshes retained receipts without repeatedly calling the public APIs."
                  : stopped
                    ? "Scheduled pulls are paused. Existing accepted snapshots remain available and manual source runs are still possible for power users."
                    : "Waiting for the protected controller receipt. Compass does not claim that acquisition is running or stopped until that receipt is verified."}
            </p>
            <p className="mt-1 font-mono text-[9px] text-text-subtle">
              {lastRefreshedAt ? `Screen receipt refreshed ${new Date(lastRefreshedAt).toLocaleTimeString()}` : verifying ? "Verifying protected source receipts" : "Protected source receipt unavailable"}
              {control?.updated_by ? ` | last control by ${control.updated_by}` : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing || controlling}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-bold text-text-muted hover:bg-surface-2 disabled:opacity-50"
          >
            <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden />
            Refresh receipts
          </button>
          {auth.role === "poweruser" ? (
            <button
              type="button"
              onClick={() => onSetContinuous(stopped)}
              disabled={controlling || !control || state === "attention"}
              className={`inline-flex min-h-11 items-center gap-2 rounded-md px-4 text-xs font-bold text-white disabled:opacity-50 ${running ? "bg-warn hover:brightness-95" : verifying || state === "attention" ? "bg-info" : "bg-success hover:brightness-95"}`}
            >
              {controlling || verifying ? <Loader2 className="size-4 animate-spin" aria-hidden /> : running ? <Pause className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}
              {controlling ? "Updating" : verifying ? "Waiting for control receipt" : running ? "Stop continuous pulls" : "Start continuous pulls"}
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

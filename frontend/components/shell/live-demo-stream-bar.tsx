"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FlaskConical,
  Loader2,
  Play,
  RadioTower,
  RotateCcw,
  Square,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getLiveDemoStream,
  postLiveDemoStreamStart,
  postLiveDemoStreamStop,
  setAuthContext,
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { publishLiveDemoStreamTick } from "@/lib/live-demo-stream-events";
import { useMissionDataContext } from "@/lib/mission-data-context";
import type { LiveDemoStreamResponse } from "@/lib/types";
import { liveDemoStreamReceiptKey } from "./live-demo-stream-model";

const DEFAULT_CADENCE_SECONDS = 2 as const;
const ACTIVE_POLL_MS = 1_000;
const IDLE_POLL_MS = 15_000;
const PROJECTION_SETTLE_MS = 2_500;

export function LiveDemoStreamBar() {
  const auth = useAppAuth();
  const { hydrated, selection, selectCurated } = useMissionDataContext();
  const [data, setData] = useState<LiveDemoStreamResponse | null>(null);
  const [cadence, setCadence] = useState<1 | 2>(DEFAULT_CADENCE_SECONDS);
  const [pending, setPending] = useState<"start" | "stop" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clockMs, setClockMs] = useState(() => Date.now());
  const lastReceiptKey = useRef<string | null>(null);
  const projectionSettleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const status = data?.session.status ?? "idle";

  const publishAuth = useCallback(() => {
    setAuthContext({ bearerToken: auth.idToken, role: auth.role, orgUnit: auth.orgUnit });
  }, [auth.idToken, auth.orgUnit, auth.role]);

  const applyResponse = useCallback((response: LiveDemoStreamResponse) => {
    setData(response);
    setError(null);
    const key = liveDemoStreamReceiptKey(response);
    if (!key || key === lastReceiptKey.current || !response.latest_event || !response.session.session_id) return;
    lastReceiptKey.current = key;
    publishLiveDemoStreamTick({
      sessionId: response.session.session_id,
      sequence: response.latest_event.sequence,
      runId: response.latest_event.run_id,
      occurredAt: response.latest_event.occurred_at,
    });
    if (projectionSettleTimer.current) clearTimeout(projectionSettleTimer.current);
    projectionSettleTimer.current = setTimeout(() => {
      if (!response.latest_event || !response.session.session_id) return;
      publishLiveDemoStreamTick({
        sessionId: response.session.session_id,
        sequence: response.latest_event.sequence,
        runId: response.latest_event.run_id,
        occurredAt: response.latest_event.occurred_at,
      });
    }, PROJECTION_SETTLE_MS);
  }, []);

  useEffect(() => () => {
    if (projectionSettleTimer.current) clearTimeout(projectionSettleTimer.current);
  }, []);

  useEffect(() => {
    if (status !== "running") return;
    const timer = setInterval(() => setClockMs(Date.now()), 1_000);
    return () => clearInterval(timer);
  }, [status]);

  const load = useCallback(async () => {
    if (auth.isLoading) return null;
    publishAuth();
    try {
      const response = await getLiveDemoStream();
      applyResponse(response);
      return response;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Live update status is unavailable.");
      return null;
    }
  }, [applyResponse, auth.isLoading, publishAuth]);

  useEffect(() => {
    if (auth.isLoading) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      const response = await load();
      if (cancelled) return;
      const running = response?.session.status === "running";
      timer = setTimeout(() => void poll(), running ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [auth.isLoading, load, status]);

  const start = async () => {
    publishAuth();
    setPending("start");
    setError(null);
    try {
      lastReceiptKey.current = null;
      applyResponse(await postLiveDemoStreamStart({
        cadence_seconds: cadence,
        stream_mode: "continuous",
      }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Live updates could not start.");
    } finally {
      setPending(null);
    }
  };

  const stop = async () => {
    const sessionId = data?.session.session_id;
    if (!sessionId) return;
    publishAuth();
    setPending("stop");
    setError(null);
    try {
      applyResponse(await postLiveDemoStreamStop({ session_id: sessionId }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Live updates could not stop.");
    } finally {
      setPending(null);
    }
  };

  const running = status === "running";
  const session = data?.session;
  const elapsed = formatElapsed(session?.started_at ?? null, clockMs);
  const scaleSelected = hydrated && selection.kind === "scale";

  return (
    <section
      aria-label="Live demo data"
      aria-live="polite"
      className={`border-b px-4 py-2.5 sm:px-6 xl:px-8 ${
        running ? "border-info/35 bg-info-soft" : "border-border bg-white"
      }`}
    >
      <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-3 lg:flex-row lg:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className={`relative grid size-9 shrink-0 place-items-center rounded-lg ${
            running ? "bg-info text-white" : "bg-gov-primary-lighter text-gov-primary"
          }`}>
            {running ? (
              <>
                <span className="absolute inset-1 rounded-md bg-white/25 motion-safe:animate-ping" aria-hidden />
                <RadioTower className="relative size-4" aria-hidden />
              </>
            ) : scaleSelected ? <Database className="size-4" aria-hidden /> : <FlaskConical className="size-4" aria-hidden />}
          </span>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs font-bold text-text-strong">{scaleSelected ? "Scale test selected" : "Live demo data"}</p>
              {!scaleSelected ? <StatusBadge status={status} /> : null}
              <span className="rounded-full border border-success/30 bg-success-soft px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-success">Safe synthetic data</span>
            </div>
            <p className="mt-0.5 text-[11px] leading-4 text-text-muted">
              {scaleSelected
                ? `Viewing ${selection.runId}. Return to the demo portfolio to use live updates.`
                : running
                  ? `${session?.emitted_events.toLocaleString() ?? 0} new ${session?.emitted_events === 1 ? "record" : "records"} | every ${session?.cadence_seconds ?? cadence} ${session?.cadence_seconds === 1 ? "second" : "seconds"} | live for ${elapsed}`
                  : session && session.emitted_events > 0
                    ? `Last session added ${session.emitted_events.toLocaleString()} records. Start again to keep the portfolio changing.`
                    : "Adds one sample research award at a time and updates the dashboard, trusted data, and history."}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          {error ? (
            <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-danger">
              <AlertTriangle className="size-3.5" aria-hidden /> Live status unavailable
            </span>
          ) : null}
          {scaleSelected ? (
            <button
              type="button"
              onClick={selectCurated}
              className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-[10px] font-bold text-text-strong hover:bg-surface-2"
            >
              <RotateCcw className="size-3.5" aria-hidden /> Use demo portfolio
            </button>
          ) : null}
          {auth.role === "poweruser" && !running && !scaleSelected ? (
            <>
              <label className="sr-only" htmlFor="demo-stream-cadence">Synthetic stream cadence</label>
              <select
                id="demo-stream-cadence"
                value={cadence}
                onChange={(event) => setCadence(event.target.value === "1" ? 1 : 2)}
                disabled={pending !== null}
                className="min-h-10 rounded-md border border-border bg-white px-2 text-[10px] font-bold text-text-muted"
              >
                <option value="2">Every 2 seconds</option>
                <option value="1">Every second</option>
              </select>
              <button
                type="button"
                onClick={() => void start()}
                disabled={pending !== null || auth.isLoading}
                className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-[10px] font-bold text-white transition-colors hover:bg-gov-primary-dark disabled:opacity-50"
              >
                {pending === "start" ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Play className="size-3.5" aria-hidden />}
                Start live updates
              </button>
            </>
          ) : null}
          {auth.role === "poweruser" && running && !scaleSelected ? (
            <button
              type="button"
              onClick={() => void stop()}
              disabled={pending !== null}
              className="inline-flex min-h-10 items-center gap-2 rounded-md border border-danger/30 bg-white px-3 text-[10px] font-bold text-danger transition-colors hover:bg-danger-soft disabled:opacity-50"
            >
              {pending === "stop" ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Square className="size-3.5" aria-hidden />}
              Stop live updates
            </button>
          ) : null}
          <Link href="/ingest/" className="inline-flex min-h-10 items-center rounded-md px-2 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter">
            See how data moves
          </Link>
        </div>
      </div>
    </section>
  );
}

function formatElapsed(startedAt: string | null, nowMs: number): string {
  if (!startedAt) return "0:00";
  const startMs = Date.parse(startedAt);
  if (!Number.isFinite(startMs)) return "0:00";
  const totalSeconds = Math.max(0, Math.floor((nowMs - startMs) / 1_000));
  const hours = Math.floor(totalSeconds / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
    : `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function StatusBadge({ status }: { status: LiveDemoStreamResponse["session"]["status"] }) {
  if (status === "running") {
    return <span className="rounded-full border border-info/30 bg-white px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-info">Updating now</span>;
  }
  if (status === "completed") {
    return <span className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success-soft px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-success"><CheckCircle2 className="size-3" aria-hidden /> Complete</span>;
  }
  if (status === "failed") {
    return <span className="rounded-full border border-danger/30 bg-danger-soft px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-danger">Failed</span>;
  }
  return <span className="rounded-full border border-border bg-surface-2 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-text-muted">{status === "stopped" || status === "idle" ? "Updates stopped" : status}</span>;
}

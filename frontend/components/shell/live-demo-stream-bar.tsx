"use client";

import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  Loader2,
  Play,
  RadioTower,
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
import type { LiveDemoStreamResponse } from "@/lib/types";
import { liveDemoStreamProgress, liveDemoStreamReceiptKey } from "./live-demo-stream-model";

const DEFAULT_CADENCE_SECONDS = 2 as const;
const DEFAULT_TOTAL_EVENTS = 15;
const ACTIVE_POLL_MS = 1_000;
const IDLE_POLL_MS = 15_000;
const PROJECTION_SETTLE_MS = 2_500;

export function LiveDemoStreamBar() {
  const auth = useAppAuth();
  const [data, setData] = useState<LiveDemoStreamResponse | null>(null);
  const [cadence, setCadence] = useState<1 | 2>(DEFAULT_CADENCE_SECONDS);
  const [pending, setPending] = useState<"start" | "stop" | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  const load = useCallback(async () => {
    if (auth.isLoading) return null;
    publishAuth();
    try {
      const response = await getLiveDemoStream();
      applyResponse(response);
      return response;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The accelerated stream status is unavailable.");
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
        total_events: DEFAULT_TOTAL_EVENTS,
      }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The accelerated stream could not start.");
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
      setError(cause instanceof Error ? cause.message : "The accelerated stream could not stop.");
    } finally {
      setPending(null);
    }
  };

  const running = status === "running";
  const progress = data ? liveDemoStreamProgress(data) : 0;
  const session = data?.session;
  const durationSeconds = cadence * DEFAULT_TOTAL_EVENTS;

  return (
    <section
      aria-label="Accelerated synthetic demo stream"
      aria-live="polite"
      className={`border-b px-4 py-3 sm:px-6 xl:px-8 ${
        running ? "border-info/30 bg-info-soft/55" : "border-border bg-white"
      }`}
    >
      <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-3 xl:flex-row xl:items-center">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <span className={`relative grid size-10 shrink-0 place-items-center rounded-lg ${
            running ? "bg-info text-white" : "bg-gov-primary-lighter text-gov-primary"
          }`}>
            {running ? (
              <>
                <span className="absolute inset-1 rounded-md bg-white/25 motion-safe:animate-ping" aria-hidden />
                <RadioTower className="relative size-4" aria-hidden />
              </>
            ) : <FlaskConical className="size-4" aria-hidden />}
          </span>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-strong">
                Accelerated synthetic stream
              </p>
              <StatusBadge status={status} />
              {session && session.total_events > 0 ? (
                <span className="font-mono text-[10px] font-bold text-text-muted">
                  {session.emitted_events}/{session.total_events} receipts | {session.cadence_seconds}s cadence
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-[10.5px] leading-4 text-text-muted">
              Synthetic drops use the deployed S3, EventBridge, intake, quality, lineage, catalog, and decision path. Official USAspending acquisition keeps its bounded source cadence.
            </p>
            {data?.latest_event ? (
              <p className="mt-1 truncate font-mono text-[9px] text-info" title={data.latest_event.message}>
                Latest receipt {data.latest_event.sequence}: {data.latest_event.run_id ?? data.latest_event.event_id}
              </p>
            ) : null}
            {running ? (
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/80" aria-label={`${progress}% complete`}>
                <div className="h-full rounded-full bg-info transition-[width] duration-500" style={{ width: `${progress}%` }} />
              </div>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
          {error ? (
            <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-danger">
              <AlertTriangle className="size-3.5" aria-hidden /> Status unavailable
            </span>
          ) : null}
          {auth.role === "poweruser" && !running ? (
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
                <option value="1">Every 1 second</option>
              </select>
              <button
                type="button"
                onClick={() => void start()}
                disabled={pending !== null || auth.isLoading}
                className="inline-flex min-h-10 items-center gap-2 rounded-md bg-gov-primary px-3 text-[10px] font-bold text-white transition-colors hover:bg-gov-primary-dark disabled:opacity-50"
              >
                {pending === "start" ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Play className="size-3.5" aria-hidden />}
                Start {durationSeconds}s stream
              </button>
            </>
          ) : null}
          {auth.role === "poweruser" && running ? (
            <button
              type="button"
              onClick={() => void stop()}
              disabled={pending !== null}
              className="inline-flex min-h-10 items-center gap-2 rounded-md border border-danger/30 bg-white px-3 text-[10px] font-bold text-danger transition-colors hover:bg-danger-soft disabled:opacity-50"
            >
              {pending === "stop" ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Square className="size-3.5" aria-hidden />}
              Stop stream
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: LiveDemoStreamResponse["session"]["status"] }) {
  if (status === "running") {
    return <span className="rounded-full border border-info/30 bg-white px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-info">Live now</span>;
  }
  if (status === "completed") {
    return <span className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success-soft px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-success"><CheckCircle2 className="size-3" aria-hidden /> Complete</span>;
  }
  if (status === "failed") {
    return <span className="rounded-full border border-danger/30 bg-danger-soft px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-danger">Failed</span>;
  }
  return <span className="rounded-full border border-border bg-surface-2 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-text-muted">{status}</span>;
}

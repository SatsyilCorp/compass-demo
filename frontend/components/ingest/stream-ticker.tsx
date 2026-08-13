"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ShieldCheck,
  TriangleAlert,
  Sparkles,
  CheckCircle2,
  DownloadCloud,
  RadioTower,
  type LucideIcon,
} from "lucide-react";
import { getStreamRecent, USE_MOCK } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { subscribeLiveDemoStreamTick } from "@/lib/live-demo-stream-events";
import type { StreamRecord } from "@/lib/types";

const KIND_ICON: Record<StreamRecord["kind"], LucideIcon> = {
  ingest: ArrowDownToLine,
  quality: ShieldCheck,
  anomaly: TriangleAlert,
  analytics: Sparkles,
  approval: CheckCircle2,
  export: DownloadCloud,
  "public-feed": RadioTower,
};

const KIND_TONE: Record<StreamRecord["kind"], string> = {
  ingest: "text-gov-primary",
  quality: "text-success",
  anomaly: "text-danger",
  analytics: "text-info",
  approval: "text-gold-ink",
  export: "text-text-muted",
  "public-feed": "text-info",
};

const POLL_MS = 5000;

function timeAgo(iso: string, now: number): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.round(m / 60)}h ago`;
}

/** Small streaming ticker: polls GET /stream/recent on an interval. Element 3. */
export function StreamTicker() {
  const { role, orgUnit } = useAppAuth();
  const [records, setRecords] = useState<StreamRecord[]>([]);
  const [now, setNow] = useState<number>(() => Date.now());
  const [pulsing, setPulsing] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const pulseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = (await getStreamRecent()) as Awaited<ReturnType<typeof getStreamRecent>> & {
          replay?: { generated_at: string };
        };
        if (cancelled) return;
        setRecords(res.records);
        setNow(res.replay ? new Date(res.replay.generated_at).getTime() : Date.now());
        setPulsing(true);
        if (pulseTimer.current) clearTimeout(pulseTimer.current);
        pulseTimer.current = setTimeout(() => setPulsing(false), 600);
      } catch {
        // Best-effort ticker. A failed poll just waits for the next tick.
      }
    }
    void poll();
    const unsubscribe = subscribeLiveDemoStreamTick(() => void poll());
    pollTimer.current = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      unsubscribe();
      if (pollTimer.current) clearInterval(pollTimer.current);
      if (pulseTimer.current) clearTimeout(pulseTimer.current);
    };
  }, [role, orgUnit]);

  // Live responses tick between polls. Replay responses reset this value to
  // their deterministic scenario clock on every poll.
  useEffect(() => {
    if (USE_MOCK) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <section aria-label="Recent streaming activity" className="rounded-lg border border-border bg-surface shadow-card">
      <header className="flex items-center justify-between gap-2 border-b border-border-2 px-4 py-2.5">
        <p className="flex items-center gap-2 text-[12px] font-semibold text-text-strong">
          <span className="relative flex size-2">
            <span
              className={`absolute inline-flex h-full w-full rounded-full bg-gov-secondary opacity-60 ${pulsing ? "animate-ping" : ""}`}
            />
            <span className="relative inline-flex size-2 rounded-full bg-gov-secondary" />
          </span>
          <code className="font-mono">GET /stream/recent</code>
        </p>
        <span className="text-[10.5px] text-text-subtle">every {POLL_MS / 1000}s</span>
      </header>
      <ul
        className="max-h-[26rem] divide-y divide-border-2 overflow-y-auto"
        tabIndex={0}
        aria-label="Scrollable recent activity"
      >
        {records.length === 0 && (
          <li className="px-4 py-6 text-center text-[12px] text-text-muted">Waiting for the first poll…</li>
        )}
        {records.map((r) => {
          const Icon = KIND_ICON[r.kind];
          return (
            <li key={r.id} className="flex items-start gap-2.5 px-4 py-2 text-[12px]">
              <Icon className={`mt-0.5 size-3.5 shrink-0 ${KIND_TONE[r.kind]}`} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-text-strong">{r.message}</span>
                <span className="text-[10.5px] text-text-subtle">
                  {timeAgo(r.at, now)}
                  {r.org_unit ? ` · ${r.org_unit}` : ""}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

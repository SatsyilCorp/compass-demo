"use client";

import Link from "next/link";
import {
  AlertTriangle,
  Bell,
  BellRing,
  Check,
  CheckCircle2,
  CircleAlert,
  ExternalLink,
  Info,
  Loader2,
  Mail,
  Radio,
  RefreshCcw,
  Webhook,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getOperationsSignals,
  postOperationsSignalAcknowledge,
  setAuthContext,
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import type {
  OperationsSignal,
  OperationsSignalDelivery,
  OperationsSignalsResponse,
} from "@/lib/types";
import { applySignalAcknowledgement } from "./model";

const POLL_MS = 10_000;

const SEVERITY: Record<OperationsSignal["severity"], {
  icon: LucideIcon;
  label: string;
  card: string;
  iconClass: string;
}> = {
  critical: {
    icon: CircleAlert,
    label: "Critical",
    card: "border-danger/35 bg-danger-soft/45",
    iconClass: "bg-danger text-white",
  },
  warning: {
    icon: AlertTriangle,
    label: "Warning",
    card: "border-warn/35 bg-warn-soft/55",
    iconClass: "bg-warn text-white",
  },
  info: {
    icon: Info,
    label: "Information",
    card: "border-info/25 bg-info-soft/55",
    iconClass: "bg-info text-white",
  },
};

const CHANNEL_ICON: Record<OperationsSignalDelivery["channel"], LucideIcon> = {
  in_app: Bell,
  email: Mail,
  sns: Radio,
  webhook: Webhook,
};

export function NotificationCenter() {
  const auth = useAppAuth();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<OperationsSignalsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState<Set<string>>(() => new Set());
  const closeRef = useRef<HTMLButtonElement>(null);

  const load = useCallback(async (initial = false) => {
    if (auth.isLoading) return;
    setAuthContext({ bearerToken: auth.idToken, role: auth.role, orgUnit: auth.orgUnit });
    if (initial) setLoading(true);
    try {
      const response = await getOperationsSignals();
      setData(response);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Operations signals are unavailable.");
    } finally {
      if (initial) setLoading(false);
    }
  }, [auth.idToken, auth.isLoading, auth.orgUnit, auth.role]);

  useEffect(() => {
    if (auth.isLoading) return;
    void load(true);
    const timer = window.setInterval(() => void load(false), POLL_MS);
    return () => window.clearInterval(timer);
  }, [auth.isLoading, load]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const acknowledge = async (eventId: string) => {
    setAuthContext({ bearerToken: auth.idToken, role: auth.role, orgUnit: auth.orgUnit });
    setAcknowledging((current) => new Set(current).add(eventId));
    try {
      const receipt = await postOperationsSignalAcknowledge(eventId);
      setData((current) => current ? applySignalAcknowledgement(current, receipt) : current);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The signal could not be acknowledged.");
    } finally {
      setAcknowledging((current) => {
        const next = new Set(current);
        next.delete(eventId);
        return next;
      });
    }
  };

  const unread = data?.unread_count ?? 0;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={unread > 0 ? `Open notifications, ${unread} unread` : "Open notifications"}
        aria-haspopup="dialog"
        aria-expanded={open}
        className="relative grid size-11 shrink-0 place-items-center rounded-md border border-border bg-surface text-text-muted transition-colors hover:bg-surface-2 hover:text-text-strong"
      >
        {unread > 0 ? <BellRing className="size-4.5" aria-hidden /> : <Bell className="size-4.5" aria-hidden />}
        {unread > 0 ? (
          <span className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full border-2 border-white bg-danger px-1 font-mono text-[9px] font-bold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
        {error && !data ? <span className="absolute bottom-1 right-1 size-2 rounded-full bg-warn" aria-hidden /> : null}
      </button>

      {open ? (
        <div className="fixed inset-0 z-[70]">
          <button
            type="button"
            className="absolute inset-0 min-h-11 w-full bg-gov-primary-darker/55 backdrop-blur-[2px]"
            onClick={() => setOpen(false)}
            aria-label="Close notifications"
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-labelledby="operations-notifications-title"
            className="compass-drawer-enter absolute inset-y-0 right-0 flex w-[min(94vw,500px)] flex-col border-l border-border bg-bg shadow-2xl"
          >
            <div className="border-b border-border bg-gov-primary px-5 py-5 text-white">
              <div className="flex items-start gap-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-lg border border-white/15 bg-white/10">
                  <BellRing className="size-5 text-gold-light" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 id="operations-notifications-title" className="text-base font-bold">Operations signals</h2>
                    {data ? <ModeBadge mode={data.mode} /> : null}
                  </div>
                  <p className="mt-1 text-[10.5px] leading-4 text-white/65">Workflow outcomes, model drift, acquisition health, and delivery state.</p>
                </div>
                <button
                  ref={closeRef}
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close notifications"
                  className="grid size-10 shrink-0 place-items-center rounded-md text-white/70 hover:bg-white/10 hover:text-white"
                >
                  <X className="size-5" aria-hidden />
                </button>
              </div>
              <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/10 pt-3">
                <p className="font-mono text-[10px] text-white/65">{unread} unread | {data?.signals.length ?? 0} retained</p>
                <button
                  type="button"
                  onClick={() => void load(false)}
                  className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/15 bg-white/10 px-3 text-[10px] font-bold text-white hover:bg-white/15"
                >
                  <RefreshCcw className="size-3.5" aria-hidden /> Refresh
                </button>
              </div>
            </div>

            {error ? (
              <div role="alert" className="m-4 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft p-3 text-xs leading-5 text-danger">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>{error}{data ? " The last good signal set remains visible." : ""}</span>
              </div>
            ) : null}

            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {loading && !data ? (
                <div className="grid min-h-48 place-items-center text-center text-text-muted">
                  <div><Loader2 className="mx-auto size-6 animate-spin text-gov-primary" aria-hidden /><p className="mt-3 text-xs">Loading retained signals</p></div>
                </div>
              ) : data && data.signals.length > 0 ? (
                <div className="space-y-3">
                  {data.signals.map((signal) => (
                    <SignalCard
                      key={signal.event_id}
                      signal={signal}
                      pending={acknowledging.has(signal.event_id)}
                      onAcknowledge={acknowledge}
                      onNavigate={() => setOpen(false)}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-white p-8 text-center">
                  <CheckCircle2 className="mx-auto size-7 text-success" aria-hidden />
                  <p className="mt-3 text-sm font-bold text-text-strong">No retained signals</p>
                  <p className="mt-1 text-xs text-text-muted">New workflow and monitoring events will appear here.</p>
                </div>
              )}
            </div>

            <div className="border-t border-border bg-white px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[9.5px] leading-4 text-text-subtle">{data?.disclosure ?? "Signals are loaded from the protected operations interface."}</p>
                <Link href="/admin/lineage/" onClick={() => setOpen(false)} className="inline-flex min-h-10 shrink-0 items-center gap-2 rounded-md border border-gov-primary/25 px-3 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter">
                  All runs <ExternalLink className="size-3" aria-hidden />
                </Link>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

function SignalCard({
  signal,
  pending,
  onAcknowledge,
  onNavigate,
}: {
  signal: OperationsSignal;
  pending: boolean;
  onAcknowledge: (eventId: string) => Promise<void>;
  onNavigate: () => void;
}) {
  const meta = SEVERITY[signal.severity];
  const Icon = meta.icon;
  const open = signal.status === "open";
  return (
    <article className={`overflow-hidden rounded-xl border ${open ? meta.card : "border-border bg-white opacity-80"}`}>
      <div className="p-4">
        <div className="flex items-start gap-3">
          <span className={`grid size-9 shrink-0 place-items-center rounded-md ${open ? meta.iconClass : "bg-surface-3 text-text-muted"}`}>
            {signal.status === "acknowledged" ? <Check className="size-4" aria-hidden /> : <Icon className="size-4" aria-hidden />}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[9px] font-bold uppercase tracking-wide text-text-subtle">{meta.label}</span>
              <span className={`rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase ${open ? "border-gov-primary/20 bg-white text-gov-primary" : "border-success/25 bg-success-soft text-success"}`}>{signal.status}</span>
            </div>
            <h3 className="mt-1 text-xs font-bold leading-5 text-text-strong">{signal.title}</h3>
            <p className="mt-1 text-[10.5px] leading-5 text-text-muted">{signal.message}</p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-current/10 pt-3 font-mono text-[8.5px] text-text-subtle">
          <span>{formatTimestamp(signal.occurred_at)}</span>
          <span>{signal.source}</span>
          {signal.run_id ? <span>{signal.run_id}</span> : null}
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {signal.deliveries.map((delivery) => <DeliveryChip key={`${signal.event_id}-${delivery.channel}`} delivery={delivery} />)}
        </div>
      </div>
      <div className="flex items-center gap-2 border-t border-border/80 bg-white/80 px-3 py-2">
        {signal.href ? (
          <Link href={signal.href} onClick={onNavigate} className="inline-flex min-h-10 items-center gap-1.5 rounded-md px-2 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter">
            Open evidence <ExternalLink className="size-3" aria-hidden />
          </Link>
        ) : <span className="flex-1" />}
        {open ? (
          <button
            type="button"
            onClick={() => void onAcknowledge(signal.event_id)}
            disabled={pending}
            className="ml-auto inline-flex min-h-10 items-center gap-1.5 rounded-md border border-border bg-white px-3 text-[10px] font-bold text-text-strong hover:bg-surface-2 disabled:cursor-wait disabled:opacity-55"
          >
            {pending ? <Loader2 className="size-3 animate-spin" aria-hidden /> : <Check className="size-3" aria-hidden />}
            Acknowledge
          </button>
        ) : (
          <span className="ml-auto text-[9px] text-text-subtle">Acknowledged {signal.acknowledged_at ? formatTimestamp(signal.acknowledged_at) : ""}</span>
        )}
      </div>
    </article>
  );
}

function DeliveryChip({ delivery }: { delivery: OperationsSignalDelivery }) {
  const Icon = CHANNEL_ICON[delivery.channel];
  const stateClass = delivery.state === "delivered"
    ? "border-success/25 bg-success-soft text-success"
    : delivery.state === "failed"
      ? "border-danger/30 bg-danger-soft text-danger"
      : delivery.state === "pending" || delivery.state === "published" || delivery.state === "recorded"
        ? "border-info/25 bg-info-soft text-info"
        : "border-border bg-surface-2 text-text-subtle";
  return (
    <span title={delivery.detail ?? undefined} className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[8px] font-bold uppercase ${stateClass}`}>
      <Icon className="size-2.5" aria-hidden /> {delivery.channel.replace("_", " ")} | {delivery.state.replace("_", " ")}
    </span>
  );
}

function ModeBadge({ mode }: { mode: OperationsSignalsResponse["mode"] }) {
  return <span className={`rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase tracking-wide ${mode === "live" ? "border-success/30 bg-success/10 text-emerald-100" : "border-warn/35 bg-warn/10 text-amber-100"}`}>{mode === "live" ? "Live AWS" : "Replay fixture"}</span>;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

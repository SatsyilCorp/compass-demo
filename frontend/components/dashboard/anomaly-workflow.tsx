"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  AlertTriangle,
  Check,
  CircleAlert,
  FileText,
  Loader2,
  Lock,
  RotateCcw,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";

import { getAnomalies, postApprovals, postChat } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import type { Anomaly, Approval, ChatCitation } from "@/lib/types";

import { useCompassAction, useCompassQuery } from "./use-compass-query";
import { dateTimeShort } from "./format";

/**
 * Anomaly → summary → approval (element 6).
 *
 * The three calls are real contract calls, in order:
 *   1. `GET /anomalies`   — the detection surface (rows written by the quality
 *                           gate, scoped by RLS like everything else).
 *   2. `POST /chat`       — an LLM triage note about the selected anomaly,
 *                           grounded on the grants it can cite.
 *   3. `POST /approvals`  — `request`, then `approve` / `reject`. The decision
 *                           step is gated to the power-user persona; a viewer
 *                           can raise an approval but cannot decide it.
 *
 * The stage chip on the left list and the stepper on the right both move as
 * the record moves, so the state change is visible rather than described. What
 * the UI holds in local state is the *narrative thread* (which anomaly is
 * being worked, its draft note); the authoritative record is the `approvals`
 * row returned by the API and shown verbatim.
 */
type Stage = "detected" | "summarized" | "pending" | "approved" | "rejected";

type WorkItem = {
  stage: Stage;
  summary?: string;
  citations?: ChatCitation[];
  model?: string;
  approval?: Approval;
};

const SEVERITY_STYLE: Record<Anomaly["severity"], string> = {
  low: "bg-surface-2 text-text-muted border-border",
  medium: "bg-warn-soft text-warn border-warn",
  high: "bg-warn-soft text-warn border-warn",
  critical: "bg-danger-soft text-danger border-danger",
};

const STAGE_LABEL: Record<Stage, string> = {
  detected: "Open",
  summarized: "Summarized",
  pending: "Approval pending",
  approved: "Approved",
  rejected: "Rejected",
};

const STAGE_STYLE: Record<Stage, string> = {
  detected: "bg-surface-2 text-text-muted",
  summarized: "bg-info-soft text-info",
  pending: "bg-warn-soft text-warn",
  approved: "bg-success-soft text-success",
  rejected: "bg-danger-soft text-danger",
};

const STEPS: { key: Stage; title: string }[] = [
  { key: "detected", title: "Detected" },
  { key: "summarized", title: "Summarized" },
  { key: "pending", title: "Approval requested" },
  { key: "approved", title: "Decided" },
];

const STAGE_ORDER: Record<Stage, number> = {
  detected: 0,
  summarized: 1,
  pending: 2,
  approved: 3,
  rejected: 3,
};

export function AnomalyWorkflow() {
  const { role } = useAppAuth();
  const canDecide = role === "poweruser";

  const anomalies = useCompassQuery(getAnomalies);
  const chat = useCompassAction(postChat);
  const approvals = useCompassAction(postApprovals);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [work, setWork] = useState<Record<number, WorkItem>>({});

  const rows = useMemo(() => {
    const list = anomalies.data?.anomalies ?? [];
    const rank: Record<Anomaly["status"], number> = { open: 0, acknowledged: 1, resolved: 2 };
    const sev: Record<Anomaly["severity"], number> = { critical: 0, high: 1, medium: 2, low: 3 };
    return list
      .slice()
      .sort((a, b) => rank[a.status] - rank[b.status] || sev[a.severity] - sev[b.severity]);
  }, [anomalies.data]);

  const selected = rows.find((a) => a.id === selectedId) ?? rows[0] ?? null;
  const item: WorkItem = selected ? (work[selected.id] ?? { stage: "detected" }) : { stage: "detected" };

  function patch(id: number, next: Partial<WorkItem>) {
    setWork((prev) => ({ ...prev, [id]: { ...(prev[id] ?? { stage: "detected" }), ...next } }));
  }

  async function draftSummary(a: Anomaly) {
    try {
      const res = await chat.run({
        message:
          `An automated quality check flagged grant ${a.grant_no ?? a.grant_id} with anomaly type ` +
          `"${a.kind}" (severity ${a.severity}). Reason on file: ${a.reason} ` +
          `Write a two-sentence triage note for a program officer: what the finding means and what ` +
          `to check before approving a disposition.`,
      });
      patch(a.id, {
        stage: "summarized",
        summary: res.answer,
        citations: res.citations,
        model: res.model,
      });
    } catch {
      /* surfaced via chat.error */
    }
  }

  async function requestApproval(a: Anomaly) {
    const note = work[a.id]?.summary?.slice(0, 280);
    try {
      const res = await approvals.run({
        subject_type: "anomaly",
        subject_id: String(a.id),
        action: "request",
        note,
      });
      patch(a.id, { stage: "pending", approval: res.approval });
    } catch {
      /* surfaced via approvals.error */
    }
  }

  async function decide(a: Anomaly, action: "approve" | "reject") {
    try {
      const res = await approvals.run({
        subject_type: "anomaly",
        subject_id: String(a.id),
        action,
        note: work[a.id]?.summary?.slice(0, 280),
      });
      patch(a.id, {
        stage: res.approval.state === "approved" ? "approved" : "rejected",
        approval: res.approval,
      });
    } catch {
      /* surfaced via approvals.error */
    }
  }

  return (
    <section className="compass-rise rounded-md border border-border bg-surface shadow-soft">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded bg-gov-primary text-white">
            <CircleAlert className="size-4" aria-hidden />
          </span>
          <div>
            <h2 className="text-[14.5px] font-semibold text-text-strong">
              Anomaly → summary → approval
            </h2>
            <p className="mt-0.5 max-w-2xl text-[11.5px] leading-snug text-text-muted">
              Pick a finding, draft an LLM triage note, raise it for approval, and record the
              decision. Three endpoints, one thread: GET /anomalies → POST /chat → POST /approvals.
            </p>
          </div>
        </div>
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[11px] font-semibold",
            canDecide
              ? "border-success bg-success-soft text-success"
              : "border-border bg-surface-2 text-text-muted",
          )}
        >
          {canDecide ? <ShieldCheck className="size-3.5" aria-hidden /> : <Lock className="size-3.5" aria-hidden />}
          {canDecide ? "You may decide approvals" : "Request only — decisions need the power-user role"}
        </span>
      </header>

      <div className="grid gap-0 lg:grid-cols-[minmax(280px,380px)_1fr]">
        {/* ---- Findings list -------------------------------------------- */}
        <div className="border-border lg:border-r">
          {anomalies.loading ? (
            <ul className="flex flex-col gap-2 p-4">
              {[0, 1, 2, 3].map((i) => (
                <li key={i} className="skeleton h-14 rounded" />
              ))}
            </ul>
          ) : anomalies.error ? (
            <p className="m-4 rounded border border-danger bg-danger-soft px-3 py-2 text-[12px] text-danger">
              {anomalies.error}
            </p>
          ) : rows.length === 0 ? (
            <p className="m-4 rounded border border-dashed border-border px-3 py-6 text-center text-[12px] text-text-subtle">
              No anomalies are open in the portfolio visible to you.
            </p>
          ) : (
            <ul className="max-h-[420px] overflow-y-auto">
              {rows.map((a) => {
                const stage = work[a.id]?.stage ?? "detected";
                const isSelected = selected?.id === a.id;
                return (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(a.id)}
                      aria-current={isSelected}
                      className={clsx(
                        "w-full border-b border-border-2 px-4 py-3 text-left transition-colors",
                        isSelected ? "bg-gov-primary-lighter" : "hover:bg-surface-2",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[11px] font-semibold text-gov-primary">
                          {a.grant_no ?? `grant #${a.grant_id}`}
                        </span>
                        <span
                          className={clsx(
                            "rounded border px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide",
                            SEVERITY_STYLE[a.severity],
                          )}
                        >
                          {a.severity}
                        </span>
                      </div>
                      <p className="mt-1 text-[12px] font-medium text-text-strong">{a.kind}</p>
                      <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-text-muted">
                        {a.reason}
                      </p>
                      <span
                        className={clsx(
                          "mt-1.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold",
                          STAGE_STYLE[stage],
                        )}
                      >
                        {STAGE_LABEL[stage]}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* ---- Workflow -------------------------------------------------- */}
        <div className="p-4">
          {!selected ? (
            <p className="text-[12px] text-text-subtle">Select a finding to start the workflow.</p>
          ) : (
            <>
              <Stepper stage={item.stage} />

              <div className="mt-4 rounded border border-border bg-surface-2 px-3 py-2.5">
                <p className="flex items-center gap-2 text-[12px] font-semibold text-text-strong">
                  <AlertTriangle className="size-3.5 text-warn" aria-hidden />
                  {selected.kind} · {selected.grant_no ?? `grant #${selected.grant_id}`}
                </p>
                <p className="mt-1 text-[11.5px] leading-snug text-text-muted">{selected.reason}</p>
                <p className="mt-1 font-mono text-[10px] text-text-subtle">
                  anomalies.id {selected.id} · status {selected.status} · detected{" "}
                  {dateTimeShort(selected.created_at)}
                </p>
              </div>

              {/* Step 2 — summary */}
              <div className="mt-4">
                {item.summary ? (
                  <div className="rounded border border-border px-3 py-2.5">
                    <p className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
                      <FileText className="size-3.5" aria-hidden />
                      Triage note — generated
                    </p>
                    <p className="mt-1.5 text-[12.5px] leading-relaxed text-text">{item.summary}</p>
                    {item.citations && item.citations.length > 0 ? (
                      <ul className="mt-2 flex flex-wrap gap-1.5">
                        {item.citations.map((c) => (
                          <li
                            key={c.grant_no}
                            title={c.title}
                            className="rounded border border-border-2 bg-surface-2 px-2 py-0.5 font-mono text-[10.5px] text-gov-primary"
                          >
                            {c.grant_no}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {item.model ? (
                      <p className="mt-1.5 font-mono text-[10px] text-text-subtle">
                        model: {item.model}
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => void draftSummary(selected)}
                    disabled={chat.pending}
                    className="inline-flex items-center gap-1.5 rounded bg-gov-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover disabled:opacity-50"
                  >
                    {chat.pending ? (
                      <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    ) : (
                      <FileText className="size-3.5" aria-hidden />
                    )}
                    Draft triage note
                  </button>
                )}
                {chat.error ? (
                  <p className="mt-2 text-[11.5px] text-danger">{chat.error}</p>
                ) : null}
              </div>

              {/* Step 3/4 — approval */}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {item.stage === "summarized" ? (
                  <button
                    type="button"
                    onClick={() => void requestApproval(selected)}
                    disabled={approvals.pending}
                    className="inline-flex items-center gap-1.5 rounded bg-gov-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover disabled:opacity-50"
                  >
                    {approvals.pending ? (
                      <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    ) : (
                      <Send className="size-3.5" aria-hidden />
                    )}
                    Request approval
                  </button>
                ) : null}

                {item.stage === "pending" && canDecide ? (
                  <>
                    <button
                      type="button"
                      onClick={() => void decide(selected, "approve")}
                      disabled={approvals.pending}
                      className="inline-flex items-center gap-1.5 rounded bg-success px-3 py-2 text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      <Check className="size-3.5" aria-hidden />
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => void decide(selected, "reject")}
                      disabled={approvals.pending}
                      className="inline-flex items-center gap-1.5 rounded border border-danger px-3 py-2 text-[12px] font-semibold text-danger transition-colors hover:bg-danger-soft disabled:opacity-50"
                    >
                      <X className="size-3.5" aria-hidden />
                      Reject
                    </button>
                  </>
                ) : null}

                {item.stage === "pending" && !canDecide ? (
                  <p className="flex items-center gap-1.5 rounded border border-border bg-surface-2 px-3 py-2 text-[11.5px] text-text-muted">
                    <Lock className="size-3.5" aria-hidden />
                    Waiting on a power-user decision. Switch persona to decide it.
                  </p>
                ) : null}

              </div>

              {approvals.error ? (
                <p className="mt-2 text-[11.5px] text-danger">{approvals.error}</p>
              ) : null}

              {item.approval ? <ApprovalRecord approval={item.approval} /> : null}

              {item.stage === "approved" || item.stage === "rejected" ? (
                <button
                  type="button"
                  onClick={() =>
                    setWork((prev) => {
                      const next = { ...prev };
                      delete next[selected.id];
                      return next;
                    })
                  }
                  className="mt-3 inline-flex items-center gap-1.5 rounded border border-border px-3 py-2 text-[12px] font-semibold text-text transition-colors hover:bg-surface-2"
                >
                  <RotateCcw className="size-3.5" aria-hidden />
                  Reset this finding
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function Stepper({ stage }: { stage: Stage }) {
  const current = STAGE_ORDER[stage];
  // "approved"/"rejected" are terminal: the last step is complete, not pending.
  const terminal = stage === "approved" || stage === "rejected";
  return (
    <ol className="flex flex-wrap items-center gap-1.5">
      {STEPS.map((s, i) => {
        const done = terminal || i < current;
        const active = !done && i === current;
        const label =
          s.key === "approved" && stage === "rejected" ? "Decided — rejected" : s.title;
        return (
          <li key={s.key} className="flex items-center gap-1.5">
            <span
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                done && "border-success bg-success-soft text-success",
                active && "border-gov-primary bg-gov-primary-lighter text-gov-primary",
                !done && !active && "border-border bg-surface text-text-subtle",
              )}
            >
              {done ? (
                <Check className="size-3" aria-hidden />
              ) : (
                <span className="font-mono text-[10px]">{i + 1}</span>
              )}
              {label}
            </span>
            {i < STEPS.length - 1 ? (
              <span aria-hidden className="h-px w-4 bg-border-strong" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function ApprovalRecord({ approval }: { approval: Approval }) {
  const tone =
    approval.state === "approved"
      ? "border-success bg-success-soft"
      : approval.state === "rejected"
        ? "border-danger bg-danger-soft"
        : "border-warn bg-warn-soft";
  return (
    <dl className={clsx("mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5 rounded border px-3 py-2.5 text-[11.5px] sm:grid-cols-3", tone)}>
      <Field label="approvals.id" value={String(approval.id)} mono />
      <Field label="subject" value={`${approval.subject_type}:${approval.subject_id}`} mono />
      <Field label="state" value={approval.state} mono />
      <Field label="requested_by" value={approval.requested_by} />
      <Field label="decided_by" value={approval.decided_by ?? "—"} />
      <Field
        label="decided_at"
        value={approval.decided_at ? dateTimeShort(approval.decided_at) : "—"}
      />
    </dl>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[9.5px] font-semibold uppercase tracking-[0.1em] text-text-subtle">
        {label}
      </dt>
      <dd className={clsx("truncate text-text-strong", mono && "font-mono text-[11px]")} title={value}>
        {value}
      </dd>
    </div>
  );
}

export default AnomalyWorkflow;

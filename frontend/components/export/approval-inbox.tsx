"use client";

import { useEffect, useState } from "react";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { RehearsalPersonaSwitch } from "./rehearsal-persona-switch";
import clsx from "clsx";
import {
  ArrowRight,
  Check,
  Clipboard,
  ClipboardCheck,
  Inbox,
  Loader2,
  LockKeyhole,
  RefreshCw,
  UserCheck,
  X,
} from "lucide-react";

import { dateTimeShort } from "@/components/dashboard/format";
import type { Approval, ApprovalsListResponse , Role } from "@/lib/types";

export type ApprovalHandoff = {
  approval: Approval;
  token: string;
};

type ApprovalInboxProps = {
  signedInRole: Role | null;
  data: ApprovalsListResponse | null;
  error: string | null;
  loading: boolean;
  busy: boolean;
  handoff: ApprovalHandoff | null;
  onRefresh: () => void;
  onDecide: (approval: Approval, action: "approve" | "reject") => Promise<void>;
};

export function ApprovalInbox({
  signedInRole,
  data,
  error,
  loading,
  busy,
  handoff,
  onRefresh,
  onDecide,
}: ApprovalInboxProps) {
  // Four-eyes is a two-person control: the acting-persona simulation exists
  // only in the explicitly synthetic rehearsal workspace. On the live plane a
  // second reviewer must decide in their own authenticated session.
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setCopied(false);
  }, [handoff?.token]);

  async function copyToken() {
    if (!handoff) return;
    try {
      await navigator.clipboard.writeText(handoff.token);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const canDecide = data?.can_decide ?? false;

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface shadow-soft">
      <header className="grid gap-4 border-b border-border bg-[linear-gradient(120deg,var(--surface)_0%,var(--surface-2)_100%)] px-5 py-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div className="flex items-start gap-3">
          <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-md bg-gov-primary text-white shadow-soft">
            <Inbox className="size-5" aria-hidden />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-gov-primary">
              Four-eyes control
            </p>
            <h2 className="mt-0.5 text-lg font-semibold tracking-tight text-text-strong">
              Approval inbox and secure handoff
            </h2>
            <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-text-muted">
              A requester raises the bound export request. A separate reviewer decides it in their
              own session. Only that approve response reveals a short-lived, single-use token for
              copy and paste back into the requester&apos;s original session.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading || busy}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-border bg-surface px-3.5 text-[12px] font-semibold text-text transition-colors hover:border-gov-primary hover:text-gov-primary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={clsx("size-4", loading && "animate-spin")} aria-hidden />
          Refresh inbox
        </button>
      </header>

      <div className="grid border-b border-border lg:grid-cols-3">
        <HandoffStep
          number="01"
          title="Requester"
          body="Run the export and submit its exact approval subject. Keep that tab open."
        />
        <HandoffStep
          number="02"
          title="Independent reviewer"
          body={rehearsal ? "Switch the acting persona below to the power-user reviewer, then approve. Rehearsal simulates the separate session inside this browser." : "A different signed-in reviewer opens this page in their own session and approves the matching subject."}
        />
        <HandoffStep
          number="03"
          title="Token return"
          body="Copy the one-time token, return to the requester tab, paste it, and retry."
        />
      </div>

      <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-[14px] font-semibold text-text-strong">
                {canDecide ? "Shared review queue" : "Your submitted requests"}
              </h3>
              <p className="mt-0.5 text-[11px] text-text-muted">
                Acting as <span className="font-semibold text-text-strong">{data?.actor ?? "Loading actor"}</span>
              </p>
              {rehearsal ? <RehearsalPersonaSwitch signedInRole={signedInRole} onSwitched={onRefresh} /> : null}
            </div>
            {data ? (
              <span
                className={clsx(
                  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10.5px] font-semibold",
                  canDecide
                    ? "bg-success-soft text-success"
                    : "bg-gov-primary-lighter text-gov-primary",
                )}
              >
                {canDecide ? <UserCheck className="size-3.5" aria-hidden /> : <LockKeyhole className="size-3.5" aria-hidden />}
                {canDecide ? "Decision authority" : "Requester scope only"}
              </span>
            ) : null}
          </div>

          {error ? (
            <p className="rounded-md border border-danger bg-danger-soft px-3 py-2.5 text-[11.5px] text-danger">
              {error}
            </p>
          ) : null}

          {loading && !data ? (
            <div className="flex min-h-32 items-center justify-center gap-2 text-[12px] text-text-muted">
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Loading pending approvals
            </div>
          ) : null}

          {!loading && data?.approvals.length === 0 ? (
            <div className="rounded-md border border-dashed border-border px-4 py-8 text-center">
              <Check className="mx-auto size-5 text-success" aria-hidden />
              <p className="mt-2 text-[12.5px] font-semibold text-text-strong">Queue is clear</p>
              <p className="mt-1 text-[11.5px] text-text-muted">
                {canDecide
                  ? "No pending requests are waiting for an independent decision."
                  : "Run a guarded export and request approval to place it here."}
              </p>
            </div>
          ) : null}

          {data && data.approvals.length > 0 ? (
            <ul className="space-y-2.5">
              {data.approvals.map((approval) => {
                const selfApproval = approval.requested_by === data.actor;
                return (
                  <li
                    key={approval.id}
                    className="rounded-md border border-border bg-surface-2 p-3.5 transition-colors hover:border-border-strong"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded bg-warn-soft px-2 py-1 text-[10px] font-bold uppercase tracking-[0.1em] text-warn">
                            Pending
                          </span>
                          <span className="font-mono text-[11px] text-text-muted">
                            approval {approval.id}
                          </span>
                        </div>
                        <p className="mt-2 break-all font-mono text-[12px] font-semibold text-text-strong">
                          {approval.subject_type}:{approval.subject_id}
                        </p>
                        <dl className="mt-2 grid gap-x-5 gap-y-1 text-[11px] sm:grid-cols-2">
                          <div>
                            <dt className="inline text-text-subtle">Requested by </dt>
                            <dd className="inline font-semibold text-text">{approval.requested_by}</dd>
                          </div>
                          <div>
                            <dt className="inline text-text-subtle">Created </dt>
                            <dd className="inline text-text">{dateTimeShort(approval.created_at)}</dd>
                          </div>
                        </dl>
                        {approval.note ? (
                          <p className="mt-2 text-[11.5px] leading-relaxed text-text-muted">
                            {approval.note}
                          </p>
                        ) : null}
                      </div>

                      {canDecide ? (
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => void onDecide(approval, "approve")}
                            disabled={busy || selfApproval}
                            title={selfApproval ? "Four-eyes policy blocks self approval" : undefined}
                            className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-md bg-success px-3.5 text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45"
                          >
                            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Check className="size-4" aria-hidden />}
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => void onDecide(approval, "reject")}
                            disabled={busy || selfApproval}
                            title={selfApproval ? "Four-eyes policy blocks self rejection" : undefined}
                            className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-md border border-danger bg-surface px-3.5 text-[12px] font-semibold text-danger transition-colors hover:bg-danger-soft disabled:cursor-not-allowed disabled:opacity-45"
                          >
                            <X className="size-4" aria-hidden />
                            Reject
                          </button>
                        </div>
                      ) : null}
                    </div>

                    {canDecide && selfApproval ? (
                      <p className="mt-3 flex items-start gap-2 rounded border border-warn bg-warn-soft px-2.5 py-2 text-[11px] leading-snug text-warn">
                        <LockKeyhole className="mt-px size-3.5 shrink-0" aria-hidden />
                        This actor created the request, so four-eyes policy disables both decision actions.
                      </p>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>

        <aside className="border-t border-border bg-surface-2 p-5 xl:border-l xl:border-t-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-subtle">
            Reviewer handoff
          </p>
          {handoff ? (
            <div className="mt-3 rounded-md border border-success bg-success-soft p-3.5">
              <p className="flex items-center gap-2 text-[13px] font-semibold text-success">
                <ClipboardCheck className="size-4" aria-hidden />
                Decision approved
              </p>
              <p className="mt-2 text-[11.5px] leading-relaxed text-text">
                Copy this capability once. It is held only in this page&apos;s memory and is never
                returned by the inbox route.
              </p>
              <label className="mt-3 block text-[10.5px] font-semibold text-text-muted" htmlFor="approval-handoff-token">
                One-time approval token
              </label>
              <div className="mt-1.5 flex gap-2">
                <input
                  id="approval-handoff-token"
                  value={handoff.token}
                  readOnly
                  autoComplete="off"
                  spellCheck={false}
                  data-1p-ignore
                  className="min-h-11 min-w-0 flex-1 rounded-md border border-border bg-surface px-3 font-mono text-[12px] text-text-strong outline-none"
                />
                <button
                  type="button"
                  onClick={() => void copyToken()}
                  className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-md bg-gov-primary px-3 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover"
                >
                  {copied ? <ClipboardCheck className="size-4" aria-hidden /> : <Clipboard className="size-4" aria-hidden />}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <dl className="mt-3 space-y-1 font-mono text-[10.5px] text-text-muted">
                <div className="flex justify-between gap-3">
                  <dt>Subject</dt>
                  <dd className="truncate text-right text-text">{handoff.approval.subject_id}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>Expires</dt>
                  <dd className="text-right text-text">
                    {handoff.approval.expires_at
                      ? dateTimeShort(handoff.approval.expires_at)
                      : "Server policy"}
                  </dd>
                </div>
              </dl>
              <p className="mt-3 flex items-start gap-2 border-t border-success/25 pt-3 text-[11px] leading-relaxed text-text-muted">
                <ArrowRight className="mt-px size-3.5 shrink-0 text-success" aria-hidden />
                Return to the original requester session. Paste this token beside its blocked
                export, then retry the unchanged request.
              </p>
            </div>
          ) : (
            <div className="mt-3 rounded-md border border-dashed border-border px-3.5 py-5">
              <LockKeyhole className="size-5 text-text-subtle" aria-hidden />
              <p className="mt-2 text-[12px] font-semibold text-text-strong">No token displayed</p>
              <p className="mt-1 text-[11px] leading-relaxed text-text-muted">
                Tokens are absent from queue reads. A separate reviewer sees one only after a
                successful approve action.
              </p>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}

function HandoffStep({ number, title, body }: { number: string; title: string; body: string }) {
  return (
    <div className="relative border-b border-border px-5 py-3.5 last:border-b-0 lg:border-b-0 lg:border-r lg:last:border-r-0">
      <p className="font-mono text-[10px] font-semibold text-gov-primary">{number}</p>
      <p className="mt-0.5 text-[12.5px] font-semibold text-text-strong">{title}</p>
      <p className="mt-1 text-[11px] leading-relaxed text-text-muted">{body}</p>
    </div>
  );
}

export default ApprovalInbox;

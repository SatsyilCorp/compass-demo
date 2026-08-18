"use client";

import { useCallback, useRef, useState } from "react";
import { useRehearsalIdentity } from "./use-rehearsal-identity";
import clsx from "clsx";
import {
  Check,
  Database,
  Download,
  EyeOff,
  FileDown,
  Loader2,
  ClipboardPaste,
  Minus,
  RotateCcw,
  Send,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import {
  ApiError,
  getApprovals,
  getDashboard,
  postApprovals,
  postExport,
  setAuthContext,
} from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { PageHeader } from "@/components/shell/page-header";
import type {
  Approval,
  DashboardResponse,
  ExportApprovalRequiredBody,
  ExportRequest,
  ExportResponse,
} from "@/lib/types";

import { describeError, useCompassQuery } from "@/components/dashboard/use-compass-query";
import { num } from "@/components/dashboard/format";
import { replayActor } from "@/lib/mock/actors";
import { ApprovalInbox, type ApprovalHandoff } from "./approval-inbox";
import { AuditTrail, type AuditEvent } from "./audit-trail";
import {
  DEFAULT_FILTERS,
  ExportFilters,
  selectedColumns,
  toRequestFilters,
  type ExportFilterState,
} from "./export-filters";
import { OpenApiPanel } from "./openapi-panel";

/**
 * Element 7: governed export.
 *
 * The page exists to show four controls doing their job on a real request, in
 * this order:
 *
 *   RLS   the filter options, and the rows behind them, come from the caller's
 *         own scope. A viewer cannot even name another org unit.
 *   CLS   `amount_usd` is not offered as an export column to a role that has
 *         `SELECT (amount_usd)` revoked.
 *   GUARD `POST /export` answers 428 "approval required" when the requested row
 *         count exceeds EXPORT_MAX_ROWS. The page does not work around it: it
 *         raises an approval, has a separate reviewer decide it, then retries
 *         the same call with a manually transferred one-time token.
 *   AUDIT every one of those calls is written to the append-only audit table
 *         server-side; the session echo is shown at the bottom.
 */
type Phase =
  | { kind: "idle" }
  | {
      kind: "blocked";
      guard: ExportApprovalRequiredBody;
      clientRequestId: string;
      subjectId: string;
      request: PreparedExportRequest;
    }
  | {
      kind: "pending";
      guard: ExportApprovalRequiredBody;
      clientRequestId: string;
      subjectId: string;
      approval: Approval;
      request: PreparedExportRequest;
    }
  | {
      kind: "released";
      result: ExportResponse;
      approval: Approval | null;
      request: PreparedExportRequest;
      consumedToken: string | null;
      reuseProof: "idle" | "verified" | "failed";
    };

type PreparedExportRequest = Pick<ExportRequest, "format" | "columns" | "filters">;

const STEPS = ["Request", "Aggregation guard", "Approval", "Release"] as const;

function stepIndex(phase: Phase): number {
  switch (phase.kind) {
    case "idle":
      return 0;
    case "blocked":
      return 1;
    case "pending":
      return 2;
    case "released":
      return 3;
  }
}

export function ExportView() {
  const { role: signedInRole, orgUnit: signedInOrgUnit, idToken, displayName } = useAppAuth();
  const { role, orgUnit } = useRehearsalIdentity(signedInRole, signedInOrgUnit);
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";

  const dashboard = useCompassQuery(getDashboard);
  const approvals = useCompassQuery(getApprovals);
  const amountMasked = dashboard.data ? dashboard.data.kpis.total_funding_usd === null : false;

  const [filters, setFilters] = useState<ExportFilterState>(DEFAULT_FILTERS);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [busy, setBusy] = useState<null | "export" | "approval">(null);
  const [error, setError] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [handoff, setHandoff] = useState<ApprovalHandoff | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const nextEventId = useRef(1);

  const actor = rehearsal
    ? replayActor(role)
    : approvals.data?.actor ?? displayName ?? role ?? "anonymous";

  const audit = useCallback(
    (action: string, resource: string, detail: Record<string, unknown>, outcome: AuditEvent["outcome"] = "ok") => {
      setEvents((prev) => [
        ...prev,
        {
          id: nextEventId.current++,
          at: new Date().toISOString(),
          actor,
          action,
          resource,
          detail,
          outcome,
        },
      ]);
    },
    [actor],
  );

  const publishAuth = useCallback(() => {
    setAuthContext({ bearerToken: idToken, role, orgUnit });
  }, [idToken, role, orgUnit]);

  const requestFilters = toRequestFilters(filters);
  const columns = selectedColumns(filters, amountMasked);
  const preparedRequest: PreparedExportRequest = {
    format: filters.format,
    columns,
    filters: requestFilters,
  };
  const estimate = estimateRows(dashboard.data, filters);

  async function runExport(
    request: PreparedExportRequest,
    approval: Approval | null,
    clientRequestId: string,
    approvalToken?: string,
  ) {
    const req: ExportRequest = {
      ...request,
      ...(approvalToken ? { approval_token: approvalToken } : {}),
    };
    setBusy("export");
    setError(null);
    audit("export.request", "compass.grants_curated", {
      request_id: clientRequestId,
      format: req.format,
      columns: req.columns,
      filters: req.filters,
      approval_id: approval?.id ?? null,
    });

    try {
      publishAuth();
      const result = await postExport(req);
      audit("export.completed", `export:${result.export_id}`, {
        request_id: clientRequestId,
        row_count: result.row_count,
        format: result.format,
        columns: req.columns,
      });
      setTokenInput("");
      setPhase({
        kind: "released",
        result,
        approval,
        request,
        consumedToken: approvalToken ?? null,
        reuseProof: "idle",
      });
    } catch (e) {
      if (e instanceof ApiError && e.status === 428) {
        const guard = e.body as ExportApprovalRequiredBody;
        audit(
          "export.denied",
          "compass.grants_curated",
          {
            request_id: clientRequestId,
            reason: guard.error,
            row_count: guard.row_count,
            max_rows: guard.max_rows,
            subject_id: guard.subject_id,
          },
          "denied",
        );
        if (!guard.subject_id || !guard.subject_id.startsWith("exp-")) {
          setError("The API did not return a bound approval subject. Nothing was released.");
          return;
        }
        setPhase({
          kind: "blocked",
          guard,
          clientRequestId,
          subjectId: guard.subject_id,
          request,
        });
      } else {
        setError(describeError(e));
      }
    } finally {
      setBusy(null);
    }
  }

  async function requestApproval() {
    if (phase.kind !== "blocked") return;
    setBusy("approval");
    setError(null);
    try {
      publishAuth();
      const { approval } = await postApprovals({
        subject_type: "export",
        subject_id: phase.subjectId,
        action: "request",
        note: `Export of ${phase.guard.row_count} rows as ${phase.request.format} exceeds the ${phase.guard.max_rows}-row aggregation threshold.`,
      });
      audit("approval.requested", `approvals:${approval.id}`, {
        subject: phase.subjectId,
        state: approval.state,
      });
      setPhase({ ...phase, kind: "pending", approval });
      approvals.reload();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(null);
    }
  }

  async function decideApproval(approvalRecord: Approval, action: "approve" | "reject") {
    setBusy("approval");
    setError(null);
    try {
      publishAuth();
      const response = await postApprovals({
        subject_type: approvalRecord.subject_type,
        subject_id: approvalRecord.subject_id,
        action,
        note: approvalRecord.note ?? undefined,
      });
      const { approval } = response;
      audit(
        action === "approve" ? "approval.approved" : "approval.rejected",
        `approvals:${approval.id}`,
        {
          subject: approval.subject_id,
          state: approval.state,
          decided_by: approval.decided_by,
        },
        action === "approve" ? "ok" : "denied",
      );
      if (approval.state === "approved") {
        if (!response.approval_token) {
          throw new Error("Approved decision did not return a one-time capability token");
        }
        setHandoff({ approval, token: response.approval_token });
      } else if (
        phase.kind === "pending" &&
        phase.subjectId === approval.subject_id
      ) {
        setPhase({ kind: "idle" });
      }
      approvals.reload();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(null);
    }
  }

  async function verifySingleUse() {
    if (phase.kind !== "released") return;
    const consumedToken = phase.consumedToken;
    if (!consumedToken) return;
    const released = phase;
    setBusy("export");
    setError(null);
    try {
      publishAuth();
      await postExport({
        ...released.request,
        approval_token: consumedToken,
      });
      audit(
        "approval.reuse_check",
        `approvals:${released.approval?.id ?? "unknown"}`,
        { decision: "unexpectedly_allowed" },
        "denied",
      );
      setPhase({ ...released, consumedToken: null, reuseProof: "failed" });
      setError("Single-use verification failed because the API accepted a consumed capability.");
    } catch (caught) {
      const responseCode =
        caught instanceof ApiError && caught.body && typeof caught.body === "object"
          ? (caught.body as { code?: string }).code
          : null;
      const rejected =
        responseCode === "approval_capability_consumed" ||
        (caught instanceof Error && caught.message === "approval_capability_consumed");
      if (!rejected) {
        setError(describeError(caught));
        return;
      }
      audit("approval.reuse_denied", `approvals:${released.approval?.id ?? "unknown"}`, {
        decision: "single_use_enforced",
      });
      setPhase({ ...released, consumedToken: null, reuseProof: "verified" });
    } finally {
      setBusy(null);
    }
  }

  function reset() {
    setPhase({ kind: "idle" });
    setError(null);
    setTokenInput("");
  }

  const validToken = tokenInput.trim().length >= 24;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Element 7 of 7 | Interoperability, Portability, and Secure Export"
        title="Export with the guardrails on"
        icon={<FileDown className="size-4" aria-hidden />}
        lead="Filter the curated portfolio, choose a format, and export it. Row- and column-level security scope what you can ask for; an aggregation guard stops bulk pulls until an approval is attached; every attempt is audited."
      />

      {/* ---- Enforcement strip ------------------------------------------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Control
          Icon={Database}
          title="Row-level security"
          body={`Rows are filtered by the RLS policy on compass.grants_curated for org_unit ${orgUnit ?? "not resolved"}. FORCE ROW LEVEL SECURITY is on, so even the connecting role cannot see past it.`}
        />
        <Control
          Icon={EyeOff}
          title="Column-level security"
          body={
            amountMasked
              ? "amount_usd is revoked for your role, so it is not offered as an export column and the API will not emit it."
              : "amount_usd is readable by your role and can be included as an export column."
          }
          tone={amountMasked ? "warn" : "default"}
        />
        <Control
          Icon={ShieldAlert}
          title="Aggregation guard"
          body="POST /export answers HTTP 428 'approval required' when the requested row count exceeds EXPORT_MAX_ROWS. The threshold is enforced by the API, not by this page."
        />
        <Control
          Icon={ShieldCheck}
          title="Audit"
          body="Requests, denials, approvals, and releases are appended to compass.audit_log with the actor and the exact filter payload."
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        {/* ---- Filters --------------------------------------------------- */}
        <section className="min-w-0 rounded-md border border-border bg-surface p-4 shadow-soft">
          <header className="mb-4">
            <h2 className="text-[14.5px] font-semibold text-text-strong">Export request</h2>
            <p className="mt-0.5 text-[11.5px] leading-snug text-text-muted">
              Signed in as {displayName ?? "unknown persona"}. Options are drawn from{" "}
              <code className="font-mono text-[11px]">GET /dashboard</code>, so you can only choose
              values inside your own scope.
            </p>
          </header>

          <ExportFilters
            value={filters}
            onChange={(next) => {
              setFilters(next);
              if (phase.kind !== "idle") reset();
            }}
            dashboard={dashboard.data}
            amountMasked={amountMasked}
            disabled={busy !== null}
          />

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border-2 pt-4">
            <div>
              <p className="text-[11.5px] text-text-muted">
                Rows in scope{" "}
                <span className="font-mono font-semibold text-text-strong">
                  {estimate.value === null ? "Not available" : `${estimate.upperBound ? "≤ " : ""}${num(estimate.value)}`}
                </span>
              </p>
              <p className="mt-0.5 max-w-sm text-[10.5px] leading-snug text-text-subtle">
                Upper bound computed in the browser from the aggregate counts in{" "}
                <code className="font-mono text-[10px]">/dashboard</code>. The guard is evaluated
                server-side against the exact filtered count.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void runExport(preparedRequest, null, newRequestId())}
              disabled={busy !== null || phase.kind !== "idle"}
              className="inline-flex items-center gap-1.5 rounded bg-gov-primary px-4 py-2.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy === "export" ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Download className="size-4" aria-hidden />
              )}
              Run export
            </button>
          </div>

          <details className="mt-4">
            <summary className="cursor-pointer text-[11.5px] font-semibold text-text-muted">
              Request body sent to POST /export
            </summary>
            <pre className="mt-2 overflow-x-auto rounded border border-border bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-text">
              {JSON.stringify(preparedRequest, null, 2)}
            </pre>
          </details>
        </section>

        {/* ---- Guard flow ------------------------------------------------- */}
        <section className="min-w-0 rounded-md border border-border bg-surface p-4 shadow-soft">
          <header className="mb-3">
            <h2 className="text-[14.5px] font-semibold text-text-strong">Aggregation guard</h2>
            <p className="mt-0.5 text-[11.5px] leading-snug text-text-muted">
              What the API did with the request, step by step.
            </p>
          </header>

          <ol className="flex flex-wrap items-center gap-1.5">
            {STEPS.map((s, i) => {
              const current = stepIndex(phase);
              // A request under the row threshold is released without ever
              // reaching the approval path. That step is skipped, not passed,
              // and is labelled so rather than shown as a green check.
              const skipped =
                i === 2 && phase.kind === "released" && phase.approval === null;
              const done = !skipped && (i < current || phase.kind === "released");
              const active = !done && !skipped && i === current;
              return (
                <li key={s} className="flex items-center gap-1.5">
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
                    ) : skipped ? (
                      <Minus className="size-3" aria-hidden />
                    ) : (
                      <span className="font-mono text-[10px]">{i + 1}</span>
                    )}
                    {skipped ? "Approval not required" : s}
                  </span>
                  {i < STEPS.length - 1 ? <span aria-hidden className="h-px w-4 bg-border-strong" /> : null}
                </li>
              );
            })}
          </ol>

          <div className="mt-4">
            {phase.kind === "idle" ? (
              <p className="rounded border border-dashed border-border px-3 py-6 text-center text-[12px] text-text-subtle">
                Run an export to see the guard evaluate it. Ask for the whole portfolio to trip it.
              </p>
            ) : null}

            {phase.kind !== "idle" && phase.kind !== "released" ? (
              <div className="rounded border border-danger bg-danger-soft px-3 py-2.5">
                <p className="flex items-center gap-2 text-[12.5px] font-semibold text-danger">
                  <ShieldAlert className="size-4" aria-hidden />
                  HTTP 428: approval required
                </p>
                <p className="mt-1 text-[11.5px] leading-snug text-text">
                  The request matched{" "}
                  <span className="font-mono font-semibold">{num(phase.guard.row_count)}</span> rows,
                  over the{" "}
                  <span className="font-mono font-semibold">{num(phase.guard.max_rows)}</span>-row
                  threshold. No rows were released.
                </p>
                <pre className="mt-2 overflow-x-auto rounded border border-border bg-surface p-2 font-mono text-[10.5px] text-text">
                  {JSON.stringify(phase.guard, null, 2)}
                </pre>
                <p className="mt-2 font-mono text-[10px] text-text-muted">
                  approval_subject {phase.subjectId}
                </p>
              </div>
            ) : null}

            {phase.kind === "blocked" ? (
              <button
                type="button"
                onClick={() => void requestApproval()}
                disabled={busy !== null}
                className="mt-3 inline-flex items-center gap-1.5 rounded bg-gov-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover disabled:opacity-50"
              >
                {busy === "approval" ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                ) : (
                  <Send className="size-3.5" aria-hidden />
                )}
                Request approval
              </button>
            ) : null}

            {phase.kind === "pending" ? (
              <div className="mt-3 rounded border border-border px-3 py-2.5">
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
                  Approval record
                </p>
                <p className="mt-1 font-mono text-[11.5px] text-text">
                  approvals.id {phase.approval.id} · state{" "}
                  <span
                    className={clsx(
                      "rounded px-1.5 py-0.5 font-semibold",
                      "bg-warn-soft text-warn",
                    )}
                  >
                    {phase.approval.state}
                  </span>{" "}
                  · requested_by {phase.approval.requested_by}
                </p>
                {phase.approval.note ? (
                  <p className="mt-1 text-[11.5px] leading-snug text-text-muted">
                    {phase.approval.note}
                  </p>
                ) : null}
              </div>
            ) : null}

            {phase.kind === "pending" ? (
              <div className="mt-3 rounded-md border border-gov-primary/25 bg-gov-primary-lighter/50 p-3.5">
                <p className="flex items-center gap-2 text-[12.5px] font-semibold text-text-strong">
                  <ClipboardPaste className="size-4 text-gov-primary" aria-hidden />
                  Return the reviewer token to this session
                </p>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-text-muted">
                  Keep this requester session open. In another browser session, select the
                  power-user persona and approve the matching subject in the inbox below. Copy the
                  one-time token, return here, and paste it. The retry keeps the exact format and
                  filters that produced this subject.
                </p>
                <label
                  htmlFor="requester-approval-token"
                  className="mt-3 block text-[10.5px] font-semibold text-text-muted"
                >
                  Approval token from reviewer
                </label>
                <input
                  id="requester-approval-token"
                  value={tokenInput}
                  onChange={(event) => setTokenInput(event.target.value)}
                  placeholder="Paste the opaque token from the reviewer"
                  autoComplete="off"
                  spellCheck={false}
                  data-1p-ignore
                  className="mt-1.5 min-h-11 w-full rounded-md border border-border bg-surface px-3 font-mono text-[12px] text-text-strong outline-none transition-colors placeholder:text-text-subtle focus:border-gov-primary focus:ring-2 focus:ring-gov-primary/15"
                />
                <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[10.5px] leading-snug text-text-subtle">
                    Token values are not written to the interaction trace, request preview, URL,
                    or browser storage.
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      void runExport(
                        phase.request,
                        phase.approval,
                        phase.clientRequestId,
                        tokenInput.trim(),
                      )
                    }
                    disabled={busy !== null || !validToken}
                    className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-md bg-gov-primary px-3.5 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busy === "export" ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                    ) : (
                      <Download className="size-4" aria-hidden />
                    )}
                    Retry exact export
                  </button>
                </div>
              </div>
            ) : null}

            {phase.kind === "released" ? (
              <ReleasedPanel
                result={phase.result}
                approval={phase.approval}
                reuseProof={phase.reuseProof}
                canVerify={Boolean(phase.consumedToken)}
                busy={busy === "export"}
                onVerify={() => void verifySingleUse()}
                onReset={reset}
                rehearsal={rehearsal}
              />
            ) : null}

            {error ? (
              <p className="mt-3 rounded border border-danger bg-danger-soft px-3 py-2 text-[11.5px] text-danger">
                {error}
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <ApprovalInbox
        signedInRole={signedInRole}
        data={approvals.data}
        error={approvals.error}
        loading={approvals.loading}
        busy={busy === "approval"}
        handoff={handoff}
        onRefresh={approvals.reload}
        onDecide={decideApproval}
      />

      <AuditTrail events={events} />
      <OpenApiPanel />
    </div>
  );
}

function ReleasedPanel({
  result,
  approval,
  reuseProof,
  canVerify,
  busy,
  onVerify,
  onReset,
  rehearsal,
}: {
  result: ExportResponse;
  approval: Approval | null;
  reuseProof: "idle" | "verified" | "failed";
  canVerify: boolean;
  busy: boolean;
  onVerify: () => void;
  onReset: () => void;
  rehearsal: boolean;
}) {
  const isReplayManifest = result.download_url.startsWith("data:application/json");
  const isDownloadable = /^https?:/i.test(result.download_url) || isReplayManifest;
  const requestedFormat = result.requested_format ?? result.format;
  return (
    <div className="rounded border border-success bg-success-soft px-3 py-2.5">
      <p className="flex items-center gap-2 text-[12.5px] font-semibold text-success">
        <Check className="size-4" aria-hidden />
        Export released
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
        <Field label="export_id" value={result.export_id} />
        <Field label="rows" value={num(result.row_count)} />
        <Field label="requested" value={requestedFormat} />
        <Field label="delivered" value={result.format} />
        <Field label="audited" value={String(result.audited)} />
        <Field label="approval" value={approval ? "one-time capability consumed" : "not required"} />
        <Field label="control" value={approval ? "independent reviewer" : "within threshold"} />
      </dl>

      {result.note ? (
        <p className="mt-3 rounded border border-info/25 bg-info-soft px-3 py-2 text-[11.5px] leading-relaxed text-text-muted">
          {result.note}
        </p>
      ) : null}

      {approval ? (
        <div className="mt-3 rounded border border-success/30 bg-surface px-3 py-2.5">
          {reuseProof === "verified" ? (
            <p className="flex items-center gap-2 text-[11.5px] font-semibold text-success" role="status">
              <ShieldCheck className="size-4" aria-hidden />
              Single-use control verified: the consumed capability was rejected on exact replay.
            </p>
          ) : reuseProof === "failed" ? (
            <p className="text-[11.5px] font-semibold text-danger" role="alert">
              Single-use verification failed.
            </p>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="max-w-md text-[11px] leading-snug text-text-muted">
                Prove the capability is single use by replaying the exact request once. Its value remains only in this page memory for this check.
              </p>
              <button
                type="button"
                onClick={onVerify}
                disabled={!canVerify || busy}
                className="inline-flex min-h-11 items-center gap-1.5 rounded border border-success bg-surface px-3 text-[11.5px] font-semibold text-success transition-colors hover:bg-success-soft disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <ShieldCheck className="size-4" aria-hidden />}
                Verify one-time use
              </button>
            </div>
          )}
        </div>
      ) : null}

      {isDownloadable ? (
        <a
          href={result.download_url}
          download={isReplayManifest ? `${result.export_id}.evidence.json` : undefined}
          className="mt-3 inline-flex items-center gap-1.5 rounded bg-gov-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover"
        >
          <Download className="size-3.5" aria-hidden />
          {isReplayManifest ? "Download replay evidence manifest" : "Download governed export"}
        </a>
      ) : (
        <p className="mt-3 rounded border border-border bg-surface px-2.5 py-2 text-[11px] leading-snug text-text-muted">
          {rehearsal
            ? "No cloud file is materialized in rehearsal. Live AWS releases return a pre-signed, short-lived S3 URL scoped to the caller."
            : "The API returned a non-HTTP download reference."}{" "}
          <code className="font-mono text-[10.5px]">download_url: {result.download_url || "(empty)"}</code>
        </p>
      )}

      <button
        type="button"
        onClick={onReset}
        className="mt-3 inline-flex items-center gap-1.5 rounded border border-border bg-surface px-3 py-2 text-[12px] font-semibold text-text transition-colors hover:bg-surface-2"
      >
        <RotateCcw className="size-3.5" aria-hidden />
        Run another export
      </button>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[9.5px] font-semibold uppercase tracking-[0.1em] text-text-subtle">
        {label}
      </dt>
      <dd className="truncate font-mono text-[11.5px] text-text-strong" title={value}>
        {value}
      </dd>
    </div>
  );
}

function Control({
  Icon,
  title,
  body,
  tone = "default",
}: {
  Icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
  tone?: "default" | "warn";
}) {
  return (
    <div
      className={clsx(
        "rounded-md border bg-surface p-3 shadow-soft",
        tone === "warn" ? "border-warn" : "border-border",
      )}
    >
      <p className="flex items-center gap-1.5 text-[12px] font-semibold text-text-strong">
        <Icon className="size-3.5 text-gov-primary" />
        {title}
      </p>
      <p className="mt-1 text-[11px] leading-snug text-text-muted">{body}</p>
    </div>
  );
}

function newRequestId(): string {
  return `export-req-${Date.now().toString(36)}`;
}

/**
 * Upper bound on the rows a request will match, from the aggregate counts in
 * `GET /dashboard`. `/dashboard` returns per-program-area and per-org-unit
 * counts but no per-fiscal-year count and no cross-tab, so any combination of
 * filters can only be bounded, never computed. This is why the value is labelled
 * as a bound in the UI and why the guard is enforced server-side.
 */
function estimateRows(
  d: DashboardResponse | null,
  f: ExportFilterState,
): { value: number | null; upperBound: boolean } {
  if (!d) return { value: null, upperBound: false };

  const candidates: number[] = [d.kpis.total_grants];
  let upperBound = false;

  if (f.program_area) {
    const row = d.funding_by_program_area.find((p) => p.program_area === f.program_area);
    if (row) candidates.push(row.grant_count);
  }
  if (f.org_unit) {
    const row = d.org_unit_breakdown.find((o) => o.org_unit === f.org_unit);
    if (row) candidates.push(row.grant_count);
  }
  if (f.fiscal_year) upperBound = true;
  if (candidates.length > 2) upperBound = true;

  return { value: Math.min(...candidates), upperBound };
}

export default ExportView;

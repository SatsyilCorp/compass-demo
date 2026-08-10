"use client";

import { useCallback, useRef, useState } from "react";
import clsx from "clsx";
import {
  Check,
  Database,
  Download,
  EyeOff,
  FileDown,
  Loader2,
  Lock,
  Minus,
  RotateCcw,
  Send,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";

import { ApiError, USE_MOCK, getDashboard, postApprovals, postExport, setAuthContext } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";
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
 * Element 7 — governed export.
 *
 * The page exists to show four controls doing their job on a real request, in
 * this order:
 *
 *   RLS   the filter options, and the rows behind them, come from the caller's
 *         own scope — a viewer cannot even name another org unit.
 *   CLS   `amount_usd` is not offered as an export column to a role that has
 *         `SELECT (amount_usd)` revoked.
 *   GUARD `POST /export` answers 428 "approval required" when the requested row
 *         count exceeds EXPORT_MAX_ROWS. The page does not work around it: it
 *         raises an approval, has it decided, and *retries the same call* with
 *         the approval attached.
 *   AUDIT every one of those calls is written to the append-only audit table
 *         server-side; the session echo is shown at the bottom.
 */
type Phase =
  | { kind: "idle" }
  | { kind: "blocked"; guard: ExportApprovalRequiredBody; requestId: string }
  | { kind: "pending"; guard: ExportApprovalRequiredBody; requestId: string; approval: Approval }
  | { kind: "approved"; guard: ExportApprovalRequiredBody; requestId: string; approval: Approval }
  | { kind: "released"; result: ExportResponse; approval: Approval | null };

const STEPS = ["Request", "Aggregation guard", "Approval", "Release"] as const;

function stepIndex(phase: Phase): number {
  switch (phase.kind) {
    case "idle":
      return 0;
    case "blocked":
      return 1;
    case "pending":
      return 2;
    case "approved":
      return 2;
    case "released":
      return 3;
  }
}

export function ExportView() {
  const { role, orgUnit, idToken, displayName } = useAppAuth();
  const canDecide = role === "poweruser";

  const dashboard = useCompassQuery(getDashboard);
  const amountMasked = dashboard.data ? dashboard.data.kpis.total_funding_usd === null : false;

  const [filters, setFilters] = useState<ExportFilterState>(DEFAULT_FILTERS);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [busy, setBusy] = useState<null | "export" | "approval">(null);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const nextEventId = useRef(1);

  const actor = role ?? "anonymous";

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

  const requestFilters = toRequestFilters(filters, amountMasked);
  const columns = selectedColumns(filters, amountMasked);
  const estimate = estimateRows(dashboard.data, filters);

  async function runExport(approval: Approval | null, requestId: string) {
    const req: ExportRequest = {
      format: filters.format,
      filters: requestFilters,
      ...(approval ? { approval_token: String(approval.id) } : {}),
    };
    setBusy("export");
    setError(null);
    audit("export.request", "compass.grants_curated", {
      request_id: requestId,
      format: req.format,
      filters: requestFilters,
      approval_token: approval ? String(approval.id) : null,
    });

    try {
      publishAuth();
      const result = await postExport(req);
      audit("export.completed", `export:${result.export_id}`, {
        request_id: requestId,
        row_count: result.row_count,
        format: result.format,
        columns,
      });
      setPhase({ kind: "released", result, approval });
    } catch (e) {
      if (e instanceof ApiError && e.status === 428) {
        const guard = e.body as ExportApprovalRequiredBody;
        audit(
          "export.denied",
          "compass.grants_curated",
          { request_id: requestId, reason: guard.error, row_count: guard.row_count, max_rows: guard.max_rows },
          "denied",
        );
        setPhase({ kind: "blocked", guard, requestId });
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
        subject_id: phase.requestId,
        action: "request",
        note: `Export of ${phase.guard.row_count} rows as ${filters.format} exceeds the ${phase.guard.max_rows}-row aggregation threshold.`,
      });
      audit("approval.requested", `approvals:${approval.id}`, {
        subject: `export:${phase.requestId}`,
        state: approval.state,
      });
      setPhase({ ...phase, kind: "pending", approval });
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(null);
    }
  }

  async function decide(action: "approve" | "reject") {
    if (phase.kind !== "pending") return;
    setBusy("approval");
    setError(null);
    try {
      publishAuth();
      const { approval } = await postApprovals({
        subject_type: "export",
        subject_id: phase.requestId,
        action,
        note: phase.approval.note ?? undefined,
      });
      audit(
        action === "approve" ? "approval.approved" : "approval.rejected",
        `approvals:${approval.id}`,
        { subject: `export:${phase.requestId}`, state: approval.state, decided_by: approval.decided_by },
        action === "approve" ? "ok" : "denied",
      );
      if (approval.state === "approved") {
        setPhase({ ...phase, kind: "approved", approval });
      } else {
        setPhase({ kind: "idle" });
      }
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(null);
    }
  }

  function reset() {
    setPhase({ kind: "idle" });
    setError(null);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Element 7 · Governed export"
        title="Export with the guardrails on"
        icon={<FileDown className="size-4" aria-hidden />}
        lead="Filter the curated portfolio, choose a format, and export it. Row- and column-level security scope what you can ask for; an aggregation guard stops bulk pulls until an approval is attached; every attempt is audited."
      />

      {/* ---- Enforcement strip ------------------------------------------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Control
          Icon={Database}
          title="Row-level security"
          body={`Rows are filtered by the RLS policy on compass.grants_curated for org_unit ${orgUnit ?? "—"}. FORCE ROW LEVEL SECURITY is on, so even the connecting role cannot see past it.`}
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
        <section className="rounded-md border border-border bg-surface p-4 shadow-soft">
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
                  {estimate.value === null ? "—" : `${estimate.upperBound ? "≤ " : ""}${num(estimate.value)}`}
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
              onClick={() => void runExport(null, newRequestId())}
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
              {JSON.stringify({ format: filters.format, filters: requestFilters }, null, 2)}
            </pre>
          </details>
        </section>

        {/* ---- Guard flow ------------------------------------------------- */}
        <section className="rounded-md border border-border bg-surface p-4 shadow-soft">
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
              // reaching the approval path — that step is skipped, not passed,
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
                  HTTP 428 — approval required
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
                  request_id {phase.requestId}
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

            {phase.kind === "pending" || phase.kind === "approved" ? (
              <div className="mt-3 rounded border border-border px-3 py-2.5">
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
                  Approval record
                </p>
                <p className="mt-1 font-mono text-[11.5px] text-text">
                  approvals.id {phase.approval.id} · state{" "}
                  <span
                    className={clsx(
                      "rounded px-1.5 py-0.5 font-semibold",
                      phase.approval.state === "approved"
                        ? "bg-success-soft text-success"
                        : "bg-warn-soft text-warn",
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
              canDecide ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void decide("approve")}
                    disabled={busy !== null}
                    className="inline-flex items-center gap-1.5 rounded bg-success px-3 py-2 text-[12px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                  >
                    <Check className="size-3.5" aria-hidden />
                    Approve request
                  </button>
                  <button
                    type="button"
                    onClick={() => void decide("reject")}
                    disabled={busy !== null}
                    className="inline-flex items-center gap-1.5 rounded border border-danger px-3 py-2 text-[12px] font-semibold text-danger transition-colors hover:bg-danger-soft disabled:opacity-50"
                  >
                    <X className="size-3.5" aria-hidden />
                    Reject
                  </button>
                </div>
              ) : (
                <p className="mt-3 flex items-start gap-2 rounded border border-border bg-surface-2 px-3 py-2 text-[11.5px] leading-snug text-text-muted">
                  <Lock className="mt-[1px] size-3.5 shrink-0" aria-hidden />
                  Your role may raise an approval but not decide one. Switch to the power-user
                  persona to approve it — that separation is the point of the control.
                </p>
              )
            ) : null}

            {phase.kind === "approved" ? (
              <div className="mt-3">
                <p className="text-[11.5px] leading-snug text-text-muted">
                  The approval id is attached to the retried request as{" "}
                  <code className="font-mono text-[11px]">approval_token</code>. The page does not
                  bypass the guard — it calls the same endpoint again and lets the API decide.
                </p>
                <button
                  type="button"
                  onClick={() => void runExport(phase.approval, phase.requestId)}
                  disabled={busy !== null}
                  className="mt-2 inline-flex items-center gap-1.5 rounded bg-gov-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover disabled:opacity-50"
                >
                  {busy === "export" ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden />
                  ) : (
                    <Download className="size-3.5" aria-hidden />
                  )}
                  Retry export with approval
                </button>
              </div>
            ) : null}

            {phase.kind === "released" ? (
              <ReleasedPanel result={phase.result} approval={phase.approval} onReset={reset} />
            ) : null}

            {error ? (
              <p className="mt-3 rounded border border-danger bg-danger-soft px-3 py-2 text-[11.5px] text-danger">
                {error}
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <AuditTrail events={events} />
      <OpenApiPanel />
    </div>
  );
}

function ReleasedPanel({
  result,
  approval,
  onReset,
}: {
  result: ExportResponse;
  approval: Approval | null;
  onReset: () => void;
}) {
  const isFetchable = /^https?:/i.test(result.download_url);
  return (
    <div className="rounded border border-success bg-success-soft px-3 py-2.5">
      <p className="flex items-center gap-2 text-[12.5px] font-semibold text-success">
        <Check className="size-4" aria-hidden />
        Export released
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
        <Field label="export_id" value={result.export_id} />
        <Field label="rows" value={num(result.row_count)} />
        <Field label="format" value={result.format} />
        <Field label="audited" value={String(result.audited)} />
        <Field label="approval_token" value={approval ? String(approval.id) : "not required"} />
        <Field label="decided_by" value={approval?.decided_by ?? "—"} />
      </dl>

      {isFetchable ? (
        <a
          href={result.download_url}
          className="mt-3 inline-flex items-center gap-1.5 rounded bg-gov-primary px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-action-hover"
        >
          <Download className="size-3.5" aria-hidden />
          Download file
        </a>
      ) : (
        <p className="mt-3 rounded border border-border bg-surface px-2.5 py-2 text-[11px] leading-snug text-text-muted">
          {USE_MOCK
            ? "No file is materialized in mock mode — the deployed API returns a pre-signed, short-lived S3 URL scoped to the caller."
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
 * filters can only be bounded, never computed — which is why this is labelled
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

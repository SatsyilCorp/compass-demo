"use client";

import Link from "next/link";
import clsx from "clsx";
import {
  ArrowUpRight,
  CalendarClock,
  Database,
  KeyRound,
  RefreshCw,
  TriangleAlert,
  Users,
} from "lucide-react";

import { getLicenses } from "@/lib/api";
import { PageHeader } from "@/components/shell/page-header";
import type { License } from "@/lib/types";

import { KpiCard } from "./kpi-card";
import { RAMP_PRIMARY, STATUS } from "./chart-theme";
import { dateShort, daysUntil, num, relativeDays } from "./format";
import { useCompassQuery } from "./use-compass-query";

/**
 * License lifecycle (element 6): `GET /licenses`.
 *
 * Two things a portfolio office actually needs from this table, and both are
 * here:
 *
 *   RENEWAL ALERTS  the row's urgency is *computed from `renews_on`* against
 *                   today, not taken from the stored `status` string. A stored
 *                   status goes stale the moment nobody updates it. Both are
 *                   shown, and the computed one is labelled as computed, so a
 *                   disagreement between them is visible rather than hidden.
 *   DATASET LINKAGE each license names the datasets it entitles. Those names
 *                   are the upstream feeds whose data flows into the curated
 *                   tables, which is what ties "this license lapses" to "this
 *                   catalog entry stops refreshing".
 *
 * This table is a corporate asset register, not portfolio data: it carries no
 * `org_unit` column and no RLS policy, so both personas see the same rows. Said
 * plainly on the page rather than left for an evaluator to wonder about.
 */
type Band = "expired" | "critical" | "warning" | "watch" | "ok" | "perpetual";

const BAND_META: Record<Band, { label: string; className: string }> = {
  expired: { label: "Expired", className: "border-danger bg-danger-soft text-danger" },
  critical: { label: "Renew now", className: "border-danger bg-danger-soft text-danger" },
  warning: { label: "Renew soon", className: "border-warn bg-warn-soft text-warn" },
  watch: { label: "On watch", className: "border-border bg-info-soft text-info" },
  ok: { label: "Current", className: "border-border bg-surface-2 text-text-muted" },
  perpetual: { label: "No renewal", className: "border-border bg-surface-2 text-text-subtle" },
};

const STATUS_STYLE: Record<License["status"], string> = {
  active: "bg-success-soft text-success",
  expiring: "bg-warn-soft text-warn",
  expired: "bg-danger-soft text-danger",
  suspended: "bg-danger-soft text-danger",
};

function bandFor(days: number): Band {
  if (Number.isNaN(days)) return "ok";
  if (days > 3650) return "perpetual";
  if (days < 0) return "expired";
  if (days <= 30) return "critical";
  if (days <= 90) return "warning";
  if (days <= 180) return "watch";
  return "ok";
}

export function LicensesView() {
  const { data, error, loading, reload } = useCompassQuery(getLicenses);

  const licenses = data?.licenses ?? [];
  const rows = licenses
    .map((l) => ({
      license: l,
      days: l.days_to_renewal ?? daysUntil(l.renews_on),
      band: (l.renewal_alert?.level ?? bandFor(daysUntil(l.renews_on))) as Band,
    }))
    .sort((a, b) => a.days - b.days);

  const warningDays = data?.thresholds?.warning_days ?? 90;
  const needsAction = rows.filter(
    (r) =>
      r.license.needs_action ??
      (r.band === "expired" || r.band === "critical" || r.band === "warning"),
  );
  const seatRows = licenses.filter((l) => l.seats_total > 0);
  const seatsUsed = seatRows.reduce((a, l) => a + l.seats_used, 0);
  const seatsTotal = seatRows.reduce((a, l) => a + l.seats_total, 0);
  const datasetCount = new Set(licenses.flatMap((l) => l.datasets)).size;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        kicker="Strategic Prompt (e) | Data Vendor Lifecycle"
        title="Data subscriptions, licenses, and renewal controls"
        icon={<KeyRound className="size-4" aria-hidden />}
        lead="Every commercial and public feed Compass draws on, what it entitles, which datasets it covers, and when it lapses, so a renewal never surprises the pipeline that depends on it."
        actions={
          <button
            type="button"
            onClick={reload}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded border border-border bg-surface px-3 py-2 text-[12px] font-semibold text-text shadow-soft transition-colors hover:bg-surface-2 disabled:opacity-50"
          >
            <RefreshCw className={loading ? "size-3.5 animate-spin" : "size-3.5"} aria-hidden />
            Refresh
          </button>
        }
      />

      {error ? (
        <div className="rounded-md border border-danger bg-danger-soft px-4 py-3 text-[12.5px] text-danger">
          Could not load licenses: {error}
        </div>
      ) : null}

      {loading && !data ? (
        <div className="flex flex-col gap-4" aria-busy>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="skeleton h-[104px] rounded-md" />
            ))}
          </div>
          <div className="skeleton h-[380px] rounded-md" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard label="Licenses tracked" value={licenses.length} sublabel="vendors and public feeds" Icon={KeyRound} />
            <KpiCard
              label={`Need action within ${warningDays} days`}
              value={needsAction.length}
              sublabel="expired or renewing soon"
              tone={needsAction.length > 0 ? "warn" : "default"}
              Icon={TriangleAlert}
            />
            <KpiCard
              label="Seat utilization"
              value={seatsTotal > 0 ? Math.round((seatsUsed / seatsTotal) * 100) : 0}
              format={(n) => `${n}%`}
              sublabel={`${num(seatsUsed)} of ${num(seatsTotal)} named seats`}
              Icon={Users}
            />
            <KpiCard
              label="Datasets covered"
              value={datasetCount}
              sublabel="distinct entitled feeds"
              Icon={Database}
            />
          </div>

          {/* ---- Renewal alerts ---------------------------------------- */}
          {needsAction.length > 0 ? (
            <section className="rounded-md border border-warn bg-warn-soft px-4 py-3">
              <h2 className="flex items-center gap-2 text-[13px] font-semibold text-warn">
                <CalendarClock className="size-4" aria-hidden />
                Renewal alerts
              </h2>
              <ul className="mt-2 flex flex-col gap-1.5">
                {needsAction.map(({ license, days, band }) => (
                  <li key={license.id} className="text-[12px] leading-snug text-text">
                    <span className="font-semibold text-text-strong">
                      {license.vendor}: {license.product}
                    </span>{" "}
                    renews {dateShort(license.renews_on)} ({relativeDays(days)}).{" "}
                    <span className="text-text-muted">
                      Owner {license.owner}. Covers {license.datasets.join(", ") || "no linked datasets"}.
                    </span>{" "}
                    <span className="font-semibold text-warn">{BAND_META[band].label}.</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[10.5px] text-text-muted">
                {data?.thresholds?.note ?? "Renewal urgency is calculated by the service from the recorded renewal date."}
              </p>
            </section>
          ) : null}

          {/* ---- Table ------------------------------------------------- */}
          <section className="rounded-md border border-border bg-surface shadow-soft">
            <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
              <div>
                <h2 className="text-[14.5px] font-semibold text-text-strong">License register</h2>
                <p className="mt-0.5 max-w-2xl text-[11.5px] leading-snug text-text-muted">
                  Sorted by soonest renewal. Datasets name the upstream feeds each license entitles,
                  the link between a lapsing agreement and the curated tables that stop refreshing
                  without it.
                </p>
              </div>
              <Link
                href="/catalog/"
                className="inline-flex shrink-0 items-center gap-1 rounded border border-border px-2.5 py-1.5 text-[11px] font-semibold text-link transition-colors hover:bg-surface-2"
              >
                Data catalog
                <ArrowUpRight className="size-3" aria-hidden />
              </Link>
            </header>

            <div
              className="overflow-x-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-gov-primary"
              role="region"
              aria-label="License register table"
              tabIndex={0}
            >
              <table className="w-full min-w-[900px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-border text-[10px] uppercase tracking-[0.1em] text-text-subtle">
                    <th scope="col" className="px-4 py-2.5 font-semibold">Vendor / product</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold">Datasets</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold">Entitlements</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold">Seats</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold">Renews</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold">Owner</th>
                    <th scope="col" className="px-4 py-2.5 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ license, days, band }) => (
                    <tr key={license.id} className="border-b border-border-2 align-top last:border-b-0">
                      <td className="px-4 py-3">
                        <p className="text-[12.5px] font-semibold text-text-strong">{license.vendor}</p>
                        <p className="mt-0.5 max-w-[220px] text-[11.5px] leading-snug text-text-muted">
                          {license.product}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        {license.datasets.length > 0 ? (
                          <ul className="flex flex-wrap gap-1">
                            {license.datasets.map((ds) => (
                              <li
                                key={ds}
                                className="rounded border border-border-2 bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px] text-gov-primary"
                              >
                                {ds}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-[11.5px] text-text-subtle">Not available</span>
                        )}
                      </td>
                      <td className="max-w-[240px] px-4 py-3 text-[11.5px] leading-snug text-text-muted">
                        {license.entitlements}
                      </td>
                      <td className="px-4 py-3">
                        <SeatMeter used={license.seats_used} total={license.seats_total} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <p className="font-mono text-[11.5px] text-text-strong">
                          {dateShort(license.renews_on)}
                        </p>
                        <p className="mt-0.5 text-[10.5px] text-text-muted">{relativeDays(days)}</p>
                        <span
                          className={clsx(
                            "mt-1 inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold",
                            BAND_META[band].className,
                          )}
                          title="Computed from renews_on against today"
                        >
                          {BAND_META[band].label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[11.5px] text-text">{license.owner}</td>
                      <td className="px-4 py-3">
                        <span
                          className={clsx(
                            "rounded px-1.5 py-0.5 text-[10.5px] font-semibold capitalize",
                            STATUS_STYLE[license.status],
                          )}
                          title="Effective lifecycle calculated by the service"
                        >
                          {license.status}
                        </span>
                        {license.status_stored && license.status_stored !== license.status ? (
                          <p className="mt-1 text-[10px] text-warn">
                            Register says {license.status_stored}
                          </p>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <footer className="border-t border-border px-4 py-3 text-[10.5px] leading-snug text-text-subtle">
              <code className="font-mono text-[10px]">GET /licenses</code> → the{" "}
              <code className="font-mono text-[10px]">compass.licenses</code> table. It is a
              corporate asset register with no <code className="font-mono text-[10px]">org_unit</code>{" "}
              column, so unlike the portfolio it carries no row-level security policy and reads the
              same for every persona. Renewal urgency and effective status come from the service
              using its published thresholds. A differing stored register value is shown beside it.
            </footer>
          </section>
        </>
      )}
    </div>
  );
}

function SeatMeter({ used, total }: { used: number; total: number }) {
  if (total <= 0) {
    return <span className="text-[11.5px] text-text-subtle">Unmetered</span>;
  }
  const ratio = Math.min(1, used / total);
  const fill = ratio >= 1 ? STATUS.critical : ratio >= 0.8 ? STATUS.warn : RAMP_PRIMARY[4]!;
  return (
    <div className="min-w-[92px]">
      <p className="font-mono text-[11.5px] tabular-nums text-text-strong">
        {num(used)} / {num(total)}
      </p>
      <div
        className="mt-1 h-2 w-full overflow-hidden rounded-[2px]"
        style={{ background: RAMP_PRIMARY[0] }}
        role="img"
        aria-label={`${used} of ${total} seats in use`}
      >
        <div className="h-full rounded-r-[4px]" style={{ width: `${ratio * 100}%`, background: fill }} />
      </div>
    </div>
  );
}

export default LicensesView;

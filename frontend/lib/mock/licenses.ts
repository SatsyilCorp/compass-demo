/**
 * GET /licenses fixture. Element 6. Mirrors `licenses` in
 * db/migrations/001_schema.sql. Not org_unit-scoped (a corporate asset
 * table), so identical for both demo personas.
 */
import type { License, LicensesResponse } from "@/lib/types";

const LICENSES: License[] = [
  {
    id: 1,
    vendor: "GovTribe",
    product: "Federal Opportunity & Award Intelligence API",
    datasets: ["contract_awards", "grant_awards", "forecasts"],
    entitlements: "Enterprise: unlimited seats, 90-day rolling data window",
    seats_used: 14,
    seats_total: 25,
    renews_on: "2027-02-01",
    owner: "Portfolio Analytics (Code 30)",
    status: "active",
  },
  {
    id: 2,
    vendor: "USAspending.gov",
    product: "Bulk Award Data API",
    datasets: ["federal_actions", "sub_awards"],
    entitlements: "Public API: no seat limit",
    seats_used: 0,
    seats_total: 0,
    renews_on: "2099-01-01",
    owner: "Data Engineering",
    status: "active",
  },
  {
    id: 3,
    vendor: "AWS",
    product: "Bedrock: amazon.nova-lite-v1:0 / titan-embed-text-v2:0",
    datasets: ["grant_abstracts_embeddings"],
    entitlements: "On-demand, IL5 boundary (govcloud-equivalent config)",
    seats_used: 8,
    seats_total: 20,
    renews_on: "2026-12-31",
    owner: "AI Governance",
    status: "active",
  },
  {
    id: 4,
    vendor: "GSA FPDS-NG",
    product: "Federal Procurement Data System, Next Generation",
    datasets: ["contract_actions"],
    entitlements: "Public feed: nightly ATOM sync",
    seats_used: 0,
    seats_total: 0,
    renews_on: "2026-09-15",
    owner: "Data Engineering",
    status: "expiring",
  },
  {
    id: 5,
    vendor: "SAM.gov",
    product: "Entity Management API",
    datasets: ["awardee_entities"],
    entitlements: "System account: 10,000 calls/day",
    seats_used: 1,
    seats_total: 1,
    renews_on: "2027-05-20",
    owner: "Data Engineering",
    status: "active",
  },
  {
    id: 6,
    vendor: "Esri",
    product: "ArcGIS Enterprise (maritime AOR overlays)",
    datasets: ["aor_boundaries"],
    entitlements: "5 named-user licenses",
    seats_used: 5,
    seats_total: 5,
    renews_on: "2026-11-30",
    owner: "Portfolio Analytics (Code 30)",
    status: "expiring",
  },
];

export function getLicenses(): LicensesResponse {
  const replayToday = new Date("2026-08-10T12:00:00.000Z");
  const licenses = LICENSES.map((license) => {
    const renewal = new Date(`${license.renews_on}T12:00:00.000Z`);
    const days = Math.round((renewal.getTime() - replayToday.getTime()) / 86_400_000);
    const level = days < 0 ? "expired" : days <= 30 ? "critical" : days <= 90 ? "warning" : "ok";
    const status = license.status === "suspended"
      ? "suspended"
      : level === "expired"
        ? "expired"
        : level === "critical" || level === "warning"
          ? "expiring"
          : "active";
    const utilization = license.seats_total > 0
      ? Math.round((license.seats_used / license.seats_total) * 1000) / 10
      : null;
    const seatLevel = license.seats_total > 0 && license.seats_used >= license.seats_total
      ? "critical"
      : utilization !== null && utilization >= 90
        ? "warning"
        : "ok";
    return {
      ...license,
      status,
      status_stored: license.status,
      days_to_renewal: days,
      renewal_alert: {
        level,
        days_to_renewal: days,
        message: `Replay clock: ${days} day(s) until ${license.renews_on}.`,
      },
      seat_alert: {
        level: seatLevel,
        utilization_pct: utilization,
        seats_available: license.seats_total > 0
          ? license.seats_total - license.seats_used
          : null,
        message: license.seats_total > 0
          ? `${license.seats_used} of ${license.seats_total} seats assigned.`
          : "Unmetered entitlement.",
      },
      needs_action: level === "expired" || level === "critical" || seatLevel === "critical",
    } satisfies License;
  });
  return {
    licenses,
    thresholds: {
      critical_days: 30,
      warning_days: 90,
      seat_warn_ratio: 0.9,
      note: "Replay mode uses the deterministic 2026-08-10 scenario clock.",
    },
  };
}

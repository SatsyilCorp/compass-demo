"""Data-license lifecycle API - element 6 of the Compass demo.

Route (docs/CONTRACTS.md):

    GET /licenses -> {"licenses": [...], "alerts": [...], "summary": {...}, ...}

An S&T portfolio office buys commercial data (bibliometrics, award feeds,
geospatial) under seat- and term-limited licenses, and the two ways that bites
are (a) a term lapsing under a live pipeline and (b) seats quietly hitting the
cap. So this endpoint is not a table dump: every row is scored against the
renewal window and its seat utilisation, and the rows that need action are
lifted into a separate ``alerts`` list the dashboard can render directly.

Two honesty rules the implementation follows:

* **The date decides the lifecycle, not the stored string.** ``licenses.status``
  is whatever a human last typed. The response reports an ``effective_status``
  derived from ``renews_on`` against today's date *in the database* (so the
  clock is the DB's, not a Lambda's), and keeps the stored value alongside as
  ``status_stored`` so a discrepancy is visible rather than papered over. The
  one stored value that always wins is ``suspended`` - that is an
  administrative state a date cannot infer.
* **Thresholds are stated, not implied.** The response carries the day windows
  it used, so "expiring" always comes with the number that made it so.

Licenses are a corporate asset register, not portfolio rows: the table carries
no ``org_unit`` and has no RLS policy, so both personas see the same list. The
query still runs inside :func:`compass_common.db.set_org` to keep every Compass
read on the same transactional pattern (and to make the omission of RLS here a
deliberate, reviewable choice rather than a forgotten one).
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from compass_common import db, http

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Renewal windows (days). Env-tunable so a demo can force an alert without
# editing seed data.
CRITICAL_DAYS = int(os.environ.get("LICENSE_CRITICAL_DAYS", "30"))
WARNING_DAYS = int(os.environ.get("LICENSE_WARNING_DAYS", "90"))
# Seat utilisation at or above this fraction raises a capacity alert.
SEAT_WARN_RATIO = float(os.environ.get("LICENSE_SEAT_WARN_RATIO", "0.9"))

LEVEL_ORDER = {"expired": 0, "critical": 1, "warning": 2, "ok": 3}


def resolve_identity(claims: http.Claims) -> Tuple[Optional[str], Optional[str]]:
    """Delegate to the shared deny-by-default identity contract."""
    return http.resolve_identity(claims)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def renewal_alert(days: Optional[int], renews_on: Any) -> Dict[str, Any]:
    """Classify a renewal date into ``{level, message, days_to_renewal}``."""
    when = _iso(renews_on)
    if days is None:
        return {
            "level": "warning",
            "days_to_renewal": None,
            "message": "No renewal date recorded - term cannot be verified.",
        }
    if days < 0:
        return {
            "level": "expired",
            "days_to_renewal": days,
            "message": f"Term ended {abs(days)} day(s) ago on {when}. "
                       "Any pipeline still calling this vendor is out of entitlement.",
        }
    if days <= CRITICAL_DAYS:
        return {
            "level": "critical",
            "days_to_renewal": days,
            "message": f"Renews in {days} day(s) on {when} - inside the "
                       f"{CRITICAL_DAYS}-day critical window; start the renewal action now.",
        }
    if days <= WARNING_DAYS:
        return {
            "level": "warning",
            "days_to_renewal": days,
            "message": f"Renews in {days} day(s) on {when} - inside the "
                       f"{WARNING_DAYS}-day planning window.",
        }
    return {
        "level": "ok",
        "days_to_renewal": days,
        "message": f"Renews {when} ({days} day(s) out).",
    }


def seat_alert(used: Optional[int], total: Optional[int]) -> Dict[str, Any]:
    """Classify seat utilisation. Unmetered licenses (total 0/None) are ``ok``."""
    if not total:
        return {
            "level": "ok",
            "utilization_pct": None,
            "seats_available": None,
            "message": "Unmetered entitlement - no seat cap.",
        }
    used = used or 0
    pct = round(100.0 * used / total, 1)
    available = total - used
    if used >= total:
        level = "critical"
        message = (f"All {total} seat(s) assigned - new users cannot be onboarded "
                   "without buying seats.")
    elif pct >= SEAT_WARN_RATIO * 100:
        level = "warning"
        message = f"{used} of {total} seats assigned ({pct}%) - {available} left."
    else:
        level = "ok"
        message = f"{used} of {total} seats assigned ({pct}%)."
    return {
        "level": level,
        "utilization_pct": pct,
        "seats_available": available,
        "message": message,
    }


def effective_status(stored: Optional[str], renewal_level: str) -> str:
    """Lifecycle state the dates support, with ``suspended`` always winning.

    Returns one of active|expiring|expired|suspended (the frontend's union).
    """
    if (stored or "").lower() == "suspended":
        return "suspended"
    if renewal_level == "expired":
        return "expired"
    if renewal_level in ("critical", "warning"):
        return "expiring"
    return "active"


def load_licenses(conn) -> List[Dict[str, Any]]:
    """Read the register and score every row. ``CURRENT_DATE`` is the DB clock."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, vendor, product, datasets, entitlements,
                   seats_used, seats_total, renews_on, owner, status,
                   (renews_on - CURRENT_DATE) AS days_to_renewal
              FROM licenses
             ORDER BY renews_on NULLS LAST, vendor, product
            """
        )
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    out: List[Dict[str, Any]] = []
    for r in rows:
        days = _int(r["days_to_renewal"])
        ren = renewal_alert(days, r["renews_on"])
        seats = seat_alert(_int(r["seats_used"]), _int(r["seats_total"]))
        out.append(
            {
                "id": _int(r["id"]),
                "vendor": r["vendor"],
                "product": r["product"],
                "datasets": list(r["datasets"] or []),
                "entitlements": r["entitlements"],
                "seats_used": _int(r["seats_used"]) or 0,
                "seats_total": _int(r["seats_total"]) or 0,
                "renews_on": _iso(r["renews_on"]),
                "owner": r["owner"],
                # `status` is the lifecycle the dates support (what the UI shows);
                # `status_stored` is what the register says, so drift is visible.
                "status": effective_status(r["status"], ren["level"]),
                "status_stored": r["status"],
                "days_to_renewal": days,
                "renewal_alert": ren,
                "seat_alert": seats,
                "needs_action": ren["level"] in ("expired", "critical")
                or seats["level"] == "critical",
            }
        )
    return out


def summarize(licenses: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    for lic in licenses:
        by_status[lic["status"]] = by_status.get(lic["status"], 0) + 1
    seats_total = sum(lic["seats_total"] for lic in licenses)
    seats_used = sum(lic["seats_used"] for lic in licenses)
    return {
        "total": len(licenses),
        "by_status": by_status,
        "expired": sum(
            1
            for license_item in licenses
            if license_item["renewal_alert"]["level"] == "expired"
        ),
        "renewing_within_critical_days": sum(
            1
            for license_item in licenses
            if license_item["renewal_alert"]["level"] == "critical"
        ),
        "renewing_within_warning_days": sum(
            1
            for license_item in licenses
            if license_item["renewal_alert"]["level"] == "warning"
        ),
        "at_seat_capacity": sum(
            1
            for license_item in licenses
            if license_item["seat_alert"]["level"] == "critical"
        ),
        "needs_action": sum(
            1 for license_item in licenses if license_item["needs_action"]
        ),
        "seats_used": seats_used,
        "seats_total": seats_total,
        "seat_utilization_pct": round(100.0 * seats_used / seats_total, 1)
        if seats_total
        else None,
    }


def build_alerts(licenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten the non-ok renewal/seat findings into one urgency-sorted list."""
    alerts: List[Dict[str, Any]] = []
    for lic in licenses:
        for kind, key in (("renewal", "renewal_alert"), ("seats", "seat_alert")):
            a = lic[key]
            if a["level"] == "ok":
                continue
            alerts.append(
                {
                    "license_id": lic["id"],
                    "vendor": lic["vendor"],
                    "product": lic["product"],
                    "owner": lic["owner"],
                    "kind": kind,
                    "level": a["level"],
                    "message": a["message"],
                    "renews_on": lic["renews_on"],
                    "days_to_renewal": lic["days_to_renewal"],
                }
            )
    alerts.sort(
        key=lambda a: (
            LEVEL_ORDER.get(a["level"], 9),
            a["days_to_renewal"] if a["days_to_renewal"] is not None else 10**6,
        )
    )
    return alerts


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    claims = http.get_claims(event)
    role, org_unit = resolve_identity(claims)
    if not role:
        return http.forbidden(
            "no Compass role on this identity - expected one of the "
            "compass-poweruser / compass-viewer Cognito groups"
        )

    try:
        conn = db.get_conn()
        with db.set_org(conn, org_unit) as c:
            licenses = load_licenses(c)
    except Exception:
        log.exception("license lookup failed")
        return http.server_error("license query failed")

    return http.ok(
        {
            "licenses": licenses,
            "alerts": build_alerts(licenses),
            "summary": summarize(licenses),
            "thresholds": {
                "critical_days": CRITICAL_DAYS,
                "warning_days": WARNING_DAYS,
                "seat_warn_ratio": SEAT_WARN_RATIO,
                "note": "Renewal levels are computed against CURRENT_DATE in "
                        "PostgreSQL, so every caller sees the same clock.",
            },
            "scope": {
                "org_unit": org_unit,
                "note": "The license register is a corporate asset table with no "
                        "org_unit column and no RLS policy - both personas see "
                        "the same rows by design.",
            },
        }
    )

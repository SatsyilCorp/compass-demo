"""DashboardFunction — GET /dashboard (element 6, docs/CONTRACTS.md).

One round trip: every KPI tile + every chart series the executive dashboard
page needs, computed from the live `compass` schema and shaped to exactly
match `frontend/lib/types.ts::DashboardResponse` (the locked wire contract
the frontend already builds against). Mirrors the single-endpoint aggregation
pattern proven in a prior production dashboard service: one Lambda,
several small GROUP BY queries against a shared cursor, assembled into one
JSON body, cached in-process for 60s.

RLS / CLS
---------
`grants_curated` is the only RLS-protected table (db/migrations/002_rls.sql).
Every query against it runs inside `compass_common.db.set_org(conn,
claims.org_unit)`, which issues `SET LOCAL compass.org_unit = <claim>` so the
`grants_rls_read` policy filters rows automatically — this module never adds
its own `WHERE org_unit = ...` clause.

Column-Level Security masks `amount_usd`: `compass_app` has that column
REVOKEd on the base table for every persona, and only the unmasked
`grants_curated_corp` view carries it (granted back via the schema's default
privileges). This module reads dollar figures ONLY when
`claims.is_corporate` (org_unit == ONR-Corporate) — the same branch under
which the RLS policy already admits every row unconditionally, so which
identity Postgres uses to evaluate the view's underlying SELECT is moot: the
policy's `current_setting(...) = 'ONR-Corporate'` clause is true regardless.
For every other org_unit this module queries the base table and never
selects `amount_usd`, so a caller can't even accidentally request a column
its role isn't granted — the same "poweruser reads the corp view, viewer
reads the masked base table" split already documented in
`frontend/lib/mock/grants.ts` (`maskAmount`).

`grant_quality`, `anomalies`, `approvals`, `model_runs`, `topics` and
`grant_topics` carry no RLS of their own (only `grants_curated` does per
002_rls.sql). Anomalies are still scoped to the caller's visible portfolio by
joining through `grants_curated` (which RLS filters); quality/approvals
telemetry is intentionally global operational data, not per-grant.

Every numeric value pulled out of Postgres (NUMERIC -> Decimal, bigint ->
int) is cast to a native Python type before it reaches `http.ok()` — psycopg2
Decimals would otherwise fall through `json.dumps(..., default=str)` as JSON
*strings*, silently breaking every `number | null` field in the contract.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from compass_common import db, http

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 60

# The only two tables this module ever selects grants from: the masked base
# table (default, every non-corporate org_unit) and the unmasked corporate
# view (only when the caller's RLS context is ONR-Corporate). Never built
# from request input — always one of exactly these two literals.
_BASE_TABLE = "grants_curated"
_CORP_VIEW = "grants_curated_corp"


def _table(is_corporate: bool) -> str:
    return _CORP_VIEW if is_corporate else _BASE_TABLE


# --------------------------------------------------------------------------- #
# Chart series — each a single GROUP BY, RLS-filtered via the caller's
# SET LOCAL compass.org_unit context (see db.set_org in the handler below).
# --------------------------------------------------------------------------- #
def _funding_by_program_area(cur, is_corporate: bool) -> List[Dict[str, Any]]:
    if is_corporate:
        cur.execute(
            f"""
            SELECT program_area, count(*), COALESCE(sum(amount_usd), 0)
            FROM {_CORP_VIEW}
            GROUP BY program_area
            ORDER BY count(*) DESC, program_area ASC
            """
        )
        return [
            {"program_area": r[0], "grant_count": int(r[1]), "amount_usd": float(r[2])}
            for r in cur.fetchall()
        ]
    cur.execute(
        f"""
        SELECT program_area, count(*)
        FROM {_BASE_TABLE}
        GROUP BY program_area
        ORDER BY count(*) DESC, program_area ASC
        """
    )
    return [{"program_area": r[0], "grant_count": int(r[1]), "amount_usd": None} for r in cur.fetchall()]


def _funding_by_fiscal_year(cur, is_corporate: bool) -> List[Dict[str, Any]]:
    if is_corporate:
        cur.execute(
            f"""
            SELECT fiscal_year, COALESCE(sum(amount_usd), 0)
            FROM {_CORP_VIEW}
            GROUP BY fiscal_year
            ORDER BY fiscal_year ASC
            """
        )
        return [{"fiscal_year": int(r[0]), "amount_usd": float(r[1])} for r in cur.fetchall()]
    cur.execute(f"SELECT DISTINCT fiscal_year FROM {_BASE_TABLE} ORDER BY fiscal_year ASC")
    return [{"fiscal_year": int(r[0]), "amount_usd": None} for r in cur.fetchall()]


def _quality_trend(cur) -> List[Dict[str, Any]]:
    """One point per ingest run: the mean of that run's per-rule quality
    scores, ordered by when the run actually landed. Global — grant_quality
    carries no org_unit and no RLS policy (batch/pipeline telemetry, not
    portfolio data)."""
    cur.execute(
        """
        SELECT run_id, MIN(created_at) AS run_started, AVG(score) AS avg_score
        FROM grant_quality
        GROUP BY run_id
        ORDER BY run_started ASC
        """
    )
    out = []
    for run_id, run_started, avg_score in cur.fetchall():
        out.append(
            {
                "run_id": run_id,
                "date": run_started.isoformat() if run_started else None,
                "score": round(float(avg_score), 1) if avg_score is not None else 0.0,
            }
        )
    return out


def _top_topics(cur, is_corporate: bool) -> List[Dict[str, Any]]:
    """Top 5 topics from the most recent completed topic_model run, weighted
    by how many of the CALLER'S VISIBLE grants carry that topic. Empty list
    (not an error) when no analytics run has been executed yet — /analytics/run
    is a separate element and may not have run before the demo dashboard
    first loads."""
    cur.execute(
        "SELECT run_id FROM model_runs WHERE kind = 'topic_model' ORDER BY created_at DESC LIMIT 1"
    )
    latest = cur.fetchone()
    if not latest:
        return []
    run_id = latest[0]

    # The grants_curated join is what makes this RLS-aware: gt.grant_id rows
    # whose grant isn't visible under the caller's org context simply don't
    # match and drop out of the count, regardless of is_corporate.
    cur.execute(
        """
        SELECT t.topic_id, t.label, count(gt.grant_id) AS grant_count
        FROM topics t
        JOIN grant_topics gt ON gt.run_id = t.run_id AND gt.topic_id = t.topic_id
        JOIN grants_curated g ON g.id = gt.grant_id
        WHERE t.run_id = %s
        GROUP BY t.topic_id, t.label
        """,
        (run_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return []
    total = sum(int(r[2]) for r in rows) or 1
    ranked = sorted(rows, key=lambda r: r[2], reverse=True)[:5]
    return [
        {"topic_id": int(r[0]), "label": r[1], "weight": round(int(r[2]) / total, 3)}
        for r in ranked
    ]


def _org_unit_breakdown(cur, is_corporate: bool) -> List[Dict[str, Any]]:
    if is_corporate:
        cur.execute(
            f"""
            SELECT org_unit, count(*), COALESCE(sum(amount_usd), 0)
            FROM {_CORP_VIEW}
            GROUP BY org_unit
            ORDER BY count(*) DESC, org_unit ASC
            """
        )
        return [
            {"org_unit": r[0], "grant_count": int(r[1]), "amount_usd": float(r[2])}
            for r in cur.fetchall()
        ]
    cur.execute(
        f"""
        SELECT org_unit, count(*)
        FROM {_BASE_TABLE}
        GROUP BY org_unit
        ORDER BY count(*) DESC, org_unit ASC
        """
    )
    return [{"org_unit": r[0], "grant_count": int(r[1]), "amount_usd": None} for r in cur.fetchall()]


def _open_anomalies_count(cur) -> int:
    """Anomalies carry no org_unit column of their own; scope them to the
    caller's visible portfolio by requiring their grant (when they have one)
    to show up in a `grants_curated` select — RLS filters that select the
    same way it filters every other query in this module. Batch-level
    anomalies with no grant_id (grant_id IS NULL) are portfolio-wide
    findings, not tied to one org, so they always count."""
    cur.execute(
        """
        SELECT count(*)
        FROM anomalies a
        WHERE a.status = 'open'
          AND (a.grant_id IS NULL OR EXISTS (SELECT 1 FROM grants_curated g WHERE g.id = a.grant_id))
        """
    )
    return int(cur.fetchone()[0])


def _pending_approvals_count(cur) -> int:
    cur.execute("SELECT count(*) FROM approvals WHERE state = 'pending'")
    return int(cur.fetchone()[0])


# --------------------------------------------------------------------------- #
# Assemble the full DashboardResponse
# --------------------------------------------------------------------------- #
def _compute_dashboard(cur, is_corporate: bool) -> Dict[str, Any]:
    program_area_rows = _funding_by_program_area(cur, is_corporate)
    fiscal_year_rows = _funding_by_fiscal_year(cur, is_corporate)
    quality_rows = _quality_trend(cur)
    topic_rows = _top_topics(cur, is_corporate)
    org_unit_rows = _org_unit_breakdown(cur, is_corporate)

    # KPI tiles are DERIVED from the chart series wherever possible (rather
    # than a second independent count) so the tile and the chart underneath
    # it can never disagree — the same discipline the frontend fixture's
    # docstring calls out (lib/mock/dashboard.ts).
    total_grants = sum(r["grant_count"] for r in program_area_rows)
    total_funding_usd: Optional[float] = (
        round(sum(r["amount_usd"] for r in program_area_rows), 2) if is_corporate else None
    )
    avg_quality_score = (
        round(sum(r["score"] for r in quality_rows) / len(quality_rows), 1) if quality_rows else 100.0
    )

    return {
        "kpis": {
            "total_grants": total_grants,
            "total_funding_usd": total_funding_usd,
            "active_program_areas": len(program_area_rows),
            "avg_quality_score": avg_quality_score,
            "open_anomalies": _open_anomalies_count(cur),
            "pending_approvals": _pending_approvals_count(cur),
        },
        "funding_by_program_area": program_area_rows,
        "funding_by_fiscal_year": fiscal_year_rows,
        "quality_trend": quality_rows,
        "top_topics": topic_rows,
        "org_unit_breakdown": org_unit_rows,
    }


# --------------------------------------------------------------------------- #
# In-process cache — keyed on the RLS context that actually changes the
# result set (org_unit + whether it resolves to the unmasked corporate
# view). 60s TTL: the underlying data moves at ingest/analytics-run cadence,
# so a demo audience never notices a minute-old dashboard, and this keeps
# the DB off the hot path for repeated dashboard loads within a session.
# --------------------------------------------------------------------------- #
def _cache_key(org_unit: str, is_corporate: bool) -> str:
    raw = json.dumps({"org_unit": org_unit, "is_corporate": is_corporate}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _log(**fields: Any) -> None:
    print(json.dumps(fields, default=str))


def handler(event, context):
    method = http.get_method(event) or "GET"
    if method == "OPTIONS":
        return http.json_response(200, {})

    claims = http.get_claims(event)
    if not claims.is_authenticated:
        return http.unauthorized()

    key = _cache_key(claims.org_unit, claims.is_corporate)
    now = time.time()
    cached = CACHE.get(key)
    if cached is not None and cached["expires"] > now:
        _log(
            fn=getattr(context, "function_name", "dashboard"),
            request_id=getattr(context, "aws_request_id", None),
            route="GET /dashboard",
            org_unit=claims.org_unit,
            cache="hit",
        )
        return http.ok(cached["value"])

    try:
        conn = db.get_conn()
        with db.set_org(conn, claims.org_unit) as c:
            with c.cursor() as cur:
                body = _compute_dashboard(cur, claims.is_corporate)
    except Exception as exc:  # noqa: BLE001 — never leak internals to the caller
        _log(
            fn=getattr(context, "function_name", "dashboard"),
            request_id=getattr(context, "aws_request_id", None),
            route="GET /dashboard",
            org_unit=claims.org_unit,
            error=str(exc),
        )
        return http.server_error("failed to compute dashboard")

    CACHE[key] = {"value": body, "expires": now + CACHE_TTL_SECONDS}

    _log(
        fn=getattr(context, "function_name", "dashboard"),
        request_id=getattr(context, "aws_request_id", None),
        route="GET /dashboard",
        org_unit=claims.org_unit,
        is_corporate=claims.is_corporate,
        cache="miss",
        total_grants=body["kpis"]["total_grants"],
    )
    return http.ok(body)

"""Summarize Lambda - GET /dashboard, GET /anomalies, and the executive
weekly summary (Bedrock Nova Lite), per docs/CONTRACTS.md element 6.

GET /dashboard - ONE round trip: KPIs + every chart series + the latest
stored executive summary. Response shape (the frontend contract):

    {
      "as_of": iso8601, "org_unit": str, "masked": bool,
      "kpis": {
        "total_grants": int, "total_funding_usd": float|null,
        "program_areas": int, "fiscal_year_range": [int, int]|null,
        "open_anomalies": int, "pending_approvals": int,
        "licenses_renewing_60d": int
      },
      "series": {
        "grants_by_fy":            [{"fiscal_year", "grants", "amount_usd"|null}],
        "funding_by_program_area": [{"program_area", "grants", "amount_usd"|null}],
        "grants_by_org_unit":      [{"org_unit", "grants"}],
        "anomalies_by_severity":   [{"severity", "count"}],
        "topic_trend": {"run_id": str|null,
                        "topics": [{"topic_id","label","top_terms","trend"}]}
      },
      "executive_summary": {"run_id","text","generated_at"} | null
    }

``?refresh=true`` (corporate persona only) regenerates the executive summary
synchronously via Bedrock before returning.

GET /anomalies - open anomalies, INNER-JOINed to ``grants_curated`` so RLS
filters them to grants the caller can see. Dollar figures inside ``reason``
are masked for non-corporate callers (CLS: viewers cannot read amounts).

Weekly executive summary - also callable OUTSIDE the API by the
approvals/dashboard flow with a direct Lambda invoke::

    {"action": "weekly_summary"}            # runs as ONR-Corporate, actor "system"

Generation snapshots the portfolio state (KPIs, latest topic-model movement,
open anomalies, licenses renewing <= 60 days), asks Nova Lite for a ~200-word
executive brief, and persists it to ``model_runs`` (kind ``weekly_summary``,
``recommendation`` = the brief) so GET /dashboard serves it with no model
call on the hot path.

RLS/CLS: every grant read runs inside ``db.set_org``; dollar sums come from
the ``grants_curated_corp`` view and only for the corporate persona - viewer
responses carry ``amount_usd: null`` and ``masked: true``.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

from compass_common import config, db, http, llm

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

SUMMARY_KIND = "weekly_summary"
DOLLAR_RE = re.compile(r"\$[0-9][0-9,]*(?:\.[0-9]+)?")

SUMMARY_SYSTEM_PROMPT = (
    "You are the executive briefer for Compass, an S&T portfolio intelligence "
    "platform over a synthetic (mock) ONR research-grant portfolio. From the "
    "JSON snapshot provided, write a crisp weekly executive summary of 150-220 "
    "words for portfolio leadership: 1) portfolio posture (size, spread), "
    "2) topic movement (what is emerging or contracting), 3) risk items "
    "(funding anomalies, licenses renewing soon, pending approvals), "
    "4) exactly one recommended action. Use ONLY figures present in the "
    "snapshot - never invent numbers. Plain prose, no markdown headings."
)


def handler(event, context):
    try:
        # Direct (non-HTTP) invoke: the approvals/dashboard flow's entry point.
        if not (event or {}).get("requestContext"):
            if (event or {}).get("action") == SUMMARY_KIND:
                conn = db.get_conn()
                with db.set_org(conn, config.CORPORATE_ORG_UNIT) as c:
                    return _generate_weekly_summary(c, actor="system")
            return {"error": f"unknown direct action {(event or {}).get('action')!r}"}

        claims = http.get_claims(event)
        if not claims.is_authenticated:
            return http.unauthorized()

        path = http.get_path(event) or ""
        if path.endswith("/anomalies"):
            return _get_anomalies(claims)
        if path.endswith("/dashboard"):
            refresh = http.query_params(event).get("refresh", "").lower() in (
                "1", "true", "yes",
            )
            return _get_dashboard(claims, refresh=refresh)
        return http.not_found("unknown summarize route")
    except ValueError as e:
        return http.bad_request(str(e))
    except Exception:
        logger.exception("summarize handler failed")
        return http.server_error()


# --------------------------------------------------------------------------- #
# GET /dashboard
# --------------------------------------------------------------------------- #
def _get_dashboard(claims, *, refresh: bool):
    corporate = claims.is_corporate
    if refresh and not corporate:
        return http.forbidden("summary refresh requires the ONR-Corporate persona")

    conn = db.get_conn()
    with db.set_org(conn, claims.org_unit) as c:
        if refresh:
            _generate_weekly_summary(c, actor=claims.username or claims.sub or "unknown")
        snapshot = _portfolio_snapshot(c, corporate=corporate)
        topic_trend = _latest_topic_trend(c)
        exec_summary = _latest_weekly_summary(c)

    return http.ok(
        {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "org_unit": claims.org_unit,
            "masked": not corporate,
            "kpis": snapshot["kpis"],
            "series": {
                "grants_by_fy": snapshot["grants_by_fy"],
                "funding_by_program_area": snapshot["funding_by_program_area"],
                "grants_by_org_unit": snapshot["grants_by_org_unit"],
                "anomalies_by_severity": snapshot["anomalies_by_severity"],
                "topic_trend": topic_trend,
            },
            "executive_summary": exec_summary,
        }
    )


def _portfolio_snapshot(c, *, corporate: bool):
    """All KPI counts + chart series in a handful of GROUP BY queries.

    Dollar sums only for the corporate persona (CLS): viewers get counts with
    ``amount_usd: null``. Grant reads are RLS-filtered by the ambient org GUC.
    """
    table = "grants_curated_corp" if corporate else "grants_curated"
    amount_expr = "SUM(amount_usd)" if corporate else "NULL"

    with c.cursor() as cur:
        cur.execute(
            f"SELECT fiscal_year, COUNT(*), {amount_expr} FROM {table} "
            "GROUP BY fiscal_year ORDER BY fiscal_year"
        )
        by_fy = [
            {
                "fiscal_year": r[0],
                "grants": r[1],
                "amount_usd": float(r[2]) if r[2] is not None else None,
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            f"SELECT program_area, COUNT(*), {amount_expr} FROM {table} "
            "GROUP BY program_area ORDER BY COUNT(*) DESC"
        )
        by_area = [
            {
                "program_area": r[0],
                "grants": r[1],
                "amount_usd": float(r[2]) if r[2] is not None else None,
            }
            for r in cur.fetchall()
        ]

        cur.execute(
            "SELECT org_unit, COUNT(*) FROM grants_curated "
            "GROUP BY org_unit ORDER BY org_unit"
        )
        by_org = [{"org_unit": r[0], "grants": r[1]} for r in cur.fetchall()]

        # Anomalies joined to grants so RLS decides visibility.
        cur.execute(
            "SELECT a.severity, COUNT(*) FROM anomalies a "
            "JOIN grants_curated g ON g.id = a.grant_id "
            "WHERE a.status = 'open' GROUP BY a.severity ORDER BY a.severity"
        )
        by_severity = [{"severity": r[0], "count": r[1]} for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*) FROM approvals WHERE state = 'pending'")
        pending_approvals = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM licenses WHERE status = 'active' "
            "AND renews_on <= CURRENT_DATE + INTERVAL '60 days'"
        )
        renewing = cur.fetchone()[0]

    total_grants = sum(e["grants"] for e in by_fy)
    total_funding = (
        sum(e["amount_usd"] for e in by_fy if e["amount_usd"] is not None)
        if corporate
        else None
    )
    fys = [e["fiscal_year"] for e in by_fy]
    return {
        "kpis": {
            "total_grants": total_grants,
            "total_funding_usd": total_funding,
            "program_areas": len(by_area),
            "fiscal_year_range": [min(fys), max(fys)] if fys else None,
            "open_anomalies": sum(e["count"] for e in by_severity),
            "pending_approvals": pending_approvals,
            "licenses_renewing_60d": renewing,
        },
        "grants_by_fy": by_fy,
        "funding_by_program_area": by_area,
        "grants_by_org_unit": by_org,
        "anomalies_by_severity": by_severity,
    }


def _latest_topic_trend(c):
    with c.cursor() as cur:
        cur.execute(
            "SELECT run_id FROM model_runs WHERE kind = 'topic_model' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            return {"run_id": None, "topics": []}
        run_id = row[0]
        cur.execute(
            "SELECT topic_id, label, top_terms, trend_jsonb "
            "FROM topics WHERE run_id = %s ORDER BY topic_id",
            (run_id,),
        )
        topics = [
            {"topic_id": r[0], "label": r[1], "top_terms": r[2], "trend": r[3]}
            for r in cur.fetchall()
        ]
    return {"run_id": run_id, "topics": topics}


def _latest_weekly_summary(c):
    with c.cursor() as cur:
        cur.execute(
            "SELECT run_id, recommendation, created_at FROM model_runs "
            "WHERE kind = %s ORDER BY created_at DESC LIMIT 1",
            (SUMMARY_KIND,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {"run_id": row[0], "text": row[1], "generated_at": row[2]}


# --------------------------------------------------------------------------- #
# GET /anomalies
# --------------------------------------------------------------------------- #
def _get_anomalies(claims):
    conn = db.get_conn()
    with db.set_org(conn, claims.org_unit) as c, c.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.grant_id, g.grant_no, g.title, g.program_area, "
            "       g.org_unit, a.kind, a.severity, a.reason, a.status, a.created_at "
            "FROM anomalies a JOIN grants_curated g ON g.id = a.grant_id "
            "WHERE a.status = 'open' "
            "ORDER BY CASE a.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
            "         a.created_at DESC "
            "LIMIT 200"
        )
        rows = cur.fetchall()

    mask = not claims.is_corporate
    anomalies = []
    for r in rows:
        reason = r[8]
        if mask and reason:
            # CLS: viewers cannot read dollar amounts anywhere, including here.
            reason = DOLLAR_RE.sub("$***", reason)
        anomalies.append(
            {
                "id": r[0],
                "grant_id": r[1],
                "grant_no": r[2],
                "title": r[3],
                "program_area": r[4],
                "org_unit": r[5],
                "kind": r[6],
                "severity": r[7],
                "reason": reason,
                "status": r[9],
                "created_at": r[10],
            }
        )
    return http.ok({"anomalies": anomalies, "count": len(anomalies), "masked": mask})


# --------------------------------------------------------------------------- #
# Weekly executive summary (Bedrock Nova Lite)
# --------------------------------------------------------------------------- #
def _generate_weekly_summary(c, *, actor: str):
    """Snapshot portfolio state, brief Nova Lite, persist to model_runs.

    Runs inside an ambient ``set_org`` transaction (corporate for the direct
    invoke path). Returns the summary payload (also the direct-invoke result).
    """
    snapshot = _portfolio_snapshot(c, corporate=True)
    topic_trend = _latest_topic_trend(c)

    movers = []
    for t in topic_trend["topics"]:
        growth = (t.get("trend") or {}).get("growth_pct")
        if growth is not None:
            movers.append({"label": t["label"], "growth_pct": growth})
    movers.sort(key=lambda m: -abs(m["growth_pct"]))

    with c.cursor() as cur:
        cur.execute(
            "SELECT recommendation FROM model_runs WHERE kind = 'topic_model' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    latest_recommendation = row[0] if row else None

    brief_input = {
        "week_of": datetime.now(timezone.utc).date().isoformat(),
        "kpis": snapshot["kpis"],
        "funding_by_program_area": snapshot["funding_by_program_area"][:8],
        "topic_movers": movers[:5],
        "latest_model_recommendation": latest_recommendation,
        "anomalies_by_severity": snapshot["anomalies_by_severity"],
    }

    result = llm.converse(
        system=SUMMARY_SYSTEM_PROMPT,
        user=json.dumps(brief_input, default=str),
        max_tokens=500,
        temperature=0.2,
    )
    text = result["text"].strip()

    run_id = f"ws-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    with c.cursor() as cur:
        cur.execute(
            "INSERT INTO model_runs (run_id, kind, params_jsonb, metrics_jsonb, recommendation) "
            "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s)",
            (
                run_id,
                SUMMARY_KIND,
                json.dumps({"actor": actor, "model_id": result["model_id"]}),
                json.dumps(brief_input, default=str),
                text,
            ),
        )
    logger.info("weekly summary %s generated by %s (%s chars)", run_id, actor, len(text))
    return {"run_id": run_id, "summary": text, "generated_at": datetime.now(timezone.utc).isoformat()}

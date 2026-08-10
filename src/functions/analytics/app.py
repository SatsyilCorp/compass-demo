"""Analytics Lambda — POST /analytics/run and GET /analytics/{run_id}.

POST /analytics/run  (poweruser / ONR-Corporate only)
    Body (all optional): {"k": 2..20 (default 8), "seed": int}
    Runs the real TF-IDF + NMF topic model in ``topic_model.py`` over every
    grant abstract the caller's RLS context can see, flags funding z-score
    anomalies, and persists in ONE transaction:
      * ``model_runs``   — params, metrics, and the decision RECOMMENDATION
      * ``topics``       — label, top_terms, per-FY trend (trend_jsonb)
      * ``grant_topics`` — doc→topic weights (>= 0.10, plus each dominant)
      * ``anomalies``    — new open ``funding_zscore`` rows (deduped against
                           existing open flags for the same grant)
      * ``lineage_nodes/edges`` — the analysis run's provenance graph
    Returns 200 with ``{"run_id", "status": "completed", ...}`` (the model runs
    in well under the 120 s timeout at this corpus size, so the route is
    synchronous by design — no fake job queue).

GET /analytics/{run_id}  (any authenticated caller)
    Returns ``{"run_id", "kind", "created_at", "params", "metrics",
    "recommendation", "topics": [{"topic_id", "label", "top_terms", "trend"}]}``
    or 404.

RLS/CLS notes
    * All grant reads run inside ``db.set_org(conn, claims.org_unit)`` — the
      caller's row-level view is what gets modeled.
    * ``amount_usd`` is column-revoked from ``compass_app`` on the base table
      (002_rls.sql); the anomaly routine reads it through the
      ``grants_curated_corp`` view, which is why POST is gated to the
      corporate persona — model output lands in shared (non-RLS) tables.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from compass_common import db, http

import topic_model

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

RUN_KIND = "topic_model"
ANOMALY_KIND = "funding_zscore"
DEFAULT_K = 8
DEFAULT_SEED = 20260810


def handler(event, context):
    try:
        claims = http.get_claims(event)
        if not claims.is_authenticated:
            return http.unauthorized()

        method = http.get_method(event)
        run_id = http.path_param(event, "run_id")
        if method == "POST":
            return _run_analytics(event, claims)
        if method == "GET" and run_id:
            return _get_run(run_id, claims)
        return http.not_found("unknown analytics route")
    except ValueError as e:
        return http.bad_request(str(e))
    except Exception:
        logger.exception("analytics handler failed")
        return http.server_error()


# --------------------------------------------------------------------------- #
# POST /analytics/run
# --------------------------------------------------------------------------- #
def _run_analytics(event, claims):
    if not (claims.is_corporate or claims.role == "poweruser"):
        return http.forbidden(
            "analytics runs write shared model output; requires the poweruser "
            "(ONR-Corporate) persona"
        )

    body = http.parse_body(event)
    try:
        k = int(body.get("k", DEFAULT_K))
        seed = int(body.get("seed", DEFAULT_SEED))
    except (TypeError, ValueError):
        return http.bad_request("'k' and 'seed' must be integers")
    if not 2 <= k <= 20:
        return http.bad_request("'k' must be between 2 and 20")

    run_id = f"tm-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    actor = claims.username or claims.sub or "unknown"

    conn = db.get_conn()
    with db.set_org(conn, claims.org_unit) as c:
        docs = _fetch_docs(c)
        try:
            result = topic_model.fit_topics(docs, k=k, seed=seed)
        except ValueError as e:
            return http.error_response(422, str(e))

        amount_rows = _fetch_amounts(c)
        flagged = topic_model.funding_zscores(amount_rows)
        new_anomalies = _persist_anomalies(c, flagged)

        recommendation = topic_model.build_recommendation(result, flagged)
        result.metrics["anomalies_flagged"] = len(flagged)
        result.metrics["anomalies_new"] = new_anomalies
        result.params["org_unit"] = claims.org_unit
        result.params["requested_by"] = actor

        _persist_run(c, run_id, result, recommendation)
        _persist_lineage(c, run_id, result)

    logger.info(
        "analytics run %s complete: %s docs, k=%s, %s anomalies (%s new)",
        run_id, result.metrics["n_docs"], result.metrics["k"],
        len(flagged), new_anomalies,
    )
    return http.ok(
        {
            "run_id": run_id,
            # "completed" is the frontend contract's union member
            # (lib/types.ts AnalyticsRunResponse) — the run is synchronous.
            "status": "completed",
            "kind": RUN_KIND,
            "metrics": result.metrics,
            "recommendation": recommendation,
            "topics": [
                {"topic_id": t["topic_id"], "label": t["label"], "top_terms": t["top_terms"]}
                for t in result.topics
            ],
        }
    )


def _fetch_docs(c):
    with c.cursor() as cur:
        cur.execute(
            "SELECT id, title, abstract, program_area, fiscal_year "
            "FROM grants_curated "
            "WHERE abstract IS NOT NULL AND length(btrim(abstract)) > 0"
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "abstract": r[2],
            "program_area": r[3],
            "fiscal_year": r[4],
        }
        for r in rows
    ]


def _fetch_amounts(c):
    # amount_usd is CLS-revoked on the base table for compass_app; the
    # grants_curated_corp view (owner-executed, still FORCE-RLS-filtered by the
    # transaction's compass.org_unit GUC) is the sanctioned read path.
    with c.cursor() as cur:
        cur.execute(
            "SELECT id, grant_no, program_area, amount_usd FROM grants_curated_corp"
        )
        rows = cur.fetchall()
    return [
        {"grant_id": r[0], "grant_no": r[1], "program_area": r[2], "amount_usd": r[3]}
        for r in rows
    ]


def _persist_anomalies(c, flagged) -> int:
    """Insert open funding anomalies, skipping grants already openly flagged."""
    if not flagged:
        return 0
    with c.cursor() as cur:
        cur.execute(
            "SELECT grant_id FROM anomalies WHERE kind = %s AND status = 'open'",
            (ANOMALY_KIND,),
        )
        already = {r[0] for r in cur.fetchall()}
        new_rows = [f for f in flagged if f["grant_id"] not in already]
        cur.executemany(
            "INSERT INTO anomalies (grant_id, kind, severity, reason, status) "
            "VALUES (%s, %s, %s, %s, 'open')",
            [(f["grant_id"], ANOMALY_KIND, f["severity"], f["reason"]) for f in new_rows],
        )
    return len(new_rows)


def _persist_run(c, run_id, result, recommendation):
    with c.cursor() as cur:
        cur.execute(
            "INSERT INTO model_runs (run_id, kind, params_jsonb, metrics_jsonb, recommendation) "
            "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s)",
            (
                run_id,
                RUN_KIND,
                json.dumps(result.params),
                json.dumps(result.metrics),
                recommendation,
            ),
        )
        cur.executemany(
            "INSERT INTO topics (run_id, topic_id, label, top_terms, trend_jsonb) "
            "VALUES (%s, %s, %s, %s, %s::jsonb)",
            [
                (run_id, t["topic_id"], t["label"], t["top_terms"], json.dumps(t["trend"]))
                for t in result.topics
            ],
        )
        cur.executemany(
            "INSERT INTO grant_topics (grant_id, run_id, topic_id, weight) "
            "VALUES (%s, %s, %s, %s)",
            [
                (d["grant_id"], run_id, d["topic_id"], d["weight"])
                for d in result.doc_topics
            ],
        )


def _persist_lineage(c, run_id, result):
    """Emit this analysis run's provenance graph (kind vocabulary per 001_schema)."""
    nodes = [
        ("tbl:grants_curated", "table", "compass.grants_curated",
         {"n_docs": result.metrics["n_docs"]}),
        ("model:topic_nmf", "model", "TF-IDF + NMF topic model (numpy)",
         {"k": result.metrics["k"],
          "reconstruction_error": result.metrics["reconstruction_error"]}),
        ("tbl:topics", "table", "compass.topics + compass.grant_topics",
         {"rows": result.metrics["grant_topic_rows"]}),
        ("tbl:anomalies", "table", "compass.anomalies",
         {"flagged": result.metrics["anomalies_flagged"]}),
        ("dash:analytics", "dashboard", "Analytics & Executive Dashboard", None),
    ]
    edges = [
        ("tbl:grants_curated", "model:topic_nmf"),
        ("model:topic_nmf", "tbl:topics"),
        ("model:topic_nmf", "tbl:anomalies"),
        ("tbl:topics", "dash:analytics"),
        ("tbl:anomalies", "dash:analytics"),
    ]
    with c.cursor() as cur:
        cur.executemany(
            "INSERT INTO lineage_nodes (run_id, node_id, kind, label, meta_jsonb) "
            "VALUES (%s, %s, %s, %s, %s::jsonb)",
            [
                (run_id, nid, kind, label, json.dumps(meta) if meta else None)
                for nid, kind, label, meta in nodes
            ],
        )
        cur.executemany(
            "INSERT INTO lineage_edges (run_id, from_node, to_node) VALUES (%s, %s, %s)",
            [(run_id, a, b) for a, b in edges],
        )


# --------------------------------------------------------------------------- #
# GET /analytics/{run_id}
# --------------------------------------------------------------------------- #
def _shape_topic(topic_id, label, top_terms, trend_jsonb, funding_usd):
    """Reshape a stored topic row to the frontend contract (lib/types.ts Topic).

    ``trend_jsonb`` is the model's rich per-FY record
    (``{"by_fy": [...], "window", "growth_pct"}``); the wire contract wants a
    flat ``[{"period", "value"}]`` series (value = dominant-grant count that
    FY). The full record travels alongside as ``trend_detail`` so nothing the
    model computed is hidden.
    """
    detail = trend_jsonb or {}
    by_fy = detail.get("by_fy") or []
    trend = [
        {"period": f"FY{e['fiscal_year']}", "value": int(e.get("grants") or 0)}
        for e in by_fy
    ]
    return {
        "topic_id": topic_id,
        "label": label,
        "top_terms": top_terms or [],
        "trend": trend,
        "trend_detail": detail,
        "grant_count": sum(p["value"] for p in trend),
        # null unless the caller's CLS entitlement lets amounts be read.
        "total_funding_usd": funding_usd,
    }


def _topic_funding(c, run_id: str):
    """Per-topic funding sums via the unmasked corp view (corporate calls only).

    Sums ``amount_usd`` over the RLS-visible grants linked to each topic in
    ``grant_topics`` (weight >= the model's link threshold). Returns
    ``{topic_id: float}``; empty dict if the view is not readable (fail closed
    to masked rather than erroring).
    """
    import psycopg2.errors

    with c.cursor() as cur:
        cur.execute("SAVEPOINT topic_funding")
    try:
        with c.cursor() as cur:
            cur.execute(
                "SELECT gt.topic_id, SUM(g.amount_usd) "
                "FROM grant_topics gt "
                "JOIN grants_curated_corp g ON g.id = gt.grant_id "
                "WHERE gt.run_id = %s GROUP BY gt.topic_id",
                (run_id,),
            )
            rows = cur.fetchall()
        with c.cursor() as cur:
            cur.execute("RELEASE SAVEPOINT topic_funding")
        return {int(r[0]): float(r[1]) for r in rows if r[1] is not None}
    except (psycopg2.errors.InsufficientPrivilege, psycopg2.errors.UndefinedTable):
        with c.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT topic_funding")
        logger.warning("grants_curated_corp unreadable; topic funding masked")
        return {}


def _get_run(run_id: str, claims):
    conn = db.get_conn()
    with db.set_org(conn, claims.org_unit) as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT run_id, kind, params_jsonb, metrics_jsonb, recommendation, created_at "
                "FROM model_runs WHERE run_id = %s",
                (run_id,),
            )
            run = cur.fetchone()
            if run is None:
                return http.not_found(f"no analytics run {run_id!r}")
            cur.execute(
                "SELECT topic_id, label, top_terms, trend_jsonb "
                "FROM topics WHERE run_id = %s ORDER BY topic_id",
                (run_id,),
            )
            topic_rows = cur.fetchall()

        # CLS: dollar sums only for the corporate persona; everyone else gets
        # total_funding_usd = null (masked), same rule as /dashboard.
        funding = _topic_funding(c, run_id) if claims.is_corporate else {}

    metrics = dict(run[3] or {})
    # Contract alias: the frontend's RecommendationPanel reads `grants_scored`.
    if "grants_scored" not in metrics and "n_docs" in metrics:
        metrics["grants_scored"] = metrics["n_docs"]

    return http.ok(
        {
            "run_id": run[0],
            "kind": run[1],
            "status": "completed",
            "params": run[2],
            "metrics": metrics,
            "recommendation": run[4],
            "created_at": run[5],
            "topics": [
                _shape_topic(t[0], t[1], t[2], t[3], funding.get(t[0]))
                for t in topic_rows
            ],
        }
    )

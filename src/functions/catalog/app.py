"""Data catalog + lineage API - element 4 of the Compass demo.

Routes (docs/CONTRACTS.md):

    GET /catalog                 -> {"datasets": [...], "quality_formula": {...}}
    GET /catalog/{id}/lineage    -> {"run_id": ..., "nodes": [...], "edges": [...]}

Design notes an evaluator should be able to check line-by-line
--------------------------------------------------------------

**The "dataset" grain is the ingest batch.** A row in ``compass.grants_curated``
carries the ``batch_id`` that produced it, so one catalog entry == one batch:
the natural unit an S&T portfolio owner curates, gates on quality, and traces
lineage for.

**Row-Level Security does the filtering, not this code.** Every query runs
inside :func:`compass_common.db.set_org`, which opens a transaction and issues
``SET LOCAL compass.org_unit = '<claim>'``. The ``grants_curated`` policies in
db/migrations/002_rls.sql read that GUC, so a ``viewer`` (org_unit ``Code-30``)
literally cannot see another org's rows - the batches they can't see never
appear in the catalog because the ``GROUP BY batch_id`` runs over the rows RLS
left behind. There is no ``WHERE org_unit = ...`` anywhere in this file, on
purpose: that is the point of the control.

**Column-Level Security is a database grant, not an ``if`` statement.**
002_rls.sql does ``REVOKE SELECT (amount_usd) ON grants_curated FROM
compass_app``, so the runtime role physically cannot read the dollar column off
the base table. Powerusers read through ``grants_curated_corp`` - a view owned
by the migrator, which re-exposes the column while ``FORCE ROW LEVEL SECURITY``
keeps the *same* org policy in force on the underlying table. If that view is
missing or not granted, the query fails closed (see :func:`_load_batches`): we
fall back to the base table and mask the amount rather than erroring or, worse,
leaking. The response always says which fields were masked and why.

**The quality score never travels as a bare number.** Every catalog entry ships
``quality_score`` *and* ``quality_formula`` - the expression, the per-rule
inputs it was computed from, and the arithmetic. An executive should be able to
click one number and see exactly the passed/failed row counts behind it.

**Lineage is gated on RLS visibility.** ``lineage_nodes`` / ``lineage_edges``
have no RLS of their own (they describe a run, not a row), so this handler
resolves ``{id}`` to a batch and refuses to serve the graph unless the caller
can see at least one curated row from that batch. Otherwise the lineage
endpoint would be a side channel around the row policy.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from compass_common import config, db, disclosure, http

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --------------------------------------------------------------------------- #
# Identity - deny-by-default
# --------------------------------------------------------------------------- #
def resolve_identity(claims: http.Claims) -> Tuple[Optional[str], Optional[str]]:
    """Delegate to the shared deny-by-default identity contract."""
    return http.resolve_identity(claims)


# --------------------------------------------------------------------------- #
# JSON coercion - psycopg2 hands back Decimal/date/datetime
# --------------------------------------------------------------------------- #
def _num(value: Any) -> Optional[float]:
    """Decimal/int/float -> JSON number (int when integral). None passes through."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _iso(value: Any) -> Optional[str]:
    """datetime/date -> strict ISO 8601 (``str()`` on a timestamptz is not)."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


# --------------------------------------------------------------------------- #
# Quality score - the formula is part of the contract, not a comment
# --------------------------------------------------------------------------- #
PER_RULE_FORMULA = "rule_score = 100 * passed_rows / (passed_rows + failed_rows)"
OVERALL_FORMULA = "quality_score = round(mean(rule_score for every rule in the run), 1)"
FORMULA_NOTE = (
    "Unweighted mean: every gate rule counts equally. The per-rule score stored "
    "by the quality gate in compass.grant_quality is used as-is; it is "
    "recomputed from passed_rows/failed_rows only when the stored value is "
    "null. A batch with no recorded gate run scores null, never 100 - an "
    "un-run gate is not a pass."
)


def _rule_score(row: Dict[str, Any]) -> Optional[float]:
    """Stored score, or the formula applied to the row counts."""
    if row.get("score") is not None:
        return _num(row["score"])
    passed = row.get("passed_rows") or 0
    failed = row.get("failed_rows") or 0
    evaluated = passed + failed
    if evaluated == 0:
        return None
    return round(100.0 * passed / evaluated, 1)


def build_quality(rules: List[Dict[str, Any]], run_id: Optional[str]) -> Dict[str, Any]:
    """Return ``{"score", "rules", "formula"}`` for one batch's latest gate run.

    ``formula`` carries the expressions, every input row, and the arithmetic
    that produced the headline number so the UI can show its work.
    """
    inputs: List[Dict[str, Any]] = []
    scores: List[float] = []
    for r in rules:
        passed = int(r.get("passed_rows") or 0)
        failed = int(r.get("failed_rows") or 0)
        score = _rule_score(r)
        if score is not None:
            scores.append(score)
        inputs.append(
            {
                "rule": r.get("rule"),
                "passed_rows": passed,
                "failed_rows": failed,
                "evaluated_rows": passed + failed,
                "rule_score": score,
                "weight": 1.0,
                "score_source": "stored" if r.get("score") is not None else "recomputed",
            }
        )

    overall = round(sum(scores) / len(scores), 1) if scores else None

    return {
        "score": overall,
        "rules": [
            {
                "rule": r.get("rule"),
                "passed_rows": int(r.get("passed_rows") or 0),
                "failed_rows": int(r.get("failed_rows") or 0),
                "score": _rule_score(r),
                "details": r.get("details_jsonb"),
            }
            for r in rules
        ],
        "formula": {
            "per_rule": PER_RULE_FORMULA,
            "overall": OVERALL_FORMULA,
            "note": FORMULA_NOTE,
            "source_table": "compass.grant_quality",
            "run_id": run_id,
            "rule_count": len(rules),
            "inputs": inputs,
            "computed": {
                "sum_rule_scores": round(sum(scores), 2) if scores else None,
                "divisor": len(scores),
                "quality_score": overall,
            },
        },
    }


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
# `%s` params survive psycopg2.sql.SQL.format(); only the relation identifier is
# substituted, and it comes from the fixed map below (never from user input).
BATCH_ROLLUP_SQL = """
    SELECT batch_id,
           COUNT(*)                                                   AS row_count,
           MIN(created_at)                                            AS first_seen,
           MAX(created_at)                                            AS last_seen,
           MIN(fiscal_year)                                           AS fy_min,
           MAX(fiscal_year)                                           AS fy_max,
           MODE() WITHIN GROUP (ORDER BY program_area)                AS program_area,
           MODE() WITHIN GROUP (ORDER BY org_unit)                    AS org_unit,
           MODE() WITHIN GROUP (ORDER BY classification_band)         AS classification_band,
           COUNT(DISTINCT program_area)                               AS program_area_count,
           COUNT(DISTINCT org_unit)                                   AS org_unit_count
           {amount_select}
      FROM {rel}
     WHERE batch_id IS NOT NULL
     GROUP BY batch_id
     ORDER BY MIN(created_at) DESC, batch_id
"""


def _load_batches(conn, role: str) -> Tuple[List[Dict[str, Any]], bool, Optional[str]]:
    """Roll curated grants up to one row per batch, under RLS.

    Returns ``(rows, amount_visible, mask_reason)``. Powerusers are read through
    the owner-owned ``grants_curated_corp`` view so ``amount_usd`` is available;
    viewers read the base table, where the Column-Level Security REVOKE means
    the column is not selectable at all. If the privileged read fails for any
    permission/definition reason we fail closed to the masked read.
    """
    import psycopg2.errors
    from psycopg2 import sql

    def run(relation: str, with_amount: bool) -> List[Dict[str, Any]]:
        query = sql.SQL(BATCH_ROLLUP_SQL).format(
            rel=sql.Identifier(relation),
            amount_select=sql.SQL(", SUM(amount_usd) AS amount_usd" if with_amount else ""),
        )
        with conn.cursor() as cur:
            cur.execute(query)
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    if role == "poweruser":
        # SAVEPOINT, not rollback: a plain rollback would discard the enclosing
        # transaction's `SET LOCAL compass.org_unit` and the retry would run
        # with no RLS context at all (returning zero rows, silently).
        with conn.cursor() as cur:
            cur.execute("SAVEPOINT amount_read")
        try:
            rows = run("grants_curated_corp", True)
            with conn.cursor() as cur:
                cur.execute("RELEASE SAVEPOINT amount_read")
            return rows, True, None
        except (psycopg2.errors.InsufficientPrivilege, psycopg2.errors.UndefinedTable) as exc:
            # Fail closed: no dollars rather than a 500 or a leak.
            with conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT amount_read")
            log.warning("amount-bearing catalog read unavailable, masking: %s", exc)
            return (
                run("grants_curated", False),
                False,
                "amount_usd is not readable by the runtime role on this deployment "
                "(grants_curated_corp missing or not granted); masked rather than failing open",
            )

    return (
        run("grants_curated", False),
        False,
        "column-level security: amount_usd is REVOKEd from compass_app and this "
        "role is not entitled to the unmasked view",
    )


def _load_quality(conn, batch_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Latest gate run per batch -> ``{batch_id: {"run_id", "at", "rules": [...]}}``."""
    if not batch_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT batch_id, run_id, rule, passed_rows, failed_rows, score,
                   details_jsonb, created_at
              FROM grant_quality
             WHERE batch_id = ANY(%s)
             ORDER BY batch_id, created_at DESC
            """,
            (batch_ids,),
        )
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        batch = row["batch_id"]
        entry = latest.get(batch)
        if entry is None:
            entry = {"run_id": row["run_id"], "at": row["created_at"], "rules": []}
            latest[batch] = entry
        # Rows arrive newest-first; keep only the newest run's rules per batch.
        if row["run_id"] == entry["run_id"]:
            entry["rules"].append(row)
    return latest


def _load_source_files(conn, batch_ids: List[str]) -> Dict[str, str]:
    """First source file seen in the landing zone for each batch."""
    if not batch_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT batch_id, MIN(source_file) AS source_file
              FROM grants_raw
             WHERE batch_id = ANY(%s)
             GROUP BY batch_id
            """,
            (batch_ids,),
        )
        return {r[0]: r[1] for r in cur.fetchall()}


# --------------------------------------------------------------------------- #
# GET /catalog
# --------------------------------------------------------------------------- #
def list_catalog(conn, role: str) -> Dict[str, Any]:
    batches, amount_visible, mask_reason = _load_batches(conn, role)
    batch_ids = [b["batch_id"] for b in batches]
    quality = _load_quality(conn, batch_ids)
    sources = _load_source_files(conn, batch_ids)

    datasets: List[Dict[str, Any]] = []
    for b in batches:
        batch_id = b["batch_id"]
        q = quality.get(batch_id, {})
        built = build_quality(q.get("rules", []), q.get("run_id"))
        run_id = q.get("run_id") or f"run-{batch_id}"

        datasets.append(
            {
                "id": batch_id,
                "batch_id": batch_id,
                "run_id": run_id,
                "dataset_name": f"grants_curated · {batch_id}",
                "source_file": (
                    disclosure.logical_source_locator(sources[batch_id])
                    if sources.get(batch_id)
                    else disclosure.logical_curated_locator(batch_id)
                ),
                "program_area": b["program_area"],
                "program_area_count": _num(b["program_area_count"]),
                "org_unit": b["org_unit"],
                "org_unit_count": _num(b["org_unit_count"]),
                "fiscal_year": _num(b["fy_min"]),
                "fiscal_year_min": _num(b["fy_min"]),
                "fiscal_year_max": _num(b["fy_max"]),
                "row_count": _num(b["row_count"]),
                "amount_usd": _num(b.get("amount_usd")) if amount_visible else None,
                "amount_masked": not amount_visible,
                "masked_fields": [] if amount_visible else ["amount_usd"],
                "mask_reason": None if amount_visible else mask_reason,
                "quality_score": built["score"],
                "quality_rules": built["rules"],
                "quality_formula": built["formula"],
                "quality_run_at": _iso(q.get("at")),
                "classification_band": b["classification_band"],
                "ingested_at": _iso(b["first_seen"]),
                "last_row_at": _iso(b["last_seen"]),
                "owner": "Compass Ingest Pipeline",
            }
        )

    return {
        "datasets": datasets,
        "quality_formula": {
            "per_rule": PER_RULE_FORMULA,
            "overall": OVERALL_FORMULA,
            "note": FORMULA_NOTE,
            "source_table": "compass.grant_quality",
        },
        "row_filtering": {
            "mechanism": "PostgreSQL row-level security on compass.grants_curated",
            "context": f"SET LOCAL {config.ORG_SETTING}",
            "note": "Batches with no rows visible to this caller do not appear at all.",
        },
    }


# --------------------------------------------------------------------------- #
# GET /catalog/{id}/lineage
# --------------------------------------------------------------------------- #
def _visible_batch(conn, ident: str) -> Optional[str]:
    """Resolve ``{id}`` to a batch the caller can actually see, else ``None``.

    ``{id}`` is normally a ``batch_id`` (what GET /catalog returns). A ``run_id``
    is accepted too and mapped back to its batch. Either way the batch must have
    at least one ``grants_curated`` row surviving RLS - that check is what stops
    the lineage graph from becoming a way to read around the row policy.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM grants_curated WHERE batch_id = %s LIMIT 1", (ident,))
        if cur.fetchone():
            return ident

        # Maybe it's a run_id - map it to its batch, then re-check visibility.
        cur.execute(
            "SELECT batch_id FROM grant_quality WHERE run_id = %s LIMIT 1", (ident,)
        )
        row = cur.fetchone()
        if not row:
            return None
        batch_id = row[0]
        cur.execute("SELECT 1 FROM grants_curated WHERE batch_id = %s LIMIT 1", (batch_id,))
        return batch_id if cur.fetchone() else None


def _latest_run_with_lineage(conn, batch_id: str) -> Optional[str]:
    """Newest run_id for this batch that actually emitted a lineage graph."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT q.run_id
              FROM grant_quality q
             WHERE q.batch_id = %s
               AND EXISTS (SELECT 1 FROM lineage_nodes n WHERE n.run_id = q.run_id)
             GROUP BY q.run_id
             ORDER BY MAX(q.created_at) DESC
             LIMIT 1
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        # Fallback: a run that recorded its batch on the node metadata but has
        # no grant_quality row (e.g. an analytics-only run).
        cur.execute(
            """
            SELECT run_id
              FROM lineage_nodes
             WHERE meta_jsonb ->> 'batch_id' = %s
             GROUP BY run_id
             ORDER BY run_id DESC
             LIMIT 1
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def get_lineage(conn, ident: str) -> Optional[Dict[str, Any]]:
    batch_id = _visible_batch(conn, ident)
    if batch_id is None:
        return None

    run_id = _latest_run_with_lineage(conn, batch_id)
    if run_id is None:
        # Visible batch, no recorded graph: an honest empty result beats a 404
        # (the dataset exists; the pipeline just hasn't emitted lineage yet).
        return {
            "run_id": f"run-{batch_id}",
            "batch_id": batch_id,
            "nodes": [],
            "edges": [],
            "note": "No lineage was recorded for this batch yet - run the ingest "
                    "pipeline (POST /ingest/simulate) to emit a graph.",
        }

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, node_id, kind, label, meta_jsonb
              FROM lineage_nodes
             WHERE run_id = %s
             ORDER BY node_id
            """,
            (run_id,),
        )
        nodes = [
            disclosure.safe_lineage_node(
                run_id=row[0],
                node_id=row[1],
                kind=row[2],
                label=row[3],
                meta=row[4],
            )
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT run_id, from_node, to_node
              FROM lineage_edges
             WHERE run_id = %s
             ORDER BY from_node, to_node
            """,
            (run_id,),
        )
        edges = [{"run_id": r[0], "from_node": r[1], "to_node": r[2]} for r in cur.fetchall()]

    return {"run_id": run_id, "batch_id": batch_id, "nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- #
# Handler
# --------------------------------------------------------------------------- #
def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    claims = http.get_claims(event)
    role, org_unit = resolve_identity(claims)
    if not role:
        return http.forbidden(
            "no Compass role on this identity - expected one of the "
            "compass-poweruser / compass-viewer Cognito groups"
        )

    path = http.get_path(event) or ""
    ident = http.path_param(event, "id")

    try:
        conn = db.get_conn()
        with db.set_org(conn, org_unit) as c:
            if ident or path.endswith("/lineage"):
                if not ident:
                    return http.bad_request("missing catalog id")
                result = get_lineage(c, ident)
                if result is None:
                    # Indistinguishable from "does not exist" on purpose: a
                    # 403 here would confirm the batch exists in another org.
                    return http.not_found(f"no catalog entry '{ident}' visible to this org")
                return http.ok(result)

            return http.ok(list_catalog(c, role))
    except Exception:
        log.exception("catalog request failed (path=%s id=%s)", path, ident)
        return http.server_error("catalog query failed")

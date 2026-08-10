"""Compass quality gate — the Validate and Quarantine states of the intake pipeline.

Invoked only by ``statemachines/intake.asl.yaml`` (no API route). Two actions:

``{"action":"validate", "batch_id": ..., "run_id": ...}``
    Read the batch out of ``grants_raw``, run every rule in ``rules.py``, write
    one ``grant_quality`` row per rule, stamp each raw row with its verdict,
    raise an ``anomalies`` row for each quarantined record, emit the
    ``quality-gate`` lineage node, and return the gate decision the state
    machine's Choice routes on.

``{"action":"quarantine", "batch_id": ..., "run_id": ...}``
    The fail branch. Holds the whole batch: marks its raw rows, records a
    batch-level anomaly with the score and the threshold that rejected it, and
    emits the ``quarantine`` lineage node. Nothing is curated.

Two levels of quarantine, on purpose
------------------------------------
*Row level*: a record that fails any rule is marked ``quarantined`` in
``grants_raw`` and is never eligible for ``grants_curated`` — this happens on
every run, pass or fail. *Batch level*: if the batch's row pass-rate falls below
``QUALITY_PASS_THRESHOLD`` the gate rejects the batch as a whole and no rows are
curated at all, even the clean ones. The demo fixtures exercise both:
``drop_good`` and ``drop_compatible_variant`` score 100 and flow through;
``drop_incompatible_bad`` scores 75.0 (45 of 60 rows clean) and is held.

Nothing is deleted, ever. ``compass_app`` has no DELETE grant, and quarantined
data stays in the landing zone with its verdict attached, which is what makes
the "why was this row rejected?" question answerable months later.

Environment
-----------
QUALITY_PASS_THRESHOLD  Batch row pass-rate needed to curate.   default 90
QUALITY_FY_MIN / _MAX   Accepted fiscal-year window.            default 2015 / 2035
QUALITY_AMOUNT_MAX      Upper sanity bound on one award.        default 100000000
KNOWN_ORG_UNITS         Comma-separated recognized RLS keys.    default: the six ONR units
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from compass_common import audit, config, db

import rules

PIPELINE_ORG_UNIT = config.CORPORATE_ORG_UNIT
PIPELINE_ACTOR = "compass-quality-gate"


def run_id_for(batch_id: str) -> str:
    return f"run-{batch_id}"


def _settings() -> Dict[str, Any]:
    units = os.environ.get("KNOWN_ORG_UNITS")
    return {
        "threshold": float(os.environ.get("QUALITY_PASS_THRESHOLD", rules.DEFAULT_PASS_THRESHOLD)),
        "fy_min": int(os.environ.get("QUALITY_FY_MIN", rules.DEFAULT_FY_MIN)),
        "fy_max": int(os.environ.get("QUALITY_FY_MAX", rules.DEFAULT_FY_MAX)),
        "amount_max": float(os.environ.get("QUALITY_AMOUNT_MAX", rules.DEFAULT_AMOUNT_MAX)),
        "known_org_units": (
            {u.strip() for u in units.split(",") if u.strip()} if units else rules.KNOWN_ORG_UNITS
        ),
    }


# --------------------------------------------------------------------------- #
# Lineage helpers — same two upserts as intake/pipeline.py. Lambda packages are
# independent deployment units, so the small duplication is deliberate; the
# alternative is a shared-layer dependency for twenty lines of SQL.
# --------------------------------------------------------------------------- #
def upsert_lineage_nodes(cur, run_id: str, nodes: Sequence[Dict[str, Any]]) -> None:
    for node in nodes:
        cur.execute(
            "INSERT INTO lineage_nodes (run_id, node_id, kind, label, meta_jsonb) "
            "VALUES (%s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (run_id, node_id) DO UPDATE "
            "SET kind = EXCLUDED.kind, label = EXCLUDED.label, "
            "    meta_jsonb = EXCLUDED.meta_jsonb",
            (run_id, node["node_id"], node["kind"], node["label"],
             json.dumps(node.get("meta") or {}, default=str)),
        )


def upsert_lineage_edges(cur, run_id: str, edges: Sequence[Tuple[str, str]]) -> None:
    for from_node, to_node in edges:
        cur.execute(
            "INSERT INTO lineage_edges (run_id, from_node, to_node) VALUES (%s, %s, %s) "
            "ON CONFLICT (run_id, from_node, to_node) DO NOTHING",
            (run_id, from_node, to_node),
        )


def _raise_anomaly(cur, kind: str, severity: str, reason: str, grant_id: Optional[int] = None) -> None:
    """Append an anomaly unless an identical one is already open.

    ``compass_app`` holds no DELETE grant, so re-running a batch must not stack
    duplicates; the guard is a NOT EXISTS on (kind, reason), and the reason
    always carries the batch id to keep it distinguishing.
    """
    cur.execute(
        "INSERT INTO anomalies (grant_id, kind, severity, reason, status) "
        "SELECT %s, %s, %s, %s, 'open' "
        "WHERE NOT EXISTS (SELECT 1 FROM anomalies WHERE kind = %s AND reason = %s)",
        (grant_id, kind, severity, reason, kind, reason),
    )


# --------------------------------------------------------------------------- #
# Validate
# --------------------------------------------------------------------------- #
def _load_batch(cur, batch_id: str) -> List[Dict[str, Any]]:
    cur.execute(
        "SELECT id, raw_jsonb FROM grants_raw WHERE batch_id = %s ORDER BY id",
        (batch_id,),
    )
    rows = []
    for raw_id, envelope in cur.fetchall():
        if isinstance(envelope, str):
            envelope = json.loads(envelope)
        envelope = envelope or {}
        rows.append(
            {
                "raw_id": raw_id,
                "record": envelope.get("record") or {},
                "normalized": envelope.get("normalized") or {},
                "meta": envelope.get("meta") or {},
            }
        )
    return rows


def _existing_grant_nos(cur, batch_id: str) -> set:
    """Curated grant numbers from *other* batches.

    Excluding this batch's own rows is what makes a re-run idempotent: without
    it, a batch that curated successfully would fail its own uniqueness rule the
    second time it ran.
    """
    cur.execute(
        "SELECT grant_no FROM grants_curated WHERE batch_id IS DISTINCT FROM %s",
        (batch_id,),
    )
    return {row[0] for row in cur.fetchall()}


def validate_stage(payload: Dict[str, Any]) -> Dict[str, Any]:
    batch_id = payload.get("batch_id")
    if not batch_id:
        raise ValueError("validate requires a batch_id")
    run_id = payload.get("run_id") or run_id_for(batch_id)
    settings = _settings()

    conn = db.get_conn()
    with db.set_org(conn, PIPELINE_ORG_UNIT) as c, c.cursor() as cur:
        rows = _load_batch(cur, batch_id)
        if not rows:
            raise ValueError(f"no grants_raw rows for batch {batch_id!r} — did Fetch run?")
        existing = _existing_grant_nos(cur, batch_id)

        result = rules.evaluate_batch(
            rows,
            existing_grant_nos=existing,
            fy_min=settings["fy_min"],
            fy_max=settings["fy_max"],
            amount_max=settings["amount_max"],
            known_org_units=settings["known_org_units"],
            threshold=settings["threshold"],
        )

        # 1) stamp every raw row with its verdict
        checked_at = payload.get("checked_at")
        for row_result in result.rows:
            verdict = {
                "quality": {
                    "status": "passed" if row_result.passed else "quarantined",
                    "run_id": run_id,
                    "violations": row_result.violations,
                    "checked_at": checked_at,
                }
            }
            cur.execute(
                "UPDATE grants_raw SET raw_jsonb = raw_jsonb || %s::jsonb WHERE id = %s",
                (json.dumps(verdict, default=str), row_result.raw_id),
            )

        # 2) one grant_quality row per rule, each carrying its own score formula
        for rule in result.rules:
            cur.execute(
                "INSERT INTO grant_quality "
                "(batch_id, run_id, rule, passed_rows, failed_rows, score, details_jsonb) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb) "
                "ON CONFLICT (run_id, rule) DO UPDATE SET "
                "  batch_id = EXCLUDED.batch_id, passed_rows = EXCLUDED.passed_rows, "
                "  failed_rows = EXCLUDED.failed_rows, score = EXCLUDED.score, "
                "  details_jsonb = EXCLUDED.details_jsonb, created_at = now()",
                (
                    batch_id,
                    run_id,
                    rule.rule,
                    rule.passed_rows,
                    rule.failed_rows,
                    rule.score,
                    json.dumps(rule.details(), default=str),
                ),
            )

        # 3) an open anomaly per quarantined row
        for row_result in result.rows:
            if row_result.passed:
                continue
            label = row_result.grant_no or f"row {row_result.row_index}"
            _raise_anomaly(
                cur,
                kind="quality_violation",
                severity=row_result.severity,
                reason=f"[{batch_id}] {label}: {row_result.reason}",
            )

        # 4) lineage: the gate node carries the verdict the Choice state uses
        upsert_lineage_nodes(
            cur,
            run_id,
            [
                {
                    "node_id": "quality-gate",
                    "kind": "stage",
                    "label": "Quality gate",
                    "meta": {
                        "batch_id": batch_id,
                        "rules": [r.rule for r in result.rules],
                        "rows_checked": result.rows_checked,
                        "rows_passed": result.rows_passed,
                        "rows_failed": result.rows_failed,
                        "overall_score": result.overall_score,
                        "rule_evaluation_score": result.rule_evaluation_score,
                        "score_formula": rules.SCORE_FORMULA,
                        "threshold": result.threshold,
                        "decision": result.gate,
                    },
                }
            ],
        )
        upsert_lineage_edges(cur, run_id, [("raw", "quality-gate")])

        audit.write_audit(
            c,
            actor=PIPELINE_ACTOR,
            action="quality_gate",
            resource=f"grants_raw:{batch_id}",
            detail={
                "run_id": run_id,
                "rows_checked": result.rows_checked,
                "rows_passed": result.rows_passed,
                "overall_score": result.overall_score,
                "threshold": result.threshold,
                "decision": result.gate,
            },
        )

    out = {
        "status": "ok",
        "action": "validate",
        "batch_id": batch_id,
        "run_id": run_id,
        "source_file": payload.get("source_file"),
        "bucket": payload.get("bucket"),
        "key": payload.get("key"),
        "gate": result.gate,
        **result.summary(),
    }
    print(json.dumps({"event_type": "quality_gate_complete", **out}, default=str))
    return out


# --------------------------------------------------------------------------- #
# Quarantine
# --------------------------------------------------------------------------- #
def quarantine_stage(payload: Dict[str, Any]) -> Dict[str, Any]:
    batch_id = payload.get("batch_id")
    if not batch_id:
        raise ValueError("quarantine requires a batch_id")
    run_id = payload.get("run_id") or run_id_for(batch_id)
    score = payload.get("overall_score")
    threshold = payload.get("threshold", _settings()["threshold"])
    rows_failed = payload.get("rows_failed")
    rows_checked = payload.get("rows_checked")

    reason = (
        f"[{batch_id}] batch quarantined: row pass-rate {score} is below the "
        f"{threshold} threshold ({rows_failed} of {rows_checked} rows failed at "
        "least one quality rule); no rows were curated"
    )

    conn = db.get_conn()
    with db.set_org(conn, PIPELINE_ORG_UNIT) as c, c.cursor() as cur:
        cur.execute(
            "UPDATE grants_raw SET raw_jsonb = raw_jsonb || %s::jsonb WHERE batch_id = %s",
            (json.dumps({"batch_status": "quarantined"}), batch_id),
        )
        held = cur.rowcount
        _raise_anomaly(cur, kind="batch_quarantined", severity="high", reason=reason)
        upsert_lineage_nodes(
            cur,
            run_id,
            [
                {
                    "node_id": "quarantine",
                    "kind": "stage",
                    "label": "Quarantine (batch held)",
                    "meta": {
                        "batch_id": batch_id,
                        "rows_held": held,
                        "rows_failed": rows_failed,
                        "rows_checked": rows_checked,
                        "overall_score": score,
                        "threshold": threshold,
                        "retention": "rows remain in grants_raw with their verdicts",
                    },
                }
            ],
        )
        upsert_lineage_edges(cur, run_id, [("quality-gate", "quarantine")])
        audit.write_audit(
            c,
            actor=PIPELINE_ACTOR,
            action="quarantine_batch",
            resource=f"grants_raw:{batch_id}",
            detail={"run_id": run_id, "rows_held": held, "overall_score": score,
                    "threshold": threshold},
        )

    out = {
        "status": "ok",
        "action": "quarantine",
        "batch_id": batch_id,
        "run_id": run_id,
        "rows_held": held,
        "rows_curated": 0,
        "overall_score": score,
        "threshold": threshold,
        "reason": reason,
    }
    print(json.dumps({"event_type": "quarantine_complete", **out}, default=str))
    return out


def handler(event, context=None):
    event = event or {}
    action = event.get("action")
    if action == "validate":
        return validate_stage(event)
    if action == "quarantine":
        return quarantine_stage(event)
    raise ValueError(
        f"unrecognized quality_gate action {action!r}; expected 'validate' or 'quarantine'"
    )

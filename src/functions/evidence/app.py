"""Protected, sanitized backend evidence for the Compass System Inspector.

GET /system/evidence is intentionally read-only and poweruser-only. It exposes
application-owned projections that help a presenter prove the working system
without exposing infrastructure identifiers, secrets, raw claims, SQL, source
records, prompts, or exception details.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from compass_common import db, disclosure, http


SERVICE_EVIDENCE = (
    {
        "id": "identity",
        "label": "Identity boundary",
        "purpose": "JWT validation and group-to-role resolution",
        "status": "operational",
    },
    {
        "id": "api",
        "label": "API boundary",
        "purpose": "Deny-by-default, versioned application routes",
        "status": "operational",
    },
    {
        "id": "data",
        "label": "Data boundary",
        "purpose": "Private PostgreSQL with transaction-scoped row policy",
        "status": "operational",
    },
    {
        "id": "workflow",
        "label": "Workflow boundary",
        "purpose": "Event-driven intake, quality gate, and quarantine",
        "status": "operational",
    },
    {
        "id": "evidence",
        "label": "Evidence boundary",
        "purpose": "Append-only audit and lineage projections",
        "status": "operational",
    },
)

def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _number(value: Any) -> Any:
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _safe_detail(value: Any) -> Dict[str, Any]:
    """Return a tiny allowlisted subset of an audit detail document."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return disclosure.safe_audit_detail(value)


def _resource_category(action: str) -> str:
    lowered = action.lower()
    if "export" in lowered:
        return "controlled export"
    if "approval" in lowered:
        return "approval decision"
    if "ingest" in lowered or "quality" in lowered:
        return "intake workflow"
    if "model" in lowered or "analytics" in lowered:
        return "analytics run"
    return "application record"


def _recent_runs(cur, limit: int = 8) -> List[Dict[str, Any]]:
    cur.execute(
        """
        WITH quality AS (
          SELECT run_id,
                 MIN(batch_id) AS batch_id,
                 MIN(created_at) AS started_at,
                 MAX(created_at) AS completed_at,
                 AVG(score) AS quality_score
          FROM grant_quality
          GROUP BY run_id
        ), curated AS (
          SELECT batch_id, COUNT(*) AS curated_rows
          FROM grants_curated
          WHERE batch_id IS NOT NULL
          GROUP BY batch_id
        )
        SELECT q.run_id, q.batch_id, q.started_at, q.completed_at,
               q.quality_score, COALESCE(c.curated_rows, 0),
               COALESCE(
                 jsonb_object_agg(n.node_id, n.meta_jsonb)
                   FILTER (WHERE n.node_id IS NOT NULL),
                 '{}'::jsonb
               ) AS lineage_receipts
        FROM quality q
        LEFT JOIN curated c ON c.batch_id = q.batch_id
        LEFT JOIN lineage_nodes n ON n.run_id = q.run_id
        GROUP BY q.run_id, q.batch_id, q.started_at, q.completed_at,
                 q.quality_score, c.curated_rows
        ORDER BY q.completed_at DESC
        LIMIT %s
        """,
        (limit * 3,),
    )
    rows: List[Dict[str, Any]] = []
    for (
        run_id,
        batch_id,
        started_at,
        completed_at,
        score,
        curated_rows,
        lineage_receipts,
    ) in cur.fetchall():
        score_value = round(float(score or 0), 1)
        curated = int(curated_rows or 0)
        receipts = lineage_receipts if isinstance(lineage_receipts, dict) else {}
        gate_meta = receipts.get("quality-gate")
        gate_decision = (
            str(gate_meta.get("decision") or "").lower()
            if isinstance(gate_meta, dict)
            else ""
        )
        quarantined = "quarantine" in receipts or gate_decision in {"fail", "quarantine"}
        if curated > 0:
            outcome = "curated"
        elif quarantined or score_value < 90:
            outcome = "quarantined"
        else:
            # A passing gate may be visible before the persist state commits.
            # Do not present that transient projection as a completed run.
            continue
        rows.append(
            {
                "run_id": str(run_id),
                "batch_id": str(batch_id),
                "started_at": _iso(started_at),
                "completed_at": _iso(completed_at),
                "status": "completed",
                "outcome": outcome,
                "quality_score": score_value,
                "curated_rows": curated,
                "stages": _stages_for(
                    outcome,
                    curated_rows=curated,
                    lineage_receipts=receipts,
                ),
                "source": "database_projection",
            }
        )
    return rows[:limit]


def _stages_for(
    outcome: str,
    *,
    curated_rows: int,
    lineage_receipts: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build a trace only from persisted quality, lineage, and row receipts."""
    has_raw = "raw" in lineage_receipts
    has_source = "src-file" in lineage_receipts
    has_gate = "quality-gate" in lineage_receipts
    has_terminal_node = "curated" in lineage_receipts or "quarantine" in lineage_receipts
    gate_meta = lineage_receipts.get("quality-gate")
    gate_decision = (
        str(gate_meta.get("decision") or "recorded")
        if isinstance(gate_meta, dict)
        else "recorded"
    )
    return [
        {
            "id": "receive",
            "label": "Receive",
            "status": "completed" if has_source or has_raw else "skipped",
            "receipt": (
                "Landing receipt recorded"
                if has_source or has_raw
                else "No landing receipt is available for this seeded batch"
            ),
        },
        {
            "id": "normalize",
            "label": "Normalize",
            "status": "completed" if has_raw else "skipped",
            "receipt": (
                "Canonical grants_raw node recorded"
                if has_raw
                else "Normalization receipt is not available for this seeded batch"
            ),
        },
        {
            "id": "validate",
            "label": "Validate",
            "status": "completed",
            "receipt": "Deterministic grant_quality rows recorded",
        },
        {
            "id": "gate",
            "label": "Quality gate",
            "status": "completed",
            "receipt": (
                f"Quality-gate lineage decision recorded: {gate_decision}"
                if has_gate
                else "Quality score receipt recorded"
            ),
        },
        {
            "id": "persist",
            "label": "Curate",
            "status": "completed" if outcome == "curated" else "skipped",
            "receipt": (
                f"{curated_rows} curated rows persisted under row security"
                if outcome == "curated"
                else "Quarantine receipt recorded; no curated rows written"
            ),
        },
        {
            "id": "evidence",
            "label": "Evidence",
            "status": "completed" if has_terminal_node or has_gate else "skipped",
            "receipt": (
                f"{len(lineage_receipts)} lineage receipts plus quality evidence recorded"
                if lineage_receipts
                else "Quality evidence recorded; lineage receipt is unavailable"
            ),
        },
    ]


def _service_evidence(
    runs: List[Dict[str, Any]],
    audit_events: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Attach posture only when the current request produced supporting proof."""
    services = [dict(item) for item in SERVICE_EVIDENCE]
    for service in services:
        if service["id"] == "workflow" and not runs:
            service["status"] = "degraded"
            service["purpose"] = "No terminal workflow receipt is currently projected"
        if service["id"] == "evidence" and not audit_events:
            service["status"] = "degraded"
            service["purpose"] = "No append-only audit receipt is currently projected"
    return services


def _recent_audit(cur, limit: int = 10) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT id, action, detail_jsonb, at
        FROM audit_log
        ORDER BY at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    )
    return [
        {
            "event_id": f"audit-{int(event_id)}",
            "action": str(action),
            "category": _resource_category(str(action)),
            "detail": _safe_detail(detail),
            "at": _iso(at),
            "source": "append_only_audit",
        }
        for event_id, action, detail, at in cur.fetchall()
    ]


def _latest_model(cur) -> Optional[Dict[str, Any]]:
    cur.execute(
        """
        SELECT run_id, kind, metrics_jsonb, created_at
        FROM model_runs
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return None
    run_id, kind, metrics, created_at = row
    safe_metrics: Dict[str, Any] = {}
    if isinstance(metrics, dict):
        for key in (
            "n_docs",
            "vocab_size",
            "k",
            "iterations_run",
            "reconstruction_error",
            "grant_topic_rows",
            "anomalies_flagged",
            "anomalies_new",
        ):
            value = metrics.get(key)
            if isinstance(value, (bool, int, float, Decimal)):
                safe_metrics[key] = _number(value)
    return {
        "run_id": str(run_id),
        "kind": str(kind),
        "status": "completed",
        "created_at": _iso(created_at),
        "metrics": safe_metrics,
        "source": "model_run_projection",
    }


def _portfolio_metrics(cur) -> Dict[str, int]:
    cur.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM grants_curated),
          (SELECT COUNT(DISTINCT batch_id) FROM grants_curated WHERE batch_id IS NOT NULL),
          (SELECT COUNT(*) FROM anomalies WHERE status = 'open'),
          (SELECT COUNT(*) FROM approvals WHERE state = 'pending'),
          (SELECT COUNT(*) FROM audit_log)
        """
    )
    row = cur.fetchone() or (0, 0, 0, 0, 0)
    return {
        "curated_records": int(row[0] or 0),
        "curated_batches": int(row[1] or 0),
        "open_anomalies": int(row[2] or 0),
        "pending_approvals": int(row[3] or 0),
        "audit_receipts": int(row[4] or 0),
    }


def _request_id(context: Any) -> str:
    value = getattr(context, "aws_request_id", None)
    return str(value or "local-evidence-request")


def _log(fields: Dict[str, Any]) -> None:
    print(json.dumps(fields, default=str, sort_keys=True))


def handler(event, context):
    started = time.perf_counter()
    method = http.get_method(event) or "GET"
    if method == "OPTIONS":
        return http.json_response(200, {})
    if method != "GET":
        return http.not_found("no evidence route for this request")

    claims = http.get_claims(event)
    if not claims.is_authenticated:
        return http.unauthorized()
    if claims.role != "poweruser" or not claims.is_corporate:
        return http.forbidden("System Inspector requires the poweruser role")

    correlation_id = _request_id(context)
    try:
        conn = db.get_conn()
        with db.set_org(conn, claims.org_unit) as scoped:
            with scoped.cursor() as cur:
                runs = _recent_runs(cur)
                audit_events = _recent_audit(cur)
                latest_model = _latest_model(cur)
                metrics = _portfolio_metrics(cur)
    except Exception as exc:  # noqa: BLE001
        _log(
            {
                "event_type": "system_evidence_failed",
                "correlation_id": correlation_id,
                "error_type": type(exc).__name__,
            }
        )
        return http.server_error("system evidence is temporarily unavailable")

    latency_ms = max(1, round((time.perf_counter() - started) * 1000))
    generated_at = datetime.now(timezone.utc).isoformat()
    body = {
        "mode": "live",
        "evidence_class": "sanitized_application_projection",
        "generated_at": generated_at,
        "deploy_revision": os.environ.get("DEPLOY_REV", "local"),
        "correlation_id": correlation_id,
        "request": {
            "method": "GET",
            "route": "/system/evidence",
            "status": 200,
            "latency_ms": latency_ms,
        },
        "identity_decision": {
            "authenticated": True,
            "role": "poweruser",
            "scope": "corporate portfolio",
            "row_policy": "transaction scoped",
            "column_policy": "role gated",
        },
        "health": {
            "status": "operational",
            "database": "reachable",
            "projection_freshness": "current request",
        },
        "metrics": metrics,
        "services": _service_evidence(runs, audit_events),
        "recent_runs": runs,
        "recent_audit": audit_events,
        "latest_model_run": latest_model,
        "controls": [
            {
                "id": "authz",
                "label": "Deny-by-default authorization",
                "status": "enforced",
                "evidence": "Poweruser and corporate scope resolved before data access",
            },
            {
                "id": "rls",
                "label": "Row policy context",
                "status": "enforced",
                "evidence": "Organization scope bound to this database transaction",
            },
            {
                "id": "cls",
                "label": "Funding column policy",
                "status": "enforced",
                "evidence": "Unmasked values require the corporate policy path",
            },
            {
                "id": "audit",
                "label": "Audit integrity",
                "status": "configured",
                "evidence": "System view reads a sanitized append-only projection",
            },
            {
                "id": "boundary",
                "label": "Demonstration data boundary",
                "status": "enforced",
                "evidence": "Synthetic portfolio data only",
            },
        ],
        "disclosure": (
            "This view exposes sanitized application evidence only. Infrastructure identifiers, "
            "credentials, tokens, personal data, raw records, SQL, prompts, and exceptions are excluded."
        ),
    }
    _log(
        {
            "event_type": "system_evidence_served",
            "correlation_id": correlation_id,
            "latency_ms": latency_ms,
            "run_count": len(runs),
            "audit_count": len(audit_events),
        }
    )
    return http.ok(body)

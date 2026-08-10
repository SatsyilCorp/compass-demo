"""Approval workflow + anomaly queue — element 6 of the Compass demo.

Routes (docs/CONTRACTS.md):

    POST /approvals   -> create or advance an approval  {"approval": {...}, ...}
    GET  /anomalies   -> the open anomaly queue         {"anomalies": [...], ...}

Why these two live together
---------------------------
They are the two halves of "a human is in the loop": an anomaly is the system
asking for attention, an approval is a named person answering for a decision.
Both are read/written through the same RLS transaction, so what a caller can
act on is exactly what they can see.

The approval state machine
--------------------------
``request`` -> ``pending`` -> ``approve`` | ``reject``. Nothing can be decided
that was not first requested: ``POST {"action":"approve"}`` against a subject
with no pending request is a 404, not an implicit create. That is deliberate —
an approval record whose "request" step never happened is not evidence of
anything.

An **approved** decision returns an ``approval_token`` (``apr-<id>``). That is
the token ``POST /export`` accepts to clear its aggregation guard, which is how
the 428 in element 7 turns into a completed export without anyone editing a
config value.

**Separation of duties.** Only ``poweruser`` may approve or reject; a
``viewer`` may request. Whether the *same* person may approve their own request
is a policy switch (``APPROVAL_REQUIRE_FOUR_EYES``, default off so a one-person
demo can walk the whole flow), but self-approval is *always* recorded — on the
response as ``four_eyes.self_approved`` and in ``audit_log.detail_jsonb``. The
control is never silently absent from the record.

Every action writes ``compass.audit_log`` inside the same transaction as the
state change, so an approval and its audit row commit or fail together.

Route note: ``template.yaml`` currently attaches ``GET /anomalies`` to the
summarize function's HttpApi event, and this handler also implements it. Both
implementations are real; only one route can be wired to the HTTP API, so the
stack's ``Events`` block is the tie-breaker.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from compass_common import audit, config, db, http

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

GROUP_TO_ROLE = {"compass-poweruser": "poweruser", "compass-viewer": "viewer"}
ROLE_TO_ORG = {"poweruser": config.CORPORATE_ORG_UNIT, "viewer": "Code-30"}

# Roles allowed to decide (not merely request) an approval.
DECIDER_ROLES = {"poweruser"}
REQUIRE_FOUR_EYES = os.environ.get("APPROVAL_REQUIRE_FOUR_EYES", "false").lower() == "true"

VALID_ACTIONS = ("request", "approve", "reject")
ACTION_TO_STATE = {"approve": "approved", "reject": "rejected"}

ANOMALY_STATUSES = ("open", "acknowledged", "resolved")
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEFAULT_ANOMALY_LIMIT = 100
MAX_ANOMALY_LIMIT = 500


# --------------------------------------------------------------------------- #
# Identity / coercion
# --------------------------------------------------------------------------- #
def resolve_identity(claims: http.Claims) -> Tuple[Optional[str], Optional[str]]:
    """``(role, org_unit)``, or ``(None, None)`` to deny. See catalog/app.py."""
    role = (claims.role or "").strip().lower() or None
    org = (claims.org_unit or "").strip() or None
    if role is None:
        for g in claims.groups:
            mapped = GROUP_TO_ROLE.get(str(g).strip().lower())
            if mapped:
                role = mapped
                break
    if role and org is None:
        org = ROLE_TO_ORG.get(role)
    if role not in ROLE_TO_ORG or not org:
        return None, None
    return role, org


def actor_of(claims: http.Claims) -> str:
    """Stable, human-readable identity for the audit trail."""
    return claims.username or claims.email or claims.sub or "unknown"


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


APPROVAL_COLUMNS = (
    "id, subject_type, subject_id, state, requested_by, decided_by, "
    "decided_at, note, created_at"
)


def _approval_row(row: Optional[tuple]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {
        "id": _int(row[0]),
        "subject_type": row[1],
        "subject_id": row[2],
        "state": row[3],
        "requested_by": row[4],
        "decided_by": row[5],
        "decided_at": _iso(row[6]),
        "note": row[7],
        "created_at": _iso(row[8]),
    }


def approval_token(approval: Dict[str, Any]) -> Optional[str]:
    """The token POST /export accepts — issued only for an approved decision."""
    if approval.get("state") == "approved":
        return f"apr-{approval['id']}"
    return None


# --------------------------------------------------------------------------- #
# POST /approvals
# --------------------------------------------------------------------------- #
def create_or_advance(
    conn, body: Dict[str, Any], actor: str, role: str
) -> Dict[str, Any]:
    """Run one step of the approval state machine.

    Returns ``{"status": <http status>, "body": <response body>}`` so the
    handler stays a thin transport wrapper.
    """
    subject_type = (body.get("subject_type") or "").strip()
    subject_id = str(body.get("subject_id") or "").strip()
    action = (body.get("action") or "").strip().lower()
    note = body.get("note")

    if not subject_type or not subject_id:
        return {"status": 400, "body": {"error": "subject_type and subject_id are required"}}
    if action not in VALID_ACTIONS:
        return {
            "status": 400,
            "body": {"error": f"action must be one of {list(VALID_ACTIONS)}", "action": action},
        }
    if note is not None and not isinstance(note, str):
        return {"status": 400, "body": {"error": "note must be a string"}}

    with conn.cursor() as cur:
        if action == "request":
            # Idempotent: an identical outstanding request is returned, not
            # duplicated, so a double-click cannot fan out the queue.
            cur.execute(
                f"""
                SELECT {APPROVAL_COLUMNS}
                  FROM approvals
                 WHERE subject_type = %s AND subject_id = %s
                   AND state = 'pending' AND requested_by = %s
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                (subject_type, subject_id, actor),
            )
            existing = _approval_row(cur.fetchone())
            if existing:
                audit.write_audit(
                    conn,
                    actor=actor,
                    action="approval_request_deduplicated",
                    resource=f"approvals/{existing['id']}",
                    detail={"subject_type": subject_type, "subject_id": subject_id},
                )
                return {
                    "status": 200,
                    "body": {
                        "approval": existing,
                        "approval_token": approval_token(existing),
                        "deduplicated": True,
                    },
                }

            cur.execute(
                f"""
                INSERT INTO approvals (subject_type, subject_id, state, requested_by, note)
                VALUES (%s, %s, 'pending', %s, %s)
                RETURNING {APPROVAL_COLUMNS}
                """,
                (subject_type, subject_id, actor, note),
            )
            approval = _approval_row(cur.fetchone())
            audit.write_audit(
                conn,
                actor=actor,
                action="approval_requested",
                resource=f"approvals/{approval['id']}",
                detail={
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                    "note": note,
                    "requester_role": role,
                },
            )
            return {"status": 201, "body": {"approval": approval, "approval_token": None}}

        # --- decide (approve | reject) -------------------------------------- #
        if role not in DECIDER_ROLES:
            audit.write_audit(
                conn,
                actor=actor,
                action="approval_decision_denied",
                resource=f"{subject_type}/{subject_id}",
                detail={"action": action, "role": role, "reason": "role may not decide approvals"},
            )
            return {
                "status": 403,
                "body": {
                    "error": "separation of duties: this role may request an approval "
                             "but not decide one",
                    "role": role,
                    "decider_roles": sorted(DECIDER_ROLES),
                },
            }

        # FOR UPDATE: two reviewers clicking at once must not both decide.
        cur.execute(
            f"""
            SELECT {APPROVAL_COLUMNS}
              FROM approvals
             WHERE subject_type = %s AND subject_id = %s AND state = 'pending'
             ORDER BY created_at ASC
             LIMIT 1
             FOR UPDATE
            """,
            (subject_type, subject_id),
        )
        pending = _approval_row(cur.fetchone())
        if pending is None:
            return {
                "status": 404,
                "body": {
                    "error": "no pending approval for this subject — POST "
                             "{\"action\":\"request\"} first",
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                },
            }

        self_approving = pending["requested_by"] == actor
        if self_approving and REQUIRE_FOUR_EYES:
            audit.write_audit(
                conn,
                actor=actor,
                action="approval_decision_denied",
                resource=f"approvals/{pending['id']}",
                detail={"action": action, "reason": "four-eyes: requester may not decide"},
            )
            return {
                "status": 403,
                "body": {
                    "error": "four-eyes control: the requester may not decide their "
                             "own approval",
                    "approval": pending,
                },
            }

        cur.execute(
            f"""
            UPDATE approvals
               SET state = %s,
                   decided_by = %s,
                   decided_at = now(),
                   note = COALESCE(%s, note)
             WHERE id = %s
            RETURNING {APPROVAL_COLUMNS}
            """,
            (ACTION_TO_STATE[action], actor, note, pending["id"]),
        )
        approval = _approval_row(cur.fetchone())

    token = approval_token(approval)
    audit.write_audit(
        conn,
        actor=actor,
        action=f"approval_{approval['state']}",
        resource=f"approvals/{approval['id']}",
        detail={
            "subject_type": subject_type,
            "subject_id": subject_id,
            "requested_by": approval["requested_by"],
            "decided_by": approval["decided_by"],
            "self_approved": self_approving,
            "four_eyes_enforced": REQUIRE_FOUR_EYES,
            "note": note,
            "token_issued": bool(token),
        },
    )
    return {
        "status": 200,
        "body": {
            "approval": approval,
            "approval_token": token,
            "four_eyes": {
                "enforced": REQUIRE_FOUR_EYES,
                "self_approved": self_approving,
                "note": "Self-approval is recorded on the approval and in audit_log "
                        "whether or not the four-eyes control is enforced.",
            },
        },
    }


# --------------------------------------------------------------------------- #
# GET /anomalies
# --------------------------------------------------------------------------- #
ANOMALY_SQL = """
    SELECT a.id, a.grant_id, g.grant_no, g.title, g.program_area, g.org_unit,
           a.kind, a.severity, a.reason, a.status, a.created_at
      FROM anomalies a
      LEFT JOIN grants_curated g ON g.id = a.grant_id
     WHERE (a.grant_id IS NULL OR g.id IS NOT NULL)
       {status_clause}
       {severity_clause}
     ORDER BY CASE lower(a.severity)
                WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium'   THEN 2 WHEN 'low'  THEN 3 ELSE 4 END,
              a.created_at DESC
     LIMIT %s
"""


def list_anomalies(conn, params: Dict[str, str]) -> Dict[str, Any]:
    """Anomalies the caller is entitled to see.

    The RLS filter is the ``LEFT JOIN`` itself: ``anomalies`` has no
    ``org_unit`` column and no policy of its own, so a row is only surfaced if
    joining it to ``grants_curated`` under the caller's org context actually
    produced a grant (or if it is a batch-level anomaly with no ``grant_id``).
    An inner join would have silently dropped those batch-level rows; a bare
    ``SELECT * FROM anomalies`` would have leaked another org's grant numbers.
    """
    status = (params.get("status") or "open").strip().lower()
    severity = (params.get("severity") or "").strip().lower()
    try:
        limit = int(params.get("limit") or DEFAULT_ANOMALY_LIMIT)
    except ValueError:
        limit = DEFAULT_ANOMALY_LIMIT
    limit = max(1, min(limit, MAX_ANOMALY_LIMIT))

    args: List[Any] = []
    if status in ("all", "*"):
        status_clause = ""
    else:
        if status not in ANOMALY_STATUSES:
            status = "open"
        status_clause = "AND a.status = %s"
        args.append(status)

    if severity and severity in SEVERITY_RANK:
        severity_clause = "AND lower(a.severity) = %s"
        args.append(severity)
    else:
        severity_clause = ""
        severity = ""

    sql_text = ANOMALY_SQL.format(
        status_clause=status_clause, severity_clause=severity_clause
    )
    args.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql_text, tuple(args))
        rows = cur.fetchall()

    anomalies = [
        {
            "id": _int(r[0]),
            "grant_id": _int(r[1]),
            "grant_no": r[2],
            "title": r[3],
            "program_area": r[4],
            "org_unit": r[5],
            "kind": r[6],
            "severity": r[7],
            "reason": r[8],
            "status": r[9],
            "created_at": _iso(r[10]),
        }
        for r in rows
    ]

    by_severity: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for a in anomalies:
        sev = (a["severity"] or "unknown").lower()
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1

    return {
        "anomalies": anomalies,
        "summary": {
            "returned": len(anomalies),
            "by_severity": by_severity,
            "by_status": by_status,
            "truncated": len(anomalies) == limit,
        },
        "filters": {
            "status": status or "all",
            "severity": severity or "all",
            "limit": limit,
        },
    }


# --------------------------------------------------------------------------- #
# Handler
# --------------------------------------------------------------------------- #
def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    claims = http.get_claims(event)
    role, org_unit = resolve_identity(claims)
    if not role:
        return http.forbidden(
            "no Compass role on this identity — expected one of the "
            "compass-poweruser / compass-viewer Cognito groups"
        )

    method = (http.get_method(event) or "GET").upper()
    path = http.get_path(event) or ""
    actor = actor_of(claims)

    if method == "GET" or path.endswith("/anomalies"):
        try:
            conn = db.get_conn()
            with db.set_org(conn, org_unit) as c:
                return http.ok(list_anomalies(c, http.query_params(event)))
        except Exception:
            log.exception("anomaly query failed")
            return http.server_error("anomaly query failed")

    try:
        body = http.parse_body(event)
    except ValueError as exc:
        return http.bad_request(f"invalid JSON body: {exc}")

    try:
        conn = db.get_conn()
        with db.set_org(conn, org_unit) as c:
            result = create_or_advance(c, body, actor=actor, role=role)
    except Exception:
        log.exception("approval action failed")
        return http.server_error("approval action failed")

    return http.json_response(result["status"], result["body"])

"""Approval workflow and anomaly queue for the Compass demo.

Routes (docs/CONTRACTS.md):

    GET  /approvals   -> list pending approvals visible to the caller
    POST /approvals   -> create or advance an approval
    GET  /anomalies   -> list the caller's anomaly queue

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
with no pending request is a 404, not an implicit create. That is deliberate:
an approval record whose "request" step never happened is not evidence of
anything.

An **approved** decision returns an opaque ``approval_token``. Only the SHA-256
digest of its 32-byte secret is stored. The plaintext is returned once to the
reviewer and is never available from a read route. ``POST /export`` accepts the
token to clear its aggregation guard.

**Separation of duties.** Only ``poweruser`` may approve or reject; a
``viewer`` may request. Whether the *same* person may approve their own request
is a policy switch (``APPROVAL_REQUIRE_FOUR_EYES``, enabled by default), and
self-approval attempts are always recorded on the
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
import hashlib
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from compass_common import audit, db, http

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Roles allowed to decide (not merely request) an approval.
DECIDER_ROLES = {"poweruser"}
REQUIRE_FOUR_EYES = os.environ.get("APPROVAL_REQUIRE_FOUR_EYES", "true").lower() == "true"
APPROVAL_TTL_SECONDS = max(
    60,
    int(os.environ.get("APPROVAL_TTL_SECONDS", "3600")),
)

VALID_ACTIONS = ("request", "approve", "reject")
ACTION_TO_STATE = {"approve": "approved", "reject": "rejected"}

ANOMALY_STATUSES = ("open", "acknowledged", "resolved")
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEFAULT_ANOMALY_LIMIT = 100
MAX_ANOMALY_LIMIT = 500
APPROVAL_LIST_LIMIT = 100


# --------------------------------------------------------------------------- #
# Identity / coercion
# --------------------------------------------------------------------------- #
def resolve_identity(claims: http.Claims) -> Tuple[Optional[str], Optional[str]]:
    """Delegate to the shared deny-by-default identity contract."""
    return http.resolve_identity(claims)


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
    "decided_at, note, created_at, expires_at, consumed_at, consumed_by"
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
        "expires_at": _iso(row[9]),
        "consumed_at": _iso(row[10]),
        "consumed_by": row[11],
    }


def capability_digest(secret: str) -> str:
    """Return the storage-safe SHA-256 digest for a capability secret."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def build_approval_token(approval_id: int, secret: str) -> str:
    """Build the single response value from an id and a fresh opaque secret."""
    return f"apr-{approval_id}.{secret}"


# --------------------------------------------------------------------------- #
# GET /approvals
# --------------------------------------------------------------------------- #
def list_pending_approvals(
    conn,
    *,
    actor: str,
    role: str,
) -> Dict[str, Any]:
    """List pending decisions without crossing the caller's approval scope.

    A poweruser may review the shared pending queue. A viewer receives only
    requests whose ``requested_by`` value exactly matches the resolved actor.
    Capability tokens are never returned by this read path. They are issued
    once, to the separate reviewer, by the approved POST decision response.
    """
    params: List[Any] = ["pending"]
    actor_clause = ""
    if role not in DECIDER_ROLES:
        actor_clause = "AND requested_by = %s"
        params.append(actor)
    params.append(APPROVAL_LIST_LIMIT)

    with conn.cursor() as cur:
        query = (
            f"SELECT {APPROVAL_COLUMNS} "
            "FROM approvals WHERE state = %s "
            f"{actor_clause} ORDER BY created_at ASC, id ASC LIMIT %s"
        )
        cur.execute(
            query,
            tuple(params),
        )
        approvals = [
            approval
            for approval in (_approval_row(row) for row in cur.fetchall())
            if approval is not None
        ]

    return {
        "approvals": approvals,
        "actor": actor,
        "scope": "all_pending" if role in DECIDER_ROLES else "requested_by_actor",
        "can_decide": role in DECIDER_ROLES,
        "four_eyes_enforced": REQUIRE_FOUR_EYES,
        "tokens_included": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


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
            query = (
                f"SELECT {APPROVAL_COLUMNS} "
                "FROM approvals WHERE subject_type = %s AND subject_id = %s "
                "AND state = 'pending' AND requested_by = %s "
                "ORDER BY created_at DESC LIMIT 1"
            )
            cur.execute(
                query,
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
                        "approval_token": None,
                        "deduplicated": True,
                    },
                }

            query = (
                "INSERT INTO approvals "
                "(subject_type, subject_id, state, requested_by, note) "
                "VALUES (%s, %s, 'pending', %s, %s) "
                f"RETURNING {APPROVAL_COLUMNS}"
            )
            cur.execute(
                query,
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

        # Decide: approve or reject.
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
        query = (
            f"SELECT {APPROVAL_COLUMNS} "
            "FROM approvals WHERE subject_type = %s AND subject_id = %s "
            "AND state = 'pending' ORDER BY created_at ASC LIMIT 1 FOR UPDATE"
        )
        cur.execute(
            query,
            (subject_type, subject_id),
        )
        pending = _approval_row(cur.fetchone())
        if pending is None:
            return {
                "status": 404,
                "body": {
                    "error": "no pending approval for this subject. POST "
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

        capability_secret = secrets.token_urlsafe(32) if action == "approve" else None
        capability_hash = (
            capability_digest(capability_secret)
            if capability_secret is not None
            else None
        )

        query = (
            "UPDATE approvals SET state = %s, decided_by = %s, "
            "decided_at = now(), note = COALESCE(%s, note), "
            "expires_at = CASE WHEN %s = 'approved' "
            "THEN now() + (%s * interval '1 second') ELSE NULL END, "
            "consumed_at = NULL, consumed_by = NULL, capability_hash = %s "
            "WHERE id = %s "
            f"RETURNING {APPROVAL_COLUMNS}"
        )
        cur.execute(
            query,
            (
                ACTION_TO_STATE[action],
                actor,
                note,
                ACTION_TO_STATE[action],
                APPROVAL_TTL_SECONDS,
                capability_hash,
                pending["id"],
            ),
        )
        approval = _approval_row(cur.fetchone())

    token = (
        build_approval_token(approval["id"], capability_secret)
        if capability_secret is not None and approval["state"] == "approved"
        else None
    )
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
            "expires_at": approval["expires_at"],
            "ttl_seconds": APPROVAL_TTL_SECONDS if token else None,
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
     WHERE {scope_clause}
       {status_clause}
       {severity_clause}
     ORDER BY CASE lower(a.severity)
                WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                WHEN 'medium'   THEN 2 WHEN 'low'  THEN 3 ELSE 4 END,
              a.created_at DESC
     LIMIT %s
"""


def list_anomalies(
    conn,
    params: Dict[str, str],
    *,
    include_unbound: bool = False,
) -> Dict[str, Any]:
    """Anomalies the caller is entitled to see.

    The RLS filter is the ``LEFT JOIN`` itself: ``anomalies`` has no
    ``org_unit`` column and no policy of its own, so a row is only surfaced if
    joining it to ``grants_curated`` under the caller's org context actually
    produced a grant. Batch-level findings have no organization key, so they
    fail closed for viewers and are included only for the corporate reviewer.
    A bare ``SELECT * FROM anomalies`` would leak another org's findings.
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
        scope_clause=(
            "(a.grant_id IS NULL OR g.id IS NOT NULL)"
            if include_unbound
            else "g.id IS NOT NULL"
        ),
        status_clause=status_clause,
        severity_clause=severity_clause,
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
            "no Compass role on this identity. Expected one of the "
            "compass-poweruser / compass-viewer Cognito groups"
        )

    method = (http.get_method(event) or "GET").upper()
    path = http.get_path(event) or ""
    actor = actor_of(claims)

    if method == "OPTIONS":
        return http.json_response(200, {})

    if method == "GET" and path.rstrip("/").endswith("/approvals"):
        try:
            conn = db.get_conn()
            with db.set_org(conn, org_unit) as c:
                return http.ok(
                    list_pending_approvals(c, actor=actor, role=role)
                )
        except Exception:
            log.exception("approval inbox query failed")
            return http.server_error("approval inbox query failed")

    if method == "GET" and path.rstrip("/").endswith("/anomalies"):
        try:
            conn = db.get_conn()
            with db.set_org(conn, org_unit) as c:
                return http.ok(
                    list_anomalies(
                        c,
                        http.query_params(event),
                        include_unbound=role in DECIDER_ROLES,
                    )
                )
        except Exception:
            log.exception("anomaly query failed")
            return http.server_error("anomaly query failed")

    if method != "POST" or not path.rstrip("/").endswith("/approvals"):
        return http.not_found("approval route not found")

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

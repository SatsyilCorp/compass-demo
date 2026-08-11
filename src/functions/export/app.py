"""Governed export plus the served OpenAPI contract, element 7 of the Compass demo.

Routes (docs/CONTRACTS.md):

    POST /export        -> filtered export in csv | json | parquet
    GET  /openapi.json  -> the OpenAPI 3.1 document for the whole API

This is the endpoint where the governance story either holds or doesn't, so
all four controls are enforced here in one visible path:

1. **Row-level security.** Every query runs inside
   :func:`compass_common.db.set_org`, which issues
   ``SET LOCAL compass.org_unit = '<claim>'`` for the transaction. The
   ``grants_curated`` policies in db/migrations/002_rls.sql filter on that GUC.
   There is no ``WHERE org_unit = ...`` in this file: a ``viewer`` exports
   Code-30 rows because the database will not hand them anything else.

2. **Column-level security.** 002_rls.sql REVOKEs ``SELECT (amount_usd)`` from
   the runtime role, so a viewer's export physically cannot contain the dollar
   column. Powerusers read through the owner-owned ``grants_curated_corp`` view,
   which re-exposes the column while ``FORCE ROW LEVEL SECURITY`` keeps the same
   row policy in force. Two consequences worth noticing: asking for
   ``columns: ["amount_usd"]`` as a viewer is a 403, not a silently-dropped
   column, and *filtering* on ``min_amount_usd`` is refused for the same caller.
   a filter on a hidden column is a read of that column by binary search.

3. **The aggregation guard.** If the filter matches more than
   ``EXPORT_MAX_ROWS`` rows, the request is refused with **HTTP 428** and a body
   that names the row count, the cap, and the exact ``subject_id`` to request an
   approval for. Attaching an approved ``approval_token`` from ``POST /approvals``
   clears it. The guard measures the rows the *filter matched*, not the page
   returned, so lowering ``limit`` cannot page around the control.

4. **Audit.** Every outcome, including delivered, blocked at the guard, denied
   on a bad token, or failed in delivery, appends to ``compass.audit_log``. The
   allow-decision row is written inside the same transaction as the read, before
   any bytes leave the boundary, so the trail can over-record but never
   under-record.

Format support
--------------
``csv`` and ``json`` are always available (Python standard library only).
``parquet`` requires **pyarrow**, which is deliberately *not* bundled: the arm64
wheel is ~90 MB and would dominate this function's package for a format the demo
rarely uses. When pyarrow is absent, a parquet request does not fail. It returns
CSV with ``requested_format: "parquet"`` and an explicit note saying the parquet
layer is not installed and how to install it (uncomment the pinned line in
``src/functions/export/requirements.txt`` and redeploy). When pyarrow *is*
present, real parquet bytes are produced by the same code path. Nothing here
pretends to have written parquet that it didn't.

Delivery
--------
With ``EXPORT_BUCKET`` set (template.yaml wires it to the KMS-encrypted raw
bucket, write-scoped to ``exports/*``), the file is written to S3 and returned as
a 15-minute presigned URL. Without a bucket, such as local invoke or ``sam local``, a
small export is returned inline as a ``data:`` URI so the whole path is still
exercisable offline. Anything too large for either route is a 413 that says so.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from compass_common import audit, config, db, http

from openapi import build_openapi

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
EXPORT_BUCKET = os.environ.get("EXPORT_BUCKET", "")
EXPORT_PREFIX = os.environ.get("EXPORT_PREFIX", "exports")
PRESIGN_TTL_SECONDS = int(os.environ.get("EXPORT_PRESIGN_TTL", "900"))
# API Gateway caps a response near 6 MB and base64 inflates by 4/3, so keep the
# inline path well under it.
INLINE_MAX_BYTES = int(os.environ.get("EXPORT_INLINE_MAX_BYTES", "3000000"))
# Refuse to materialise an unbounded result set in a 1 GB Lambda.
HARD_MAX_ROWS = int(os.environ.get("EXPORT_HARD_MAX_ROWS", "100000"))

FORMATS = ("csv", "json", "parquet")
AMOUNT_COLUMN = "amount_usd"

# Columns a caller may export, and the default set.
DEFAULT_COLUMNS = [
    "grant_no",
    "title",
    "program_area",
    "fiscal_year",
    "awardee",
    "org_unit",
    "classification_band",
    "batch_id",
    "created_at",
]
OPTIONAL_COLUMNS = ["id", "abstract", AMOUNT_COLUMN]
ALLOWED_COLUMNS = DEFAULT_COLUMNS + OPTIONAL_COLUMNS

CONTENT_TYPES = {
    "csv": "text/csv",
    "json": "application/json",
    "parquet": "application/vnd.apache.parquet",
}
EXTENSIONS = {"csv": "csv", "json": "json", "parquet": "parquet"}


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def resolve_identity(claims: http.Claims) -> Tuple[Optional[str], Optional[str]]:
    """Delegate to the shared deny-by-default identity contract."""
    return http.resolve_identity(claims)


def actor_of(claims: http.Claims) -> str:
    return claims.username or claims.email or claims.sub or "unknown"


# --------------------------------------------------------------------------- #
# Filters: whitelist only
# --------------------------------------------------------------------------- #
def _like(value: Any) -> str:
    return f"%{value}%"


# name -> (sql fragment, number of params, param builder)
FILTER_SPEC: Dict[str, Tuple[str, Any]] = {
    "program_area": ("program_area = %s", lambda v: (str(v),)),
    "org_unit": ("org_unit = %s", lambda v: (str(v),)),
    "awardee": ("awardee ILIKE %s", lambda v: (_like(v),)),
    "classification_band": ("classification_band = %s", lambda v: (str(v),)),
    "batch_id": ("batch_id = %s", lambda v: (str(v),)),
    "grant_no": ("grant_no = %s", lambda v: (str(v),)),
    "fiscal_year": ("fiscal_year = %s", lambda v: (int(v),)),
    "fiscal_year_min": ("fiscal_year >= %s", lambda v: (int(v),)),
    "fiscal_year_max": ("fiscal_year <= %s", lambda v: (int(v),)),
    "q": ("(title ILIKE %s OR abstract ILIKE %s)", lambda v: (_like(v), _like(v))),
}
# Filters that read the CLS-protected money column.
AMOUNT_FILTER_SPEC: Dict[str, Tuple[str, Any]] = {
    "min_amount_usd": ("amount_usd >= %s", lambda v: (Decimal(str(v)),)),
    "max_amount_usd": ("amount_usd <= %s", lambda v: (Decimal(str(v)),)),
}
NON_PREDICATE_FILTERS = {"limit"}


class FilterError(ValueError):
    """A filter the caller may not use, or cannot be parsed."""

    def __init__(self, message: str, status: int = 400, **extra: Any):
        super().__init__(message)
        self.status = status
        self.extra = extra


def build_where(filters: Dict[str, Any], amount_visible: bool) -> Tuple[str, List[Any], Dict[str, Any]]:
    """Compile whitelisted filters into ``(where_sql, params, applied)``.

    Unknown keys are a 400. A filter the caller
    believes was applied but wasn't is a governance bug). Amount filters are a
    403 for a caller whose ``amount_usd`` is masked: allowing them would let a
    viewer binary-search a column they are not entitled to read.
    """
    clauses: List[str] = []
    params: List[Any] = []
    applied: Dict[str, Any] = {}

    for key, value in (filters or {}).items():
        if value is None or value == "":
            continue
        if key in NON_PREDICATE_FILTERS:
            continue
        if key in AMOUNT_FILTER_SPEC:
            if not amount_visible:
                raise FilterError(
                    "column-level security: this role cannot read amount_usd, so it "
                    "cannot filter on it either",
                    status=403,
                    filter=key,
                )
            frag, builder = AMOUNT_FILTER_SPEC[key]
        elif key in FILTER_SPEC:
            frag, builder = FILTER_SPEC[key]
        else:
            raise FilterError(
                f"unsupported filter '{key}'",
                status=400,
                supported=sorted(list(FILTER_SPEC) + list(AMOUNT_FILTER_SPEC) + list(NON_PREDICATE_FILTERS)),
            )
        try:
            built = builder(value)
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise FilterError(f"filter '{key}' has an invalid value: {exc}", status=400) from exc
        clauses.append(frag)
        params.extend(built)
        applied[key] = value

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params, applied


def parse_limit(filters: Dict[str, Any]) -> Optional[int]:
    raw = (filters or {}).get("limit")
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise FilterError(f"limit must be an integer: {raw}", status=400) from exc
    if value <= 0:
        raise FilterError("limit must be positive", status=400)
    return value


def resolve_columns(requested: Any, amount_visible: bool) -> List[str]:
    """Validate the requested column list against the whitelist."""
    if not requested:
        cols = list(DEFAULT_COLUMNS)
        if amount_visible:
            cols.insert(cols.index("awardee"), AMOUNT_COLUMN)
        return cols

    if not isinstance(requested, list) or not all(isinstance(c, str) for c in requested):
        raise FilterError("columns must be an array of strings", status=400)

    cols: List[str] = []
    for c in requested:
        name = c.strip()
        if name not in ALLOWED_COLUMNS:
            raise FilterError(
                f"column '{name}' is not exportable",
                status=400,
                allowed=ALLOWED_COLUMNS,
            )
        if name == AMOUNT_COLUMN and not amount_visible:
            raise FilterError(
                "column-level security: amount_usd is not readable by this role",
                status=403,
                column=name,
            )
        if name not in cols:
            cols.append(name)
    if not cols:
        raise FilterError("columns must not be empty", status=400)
    return cols


# --------------------------------------------------------------------------- #
# Approval tokens
# --------------------------------------------------------------------------- #
def filter_fingerprint(org_unit: str, fmt: str, columns: Sequence[str], applied: Dict[str, Any]) -> str:
    """Deterministic id for *this exact* export request.

    Returned in the 428 body as ``subject_id`` so an approval is granted for a
    specific query, from a specific org, in a specific shape, not a standing
    licence to export anything. Includes ``org_unit`` so an approval issued to
    one org cannot be replayed by another.
    """
    canonical = json.dumps(
        {
            "org_unit": org_unit,
            "format": fmt,
            "columns": sorted(columns),
            "filters": {k: str(v) for k, v in sorted(applied.items())},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "exp-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


APPROVAL_TOKEN_PATTERN = re.compile(
    r"^apr-(?P<approval_id>[1-9][0-9]*)\.(?P<secret>[A-Za-z0-9_-]{43})$"
)


def parse_token(token: str) -> Optional[Tuple[int, str]]:
    """Parse the opaque token shape and reject legacy id-only tokens."""
    matched = APPROVAL_TOKEN_PATTERN.fullmatch((token or "").strip())
    if matched is None:
        return None
    return int(matched.group("approval_id")), matched.group("secret")


def capability_digest(secret: str) -> str:
    """Return the SHA-256 digest stored by the approval service."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def check_approval(
    conn,
    token: str,
    subject_id: str,
    *,
    actor: str = "unknown",
) -> Tuple[bool, Dict[str, Any]]:
    """Atomically validate and consume an export approval token.

    The approval must be approved, unexpired, unused, and bound to the exact
    export fingerprint. ``FOR UPDATE`` plus the conditional consume update
    means two concurrent exports cannot spend the same approval.
    """
    parsed = parse_token(token)
    if parsed is None:
        return False, {
            "code": "approval_capability_invalid",
            "reason": "malformed or legacy approval_token",
        }
    approval_id, presented_secret = parsed
    presented_hash = capability_digest(presented_secret)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, subject_type, subject_id, state, requested_by, decided_by,
                   decided_at, expires_at, consumed_at, consumed_by,
                   capability_hash,
                   (expires_at IS NOT NULL AND expires_at > now()) AS is_active
              FROM approvals
             WHERE id = %s
             FOR UPDATE
            """,
            (approval_id,),
        )
        row = cur.fetchone()

    if row is None:
        return False, {
            "code": "approval_capability_invalid",
            "reason": f"approval {approval_id} does not exist",
            "approval_id": approval_id,
        }

    stored_hash = row[10]
    if not isinstance(stored_hash, str) or not hmac.compare_digest(
        stored_hash,
        presented_hash,
    ):
        return False, {
            "code": "approval_capability_invalid",
            "reason": "approval_token secret rejected",
            "approval_id": approval_id,
        }

    detail = {
        "approval_id": int(row[0]),
        "subject_type": row[1],
        "subject_id": row[2],
        "state": row[3],
        "requested_by": row[4],
        "decided_by": row[5],
        "decided_at": row[6].isoformat() if isinstance(row[6], (datetime, date)) else row[6],
        "expires_at": row[7].isoformat() if isinstance(row[7], (datetime, date)) else row[7],
        "consumed_at": row[8].isoformat() if isinstance(row[8], (datetime, date)) else row[8],
        "consumed_by": row[9],
    }

    if detail["state"] != "approved":
        detail["code"] = "approval_capability_invalid"
        detail["reason"] = f"approval {approval_id} is '{detail['state']}', not 'approved'"
        return False, detail
    if (detail["subject_type"] or "").lower() != "export":
        detail["code"] = "approval_capability_invalid"
        detail["reason"] = (
            f"approval {approval_id} was raised for subject_type "
            f"'{detail['subject_type']}', not 'export'"
        )
        return False, detail

    subject = detail["subject_id"] or ""
    if not subject_id.startswith("exp-") or subject != subject_id:
        detail["code"] = "approval_capability_unbound"
        detail["binding"] = "rejected"
        detail["reason"] = (
            "approval is not bound to this exact export fingerprint "
            f"(approved {subject or 'empty'}; expected {subject_id})"
        )
        return False, detail
    if detail["consumed_at"] is not None:
        detail["code"] = "approval_capability_consumed"
        detail["reason"] = (
            f"approval {approval_id} was already consumed at "
            f"{detail['consumed_at']}"
        )
        return False, detail
    if not bool(row[11]):
        detail["code"] = "approval_capability_expired"
        detail["reason"] = (
            f"approval {approval_id} expired at "
            f"{detail['expires_at'] or 'an unspecified time'}"
        )
        return False, detail

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE approvals
               SET consumed_at = now(), consumed_by = %s
             WHERE id = %s
               AND state = 'approved'
               AND consumed_at IS NULL
               AND expires_at > now()
               AND capability_hash = %s
            RETURNING consumed_at
            """,
            (actor, approval_id, presented_hash),
        )
        consumed = cur.fetchone()
    if consumed is None:
        detail["code"] = "approval_capability_unavailable"
        detail["reason"] = (
            f"approval {approval_id} could not be consumed because it expired "
            "or was used by another request"
        )
        return False, detail

    consumed_at = consumed[0]
    detail["consumed_at"] = (
        consumed_at.isoformat()
        if isinstance(consumed_at, (datetime, date))
        else consumed_at
    )
    detail["consumed_by"] = actor
    detail["binding"] = "exact-request"
    return True, detail


# --------------------------------------------------------------------------- #
# Reading rows
# --------------------------------------------------------------------------- #
def _relation(amount_needed: bool) -> str:
    """``grants_curated_corp`` re-exposes amount_usd; the base table does not."""
    return "grants_curated_corp" if amount_needed else "grants_curated"


def amount_readable(conn, role: str) -> Tuple[bool, Optional[str]]:
    """Can this caller actually read ``amount_usd``? Probe, don't assume.

    Entitlement is a database grant, so it is answered by asking the database.
    The probe runs inside a SAVEPOINT: a plain failed statement would poison the
    transaction, and a plain rollback would discard the enclosing
    ``SET LOCAL compass.org_unit`` and silently drop RLS context for everything
    that followed.
    """
    if role != "poweruser":
        return False, (
            "column-level security: amount_usd is REVOKEd from the compass_app role "
            "and this persona is not entitled to the unmasked view"
        )

    import psycopg2.errors

    with conn.cursor() as cur:
        cur.execute("SAVEPOINT amount_probe")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT amount_usd FROM grants_curated_corp LIMIT 1")
            cur.fetchall()
        with conn.cursor() as cur:
            cur.execute("RELEASE SAVEPOINT amount_probe")
        return True, None
    except (psycopg2.errors.InsufficientPrivilege, psycopg2.errors.UndefinedTable) as exc:
        with conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT amount_probe")
        log.warning("amount_usd unreadable for a poweruser, masking: %s", exc)
        return False, (
            "amount_usd is not readable by the runtime role on this deployment "
            "(grants_curated_corp missing or not granted); masked rather than failing open"
        )


def count_rows(conn, relation: str, where: str, params: Sequence[Any]) -> int:
    from psycopg2 import sql

    query = sql.SQL("SELECT COUNT(*) FROM {rel}" + where).format(rel=sql.Identifier(relation))
    with conn.cursor() as cur:
        cur.execute(query, tuple(params))
        return int(cur.fetchone()[0])


def fetch_rows(
    conn,
    relation: str,
    columns: Sequence[str],
    where: str,
    params: Sequence[Any],
    limit: Optional[int],
) -> List[tuple]:
    from psycopg2 import sql

    col_sql = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
    text = "SELECT {cols} FROM {rel}" + where + " ORDER BY grant_no"
    args = list(params)
    if limit is not None:
        text += " LIMIT %s"
        args.append(limit)
    query = sql.SQL(text).format(cols=col_sql, rel=sql.Identifier(relation))
    with conn.cursor() as cur:
        cur.execute(query, tuple(args))
        return cur.fetchall()


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def _scalar(value: Any) -> Any:
    """DB value -> JSON/CSV-friendly scalar."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        f = float(value)
        return int(f) if f.is_integer() else f
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def to_csv(columns: Sequence[str], rows: Sequence[tuple]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if v is None else _scalar(v) for v in row])
    return buf.getvalue().encode("utf-8")


def to_json(
    columns: Sequence[str],
    rows: Sequence[tuple],
    meta: Dict[str, Any],
) -> bytes:
    records = [{c: _scalar(v) for c, v in zip(columns, row)} for row in rows]
    payload = dict(meta)
    payload["records"] = records
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def parquet_available() -> bool:
    """True only if pyarrow imports *and* exposes the writer we call.

    A bare ``find_spec`` would pass for a wheel built for the wrong architecture;
    actually importing is the only honest check on a Lambda package.
    """
    try:
        import pyarrow.parquet as pq
    except Exception:  # ImportError, or a wheel built for the wrong arch
        return False
    return hasattr(pq, "write_table")


PARQUET_MISSING_NOTE = (
    "parquet layer not installed: pyarrow is not bundled with this function, so "
    "CSV was produced instead. To enable parquet, uncomment the pinned pyarrow "
    "line in src/functions/export/requirements.txt and redeploy "
    "(`sam build --use-container` on macOS so the arm64 manylinux wheel is used)."
)


def to_parquet(columns: Sequence[str], rows: Sequence[tuple]) -> bytes:
    """Real parquet bytes. Only called when :func:`parquet_available` is True."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    def native(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        return value

    table = pa.table(
        {col: [native(row[i]) for row in rows] for i, col in enumerate(columns)}
    )
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="snappy")
    return sink.getvalue()


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #
def deliver(payload: bytes, key_name: str, content_type: str) -> Dict[str, Any]:
    """Return ``{download_url, delivery, ...}`` or raise ``FilterError(413)``."""
    if EXPORT_BUCKET:
        import boto3

        s3 = boto3.client("s3", region_name=config.aws_region())
        now = datetime.now(timezone.utc)
        key = f"{EXPORT_PREFIX}/{now:%Y/%m/%d}/{key_name}"
        # The bucket enforces SSE-KMS by default (template.yaml), so no explicit
        # encryption arguments are needed. None are passed, so the bucket's
        # key is always the one used.
        s3.put_object(
            Bucket=EXPORT_BUCKET,
            Key=key,
            Body=payload,
            ContentType=content_type,
        )
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": EXPORT_BUCKET, "Key": key},
            ExpiresIn=PRESIGN_TTL_SECONDS,
        )
        return {
            "download_url": url,
            "delivery": "s3-presigned",
            "s3_uri": f"s3://{EXPORT_BUCKET}/{key}",
            "expires_in_seconds": PRESIGN_TTL_SECONDS,
        }

    if len(payload) <= INLINE_MAX_BYTES:
        b64 = base64.b64encode(payload).decode("ascii")
        return {
            "download_url": f"data:{content_type};base64,{b64}",
            "delivery": "inline-data-uri",
            "s3_uri": None,
        }

    raise FilterError(
        f"export is {len(payload)} bytes, which exceeds the {INLINE_MAX_BYTES}-byte "
        "inline limit and no EXPORT_BUCKET is configured for this deployment; "
        "narrow the filters or set EXPORT_BUCKET",
        status=413,
    )


# --------------------------------------------------------------------------- #
# POST /export
# --------------------------------------------------------------------------- #
def run_export(
    conn, body: Dict[str, Any], *, actor: str, role: str, org_unit: str
) -> Dict[str, Any]:
    """Execute the guarded export. Returns ``{"status", "body", "payload"?}``.

    ``payload`` (bytes + content type) is returned separately so the caller can
    deliver it *after* the read transaction commits. The audit row lands first.
    """
    fmt = str(body.get("format") or "csv").strip().lower()
    if fmt not in FORMATS:
        return {"status": 400, "body": {"error": f"format must be one of {list(FORMATS)}", "format": fmt}}

    amount_visible, mask_reason = amount_readable(conn, role)
    filters = body.get("filters") or {}
    if not isinstance(filters, dict):
        return {"status": 400, "body": {"error": "filters must be an object"}}

    try:
        columns = resolve_columns(body.get("columns"), amount_visible)
        where, params, applied = build_where(filters, amount_visible)
        limit = parse_limit(filters)
    except FilterError as exc:
        return {"status": exc.status, "body": {"error": str(exc), **exc.extra}}

    amount_needed = AMOUNT_COLUMN in columns or any(k in AMOUNT_FILTER_SPEC for k in applied)
    relation = _relation(amount_needed and amount_visible)
    masked_fields: List[str] = [] if amount_visible else [AMOUNT_COLUMN]
    request_filters = dict(applied)
    if limit is not None:
        request_filters["limit"] = limit

    matched = count_rows(conn, relation, where, params)
    subject_id = filter_fingerprint(org_unit, fmt, columns, request_filters)
    max_rows = config.export_max_rows()

    base_detail = {
        "role": role,
        "org_unit": org_unit,
        "format": fmt,
        "columns": columns,
        "filters": request_filters,
        "matched_rows": matched,
        "max_rows": max_rows,
        "subject_id": subject_id,
    }

    # The hard materialization cap cannot be overridden by an approval. Check
    # it before consuming a one-time token so a request that can never run does
    # not spend the approval.
    to_write = matched if limit is None else min(matched, limit)
    if to_write > HARD_MAX_ROWS:
        audit.write_audit(
            conn,
            actor=actor,
            action="export_denied",
            resource="grants_curated",
            detail={**base_detail, "decision": "denied", "reason": "hard row cap"},
        )
        return {
            "status": 413,
            "body": {
                "error": f"export of {to_write} rows exceeds the {HARD_MAX_ROWS}-row "
                         "materialisation cap for this function",
                "row_count": to_write,
                "hard_max_rows": HARD_MAX_ROWS,
            },
        }

    # --- aggregation guard --------------------------------------------------- #
    token = (body.get("approval_token") or "").strip()
    approval_detail: Optional[Dict[str, Any]] = None
    if matched > max_rows:
        if not token:
            audit.write_audit(
                conn,
                actor=actor,
                action="export_blocked",
                resource="grants_curated",
                detail={**base_detail, "decision": "blocked", "reason": "aggregation guard"},
            )
            return {
                "status": 428,
                "body": {
                    "error": "approval_required",
                    "row_count": matched,
                    "max_rows": max_rows,
                    "subject_type": "export",
                    "subject_id": subject_id,
                    "how_to_clear": (
                        'POST /approvals {"subject_type":"export","subject_id":'
                        f'"{subject_id}","action":"request"}}, have a poweruser approve it, '
                        "then retry this export with the returned approval_token."
                    ),
                },
            }

        ok, approval_detail = check_approval(
            conn,
            token,
            subject_id,
            actor=actor,
        )
        if not ok:
            audit.write_audit(
                conn,
                actor=actor,
                action="export_denied",
                resource="grants_curated",
                detail={**base_detail, "decision": "denied", "approval": approval_detail},
            )
            return {
                "status": 403,
                "body": {
                    "error": "approval_token rejected",
                    "code": approval_detail.get(
                        "code", "approval_capability_invalid"
                    ),
                    "reason": (
                        "opaque approval capability is invalid, expired, consumed, "
                        "or not bound to this request"
                    ),
                    "row_count": matched,
                    "max_rows": max_rows,
                    "subject_type": "export",
                    "subject_id": subject_id,
                },
            }

    rows = fetch_rows(conn, relation, columns, where, params, limit)

    # --- serialise ------------------------------------------------------------ #
    export_id = f"export-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    effective_format = fmt
    note: Optional[str] = None

    if fmt == "parquet" and not parquet_available():
        effective_format = "csv"
        note = PARQUET_MISSING_NOTE

    meta = {
        "export_id": export_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "compass.grants_curated",
        "org_unit": org_unit,
        "role": role,
        "columns": list(columns),
        "filters": request_filters,
        "matched_rows": matched,
        "row_count": len(rows),
        "masked_fields": masked_fields,
        "mask_reason": mask_reason,
        "classification": "CUI-Mock | fully synthetic demonstration data, no real CUI/PII",
    }

    if effective_format == "csv":
        payload = to_csv(columns, rows)
    elif effective_format == "json":
        payload = to_json(columns, rows, meta)
    else:
        payload = to_parquet(columns, rows)

    detail = {
        **base_detail,
        "decision": "allowed",
        "row_count": len(rows),
        "effective_format": effective_format,
        "bytes": len(payload),
        "export_id": export_id,
        "masked_fields": masked_fields,
        "approval_used": bool(token),
        "approval_id": approval_detail.get("approval_id") if approval_detail else None,
        "approval": approval_detail,
        "guard_tripped": matched > max_rows,
    }
    audit_id = audit.write_audit(
        conn,
        actor=actor,
        action="export",
        resource="grants_curated",
        detail=detail,
    )

    response = {
        "export_id": export_id,
        "row_count": len(rows),
        "matched_rows": matched,
        "format": effective_format,
        "requested_format": fmt,
        "columns": list(columns),
        "masked_fields": masked_fields,
        "mask_reason": mask_reason,
        "filters_applied": request_filters,
        "bytes": len(payload),
        "audited": True,
        "audit_id": audit_id,
        "guard": {
            "max_rows": max_rows,
            "matched_rows": matched,
            "tripped": matched > max_rows,
            "cleared_by_approval": approval_detail,
        },
    }
    if note:
        response["note"] = note

    return {
        "status": 200,
        "body": response,
        "payload": payload,
        "content_type": CONTENT_TYPES[effective_format],
        "filename": f"{export_id}.{EXTENSIONS[effective_format]}",
        "audit_detail": detail,
    }


# --------------------------------------------------------------------------- #
# GET /openapi.json
# --------------------------------------------------------------------------- #
def server_url_from(event: Dict[str, Any]) -> str:
    """Bind the contract's ``servers`` block to the deployment serving it."""
    rc = (event or {}).get("requestContext") or {}
    domain = rc.get("domainName")
    stage = rc.get("stage")
    if not domain:
        return ""
    if stage and stage != "$default" and domain.endswith(".amazonaws.com"):
        return f"https://{domain}/{stage}"
    return f"https://{domain}"


# --------------------------------------------------------------------------- #
# Handler
# --------------------------------------------------------------------------- #
def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    path = http.get_path(event) or ""
    method = (http.get_method(event) or "POST").upper()

    # The contract itself. Still behind the API's JWT authorizer (deny-by-default
    # happens at the gateway); no Compass role is required to read the schema.
    if method == "GET" or path.endswith("openapi.json"):
        return http.json_response(200, build_openapi(server_url_from(event)))

    claims = http.get_claims(event)
    role, org_unit = resolve_identity(claims)
    if not role:
        return http.forbidden(
            "no Compass role on this identity. Expected one of the "
            "compass-poweruser / compass-viewer Cognito groups"
        )
    actor = actor_of(claims)

    try:
        body = http.parse_body(event)
    except ValueError as exc:
        return http.bad_request(f"invalid JSON body: {exc}")

    try:
        conn = db.get_conn()
        with db.set_org(conn, org_unit) as c:
            result = run_export(c, body, actor=actor, role=role, org_unit=org_unit)
    except FilterError as exc:
        return http.json_response(exc.status, {"error": str(exc), **exc.extra})
    except Exception:
        log.exception("export failed (actor=%s org=%s)", actor, org_unit)
        return http.server_error("export failed")

    if result["status"] != 200:
        return http.json_response(result["status"], result["body"])

    # The read transaction has committed and the audit row is durable; only now
    # do bytes leave the boundary.
    try:
        delivery = deliver(result["payload"], result["filename"], result["content_type"])
    except FilterError as exc:
        _audit_out_of_band(
            actor,
            "export_delivery_failed",
            {**result["audit_detail"], "reason": str(exc)},
        )
        return http.json_response(exc.status, {"error": str(exc), **exc.extra})
    except Exception as exc:
        log.exception("export delivery failed")
        _audit_out_of_band(
            actor,
            "export_delivery_failed",
            {**result["audit_detail"], "reason": repr(exc)},
        )
        return http.server_error("export was authorised and audited but delivery failed")

    delivery_locator = delivery.get("s3_uri")
    _audit_out_of_band(
        actor,
        "export_delivered",
        {
            "export_id": result["body"]["export_id"],
            "audit_id": result["body"]["audit_id"],
            "delivery": delivery["delivery"],
            "delivery_reference": (
                hashlib.sha256(str(delivery_locator).encode()).hexdigest()[:16]
                if delivery_locator
                else None
            ),
            "bytes": result["body"]["bytes"],
        },
    )

    body_out = dict(result["body"])
    body_out.update(
        {
            "download_url": delivery["download_url"],
            "delivery": delivery["delivery"],
        }
    )
    if "expires_in_seconds" in delivery:
        body_out["expires_in_seconds"] = delivery["expires_in_seconds"]
    return http.ok(body_out)


def _audit_out_of_band(actor: str, action: str, detail: Dict[str, Any]) -> None:
    """Append a post-transaction audit row; never let auditing break the reply."""
    try:
        conn = db.get_conn()
        audit.write_audit(conn, actor=actor, action=action, resource="grants_curated", detail=detail)
    except Exception:
        log.exception("could not append %s audit row", action)

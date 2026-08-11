"""Immutable audit trail - append one row to ``compass.audit_log``.

Every export and every aggregation-guard decision writes here (the ``/export``
route's tamper-evidence story). The insert is unqualified: the ``search_path``
db.py pins to the ``compass`` schema routes it to ``compass.audit_log`` - never
``public``.

``detail`` is serialized with ``json.dumps`` and cast to ``jsonb`` in SQL
(``%s::jsonb``) rather than via ``psycopg2.extras.Json``, so this module imports
with no native psycopg2 extension and the offline smoke test can exercise it
against a fake cursor.
"""
from __future__ import annotations

import json
from typing import Any, Optional


def write_audit(
    conn,
    actor: str,
    action: str,
    resource: Optional[str] = None,
    detail: Optional[Any] = None,
) -> int:
    """Append an audit record and return its new ``id``.

    Args:
        conn:     a live connection (from :func:`compass_common.db.get_conn`).
                  If called inside a :func:`compass_common.db.set_org` block the
                  insert participates in that transaction and commits with it;
                  otherwise the connection's autocommit persists it immediately.
        actor:    who did it (username / sub from the JWT claims).
        action:   what they did (e.g. ``"export"``, ``"export_blocked"``).
        resource: what it acted on (e.g. ``"grants_curated"``).
        detail:   any JSON-serializable context (row counts, filters, decision).

    Returns:
        The generated ``audit_log.id``.
    """
    detail_json = None if detail is None else json.dumps(detail, default=str)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log (actor, action, resource, detail_jsonb) "
            "VALUES (%s, %s, %s, %s::jsonb) RETURNING id",
            (actor, action, resource, detail_json),
        )
        row = cur.fetchone()
    return row[0] if row else 0

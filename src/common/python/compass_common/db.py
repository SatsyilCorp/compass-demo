"""Schema-isolated, RLS-aware Postgres access for every Compass Lambda.

Adapted from the ``satsyil_db`` building block (cached psycopg2 connection with
cold-start retry + search_path isolation), extended with the two things
Compass's IL5 story depends on:

1. **Run as the least-privilege role.** The DB *login* (from Secrets Manager)
   is only a *member* of ``compass_app``; ``compass_app`` itself is ``NOLOGIN``.
   Right after connecting we ``SET ROLE compass_app`` so all application SQL runs
   as the non-owner role that Column-Level Security (the ``amount_usd`` REVOKE in
   002_rls.sql) and ``FORCE ROW LEVEL SECURITY`` actually bind to. Connecting as
   an owner/superuser would silently bypass CLS and, without FORCE, RLS.

2. **Apply the request's org context per transaction.** ``set_org(conn, org)``
   opens a real transaction and issues ``SET LOCAL compass.org_unit = %s`` — the
   exact GUC the ``grants_curated`` policies read via
   ``current_setting('compass.org_unit', true)``. ``SET LOCAL`` is scoped to the
   transaction, so the context can never leak to the next request on a warm,
   pooled connection.

Never write ``public.<table>``. The ``search_path`` is pinned to
``<DB_SCHEMA>, public`` (default schema ``compass``) after every connect, so all
application SQL stays *unqualified* and routes to the ``compass`` schema.

Dependency injection (for offline tests): ``get_conn(connect=..., secret_loader=...)``
accepts fakes so the smoke test touches no network, AWS, or DB. psycopg2 is
imported lazily inside the default factories, so this module imports cleanly
with no native extension present.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Callable, Iterator

from . import config

# Per-execution-environment cache (each warm Lambda instance keeps its own).
_db_conn = None
_secrets_client = None


def _default_secret_loader() -> dict:
    """Fetch the DB credential secret ({"username","password"}) from Secrets Manager."""
    global _secrets_client
    import boto3  # lazy — not needed when a fake loader is injected

    if _secrets_client is None:
        _secrets_client = boto3.client("secretsmanager", region_name=config.aws_region())
    resp = _secrets_client.get_secret_value(SecretId=config.db_secret_arn())
    return json.loads(resp["SecretString"])


def _default_connect(secret: dict):
    """Open a fresh TLS psycopg2 connection using the login credentials."""
    import psycopg2

    return psycopg2.connect(
        host=config.db_host(),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=config.db_name(),
        user=secret["username"],
        password=secret["password"],
        sslmode="require",
        connect_timeout=60,
    )


def _apply_session_settings(conn, schema: str) -> None:
    """Assume ``compass_app`` and pin the search_path — re-run after any reconnect.

    Both are session-level settings that Postgres resets to the role default if
    the connection drops, so they are re-applied on every (re)connect. ``SET``
    cannot be parameterized; ``psycopg2.sql`` identifier quoting keeps the role
    and schema names injection-safe.
    """
    from psycopg2 import sql

    with conn.cursor() as cur:
        cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(config.APP_ROLE)))
        cur.execute(
            sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema))
        )


def get_conn(
    connect: Callable[[dict], object] | None = None,
    secret_loader: Callable[[], dict] | None = None,
):
    """Return a healthy connection running as ``compass_app``, reconnecting if stale.

    Three cold-start connect attempts with 20s/40s/60s backoff. On warm reuse,
    roll back a connection left in a non-READY state and re-assert the session
    settings; on a dead socket, drop and reconnect. ``autocommit`` is True at
    rest — ``set_org`` opens the explicit transactions that RLS needs.
    """
    global _db_conn
    import psycopg2
    import psycopg2.extensions

    connect = connect or _default_connect
    secret_loader = secret_loader or _default_secret_loader
    schema = config.db_schema()

    if _db_conn is None or getattr(_db_conn, "closed", 0):
        secret = secret_loader()
        last_err = None
        for attempt in range(3):
            try:
                _db_conn = connect(secret)
                _db_conn.autocommit = True
                _apply_session_settings(_db_conn, schema)
                return _db_conn
            except psycopg2.OperationalError as e:
                last_err = e
                if attempt < 2:
                    time.sleep(20 * (attempt + 1))
        raise last_err
    else:
        try:
            if _db_conn.status != psycopg2.extensions.STATUS_READY:
                _db_conn.rollback()
                _apply_session_settings(_db_conn, schema)
        except Exception:
            _db_conn = None
            return get_conn(connect=connect, secret_loader=secret_loader)
    return _db_conn


@contextmanager
def set_org(conn, org_unit: str) -> Iterator[object]:
    """Bind the request's RLS org context for the duration of one transaction.

    Opens a real transaction (``autocommit`` off), issues
    ``SET LOCAL compass.org_unit = %s`` so the ``grants_curated`` policies filter
    to the caller's org (or, for ``ONR-Corporate``, all rows), yields the
    connection for the caller's queries, then commits. Any exception rolls the
    transaction back — nothing partial, and the org GUC is discarded with the
    transaction so it cannot bleed into the next invocation on a warm connection.

    Yields the connection; open cursors off it inside the ``with`` block::

        with set_org(conn, claims.org_unit) as c, c.cursor() as cur:
            cur.execute("SELECT grant_no, title FROM grants_curated")
    """
    if not isinstance(org_unit, str) or not org_unit.strip():
        raise ValueError("set_org requires a non-empty org_unit (RLS context)")

    prev_autocommit = conn.autocommit
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            # psycopg2 mogrifies params client-side, so a parameterized SET is safe.
            cur.execute("SET LOCAL compass.org_unit = %s", (org_unit,))
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = prev_autocommit


def reset_cache() -> None:
    """Drop the cached connection + secrets client (used between tests)."""
    global _db_conn, _secrets_client
    _db_conn = None
    _secrets_client = None

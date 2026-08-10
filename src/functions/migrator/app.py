"""In-VPC SQL runner: applies ``db/migrations/*.sql`` to the private cluster.

Adapted from the ``db-conn-schema-isolation`` block's ``migrator_handler``
(satsyil-blocks/code/py/satsyil_db/satsyil_db/migrator.py) — same operator
story: the Aurora cluster has no public endpoint, so the only way in is a
Lambda that already lives in the VPC. Extended here with a ``{"migrate":"all"}``
mode that applies a whole migration set in order and records each file in
``compass._schema_migrations``.

**Why this function does NOT use ``compass_common.db``**
``compass_common.db.get_conn`` issues ``SET ROLE compass_app`` — the
least-privilege, non-owner role every application Lambda runs as, and the role
that ``FORCE ROW LEVEL SECURITY`` and the ``amount_usd`` column REVOKE bind to.
The migrator is the *owner*: it must create schemas, tables, roles and
policies, which ``compass_app`` cannot do. So it connects with the login
credentials directly and never assumes the app role. That split — "migrator
owns; app connects as compass_app" — is exactly what docs/CONTRACTS.md
requires for RLS to be real rather than decorative.

Event shapes
------------
``{"migrate": "all"}``
    Discover ``*.sql`` recursively under the first readable migrations root
    (see :func:`find_migrations_root`), apply them in sorted filename order,
    skip any already recorded in ``_schema_migrations``, and record each one.
``{"migrate": "all", "migrations": [{"name": "001_schema", "sql": "..."}]}``
    Same, but the caller supplies the files (the deploy script reads
    ``db/migrations`` locally and passes the contents — no bundling needed).
``{"migrate": "all", "force": true}``
    Re-apply files even if already recorded (every migration in this repo is
    written to be idempotent).
``{"sql": "...", "fetch": "all"|"one", "migration_name": "007"}``
    The block's original passthrough: run one statement/script, optionally
    fetch rows, optionally record it as a migration.
``{"bootstrap_role": true}``
    Run only the role-membership bootstrap described below.

Role bootstrap
--------------
``002_rls.sql`` creates ``compass_app`` as a ``NOLOGIN`` role and grants it
table privileges, but nothing makes the *login* user a member of it — and
without membership every application Lambda's ``SET ROLE compass_app`` fails.
After a successful ``migrate: all`` this handler runs
``GRANT compass_app TO CURRENT_USER`` (idempotent). It is reported in the
result as ``role_bootstrap`` and a failure is surfaced as a warning rather
than failing the migration, so the operator sees exactly what happened. Set
``BOOTSTRAP_APP_ROLE=false`` to skip it.

Environment
-----------
DB_HOST / DB_NAME / DB_SECRET_ARN / DB_SCHEMA  (compass_common.config contract)
MIGRATIONS_DIR       Explicit migrations root, checked first.
BOOTSTRAP_APP_ROLE   "true"/"false".                        default "true"

Dependency injection: ``handler(event, context, connect=..., secret_loader=...)``
takes the same fakes as the block, so the whole flow can be exercised with no
network, AWS, or database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from compass_common import config

APP_ROLE = config.APP_ROLE  # "compass_app"


# --------------------------------------------------------------------------- #
# Connection (owner role — see the module docstring)
# --------------------------------------------------------------------------- #
def _default_secret_loader() -> dict:
    import boto3

    resp = boto3.client(
        "secretsmanager", region_name=config.aws_region()
    ).get_secret_value(SecretId=config.db_secret_arn())
    return json.loads(resp["SecretString"])


def _default_connect(secret: dict):
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


def _open(connect, secret_loader, schema: str):
    """Connect, autocommit on, ``search_path`` pinned to the Compass schema.

    ``search_path`` is set with ``psycopg2.sql`` identifier quoting (``SET``
    cannot be parameterized) so unqualified DDL in the migration files lands in
    ``compass``, never ``public``. Note ``001_schema.sql`` creates the schema
    itself, so the very first run sets a search_path whose first entry does not
    exist yet — Postgres tolerates that and resolves it once the schema exists.
    """
    from psycopg2 import sql

    conn = connect(secret_loader())
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema))
        )
    return conn


# --------------------------------------------------------------------------- #
# Migration discovery
# --------------------------------------------------------------------------- #
def candidate_roots() -> List[Path]:
    """Ordered places a bundled/derivable ``db/migrations`` may live.

    In Lambda the SQL must be inside the function package (``CodeUri`` is
    ``src/functions/migrator/``), so a deploy step copies ``db/migrations`` to
    ``src/functions/migrator/migrations``. Running locally (tests, a container
    with the repo mounted) the walk-up finds the repo's ``db/migrations``
    directly, which is why the same event works in both places.
    """
    roots: List[Path] = []
    env_dir = os.environ.get("MIGRATIONS_DIR")
    if env_dir:
        roots.append(Path(env_dir))
    task_root = os.environ.get("LAMBDA_TASK_ROOT")
    if task_root:
        roots.append(Path(task_root) / "migrations")
        roots.append(Path(task_root) / "db" / "migrations")
    here = Path(__file__).resolve().parent
    roots.append(here / "migrations")
    for parent in here.parents:
        roots.append(parent / "db" / "migrations")
    return roots


def find_migrations_root() -> Optional[Path]:
    for root in candidate_roots():
        try:
            if root.is_dir() and any(root.rglob("*.sql")):
                return root
        except OSError:
            continue
    return None


def load_migrations(root: Path) -> List[Dict[str, str]]:
    """Read every ``*.sql`` under ``root`` recursively, sorted by relative path.

    Sorting on the relative path keeps the numeric prefixes (``001_``, ``002_``)
    authoritative and makes nested directories deterministic.
    """
    files = sorted(root.rglob("*.sql"), key=lambda p: str(p.relative_to(root)))
    return [
        {"name": p.stem, "sql": p.read_text(encoding="utf-8"), "path": str(p)}
        for p in files
    ]


# --------------------------------------------------------------------------- #
# Applying
# --------------------------------------------------------------------------- #
def _applied_names(cur) -> set:
    """Names already in ``_schema_migrations`` (empty before 001 creates it)."""
    import psycopg2

    try:
        cur.execute("SELECT name FROM _schema_migrations")
        return {row[0] for row in cur.fetchall()}
    except psycopg2.Error:
        cur.connection.rollback()
        return set()


def _record(cur, name: str) -> bool:
    import psycopg2

    try:
        cur.execute(
            "INSERT INTO _schema_migrations (name, applied_at) VALUES (%s, now()) "
            "ON CONFLICT (name) DO NOTHING",
            (name,),
        )
        return True
    except psycopg2.Error:
        # The migration that creates _schema_migrations must run first; a
        # follow-up call records it.
        cur.connection.rollback()
        return False


def bootstrap_app_role(cur) -> Dict[str, Any]:
    """Make the login user a member of ``compass_app`` (idempotent).

    Without this, ``compass_common.db``'s ``SET ROLE compass_app`` fails and
    every application Lambda is dead on arrival — see the module docstring.
    """
    from psycopg2 import sql

    try:
        cur.execute(
            sql.SQL("GRANT {} TO CURRENT_USER").format(sql.Identifier(APP_ROLE))
        )
        return {"status": "granted", "role": APP_ROLE}
    except Exception as exc:  # noqa: BLE001 — reported, never fatal
        cur.connection.rollback()
        return {"status": "warning", "role": APP_ROLE, "error": str(exc)}


def apply_migrations(
    conn, migrations: List[Dict[str, str]], *, force: bool = False
) -> Tuple[List[Dict[str, Any]], int]:
    """Apply each migration in order; return (per-file results, applied count)."""
    results: List[Dict[str, Any]] = []
    applied = 0
    with conn.cursor() as cur:
        already = _applied_names(cur)
        for mig in migrations:
            name = mig["name"]
            if name in already and not force:
                results.append({"name": name, "status": "skipped", "reason": "already recorded"})
                continue
            cur.execute(mig["sql"])
            recorded = _record(cur, name)
            applied += 1
            results.append(
                {
                    "name": name,
                    "status": "applied",
                    "rowcount": cur.rowcount,
                    "recorded": recorded,
                }
            )
        # 001 creates _schema_migrations, so names that could not be recorded
        # on their own pass are recorded now that the table exists.
        for r in results:
            if r.get("status") == "applied" and r.get("recorded") is False:
                r["recorded"] = _record(cur, r["name"])
    return results, applied


# --------------------------------------------------------------------------- #
# Handler
# --------------------------------------------------------------------------- #
def handler(
    event,
    context=None,
    connect: Optional[Callable[[dict], Any]] = None,
    secret_loader: Optional[Callable[[], dict]] = None,
):
    event = event or {}
    connect = connect or _default_connect
    secret_loader = secret_loader or _default_secret_loader
    schema = config.db_schema()

    conn = _open(connect, secret_loader, schema)
    try:
        if event.get("bootstrap_role") and not event.get("migrate"):
            with conn.cursor() as cur:
                out = {"status": "ok", "role_bootstrap": bootstrap_app_role(cur)}
            print(json.dumps({"event_type": "migrator_complete", **out}))
            return out

        if event.get("migrate") == "all":
            migrations = event.get("migrations")
            source = "event"
            if not migrations:
                root = find_migrations_root()
                if root is None:
                    raise FileNotFoundError(
                        "no migrations found. Bundle db/migrations into the function "
                        "package (src/functions/migrator/migrations/), set "
                        "MIGRATIONS_DIR, or pass "
                        '{"migrate":"all","migrations":[{"name":...,"sql":...}]}. '
                        f"Searched: {[str(p) for p in candidate_roots()]}"
                    )
                migrations = load_migrations(root)
                source = str(root)
            results, applied = apply_migrations(
                conn, migrations, force=bool(event.get("force"))
            )
            out: Dict[str, Any] = {
                "status": "ok",
                "source": source,
                "schema": schema,
                "applied": applied,
                "total": len(migrations),
                "migrations": results,
            }
            if os.environ.get("BOOTSTRAP_APP_ROLE", "true").lower() != "false":
                with conn.cursor() as cur:
                    out["role_bootstrap"] = bootstrap_app_role(cur)
            print(json.dumps({"event_type": "migrator_complete", **out}, default=str))
            return out

        # --- passthrough (the block's original single-statement mode) -------
        sql_text = event.get("sql")
        if not sql_text:
            raise ValueError(
                'event must include "sql", {"migrate":"all"}, or {"bootstrap_role":true}'
            )
        fetch = event.get("fetch")
        migration_name = event.get("migration_name")
        with conn.cursor() as cur:
            cur.execute(sql_text)
            rowcount = cur.rowcount
            rows = None
            if fetch == "all":
                rows = cur.fetchall()
            elif fetch == "one":
                rows = cur.fetchone()
            recorded = _record(cur, migration_name) if migration_name else None

        out = {"status": "ok", "rowcount": rowcount, "schema": schema}
        if rows is not None:
            out["rows"] = (
                [list(r) for r in rows] if fetch == "all" else (list(rows) if rows else None)
            )
        if migration_name:
            out["migration_recorded"] = recorded
        print(json.dumps({"event_type": "migrator_complete", **out}, default=str))
        return out
    finally:
        conn.close()

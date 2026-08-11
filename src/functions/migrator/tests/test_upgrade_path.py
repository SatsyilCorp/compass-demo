"""Offline migration-order tests for already-deployed Compass stacks."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[4]
MIGRATOR_DIR = ROOT / "src" / "functions" / "migrator"
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))
sys.path.insert(0, str(MIGRATOR_DIR))

os.environ.setdefault("DB_HOST", "fake")
os.environ.setdefault("DB_NAME", "fake")
os.environ.setdefault("DB_SECRET_ARN", "fake")

APP_SPEC = importlib.util.spec_from_file_location(
    "compass_migrator_app",
    MIGRATOR_DIR / "app.py",
)
assert APP_SPEC and APP_SPEC.loader
app = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_SPEC.name] = app
APP_SPEC.loader.exec_module(app)


class FakePsycopgError(Exception):
    pass


class Cursor:
    def __init__(self, applied: set[str]):
        self.applied = applied
        self.rows: list[tuple[str]] = []
        self.scripts: list[str] = []
        self.rowcount = 0
        self.connection = self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        text = str(query)
        if text.startswith("SELECT name FROM _schema_migrations"):
            self.rows = [(name,) for name in sorted(self.applied)]
            return
        if text.startswith("INSERT INTO _schema_migrations") and params:
            self.applied.add(params[0])
            self.rowcount = 1
            return
        self.scripts.append(text)
        self.rowcount = 0

    def fetchall(self):
        return self.rows

    def rollback(self):
        raise AssertionError("upgrade path must not roll back")


class Connection:
    def __init__(self, applied: set[str]):
        self.cursor_instance = Cursor(applied)

    def cursor(self):
        return self.cursor_instance


def test_stack_with_003_recorded_still_applies_004(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "psycopg2",
        SimpleNamespace(Error=FakePsycopgError),
    )
    migrations = app.load_migrations(ROOT / "db" / "migrations")
    conn = Connection(
        {
            "001_schema",
            "002_rls",
            "003_security_hardening",
        }
    )

    results, applied_count = app.apply_migrations(conn, migrations)

    by_name = {item["name"]: item for item in results}
    assert by_name["003_security_hardening"]["status"] == "skipped"
    assert by_name["004_opaque_approval_capability"]["status"] == "applied"
    assert applied_count == 1
    assert len(conn.cursor_instance.scripts) == 1
    assert "ADD COLUMN IF NOT EXISTS capability_hash TEXT" in conn.cursor_instance.scripts[0]
    assert "GRANT UPDATE (capability_hash)" in conn.cursor_instance.scripts[0]
    assert "004_opaque_approval_capability" in conn.cursor_instance.applied

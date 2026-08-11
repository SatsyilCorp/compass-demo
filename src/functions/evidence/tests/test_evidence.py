"""Offline contract checks for the sanitized System Inspector endpoint."""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))
sys.path.insert(0, str(ROOT / "src" / "functions" / "evidence"))

os.environ.setdefault("DB_HOST", "fake")
os.environ.setdefault("DB_NAME", "fake")
os.environ.setdefault("DB_SECRET_ARN", "fake")

APP_SPEC = importlib.util.spec_from_file_location(
    "compass_evidence_app",
    ROOT / "src" / "functions" / "evidence" / "app.py",
)
assert APP_SPEC is not None and APP_SPEC.loader is not None
app = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_SPEC.name] = app
APP_SPEC.loader.exec_module(app)


NOW = datetime(2026, 8, 10, 14, 30, tzinfo=timezone.utc)


class Cursor:
    def __init__(self):
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=None):
        self.query = str(query)

    def fetchall(self):
        if "WITH quality" in self.query:
            return [
                (
                    "run-safe",
                    "batch-safe",
                    NOW,
                    NOW,
                    98.5,
                    40,
                    {
                        "src-file": {"schema_variant": "canonical"},
                        "raw": {"rows": 40},
                        "quality-gate": {"decision": "pass"},
                        "curated": {"rows": 40},
                    },
                )
            ]
        if "FROM audit_log" in self.query:
            return [
                (
                    9,
                    "export_completed",
                    {
                        "row_count": 40,
                        "matched_rows": 400,
                        "max_rows": 250,
                        "format": "csv",
                        "subject_id": "exp-abc123def4567890",
                        "approval_id": 42,
                        "approval_used": True,
                        "approval": {"capability_hash": "must-not-leak"},
                        "actor_email": "must-not-leak@example.test",
                        "download_url": "must-not-leak",
                    },
                    NOW,
                )
            ]
        return []

    def fetchone(self):
        if "FROM model_runs" in self.query:
            return ("model-safe", "topic_model", {"topic_count": 4, "prompt": "secret"}, NOW)
        if "SELECT\n          (SELECT COUNT" in self.query:
            return (40, 1, 2, 1, 9)
        return None


class Connection:
    def __init__(self):
        self.cur = Cursor()

    def cursor(self):
        return self.cur


@contextmanager
def scoped(conn, org):
    assert org == "ONR-Corporate"
    yield conn


class Context:
    aws_request_id = "request-safe-123"


def event(group="compass-poweruser"):
    return {
        "requestContext": {
            "http": {"method": "GET", "path": "/system/evidence"},
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "user-safe",
                        "cognito:groups": f"[{group}]",
                    }
                }
            },
        }
    }


def test_poweruser_receives_sanitized_projection(monkeypatch):
    monkeypatch.setattr(app.db, "get_conn", lambda: Connection())
    monkeypatch.setattr(app.db, "set_org", scoped)
    response = app.handler(event(), Context())
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["mode"] == "live"
    assert body["identity_decision"]["scope"] == "corporate portfolio"
    assert body["recent_runs"][0]["outcome"] == "curated"
    assert body["recent_runs"][0]["stages"][4] == {
        "id": "persist",
        "label": "Curate",
        "status": "completed",
        "receipt": "40 curated rows persisted under row security",
    }
    assert body["recent_audit"][0]["detail"] == {
        "approval_id": 42,
        "matched_rows": 400,
        "max_rows": 250,
        "row_count": 40,
        "approval_used": True,
        "format": "csv",
        "subject_id": "exp-abc123def4567890",
    }
    encoded = json.dumps(body)
    for forbidden in (
        "actor_email",
        "download_url",
        "example.test",
        '"prompt":',
        "capability_hash",
        "must-not-leak",
    ):
        assert forbidden not in encoded


def test_viewer_is_denied_before_database_access(monkeypatch):
    called = False

    def get_conn():
        nonlocal called
        called = True

    monkeypatch.setattr(app.db, "get_conn", get_conn)
    response = app.handler(event("compass-viewer"), Context())
    assert response["statusCode"] == 403
    assert called is False


def test_anonymous_is_denied():
    response = app.handler({"requestContext": {"http": {"method": "GET"}}}, Context())
    assert response["statusCode"] == 401

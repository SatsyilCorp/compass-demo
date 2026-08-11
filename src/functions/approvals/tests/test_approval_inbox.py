"""Offline contract tests for the four-eyes approval inbox."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))
APP_DIR = ROOT / "src" / "functions" / "approvals"
sys.path.insert(0, str(APP_DIR))

os.environ.setdefault("DB_HOST", "fake")
os.environ.setdefault("DB_NAME", "fake")
os.environ.setdefault("DB_SECRET_ARN", "fake")

APP_SPEC = importlib.util.spec_from_file_location(
    "compass_approvals_app",
    APP_DIR / "app.py",
)
assert APP_SPEC and APP_SPEC.loader
app = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_SPEC.name] = app
APP_SPEC.loader.exec_module(app)


CREATED_AT = datetime(2026, 8, 10, 14, 0, tzinfo=timezone.utc)


def approval_row(requested_by: str = "requester-123") -> tuple:
    return (
        42,
        "export",
        "exp-0123456789abcdef",
        "pending",
        requested_by,
        None,
        None,
        "Release sanitized portfolio",
        CREATED_AT,
        None,
        None,
        None,
    )


class Cursor:
    def __init__(self, rows: list[tuple]):
        self.rows = rows
        self.executed: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows: list[tuple]):
        self.cursor_instance = Cursor(rows)

    def cursor(self):
        return self.cursor_instance


class DecisionCursor:
    def __init__(self):
        self.result = None
        self.executed: list[tuple[str, object]] = []
        self.update_params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        text = " ".join(str(query).split())
        self.executed.append((text, params))
        if text.startswith("SELECT id, subject_type"):
            self.result = approval_row()
            return
        if text.startswith("UPDATE approvals SET state"):
            self.update_params = params
            state, actor, note, _, ttl_seconds, _, _ = params
            self.result = (
                42,
                "export",
                "exp-0123456789abcdef",
                state,
                "requester-123",
                actor,
                CREATED_AT,
                note,
                CREATED_AT,
                CREATED_AT + timedelta(seconds=ttl_seconds) if state == "approved" else None,
                None,
                None,
            )

    def fetchone(self):
        return self.result


class DecisionConnection:
    def __init__(self):
        self.cursor_instance = DecisionCursor()

    def cursor(self):
        return self.cursor_instance


def test_viewer_inbox_binds_actor_and_never_returns_tokens():
    conn = Connection([approval_row()])
    body = app.list_pending_approvals(
        conn,
        actor="requester-123",
        role="viewer",
    )

    query, params = conn.cursor_instance.executed[0]
    assert "requested_by = %s" in query
    assert params == ("pending", "requester-123", app.APPROVAL_LIST_LIMIT)
    assert body["scope"] == "requested_by_actor"
    assert body["can_decide"] is False
    assert body["tokens_included"] is False
    assert body["approvals"][0]["subject_id"] == "exp-0123456789abcdef"
    assert "approval_token" not in json.dumps(body)


def test_poweruser_inbox_reads_shared_pending_queue_without_actor_predicate():
    conn = Connection([approval_row("requester-123"), approval_row("requester-456")])
    body = app.list_pending_approvals(
        conn,
        actor="reviewer-789",
        role="poweruser",
    )

    query, params = conn.cursor_instance.executed[0]
    assert "requested_by = %s" not in query
    assert params == ("pending", app.APPROVAL_LIST_LIMIT)
    assert body["scope"] == "all_pending"
    assert body["can_decide"] is True
    assert len(body["approvals"]) == 2


def request_event(group: str, path: str) -> dict:
    return {
        "requestContext": {
            "http": {"method": "GET", "path": path},
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "requester-123",
                        "cognito:groups": f"[{group}]",
                    }
                }
            },
        }
    }


@contextmanager
def scoped(conn, org_unit):
    assert org_unit in {"Code-30", "ONR-Corporate"}
    yield conn


def test_get_approvals_routes_to_inbox_not_anomalies(monkeypatch):
    conn = Connection([approval_row()])
    anomaly_called = False

    def anomaly_probe(*_args, **_kwargs):
        nonlocal anomaly_called
        anomaly_called = True
        return {"anomalies": []}

    monkeypatch.setattr(app.db, "get_conn", lambda: conn)
    monkeypatch.setattr(app.db, "set_org", scoped)
    monkeypatch.setattr(app, "list_anomalies", anomaly_probe)

    response = app.handler(
        request_event("compass-viewer", "/approvals"),
        None,
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert anomaly_called is False
    assert body["actor"] == "requester-123"
    assert body["approvals"][0]["requested_by"] == "requester-123"


def test_unknown_get_path_fails_closed_before_database_access(monkeypatch):
    database_called = False

    def fail_if_called():
        nonlocal database_called
        database_called = True
        raise AssertionError("database must not be reached")

    monkeypatch.setattr(app.db, "get_conn", fail_if_called)
    response = app.handler(
        request_event("compass-poweruser", "/not-approvals"),
        None,
    )

    assert response["statusCode"] == 404
    assert database_called is False


def test_approve_returns_opaque_token_once_and_stores_only_sha256(monkeypatch):
    secret = "S" * 43
    audit_details: list[dict] = []
    conn = DecisionConnection()

    monkeypatch.setattr(app.secrets, "token_urlsafe", lambda byte_count: secret)
    monkeypatch.setattr(
        app.audit,
        "write_audit",
        lambda _conn, **kwargs: audit_details.append(kwargs["detail"]) or 1,
    )

    result = app.create_or_advance(
        conn,
        {
            "subject_type": "export",
            "subject_id": "exp-0123456789abcdef",
            "action": "approve",
            "note": "Independent release review",
        },
        actor="reviewer-789",
        role="poweruser",
    )

    token = result["body"]["approval_token"]
    assert token == f"apr-42.{secret}"
    assert result["body"]["approval"]["decided_by"] == "reviewer-789"
    assert conn.cursor_instance.update_params[5] == app.capability_digest(secret)
    assert secret not in json.dumps(conn.cursor_instance.executed, default=str)
    assert secret not in json.dumps(audit_details, default=str)
    assert audit_details[-1]["token_issued"] is True


def test_reject_never_generates_or_stores_a_capability(monkeypatch):
    conn = DecisionConnection()

    def fail_if_called(_byte_count):
        raise AssertionError("reject must not generate a capability secret")

    monkeypatch.setattr(app.secrets, "token_urlsafe", fail_if_called)
    monkeypatch.setattr(app.audit, "write_audit", lambda *_args, **_kwargs: 1)
    result = app.create_or_advance(
        conn,
        {
            "subject_type": "export",
            "subject_id": "exp-0123456789abcdef",
            "action": "reject",
        },
        actor="reviewer-789",
        role="poweruser",
    )

    assert result["body"]["approval_token"] is None
    assert conn.cursor_instance.update_params[5] is None


def test_viewer_anomaly_queue_excludes_unbound_global_findings():
    conn = Connection([])
    app.list_anomalies(conn, {}, include_unbound=False)
    query, _ = conn.cursor_instance.executed[0]
    assert "g.id IS NOT NULL" in query
    assert "a.grant_id IS NULL" not in query


def test_corporate_anomaly_queue_can_include_unbound_findings():
    conn = Connection([])
    app.list_anomalies(conn, {}, include_unbound=True)
    query, _ = conn.cursor_instance.executed[0]
    assert "a.grant_id IS NULL OR g.id IS NOT NULL" in query

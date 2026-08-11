"""Offline security and query contract tests for GET /dashboard."""
from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))
sys.path.insert(0, str(ROOT / "src" / "functions" / "dashboard"))

os.environ.setdefault("DB_HOST", "fake")
os.environ.setdefault("DB_NAME", "fake")
os.environ.setdefault("DB_SECRET_ARN", "fake")

APP_SPEC = importlib.util.spec_from_file_location(
    "compass_dashboard_app",
    ROOT / "src" / "functions" / "dashboard" / "app.py",
)
assert APP_SPEC is not None and APP_SPEC.loader is not None
app = importlib.util.module_from_spec(APP_SPEC)
sys.modules[APP_SPEC.name] = app
APP_SPEC.loader.exec_module(app)


class Context:
    function_name = "dashboard-test"
    aws_request_id = "request-test"


def request_event(
    group: str,
    params: dict[str, str] | None = None,
) -> dict:
    return {
        "requestContext": {
            "http": {"method": "GET", "path": "/dashboard"},
            "authorizer": {
                "jwt": {"claims": {"sub": "test-user", "cognito:groups": f"[{group}]"}}
            },
        },
        "queryStringParameters": params or {},
    }


def test_filter_values_are_bound_and_like_wildcards_are_literal():
    attack = "Cyber' OR TRUE --"
    filters = app._parse_filters(
        {
            "program_area": attack,
            "fiscal_year": "2026",
            "org_unit": "Code-30",
            "q": r"100%_ready\path",
        }
    )
    sql, params = app._grant_where(filters)

    assert attack not in sql
    assert "Code-30" not in sql
    assert "100%" not in sql
    assert sql.count("%s") == len(params)
    assert params[:3] == (attack, 2026, "Code-30")
    assert params[3:] == (r"%100\%\_ready\\path%",) * 4


def test_cache_key_changes_for_each_filter_dimension():
    base = app._cache_key(
        "ONR-Corporate",
        True,
        app.DashboardFilters(),
        "reviewer-123",
    )
    candidates = [
        app.DashboardFilters(program_area="Autonomous Systems"),
        app.DashboardFilters(fiscal_year=2026),
        app.DashboardFilters(org_unit="Code-30"),
        app.DashboardFilters(q="autonomy"),
    ]
    keys = [
        app._cache_key("ONR-Corporate", True, item, "reviewer-123")
        for item in candidates
    ]
    assert base not in keys
    assert len(set(keys)) == len(keys)


def test_cache_key_separates_viewers_in_the_same_org():
    filters = app.DashboardFilters()
    first = app._cache_key("Code-30", False, filters, "requester-123")
    second = app._cache_key("Code-30", False, filters, "requester-456")
    assert first != second


def test_filter_options_do_not_include_request_predicates():
    class Cursor:
        def __init__(self):
            self.queries: list[tuple[str, object]] = []
            self.responses = [
                [("Autonomous Systems",), ("Undersea Warfare",)],
                [(2026,), (2025,)],
                [("Code-30",), ("Code-31",)],
            ]

        def execute(self, query, params=None):
            self.queries.append((str(query), params))

        def fetchall(self):
            return self.responses.pop(0)

    cursor = Cursor()
    options = app._filter_options(cursor)
    assert options == {
        "program_areas": ["Autonomous Systems", "Undersea Warfare"],
        "fiscal_years": [2026, 2025],
        "org_units": ["Code-30", "Code-31"],
    }
    assert len(cursor.queries) == 3
    assert all(params is None for _, params in cursor.queries)
    assert all("WHERE" not in sql.upper() for sql, _ in cursor.queries)


def test_viewer_cannot_widen_org_scope_before_database_access(monkeypatch):
    database_called = False

    def fail_if_called():
        nonlocal database_called
        database_called = True
        raise AssertionError("database must not be reached")

    monkeypatch.setattr(app.db, "get_conn", fail_if_called)
    response = app.handler(
        request_event("compass-viewer", {"org_unit": "Code-31"}),
        Context(),
    )

    assert response["statusCode"] == 403
    assert database_called is False
    assert "exceeds" in json.loads(response["body"])["error"]


def test_invalid_filter_is_rejected_before_database_access(monkeypatch):
    database_called = False

    def fail_if_called():
        nonlocal database_called
        database_called = True
        raise AssertionError("database must not be reached")

    monkeypatch.setattr(app.db, "get_conn", fail_if_called)
    response = app.handler(
        request_event("compass-poweruser", {"fiscal_year": "2026 OR 1=1"}),
        Context(),
    )

    assert response["statusCode"] == 400
    assert database_called is False


class ProjectionCursor:
    def __init__(self, *, one=(0,), many=None):
        self.queries: list[tuple[str, object]] = []
        self.one = one
        self.many = many or []

    def execute(self, query, params=None):
        self.queries.append((" ".join(str(query).split()), params))

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


def test_quality_projection_is_rls_scoped_even_without_filters():
    cursor = ProjectionCursor(many=[])
    assert app._quality_trend(cursor, app.DashboardFilters()) == []

    query, params = cursor.queries[0]
    assert "WHERE EXISTS" in query
    assert "FROM grants_curated AS g" in query
    assert "g.batch_id = q.batch_id" in query
    assert params == ()


def test_corporate_quality_projection_includes_terminal_quarantine_receipts():
    cursor = ProjectionCursor(many=[])
    assert (
        app._quality_trend_for_scope(
            cursor,
            app.DashboardFilters(),
            is_corporate=True,
        )
        == []
    )

    query, params = cursor.queries[0]
    assert "terminal.node_id = 'quarantine'" in query
    assert "FROM grants_raw AS r" in query
    assert params == ()


def test_latest_topic_run_is_selected_only_from_visible_grants():
    cursor = ProjectionCursor(one=None)
    assert app._top_topics(cursor, app.DashboardFilters()) == []

    query, params = cursor.queries[0]
    assert "EXISTS" in query
    assert "JOIN grants_curated AS g" in query
    assert "visible_gt.run_id = mr.run_id" in query
    assert params == ("topic_model",)


def test_viewer_anomaly_count_excludes_unbound_global_findings():
    cursor = ProjectionCursor(one=(3,))
    assert (
        app._open_anomalies_count(
            cursor,
            app.DashboardFilters(),
            is_corporate=False,
        )
        == 3
    )

    query, params = cursor.queries[0]
    assert "EXISTS" in query
    assert "g.id = a.grant_id" in query
    assert "a.grant_id IS NULL" not in query
    assert params == ("open",)


def test_corporate_anomaly_count_can_include_unbound_findings_without_filters():
    cursor = ProjectionCursor(one=(8,))
    assert (
        app._open_anomalies_count(
            cursor,
            app.DashboardFilters(),
            is_corporate=True,
        )
        == 8
    )
    query, _ = cursor.queries[0]
    assert "a.grant_id IS NULL" in query


def test_pending_approval_count_is_actor_bound_for_viewers():
    cursor = ProjectionCursor(one=(1,))
    assert (
        app._pending_approvals_count(
            cursor,
            is_corporate=False,
            actor="requester-123",
        )
        == 1
    )
    query, params = cursor.queries[0]
    assert "requested_by = %s" in query
    assert params == ("pending", "requester-123")


def test_pending_approval_count_is_shared_only_for_corporate_reviewers():
    cursor = ProjectionCursor(one=(4,))
    assert (
        app._pending_approvals_count(
            cursor,
            is_corporate=True,
            actor="reviewer-123",
        )
        == 4
    )
    query, params = cursor.queries[0]
    assert "requested_by" not in query
    assert params == ("pending",)

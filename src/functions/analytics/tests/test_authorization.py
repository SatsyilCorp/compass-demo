"""Authorization regression tests for every analytics handler branch."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


FUNCTION_DIR = Path(__file__).resolve().parents[1]
if str(FUNCTION_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTION_DIR))

SPEC = importlib.util.spec_from_file_location(
    "compass_analytics_authorization_app",
    FUNCTION_DIR / "app.py",
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


def _event(method: str, role: str, org_unit: str, run_id: str | None = None):
    return {
        "requestContext": {
            "http": {"method": method, "path": "/analytics/run"},
            "authorizer": {
                "lambda": {
                    "sub": "authorization-test",
                    "role": role,
                    "org_unit": org_unit,
                }
            },
        },
        "pathParameters": {"run_id": run_id} if run_id else None,
    }


def test_viewer_cannot_start_or_read_shared_analytics(monkeypatch):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("analytics implementation ran before authorization")

    monkeypatch.setattr(app, "_run_analytics", unexpected)
    monkeypatch.setattr(app, "_get_run", unexpected)

    for event in (
        _event("POST", "viewer", "Code-30"),
        _event("GET", "viewer", "Code-30", "tm-test"),
    ):
        response = app.handler(event, None)
        assert response["statusCode"] == 403


def test_noncorporate_poweruser_alias_fails_closed(monkeypatch):
    monkeypatch.setattr(
        app,
        "_get_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("noncorporate request reached analytics read")
        ),
    )
    response = app.handler(
        _event("GET", "poweruser", "Code-30", "tm-test"),
        None,
    )
    assert response["statusCode"] == 401

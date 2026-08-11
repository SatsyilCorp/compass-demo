"""The direct baseline action is bounded and uses an honest service actor."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


FUNCTION_DIR = Path(__file__).resolve().parents[1]
if str(FUNCTION_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTION_DIR))

SPEC = importlib.util.spec_from_file_location(
    "compass_analytics_demo_preparation_app",
    FUNCTION_DIR / "app.py",
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


def test_direct_baseline_action_uses_fixed_service_actor(monkeypatch):
    captured = {}

    def run(event, claims):
        captured["event"] = event
        captured["claims"] = claims
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "completed",
                    "run_id": "tm-demo",
                    "metrics": {"n_docs": 400, "k": 8},
                }
            ),
        }

    monkeypatch.setattr(app, "_run_analytics", run)
    response = app.handler(
        {"action": app.DEMO_BASELINE_ACTION, "k": 8, "seed": 20260810},
        None,
    )

    assert response["status"] == "ok"
    assert captured["claims"].username == "compass-demo-preparer"
    assert captured["claims"].org_unit == "ONR-Corporate"
    assert "requestContext" not in captured["event"]


def test_direct_baseline_action_rejects_parameter_drift(monkeypatch):
    monkeypatch.setattr(
        app,
        "_run_analytics",
        lambda *_args: (_ for _ in ()).throw(AssertionError("model should not run")),
    )
    for event in (
        {"action": app.DEMO_BASELINE_ACTION, "k": 7, "seed": 20260810},
        {"action": app.DEMO_BASELINE_ACTION, "k": 8, "seed": 1},
    ):
        response = app.handler(event, None)
        assert response == {"status": "error", "code": "invalid_baseline_parameters"}

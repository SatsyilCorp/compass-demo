from __future__ import annotations

import json
import os
import sys
import importlib.util
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))

os.environ.setdefault("OPERATIONS_TABLE", "test")
SPEC = importlib.util.spec_from_file_location(
    "compass_operations_app", ROOT / "src" / "functions" / "operations" / "app.py"
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class KeyExpr:
    def eq(self, value):
        return value


class Table:
    def __init__(self):
        self.signal = {
            "pk": "SIGNAL#sig-safe",
            "sk": "STATE",
            "gsi1pk": "SIGNAL",
            "gsi1sk": "2026-08-12#sig-safe",
            "event_id": "sig-safe",
            "severity": "high",
            "status": "open",
            "title": "Quality gate blocked publication",
        }
        self.stages = [
            {
                "pk": "RUN#doc-safe",
                "sk": "STAGE#001#source",
                "gsi1pk": "LINEAGE",
                "gsi1sk": "2026-08-12#doc-safe#001",
                "run_id": "doc-safe",
                "run_kind": "document-intake",
                "sequence": Decimal("1"),
                "stage_id": "source",
                "status": "completed",
                "source": "document-lake://documents/incoming/doc-safe/report.txt",
                "source_sha256": "a" * 64,
                "updated_at": "2026-08-12T12:00:00+00:00",
            },
            {
                "pk": "RUN#doc-safe",
                "sk": "STAGE#002#gold",
                "gsi1pk": "LINEAGE",
                "gsi1sk": "2026-08-12#doc-safe#002",
                "run_id": "doc-safe",
                "run_kind": "document-intake",
                "sequence": Decimal("2"),
                "stage_id": "gold",
                "status": "completed",
                "detail": {"consumer": "decision workspace", "model_version": "m-1"},
                "updated_at": "2026-08-12T12:00:01+00:00",
            },
        ]
        self.acquisitions = []

    def query(self, **kwargs):
        value = kwargs["KeyConditionExpression"]
        if value == "SIGNAL":
            return {"Items": [self.signal]}
        if value == "LINEAGE":
            return {"Items": list(reversed(self.stages))}
        if value == "ACQUISITION":
            return {"Items": self.acquisitions}
        if value == "RUN#doc-safe":
            return {"Items": self.stages}
        return {"Items": []}

    def update_item(self, **kwargs):
        self.signal.update(
            {
                "status": "acknowledged",
                "acknowledged_at": kwargs["ExpressionAttributeValues"][":at"],
            }
        )
        return {"Attributes": self.signal}


def event(method: str, path: str, role: str = "poweruser"):
    return {
        "requestContext": {
            "http": {"method": method, "path": path},
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "user-safe",
                        "username": "presenter-safe",
                        "cognito:groups": f"[compass-{role}]",
                    }
                }
            },
        }
    }


def test_lineage_returns_directed_server_receipts(monkeypatch):
    table = Table()
    monkeypatch.setattr(app, "_TABLE", table)
    monkeypatch.setattr(app, "_key", lambda _name: KeyExpr())
    response = app.handler(event("GET", "/operations/lineage/doc-safe"))
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["source_sha256"] == "a" * 64
    assert body["model"] == "m-1"
    assert body["edges"] == [{"from": "source", "to": "gold"}]
    assert "pk" not in response["body"]


def test_signal_acknowledgement_is_protected(monkeypatch):
    table = Table()
    monkeypatch.setattr(app, "_TABLE", table)
    response = app.handler(
        event("POST", "/operations/signals/sig-safe/acknowledge")
    )
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "acknowledged"
    denied = app.handler(event("GET", "/operations/signals", role="viewer"))
    assert denied["statusCode"] == 403


def test_summary_preserves_last_accepted_snapshot_after_failed_attempt(monkeypatch):
    table = Table()
    table.acquisitions = [
        {
            "run_id": "acq-failed",
            "source_id": "usaspending-awards",
            "status": "failed",
            "started_at": "2026-08-12T12:05:00+00:00",
        },
        {
            "run_id": "acq-accepted",
            "source_id": "usaspending-awards",
            "status": "completed",
            "started_at": "2026-08-12T12:00:00+00:00",
            "updated_at": "2026-08-12T12:00:01+00:00",
            "watermark": "2026-08-12T12:00:00+00:00",
            "added_records": 10,
        },
    ]
    monkeypatch.setattr(app, "_TABLE", table)
    monkeypatch.setattr(app, "_key", lambda _name: KeyExpr())

    response = app.handler(event("GET", "/operations/summary"))
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["latest_public_acquisition"]["run_id"] == "acq-accepted"
    assert body["latest_public_acquisition_attempt"]["run_id"] == "acq-failed"
    assert body["latest_public_acquisition"]["watermark"] == "2026-08-12T12:00:00+00:00"

"""Kinesis ticker scope and recency regression tests."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


FUNCTION_DIR = Path(__file__).resolve().parents[1]
if str(FUNCTION_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTION_DIR))

SPEC = importlib.util.spec_from_file_location(
    "compass_intake_stream_scope_app",
    FUNCTION_DIR / "app.py",
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class FakeKinesis:
    def __init__(self):
        self.iterator_request = None

    def list_shards(self, **_kwargs):
        return {"Shards": [{"ShardId": "shard-1"}]}

    def get_shard_iterator(self, **kwargs):
        self.iterator_request = kwargs
        return {"ShardIterator": "page-1"}

    def get_records(self, **_kwargs):
        records = [
            {"id": "same", "org_unit": "Code-30", "at": "2026-08-10T13:00:03Z"},
            {"id": "other", "org_unit": "Code-31", "at": "2026-08-10T13:00:02Z"},
            {"id": "unbound", "org_unit": None, "at": "2026-08-10T13:00:01Z"},
        ]
        return {
            "Records": [
                {"Data": json.dumps(record).encode("utf-8")}
                for record in records
            ],
            "NextShardIterator": None,
        }


def test_unit_viewer_only_receives_exact_scope_from_recent_stream(monkeypatch):
    client = FakeKinesis()
    monkeypatch.setenv("STREAM_NAME", "contract-stream")
    monkeypatch.setattr(app, "_KINESIS", client)
    identity = app.Identity("viewer", "Code-30", "viewer", ["compass-viewer"])

    records = app._activity_from_kinesis(identity, 25)

    assert [record["id"] for record in records] == ["same"]
    assert client.iterator_request["ShardIteratorType"] == "AT_TIMESTAMP"
    assert "Timestamp" in client.iterator_request


def test_corporate_scope_can_read_bound_and_unbound_stream_records(monkeypatch):
    monkeypatch.setenv("STREAM_NAME", "contract-stream")
    monkeypatch.setattr(app, "_KINESIS", FakeKinesis())
    identity = app.Identity(
        "poweruser",
        "ONR-Corporate",
        "poweruser",
        ["compass-poweruser"],
    )

    records = app._activity_from_kinesis(identity, 25)

    assert {record["id"] for record in records} == {"same", "other", "unbound"}

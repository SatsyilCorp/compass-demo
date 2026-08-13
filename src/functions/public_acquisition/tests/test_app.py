from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))
os.environ.setdefault("OPERATIONS_TABLE", "test")
os.environ.setdefault("PUBLIC_ACQUISITION_BUCKET", "test-bucket")
os.environ.setdefault("STREAM_NAME", "test-stream")

SPEC = importlib.util.spec_from_file_location(
    "compass_public_acquisition_app",
    ROOT / "src" / "functions" / "public_acquisition" / "app.py",
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return json.dumps(self.value).encode()


class Table:
    def __init__(self):
        self.items = {}

    def get_item(self, *, Key, **_kwargs):
        return {"Item": self.items.get((Key["pk"], Key["sk"]))}

    def put_item(self, *, Item):
        self.items[(Item["pk"], Item["sk"])] = Item

    def query(self, **_kwargs):
        values = [
            item for item in self.items.values() if item.get("gsi1pk") == "ACQUISITION"
        ]
        return {"Items": values}


class S3:
    def __init__(self):
        self.objects = []

    def put_object(self, **kwargs):
        self.objects.append(kwargs)
        return {"VersionId": f"v{len(self.objects)}"}


class Kinesis:
    def __init__(self):
        self.records = []

    def put_records(self, **kwargs):
        self.records.extend(kwargs["Records"])
        return {"FailedRecordCount": 0}


def source_response(amount=120000, award_id="N00014-26-1-0001"):
    return {
        "results": [
            {
                "Award ID": award_id,
                "Start Date": "2026-01-10",
                "End Date": "2027-01-10",
                "Award Amount": amount,
                "Awarding Agency": "Department of Defense",
                "Awarding Sub Agency": "Department of the Navy",
                "Award Type": "PROJECT GRANT",
                "Description": "Autonomous maritime sensing research at analyst@example.com",
                "Recipient Name": "Example Research LLC",
            }
        ],
        "page_metadata": {"hasNext": False},
    }


def configure(monkeypatch, value):
    table, s3, stream = Table(), S3(), Kinesis()
    monkeypatch.setattr(app, "_TABLE", table)
    monkeypatch.setattr(app, "_S3", s3)
    monkeypatch.setattr(app, "_KINESIS", stream)
    monkeypatch.setattr(app, "_URL_OPEN", lambda *_args, **_kwargs: Response(value))
    monkeypatch.setattr(app.operational_evidence, "record_stage", lambda **_kwargs: True)
    monkeypatch.setattr(app.operational_evidence, "record_signal", lambda **_kwargs: "sig-safe")
    return table, s3, stream


def test_acquisition_persists_hashes_deltas_and_stream_event(monkeypatch):
    table, s3, stream = configure(monkeypatch, source_response())
    receipt = app.run_acquisition(actor="presenter")
    assert receipt["status"] == "completed"
    assert receipt["record_count"] == 1
    assert receipt["added_records"] == 1
    assert len(receipt["snapshot_sha256"]) == 64
    assert len(s3.objects) == 2
    assert all(
        item["Metadata"]["sha256"] == hashlib.sha256(item["Body"]).hexdigest()
        for item in s3.objects
    )
    assert s3.objects[1]["Metadata"]["snapshot-sha256"] == receipt["snapshot_sha256"]
    assert receipt["canonical_object_sha256"] == s3.objects[1]["Metadata"]["sha256"]
    assert len(stream.records) == 1
    stream_event = json.loads(stream.records[0]["Data"])
    assert stream_event["kind"] == "public-feed"
    assert stream_event["change_kind"] == "added"
    assert stream_event["grant_no"] == "N00014-26-1-0001"
    assert "Recipient Name" not in s3.objects[1]["Body"].decode()
    assert "analyst@example.com" not in s3.objects[1]["Body"].decode()
    alias = table.items[(f"ACQUISITION_ALIAS#{app.SOURCE_ID}", "STATE")]
    assert alias["run_id"] == receipt["run_id"]


def test_second_identical_snapshot_reports_unchanged(monkeypatch):
    table, _s3, stream = configure(monkeypatch, source_response())
    first = app.run_acquisition()
    second = app.run_acquisition()
    assert first["added_records"] == 1
    assert second["added_records"] == 0
    assert second["changed_records"] == 0
    assert second["unchanged_records"] == 1
    assert len(stream.records) == 1


def test_bounded_page_absence_is_not_reported_as_source_deletion(monkeypatch):
    _table, _s3, _stream = configure(monkeypatch, source_response())
    app.run_acquisition()
    monkeypatch.setattr(
        app,
        "_URL_OPEN",
        lambda *_args, **_kwargs: Response(source_response(award_id="N00014-26-1-0002")),
    )
    second = app.run_acquisition()
    assert second["not_observed_records"] == 1
    assert "removed_records" not in second


def test_failure_retains_a_sanitized_failure_receipt(monkeypatch):
    table, _s3, _stream = configure(monkeypatch, {})
    try:
        app.run_acquisition()
    except app.AcquisitionFailure:
        pass
    else:
        raise AssertionError("expected acquisition failure")
    failures = [
        item for item in table.items.values() if item.get("status") == "failed"
    ]
    assert len(failures) == 1
    assert "results" not in json.dumps(failures)

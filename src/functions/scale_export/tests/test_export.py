"""Focused evidence, ledger, cancellation, and SQS tests for Scale export."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[4]
COMMON = ROOT / "src" / "common" / "python"
APP_PATH = ROOT / "src" / "functions" / "scale_export" / "app.py"
sys.path.insert(0, str(COMMON))

SPEC = importlib.util.spec_from_file_location("scale_export_app", APP_PATH)
export_app = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = export_app
SPEC.loader.exec_module(export_app)


RUN_ID = "scale-20260811010101-a1b2c3d4e5"
EXPORT_ID = "export-0123456789abcdefabcd"


class FakeS3:
    def __init__(self):
        self.source = {
            f"parquet/grants/run_id={RUN_ID}/object-a.parquet": b"parquet-a",
            f"parquet/grants/run_id={RUN_ID}/object-b.parquet": b"parquet-b-data",
        }
        self.puts = []

    def list_objects_v2(self, **request):
        prefix = request["Prefix"]
        contents = [
            {"Key": key, "Size": len(value)}
            for key, value in self.source.items()
            if key.startswith(prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}

    def get_object(self, **request):
        key = request["Key"]
        if key in self.source:
            return {"Body": io.BytesIO(self.source[key])}
        for put in self.puts:
            if put["Key"] == key:
                return {"Body": io.BytesIO(put["Body"])}
        raise KeyError(key)

    def put_object(self, **request):
        self.puts.append(request)
        return {}


class FakeDdb:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.requests = []

    def transact_write_items(self, **request):
        self.requests.append(request)
        if self.error:
            raise self.error


def _run(status: str = "completed") -> dict:
    return {
        "run_id": RUN_ID,
        "status": status,
        "curated_records": 198,
        "manifest_sha256": "f" * 64,
    }


def _export(status: str = "building") -> dict:
    return {
        "run_id": RUN_ID,
        "export_id": EXPORT_ID,
        "status": status,
        "dataset": "grants",
        "format": "parquet",
        "created_at": "2026-08-11T01:00:00+00:00",
        "expires_at": "2026-08-12T01:00:00+00:00",
        "worker_request_id": "request-1",
    }


def test_artifact_hashes_every_object_and_exposes_only_logical_locators(
    monkeypatch,
):
    fake_s3 = FakeS3()
    monkeypatch.setenv("SCALE_LAKE_BUCKET", "physical-bucket-must-stay-private")
    monkeypatch.setattr(export_app, "_S3", fake_s3)
    monkeypatch.setattr(export_app, "_assert_active", lambda *args: None)
    monkeypatch.setattr(export_app, "_dataset_row_count", lambda *args: 198)

    artifact = export_app._build_artifact(_run(), _export(), "request-1")
    manifest = artifact.manifest
    assert manifest["row_count"] == 198
    assert manifest["bytes"] == len(b"parquet-a") + len(b"parquet-b-data")
    assert manifest["object_count"] == 2
    assert hashlib.sha256(artifact.encoded).hexdigest() == artifact.manifest_sha256
    assert artifact.object_uri.startswith("lake://scale-runs/")
    serialized = json.dumps(manifest, sort_keys=True)
    assert "physical-bucket-must-stay-private" not in serialized
    assert "object-a.parquet" not in serialized
    assert "object-b.parquet" not in serialized
    for item in manifest["objects"]:
        assert item["logical_locator"].startswith("lake://scale-runs/")
        expected = fake_s3.source[
            f"parquet/grants/run_id={RUN_ID}/"
            + ("object-a.parquet" if item["ordinal"] == 0 else "object-b.parquet")
        ]
        assert item["sha256"] == hashlib.sha256(expected).hexdigest()
    manifest_put = fake_s3.puts[0]
    assert manifest_put["IfNoneMatch"] == "*"
    assert manifest_put["Metadata"]["sha256"] == artifact.manifest_sha256


def test_completion_persists_exact_frontend_receipt_in_run_ledger(monkeypatch):
    fake_ddb = FakeDdb()
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(export_app, "_DDB", fake_ddb)
    monkeypatch.setattr(export_app, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(
        export_app, "_iso", lambda value=None: "2026-08-11T01:05:00+00:00"
    )
    artifact = export_app.ExportArtifact(
        manifest={},
        encoded=b"{}",
        manifest_sha256="a" * 64,
        manifest_key=f"exports/run_id={RUN_ID}/{EXPORT_ID}/manifest.json",
        row_count=198,
        byte_count=1234,
        object_count=2,
        object_uri=f"lake://scale-runs/{RUN_ID}/exports/{EXPORT_ID}/manifest",
    )

    receipt = export_app._commit(_run(), _export(), artifact, "request-1")
    assert set(receipt) == {
        "export_id",
        "status",
        "format",
        "row_count",
        "bytes",
        "object_uri",
        "download_url",
        "expires_at",
        "sha256",
    }
    assert receipt["status"] == "ready"
    assert receipt["download_url"] is None
    assert receipt["sha256"] == "a" * 64
    transaction = fake_ddb.requests[0]["TransactItems"]
    export_values = transaction[0]["Update"]["ExpressionAttributeValues"]
    run_values = transaction[1]["Update"]["ExpressionAttributeValues"]
    assert set(export_values) == {
        ":building",
        ":ready",
        ":worker",
        ":at",
        ":rows",
        ":bytes",
        ":uri",
        ":null",
        ":expires",
        ":sha",
        ":manifest_key",
        ":object_count",
        ":audit",
    }
    assert set(run_values) == {
        ":receipt",
        ":at",
        ":completed",
        ":completed_quarantine",
    }
    assert run_values[":receipt"] == receipt


def test_claim_uses_a_lease_and_exact_transaction_values(monkeypatch):
    fake_ddb = FakeDdb()
    items = iter([_run(), _export("queued")])
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(export_app, "_DDB", fake_ddb)
    monkeypatch.setattr(export_app, "_get_item", lambda key: next(items))
    monkeypatch.setattr(export_app, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(
        export_app, "_iso", lambda value=None: "2026-08-11T01:05:00+00:00"
    )
    monkeypatch.setattr(
        export_app,
        "_now",
        lambda: export_app.datetime(2026, 8, 11, 1, 5, tzinfo=export_app.timezone.utc),
    )

    claimed = export_app._claim(RUN_ID, EXPORT_ID, "request-1")
    assert claimed is not None
    transaction = fake_ddb.requests[0]["TransactItems"]
    export_values = transaction[0]["Update"]["ExpressionAttributeValues"]
    run_values = transaction[1]["Update"]["ExpressionAttributeValues"]
    assert set(export_values) == {
        ":queued",
        ":building",
        ":now_epoch",
        ":lease_epoch",
        ":at",
        ":request",
        ":one",
    }
    assert export_values[":lease_epoch"] - export_values[":now_epoch"] == 900
    assert set(run_values) == {
        ":receipt",
        ":at",
        ":completed",
        ":completed_quarantine",
    }
    assert set(run_values[":receipt"]) == {
        "export_id",
        "status",
        "format",
        "row_count",
        "bytes",
        "object_uri",
        "download_url",
        "expires_at",
        "sha256",
    }


def test_claim_stops_and_records_cancellation_before_object_access(monkeypatch):
    items = iter([_run("canceled"), _export("queued")])
    cancellations = []
    monkeypatch.setattr(export_app, "_get_item", lambda key: next(items))
    monkeypatch.setattr(
        export_app,
        "_mark_canceled",
        lambda run, export, reason: cancellations.append(reason),
    )

    with pytest.raises(export_app.ExportCanceled):
        export_app._claim(RUN_ID, EXPORT_ID, "request-1")
    assert cancellations == ["run_not_exportable"]


def test_immutable_manifest_retry_accepts_identical_bytes_only(monkeypatch):
    class PreconditionFailed(Exception):
        pass

    class ExistingS3:
        def __init__(self, existing):
            self.existing = existing

        def put_object(self, **request):
            raise PreconditionFailed("exists")

        def get_object(self, **request):
            return {"Body": io.BytesIO(self.existing)}

    encoded = b'{"immutable":true}'
    digest = hashlib.sha256(encoded).hexdigest()
    monkeypatch.setenv("SCALE_LAKE_BUCKET", "private")
    monkeypatch.setattr(export_app, "_S3", ExistingS3(encoded))
    export_app._put_manifest_immutable("safe/manifest.json", encoded, digest)

    monkeypatch.setattr(export_app, "_S3", ExistingS3(b"different"))
    with pytest.raises(RuntimeError, match="different bytes"):
        export_app._put_manifest_immutable("safe/manifest.json", encoded, digest)


def test_handler_uses_partial_batch_failures_and_acknowledges_cancellation(monkeypatch):
    def process(message, request_id):
        if message["export_id"].endswith("0000"):
            raise export_app.ExportCanceled("canceled")
        if message["export_id"].endswith("1111"):
            raise RuntimeError("retry")

    resets = []
    monkeypatch.setattr(export_app, "_process", process)
    monkeypatch.setattr(
        export_app,
        "_reset_for_retry",
        lambda run_id, export_id, request_id: resets.append(export_id),
    )
    event = {
        "Records": [
            {
                "messageId": "ok",
                "body": json.dumps({"run_id": RUN_ID, "export_id": EXPORT_ID}),
            },
            {
                "messageId": "canceled",
                "body": json.dumps(
                    {"run_id": RUN_ID, "export_id": "export-00000000000000000000"}
                ),
            },
            {
                "messageId": "retry",
                "body": json.dumps(
                    {"run_id": RUN_ID, "export_id": "export-11111111111111111111"}
                ),
            },
            {"messageId": "invalid", "body": "not-json"},
        ]
    }
    result = export_app.handler(event, SimpleNamespace(aws_request_id="request-1"))

    assert result == {
        "batchItemFailures": [
            {"itemIdentifier": "retry"},
            {"itemIdentifier": "invalid"},
        ]
    }
    assert resets == ["export-11111111111111111111"]

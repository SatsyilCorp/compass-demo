"""Continuous demo stream contract, rotation, and synthetic event tests."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


FUNCTION_DIR = Path(__file__).resolve().parents[1]
if str(FUNCTION_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTION_DIR))

SPEC = importlib.util.spec_from_file_location(
    "compass_intake_demo_stream_app",
    FUNCTION_DIR / "app.py",
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class FakeTable:
    def __init__(self):
        self.item = None

    def get_item(self, **_kwargs):
        return {"Item": self.item} if self.item else {}

    def put_item(self, *, Item, **_kwargs):
        self.item = dict(Item)
        return {}

    def update_item(self, *, ExpressionAttributeValues, UpdateExpression, **_kwargs):
        assert self.item
        assert self.item["session_id"] == ExpressionAttributeValues[":session_id"]
        if "execution_arn" in UpdateExpression:
            self.item["execution_arn"] = ExpressionAttributeValues[":execution_arn"]
            self.item["execution_chunk_number"] = ExpressionAttributeValues[":chunk_number"]
        elif "emitted_events" in UpdateExpression:
            self.item.update(
                status=ExpressionAttributeValues[":status"],
                emitted_events=ExpressionAttributeValues[":sequence"],
                latest_batch_id=ExpressionAttributeValues[":batch_id"],
                latest_event=ExpressionAttributeValues[":latest_event"],
                updated_at=ExpressionAttributeValues[":updated_at"],
                completed_at=ExpressionAttributeValues[":completed_at"],
            )
        else:
            self.item.update(
                status=ExpressionAttributeValues[":status"],
                updated_at=ExpressionAttributeValues[":now"],
                completed_at=ExpressionAttributeValues[":now"],
            )
        return {}


class ConditionalFailure(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class S3PreconditionFailure(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "PreconditionFailed"}}


class RunningTable(FakeTable):
    def put_item(self, *, Item, ConditionExpression=None, **_kwargs):
        if ConditionExpression and self.item and self.item.get("status") == "running":
            raise ConditionalFailure()
        return super().put_item(Item=Item)


class FakeStepFunctions:
    def __init__(self):
        self.started = []
        self.stopped = []

    def start_execution(self, **kwargs):
        self.started.append(kwargs)
        return {"executionArn": "arn:aws:states:region:account:execution:demo:session"}

    def stop_execution(self, **kwargs):
        self.stopped.append(kwargs)
        return {}


class FakeS3:
    def __init__(self):
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        return {}


class ExistingObjectS3(FakeS3):
    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        raise S3PreconditionFailure()


class FakeKinesis:
    def __init__(self):
        self.puts = []

    def put_record(self, **kwargs):
        self.puts.append(kwargs)
        return {}


def identity():
    return app.Identity(
        "poweruser", "ONR-Corporate", "presenter@compass.demo", ["compass-poweruser"]
    )


def test_default_stream_records_use_only_governed_org_units():
    governed = {"Code-30", "Code-31", "Code-32", "Code-34", "Code-35"}

    records = [
        app._demo_stream_record("pulse-policy", sequence, "2026-08-13T12:00:00Z")
        for sequence in range(1, 16)
    ]

    assert {record["org_unit"] for record in records} == governed


def test_legacy_bounded_start_remains_available_for_smoke_tests(monkeypatch):
    table = FakeTable()
    states = FakeStepFunctions()
    monkeypatch.setenv(
        "DEMO_STREAM_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:123456789012:stateMachine:demo-stream",
    )
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app, "_STEP_FUNCTIONS", states)

    status_code, response = app.start_demo_stream(
        identity(), {"cadence_seconds": 2, "total_events": 15}
    )

    assert status_code == 202
    assert response["contract"] == "compass.demo-stream.v1"
    assert response["stream_kind"] == "continuous-synthetic"
    assert response["session"]["status"] == "running"
    assert response["session"]["stream_mode"] == "bounded"
    assert response["session"]["total_events"] == 15
    assert len(states.started) == 1
    started = json.loads(states.started[0]["input"])
    assert started["sequence"] == 1
    assert started["cadence_seconds"] == 2
    assert started["stream_mode"] == "bounded"
    assert started["chunk_number"] == 1
    assert table.item["execution_arn"].endswith(":session")


def test_continuous_start_has_no_event_limit(monkeypatch):
    table = FakeTable()
    states = FakeStepFunctions()
    monkeypatch.setenv(
        "DEMO_STREAM_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:123456789012:stateMachine:demo-stream",
    )
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app, "_STEP_FUNCTIONS", states)

    status_code, response = app.start_demo_stream(
        identity(), {"cadence_seconds": 1, "stream_mode": "continuous"}
    )

    assert status_code == 202
    assert response["session"]["stream_mode"] == "continuous"
    assert response["session"]["total_events"] is None
    assert response["safeguards"]["estimated_events_per_hour"] == 3600
    started = json.loads(states.started[0]["input"])
    assert started["total_events"] is None
    assert started["chunk_emitted"] == 0


def test_concurrent_start_returns_the_existing_session_without_overlap(monkeypatch):
    table = RunningTable()
    table.item = {
        "pk": app.DEMO_STREAM_PK,
        "sk": app.DEMO_STREAM_SK,
        "session_id": "pulse-existing",
        "status": "running",
        "cadence_seconds": 2,
        "total_events": 15,
        "emitted_events": 3,
    }
    states = FakeStepFunctions()
    monkeypatch.setenv(
        "DEMO_STREAM_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:123456789012:stateMachine:demo-stream",
    )
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app, "_STEP_FUNCTIONS", states)

    status_code, response = app.start_demo_stream(
        identity(), {"cadence_seconds": 1, "total_events": 5}
    )

    assert status_code == 200
    assert response["session"]["session_id"] == "pulse-existing"
    assert response["session"]["emitted_events"] == 3
    assert states.started == []


def test_tick_lands_one_real_drop_and_publishes_immediate_receipt(monkeypatch):
    table = FakeTable()
    table.item = {
        "pk": app.DEMO_STREAM_PK,
        "sk": app.DEMO_STREAM_SK,
        "session_id": "pulse-abc12345",
        "status": "running",
        "cadence_seconds": 2,
        "total_events": 2,
        "emitted_events": 0,
    }
    s3 = FakeS3()
    stream = FakeKinesis()
    monkeypatch.setenv("RAW_BUCKET", "raw-bucket")
    monkeypatch.setenv("STREAM_NAME", "ticker-stream")
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app, "_KINESIS", stream)
    monkeypatch.setattr(app.pipeline, "_S3", s3)

    result = app.demo_stream_tick(
        {
            "action": "demo_stream_tick",
            "session_id": "pulse-abc12345",
            "sequence": 1,
            "cadence_seconds": 2,
            "total_events": 2,
        }
    )

    assert result["continue"] is True
    assert result["sequence"] == 2
    assert table.item["emitted_events"] == 1
    assert len(s3.puts) == 1
    assert s3.puts[0]["Key"].endswith("/00000001.json")
    assert s3.puts[0]["IfNoneMatch"] == "*"
    envelope = json.loads(s3.puts[0]["Body"])
    assert envelope["synthetic_only"] is True
    assert envelope["record_count"] == 1
    assert envelope["records"][0]["grant_no"].startswith("ONR-LIVE-")
    assert len(stream.puts) == 1
    event = json.loads(stream.puts[0]["Data"])
    assert event["id"] == "demo-stream:pulse-abc12345:00000001"


def test_continuous_tick_rotates_workflow_without_completing_session(monkeypatch):
    table = FakeTable()
    table.item = {
        "pk": app.DEMO_STREAM_PK,
        "sk": app.DEMO_STREAM_SK,
        "session_id": "pulse-rotate123",
        "status": "running",
        "stream_mode": "continuous",
        "cadence_seconds": 1,
        "total_events": None,
        "emitted_events": 0,
        "execution_chunk_number": 1,
    }
    states = FakeStepFunctions()
    s3 = FakeS3()
    monkeypatch.setenv("RAW_BUCKET", "raw-bucket")
    monkeypatch.setenv(
        "DEMO_STREAM_STATE_MACHINE_ARN",
        "arn:aws:states:us-east-1:123456789012:stateMachine:demo-stream",
    )
    monkeypatch.delenv("STREAM_NAME", raising=False)
    monkeypatch.setattr(app, "DEMO_STREAM_EXECUTION_CHUNK_EVENTS", 2)
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app, "_STEP_FUNCTIONS", states)
    monkeypatch.setattr(app.pipeline, "_S3", s3)

    first = app.demo_stream_tick(
        {
            "session_id": "pulse-rotate123",
            "sequence": 1,
            "cadence_seconds": 1,
            "chunk_number": 1,
            "chunk_emitted": 0,
        }
    )
    second = app.demo_stream_tick(first)

    assert first["continue"] is True
    assert second["continue"] is False
    assert second["rotated"] is True
    assert second["status"] == "running"
    assert table.item["status"] == "running"
    assert table.item["execution_chunk_number"] == 2
    assert len(states.started) == 1
    rotated_input = json.loads(states.started[0]["input"])
    assert rotated_input["sequence"] == 3
    assert rotated_input["chunk_number"] == 2


def test_tick_retry_reconciles_an_existing_object_without_duplicate_transport(monkeypatch):
    table = FakeTable()
    table.item = {
        "pk": app.DEMO_STREAM_PK,
        "sk": app.DEMO_STREAM_SK,
        "session_id": "pulse-retry123",
        "status": "running",
        "stream_mode": "continuous",
        "cadence_seconds": 1,
        "total_events": None,
        "emitted_events": 0,
        "execution_chunk_number": 1,
    }
    s3 = ExistingObjectS3()
    stream = FakeKinesis()
    monkeypatch.setenv("RAW_BUCKET", "raw-bucket")
    monkeypatch.setenv("STREAM_NAME", "ticker-stream")
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app, "_KINESIS", stream)
    monkeypatch.setattr(app.pipeline, "_S3", s3)

    result = app.demo_stream_tick(
        {
            "session_id": "pulse-retry123",
            "sequence": 1,
            "cadence_seconds": 1,
            "chunk_number": 1,
            "chunk_emitted": 0,
        }
    )

    assert result["continue"] is True
    assert table.item["emitted_events"] == 1
    assert len(s3.puts) == 1
    assert stream.puts == []


def test_final_tick_completes_session_and_a_stopped_session_emits_nothing(monkeypatch):
    table = FakeTable()
    table.item = {
        "pk": app.DEMO_STREAM_PK,
        "sk": app.DEMO_STREAM_SK,
        "session_id": "pulse-final123",
        "status": "running",
        "cadence_seconds": 1,
        "total_events": 1,
        "emitted_events": 0,
    }
    s3 = FakeS3()
    monkeypatch.setenv("RAW_BUCKET", "raw-bucket")
    monkeypatch.delenv("STREAM_NAME", raising=False)
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app.pipeline, "_S3", s3)

    result = app.demo_stream_tick(
        {
            "action": "demo_stream_tick",
            "session_id": "pulse-final123",
            "sequence": 1,
            "cadence_seconds": 1,
            "total_events": 1,
        }
    )

    assert result["continue"] is False
    assert result["status"] == "completed"
    assert table.item["status"] == "completed"
    assert table.item["completed_at"]
    before = len(s3.puts)
    stopped = app.demo_stream_tick(
        {
            "action": "demo_stream_tick",
            "session_id": "pulse-final123",
            "sequence": 2,
            "cadence_seconds": 1,
            "total_events": 3,
        }
    )
    assert stopped["continue"] is False
    assert len(s3.puts) == before


def test_stop_marks_session_and_requests_workflow_stop(monkeypatch):
    table = FakeTable()
    table.item = {
        "pk": app.DEMO_STREAM_PK,
        "sk": app.DEMO_STREAM_SK,
        "session_id": "pulse-stop123",
        "status": "running",
        "execution_arn": "arn:execution",
        "cadence_seconds": 2,
        "total_events": 15,
        "emitted_events": 4,
    }
    states = FakeStepFunctions()
    monkeypatch.setattr(app, "_OPERATIONS_TABLE", table)
    monkeypatch.setattr(app, "_STEP_FUNCTIONS", states)

    response = app.stop_demo_stream("pulse-stop123")

    assert response["session"]["status"] == "stopped"
    assert states.stopped[0]["executionArn"] == "arn:execution"


def test_invalid_settings_fail_closed():
    for body in (
        {"cadence_seconds": 0, "total_events": 15},
        {"cadence_seconds": 3, "total_events": 15},
        {"cadence_seconds": 2, "total_events": 0},
        {"cadence_seconds": 2, "total_events": 61},
    ):
        try:
            app._valid_demo_stream_settings(body)
        except ValueError:
            continue
        raise AssertionError(f"expected invalid settings to fail: {body}")

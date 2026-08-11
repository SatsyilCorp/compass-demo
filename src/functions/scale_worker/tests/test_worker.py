"""Focused transaction and batch tests for the synthetic partition worker."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
COMMON = ROOT / "src" / "common" / "python"
APP_PATH = ROOT / "src" / "functions" / "scale_worker" / "app.py"
sys.path.insert(0, str(COMMON))

SPEC = importlib.util.spec_from_file_location("scale_worker_app", APP_PATH)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(worker)


class FakeDdb:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.requests = []

    def transact_write_items(self, **request):
        self.requests.append(request)
        if self.error:
            raise self.error


class ConflictThenSuccessDdb:
    def __init__(self, conflicts: int):
        self.conflicts = conflicts
        self.requests = []

    def transact_write_items(self, **request):
        self.requests.append(request)
        if len(self.requests) <= self.conflicts:
            raise ClientError(
                {
                    "Error": {"Code": "TransactionCanceledException"},
                    "CancellationReasons": [
                        {"Code": "None"},
                        {"Code": "TransactionConflict"},
                    ],
                }
            )


class ClientError(Exception):
    """Minimal botocore ClientError shape used without an SDK dependency."""

    def __init__(self, response):
        super().__init__(response.get("Error", {}).get("Message", "AWS error"))
        self.response = response


class FakeTable:
    def __init__(self, update_error: Exception | None = None):
        self.update_error = update_error
        self.updates = []

    def get_item(self, **request):
        return {"Item": {"status": "partitioning"}}

    def update_item(self, **request):
        self.updates.append(request)
        if self.update_error:
            raise self.update_error


def _message() -> dict:
    return {
        "run_id": "scale-20260811010101-a1b2c3d4e5",
        "dataset": "grants",
        "partition_id": "part-00000",
    }


def _output() -> dict:
    return {
        "receipt": {
            "quality": {
                "generated_records": 100,
                "valid_records": 99,
                "invalid_records": 1,
            }
        },
        "receipt_sha256": "a" * 64,
        "receipt_key": "receipts/grants/run_id=scale-safe/part-00000.json",
        "duration_ms": 125,
        "landing_bytes": 800,
        "curated_bytes": 700,
        "quarantine_bytes": 100,
    }


def test_commit_uses_exact_expression_values_for_each_transaction_update(monkeypatch):
    fake = FakeDdb()
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(worker, "_DDB", fake)
    monkeypatch.setattr(worker, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(worker, "_iso_now", lambda: "2026-08-11T01:02:03+00:00")

    assert worker._commit(_message(), _output()) is True
    transaction = fake.requests[0]["TransactItems"]
    partition_values = transaction[0]["Update"]["ExpressionAttributeValues"]
    run_values = transaction[1]["Update"]["ExpressionAttributeValues"]

    assert set(partition_values) == {
        ":completed",
        ":failed",
        ":at",
        ":records",
        ":curated",
        ":quarantine",
        ":duration",
        ":landing_bytes",
        ":curated_bytes",
        ":quarantine_bytes",
        ":receipt_sha",
        ":receipt_key",
    }
    assert set(run_values) == {
        ":at",
        ":one",
        ":records",
        ":curated",
        ":quarantine",
        ":duration",
        ":landing_bytes",
        ":curated_bytes",
        ":quarantine_bytes",
        ":requested",
        ":partitioning",
    }
    assert transaction[0]["Update"]["ConditionExpression"] == (
        "#status <> :completed AND #status <> :failed"
    )
    assert transaction[1]["Update"]["ConditionExpression"] == (
        "#status = :requested OR #status = :partitioning"
    )


def test_proven_terminal_transaction_cancellation_is_counted_as_duplicate(monkeypatch):
    fake = FakeDdb(
        ClientError(
            {
                "Error": {
                    "Code": "TransactionCanceledException",
                    "Message": "transaction canceled",
                },
                "CancellationReasons": [
                    {
                        "Code": "ConditionalCheckFailed",
                        "Item": {"status": {"S": "completed"}},
                    },
                    {"Code": "None"},
                ],
            }
        )
    )
    duplicates = []
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(worker, "_DDB", fake)
    monkeypatch.setattr(worker, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(worker, "_record_duplicate", duplicates.append)

    assert worker._commit(_message(), _output()) is False
    assert duplicates == [_message()["run_id"]]
    first_update = fake.requests[0]["TransactItems"][0]["Update"]
    assert first_update["ReturnValuesOnConditionCheckFailure"] == "ALL_OLD"


def test_mark_running_recognizes_client_error_condition_code(monkeypatch):
    error = ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "condition failed",
            }
        }
    )
    fake_table = FakeTable(update_error=error)
    duplicates = []
    monkeypatch.setattr(worker, "_TABLE", fake_table)
    monkeypatch.setattr(worker, "_record_duplicate", duplicates.append)

    message = {**_message(), "profile_id": "1k"}
    assert worker._mark_running(message, "request-1") is False
    assert duplicates == [message["run_id"]]


def test_mark_running_propagates_transient_client_error(monkeypatch):
    error = ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "throttled",
            }
        }
    )
    monkeypatch.setattr(worker, "_TABLE", FakeTable(update_error=error))
    monkeypatch.setattr(
        worker,
        "_record_duplicate",
        lambda run_id: pytest.fail("transient error was classified as duplicate"),
    )

    with pytest.raises(ClientError) as raised:
        worker._mark_running(_message(), "request-1")
    assert raised.value is error


def test_mark_running_keeps_failed_partition_terminal(monkeypatch):
    error = ClientError(
        {
            "Error": {"Code": "ConditionalCheckFailedException"},
        }
    )
    fake_table = FakeTable(update_error=error)
    monkeypatch.setattr(worker, "_TABLE", fake_table)
    monkeypatch.setattr(worker, "_record_duplicate", lambda _run_id: None)

    assert worker._mark_running(_message(), "request-1") is False
    request = fake_table.updates[0]
    assert request["ConditionExpression"] == (
        "#status <> :completed AND #status <> :failed"
    )
    assert request["ExpressionAttributeValues"][":failed"] == "failed"


@pytest.mark.parametrize(
    "run_status",
    ["aggregating", "canceling", "canceled", "completed", "failed"],
)
def test_mark_running_rejects_runs_outside_partition_processing(
    monkeypatch,
    run_status,
):
    monkeypatch.setattr(worker, "_run_item", lambda _run_id: {"status": run_status})

    class NoWriteTable:
        def update_item(self, **_request):
            pytest.fail("closed worker phase must not be reopened")

    monkeypatch.setattr(worker, "_TABLE", NoWriteTable())

    assert worker._mark_running(_message(), "request-1") is False


@pytest.mark.parametrize("run_status", ["canceling", "canceled", "failed"])
def test_commit_acknowledges_proven_terminal_run_without_mutating_totals(
    monkeypatch,
    run_status,
):
    fake = FakeDdb(
        ClientError(
            {
                "Error": {"Code": "TransactionCanceledException"},
                "CancellationReasons": [
                    {"Code": "None"},
                    {
                        "Code": "ConditionalCheckFailed",
                        "Item": {"status": {"S": run_status}},
                    },
                ],
            }
        )
    )
    duplicates = []
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(worker, "_DDB", fake)
    monkeypatch.setattr(worker, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(worker, "_record_duplicate", duplicates.append)

    assert worker._commit(_message(), _output()) is False
    assert duplicates == [_message()["run_id"]]


@pytest.mark.parametrize(
    "response",
    [
        {
            "Error": {"Code": "TransactionCanceledException"},
        },
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [
                {"Code": "ConditionalCheckFailed"},
                {"Code": "None"},
            ],
        },
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [
                {
                    "Code": "ConditionalCheckFailed",
                    "Item": {"status": {"S": "running"}},
                },
                {"Code": "None"},
            ],
        },
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [
                {"Code": "TransactionConflict"},
                {"Code": "None"},
            ],
        },
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [
                {"Code": "ConditionalCheckFailed"},
                {"Code": "ThrottlingError"},
            ],
        },
        {
            "Error": {"Code": "TransactionConflictException"},
        },
        {
            "Error": {"Code": "ValidationException"},
        },
    ],
)
def test_ambiguous_or_transient_commit_cancellation_is_retried(
    monkeypatch, response
):
    error = ClientError(response)
    fake = FakeDdb(error)
    duplicates = []
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(worker, "_DDB", fake)
    monkeypatch.setattr(worker, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(worker, "_record_duplicate", duplicates.append)
    monkeypatch.setattr(worker.time, "sleep", lambda _seconds: None)

    with pytest.raises(ClientError) as raised:
        worker._commit(_message(), _output())
    assert raised.value is error
    assert duplicates == []


def test_commit_retries_transaction_conflicts_inside_the_worker(monkeypatch):
    fake = ConflictThenSuccessDdb(conflicts=3)
    delays = []
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(worker, "_DDB", fake)
    monkeypatch.setattr(worker, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(worker.time, "sleep", delays.append)
    monkeypatch.setattr(worker.random, "uniform", lambda _low, _high: 1.0)

    assert worker._commit(_message(), _output()) is True
    assert len(fake.requests) == 4
    assert delays == [0.025, 0.05, 0.1]


def test_handler_returns_only_failed_sqs_items(monkeypatch):
    processed = []

    def process(message, request_id):
        processed.append((message["partition_id"], request_id))
        if message["partition_id"] == "part-00001":
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(worker, "_process", process)
    event = {
        "Records": [
            {
                "messageId": "message-ok",
                "body": json.dumps({"partition_id": "part-00000"}),
            },
            {
                "messageId": "message-failed",
                "body": json.dumps({"partition_id": "part-00001"}),
            },
        ]
    }
    result = worker.handler(event, SimpleNamespace(aws_request_id="request-1"))

    assert result == {"batchItemFailures": [{"itemIdentifier": "message-failed"}]}
    assert processed == [
        ("part-00000", "request-1"),
        ("part-00001", "request-1"),
    ]


def test_terminal_receive_atomically_marks_exact_partition_failed(monkeypatch):
    fake = FakeDdb()
    monkeypatch.setenv("SCALE_RUNS_TABLE", "scale-runs")
    monkeypatch.setattr(worker, "_DDB", fake)
    monkeypatch.setattr(worker, "_serialize", lambda value: dict(value))
    monkeypatch.setattr(worker, "_iso_now", lambda: "2026-08-11T01:02:03+00:00")

    assert worker._mark_partition_failed(
        _message(), RuntimeError("synthetic partition failure")
    ) is True

    transaction = fake.requests[0]["TransactItems"]
    partition = transaction[0]["Update"]
    run = transaction[1]["Update"]
    assert partition["Key"] == {
        "pk": f"RUN#{_message()['run_id']}",
        "sk": "PART#grants#part-00000",
    }
    assert partition["ConditionExpression"] == (
        "#status <> :completed AND #status <> :failed"
    )
    assert partition["ReturnValuesOnConditionCheckFailure"] == "ALL_OLD"
    assert partition["ExpressionAttributeValues"][":failure_code"] == (
        "partition_processing_exhausted"
    )
    assert run["UpdateExpression"] == (
        "SET updated_at = :at ADD failed_partitions :one"
    )
    assert run["ConditionExpression"] == (
        "#status = :requested OR #status = :partitioning"
    )
    assert run["ReturnValuesOnConditionCheckFailure"] == "ALL_OLD"


@pytest.mark.parametrize(("receive_count", "expected_marks"), [("2", 0), ("3", 1)])
def test_handler_marks_poison_partition_on_configured_final_receive(
    monkeypatch,
    receive_count,
    expected_marks,
):
    message = {**_message(), "profile_id": "1k"}
    marked = []

    def fail(_message_value, _request_id):
        raise RuntimeError("synthetic terminal failure")

    monkeypatch.setattr(worker, "_process", fail)
    monkeypatch.setattr(
        worker,
        "_mark_partition_failed",
        lambda message_value, exc: marked.append(
            (message_value["partition_id"], type(exc).__name__)
        )
        or True,
    )
    event = {
        "Records": [
            {
                "messageId": "message-poison",
                "body": json.dumps(message),
                "attributes": {"ApproximateReceiveCount": receive_count},
            }
        ]
    }

    result = worker.handler(event, SimpleNamespace(aws_request_id="request-1"))

    assert result == {
        "batchItemFailures": [{"itemIdentifier": "message-poison"}]
    }
    assert len(marked) == expected_marks
    if marked:
        assert marked == [("part-00000", "RuntimeError")]

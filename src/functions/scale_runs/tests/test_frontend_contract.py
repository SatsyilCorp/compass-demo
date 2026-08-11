"""Scale Run HTTP payloads match the frontend Scale Lab Interface exactly."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
FUNCTION_DIR = ROOT / "src" / "functions" / "scale_runs"
COMMON_DIR = ROOT / "src" / "common" / "python"
for path in (str(COMMON_DIR), str(FUNCTION_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("SCALE_MAX_ESTIMATED_COST_USD", "10.00")
os.environ.setdefault("SCALE_MAX_CONCURRENCY", "4")
os.environ.setdefault("SCALE_EXPORT_QUEUE_URL", "https://sqs.example/exports")
os.environ.setdefault("SCALE_QUEUE_URL", "https://sqs.example/work")
os.environ.setdefault("SCALE_DLQ_URL", "https://sqs.example/dlq")
os.environ.setdefault("SCALE_LAKE_BUCKET", "compass-scale-contract")
os.environ.setdefault("SCALE_RUNS_TABLE", "compass-scale-contract")

SPEC = importlib.util.spec_from_file_location(
    "compass_scale_runs_contract_app",
    FUNCTION_DIR / "app.py",
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = app
SPEC.loader.exec_module(app)


class BotocoreStyleClientError(Exception):
    """Lean test double for the stable ClientError response interface."""

    def __init__(self, response, operation_name):
        super().__init__(response.get("Error", {}).get("Code", "ClientError"))
        self.response = response
        self.operation_name = operation_name


PROFILE_KEYS = {
    "id",
    "label",
    "short_label",
    "total_records",
    "description",
    "capacity_state",
    "capacity_note",
    "recommended",
}
PLAN_KEYS = {
    "plan_id",
    "profile_id",
    "seed",
    "generated_at",
    "capacity_state",
    "total_records",
    "estimated_raw_bytes",
    "target_duration_seconds",
    "concurrency_limit",
    "partition_count",
    "dataset_mix",
    "stages",
    "cost",
}
RUN_KEYS = {
    "run_id",
    "mode",
    "status",
    "created_at",
    "started_at",
    "updated_at",
    "completed_at",
    "cancelled_at",
    "plan",
    "progress",
    "quality",
    "costs",
    "intelligence",
    "export_receipt",
    "evidence",
    "error",
}
PROGRESS_KEYS = {
    "stage",
    "percent",
    "records_generated",
    "records_ingested",
    "records_curated",
    "records_quarantined",
    "bytes_written",
    "partitions_completed",
    "partitions_total",
    "current_throughput_rps",
    "peak_throughput_rps",
    "elapsed_seconds",
    "eta_seconds",
}
QUALITY_KEYS = {
    "overall_score",
    "passed_records",
    "failed_records",
    "quarantined_records",
    "rules",
}
QUALITY_RULE_KEYS = {
    "id",
    "label",
    "score",
    "passed_records",
    "failed_records",
}
INTELLIGENCE_KEYS = {
    "status",
    "model_run_id",
    "grants_analyzed",
    "topic_count",
    "anomalies_detected",
    "processing_seconds",
    "top_topics",
}
TOPIC_KEYS = {"label", "record_count", "confidence", "terms"}
EVIDENCE_KEYS = {
    "correlation_id",
    "audit_receipt",
    "manifest_uri",
    "manifest_sha256",
    "metrics_recorded_at",
    "recovery_queue_depth",
    "duplicate_records_suppressed",
    "stages",
}
EVIDENCE_STAGE_KEYS = {"id", "label", "status", "receipt", "recorded_at"}
EXPORT_KEYS = {
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


def cost_estimate() -> dict:
    return {
        "kind": "pre_run_estimate",
        "currency": "USD",
        "estimated_cost_usd": "0.02000000",
        "maximum_cost_usd": "0.10000000",
        "price_snapshot_captured_at": "2026-08-11T00:00:00+00:00",
        "disclosure": "Estimate excludes free tier and discounts.",
        "line_items": [
            {
                "key": "lambda_arm_request",
                "quantity": "12",
                "unit": "Requests",
                "rate_usd": "0.00000020",
                "cost_usd": "0.00000240",
            }
        ],
        "within_envelope": True,
        "price_snapshot_fresh": True,
    }


def internal_profile() -> dict:
    return {
        "id": "1k",
        "total_records": 1_000,
        "dataset_counts": {
            "grants": 200,
            "finance": 300,
            "milestones": 200,
            "documents": 100,
            "licenses": 20,
            "stream_events": 180,
        },
        "partitions": 6,
        "max_concurrency": 4,
        "expected_duration_seconds": 90,
        "capacity_state": "ready",
        "locked_reason": None,
    }


def internal_plan() -> dict:
    return {
        "plan_id": "plan-contract",
        "profile_id": "1k",
        "seed": 424242,
        "profile": internal_profile(),
        "cost": cost_estimate(),
        "launch_allowed": True,
        "locked_reason": None,
        "created_at": "2026-08-11T01:00:00+00:00",
        "expires_at": "2026-08-11T01:15:00+00:00",
        "synthetic_contract": "compass.synthetic-scale.v1",
    }


def internal_run(status: str = "completed_with_quarantine") -> dict:
    return {
        "run_id": "scale-contract",
        "plan_id": "plan-contract",
        "profile_id": "1k",
        "profile": internal_profile(),
        "seed": 424242,
        "synthetic_contract": "compass.synthetic-scale.v1",
        "status": status,
        "created_at": "2026-08-11T01:00:00+00:00",
        "execution_started_at": "2026-08-11T01:00:01+00:00",
        "updated_at": "2026-08-11T01:01:30+00:00",
        "completed_at": "2026-08-11T01:01:30+00:00"
        if status in app.TERMINAL_STATES
        else None,
        "cost": cost_estimate(),
        "total_partitions": 6,
        "completed_partitions": 6 if status in app.TERMINAL_STATES else 3,
        "failed_partitions": 0,
        "generated_records": 1_000 if status in app.TERMINAL_STATES else 500,
        "curated_records": 990 if status in app.TERMINAL_STATES else 495,
        "quarantined_records": 10 if status in app.TERMINAL_STATES else 5,
        "raw_bytes": 100_000,
        "curated_bytes": 70_000,
        "quarantine_bytes": 1_000,
        "parquet_bytes": 25_000,
        "duplicate_replays": 2,
        "manifest_sha256": "a" * 64,
        "evidence": {
            "run_manifest": "lake://scale-runs/scale-contract/manifest",
            "partition_receipts": 6,
        },
        "quality": {
            "valid_records": 990,
            "invalid_records": 10,
            "quality_score_basis_points": 9_900,
            "issues_by_code": {"required": 6, "range": 4},
        },
        "intelligence": {
            "dataset_records": {"grants": 200},
            "topics": [
                {
                    "label": "Autonomy",
                    "documents": 80,
                    "scope": "full_corpus_deterministic",
                }
            ],
            "anomalies": [{"kind": "at_risk_milestones", "records": 7}],
            "result_sha256": "b" * 64,
        },
    }


def test_profiles_response_is_the_exact_frontend_shape(monkeypatch):
    monkeypatch.setattr(app, "_capacity_state", lambda _profile_id: ("ready", None))

    response = app._profiles_response()

    assert set(response) == {"profiles", "generated_at"}
    assert [profile["id"] for profile in response["profiles"]] == [
        "1k",
        "10k",
        "100k",
        "1m",
    ]
    assert all(set(profile) == PROFILE_KEYS for profile in response["profiles"])
    assert response["profiles"][1]["recommended"] is True


def test_plan_response_is_the_exact_frontend_shape():
    plan = app._public_plan(internal_plan())

    assert set(plan) == PLAN_KEYS
    assert plan["generated_at"] == "2026-08-11T01:00:00+00:00"
    assert plan["capacity_state"] == "ready"
    assert sum(row["records"] for row in plan["dataset_mix"]) == 1_000
    assert {row["domain"] for row in plan["dataset_mix"]} == {
        "grants",
        "finance",
        "milestones",
        "documents",
        "licenses",
        "stream_events",
    }
    documents = next(row for row in plan["dataset_mix"] if row["domain"] == "documents")
    assert "searchable" not in documents["purpose"].lower()
    assert [stage["id"] for stage in plan["stages"]] == [
        "plan",
        "buffer",
        "generate",
        "ingest",
        "quality",
        "curate",
        "intelligence",
        "export",
        "evidence",
    ]
    assert set(plan["cost"]) == {
        "currency",
        "estimated_run_usd",
        "upper_bound_usd",
        "incremental_idle_monthly_usd",
        "pricing_as_of",
        "estimate_source",
        "disclaimer",
        "line_items",
    }


@pytest.mark.parametrize("profile_id", ["1k", "10k", "100k", "1m"])
def test_pre_run_estimate_uses_exact_six_dataset_partition_count(
    monkeypatch,
    profile_id,
):
    captured = []
    real_modeled_quantities = app.modeled_quantities

    def observed(records, partition_records, *, partition_count=None):
        captured.append(partition_count)
        return real_modeled_quantities(
            records,
            partition_records,
            partition_count=partition_count,
        )

    monkeypatch.setattr(app, "modeled_quantities", observed)
    monkeypatch.setattr(app, "_capacity_state", lambda _profile_id: ("ready", None))
    profile = app.get_profile(profile_id)

    app._profile_payload(profile_id)

    assert captured == [app._partition_count(profile)]


@pytest.mark.parametrize(
    ("internal", "public", "stage"),
    [
        ("requested", "queued", "plan"),
        ("generating", "generating", "generate"),
        ("landing", "ingesting", "ingest"),
        ("partitioning", "ingesting", "ingest"),
        ("validating", "quality", "quality"),
        ("curating", "quality", "curate"),
        ("enriching", "intelligence", "intelligence"),
        ("aggregating", "intelligence", "intelligence"),
        ("canceling", "cancelling", "evidence"),
        ("canceled", "cancelled", "evidence"),
        ("completed_with_quarantine", "completed", "evidence"),
        ("completed", "completed", "evidence"),
        ("failed", "failed", "evidence"),
    ],
)
def test_run_response_maps_internal_states_to_frontend_contract(
    monkeypatch,
    internal,
    public,
    stage,
):
    monkeypatch.setattr(app, "_queue_evidence", lambda: {
        "queue_depth": 0,
        "running_messages": 0,
        "dlq_count": 0,
    })
    monkeypatch.setattr(app, "_exports_for_run", lambda _run_id: [])

    run = app._run_snapshot(internal_run(internal), include_partitions=False)

    assert set(run) == RUN_KEYS
    assert set(run["plan"]) == PLAN_KEYS
    assert set(run["progress"]) == PROGRESS_KEYS
    assert set(run["quality"]) == QUALITY_KEYS
    assert all(set(rule) == QUALITY_RULE_KEYS for rule in run["quality"]["rules"])
    assert run["status"] == public
    assert run["progress"]["stage"] == stage
    assert run["mode"] == "live"
    assert run["error"] is None
    assert set(run["export_receipt"]) == EXPORT_KEYS
    assert run["costs"]["estimate_source"] == "aws_price_model"
    assert set(run["intelligence"]) == INTELLIGENCE_KEYS
    assert run["intelligence"]["model_run_id"] == f"intelligence-{'b' * 16}"
    assert all(
        set(topic) == TOPIC_KEYS for topic in run["intelligence"]["top_topics"]
    )
    assert set(run["evidence"]) == EVIDENCE_KEYS
    assert all(
        set(evidence_stage) == EVIDENCE_STAGE_KEYS
        for evidence_stage in run["evidence"]["stages"]
    )
    assert len(run["evidence"]["stages"]) == 9


def test_run_list_response_has_no_storage_or_deployment_fields(monkeypatch):
    class RunTable:
        def query(self, **kwargs):
            assert kwargs["IndexName"] == "gsi1"
            return {"Items": [internal_run()]}

    monkeypatch.setattr(app, "_TABLE", RunTable())
    monkeypatch.setattr(app, "_exports_for_run", lambda _run_id: [])

    response = app._list_runs()

    assert set(response) == {"runs", "generated_at"}
    assert len(response["runs"]) == 1
    assert set(response["runs"][0]) == RUN_KEYS


def test_public_export_is_the_exact_frontend_receipt_shape():
    receipt = app._public_export(
        {
            "export_id": "export-contract",
            "run_id": "scale-contract",
            "dataset": "curated_portfolio",
            "format": "parquet",
            "status": "completed",
            "rows": 990,
            "bytes": 25_000,
            "manifest_key": "exports/scale-contract/manifest.json",
            "manifest_sha256": "c" * 64,
            "download_url": "https://example.invalid/signed",
            "expires_at": "2026-08-12T01:00:00+00:00",
        }
    )

    assert set(receipt) == EXPORT_KEYS
    assert receipt == {
        "export_id": "export-contract",
        "status": "ready",
        "format": "parquet",
        "row_count": 990,
        "bytes": 25_000,
        "object_uri": "lake://scale-runs/scale-contract/exports/export-contract",
        "download_url": "https://example.invalid/signed",
        "expires_at": "2026-08-12T01:00:00+00:00",
        "sha256": "c" * 64,
    }


def test_ready_export_gets_a_presigned_download_url(monkeypatch):
    class ExportTable:
        def get_item(self, **_kwargs):
            return {
                "Item": {
                    "export_id": "export-contract",
                    "run_id": "scale-contract",
                    "status": "ready",
                    "rows": 990,
                    "bytes": 25_000,
                    "manifest_key": "exports/scale-contract/manifest.json",
                    "manifest_sha256": "c" * 64,
                    "expires_at": "2026-08-12T01:00:00+00:00",
                }
            }

    class ExportS3:
        def generate_presigned_url(self, operation, **kwargs):
            assert operation == "get_object"
            assert kwargs["Params"]["Key"] == "exports/scale-contract/manifest.json"
            return "https://example.invalid/ready-export"

    monkeypatch.setattr(app, "_TABLE", ExportTable())
    monkeypatch.setattr(app, "_S3", ExportS3())
    monkeypatch.setattr(
        app,
        "_now",
        lambda: app.datetime.fromisoformat("2026-08-11T01:00:00+00:00"),
    )

    receipt = app._get_export("scale-contract", "export-contract")

    assert receipt["status"] == "ready"
    assert receipt["download_url"] == "https://example.invalid/ready-export"


@pytest.mark.parametrize(
    ("reasons", "expected"),
    [
        (
            [
                {"Code": "ConditionalCheckFailed"},
                {"Code": "None"},
                {"Code": "None"},
                {"Code": "None"},
            ],
            True,
        ),
        (
            [
                {"Code": "None"},
                {"Code": "ConditionalCheckFailed"},
                {"Code": "None"},
                {"Code": "None"},
            ],
            True,
        ),
        (
            [
                {"Code": "TransactionConflict"},
                {"Code": "None"},
                {"Code": "None"},
                {"Code": "None"},
            ],
            False,
        ),
        ([{"Code": "ConditionalCheckFailed"}], False),
        ([], False),
    ],
)
def test_transaction_cancel_only_maps_known_condition_conflicts(reasons, expected):
    error = BotocoreStyleClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "transaction cancelled",
            },
            "CancellationReasons": reasons,
        },
        "TransactWriteItems",
    )

    assert app._is_transaction_condition_conflict(error) is expected


def test_non_transaction_client_error_is_not_a_condition_conflict():
    error = BotocoreStyleClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException"}},
        "TransactWriteItems",
    )

    assert app._is_transaction_condition_conflict(error) is False


def _configure_create_run_transaction_failure(monkeypatch, error):
    class RunTable:
        def get_item(self, *, Key, ConsistentRead):
            assert ConsistentRead is True
            if Key["pk"].startswith("IDEMP#"):
                return {}
            plan = internal_plan()
            plan["created_by"] = "poweruser"
            return {"Item": plan}

    class FailingDdb:
        def transact_write_items(self, **_kwargs):
            raise error

    monkeypatch.setattr(app, "_TABLE", RunTable())
    monkeypatch.setattr(app, "_DDB_CLIENT", FailingDdb())
    monkeypatch.setattr(app, "_serialize", lambda item: dict(item))
    monkeypatch.setattr(
        app,
        "_now",
        lambda: app.datetime.fromisoformat("2026-08-11T01:00:00+00:00"),
    )


def test_create_run_maps_lock_condition_cancellation_to_value_error(monkeypatch):
    error = BotocoreStyleClientError(
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [
                {"Code": "ConditionalCheckFailed"},
                {"Code": "None"},
                {"Code": "None"},
                {"Code": "None"},
            ],
        },
        "TransactWriteItems",
    )
    _configure_create_run_transaction_failure(monkeypatch, error)

    with pytest.raises(ValueError, match="Another Scale Run is active"):
        app._create_run(
            {"plan_id": "plan-contract", "idempotency_key": "run-contract-key"},
            SimpleNamespace(username="poweruser", sub="poweruser-sub"),
        )


def test_create_run_propagates_ambiguous_transaction_cancellation(monkeypatch):
    error = BotocoreStyleClientError(
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [{"Code": "ConditionalCheckFailed"}],
        },
        "TransactWriteItems",
    )
    _configure_create_run_transaction_failure(monkeypatch, error)

    with pytest.raises(BotocoreStyleClientError) as captured:
        app._create_run(
            {"plan_id": "plan-contract", "idempotency_key": "run-contract-key"},
            SimpleNamespace(username="poweruser", sub="poweruser-sub"),
        )

    assert captured.value is error


class FakeExportTable:
    def __init__(self):
        self.put = None

    def get_item(self, *, Key, ConsistentRead):
        del ConsistentRead
        if Key["sk"] == "META":
            return {"Item": {"run_id": "scale-contract", "status": "completed"}}
        return {}

    def put_item(self, *, Item, ConditionExpression):
        assert ConditionExpression == "attribute_not_exists(sk)"
        self.put = Item


class FakeSqs:
    def __init__(self):
        self.send = None
        self.attribute_requests = []

    def send_message(self, **kwargs):
        self.send = kwargs
        return {"MessageId": "message-contract"}

    def get_queue_attributes(self, **kwargs):
        self.attribute_requests.append(kwargs)
        return {"Attributes": {"ApproximateNumberOfMessages": "2"}}


def test_curated_portfolio_export_is_accepted_and_queued(monkeypatch):
    table = FakeExportTable()
    sqs = FakeSqs()
    monkeypatch.setattr(app, "_TABLE", table)
    monkeypatch.setattr(app, "_SQS", sqs)
    claims = SimpleNamespace(username="poweruser", sub="poweruser-sub")

    response = app._create_export(
        "scale-contract",
        {
            "dataset": "curated_portfolio",
            "format": "parquet",
            "idempotency_key": "export-contract-key",
        },
        claims,
    )

    assert table.put["dataset"] == "curated_portfolio"
    assert response["status"] == "building"
    assert response["format"] == "parquet"
    assert set(response) == EXPORT_KEYS
    assert sqs.send["QueueUrl"] == "https://sqs.example/exports"


def test_queue_evidence_only_requests_supported_sqs_attributes(monkeypatch):
    sqs = FakeSqs()
    monkeypatch.setattr(app, "_SQS", sqs)

    evidence = app._queue_evidence()

    requested = {
        name
        for call in sqs.attribute_requests
        for name in call["AttributeNames"]
    }
    assert "ApproximateAgeOfOldestMessage" not in requested
    assert requested <= {
        "ApproximateNumberOfMessages",
        "ApproximateNumberOfMessagesNotVisible",
    }
    assert evidence == {
        "queue_depth": 2,
        "running_messages": 0,
        "dlq_count": 2,
    }


def test_direct_orchestration_exceptions_propagate_to_step_functions(monkeypatch):
    def fail(_run_id):
        raise RuntimeError("dispatch contract failure")

    monkeypatch.setattr(app, "_dispatch", fail)

    with pytest.raises(RuntimeError, match="dispatch contract failure"):
        app.handler({"action": "dispatch", "run_id": "scale-contract"}, None)


class DispatchTable:
    def __init__(self):
        self.meta = {
            "pk": "RUN#scale-contract",
            "sk": "META",
            "run_id": "scale-contract",
            "profile_id": "1k",
            "seed": 424242,
            "status": "requested",
            "expires_at_epoch": 1_800_000_000,
        }
        self.partitions = {}

    @staticmethod
    def _condition_failure():
        return BotocoreStyleClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "PutItem",
        )

    def get_item(self, *, Key, ConsistentRead):
        assert ConsistentRead is True
        if Key["sk"] == "META":
            return {"Item": self.meta}
        item = self.partitions.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}

    def put_item(self, *, Item, ConditionExpression):
        assert ConditionExpression == "attribute_not_exists(pk)"
        key = (Item["pk"], Item["sk"])
        if key in self.partitions:
            raise self._condition_failure()
        self.partitions[key] = dict(Item)

    def update_item(self, **request):
        key = request["Key"]
        values = request["ExpressionAttributeValues"]
        if key["sk"] == "META":
            if self.meta["status"] not in {"requested", "partitioning"}:
                raise self._condition_failure()
            self.meta["total_partitions"] = values[":total"]
            self.meta.setdefault("dlq_baseline_count", values.get(":dlq", 0))
            if ":next_status" in values:
                self.meta["status"] = values[":next_status"]
                self.meta.setdefault("dispatched_at", values[":at"])
            self.meta["updated_at"] = values[":at"]
            return
        item = self.partitions[(key["pk"], key["sk"])]
        if ":message_id" in values:
            item.setdefault("dispatch_acknowledged_at", values[":at"])
            item.setdefault("dispatch_message_id", values[":message_id"])
            item["dispatch_state"] = values[":acknowledged"]
        elif ":failure_code" in values:
            item["dispatch_state"] = values[":queued"]
            item["last_dispatch_failure_code"] = values[":failure_code"]
        else:
            item["dispatch_state"] = values[":dispatching"]
            item.setdefault("dispatch_attempted_at", values[":at"])


class PartiallyFailingDispatchSqs:
    def __init__(self):
        self.calls = []

    def send_message_batch(self, **request):
        self.calls.append(request)
        entries = request["Entries"]
        if len(self.calls) == 1:
            return {
                "Successful": [
                    {"Id": entries[0]["Id"], "MessageId": "accepted-first"}
                ],
                "Failed": [
                    {"Id": entries[1]["Id"], "Code": "InternalError"}
                ],
            }
        return {
            "Successful": [
                {"Id": entry["Id"], "MessageId": "accepted-retry"}
                for entry in entries
            ]
        }


def test_dispatch_retry_preserves_committed_rows_and_only_resends_unacknowledged_work(
    monkeypatch,
):
    table = DispatchTable()
    sqs = PartiallyFailingDispatchSqs()
    specs = [
        SimpleNamespace(
            partition_id=f"part-{index:05d}",
            ordinal=index,
            start=index * 100,
            stop=(index + 1) * 100,
            record_count=100,
        )
        for index in range(2)
    ]
    monkeypatch.setattr(app, "DATASETS", ("grants",))
    monkeypatch.setattr(app, "get_profile", lambda _profile_id: SimpleNamespace(name="1k"))
    monkeypatch.setattr(
        app,
        "iter_partition_specs",
        lambda _profile, _dataset: iter(specs),
    )
    monkeypatch.setattr(app, "_TABLE", table)
    monkeypatch.setattr(app, "_SQS", sqs)
    monkeypatch.setattr(
        app,
        "_queue_evidence",
        lambda: {"queue_depth": 0, "running_messages": 0, "dlq_count": 4},
    )
    monkeypatch.setattr(app, "_emit_metrics", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="partition dispatch failed"):
        app._dispatch("scale-contract")

    first_key = ("RUN#scale-contract", "PART#grants#part-00000")
    table.partitions[first_key].update(
        {"status": "completed", "receipt_sha256": "a" * 64}
    )

    response = app._dispatch("scale-contract")

    assert response == {
        "run_id": "scale-contract",
        "status": "partitioning",
        "dispatched": True,
        "partitions": 2,
    }
    assert len(sqs.calls) == 2
    retried = [json.loads(entry["MessageBody"]) for entry in sqs.calls[1]["Entries"]]
    assert [message["partition_id"] for message in retried] == ["part-00001"]
    assert table.partitions[first_key]["status"] == "completed"
    assert table.partitions[first_key]["receipt_sha256"] == "a" * 64
    assert table.meta["dlq_baseline_count"] == 4


def test_dispatch_never_resends_an_uncertain_sqs_outcome(monkeypatch):
    table = DispatchTable()

    class UncertainSqs:
        def __init__(self):
            self.calls = 0

        def send_message_batch(self, **_request):
            self.calls += 1
            raise TimeoutError("SQS response was lost")

    sqs = UncertainSqs()
    spec = SimpleNamespace(
        partition_id="part-00000",
        ordinal=0,
        start=0,
        stop=100,
        record_count=100,
    )
    monkeypatch.setattr(app, "DATASETS", ("grants",))
    monkeypatch.setattr(app, "get_profile", lambda _profile_id: SimpleNamespace(name="1k"))
    monkeypatch.setattr(
        app,
        "iter_partition_specs",
        lambda _profile, _dataset: iter((spec,)),
    )
    monkeypatch.setattr(app, "_TABLE", table)
    monkeypatch.setattr(app, "_SQS", sqs)
    monkeypatch.setattr(
        app,
        "_queue_evidence",
        lambda: {"queue_depth": 0, "running_messages": 0, "dlq_count": 0},
    )

    with pytest.raises(TimeoutError, match="response was lost"):
        app._dispatch("scale-contract")
    with pytest.raises(RuntimeError, match="outcome is uncertain"):
        app._dispatch("scale-contract")

    assert sqs.calls == 1


def test_athena_cancellation_stops_queries_and_releases_run(monkeypatch):
    class Athena:
        def __init__(self):
            self.stopped = []

        def stop_query_execution(self, **request):
            self.stopped.append(request["QueryExecutionId"])

        def get_query_execution(self, **_request):
            pytest.fail("canceled Athena work must not be polled")

    athena = Athena()
    completed = []
    monkeypatch.setattr(
        app,
        "_get_run_item",
        lambda _run_id: {
            "status": "canceling",
            "athena_queries": {"grants": "query-1", "finance": "query-2"},
        },
    )
    monkeypatch.setattr(app, "_ATHENA", athena)
    monkeypatch.setattr(app, "_complete_cancel", completed.append)

    response = app._check_athena("scale-contract")

    assert response == {
        "run_id": "scale-contract",
        "status": "canceled",
        "terminal": True,
    }
    assert athena.stopped == ["query-1", "query-2"]
    assert completed == ["scale-contract"]


@pytest.mark.parametrize("action_name", ["_start_athena", "_finalize"])
def test_post_poll_actions_honor_cancellation_before_side_effects(
    monkeypatch,
    action_name,
):
    completed = []
    monkeypatch.setattr(
        app,
        "_get_run_item",
        lambda _run_id: {"status": "canceling"},
    )
    monkeypatch.setattr(app, "_complete_cancel", completed.append)
    monkeypatch.setattr(
        app,
        "_all_partition_items",
        lambda _run_id: pytest.fail("canceled run must not load partition receipts"),
    )

    response = getattr(app, action_name)("scale-contract")

    assert response == {
        "run_id": "scale-contract",
        "status": "canceled",
        "terminal": True,
    }
    assert completed == ["scale-contract"]


@pytest.mark.parametrize("terminal_status", sorted(app.TERMINAL_STATES))
def test_cancel_api_never_reopens_a_terminal_run(monkeypatch, terminal_status):
    run = {"run_id": "scale-contract", "status": terminal_status}
    monkeypatch.setattr(app, "_get_run_item", lambda _run_id: run)
    monkeypatch.setattr(app, "_run_snapshot", lambda item: dict(item))

    class NoWriteTable:
        def update_item(self, **_request):
            pytest.fail("terminal run must not be changed to canceling")

    monkeypatch.setattr(app, "_TABLE", NoWriteTable())

    response = app._cancel_run(
        "scale-contract",
        SimpleNamespace(username="poweruser", sub="poweruser-sub"),
    )

    assert response["status"] == terminal_status


@pytest.mark.parametrize(
    ("failed_partitions", "dlq_baseline", "dlq_count", "expected_code"),
    [
        (1, 0, 0, "partition_processing_exhausted"),
        (0, 2, 3, "partition_dlq_detected"),
    ],
)
def test_partition_poison_evidence_fails_run_on_next_poll(
    monkeypatch,
    failed_partitions,
    dlq_baseline,
    dlq_count,
    expected_code,
):
    failures = []
    monkeypatch.setattr(
        app,
        "_get_run_item",
        lambda _run_id: {
            "status": "partitioning",
            "deadline_at": "2026-08-11T02:00:00+00:00",
            "failed_partitions": failed_partitions,
            "dlq_baseline_count": dlq_baseline,
        },
    )
    monkeypatch.setattr(
        app,
        "_now",
        lambda: app.datetime.fromisoformat("2026-08-11T01:00:00+00:00"),
    )
    monkeypatch.setattr(
        app,
        "_queue_evidence",
        lambda: {
            "queue_depth": 0,
            "running_messages": 0,
            "dlq_count": dlq_count,
        },
    )
    monkeypatch.setattr(
        app,
        "_fail_run",
        lambda run_id, code: failures.append((run_id, code)),
    )

    response = app._check("scale-contract")

    assert response == {
        "run_id": "scale-contract",
        "status": "failed",
        "terminal": True,
    }
    assert failures == [("scale-contract", expected_code)]


def test_fail_action_persists_terminal_failure_and_returns_for_step_functions(
    monkeypatch,
):
    calls = []

    def fail_run(run_id, code):
        calls.append((run_id, code))

    monkeypatch.setattr(app, "_fail_run", fail_run)

    response = app._orchestration_action(
        {"action": "fail", "run_id": "scale-contract"}
    )

    assert calls == [("scale-contract", "orchestration_failure")]
    assert response == {
        "run_id": "scale-contract",
        "status": "failed",
        "terminal": True,
    }


def test_fail_run_persists_public_evidence_and_releases_lock(monkeypatch):
    class FailureTable:
        def __init__(self):
            self.update = None

        def update_item(self, **kwargs):
            self.update = kwargs

    table = FailureTable()
    released = []
    monkeypatch.setattr(app, "_TABLE", table)
    monkeypatch.setattr(app, "_release_lock", lambda run_id: released.append(run_id))

    app._fail_run("scale-contract", "orchestration_failure")

    values = table.update["ExpressionAttributeValues"]
    assert values[":status"] == "failed"
    assert values[":error"]["retryable"] is False
    assert values[":evidence"]["failure_code"] == "orchestration_failure"
    assert values[":evidence"]["failure_receipt"].startswith("run://")
    assert released == ["scale-contract"]


def test_metered_worker_cost_uses_two_gb_plus_control_export_allowance(monkeypatch):
    captured = {}

    def estimate(profile_id, quantities, **kwargs):
        captured["profile_id"] = profile_id
        captured["quantities"] = quantities
        captured["kwargs"] = kwargs
        return {"estimated_cost_usd": "0.01000000"}

    monkeypatch.setattr(app, "estimate_incremental", estimate)
    monkeypatch.setattr(app.PriceCatalog, "load", classmethod(lambda _cls: object()))
    run = {
        "profile_id": "1k",
        "generated_records": 1_000,
        "completed_partitions": app._partition_count(app.get_profile("1k")),
        "worker_duration_ms": 1_000,
        "raw_bytes": 1_000,
        "curated_bytes": 500,
        "athena_scanned_bytes": 0,
    }

    app._metered_cost(run, parquet_bytes=250)

    assert captured["profile_id"] == "1k"
    assert captured["quantities"].lambda_arm_gb_seconds == app.Decimal(152)
    assert captured["kwargs"]["deployed_hard_cap_usd"] == app._max_cost()

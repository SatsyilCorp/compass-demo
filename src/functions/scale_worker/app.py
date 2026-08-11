"""Bounded, retry-safe worker for one Compass synthetic partition."""
from __future__ import annotations

import base64
import json
import logging
import os
import random
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from compass_common.scale_workload import (
    DefectPolicy,
    DeterministicGzipJsonlWriter,
    PartitionReceiptBuilder,
    PartitionSpec,
    canonical_json_bytes,
    iter_record_results,
    sha256_hex,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

MAX_RECEIVE_COUNT = int(os.environ.get("SCALE_WORKER_MAX_RECEIVE_COUNT", "3"))
TRANSACTION_CONFLICT_ATTEMPTS = max(
    1,
    int(os.environ.get("SCALE_TRANSACTION_CONFLICT_ATTEMPTS", "8")),
)

_TABLE = None
_DDB = None
_S3 = None


def _table():
    global _TABLE
    if _TABLE is None:
        import boto3

        _TABLE = boto3.resource("dynamodb").Table(os.environ["SCALE_RUNS_TABLE"])
    return _TABLE


def _ddb():
    global _DDB
    if _DDB is None:
        import boto3

        _DDB = boto3.client("dynamodb")
    return _DDB


def _s3():
    global _S3
    if _S3 is None:
        import boto3

        _S3 = boto3.client("s3")
    return _S3


def _serialize(item: Mapping[str, Any]) -> dict[str, Any]:
    from boto3.dynamodb.types import TypeSerializer

    serializer = TypeSerializer()
    return {key: serializer.serialize(value) for key, value in item.items()}


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _run_item(run_id: str) -> dict[str, Any]:
    item = _table().get_item(
        Key={"pk": f"RUN#{run_id}", "sk": "META"},
        ConsistentRead=True,
    ).get("Item")
    if not item:
        raise ValueError("Scale Run was not found")
    return item


def _partition_key(message: Mapping[str, Any]) -> dict[str, str]:
    return {
        "pk": f"RUN#{message['run_id']}",
        "sk": f"PART#{message['dataset']}#{message['partition_id']}",
    }


def _aws_error_code(exc: Exception) -> str | None:
    """Read the stable botocore ClientError code without importing botocore."""

    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return None
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("Code")
    return str(code) if code else None


def _is_terminal_partition_cancellation(exc: Exception) -> bool:
    """Return true only when a terminal ledger condition canceled commit.

    TransactItems order is part of the commit contract: item zero conditionally
    completes the partition, then item one conditionally increments totals for
    an active run. A precise ConditionalCheckFailed reason and returned old item
    can prove either that the partition or its run is terminal. Missing,
    truncated, conflicting, or otherwise ambiguous reasons must be retried.
    """

    if _aws_error_code(exc) != "TransactionCanceledException":
        return False
    response = getattr(exc, "response", None)
    reasons = response.get("CancellationReasons") if isinstance(response, Mapping) else None
    if not isinstance(reasons, list) or len(reasons) != 2:
        return False
    first, second = reasons
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        return False
    first_code = first.get("Code")
    second_code = second.get("Code")
    if first_code == "ConditionalCheckFailed" and second_code in {None, "None"}:
        return _status_from_cancellation_reason(first) in {"completed", "failed"}
    if first_code in {None, "None"} and second_code == "ConditionalCheckFailed":
        return _status_from_cancellation_reason(second) in {
            "canceling",
            "canceled",
            "completed",
            "completed_with_quarantine",
            "failed",
        }
    return False


def _is_transaction_conflict(exc: Exception) -> bool:
    """Return true for DynamoDB transaction contention that is safe to retry."""

    code = _aws_error_code(exc)
    if code == "TransactionConflictException":
        return True
    if code != "TransactionCanceledException":
        return False
    response = getattr(exc, "response", None)
    reasons = response.get("CancellationReasons") if isinstance(response, Mapping) else None
    if not isinstance(reasons, list):
        return False
    return any(
        isinstance(reason, Mapping) and reason.get("Code") == "TransactionConflict"
        for reason in reasons
    )


def _transact_write_with_conflict_retry(items: list[dict[str, Any]]) -> None:
    """Commit a transaction with short jittered retries for ledger contention."""

    for attempt in range(TRANSACTION_CONFLICT_ATTEMPTS):
        try:
            _ddb().transact_write_items(TransactItems=items)
            return
        except Exception as exc:
            final_attempt = attempt + 1 >= TRANSACTION_CONFLICT_ATTEMPTS
            if not _is_transaction_conflict(exc) or final_attempt:
                raise
            base_delay = min(0.5, 0.025 * (2**attempt))
            time.sleep(base_delay * random.uniform(0.75, 1.25))


def _status_from_cancellation_reason(reason: Mapping[str, Any]) -> str | None:
    failed_item = reason.get("Item")
    if not isinstance(failed_item, Mapping):
        return None
    status = failed_item.get("status")
    if not isinstance(status, Mapping) or not status.get("S"):
        return None
    return str(status["S"])


def _terminal_partition_status(exc: Exception) -> str | None:
    """Return a proven terminal partition status from a two-item transaction."""

    if _aws_error_code(exc) != "TransactionCanceledException":
        return None
    response = getattr(exc, "response", None)
    reasons = response.get("CancellationReasons") if isinstance(response, Mapping) else None
    if not isinstance(reasons, list) or len(reasons) != 2:
        return None
    first, second = reasons
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        return None
    if first.get("Code") != "ConditionalCheckFailed":
        return None
    if second.get("Code") not in {None, "None"}:
        return None
    return _status_from_cancellation_reason(first)


def _terminal_run_status(exc: Exception) -> str | None:
    """Return a proven terminal run status from a two-item transaction."""

    if _aws_error_code(exc) != "TransactionCanceledException":
        return None
    response = getattr(exc, "response", None)
    reasons = response.get("CancellationReasons") if isinstance(response, Mapping) else None
    if not isinstance(reasons, list) or len(reasons) != 2:
        return None
    first, second = reasons
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        return None
    if first.get("Code") not in {None, "None"}:
        return None
    if second.get("Code") != "ConditionalCheckFailed":
        return None
    return _status_from_cancellation_reason(second)


def _mark_running(message: Mapping[str, Any], request_id: str) -> bool:
    run = _run_item(str(message["run_id"]))
    if run["status"] not in {"requested", "partitioning"}:
        return False
    try:
        _table().update_item(
            Key=_partition_key(message),
            UpdateExpression=(
                "SET #status = :running, started_at = if_not_exists(started_at, :at), "
                "last_request_id = :request, attempts = if_not_exists(attempts, :zero) + :one"
            ),
            ConditionExpression="#status <> :completed AND #status <> :failed",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":running": "running",
                ":completed": "completed",
                ":failed": "failed",
                ":at": _iso_now(),
                ":request": request_id,
                ":zero": 0,
                ":one": 1,
            },
        )
        return True
    except Exception as exc:
        if _aws_error_code(exc) == "ConditionalCheckFailedException":
            _record_duplicate(str(message["run_id"]))
            return False
        raise


def _record_duplicate(run_id: str) -> None:
    _table().update_item(
        Key={"pk": f"RUN#{run_id}", "sk": "META"},
        UpdateExpression="ADD duplicate_replays :one",
        ExpressionAttributeValues={":one": 1},
    )


def _mark_partition_failed(message: Mapping[str, Any], exc: Exception) -> bool:
    """Atomically record one exhausted partition and increment the run total."""

    run_id = str(message["run_id"])
    at = _iso_now()
    partition_values = {
        ":failed": "failed",
        ":completed": "completed",
        ":at": at,
        ":failure_code": "partition_processing_exhausted",
        ":failure_type": type(exc).__name__,
    }
    run_values = {
        ":at": at,
        ":one": 1,
        ":requested": "requested",
        ":partitioning": "partitioning",
    }
    try:
        _transact_write_with_conflict_retry(
            [
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize(_partition_key(message)),
                        "UpdateExpression": (
                            "SET #status = :failed, failed_at = :at, "
                            "failure_code = :failure_code, "
                            "failure_type = :failure_type"
                        ),
                        "ConditionExpression": (
                            "#status <> :completed AND #status <> :failed"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": _serialize(partition_values),
                        "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
                    }
                },
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize({"pk": f"RUN#{run_id}", "sk": "META"}),
                        "UpdateExpression": (
                            "SET updated_at = :at ADD failed_partitions :one"
                        ),
                        "ConditionExpression": (
                            "#status = :requested OR #status = :partitioning"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": _serialize(run_values),
                        "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
                    }
                },
            ]
        )
        return True
    except Exception as write_exc:
        terminal_status = _terminal_partition_status(write_exc)
        if terminal_status == "failed":
            return True
        if terminal_status == "completed":
            return False
        if _terminal_run_status(write_exc) in {
            "canceling",
            "canceled",
            "completed",
            "completed_with_quarantine",
            "failed",
        }:
            return False
        raise


def _is_terminal_receive(record: Mapping[str, Any]) -> bool:
    attributes = record.get("attributes")
    if not isinstance(attributes, Mapping):
        return False
    try:
        return int(attributes.get("ApproximateReceiveCount", 0)) >= MAX_RECEIVE_COUNT
    except (TypeError, ValueError):
        return False


def _write_partition_files(message: Mapping[str, Any]) -> dict[str, Any]:
    run_id = str(message["run_id"])
    dataset = str(message["dataset"])
    partition_id = str(message["partition_id"])
    spec = PartitionSpec(
        profile=str(message["profile_id"]),
        dataset=dataset,
        ordinal=int(message["partition_ordinal"]),
        partition_id=partition_id,
        start=int(message["start"]),
        stop=int(message["stop"]),
    )
    seed = int(message["seed"])
    policy = DefectPolicy(rate_basis_points=int(message["defect_rate_basis_points"]))
    builder = PartitionReceiptBuilder(spec, seed=seed, defect_policy=policy)
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="compass-scale-") as temp_dir:
        root = Path(temp_dir)
        raw_path = root / "landing.jsonl.gz"
        curated_path = root / "curated.jsonl.gz"
        quarantine_path = root / "quarantine.jsonl.gz"
        with (
            raw_path.open("wb") as raw_file,
            curated_path.open("wb") as curated_file,
            quarantine_path.open("wb") as quarantine_file,
        ):
            raw_writer = DeterministicGzipJsonlWriter(raw_file)
            curated_writer = DeterministicGzipJsonlWriter(curated_file)
            quarantine_writer = DeterministicGzipJsonlWriter(quarantine_file)
            for result in iter_record_results(
                spec.profile,
                dataset,
                seed=seed,
                start=spec.start,
                stop=spec.stop,
                defect_policy=policy,
            ):
                raw_writer.write(result.record)
                builder.observe(result)
                lake_record = {
                    **result.record,
                    "scale_run_id": run_id,
                    "scale_dataset": dataset,
                    "scale_partition_id": partition_id,
                    "scale_record_index": result.index,
                }
                if result.valid:
                    curated_writer.write(lake_record)
                else:
                    quarantine_writer.write(
                        {
                            "scale_run_id": run_id,
                            "scale_dataset": dataset,
                            "scale_partition_id": partition_id,
                            "scale_record_index": result.index,
                            "record": result.record,
                            "issues": [issue.to_dict() for issue in result.issues],
                            "injected_defect": result.injected_defect,
                            "synthetic": True,
                        }
                    )
            raw_object = raw_writer.close()
            curated_object = curated_writer.close()
            quarantine_object = quarantine_writer.close()

        receipt = builder.finish()
        if raw_object.content_sha256 != receipt["content"]["content_sha256"]:
            raise RuntimeError("landing content checksum does not match the Partition Receipt")
        duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        prefix = f"{dataset}/run_id={run_id}/{partition_id}.jsonl.gz"
        keys = {
            "landing": f"landing/{prefix}",
            "curated": f"curated/{prefix}",
            "quarantine": f"quarantine/{prefix}",
            "receipt": f"receipts/{dataset}/run_id={run_id}/{partition_id}.json",
        }
        _upload_file(raw_path, keys["landing"], raw_object.object_sha256, raw_object.record_count)
        _upload_file(
            curated_path,
            keys["curated"],
            curated_object.object_sha256,
            curated_object.record_count,
        )
        if quarantine_object.record_count:
            _upload_file(
                quarantine_path,
                keys["quarantine"],
                quarantine_object.object_sha256,
                quarantine_object.record_count,
            )
        receipt.update(
            {
                "run_id": run_id,
                "duration_ms": duration_ms,
                "objects": {
                    "landing": raw_object.to_dict(),
                    "curated": curated_object.to_dict(),
                    "quarantine": quarantine_object.to_dict(),
                },
                "logical_locators": {
                    "landing": f"lake://scale-runs/{run_id}/landing/{dataset}/{partition_id}",
                    "curated": f"lake://scale-runs/{run_id}/curated/{dataset}/{partition_id}",
                    "quarantine": (
                        f"lake://scale-runs/{run_id}/quarantine/{dataset}/{partition_id}"
                        if quarantine_object.record_count
                        else None
                    ),
                },
            }
        )
        encoded = canonical_json_bytes(receipt)
        receipt_sha = sha256_hex(encoded)
        _s3().put_object(
            Bucket=os.environ["SCALE_LAKE_BUCKET"],
            Key=keys["receipt"],
            Body=encoded,
            ContentType="application/json",
            Metadata={
                "sha256": receipt_sha,
                "synthetic-only": "true",
                "dataset": dataset,
            },
        )
    return {
        "receipt": receipt,
        "receipt_sha256": receipt_sha,
        "receipt_key": keys["receipt"],
        "duration_ms": duration_ms,
        "landing_bytes": raw_object.compressed_bytes,
        "curated_bytes": curated_object.compressed_bytes,
        "quarantine_bytes": quarantine_object.compressed_bytes,
    }


def _upload_file(path: Path, key: str, sha256_hex_value: str, records: int) -> None:
    checksum = base64.b64encode(bytes.fromhex(sha256_hex_value)).decode("ascii")
    with path.open("rb") as handle:
        _s3().put_object(
            Bucket=os.environ["SCALE_LAKE_BUCKET"],
            Key=key,
            Body=handle,
            ContentType="application/gzip",
            ChecksumSHA256=checksum,
            Metadata={
                "sha256": sha256_hex_value,
                "records": str(records),
                "synthetic-only": "true",
            },
        )


def _commit(message: Mapping[str, Any], output: Mapping[str, Any]) -> bool:
    receipt = output["receipt"]
    quality = receipt["quality"]
    run_id = str(message["run_id"])
    partition_values = {
        ":completed": "completed",
        ":failed": "failed",
        ":at": _iso_now(),
        ":records": int(quality["generated_records"]),
        ":curated": int(quality["valid_records"]),
        ":quarantine": int(quality["invalid_records"]),
        ":duration": int(output["duration_ms"]),
        ":landing_bytes": int(output["landing_bytes"]),
        ":curated_bytes": int(output["curated_bytes"]),
        ":quarantine_bytes": int(output["quarantine_bytes"]),
        ":receipt_sha": str(output["receipt_sha256"]),
        ":receipt_key": str(output["receipt_key"]),
    }
    run_values = {
        ":at": partition_values[":at"],
        ":one": 1,
        ":records": partition_values[":records"],
        ":curated": partition_values[":curated"],
        ":quarantine": partition_values[":quarantine"],
        ":duration": partition_values[":duration"],
        ":landing_bytes": partition_values[":landing_bytes"],
        ":curated_bytes": partition_values[":curated_bytes"],
        ":quarantine_bytes": partition_values[":quarantine_bytes"],
        ":requested": "requested",
        ":partitioning": "partitioning",
    }
    try:
        _transact_write_with_conflict_retry(
            [
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize(_partition_key(message)),
                        "UpdateExpression": (
                            "SET #status = :completed, completed_at = :at, records = :records, "
                            "curated_records = :curated, quarantined_records = :quarantine, "
                            "duration_ms = :duration, landing_bytes = :landing_bytes, "
                            "curated_bytes = :curated_bytes, quarantine_bytes = :quarantine_bytes, "
                            "receipt_sha256 = :receipt_sha, receipt_key = :receipt_key"
                        ),
                        "ConditionExpression": (
                            "#status <> :completed AND #status <> :failed"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": _serialize(partition_values),
                        "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
                    }
                },
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize({"pk": f"RUN#{run_id}", "sk": "META"}),
                        "UpdateExpression": (
                            "SET updated_at = :at ADD completed_partitions :one, "
                            "generated_records :records, curated_records :curated, "
                            "quarantined_records :quarantine, raw_bytes :landing_bytes, "
                            "curated_bytes :curated_bytes, quarantine_bytes :quarantine_bytes, "
                            "worker_duration_ms :duration"
                        ),
                        "ConditionExpression": (
                            "#status = :requested OR #status = :partitioning"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": _serialize(run_values),
                        "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
                    }
                },
            ]
        )
        return True
    except Exception as exc:
        if _is_terminal_partition_cancellation(exc):
            _record_duplicate(run_id)
            return False
        raise


def _emit(profile: str, dataset: str, outcome: str, output: Mapping[str, Any]) -> None:
    receipt = output["receipt"]
    quality = receipt["quality"]
    payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "Compass/Scale",
                    "Dimensions": [["Profile", "Dataset", "Outcome"]],
                    "Metrics": [
                        {"Name": "Records", "Unit": "Count"},
                        {"Name": "InvalidRecords", "Unit": "Count"},
                        {"Name": "Duration", "Unit": "Milliseconds"},
                        {"Name": "CompressedBytes", "Unit": "Bytes"},
                    ],
                }
            ],
        },
        "Profile": profile,
        "Dataset": dataset,
        "Outcome": outcome,
        "Records": int(quality["generated_records"]),
        "InvalidRecords": int(quality["invalid_records"]),
        "Duration": int(output["duration_ms"]),
        "CompressedBytes": int(output["landing_bytes"]),
    }
    print(json.dumps(payload, sort_keys=True))


def _process(message: Mapping[str, Any], request_id: str) -> None:
    required = {
        "run_id",
        "profile_id",
        "seed",
        "dataset",
        "partition_id",
        "partition_ordinal",
        "start",
        "stop",
        "defect_rate_basis_points",
    }
    if not required.issubset(message):
        raise ValueError("partition message is incomplete")
    if not _mark_running(message, request_id):
        return
    output = _write_partition_files(message)
    committed = _commit(message, output)
    _emit(
        str(message["profile_id"]),
        str(message["dataset"]),
        "completed" if committed else "duplicate",
        output,
    )


def handler(event, context):
    failures = []
    for record in (event or {}).get("Records", []):
        message_id = str(record.get("messageId") or "unknown")
        message = None
        try:
            message = json.loads(record["body"])
            _process(message, getattr(context, "aws_request_id", "local-scale-worker"))
        except Exception as exc:
            logger.exception("Scale partition failed: %s", message_id)
            if (
                isinstance(message, Mapping)
                and {"run_id", "dataset", "partition_id"}.issubset(message)
                and _is_terminal_receive(record)
            ):
                try:
                    marked = _mark_partition_failed(message, exc)
                except Exception:
                    logger.exception(
                        "Scale partition terminal failure could not be recorded: %s",
                        message_id,
                    )
                else:
                    if not marked:
                        continue
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}

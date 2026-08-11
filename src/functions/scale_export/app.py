"""Retry-safe governed export manifest worker for Compass Scale Runs.

The worker never exposes a physical bucket name or object key. It hashes every
selected Parquet object, writes one canonical immutable manifest, and commits
the exact frontend export receipt into both the export item and run ledger.
SQS partial batch responses preserve independent retry behavior.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import re
from typing import Any, Mapping

from compass_common.scale_workload import (
    DATASETS,
    canonical_json_bytes,
    sha256_hex,
)


logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

MANIFEST_CONTRACT = "compass.scale-export-manifest.v1"
LEASE_SECONDS = 15 * 60
COMPLETED_RUN_STATES = {"completed", "completed_with_quarantine"}
CANCELED_RUN_STATES = {"canceling", "canceled", "cancelling", "cancelled", "failed"}
READY_EXPORT_STATES = {"ready", "completed"}
CANCELED_EXPORT_STATES = {"canceled", "cancelled"}
_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{7,95}")

_TABLE = None
_DDB = None
_S3 = None


class ExportCanceled(RuntimeError):
    """A terminal cancellation that should be acknowledged by SQS."""


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _safe_identifier(value: Any, field: str) -> str:
    text = str(value or "")
    if _SAFE_IDENTIFIER.fullmatch(text) is None:
        raise ValueError(f"{field} has an invalid format")
    return text


def _run_key(run_id: str) -> dict[str, str]:
    return {"pk": f"RUN#{run_id}", "sk": "META"}


def _export_key(run_id: str, export_id: str) -> dict[str, str]:
    return {"pk": f"RUN#{run_id}", "sk": f"EXPORT#{export_id}"}


def _get_item(key: Mapping[str, str]) -> dict[str, Any]:
    item = _table().get_item(Key=dict(key), ConsistentRead=True).get("Item")
    if not item:
        raise ValueError("Scale export ledger item was not found")
    return item


def _frontend_receipt(
    *,
    export_id: str,
    status: str,
    output_format: str,
    row_count: int,
    byte_count: int,
    object_uri: str | None,
    expires_at: str | None,
    sha256: str | None,
) -> dict[str, Any]:
    """Return the exact frontend ScaleExportReceipt field set."""

    return {
        "export_id": export_id,
        "status": status,
        "format": output_format,
        "row_count": row_count,
        "bytes": byte_count,
        "object_uri": object_uri,
        "download_url": None,
        "expires_at": expires_at,
        "sha256": sha256,
    }


def _is_condition_failure(exc: Exception) -> bool:
    name = type(exc).__name__
    if "ConditionalCheckFailed" in name or "TransactionCanceled" in name:
        return True
    response = getattr(exc, "response", {}) or {}
    code = response.get("Error", {}).get("Code")
    return code in {"ConditionalCheckFailedException", "TransactionCanceledException"}


def _claim(
    run_id: str,
    export_id: str,
    request_id: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    run = _get_item(_run_key(run_id))
    export = _get_item(_export_key(run_id, export_id))
    if str(export.get("run_id")) != run_id or str(export.get("export_id")) != export_id:
        raise ValueError("Scale export ledger identity does not match the message")
    export_status = str(export.get("status"))
    if export_status in READY_EXPORT_STATES:
        return None
    if export_status in CANCELED_EXPORT_STATES:
        raise ExportCanceled("Scale export is already canceled")
    run_status = str(run.get("status"))
    if run_status in CANCELED_RUN_STATES:
        _mark_canceled(run, export, "run_not_exportable")
        raise ExportCanceled("Scale Run was canceled before export")
    if run_status not in COMPLETED_RUN_STATES:
        raise RuntimeError("Scale Run is not complete")

    output_format = str(export.get("format") or "parquet").lower()
    if output_format != "parquet":
        raise ValueError("Scale export format must be parquet")
    dataset = str(export.get("dataset") or "curated_portfolio")
    if dataset != "curated_portfolio" and dataset not in DATASETS:
        raise ValueError("Scale export dataset is not supported")

    claimed_at = _iso()
    now_epoch = int(_now().timestamp())
    lease_epoch = now_epoch + LEASE_SECONDS
    building_receipt = _frontend_receipt(
        export_id=export_id,
        status="building",
        output_format=output_format,
        row_count=int(export.get("row_count", export.get("rows", 0))),
        byte_count=int(export.get("bytes", 0)),
        object_uri=None,
        expires_at=str(export.get("expires_at")) if export.get("expires_at") else None,
        sha256=None,
    )
    export_values = {
        ":queued": "queued",
        ":building": "building",
        ":now_epoch": now_epoch,
        ":lease_epoch": lease_epoch,
        ":at": claimed_at,
        ":request": request_id,
        ":one": 1,
    }
    run_values = {
        ":receipt": building_receipt,
        ":at": claimed_at,
        ":completed": "completed",
        ":completed_quarantine": "completed_with_quarantine",
    }
    try:
        _ddb().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize(_export_key(run_id, export_id)),
                        "UpdateExpression": (
                            "SET #status = :building, started_at = if_not_exists(started_at, :at), "
                            "worker_request_id = :request, lease_expires_at = :lease_epoch "
                            "ADD attempts :one"
                        ),
                        "ConditionExpression": (
                            "#status = :queued OR "
                            "(#status = :building AND lease_expires_at < :now_epoch)"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": _serialize(export_values),
                    }
                },
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize(_run_key(run_id)),
                        "UpdateExpression": "SET export_receipt = :receipt, updated_at = :at",
                        "ConditionExpression": (
                            "#status IN (:completed, :completed_quarantine)"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": _serialize(run_values),
                    }
                },
            ]
        )
    except Exception as exc:
        if not _is_condition_failure(exc):
            raise
        current = _get_item(_export_key(run_id, export_id))
        if str(current.get("status")) in READY_EXPORT_STATES:
            return None
        current_run = _get_item(_run_key(run_id))
        if str(current_run.get("status")) in CANCELED_RUN_STATES:
            _mark_canceled(current_run, current, "run_canceled_during_claim")
            raise ExportCanceled("Scale Run was canceled during export claim") from exc
        raise RuntimeError("Scale export is already owned by an active worker") from exc
    return run, {
        **export,
        "status": "building",
        "worker_request_id": request_id,
        "lease_expires_at": lease_epoch,
    }


def _mark_canceled(
    run: Mapping[str, Any], export: Mapping[str, Any], reason: str
) -> None:
    run_id = _safe_identifier(run.get("run_id"), "run_id")
    export_id = _safe_identifier(export.get("export_id"), "export_id")
    at = _iso()
    receipt = _frontend_receipt(
        export_id=export_id,
        status="cancelled",
        output_format=str(export.get("format") or "parquet"),
        row_count=int(export.get("row_count", export.get("rows", 0))),
        byte_count=int(export.get("bytes", 0)),
        object_uri=None,
        expires_at=str(export.get("expires_at")) if export.get("expires_at") else None,
        sha256=None,
    )
    _table().update_item(
        Key=_export_key(run_id, export_id),
        UpdateExpression=(
            "SET #status = :status, completed_at = :at, cancel_reason = :reason, "
            "row_count = :rows, #bytes = :bytes, object_uri = :null, "
            "download_url = :null, sha256 = :null REMOVE worker_request_id, lease_expires_at"
        ),
        ConditionExpression="#status <> :ready AND #status <> :completed",
        ExpressionAttributeNames={"#status": "status", "#bytes": "bytes"},
        ExpressionAttributeValues={
            ":status": "cancelled",
            ":at": at,
            ":reason": reason,
            ":rows": receipt["row_count"],
            ":bytes": receipt["bytes"],
            ":null": None,
            ":ready": "ready",
            ":completed": "completed",
        },
    )
    _table().update_item(
        Key=_run_key(run_id),
        UpdateExpression="SET export_receipt = :receipt, updated_at = :at",
        ExpressionAttributeValues={":receipt": receipt, ":at": at},
    )


def _assert_active(run_id: str, export_id: str, request_id: str) -> None:
    run = _get_item(_run_key(run_id))
    export = _get_item(_export_key(run_id, export_id))
    if str(run.get("status")) in CANCELED_RUN_STATES:
        _mark_canceled(run, export, "run_canceled_during_export")
        raise ExportCanceled("Scale Run was canceled during export")
    if str(run.get("status")) not in COMPLETED_RUN_STATES:
        raise RuntimeError("Scale Run is no longer exportable")
    if str(export.get("status")) in CANCELED_EXPORT_STATES:
        raise ExportCanceled("Scale export was canceled")
    if (
        str(export.get("status")) != "building"
        or str(export.get("worker_request_id")) != request_id
    ):
        raise RuntimeError("Scale export lease is no longer owned by this worker")


@dataclass(frozen=True)
class SourceObject:
    dataset: str
    key: str
    size: int


@dataclass(frozen=True)
class ExportArtifact:
    manifest: dict[str, Any]
    encoded: bytes
    manifest_sha256: str
    manifest_key: str
    row_count: int
    byte_count: int
    object_count: int
    object_uri: str


def _datasets_for_export(dataset: str) -> tuple[str, ...]:
    if dataset == "curated_portfolio":
        return DATASETS
    if dataset in DATASETS:
        return (dataset,)
    raise ValueError("Scale export dataset is not supported")


def _list_prefix(dataset: str, run_id: str) -> list[SourceObject]:
    prefix = f"parquet/{dataset}/run_id={run_id}/"
    token = None
    found: list[SourceObject] = []
    while True:
        request: dict[str, Any] = {
            "Bucket": os.environ["SCALE_LAKE_BUCKET"],
            "Prefix": prefix,
            "MaxKeys": 1_000,
        }
        if token:
            request["ContinuationToken"] = token
        response = _s3().list_objects_v2(**request)
        for item in response.get("Contents", []):
            key = str(item.get("Key") or "")
            size = int(item.get("Size", 0))
            if not key.startswith(prefix):
                raise RuntimeError("object listing escaped the governed export prefix")
            if size > 0:
                found.append(SourceObject(dataset=dataset, key=key, size=size))
        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")
        if not token:
            raise RuntimeError("object listing pagination token is missing")
    return found


def _list_sources(dataset: str, run_id: str) -> list[SourceObject]:
    sources = []
    for selected in _datasets_for_export(dataset):
        sources.extend(_list_prefix(selected, run_id))
    sources.sort(key=lambda item: (item.dataset, item.key))
    if not sources:
        raise RuntimeError("governed export has no source objects")
    return sources


def _read_body(body: Any, hasher: Any | None = None) -> tuple[bytes | None, int]:
    chunks = [] if hasher is None else None
    byte_count = 0
    while True:
        chunk = body.read(1024 * 1024)
        if not chunk:
            break
        byte_count += len(chunk)
        if hasher is None:
            chunks.append(chunk)
        else:
            hasher.update(chunk)
    return (b"".join(chunks) if chunks is not None else None), byte_count


def _hash_source(
    source: SourceObject,
    ordinal: int,
    run_id: str,
    export_id: str,
) -> dict[str, Any]:
    response = _s3().get_object(
        Bucket=os.environ["SCALE_LAKE_BUCKET"],
        Key=source.key,
        ChecksumMode="ENABLED",
    )
    hasher = hashlib.sha256()
    _, observed_size = _read_body(response["Body"], hasher)
    if observed_size != source.size:
        raise RuntimeError("source object size changed during export")
    digest = hasher.hexdigest()
    return {
        "ordinal": ordinal,
        "dataset": source.dataset,
        "logical_locator": (
            f"lake://scale-runs/{run_id}/exports/{export_id}/objects/"
            f"{ordinal:05d}-{digest[:12]}"
        ),
        "bytes": observed_size,
        "sha256": digest,
    }


def _dataset_row_count(run_id: str, dataset: str, run: Mapping[str, Any]) -> int:
    if dataset == "curated_portfolio":
        return int(run.get("curated_records", 0))
    total = 0
    start_key = None
    while True:
        request: dict[str, Any] = {
            "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
            "ExpressionAttributeValues": {
                ":pk": f"RUN#{run_id}",
                ":prefix": f"PART#{dataset}#",
            },
            "ProjectionExpression": "curated_records",
        }
        if start_key:
            request["ExclusiveStartKey"] = start_key
        response = _table().query(**request)
        total += sum(int(item.get("curated_records", 0)) for item in response.get("Items", []))
        start_key = response.get("LastEvaluatedKey")
        if not start_key:
            return total


def _is_precondition_failure(exc: Exception) -> bool:
    if "PreconditionFailed" in type(exc).__name__:
        return True
    response = getattr(exc, "response", {}) or {}
    return response.get("Error", {}).get("Code") in {"PreconditionFailed", "412"}


def _put_manifest_immutable(key: str, encoded: bytes, digest: str) -> None:
    checksum = base64.b64encode(bytes.fromhex(digest)).decode("ascii")
    try:
        _s3().put_object(
            Bucket=os.environ["SCALE_LAKE_BUCKET"],
            Key=key,
            Body=encoded,
            ContentType="application/json",
            ChecksumSHA256=checksum,
            Metadata={"sha256": digest, "synthetic-only": "true"},
            IfNoneMatch="*",
        )
    except Exception as exc:
        if not _is_precondition_failure(exc):
            raise
        response = _s3().get_object(
            Bucket=os.environ["SCALE_LAKE_BUCKET"], Key=key
        )
        existing, _ = _read_body(response["Body"])
        if existing is None or sha256_hex(existing) != digest or existing != encoded:
            raise RuntimeError("immutable export manifest already exists with different bytes") from exc


def _build_artifact(
    run: Mapping[str, Any],
    export: Mapping[str, Any],
    request_id: str,
) -> ExportArtifact:
    run_id = _safe_identifier(run.get("run_id"), "run_id")
    export_id = _safe_identifier(export.get("export_id"), "export_id")
    dataset = str(export.get("dataset") or "curated_portfolio")
    output_format = str(export.get("format") or "parquet")
    _assert_active(run_id, export_id, request_id)
    sources = _list_sources(dataset, run_id)
    evidence = []
    for ordinal, source in enumerate(sources):
        _assert_active(run_id, export_id, request_id)
        evidence.append(_hash_source(source, ordinal, run_id, export_id))
    _assert_active(run_id, export_id, request_id)
    row_count = _dataset_row_count(run_id, dataset, run)
    byte_count = sum(item["bytes"] for item in evidence)
    object_uri = f"lake://scale-runs/{run_id}/exports/{export_id}/manifest"
    manifest = {
        "contract_version": MANIFEST_CONTRACT,
        "run_id": run_id,
        "export_id": export_id,
        "dataset": dataset,
        "format": output_format,
        "synthetic_only": True,
        "created_at": (
            str(export.get("created_at")) if export.get("created_at") else None
        ),
        "expires_at": (
            str(export.get("expires_at")) if export.get("expires_at") else None
        ),
        "source_run_manifest_sha256": run.get("manifest_sha256"),
        "row_count": row_count,
        "bytes": byte_count,
        "object_count": len(evidence),
        "object_uri": object_uri,
        "objects": evidence,
    }
    encoded = canonical_json_bytes(manifest)
    manifest_sha = sha256_hex(encoded)
    manifest_key = f"exports/run_id={run_id}/{export_id}/manifest.json"
    _put_manifest_immutable(manifest_key, encoded, manifest_sha)
    return ExportArtifact(
        manifest=manifest,
        encoded=encoded,
        manifest_sha256=manifest_sha,
        manifest_key=manifest_key,
        row_count=row_count,
        byte_count=byte_count,
        object_count=len(evidence),
        object_uri=object_uri,
    )


def _commit(
    run: Mapping[str, Any],
    export: Mapping[str, Any],
    artifact: ExportArtifact,
    request_id: str,
) -> dict[str, Any]:
    run_id = _safe_identifier(run.get("run_id"), "run_id")
    export_id = _safe_identifier(export.get("export_id"), "export_id")
    at = _iso()
    receipt = _frontend_receipt(
        export_id=export_id,
        status="ready",
        output_format=str(export.get("format") or "parquet"),
        row_count=artifact.row_count,
        byte_count=artifact.byte_count,
        object_uri=artifact.object_uri,
        expires_at=str(export.get("expires_at")) if export.get("expires_at") else None,
        sha256=artifact.manifest_sha256,
    )
    audit_receipt = f"sha256:{artifact.manifest_sha256}"
    export_values = {
        ":building": "building",
        ":ready": "ready",
        ":worker": request_id,
        ":at": at,
        ":rows": artifact.row_count,
        ":bytes": artifact.byte_count,
        ":uri": artifact.object_uri,
        ":null": None,
        ":expires": receipt["expires_at"],
        ":sha": artifact.manifest_sha256,
        ":manifest_key": artifact.manifest_key,
        ":object_count": artifact.object_count,
        ":audit": audit_receipt,
    }
    run_values = {
        ":receipt": receipt,
        ":at": at,
        ":completed": "completed",
        ":completed_quarantine": "completed_with_quarantine",
    }
    try:
        _ddb().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize(_export_key(run_id, export_id)),
                        "UpdateExpression": (
                            "SET #status = :ready, completed_at = :at, row_count = :rows, "
                            "#bytes = :bytes, object_uri = :uri, download_url = :null, "
                            "expires_at = :expires, sha256 = :sha, manifest_sha256 = :sha, "
                            "manifest_key = :manifest_key, object_count = :object_count, "
                            "audit_receipt = :audit "
                            "REMOVE worker_request_id, lease_expires_at"
                        ),
                        "ConditionExpression": (
                            "#status = :building AND worker_request_id = :worker AND "
                            "attribute_not_exists(manifest_sha256)"
                        ),
                        "ExpressionAttributeNames": {
                            "#status": "status",
                            "#bytes": "bytes",
                        },
                        "ExpressionAttributeValues": _serialize(export_values),
                    }
                },
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize(_run_key(run_id)),
                        "UpdateExpression": "SET export_receipt = :receipt, updated_at = :at",
                        "ConditionExpression": (
                            "#status IN (:completed, :completed_quarantine)"
                        ),
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": _serialize(run_values),
                    }
                },
            ]
        )
    except Exception as exc:
        if not _is_condition_failure(exc):
            raise
        current = _get_item(_export_key(run_id, export_id))
        if (
            str(current.get("status")) in READY_EXPORT_STATES
            and str(current.get("sha256")) == artifact.manifest_sha256
        ):
            return receipt
        raise RuntimeError("Scale export receipt completion lost its conditional race") from exc
    return receipt


def _reset_for_retry(run_id: str, export_id: str, request_id: str) -> None:
    try:
        _table().update_item(
            Key=_export_key(run_id, export_id),
            UpdateExpression=(
                "SET #status = :queued, last_error = :error "
                "REMOVE worker_request_id, lease_expires_at"
            ),
            ConditionExpression="#status = :building AND worker_request_id = :request",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":queued": "queued",
                ":building": "building",
                ":request": request_id,
                ":error": "retryable_export_failure",
            },
        )
    except Exception:
        logger.exception("Unable to release Scale export lease for retry")


def _process(message: Mapping[str, Any], request_id: str) -> None:
    run_id = _safe_identifier(message.get("run_id"), "run_id")
    export_id = _safe_identifier(message.get("export_id"), "export_id")
    claimed = _claim(run_id, export_id, request_id)
    if claimed is None:
        return
    run, export = claimed
    artifact = _build_artifact(run, export, request_id)
    _assert_active(run_id, export_id, request_id)
    _commit(run, export, artifact, request_id)


def handler(event, context):
    failures = []
    request_id = getattr(context, "aws_request_id", "local-scale-export")
    for record in (event or {}).get("Records", []):
        message_id = str(record.get("messageId") or "unknown")
        run_id = export_id = None
        try:
            message = json.loads(record["body"])
            run_id = _safe_identifier(message.get("run_id"), "run_id")
            export_id = _safe_identifier(message.get("export_id"), "export_id")
            _process(message, request_id)
        except ExportCanceled:
            logger.info("Scale export canceled: %s", message_id)
        except Exception:
            logger.exception("Scale export failed: %s", message_id)
            if run_id and export_id:
                _reset_for_retry(run_id, export_id, request_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}

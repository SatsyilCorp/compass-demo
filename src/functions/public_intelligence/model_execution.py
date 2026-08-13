"""Bounded SageMaker smoke execution for the public SBIR transition candidate.

This module starts one ephemeral SageMaker Batch Transform smoke run from
an immutable public candidate pool. It never changes Model Registry approval,
creates no endpoint, and deletes the temporary SageMaker Model after a terminal
result. Request, input, output, and terminal receipt digests remain in the
KMS-encrypted raw bucket for audit.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping
from urllib.parse import urlparse

from compass_common import operational_evidence


CONTRACT = "compass.public-intelligence.model-execution.v1"
CANDIDATE_POOL_CONTRACT = "compass.public-intelligence.inference-candidates.v1"
EXECUTION_MODE = "sagemaker_batch_transform"
PURPOSE = "current_public_cohort_scoring"
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "STOPPED"}
MAX_SAMPLE_SIZE_HARD = 25
MAX_POOL_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_MODEL_BYTES = 64 * 1024 * 1024
MAX_RUNTIME_SECONDS_HARD = 1800
MAX_LIST_RECEIPTS = 10
EXECUTION_ID_PATTERN = re.compile(r"^sbir-batch-[0-9]{8}T[0-9]{6}-[a-f0-9]{8}$")
MODEL_NAME_PATTERN = re.compile(r"^compass-sbir-[a-z0-9-]{1,48}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REQUIRED_FEATURES = (
    "phase_i_amount_usd",
    "title_character_count",
    "abstract_character_count",
    "abstract_token_count",
    "award_year",
    "topic_family",
    "public_text",
)
ALLOWED_RECORD_KEYS = {"eventTime", "recordId", "sourceRecordIds", "features"}
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

_S3_CLIENT: Any = None
_SAGEMAKER_CLIENT: Any = None
_SCHEDULER_CLIENT: Any = None


class ExecutionError(RuntimeError):
    """A governed model execution could not be completed."""


class ExecutionConflict(ExecutionError):
    """Another cost-bounded execution is already active."""

    def __init__(self, message: str, *, execution_id: str | None = None):
        super().__init__(message)
        self.execution_id = execution_id


class ExecutionNotFound(ExecutionError):
    """The requested execution receipt does not exist."""


class ReceiptWriteConflict(ExecutionError):
    """A newer receipt version won a conditional write."""


def _s3_client() -> Any:
    global _S3_CLIENT
    if _S3_CLIENT is None:
        import boto3

        _S3_CLIENT = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _S3_CLIENT


def _sagemaker_client() -> Any:
    global _SAGEMAKER_CLIENT
    if _SAGEMAKER_CLIENT is None:
        import boto3

        _SAGEMAKER_CLIENT = boto3.client(
            "sagemaker", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
    return _SAGEMAKER_CLIENT


def _scheduler_client() -> Any:
    global _SCHEDULER_CLIENT
    if _SCHEDULER_CLIENT is None:
        import boto3

        _SCHEDULER_CLIENT = boto3.client(
            "scheduler", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
    return _SCHEDULER_CLIENT


def _required_env(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise ExecutionError(f"model execution configuration is missing {name}")
    return value


def _execution_enabled() -> bool:
    return str(os.environ.get("PUBLIC_SBIR_EXECUTION_ENABLED") or "").strip().lower() == "true"


def _now() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _clean_text(value: Any, *, max_chars: int = 500) -> str:
    return " ".join(
        str(value or "").replace("\u2014", " - ").replace("\u2013", "-").split()
    )[:max_chars]


def _bucket() -> str:
    return _required_env("PUBLIC_SBIR_EXECUTION_BUCKET")


def _prefix() -> str:
    value = _required_env("PUBLIC_SBIR_EXECUTION_PREFIX").strip("/")
    if not value.startswith("mlops/public-sbir-transition/executions") or ".." in value:
        raise ExecutionError("model execution prefix is outside the governed boundary")
    return value


def _kms_key_arn() -> str:
    value = _required_env("PUBLIC_SBIR_EXECUTION_KMS_KEY_ARN")
    if not value.startswith("arn:") or ":kms:" not in value:
        raise ExecutionError("model execution KMS key ARN is invalid")
    return value


def _max_sample_size() -> int:
    try:
        value = int(os.environ.get("PUBLIC_SBIR_EXECUTION_MAX_RECORDS", "25"))
    except ValueError as exc:
        raise ExecutionError("model execution sample limit is invalid") from exc
    return max(1, min(value, MAX_SAMPLE_SIZE_HARD))


def _max_runtime_seconds() -> int:
    try:
        value = int(os.environ.get("PUBLIC_SBIR_EXECUTION_MAX_RUNTIME_SECONDS", "1800"))
    except ValueError as exc:
        raise ExecutionError("model execution runtime limit is invalid") from exc
    return max(300, min(value, MAX_RUNTIME_SECONDS_HARD))


def _instance_price() -> float:
    try:
        value = float(os.environ.get("PUBLIC_SBIR_M5_LARGE_PRICE_USD_HOUR", "0.115"))
    except ValueError as exc:
        raise ExecutionError("model execution price estimate is invalid") from exc
    if value <= 0 or value > 10:
        raise ExecutionError("model execution price estimate is outside the allowed range")
    return value


def parse_start_request(body: Mapping[str, Any]) -> int:
    unknown = set(body) - {"sampleSize"}
    if unknown:
        raise ValueError("unsupported request fields: " + ", ".join(sorted(unknown)))
    try:
        sample_size = int(body.get("sampleSize", 8))
    except (TypeError, ValueError) as exc:
        raise ValueError("'sampleSize' must be an integer") from exc
    if isinstance(body.get("sampleSize"), bool):
        raise ValueError("'sampleSize' must be an integer")
    if sample_size < 1 or sample_size > _max_sample_size():
        raise ValueError(f"'sampleSize' must be between 1 and {_max_sample_size()}")
    return sample_size


def validate_execution_id(value: Any) -> str:
    execution_id = str(value or "").strip()
    if not EXECUTION_ID_PATTERN.fullmatch(execution_id):
        raise ValueError("execution ID is invalid")
    return execution_id


def _read_object(key: str, *, max_bytes: int) -> tuple[bytes, str | None]:
    return _read_object_version(key, max_bytes=max_bytes, version_id=None)


def _read_object_version(
    key: str,
    *,
    max_bytes: int,
    version_id: str | None,
) -> tuple[bytes, str | None]:
    request: dict[str, Any] = {"Bucket": _bucket(), "Key": key}
    if version_id:
        request["VersionId"] = version_id
    try:
        response = _s3_client().get_object(**request)
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            raise ExecutionNotFound("model execution receipt was not found") from exc
        raise ExecutionError("governed model execution evidence is unavailable") from exc
    content_length = int(response.get("ContentLength") or 0)
    if content_length and content_length > max_bytes:
        raise ExecutionError("governed model execution object exceeds its size limit")
    raw = response["Body"].read(max_bytes + 1)
    close = getattr(response["Body"], "close", None)
    if callable(close):
        close()
    if len(raw) > max_bytes:
        raise ExecutionError("governed model execution object exceeds its size limit")
    version = response.get("VersionId")
    return raw, str(version) if version else None


def _put_object(key: str, raw: bytes, *, if_none_match: bool = False) -> str | None:
    request: dict[str, Any] = {
        "Bucket": _bucket(),
        "Key": key,
        "Body": raw,
        "ContentType": "application/json",
        "ServerSideEncryption": "aws:kms",
        "SSEKMSKeyId": _kms_key_arn(),
    }
    if if_none_match:
        request["IfNoneMatch"] = "*"
    try:
        response = _s3_client().put_object(**request)
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"}:
            raise ExecutionConflict("another bounded model execution is active") from exc
        raise
    version = response.get("VersionId")
    return str(version) if version else None


def _put_model_artifact(key: str, raw: bytes) -> str | None:
    response = _s3_client().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=raw,
        ContentType="application/gzip",
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=_kms_key_arn(),
        IfNoneMatch="*",
    )
    version = response.get("VersionId")
    return str(version) if version else None


def _delete_object(key: str) -> None:
    _s3_client().delete_object(Bucket=_bucket(), Key=key)


def _read_json(key: str, *, max_bytes: int) -> tuple[dict[str, Any], bytes, str | None]:
    raw, version = _read_object(key, max_bytes=max_bytes)
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ExecutionError("governed model execution evidence is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ExecutionError("governed model execution evidence must be an object")
    return value, raw, version


def _read_json_with_etag(
    key: str, *, max_bytes: int
) -> tuple[dict[str, Any], bytes, str | None, str]:
    try:
        response = _s3_client().get_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            raise ExecutionNotFound("model execution receipt was not found") from exc
        raise ExecutionError("governed model execution evidence is unavailable") from exc
    content_length = int(response.get("ContentLength") or 0)
    if content_length and content_length > max_bytes:
        raise ExecutionError("governed model execution object exceeds its size limit")
    raw = response["Body"].read(max_bytes + 1)
    close = getattr(response["Body"], "close", None)
    if callable(close):
        close()
    if len(raw) > max_bytes:
        raise ExecutionError("governed model execution object exceeds its size limit")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ExecutionError("governed model execution evidence is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ExecutionError("governed model execution evidence must be an object")
    etag = str(response.get("ETag") or "").strip()
    if not etag:
        raise ExecutionError("governed model execution object has no conditional token")
    version = response.get("VersionId")
    return value, raw, str(version) if version else None, etag


def _pool() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    key = _required_env("PUBLIC_SBIR_CANDIDATE_POOL_KEY")
    value, raw, version = _read_json(key, max_bytes=MAX_POOL_BYTES)
    expected_sha = _required_env("PUBLIC_SBIR_CANDIDATE_POOL_SHA256")
    if not SHA256_PATTERN.fullmatch(expected_sha) or _sha256(raw) != expected_sha:
        raise ExecutionError("public SBIR candidate pool failed digest validation")
    boundary = value.get("dataBoundary")
    if value.get("contract") != CANDIDATE_POOL_CONTRACT or not isinstance(boundary, dict):
        raise ExecutionError("public SBIR candidate pool contract is invalid")
    if boundary != {
        "classification": "public",
        "containsCui": False,
        "labelsExcluded": True,
        "piiMinimized": True,
    }:
        raise ExecutionError("public SBIR candidate pool boundary is not permitted")
    source_dataset = value.get("sourceDataset")
    selection = value.get("selection")
    if (
        not isinstance(source_dataset, dict)
        or source_dataset.get("datasetId")
        != "navy-sbir-current-phase-i-public-scoring"
        or not SHA256_PATTERN.fullmatch(str(source_dataset.get("sha256") or ""))
        or not isinstance(selection, dict)
        or selection.get("cutoffExclusive") != "2023-12-31"
    ):
        raise ExecutionError("public SBIR scoring cohort provenance is invalid")
    records = value.get("records")
    if not isinstance(records, list) or not records or len(records) > MAX_SAMPLE_SIZE_HARD:
        raise ExecutionError("public SBIR candidate pool record count is invalid")
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != ALLOWED_RECORD_KEYS:
            raise ExecutionError("public SBIR candidate record contract is invalid")
        record_id = _clean_text(record.get("recordId"), max_chars=120)
        features = record.get("features")
        if not record_id or record_id in seen or not isinstance(features, dict):
            raise ExecutionError("public SBIR candidate record identity is invalid")
        if set(features) != set(REQUIRED_FEATURES):
            raise ExecutionError("public SBIR candidate feature contract is invalid")
        public_text = _clean_text(features.get("public_text"), max_chars=10_000)
        if not public_text or EMAIL_PATTERN.search(public_text):
            raise ExecutionError("public SBIR candidate text failed minimization validation")
        try:
            event_time = _parse_timestamp(record.get("eventTime"))
        except (TypeError, ValueError) as exc:
            raise ExecutionError("public SBIR candidate event time is invalid") from exc
        if event_time.date().isoformat() <= str(selection["cutoffExclusive"]):
            raise ExecutionError("public SBIR scoring record overlaps the model evaluation cohort")
        normalized = {
            "recordId": record_id,
            "eventTime": _timestamp(event_time),
            "sourceRecordIds": [
                _clean_text(item, max_chars=120)
                for item in record.get("sourceRecordIds") or []
                if _clean_text(item, max_chars=120)
            ][:10],
            "features": {
                "phase_i_amount_usd": float(features["phase_i_amount_usd"]),
                "title_character_count": int(features["title_character_count"]),
                "abstract_character_count": int(features["abstract_character_count"]),
                "abstract_token_count": int(features["abstract_token_count"]),
                "award_year": int(features["award_year"]),
                "topic_family": _clean_text(features["topic_family"], max_chars=80),
                "public_text": public_text,
            },
        }
        seen.add(record_id)
        cleaned.append(normalized)
    if int(selection.get("recordCount") or 0) != len(cleaned):
        raise ExecutionError("public SBIR scoring cohort record count is invalid")
    return cleaned, {
        "sha256": expected_sha,
        "versionId": version,
        "sourceDataset": source_dataset,
        "selection": selection,
    }


def _model_package() -> dict[str, Any]:
    package_arn = _required_env("PUBLIC_SBIR_MODEL_PACKAGE_ARN")
    expected_group_arn = _required_env("PUBLIC_SBIR_MODEL_PACKAGE_GROUP_ARN")
    expected_package_prefix = expected_group_arn.replace(
        "model-package-group/", "model-package/"
    ) + "/"
    if not package_arn.startswith(expected_package_prefix):
        raise ExecutionError("public SBIR model package is outside the configured registry")
    detail = _sagemaker_client().describe_model_package(ModelPackageName=package_arn)
    approval = str(detail.get("ModelApprovalStatus") or "")
    if detail.get("ModelPackageStatus") != "Completed" or approval != "PendingManualApproval":
        raise ExecutionError("public SBIR model package is not a pending completed candidate")
    containers = (detail.get("InferenceSpecification") or {}).get("Containers") or []
    if len(containers) != 1:
        raise ExecutionError("public SBIR model package inference contract is invalid")
    container = containers[0]
    model_data_url = str(container.get("ModelDataUrl") or "")
    parsed = urlparse(model_data_url)
    model_data_key = parsed.path.lstrip("/")
    expected_model_data_key = _required_env("PUBLIC_SBIR_MODEL_DATA_KEY")
    if (
        parsed.scheme != "s3"
        or parsed.netloc != _bucket()
        or model_data_key != expected_model_data_key
    ):
        raise ExecutionError("public SBIR model artifact is outside the governed boundary")
    image = str(container.get("Image") or "")
    image_digest = str(container.get("ImageDigest") or "")
    expected_image_digest = _required_env("PUBLIC_SBIR_IMAGE_DIGEST")
    environment = dict(container.get("Environment") or {})
    if (
        not image
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", expected_image_digest)
        or image_digest != expected_image_digest
    ):
        raise ExecutionError("public SBIR inference image is not digest-bound")
    if environment.get("SAGEMAKER_PROGRAM") != "inference.py":
        raise ExecutionError("public SBIR inference program is invalid")
    model_metrics = detail.get("ModelMetrics") or {}
    statistics = ((model_metrics.get("ModelQuality") or {}).get("Statistics") or {})
    card_digest = str(statistics.get("ContentDigest") or "").removeprefix("SHA256:")
    metadata = detail.get("CustomerMetadataProperties") or {}
    expected_training_arn = _required_env("PUBLIC_SBIR_TRAINING_JOB_ARN")
    expected_training_name = expected_training_arn.rsplit("/", 1)[-1]
    expected_artifact_sha = _required_env("PUBLIC_SBIR_MODEL_ARTIFACT_SHA256")
    expected_bundle_sha = _required_env("PUBLIC_SBIR_MODEL_BUNDLE_SHA256")
    expected_card_sha = _required_env("PUBLIC_SBIR_MODEL_CARD_SHA256")
    if (
        not SHA256_PATTERN.fullmatch(expected_artifact_sha)
        or not SHA256_PATTERN.fullmatch(expected_bundle_sha)
        or not SHA256_PATTERN.fullmatch(expected_card_sha)
        or card_digest != expected_card_sha
        or metadata.get("training_job") != expected_training_name
        or metadata.get("artifact_sha256") != expected_artifact_sha
        or metadata.get("registry_bundle_sha256") != expected_bundle_sha
    ):
        raise ExecutionError("public SBIR package provenance does not match the pinned candidate")
    expected_version = _required_env("PUBLIC_SBIR_MODEL_DATA_VERSION_ID")
    model_raw, actual_version = _read_object_version(
        model_data_key,
        max_bytes=MAX_MODEL_BYTES,
        version_id=expected_version,
    )
    if actual_version != expected_version or _sha256(model_raw) != expected_bundle_sha:
        raise ExecutionError("public SBIR model artifact failed exact digest validation")
    image_repository = image.split("@", 1)[0].rsplit(":", 1)[0]
    return {
        "name": "Public Navy SBIR transition candidate",
        "packageArn": package_arn,
        "packageVersion": int(package_arn.rsplit("/", 1)[-1]),
        "approvalStatus": approval,
        "candidateOnly": True,
        "trainingJobArn": expected_training_arn,
        "modelArtifactSha256": expected_artifact_sha,
        "modelBundleSha256": expected_bundle_sha,
        "modelArtifactSourceVersionId": actual_version,
        "modelCardSha256": card_digest,
        "image": f"{image_repository}@{image_digest}",
        "imageDigest": image_digest,
        "modelData": model_raw,
        "environment": environment,
    }


def _execution_key(execution_id: str, name: str) -> str:
    return f"{_prefix()}/{execution_id}/{name}"


def _execution_data_key(execution_id: str, name: str) -> str:
    return f"{_prefix()}/data/{execution_id}/{name}"


def _receipt_key(execution_id: str) -> str:
    return _execution_key(execution_id, "receipt.json")


def _history_key(execution_id: str) -> str:
    return f"{_prefix()}/history/{execution_id}.json"


def _lock_key() -> str:
    return f"{_prefix()}/control/active.json"


def _receipt_for_response(
    receipt: dict[str, Any], raw: bytes, version_id: str | None
) -> dict[str, Any]:
    response = json.loads(json.dumps(receipt))
    provenance = response.setdefault("provenance", {})
    provenance["receiptSha256"] = _sha256(raw)
    provenance["receiptVersionId"] = version_id
    return response


def _write_receipt(
    receipt: dict[str, Any],
    *,
    expected_etag: str | None = None,
    create: bool = False,
) -> dict[str, Any]:
    raw = _canonical_json(receipt)
    request: dict[str, Any] = {
        "Bucket": _bucket(),
        "Key": _receipt_key(receipt["executionId"]),
        "Body": raw,
        "ContentType": "application/json",
        "ServerSideEncryption": "aws:kms",
        "SSEKMSKeyId": _kms_key_arn(),
    }
    if create:
        request["IfNoneMatch"] = "*"
    elif expected_etag:
        request["IfMatch"] = expected_etag
    try:
        response = _s3_client().put_object(**request)
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"}:
            raise ReceiptWriteConflict("model execution receipt changed concurrently") from exc
        raise
    version = response.get("VersionId")
    pointer = {
        "contract": "compass.public-intelligence.model-execution-pointer.v1",
        "executionId": receipt["executionId"],
        "createdAt": receipt["createdAt"],
        "updatedAt": receipt["updatedAt"],
        "status": receipt["status"],
        "receiptSha256": _sha256(raw),
    }
    _put_object(_history_key(receipt["executionId"]), _canonical_json(pointer))
    return _receipt_for_response(
        receipt,
        raw,
        str(version) if version else None,
    )


def _read_receipt(execution_id: str) -> tuple[dict[str, Any], bytes, str | None]:
    receipt, raw, version = _read_json(_receipt_key(execution_id), max_bytes=MAX_OUTPUT_BYTES)
    if receipt.get("contract") != CONTRACT or receipt.get("executionId") != execution_id:
        raise ExecutionError("model execution receipt contract is invalid")
    return receipt, raw, version


def _read_receipt_with_etag(
    execution_id: str,
) -> tuple[dict[str, Any], bytes, str | None, str]:
    receipt, raw, version, etag = _read_json_with_etag(
        _receipt_key(execution_id), max_bytes=MAX_OUTPUT_BYTES
    )
    if receipt.get("contract") != CONTRACT or receipt.get("executionId") != execution_id:
        raise ExecutionError("model execution receipt contract is invalid")
    return receipt, raw, version, etag


def _latest_receipt_response(execution_id: str) -> dict[str, Any]:
    latest, raw, version = _read_receipt(execution_id)
    return _receipt_for_response(latest, raw, version)


def _write_reconciled_receipt(
    receipt: dict[str, Any], *, expected_etag: str
) -> dict[str, Any]:
    try:
        return _write_receipt(receipt, expected_etag=expected_etag)
    except ReceiptWriteConflict:
        return _latest_receipt_response(receipt["executionId"])


def _release_lock(execution_id: str) -> bool:
    try:
        lock, _, _, etag = _read_json_with_etag(_lock_key(), max_bytes=4096)
    except ExecutionNotFound:
        return True
    if lock.get("executionId") != execution_id:
        return False
    try:
        _s3_client().delete_object(Bucket=_bucket(), Key=_lock_key(), IfMatch=etag)
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "NotFound", "404"}:
            return True
        if code in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"}:
            return False
        raise
    return True


def _acquire_lock(execution_id: str, created_at: str) -> None:
    lock = {
        "contract": "compass.public-intelligence.model-execution-lock.v1",
        "executionId": execution_id,
        "createdAt": created_at,
        "maxRuntimeSeconds": _max_runtime_seconds(),
    }
    try:
        _put_object(_lock_key(), _canonical_json(lock), if_none_match=True)
    except ExecutionConflict as exc:
        try:
            current, _, _ = _read_json(_lock_key(), max_bytes=4096)
            current_id = validate_execution_id(current.get("executionId"))
            current_created = _parse_timestamp(current.get("createdAt"))
            stale = int((_now() - current_created).total_seconds()) > (
                int(current.get("maxRuntimeSeconds") or _max_runtime_seconds()) + 300
            )
        except Exception:
            current_id = None
            stale = False
        if stale and current_id:
            try:
                current_receipt, _, _ = _read_receipt(current_id)
                if current_receipt.get("status") in TERMINAL_STATUSES:
                    reconciled = get_execution(current_id)
                    if (
                        reconciled.get("execution", {}).get(
                            "temporaryModelCleanupStatus"
                        )
                        == "DELETED"
                    ):
                        _put_object(
                            _lock_key(),
                            _canonical_json(lock),
                            if_none_match=True,
                        )
                        return
                job_name = current_receipt["execution"]["transformJobName"]
                detail = _sagemaker_client().describe_transform_job(
                    TransformJobName=job_name
                )
                if detail.get("TransformJobStatus") == "InProgress":
                    _sagemaker_client().stop_transform_job(TransformJobName=job_name)
                elif detail.get("TransformJobStatus") in {
                    "Completed",
                    "Failed",
                    "Stopped",
                }:
                    get_execution(current_id)
            except Exception:
                pass
        raise ExecutionConflict(
            "another bounded model execution is active", execution_id=current_id
        ) from exc


def list_executions() -> dict[str, Any]:
    response = _s3_client().list_objects_v2(
        Bucket=_bucket(),
        Prefix=f"{_prefix()}/history/",
        MaxKeys=100,
    )
    identifiers = []
    for item in response.get("Contents") or []:
        key = str(item.get("Key") or "")
        name = key.rsplit("/", 1)[-1].removesuffix(".json")
        if EXECUTION_ID_PATTERN.fullmatch(name):
            identifiers.append(name)
    receipts = []
    for execution_id in sorted(identifiers, reverse=True)[:MAX_LIST_RECEIPTS]:
        try:
            receipts.append(get_execution(execution_id))
        except (ExecutionError, ExecutionNotFound):
            continue
    receipts.sort(key=lambda value: str(value.get("createdAt") or ""), reverse=True)
    return {
        "contract": "compass.public-intelligence.model-execution-list.v1",
        "executions": receipts,
    }


def _delete_model(model_name: str) -> str:
    if not MODEL_NAME_PATTERN.fullmatch(model_name):
        return "REFUSED_INVALID_NAME"
    try:
        _sagemaker_client().delete_model(ModelName=model_name)
        return "DELETED"
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        message = str(getattr(exc, "response", {}).get("Error", {}).get("Message", ""))
        if code in {"ResourceNotFound", "ResourceNotFoundException"} or (
            code == "ValidationException"
            and "Could not find model" in message
            and model_name in message
        ):
            return "DELETED"
        return "DELETE_PENDING"


def _schedule_name(execution_id: str) -> str:
    name = (
        f"{os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'compass')}"
        f"-sbir-{execution_id.rsplit('-', 1)[-1]}"
    )
    return name[:64]


def _schedule_reconciliation(execution_id: str, *, created_at: datetime) -> str:
    role_arn = _required_env("PUBLIC_SBIR_RECONCILIATION_ROLE_ARN")
    function_arn = _required_env("PUBLIC_SBIR_RECONCILIATION_FUNCTION_ARN")
    dead_letter_arn = _required_env("PUBLIC_SBIR_RECONCILIATION_DLQ_ARN")
    schedule_name = _schedule_name(execution_id)
    response = _scheduler_client().create_schedule(
        Name=schedule_name,
        GroupName="default",
        ScheduleExpression="rate(1 minute)",
        ScheduleExpressionTimezone="UTC",
        StartDate=created_at + timedelta(seconds=300),
        EndDate=created_at + timedelta(seconds=_max_runtime_seconds() + 86400),
        FlexibleTimeWindow={"Mode": "OFF"},
        ActionAfterCompletion="DELETE",
        Target={
            "Arn": function_arn,
            "RoleArn": role_arn,
            "Input": json.dumps(
                {
                    "source": "aws.scheduler",
                    "detail-type": "Public SBIR Reconciliation",
                    "executionId": execution_id,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "RetryPolicy": {
                "MaximumEventAgeInSeconds": 3600,
                "MaximumRetryAttempts": 5,
            },
            "DeadLetterConfig": {"Arn": dead_letter_arn},
        },
        Description=f"Bounded cleanup guard for {execution_id}",
        ClientToken=execution_id,
    )
    return str(response.get("ScheduleArn") or schedule_name)


def _delete_reconciliation_schedule(execution_id: str) -> None:
    try:
        _scheduler_client().delete_schedule(
            Name=_schedule_name(execution_id),
            GroupName="default",
        )
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in {"ResourceNotFoundException", "ResourceNotFound", "404"}:
            return
        raise


def _is_missing_transform(exc: Exception, transform_name: str) -> bool:
    error = getattr(exc, "response", {}).get("Error", {})
    code = str(error.get("Code", ""))
    message = str(error.get("Message", ""))
    if code in {"ResourceNotFound", "ResourceNotFoundException"}:
        return True
    normalized = message.lower()
    return (
        code == "ValidationException"
        and "could not find" in normalized
        and transform_name.lower() in normalized
    )


def _record_terminal_evidence(receipt: Mapping[str, Any]) -> None:
    execution_id = str(receipt.get("executionId") or "")
    if not execution_id:
        return
    status = str(receipt.get("status") or "FAILED")
    completed = status == "COMPLETED"
    model = receipt.get("model") if isinstance(receipt.get("model"), Mapping) else {}
    input_state = receipt.get("input") if isinstance(receipt.get("input"), Mapping) else {}
    output = receipt.get("output") if isinstance(receipt.get("output"), Mapping) else {}
    provenance = (
        receipt.get("provenance")
        if isinstance(receipt.get("provenance"), Mapping)
        else {}
    )
    model_version = f"package-{model.get('packageVersion', 'candidate')}"
    source_sha256 = str(provenance.get("candidatePoolSha256") or "") or None
    input_sha256 = str(input_state.get("sha256") or "") or None
    output_sha256 = str(output.get("sha256") or "") or None
    record_count = input_state.get("recordCount")
    created_at = str(
        receipt.get("createdAt")
        or receipt.get("updatedAt")
        or operational_evidence.utc_now()
    )
    terminal_at = str(
        receipt.get("completedAt") or receipt.get("updatedAt") or created_at
    )
    # Recreate the complete evidence chain while reconciling a terminal run.
    # This also backfills historical governed executions created before the
    # operational projection was introduced, using only their signed receipt.
    operational_evidence.record_stage(
        run_id=execution_id,
        run_kind="sagemaker-batch-inference",
        sequence=1,
        stage_id="input-sealed",
        label="Current public scoring cohort sealed",
        status="completed",
        source="public-evidence://navy-sbir-current-phase-i-public-scoring",
        destination=f"model-execution://public-sbir-transition/{execution_id}/input",
        source_sha256=source_sha256,
        output_sha256=input_sha256,
        actor="sagemaker-reconciler",
        occurred_at=created_at,
        detail={
            "record_count": record_count,
            "model_version": model_version,
            "evidence_class": "public-observed",
        },
    )
    operational_evidence.record_stage(
        run_id=execution_id,
        run_kind="sagemaker-batch-inference",
        sequence=2,
        stage_id="batch-transform",
        label=(
            "Network-isolated SageMaker Batch Transform completed"
            if completed
            else "Network-isolated SageMaker Batch Transform failed"
        ),
        status="completed" if completed else "failed",
        source=f"model-execution://public-sbir-transition/{execution_id}/input",
        destination=f"model-execution://public-sbir-transition/{execution_id}/output",
        input_sha256=input_sha256,
        output_sha256=output_sha256,
        actor="sagemaker-reconciler",
        occurred_at=terminal_at,
        detail={
            "record_count": record_count,
            "model_version": model_version,
            "consumer": "SageMaker reconciliation control",
        },
    )
    operational_evidence.record_stage(
        run_id=execution_id,
        run_kind="sagemaker-batch-inference",
        sequence=3,
        stage_id="prediction-reconciled" if completed else "prediction-failed",
        label=(
            "SageMaker predictions validated and reconciled"
            if completed
            else "SageMaker prediction run failed closed"
        ),
        status="completed" if completed else "failed",
        source="model-registry://public-sbir-transition/candidate",
        destination=(
            "mission-workspace://public-intelligence/model-signals"
            if completed
            else "model-operations://review-queue"
        ),
        source_sha256=source_sha256,
        input_sha256=input_sha256,
        output_sha256=output_sha256,
        actor="sagemaker-reconciler",
        occurred_at=terminal_at,
        detail={
            "accepted_records": output.get("predictionCount") if completed else 0,
            "failed_records": 0 if completed else input_state.get("recordCount"),
            "model_version": model_version,
            "record_count": record_count,
            "consumer": "Public Intelligence review queue",
        },
    )
    operational_evidence.record_signal(
        category="model-execution",
        severity="info" if completed else "high",
        title=(
            "SageMaker batch predictions completed"
            if completed
            else "SageMaker batch prediction failed"
        ),
        message=(
            "The bounded public cohort was scored and its prediction output passed receipt validation."
            if completed
            else "The bounded model run failed closed. The candidate approval state and prior evidence remain unchanged."
        ),
        run_id=execution_id,
        evidence_uri=f"model-execution://public-sbir-transition/{execution_id}",
        occurred_at=terminal_at,
        detail={
            "accepted_records": output.get("predictionCount") if completed else 0,
            "failed_records": 0 if completed else record_count,
            "model_version": model_version,
            "record_count": record_count,
        },
    )


def start_execution(*, sample_size: int, request_id: str, actor_role: str) -> dict[str, Any]:
    if not _execution_enabled():
        raise ExecutionError(
            "public SBIR execution is disabled until pinned model evidence is provisioned"
        )
    created = _now()
    execution_id = f"sbir-batch-{created.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    created_at = _timestamp(created)
    model_name = "compass-sbir-" + execution_id.rsplit("-", 1)[-1]
    transform_name = execution_id
    schedule_arn = _schedule_reconciliation(execution_id, created_at=created)
    try:
        _acquire_lock(execution_id, created_at)
    except Exception:
        _delete_reconciliation_schedule(execution_id)
        raise
    receipt: dict[str, Any] | None = None
    receipt_etag: str | None = None
    transform_submission_attempted = False
    schedule_created = True
    try:
        candidates, pool_provenance = _pool()
        selected = candidates[:sample_size]
        model = _model_package()
        input_lines = []
        input_records = []
        for candidate in selected:
            record = {"record_id": candidate["recordId"], **candidate["features"]}
            input_lines.append(_canonical_json(record))
            input_records.append(
                {
                    "recordId": candidate["recordId"],
                    "eventTime": candidate["eventTime"],
                    "sourceRecordIds": candidate["sourceRecordIds"],
                }
            )
        input_raw = b"\n".join(input_lines) + b"\n"
        input_key = _execution_data_key(execution_id, "input/batch.jsonl")
        input_version = _put_object(input_key, input_raw)
        input_sha = _sha256(input_raw)
        execution_model_key = _execution_data_key(execution_id, "model/model.tar.gz")
        execution_model_version = _put_model_artifact(
            execution_model_key,
            model["modelData"],
        )
        execution_model_url = f"s3://{_bucket()}/{execution_model_key}"
        receipt = {
            "contract": CONTRACT,
            "version": 1,
            "executionId": execution_id,
            "status": "SUBMITTED",
            "createdAt": created_at,
            "updatedAt": created_at,
            "completedAt": None,
            "purpose": PURPOSE,
            "executionMode": EXECUTION_MODE,
            "model": {
                key: value
                for key, value in model.items()
                if key not in {"image", "environment", "modelData"}
            },
            "input": {
                "recordCount": len(selected),
                "sha256": input_sha,
                "records": input_records,
            },
            "execution": {
                "transformJobArn": None,
                "transformJobName": transform_name,
                "instanceType": "ml.m5.large",
                "instanceCount": 1,
                "networkIsolation": True,
                "maxRuntimeSeconds": _max_runtime_seconds(),
                "temporaryModelName": model_name,
                "temporaryModelCleanupStatus": "PENDING",
                "reconciliationSchedule": schedule_arn,
            },
            "output": None,
            "cost": None,
            "provenance": {
                "requestId": _clean_text(request_id, max_chars=120),
                "actorRole": _clean_text(actor_role, max_chars=32),
                "candidatePoolSha256": pool_provenance["sha256"],
                "candidatePoolVersionId": pool_provenance["versionId"],
                "sourceDataset": pool_provenance["sourceDataset"],
                "selection": pool_provenance["selection"],
                "inputVersionId": input_version,
                "executionModelVersionId": execution_model_version,
                "outputVersionId": None,
            },
            "humanReviewRequired": True,
            "disclosure": "Current public post-cutoff cohort scoring only. This run produces review-only transition signals for newer public Navy Phase I records. It does not approve the candidate and does not predict ONR mission success.",
        }
        _write_receipt(receipt, create=True)
        operational_evidence.record_stage(
            run_id=execution_id,
            run_kind="sagemaker-batch-inference",
            sequence=1,
            stage_id="input-sealed",
            label="Current public scoring cohort sealed",
            status="completed",
            source="public-evidence://navy-sbir-current-phase-i-public-scoring",
            destination=f"model-execution://public-sbir-transition/{execution_id}/input",
            source_sha256=pool_provenance["sha256"],
            output_sha256=input_sha,
            actor=_clean_text(actor_role, max_chars=32),
            occurred_at=created_at,
            detail={
                "record_count": len(selected),
                "model_version": f"package-{model['packageVersion']}",
                "evidence_class": "public-observed",
            },
        )
        _, _, _, receipt_etag = _read_receipt_with_etag(execution_id)
        _sagemaker_client().create_model(
            ModelName=model_name,
            PrimaryContainer={
                "Image": model["image"],
                "ModelDataUrl": execution_model_url,
                "Environment": {
                    **model["environment"],
                    # Modern pip otherwise creates an isolated build environment
                    # and attempts an index lookup for setuptools. The managed
                    # sklearn image already supplies the build tools, so keep the
                    # install offline while preserving SageMaker network isolation.
                    "PIP_NO_BUILD_ISOLATION": "false",
                    "PIP_NO_INDEX": "1",
                },
            },
            ExecutionRoleArn=_required_env("PUBLIC_SBIR_EXECUTION_ROLE_ARN"),
            EnableNetworkIsolation=True,
            Tags=[
                {"Key": "compass:component", "Value": "public-intelligence"},
                {"Key": "compass:data-classification", "Value": "public"},
                {"Key": "compass:approval-state", "Value": "candidate-smoke"},
                {"Key": "compass:execution-id", "Value": execution_id},
            ],
        )
        transform_submission_attempted = True
        response = _sagemaker_client().create_transform_job(
            TransformJobName=transform_name,
            ModelName=model_name,
            MaxConcurrentTransforms=1,
            MaxPayloadInMB=1,
            BatchStrategy="SingleRecord",
            TransformInput={
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{_bucket()}/{input_key}",
                    }
                },
                "ContentType": "application/json",
                "SplitType": "Line",
                "CompressionType": "None",
            },
            TransformOutput={
                "S3OutputPath": f"s3://{_bucket()}/{_execution_data_key(execution_id, 'output/')}",
                "Accept": "application/json",
                "AssembleWith": "Line",
                "KmsKeyId": _kms_key_arn(),
            },
            TransformResources={
                "InstanceType": "ml.m5.large",
                "InstanceCount": 1,
            },
            DataProcessing={
                "InputFilter": "$",
                "OutputFilter": "$",
                "JoinSource": "None",
            },
            Tags=[
                {"Key": "compass:component", "Value": "public-intelligence"},
                {"Key": "compass:data-classification", "Value": "public"},
                {"Key": "compass:approval-state", "Value": "candidate-smoke"},
                {"Key": "compass:execution-id", "Value": execution_id},
            ],
        )
        receipt["execution"]["transformJobArn"] = response["TransformJobArn"]
        receipt["updatedAt"] = _timestamp()
        operational_evidence.record_stage(
            run_id=execution_id,
            run_kind="sagemaker-batch-inference",
            sequence=2,
            stage_id="batch-transform",
            label="Network-isolated SageMaker Batch Transform",
            status="running",
            source=f"model-execution://public-sbir-transition/{execution_id}/input",
            destination=f"model-execution://public-sbir-transition/{execution_id}/output",
            input_sha256=input_sha,
            actor=_clean_text(actor_role, max_chars=32),
            occurred_at=receipt["updatedAt"],
            detail={
                "record_count": len(selected),
                "model_version": f"package-{model['packageVersion']}",
                "consumer": "SageMaker reconciliation control",
            },
        )
        try:
            return _write_receipt(receipt, expected_etag=receipt_etag)
        except ReceiptWriteConflict:
            return _latest_receipt_response(execution_id)
    except Exception:
        # The API can accept the job and then time out before returning. Once
        # submission starts, leave the durable schedule to describe the exact
        # job name and reconcile either outcome before deleting the model.
        if transform_submission_attempted:
            raise
        cleanup_status = _delete_model(model_name)
        if receipt is not None:
            receipt["status"] = "FAILED"
            receipt["updatedAt"] = _timestamp()
            receipt["completedAt"] = receipt["updatedAt"]
            receipt["execution"]["temporaryModelCleanupStatus"] = cleanup_status
            receipt["failure"] = {
                "code": "SUBMISSION_FAILED",
                "message": "SageMaker rejected the bounded model execution submission.",
            }
            try:
                if receipt_etag is None:
                    _, _, _, receipt_etag = _read_receipt_with_etag(execution_id)
                _write_reconciled_receipt(receipt, expected_etag=receipt_etag)
            except ExecutionNotFound:
                pass
            _record_terminal_evidence(receipt)
        if receipt is None or cleanup_status == "DELETED":
            _release_lock(execution_id)
            if schedule_created:
                try:
                    _delete_reconciliation_schedule(execution_id)
                except Exception:
                    pass
        raise


def _parse_predictions(raw: bytes, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        entries = value.get("predictions") if isinstance(value, dict) else None
        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
            raise ExecutionError("SageMaker prediction output contract is invalid")
        predictions.append(entries[0])
    if len(predictions) != len(records):
        raise ExecutionError("SageMaker prediction count does not match the submitted input")
    result = []
    for record, prediction in zip(records, predictions):
        probability_value = prediction.get("observed_public_transition_probability")
        candidate_label = prediction.get("candidate_label")
        semantics_value = prediction.get("semantics")
        if (
            isinstance(probability_value, bool)
            or not isinstance(probability_value, (int, float))
            or isinstance(candidate_label, bool)
            or not isinstance(candidate_label, int)
            or not isinstance(semantics_value, str)
        ):
            raise ExecutionError("SageMaker prediction value contract is invalid")
        try:
            probability = float(probability_value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ExecutionError("SageMaker prediction value contract is invalid") from exc
        semantics = _clean_text(semantics_value, max_chars=160)
        if (
            not math.isfinite(probability)
            or probability < 0
            or probability > 1
            or candidate_label not in {0, 1}
            or not semantics
            or prediction.get("human_review_required") is not True
        ):
            raise ExecutionError("SageMaker prediction value contract is invalid")
        result.append(
            {
                "recordId": record["recordId"],
                "observedPublicTransitionProbability": round(probability, 8),
                "candidateLabel": candidate_label,
                "semantics": semantics,
                "humanReviewRequired": True,
            }
        )
    return result


def reconcile_active_execution(execution_id: str | None = None) -> dict[str, Any]:
    """Reconcile one run from a scheduled, server-side invocation."""

    if execution_id is not None:
        execution_id = validate_execution_id(execution_id)
        try:
            receipt = get_execution(execution_id)
        except ExecutionNotFound:
            _release_lock(execution_id)
            _delete_reconciliation_schedule(execution_id)
            return {
                "contract": "compass.public-intelligence.model-execution-reconcile.v1",
                "status": "MISSING_SUBMISSION",
                "executionId": execution_id,
            }
        if (
            receipt.get("status") in TERMINAL_STATUSES
            and receipt.get("execution", {}).get("temporaryModelCleanupStatus")
            != "DELETED"
        ):
            raise ExecutionError("terminal model cleanup remains pending")
        if receipt.get("status") in TERMINAL_STATUSES:
            _delete_reconciliation_schedule(execution_id)
        return {
            "contract": "compass.public-intelligence.model-execution-reconcile.v1",
            "status": receipt["status"],
            "executionId": execution_id,
        }

    try:
        lock, _, _ = _read_json(_lock_key(), max_bytes=4096)
    except ExecutionNotFound:
        return {
            "contract": "compass.public-intelligence.model-execution-reconcile.v1",
            "status": "IDLE",
            "executionId": None,
        }
    execution_id = validate_execution_id(lock.get("executionId"))
    receipt = get_execution(execution_id)
    if (
        receipt.get("status") in TERMINAL_STATUSES
        and receipt.get("execution", {}).get("temporaryModelCleanupStatus")
        != "DELETED"
    ):
        raise ExecutionError("terminal model cleanup remains pending")
    if receipt.get("status") in TERMINAL_STATUSES:
        _delete_reconciliation_schedule(execution_id)
    return {
        "contract": "compass.public-intelligence.model-execution-reconcile.v1",
        "status": receipt["status"],
        "executionId": execution_id,
    }


def _duration_seconds(detail: Mapping[str, Any]) -> int | None:
    start = detail.get("TransformStartTime") or detail.get("CreationTime")
    end = detail.get("TransformEndTime")
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    return max(0, int((end - start).total_seconds()))


def get_execution(execution_id: str) -> dict[str, Any]:
    execution_id = validate_execution_id(execution_id)
    receipt, raw, version, receipt_etag = _read_receipt_with_etag(execution_id)
    if receipt.get("status") in TERMINAL_STATUSES:
        if receipt.get("execution", {}).get("temporaryModelCleanupStatus") != "DELETED":
            cleanup_status = _delete_model(
                receipt["execution"]["temporaryModelName"]
            )
            receipt["execution"]["temporaryModelCleanupStatus"] = cleanup_status
            receipt["updatedAt"] = _timestamp()
            if cleanup_status != "DELETED":
                return _write_reconciled_receipt(receipt, expected_etag=receipt_etag)
            result = _write_reconciled_receipt(receipt, expected_etag=receipt_etag)
            _record_terminal_evidence(result)
            _release_lock(execution_id)
            return result
        _release_lock(execution_id)
        _record_terminal_evidence(receipt)
        return _receipt_for_response(receipt, raw, version)
    transform_name = receipt["execution"]["transformJobName"]
    try:
        detail = _sagemaker_client().describe_transform_job(
            TransformJobName=transform_name
        )
    except Exception as exc:
        created = _parse_timestamp(receipt["createdAt"])
        elapsed = int((_now() - created).total_seconds())
        if not _is_missing_transform(exc, transform_name) or elapsed < 120:
            raise
        receipt["status"] = "FAILED"
        receipt["updatedAt"] = _timestamp()
        receipt["completedAt"] = receipt["updatedAt"]
        receipt["execution"]["temporaryModelCleanupStatus"] = _delete_model(
            receipt["execution"]["temporaryModelName"]
        )
        receipt["failure"] = {
            "code": "SUBMISSION_INCOMPLETE",
            "message": "The durable submission receipt has no matching SageMaker transform job.",
        }
        result = _write_reconciled_receipt(receipt, expected_etag=receipt_etag)
        _record_terminal_evidence(result)
        if (
            result.get("execution", {}).get("temporaryModelCleanupStatus")
            == "DELETED"
        ):
            _release_lock(execution_id)
        return result
    aws_status = str(detail.get("TransformJobStatus") or "")
    status_map = {
        "InProgress": "IN_PROGRESS",
        "Completed": "COMPLETED",
        "Failed": "FAILED",
        "Stopping": "IN_PROGRESS",
        "Stopped": "STOPPED",
    }
    status = status_map.get(aws_status)
    if status is None:
        raise ExecutionError("SageMaker returned an unknown transform status")

    now = _now()
    created = _parse_timestamp(receipt["createdAt"])
    elapsed = int((now - created).total_seconds())
    if aws_status == "InProgress" and elapsed > _max_runtime_seconds():
        _sagemaker_client().stop_transform_job(
            TransformJobName=receipt["execution"]["transformJobName"]
        )
        receipt["status"] = "IN_PROGRESS"
        receipt["updatedAt"] = _timestamp(now)
        receipt["execution"]["stopRequestedAt"] = receipt["updatedAt"]
        receipt["execution"]["stopReason"] = "bounded runtime exceeded"
        return _write_reconciled_receipt(receipt, expected_etag=receipt_etag)

    receipt["status"] = status
    receipt["updatedAt"] = _timestamp(now)
    if status == "COMPLETED":
        try:
            output_key = _execution_data_key(execution_id, "output/batch.jsonl.out")
            output_raw, output_version = _read_object(
                output_key, max_bytes=MAX_OUTPUT_BYTES
            )
            predictions = _parse_predictions(
                output_raw, receipt["input"]["records"]
            )
            duration = _duration_seconds(detail)
            receipt["output"] = {
                "predictionCount": len(predictions),
                "sha256": _sha256(output_raw),
                "predictions": predictions,
            }
            receipt["cost"] = {
                "observedDurationSeconds": duration,
                "estimatedComputeUsd": (
                    round(duration / 3600 * _instance_price(), 6)
                    if duration is not None
                    else None
                ),
                "estimateOnly": True,
                "basis": "observed transform duration times configured ml.m5.large hourly rate; AWS invoice may differ",
            }
            receipt["provenance"]["outputVersionId"] = output_version
        except Exception:
            status = "FAILED"
            receipt["status"] = status
            receipt["failure"] = {
                "code": "OUTPUT_VALIDATION_FAILED",
                "message": "The completed SageMaker output failed governed receipt validation.",
            }
    elif status in {"FAILED", "STOPPED"}:
        receipt["failure"] = {
            "code": f"SAGEMAKER_{status}",
            "message": f"SageMaker reported a {status.lower()} bounded smoke run.",
        }
    if status in TERMINAL_STATUSES:
        receipt["completedAt"] = _timestamp(
            detail.get("TransformEndTime") if isinstance(detail.get("TransformEndTime"), datetime) else now
        )
        cleanup_status = _delete_model(
            receipt["execution"]["temporaryModelName"]
        )
        receipt["execution"]["temporaryModelCleanupStatus"] = cleanup_status
        result = _write_reconciled_receipt(receipt, expected_etag=receipt_etag)
        _record_terminal_evidence(result)
        if cleanup_status == "DELETED":
            _release_lock(execution_id)
        return result
    return _write_reconciled_receipt(receipt, expected_etag=receipt_etag)

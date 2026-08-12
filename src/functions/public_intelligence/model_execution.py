"""Bounded SageMaker execution for the public SBIR transition candidate.

This module starts one ephemeral SageMaker Batch Transform validation run from
an immutable public candidate pool. It never changes Model Registry approval,
creates no endpoint, and deletes the temporary SageMaker Model after a terminal
result. Request, input, output, and terminal receipt digests remain in the
KMS-encrypted raw bucket for audit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import urlparse


CONTRACT = "compass.public-intelligence.model-execution.v1"
CANDIDATE_POOL_CONTRACT = "compass.public-intelligence.inference-candidates.v1"
EXECUTION_MODE = "sagemaker_batch_transform"
PURPOSE = "bounded_public_validation"
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "STOPPED"}
MAX_SAMPLE_SIZE_HARD = 25
MAX_POOL_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
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


class ExecutionError(RuntimeError):
    """A governed model execution could not be completed."""


class ExecutionConflict(ExecutionError):
    """Another cost-bounded execution is already active."""

    def __init__(self, message: str, *, execution_id: str | None = None):
        super().__init__(message)
        self.execution_id = execution_id


class ExecutionNotFound(ExecutionError):
    """The requested execution receipt does not exist."""


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


def _required_env(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise ExecutionError(f"model execution configuration is missing {name}")
    return value


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
        normalized = {
            "recordId": record_id,
            "eventTime": _clean_text(record.get("eventTime"), max_chars=64),
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
    return cleaned, {
        "sha256": expected_sha,
        "versionId": version,
        "sourceDataset": value.get("sourceDataset") or {},
    }


def _model_package() -> dict[str, Any]:
    group_arn = _required_env("PUBLIC_SBIR_MODEL_PACKAGE_GROUP_ARN")
    group_name = group_arn.rsplit("/", 1)[-1]
    response = _sagemaker_client().list_model_packages(
        ModelPackageGroupName=group_name,
        ModelApprovalStatus="PendingManualApproval",
        SortBy="CreationTime",
        SortOrder="Descending",
        MaxResults=10,
    )
    summaries = [
        item
        for item in response.get("ModelPackageSummaryList") or []
        if item.get("ModelPackageStatus") == "Completed"
    ]
    if not summaries:
        raise ExecutionError("no completed pending public SBIR candidate is registered")
    package_arn = str(summaries[0].get("ModelPackageArn") or "")
    if not package_arn.startswith(group_arn.rsplit("model-package-group/", 1)[0] + "model-package/"):
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
    if (
        parsed.scheme != "s3"
        or parsed.netloc != _bucket()
        or not parsed.path.lstrip("/").startswith("mlops/public-sbir-transition/registry/")
    ):
        raise ExecutionError("public SBIR model artifact is outside the governed boundary")
    image = str(container.get("Image") or "")
    image_digest = str(container.get("ImageDigest") or "")
    environment = dict(container.get("Environment") or {})
    if not image or not image_digest.startswith("sha256:"):
        raise ExecutionError("public SBIR inference image is not digest-bound")
    if environment.get("SAGEMAKER_PROGRAM") != "inference.py":
        raise ExecutionError("public SBIR inference program is invalid")
    model_metrics = detail.get("ModelMetrics") or {}
    statistics = ((model_metrics.get("ModelQuality") or {}).get("Statistics") or {})
    card_digest = str(statistics.get("ContentDigest") or "")
    return {
        "name": "Public Navy SBIR transition candidate",
        "packageArn": package_arn,
        "packageVersion": int(package_arn.rsplit("/", 1)[-1]),
        "approvalStatus": approval,
        "candidateOnly": True,
        "trainingJobArn": _required_env("PUBLIC_SBIR_TRAINING_JOB_ARN"),
        "modelArtifactSha256": _required_env("PUBLIC_SBIR_MODEL_ARTIFACT_SHA256"),
        "modelCardSha256": card_digest.removeprefix("SHA256:"),
        "image": image,
        "imageDigest": image_digest,
        "modelDataUrl": model_data_url,
        "environment": environment,
    }


def _execution_key(execution_id: str, name: str) -> str:
    return f"{_prefix()}/{execution_id}/{name}"


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


def _write_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    raw = _canonical_json(receipt)
    version = _put_object(_receipt_key(receipt["executionId"]), raw)
    pointer = {
        "contract": "compass.public-intelligence.model-execution-pointer.v1",
        "executionId": receipt["executionId"],
        "createdAt": receipt["createdAt"],
        "updatedAt": receipt["updatedAt"],
        "status": receipt["status"],
        "receiptSha256": _sha256(raw),
    }
    _put_object(_history_key(receipt["executionId"]), _canonical_json(pointer))
    return _receipt_for_response(receipt, raw, version)


def _read_receipt(execution_id: str) -> tuple[dict[str, Any], bytes, str | None]:
    receipt, raw, version = _read_json(_receipt_key(execution_id), max_bytes=MAX_OUTPUT_BYTES)
    if receipt.get("contract") != CONTRACT or receipt.get("executionId") != execution_id:
        raise ExecutionError("model execution receipt contract is invalid")
    return receipt, raw, version


def _release_lock(execution_id: str) -> None:
    try:
        lock, _, _ = _read_json(_lock_key(), max_bytes=4096)
    except (ExecutionError, ExecutionNotFound):
        return
    if lock.get("executionId") == execution_id:
        _delete_object(_lock_key())


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
                    _release_lock(current_id)
                    _put_object(_lock_key(), _canonical_json(lock), if_none_match=True)
                    return
                job_name = current_receipt["execution"]["transformJobName"]
                detail = _sagemaker_client().describe_transform_job(
                    TransformJobName=job_name
                )
                if detail.get("TransformJobStatus") in {
                    "InProgress",
                    "Stopping",
                }:
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
    except Exception:
        return "DELETE_PENDING"


def start_execution(*, sample_size: int, request_id: str, actor_role: str) -> dict[str, Any]:
    created = _now()
    execution_id = f"sbir-batch-{created.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    created_at = _timestamp(created)
    model_name = "compass-sbir-" + execution_id.rsplit("-", 1)[-1]
    transform_name = execution_id
    _acquire_lock(execution_id, created_at)
    receipt: dict[str, Any] | None = None
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
        input_key = _execution_key(execution_id, "input/batch.jsonl")
        input_version = _put_object(input_key, input_raw)
        input_sha = _sha256(input_raw)
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
            "model": {key: value for key, value in model.items() if key not in {"image", "environment", "modelDataUrl"}},
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
            },
            "output": None,
            "cost": None,
            "provenance": {
                "requestId": _clean_text(request_id, max_chars=120),
                "actorRole": _clean_text(actor_role, max_chars=32),
                "candidatePoolSha256": pool_provenance["sha256"],
                "candidatePoolVersionId": pool_provenance["versionId"],
                "sourceDataset": pool_provenance["sourceDataset"],
                "inputVersionId": input_version,
                "outputVersionId": None,
            },
            "humanReviewRequired": True,
            "disclosure": "Candidate validation only. This run does not approve or deploy the model and does not predict ONR mission success.",
        }
        _write_receipt(receipt)
        _sagemaker_client().create_model(
            ModelName=model_name,
            PrimaryContainer={
                "Image": model["image"],
                "ModelDataUrl": model["modelDataUrl"],
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
                {"Key": "compass:approval-state", "Value": "candidate-validation"},
                {"Key": "compass:execution-id", "Value": execution_id},
            ],
        )
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
                "S3OutputPath": f"s3://{_bucket()}/{_execution_key(execution_id, 'output/')}",
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
                {"Key": "compass:approval-state", "Value": "candidate-validation"},
                {"Key": "compass:execution-id", "Value": execution_id},
            ],
        )
        receipt["execution"]["transformJobArn"] = response["TransformJobArn"]
        receipt["updatedAt"] = _timestamp()
        return _write_receipt(receipt)
    except Exception:
        _delete_model(model_name)
        if receipt is not None:
            receipt["status"] = "FAILED"
            receipt["updatedAt"] = _timestamp()
            receipt["completedAt"] = receipt["updatedAt"]
            receipt["execution"]["temporaryModelCleanupStatus"] = "DELETED"
            receipt["failure"] = {
                "code": "SUBMISSION_FAILED",
                "message": "SageMaker rejected the bounded model execution submission.",
            }
            _write_receipt(receipt)
        _release_lock(execution_id)
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
        result.append(
            {
                "recordId": record["recordId"],
                "observedPublicTransitionProbability": round(
                    float(prediction["observed_public_transition_probability"]), 8
                ),
                "candidateLabel": int(prediction["candidate_label"]),
                "semantics": _clean_text(prediction.get("semantics"), max_chars=160),
                "humanReviewRequired": bool(prediction.get("human_review_required", True)),
            }
        )
    return result


def _duration_seconds(detail: Mapping[str, Any]) -> int | None:
    start = detail.get("TransformStartTime") or detail.get("CreationTime")
    end = detail.get("TransformEndTime")
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    return max(0, int((end - start).total_seconds()))


def get_execution(execution_id: str) -> dict[str, Any]:
    execution_id = validate_execution_id(execution_id)
    receipt, raw, version = _read_receipt(execution_id)
    if receipt.get("status") in TERMINAL_STATUSES:
        return _receipt_for_response(receipt, raw, version)
    detail = _sagemaker_client().describe_transform_job(
        TransformJobName=receipt["execution"]["transformJobName"]
    )
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
    if status == "IN_PROGRESS" and elapsed > _max_runtime_seconds():
        _sagemaker_client().stop_transform_job(
            TransformJobName=receipt["execution"]["transformJobName"]
        )
        receipt["status"] = "IN_PROGRESS"
        receipt["updatedAt"] = _timestamp(now)
        receipt["execution"]["stopRequestedAt"] = receipt["updatedAt"]
        receipt["execution"]["stopReason"] = "bounded runtime exceeded"
        return _write_receipt(receipt)

    receipt["status"] = status
    receipt["updatedAt"] = _timestamp(now)
    if status == "COMPLETED":
        try:
            output_key = _execution_key(execution_id, "output/batch.jsonl.out")
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
            "message": f"SageMaker reported a {status.lower()} bounded validation run.",
        }
    if status in TERMINAL_STATUSES:
        receipt["completedAt"] = _timestamp(
            detail.get("TransformEndTime") if isinstance(detail.get("TransformEndTime"), datetime) else now
        )
        receipt["execution"]["temporaryModelCleanupStatus"] = _delete_model(
            receipt["execution"]["temporaryModelName"]
        )
        result = _write_receipt(receipt)
        _release_lock(execution_id)
        return result
    return _write_receipt(receipt)

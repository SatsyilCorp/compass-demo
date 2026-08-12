from __future__ import annotations

import io
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

import model_execution as execution


MODEL_RAW = b"pinned model artifact"
MODEL_KEY = "mlops/public-sbir-transition/registry/model.tar.gz"
MODEL_VERSION = "model-version-2"
MODEL_BUNDLE_SHA256 = hashlib.sha256(MODEL_RAW).hexdigest()
MODEL_ARTIFACT_SHA256 = "a" * 64
MODEL_CARD_SHA256 = "d" * 64
IMAGE_DIGEST = "sha256:" + "c" * 64
PACKAGE_ARN = "arn:aws:sagemaker:us-east-1:111122223333:model-package/compass-demo-public-sbir-transition/2"

ENV = {
    "PUBLIC_SBIR_EXECUTION_ENABLED": "true",
    "PUBLIC_SBIR_EXECUTION_BUCKET": "private-raw",
    "PUBLIC_SBIR_EXECUTION_PREFIX": "mlops/public-sbir-transition/executions/",
    "PUBLIC_SBIR_CANDIDATE_POOL_KEY": "mlops/public-sbir-transition/validation/candidates.json",
    "PUBLIC_SBIR_EXECUTION_KMS_KEY_ARN": "arn:aws:kms:us-east-1:111122223333:key/example",
    "PUBLIC_SBIR_MODEL_PACKAGE_GROUP_ARN": "arn:aws:sagemaker:us-east-1:111122223333:model-package-group/compass-demo-public-sbir-transition",
    "PUBLIC_SBIR_MODEL_PACKAGE_ARN": PACKAGE_ARN,
    "PUBLIC_SBIR_TRAINING_JOB_ARN": "arn:aws:sagemaker:us-east-1:111122223333:training-job/training",
    "PUBLIC_SBIR_MODEL_ARTIFACT_SHA256": MODEL_ARTIFACT_SHA256,
    "PUBLIC_SBIR_MODEL_BUNDLE_SHA256": MODEL_BUNDLE_SHA256,
    "PUBLIC_SBIR_MODEL_CARD_SHA256": MODEL_CARD_SHA256,
    "PUBLIC_SBIR_MODEL_DATA_KEY": MODEL_KEY,
    "PUBLIC_SBIR_MODEL_DATA_VERSION_ID": MODEL_VERSION,
    "PUBLIC_SBIR_IMAGE_DIGEST": IMAGE_DIGEST,
    "PUBLIC_SBIR_EXECUTION_ROLE_ARN": "arn:aws:iam::111122223333:role/compass-sagemaker",
    "PUBLIC_SBIR_EXECUTION_MAX_RECORDS": "25",
    "PUBLIC_SBIR_EXECUTION_MAX_RUNTIME_SECONDS": "1800",
    "PUBLIC_SBIR_RECONCILIATION_ROLE_ARN": "arn:aws:iam::111122223333:role/scheduler",
    "PUBLIC_SBIR_RECONCILIATION_FUNCTION_ARN": "arn:aws:lambda:us-east-1:111122223333:function:public-intelligence",
    "PUBLIC_SBIR_RECONCILIATION_DLQ_ARN": "arn:aws:sqs:us-east-1:111122223333:public-sbir-reconciliation-dlq",
    "AWS_LAMBDA_FUNCTION_NAME": "compass-demo-public-intelligence",
}


def encoded(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def pool():
    records = []
    for index in range(3):
        records.append(
            {
                "eventTime": "2023-01-01T00:00:00Z",
                "recordId": f"record-{index}",
                "sourceRecordIds": [f"source-{index}"],
                "features": {
                    "phase_i_amount_usd": 100000,
                    "title_character_count": 20,
                    "abstract_character_count": 200,
                    "abstract_token_count": 30,
                    "award_year": 2023,
                    "topic_family": "N23",
                    "public_text": "Public research abstract",
                },
            }
        )
    return {
        "contract": execution.CANDIDATE_POOL_CONTRACT,
        "dataBoundary": {
            "classification": "public",
            "containsCui": False,
            "labelsExcluded": True,
            "piiMinimized": True,
        },
        "sourceDataset": {"datasetId": "dataset", "sha256": "b" * 64},
        "records": records,
    }


class FakeS3:
    def __init__(self, pool_value):
        self.objects = {
            ENV["PUBLIC_SBIR_CANDIDATE_POOL_KEY"]: encoded(pool_value),
            MODEL_KEY: MODEL_RAW,
        }
        self.versions = {MODEL_KEY: MODEL_VERSION}

    def put_object(self, **kwargs):
        key = kwargs["Key"]
        if kwargs.get("IfNoneMatch") == "*" and key in self.objects:
            error = RuntimeError("conflict")
            error.response = {"Error": {"Code": "PreconditionFailed"}}
            raise error
        if kwargs.get("IfMatch") is not None:
            raw = self.objects.get(key)
            actual = (
                '"' + hashlib.md5(raw, usedforsecurity=False).hexdigest() + '"'
                if raw is not None
                else None
            )
            if actual != kwargs["IfMatch"]:
                error = RuntimeError("conditional conflict")
                error.response = {"Error": {"Code": "PreconditionFailed"}}
                raise error
        body = kwargs["Body"]
        if hasattr(body, "read"):
            body = body.read()
        self.objects[key] = bytes(body)
        self.versions[key] = "version-put"
        return {"VersionId": "version-put"}

    def get_object(self, *, Bucket, Key, VersionId=None):
        if Key not in self.objects:
            error = RuntimeError("missing")
            error.response = {"Error": {"Code": "NoSuchKey"}}
            raise error
        raw = self.objects[Key]
        if VersionId is not None and VersionId != self.versions.get(Key):
            raise RuntimeError("wrong version")
        return {
            "Body": io.BytesIO(raw),
            "ContentLength": len(raw),
            "VersionId": self.versions.get(Key, "version-source"),
            "ETag": '"' + hashlib.md5(raw, usedforsecurity=False).hexdigest() + '"',
        }

    def delete_object(self, *, Bucket, Key, IfMatch=None):
        if IfMatch is not None:
            raw = self.objects.get(Key)
            actual = (
                '"' + hashlib.md5(raw, usedforsecurity=False).hexdigest() + '"'
                if raw is not None
                else None
            )
            if actual != IfMatch:
                error = RuntimeError("conditional conflict")
                error.response = {"Error": {"Code": "PreconditionFailed"}}
                raise error
        self.objects.pop(Key, None)
        return {}

    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
        return {
            "Contents": [
                {"Key": key}
                for key in sorted(self.objects)
                if key.startswith(Prefix)
            ][:MaxKeys]
        }


class FakeSageMaker:
    def __init__(self):
        self.models = []
        self.transforms = []
        self.deleted = []
        self.status = "InProgress"
        self.transform_start = datetime.now(UTC)
        self.transform_missing = False

    def list_model_packages(self, **kwargs):
        return {
            "ModelPackageSummaryList": [
                {
                    "ModelPackageArn": "arn:aws:sagemaker:us-east-1:111122223333:model-package/compass-demo-public-sbir-transition/2",
                    "ModelPackageStatus": "Completed",
                }
            ]
        }

    def describe_model_package(self, **kwargs):
        return {
            "ModelPackageStatus": "Completed",
            "ModelApprovalStatus": "PendingManualApproval",
            "InferenceSpecification": {
                "Containers": [
                    {
                        "Image": "111122223333.dkr.ecr.us-east-1.amazonaws.com/image:tag",
                        "ImageDigest": IMAGE_DIGEST,
                        "ModelDataUrl": f"s3://private-raw/{MODEL_KEY}",
                        "Environment": {"SAGEMAKER_PROGRAM": "inference.py"},
                    }
                ]
            },
            "ModelMetrics": {
                "ModelQuality": {"Statistics": {"ContentDigest": "SHA256:" + "d" * 64}}
            },
            "CustomerMetadataProperties": {
                "artifact_sha256": MODEL_ARTIFACT_SHA256,
                "registry_bundle_sha256": MODEL_BUNDLE_SHA256,
                "training_job": "training",
            },
        }

    def create_model(self, **kwargs):
        self.models.append(kwargs)
        return {"ModelArn": "arn:model"}

    def create_transform_job(self, **kwargs):
        self.transforms.append(kwargs)
        return {"TransformJobArn": "arn:transform"}

    def describe_transform_job(self, **kwargs):
        if self.transform_missing:
            error = RuntimeError("missing transform")
            error.response = {
                "Error": {
                    "Code": "ValidationException",
                    "Message": (
                        "Could not find transform job "
                        + kwargs["TransformJobName"]
                    ),
                }
            }
            raise error
        value = {
            "TransformJobStatus": self.status,
            "CreationTime": self.transform_start,
            "TransformStartTime": self.transform_start,
        }
        if self.status != "InProgress":
            value["TransformEndTime"] = self.transform_start + timedelta(seconds=120)
        return value

    def stop_transform_job(self, **kwargs):
        return {}

    def delete_model(self, *, ModelName):
        self.deleted.append(ModelName)
        return {}


class FakeScheduler:
    def __init__(self):
        self.schedules = []
        self.deleted = []

    def create_schedule(self, **kwargs):
        self.schedules.append(kwargs)
        return {
            "ScheduleArn": (
                "arn:aws:scheduler:us-east-1:111122223333:schedule/default/"
                + kwargs["Name"]
            )
        }

    def delete_schedule(self, **kwargs):
        self.deleted.append(kwargs)
        return {}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    pool_raw = encoded(pool())
    monkeypatch.setenv("PUBLIC_SBIR_CANDIDATE_POOL_SHA256", execution._sha256(pool_raw))
    fake_s3 = FakeS3(pool())
    fake_sm = FakeSageMaker()
    fake_scheduler = FakeScheduler()
    execution._S3_CLIENT = fake_s3
    execution._SAGEMAKER_CLIENT = fake_sm
    execution._SCHEDULER_CLIENT = fake_scheduler
    yield fake_s3, fake_sm, fake_scheduler
    execution._S3_CLIENT = None
    execution._SAGEMAKER_CLIENT = None
    execution._SCHEDULER_CLIENT = None


def test_start_execution_is_bounded_candidate_only(configured):
    fake_s3, fake_sm, fake_scheduler = configured
    receipt = execution.start_execution(sample_size=2, request_id="request-1", actor_role="poweruser")

    assert receipt["status"] == "SUBMITTED"
    assert receipt["model"]["approvalStatus"] == "PendingManualApproval"
    assert receipt["model"]["candidateOnly"] is True
    assert receipt["model"]["modelBundleSha256"] == MODEL_BUNDLE_SHA256
    assert receipt["model"]["modelArtifactSourceVersionId"] == MODEL_VERSION
    assert receipt["input"]["recordCount"] == 2
    assert receipt["execution"]["instanceCount"] == 1
    assert receipt["execution"]["networkIsolation"] is True
    assert fake_sm.models[0]["EnableNetworkIsolation"] is True
    assert fake_sm.models[0]["PrimaryContainer"]["Image"].endswith(
        "@" + IMAGE_DIGEST
    )
    assert fake_sm.models[0]["PrimaryContainer"]["Environment"] == {
        "SAGEMAKER_PROGRAM": "inference.py",
        "PIP_NO_BUILD_ISOLATION": "false",
        "PIP_NO_INDEX": "1",
    }
    assert fake_sm.transforms[0]["TransformResources"]["InstanceType"] == "ml.m5.large"
    assert fake_scheduler.schedules[0]["ScheduleExpression"] == "rate(1 minute)"
    assert fake_scheduler.schedules[0]["ActionAfterCompletion"] == "DELETE"
    assert fake_scheduler.schedules[0]["Target"]["DeadLetterConfig"] == {
        "Arn": ENV["PUBLIC_SBIR_RECONCILIATION_DLQ_ARN"]
    }
    input_key = next(key for key in fake_s3.objects if key.endswith("input/batch.jsonl"))
    assert "label" not in fake_s3.objects[input_key].decode()


def test_ambiguous_transform_submission_is_left_for_durable_reconciliation(
    configured, monkeypatch
):
    fake_s3, fake_sm, fake_scheduler = configured

    def timeout_after_possible_acceptance(**kwargs):
        fake_sm.transforms.append(kwargs)
        raise TimeoutError("response timed out after request transmission")

    fake_sm.create_transform_job = timeout_after_possible_acceptance

    with pytest.raises(TimeoutError, match="timed out"):
        execution.start_execution(
            sample_size=1,
            request_id="request-ambiguous",
            actor_role="poweruser",
        )

    receipt_key = next(
        key for key in fake_s3.objects if key.endswith("/receipt.json")
    )
    receipt = json.loads(fake_s3.objects[receipt_key])
    assert receipt["status"] == "SUBMITTED"
    assert execution._lock_key() in fake_s3.objects
    assert fake_sm.deleted == []
    assert fake_scheduler.deleted == []

    fake_sm.transform_missing = True
    future = datetime.now(UTC) + timedelta(seconds=121)
    monkeypatch.setattr(execution, "_now", lambda: future)
    reconciled = execution.reconcile_active_execution(receipt["executionId"])

    assert reconciled["status"] == "FAILED"
    terminal = execution.get_execution(receipt["executionId"])
    assert terminal["failure"]["code"] == "SUBMISSION_INCOMPLETE"
    assert terminal["execution"]["temporaryModelCleanupStatus"] == "DELETED"
    assert execution._lock_key() not in fake_s3.objects
    assert fake_scheduler.deleted


def test_get_execution_completes_with_prediction_receipt(configured):
    fake_s3, fake_sm, _ = configured
    started = execution.start_execution(sample_size=2, request_id="request-1", actor_role="poweruser")
    execution_id = started["executionId"]
    output_key = (
        f"{ENV['PUBLIC_SBIR_EXECUTION_PREFIX'].strip('/')}/data/{execution_id}"
        "/output/batch.jsonl.out"
    )
    prediction = {
        "predictions": [
            {
                "observed_public_transition_probability": 0.67,
                "candidate_label": 1,
                "semantics": "public SBIR transition signal, not ONR mission success",
                "human_review_required": True,
            }
        ]
    }
    fake_s3.objects[output_key] = encoded(prediction) + b"\n" + encoded(prediction) + b"\n"
    fake_sm.status = "Completed"

    receipt = execution.get_execution(execution_id)

    assert receipt["status"] == "COMPLETED"
    assert receipt["output"]["predictionCount"] == 2
    assert receipt["cost"]["estimatedComputeUsd"] == pytest.approx(0.003833)
    assert receipt["humanReviewRequired"] is True
    assert receipt["execution"]["temporaryModelCleanupStatus"] == "DELETED"
    assert fake_sm.deleted


def test_list_executions_returns_latest_durable_receipt(configured):
    started = execution.start_execution(
        sample_size=1, request_id="request-1", actor_role="poweruser"
    )

    result = execution.list_executions()

    assert result["contract"] == "compass.public-intelligence.model-execution-list.v1"
    assert result["executions"][0]["executionId"] == started["executionId"]
    assert result["executions"][0]["status"] == "IN_PROGRESS"


def test_request_and_execution_id_limits(monkeypatch):
    assert execution.parse_start_request({"sampleSize": 1}) == 1
    with pytest.raises(ValueError, match="between 1 and 25"):
        execution.parse_start_request({"sampleSize": 26})
    with pytest.raises(ValueError, match="unsupported"):
        execution.parse_start_request({"sampleSize": 2, "approve": True})
    with pytest.raises(ValueError, match="invalid"):
        execution.validate_execution_id("../../escape")


def test_execution_is_disabled_without_explicit_evidence_gate(configured, monkeypatch):
    fake_s3, fake_sm, fake_scheduler = configured
    monkeypatch.setenv("PUBLIC_SBIR_EXECUTION_ENABLED", "false")

    with pytest.raises(execution.ExecutionError, match="disabled"):
        execution.start_execution(
            sample_size=1,
            request_id="request-disabled",
            actor_role="poweruser",
        )

    assert execution._lock_key() not in fake_s3.objects
    assert fake_sm.models == []
    assert fake_scheduler.schedules == []


def test_pool_rejects_non_public_boundary(configured):
    fake_s3, _, _ = configured
    value = pool()
    value["dataBoundary"]["classification"] = "CUI"
    fake_s3.objects[ENV["PUBLIC_SBIR_CANDIDATE_POOL_KEY"]] = encoded(value)
    os.environ["PUBLIC_SBIR_CANDIDATE_POOL_SHA256"] = execution._sha256(encoded(value))

    with pytest.raises(execution.ExecutionError, match="boundary"):
        execution._pool()


@pytest.mark.parametrize(
    "patch",
    [
        {"observed_public_transition_probability": float("nan")},
        {"observed_public_transition_probability": -0.01},
        {"observed_public_transition_probability": 1.01},
        {"observed_public_transition_probability": "0.7"},
        {"candidate_label": 2},
        {"candidate_label": True},
        {"semantics": ""},
        {"human_review_required": False},
    ],
)
def test_prediction_contract_fails_closed(patch):
    prediction = {
        "observed_public_transition_probability": 0.67,
        "candidate_label": 1,
        "semantics": "public transition proxy only",
        "human_review_required": True,
    }
    prediction.update(patch)
    raw = encoded({"predictions": [prediction]}) + b"\n"

    with pytest.raises(execution.ExecutionError, match="value contract"):
        execution._parse_predictions(raw, [{"recordId": "record-1"}])


def test_model_package_rejects_bundle_digest_mismatch(configured, monkeypatch):
    _, fake_sm, _ = configured
    monkeypatch.setenv("PUBLIC_SBIR_MODEL_BUNDLE_SHA256", "f" * 64)
    original = fake_sm.describe_model_package

    def describe(**kwargs):
        value = original(**kwargs)
        value["CustomerMetadataProperties"]["registry_bundle_sha256"] = "f" * 64
        return value

    fake_sm.describe_model_package = describe

    with pytest.raises(execution.ExecutionError, match="digest validation"):
        execution._model_package()


def test_model_package_rejects_model_card_digest_mismatch(configured, monkeypatch):
    monkeypatch.setenv("PUBLIC_SBIR_MODEL_CARD_SHA256", "f" * 64)

    with pytest.raises(execution.ExecutionError, match="provenance"):
        execution._model_package()


def test_lock_release_is_compare_and_swap_safe(configured):
    fake_s3, _, _ = configured
    lock_key = execution._lock_key()
    first = {
        "contract": "compass.public-intelligence.model-execution-lock.v1",
        "executionId": "sbir-batch-20260812T150516-aaaaaaaa",
        "createdAt": "2026-08-12T15:05:16Z",
        "maxRuntimeSeconds": 1800,
    }
    second = {**first, "executionId": "sbir-batch-20260812T150517-bbbbbbbb"}
    fake_s3.objects[lock_key] = encoded(first)
    original_delete = fake_s3.delete_object

    def replace_before_delete(**kwargs):
        fake_s3.objects[lock_key] = encoded(second)
        return original_delete(**kwargs)

    fake_s3.delete_object = replace_before_delete

    assert execution._release_lock(first["executionId"]) is False
    assert json.loads(fake_s3.objects[lock_key]) == second


def test_lock_release_treats_concurrent_missing_key_as_success(configured):
    fake_s3, _, _ = configured
    execution_id = "sbir-batch-20260812T150516-aaaaaaaa"
    lock_key = execution._lock_key()
    fake_s3.objects[lock_key] = encoded(
        {
            "contract": "compass.public-intelligence.model-execution-lock.v1",
            "executionId": execution_id,
            "createdAt": "2026-08-12T15:05:16Z",
            "maxRuntimeSeconds": 1800,
        }
    )

    def missing_during_delete(**kwargs):
        fake_s3.objects.pop(lock_key, None)
        error = RuntimeError("already deleted")
        error.response = {"Error": {"Code": "NoSuchKey"}}
        raise error

    fake_s3.delete_object = missing_during_delete

    assert execution._release_lock(execution_id) is True


def test_schedule_repairs_lock_when_submission_receipt_never_exists(configured):
    fake_s3, _, fake_scheduler = configured
    execution_id = "sbir-batch-20260812T150516-aaaaaaaa"
    fake_s3.objects[execution._lock_key()] = encoded(
        {
            "contract": "compass.public-intelligence.model-execution-lock.v1",
            "executionId": execution_id,
            "createdAt": "2026-08-12T15:05:16Z",
            "maxRuntimeSeconds": 1800,
        }
    )

    result = execution.reconcile_active_execution(execution_id)

    assert result["status"] == "MISSING_SUBMISSION"
    assert execution._lock_key() not in fake_s3.objects
    assert fake_scheduler.deleted


def test_terminal_cleanup_retries_before_releasing_lock(configured):
    fake_s3, fake_sm, _ = configured
    started = execution.start_execution(
        sample_size=1, request_id="request-1", actor_role="poweruser"
    )
    execution_id = started["executionId"]
    output_key = (
        f"{ENV['PUBLIC_SBIR_EXECUTION_PREFIX'].strip('/')}/data/{execution_id}"
        "/output/batch.jsonl.out"
    )
    fake_s3.objects[output_key] = encoded(
        {
            "predictions": [
                {
                    "observed_public_transition_probability": 0.67,
                    "candidate_label": 1,
                    "semantics": "public transition proxy only",
                    "human_review_required": True,
                }
            ]
        }
    ) + b"\n"
    fake_sm.status = "Completed"
    delete_calls = 0

    def delete_with_one_transient_failure(*, ModelName):
        nonlocal delete_calls
        delete_calls += 1
        if delete_calls == 1:
            raise RuntimeError("transient")
        fake_sm.deleted.append(ModelName)
        return {}

    fake_sm.delete_model = delete_with_one_transient_failure

    first = execution.get_execution(execution_id)
    assert first["status"] == "COMPLETED"
    assert first["execution"]["temporaryModelCleanupStatus"] == "DELETE_PENDING"
    assert execution._lock_key() in fake_s3.objects

    second = execution.reconcile_active_execution(execution_id)
    assert second["status"] == "COMPLETED"
    assert execution._lock_key() not in fake_s3.objects


def test_stale_terminal_lock_is_retained_until_model_cleanup_succeeds(configured):
    fake_s3, fake_sm, _ = configured
    started = execution.start_execution(
        sample_size=1, request_id="request-old", actor_role="poweruser"
    )
    execution_id = started["executionId"]
    output_key = execution._execution_data_key(
        execution_id, "output/batch.jsonl.out"
    )
    fake_s3.objects[output_key] = encoded(
        {
            "predictions": [
                {
                    "observed_public_transition_probability": 0.67,
                    "candidate_label": 1,
                    "semantics": "public transition proxy only",
                    "human_review_required": True,
                }
            ]
        }
    ) + b"\n"
    fake_sm.status = "Completed"

    def cleanup_fails(*, ModelName):
        raise RuntimeError("transient cleanup failure")

    fake_sm.delete_model = cleanup_fails
    terminal = execution.get_execution(execution_id)
    assert terminal["execution"]["temporaryModelCleanupStatus"] == "DELETE_PENDING"

    lock_key = execution._lock_key()
    lock = json.loads(fake_s3.objects[lock_key])
    lock["createdAt"] = "2026-08-10T00:00:00Z"
    fake_s3.objects[lock_key] = encoded(lock)

    with pytest.raises(execution.ExecutionConflict):
        execution.start_execution(
            sample_size=1,
            request_id="request-new",
            actor_role="poweruser",
        )

    assert json.loads(fake_s3.objects[lock_key])["executionId"] == execution_id


def test_stopping_transform_is_not_stopped_repeatedly(configured, monkeypatch):
    _, fake_sm, _ = configured
    started = execution.start_execution(
        sample_size=1, request_id="request-1", actor_role="poweruser"
    )
    execution_id = started["executionId"]
    stop_calls = []

    def record_stop(*, TransformJobName):
        stop_calls.append(TransformJobName)
        return {}

    fake_sm.stop_transform_job = record_stop
    future = datetime.now(UTC) + timedelta(
        seconds=execution._max_runtime_seconds() + 1
    )
    monkeypatch.setattr(execution, "_now", lambda: future)

    first = execution.get_execution(execution_id)
    fake_sm.status = "Stopping"
    second = execution.get_execution(execution_id)

    assert stop_calls == [execution_id]
    assert first["execution"]["stopRequestedAt"] == second["execution"]["stopRequestedAt"]
    assert second["status"] == "IN_PROGRESS"


def test_scheduler_marks_missing_submission_failed_after_startup_grace(
    configured, monkeypatch
):
    fake_s3, fake_sm, fake_scheduler = configured
    started = execution.start_execution(
        sample_size=1, request_id="request-missing", actor_role="poweruser"
    )
    fake_sm.transform_missing = True
    future = datetime.now(UTC) + timedelta(seconds=121)
    monkeypatch.setattr(execution, "_now", lambda: future)

    result = execution.reconcile_active_execution(started["executionId"])

    assert result["status"] == "FAILED"
    receipt = execution.get_execution(started["executionId"])
    assert receipt["failure"]["code"] == "SUBMISSION_INCOMPLETE"
    assert receipt["execution"]["temporaryModelCleanupStatus"] == "DELETED"
    assert fake_scheduler.deleted


def test_scheduler_raises_until_terminal_cleanup_succeeds(configured):
    fake_s3, fake_sm, _ = configured
    started = execution.start_execution(
        sample_size=1, request_id="request-cleanup", actor_role="poweruser"
    )
    execution_id = started["executionId"]
    output_key = execution._execution_data_key(
        execution_id, "output/batch.jsonl.out"
    )
    fake_s3.objects[output_key] = encoded(
        {
            "predictions": [
                {
                    "observed_public_transition_probability": 0.67,
                    "candidate_label": 1,
                    "semantics": "public transition proxy only",
                    "human_review_required": True,
                }
            ]
        }
    ) + b"\n"
    fake_sm.status = "Completed"

    def cleanup_fails(*, ModelName):
        raise RuntimeError("transient cleanup failure")

    fake_sm.delete_model = cleanup_fails

    with pytest.raises(execution.ExecutionError, match="cleanup remains pending"):
        execution.reconcile_active_execution(execution_id)


def test_stale_reconciler_cannot_overwrite_terminal_receipt(configured):
    fake_s3, fake_sm, _ = configured
    started = execution.start_execution(
        sample_size=1, request_id="request-race", actor_role="poweruser"
    )
    execution_id = started["executionId"]
    stale, _, _, stale_etag = execution._read_receipt_with_etag(execution_id)
    output_key = execution._execution_data_key(
        execution_id, "output/batch.jsonl.out"
    )
    fake_s3.objects[output_key] = encoded(
        {
            "predictions": [
                {
                    "observed_public_transition_probability": 0.67,
                    "candidate_label": 1,
                    "semantics": "public transition proxy only",
                    "human_review_required": True,
                }
            ]
        }
    ) + b"\n"
    fake_sm.status = "Completed"
    terminal = execution.get_execution(execution_id)
    assert terminal["status"] == "COMPLETED"

    stale["status"] = "IN_PROGRESS"
    stale["updatedAt"] = execution._timestamp()
    winner = execution._write_reconciled_receipt(
        stale, expected_etag=stale_etag
    )

    assert winner["status"] == "COMPLETED"
    assert execution.get_execution(execution_id)["status"] == "COMPLETED"

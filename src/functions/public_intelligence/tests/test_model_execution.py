from __future__ import annotations

import io
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

import model_execution as execution


ENV = {
    "PUBLIC_SBIR_EXECUTION_BUCKET": "private-raw",
    "PUBLIC_SBIR_EXECUTION_PREFIX": "mlops/public-sbir-transition/executions/",
    "PUBLIC_SBIR_CANDIDATE_POOL_KEY": "mlops/public-sbir-transition/validation/candidates.json",
    "PUBLIC_SBIR_EXECUTION_KMS_KEY_ARN": "arn:aws:kms:us-east-1:111122223333:key/example",
    "PUBLIC_SBIR_MODEL_PACKAGE_GROUP_ARN": "arn:aws:sagemaker:us-east-1:111122223333:model-package-group/compass-demo-public-sbir-transition",
    "PUBLIC_SBIR_TRAINING_JOB_ARN": "arn:aws:sagemaker:us-east-1:111122223333:training-job/training",
    "PUBLIC_SBIR_MODEL_ARTIFACT_SHA256": "a" * 64,
    "PUBLIC_SBIR_EXECUTION_ROLE_ARN": "arn:aws:iam::111122223333:role/compass-sagemaker",
    "PUBLIC_SBIR_EXECUTION_MAX_RECORDS": "25",
    "PUBLIC_SBIR_EXECUTION_MAX_RUNTIME_SECONDS": "1800",
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
        self.objects = {ENV["PUBLIC_SBIR_CANDIDATE_POOL_KEY"]: encoded(pool_value)}
        self.versions = {}

    def put_object(self, **kwargs):
        key = kwargs["Key"]
        if kwargs.get("IfNoneMatch") == "*" and key in self.objects:
            error = RuntimeError("conflict")
            error.response = {"Error": {"Code": "PreconditionFailed"}}
            raise error
        body = kwargs["Body"]
        if hasattr(body, "read"):
            body = body.read()
        self.objects[key] = bytes(body)
        self.versions[key] = "version-put"
        return {"VersionId": "version-put"}

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            error = RuntimeError("missing")
            error.response = {"Error": {"Code": "NoSuchKey"}}
            raise error
        raw = self.objects[Key]
        return {
            "Body": io.BytesIO(raw),
            "ContentLength": len(raw),
            "VersionId": self.versions.get(Key, "version-source"),
        }

    def delete_object(self, *, Bucket, Key):
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
                        "ImageDigest": "sha256:" + "c" * 64,
                        "ModelDataUrl": "s3://private-raw/mlops/public-sbir-transition/registry/model.tar.gz",
                        "Environment": {"SAGEMAKER_PROGRAM": "inference.py"},
                    }
                ]
            },
            "ModelMetrics": {
                "ModelQuality": {"Statistics": {"ContentDigest": "SHA256:" + "d" * 64}}
            },
        }

    def create_model(self, **kwargs):
        self.models.append(kwargs)
        return {"ModelArn": "arn:model"}

    def create_transform_job(self, **kwargs):
        self.transforms.append(kwargs)
        return {"TransformJobArn": "arn:transform"}

    def describe_transform_job(self, **kwargs):
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


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    pool_raw = encoded(pool())
    monkeypatch.setenv("PUBLIC_SBIR_CANDIDATE_POOL_SHA256", execution._sha256(pool_raw))
    fake_s3 = FakeS3(pool())
    fake_sm = FakeSageMaker()
    execution._S3_CLIENT = fake_s3
    execution._SAGEMAKER_CLIENT = fake_sm
    yield fake_s3, fake_sm
    execution._S3_CLIENT = None
    execution._SAGEMAKER_CLIENT = None


def test_start_execution_is_bounded_candidate_only(configured):
    fake_s3, fake_sm = configured
    receipt = execution.start_execution(sample_size=2, request_id="request-1", actor_role="poweruser")

    assert receipt["status"] == "SUBMITTED"
    assert receipt["model"]["approvalStatus"] == "PendingManualApproval"
    assert receipt["model"]["candidateOnly"] is True
    assert receipt["input"]["recordCount"] == 2
    assert receipt["execution"]["instanceCount"] == 1
    assert receipt["execution"]["networkIsolation"] is True
    assert fake_sm.models[0]["EnableNetworkIsolation"] is True
    assert fake_sm.models[0]["PrimaryContainer"]["Environment"] == {
        "SAGEMAKER_PROGRAM": "inference.py",
        "PIP_NO_BUILD_ISOLATION": "false",
        "PIP_NO_INDEX": "1",
    }
    assert fake_sm.transforms[0]["TransformResources"]["InstanceType"] == "ml.m5.large"
    input_key = next(key for key in fake_s3.objects if key.endswith("input/batch.jsonl"))
    assert "label" not in fake_s3.objects[input_key].decode()


def test_get_execution_completes_with_prediction_receipt(configured):
    fake_s3, fake_sm = configured
    started = execution.start_execution(sample_size=2, request_id="request-1", actor_role="poweruser")
    execution_id = started["executionId"]
    output_key = f"{ENV['PUBLIC_SBIR_EXECUTION_PREFIX'].strip('/')}/{execution_id}/output/batch.jsonl.out"
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


def test_pool_rejects_non_public_boundary(configured):
    fake_s3, _ = configured
    value = pool()
    value["dataBoundary"]["classification"] = "CUI"
    fake_s3.objects[ENV["PUBLIC_SBIR_CANDIDATE_POOL_KEY"]] = encoded(value)
    os.environ["PUBLIC_SBIR_CANDIDATE_POOL_SHA256"] = execution._sha256(encoded(value))

    with pytest.raises(execution.ExecutionError, match="boundary"):
        execution._pool()

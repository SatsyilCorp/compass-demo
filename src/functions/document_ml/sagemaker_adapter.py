"""Optional SageMaker submission adapter for Compass document classification.

The default application mode is ``demo`` and executes the deterministic model
from ``engine.py`` inside Lambda. ``sagemaker`` mode is explicit and refuses to
claim a training job was started unless an execution role and approved
training image were supplied by the deployment.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Mapping


JOB_NAME_RE = re.compile(r"[^A-Za-z0-9-]+")


def training_job_name(model_version: str) -> str:
    safe = JOB_NAME_RE.sub("-", model_version).strip("-")[:40]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"compass-doc-{safe}-{stamp}"[:63]


def build_training_job_request(
    *,
    model_version: str,
    training_data_uri: str,
    output_uri: str,
    role_arn: str,
    training_image: str,
    instance_type: str = "ml.m5.large",
) -> Dict[str, Any]:
    if not training_data_uri.startswith("s3://"):
        raise ValueError("training_data_uri must be an s3:// URI")
    if not output_uri.startswith("s3://"):
        raise ValueError("output_uri must be an s3:// URI")
    if not role_arn or not training_image:
        raise ValueError("SageMaker role and approved training image are required")
    return {
        "TrainingJobName": training_job_name(model_version),
        "RoleArn": role_arn,
        "AlgorithmSpecification": {
            "TrainingImage": training_image,
            "TrainingInputMode": "File",
            "EnableSageMakerMetricsTimeSeries": True,
        },
        "InputDataConfig": [
            {
                "ChannelName": "train",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": training_data_uri,
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "application/json",
            }
        ],
        "OutputDataConfig": {"S3OutputPath": output_uri},
        "ResourceConfig": {
            "InstanceType": instance_type,
            "InstanceCount": 1,
            "VolumeSizeInGB": 20,
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "EnableNetworkIsolation": True,
        "EnableInterContainerTrafficEncryption": True,
        "Tags": [
            {"Key": "compass:workload", "Value": "document-classification"},
            {"Key": "compass:model-version", "Value": model_version},
            {"Key": "compass:synthetic-only", "Value": "true"},
        ],
    }


class SageMakerTrainingAdapter:
    def __init__(self, client=None):
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(
            os.environ.get("SAGEMAKER_EXECUTION_ROLE_ARN")
            and os.environ.get("SAGEMAKER_TRAINING_IMAGE")
        )

    def submit(
        self,
        *,
        model_version: str,
        training_data_uri: str,
        output_uri: str,
    ) -> Dict[str, Any]:
        if not self.configured:
            return {
                "adapter": "sagemaker",
                "status": "not-submitted",
                "configured": False,
                "reason": (
                    "SAGEMAKER_EXECUTION_ROLE_ARN and SAGEMAKER_TRAINING_IMAGE "
                    "must reference Government-approved resources"
                ),
            }
        request = build_training_job_request(
            model_version=model_version,
            training_data_uri=training_data_uri,
            output_uri=output_uri,
            role_arn=os.environ["SAGEMAKER_EXECUTION_ROLE_ARN"],
            training_image=os.environ["SAGEMAKER_TRAINING_IMAGE"],
            instance_type=os.environ.get("SAGEMAKER_TRAINING_INSTANCE", "ml.m5.large"),
        )
        if self._client is None:
            import boto3

            self._client = boto3.client("sagemaker")
        response = self._client.create_training_job(**request)
        return {
            "adapter": "sagemaker",
            "status": "submitted",
            "configured": True,
            "training_job_name": request["TrainingJobName"],
            "training_job_arn": response.get("TrainingJobArn"),
            "request_digest": __import__("hashlib")
            .sha256(json.dumps(request, sort_keys=True, default=str).encode("utf-8"))
            .hexdigest(),
        }


def package_group_name() -> str:
    return os.environ.get(
        "SAGEMAKER_MODEL_PACKAGE_GROUP", "compass-document-classifier"
    )


def deployment_target(
    mode: str, state: Mapping[str, Any] | None = None
) -> Dict[str, Any]:
    if mode == "sagemaker":
        return {
            "kind": "sagemaker-registry",
            "model_package_group": package_group_name(),
            "online_endpoint": bool((state or {}).get("endpoint_name")),
            "endpoint_name": (state or {}).get("endpoint_name"),
        }
    return {
        "kind": "deterministic-demo-adapter",
        "online_endpoint": False,
        "disclosure": "Inference runs in the Lambda adapter; no SageMaker endpoint is claimed.",
    }

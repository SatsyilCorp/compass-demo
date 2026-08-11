from __future__ import annotations

from pathlib import Path
import sys


FUNCTION_DIR = Path(__file__).resolve().parents[1]
if str(FUNCTION_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTION_DIR))

import sagemaker_adapter  # noqa: E402


def test_sagemaker_request_enforces_network_and_transport_protection():
    request = sagemaker_adapter.build_training_job_request(
        model_version="doc-nb-123456789abc",
        training_data_uri="s3://training-bucket/training/",
        output_uri="s3://training-bucket/output/",
        role_arn="arn:aws:iam::111122223333:role/compass-sagemaker",
        training_image="111122223333.dkr.ecr.us-east-1.amazonaws.com/approved:1",
    )

    assert request["EnableNetworkIsolation"] is True
    assert request["EnableInterContainerTrafficEncryption"] is True
    assert request["StoppingCondition"]["MaxRuntimeInSeconds"] == 1800
    assert request["ResourceConfig"]["InstanceCount"] == 1
    assert request["InputDataConfig"][0]["DataSource"]["S3DataSource"][
        "S3Uri"
    ].startswith("s3://")


def test_sagemaker_adapter_refuses_to_claim_submission_without_configuration(
    monkeypatch,
):
    monkeypatch.delenv("SAGEMAKER_EXECUTION_ROLE_ARN", raising=False)
    monkeypatch.delenv("SAGEMAKER_TRAINING_IMAGE", raising=False)

    result = sagemaker_adapter.SageMakerTrainingAdapter().submit(
        model_version="doc-nb-123",
        training_data_uri="s3://training-bucket/training/",
        output_uri="s3://training-bucket/output/",
    )

    assert result["status"] == "not-submitted"
    assert result["configured"] is False
    assert "training_job_arn" not in result

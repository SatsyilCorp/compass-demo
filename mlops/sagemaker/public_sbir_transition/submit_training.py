#!/usr/bin/env python3
"""Build and optionally submit the governed public SBIR SageMaker job.

The default is a dry run. ``--submit`` is required for AWS writes. Submitted
jobs use a unique, digest-bound S3 prefix so the exact inputs stay auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Sequence


DEFAULT_IMAGE = (
    "683313688378.dkr.ecr.us-east-1.amazonaws.com/"
    "sagemaker-scikit-learn:1.4-2-cpu-py3"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_source_archive(repo: Path, target: Path) -> str:
    source_root = repo / "public_intelligence" / "models"
    trainer_root = repo / "mlops" / "sagemaker" / "public_sbir_transition"
    files = [trainer_root / "train.py"] + sorted(source_root.glob("*.py"))
    if any(not path.is_file() for path in files):
        raise ValueError("training source tree is incomplete")
    with tarfile.open(target, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            arcname = (
                "train.py"
                if path == trainer_root / "train.py"
                else f"public_intelligence/models/{path.name}"
            )
            info = archive.gettarinfo(str(path), arcname=arcname)
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    return sha256_file(target)


def build_job_spec(
    *,
    job_name: str,
    role_arn: str,
    image_uri: str,
    bucket: str,
    prefix: str,
    kms_key_arn: str,
    dataset_sha256: str,
    source_sha256: str,
) -> dict[str, Any]:
    root = prefix.strip("/")
    return {
        "TrainingJobName": job_name,
        "RoleArn": role_arn,
        "AlgorithmSpecification": {
            "TrainingImage": image_uri,
            "TrainingInputMode": "File",
            "EnableSageMakerMetricsTimeSeries": True,
            "ContainerEntrypoint": ["/bin/sh"],
            "ContainerArguments": ["/opt/ml/input/data/code/run.sh"],
        },
        "InputDataConfig": [
            {
                "ChannelName": "train",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket}/{root}/input/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "application/jsonlines",
                "CompressionType": "None",
                "RecordWrapperType": "None",
            },
            {
                "ChannelName": "code",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket}/{root}/code/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "application/octet-stream",
                "CompressionType": "None",
                "RecordWrapperType": "None",
            },
        ],
        "OutputDataConfig": {
            "S3OutputPath": f"s3://{bucket}/{root}/output/",
            "KmsKeyId": kms_key_arn,
        },
        "ResourceConfig": {
            "InstanceType": "ml.m5.large",
            "InstanceCount": 1,
            "VolumeSizeInGB": 20,
            "VolumeKmsKeyId": kms_key_arn,
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": 1800},
        "EnableNetworkIsolation": True,
        "EnableInterContainerTrafficEncryption": True,
        "Environment": {
            "COMPASS_DATASET_SHA256": dataset_sha256,
            "COMPASS_SOURCE_SHA256": source_sha256,
        },
        "Tags": [
            {"Key": "compass:component", "Value": "public-intelligence"},
            {"Key": "compass:data-classification", "Value": "public"},
            {"Key": "compass:model-kind", "Value": "sbir-transition"},
            {"Key": "compass:approval-state", "Value": "candidate-only"},
        ],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--kms-key-arn", required=True)
    parser.add_argument("--image-uri", default=DEFAULT_IMAGE)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", default="satsyil")
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--submit", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dataset = args.dataset.resolve()
    if not dataset.is_file():
        raise SystemExit(f"dataset does not exist: {dataset}")
    repo = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory(prefix="compass-sbir-training-") as directory:
        archive = Path(directory) / "source.tar.gz"
        source_sha256 = build_source_archive(repo, archive)
        dataset_sha256 = sha256_file(dataset)
        spec = build_job_spec(
            job_name=args.job_name,
            role_arn=args.role_arn,
            image_uri=args.image_uri,
            bucket=args.bucket,
            prefix=args.prefix,
            kms_key_arn=args.kms_key_arn,
            dataset_sha256=dataset_sha256,
            source_sha256=source_sha256,
        )
        receipt = {
            "contract": "compass.sagemaker-training-submission.v1",
            "submitted": args.submit,
            "job": spec,
            "inputs": {
                "dataset_sha256": dataset_sha256,
                "source_sha256": source_sha256,
            },
        }
        if args.submit:
            import boto3

            session = boto3.Session(profile_name=args.profile, region_name=args.region)
            identity = session.client("sts").get_caller_identity()
            if identity["Account"] != args.expected_account_id:
                raise SystemExit("AWS account mismatch, refusing submission")
            root = args.prefix.strip("/")
            encryption = {
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": args.kms_key_arn,
            }
            s3 = session.client("s3")
            for local, key in (
                (dataset, f"{root}/input/dataset.jsonl"),
                (archive, f"{root}/code/source.tar.gz"),
                (Path(__file__).with_name("run.sh"), f"{root}/code/run.sh"),
            ):
                s3.upload_file(str(local), args.bucket, key, ExtraArgs=encryption)
            response = session.client("sagemaker").create_training_job(**spec)
            receipt["training_job_arn"] = response["TrainingJobArn"]
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Resolve Compass cost dimensions through the official AWS Price List API.

The checked snapshot is reviewed evidence. This command prints matching Price
List products by default. Pass --output to write a candidate snapshot for
review rather than silently replacing the checked source.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3


SPECS = {
    "lambda_arm_gb_second": ("AWSLambda", {"group": "AWS-Lambda-Duration-ARM"}),
    "lambda_arm_request": ("AWSLambda", {"group": "AWS-Lambda-Requests-ARM"}),
    "s3_standard_gb_month": ("AmazonS3", {"usagetype": "TimedStorage-ByteHrs", "volumeType": "Standard"}),
    "s3_put_request": ("AmazonS3", {"usagetype": "Requests-Tier1"}),
    "s3_get_request": ("AmazonS3", {"usagetype": "Requests-Tier2"}),
    "sqs_standard_request": ("AWSQueueService", {"usagetype": "Requests-RBP", "queueType": "Standard"}),
    "step_functions_transition": ("AmazonStates", {"usagetype": "USE1-StateTransition"}),
    "dynamodb_write_request_unit": ("AmazonDynamoDB", {"usagetype": "WriteRequestUnits"}),
    "dynamodb_read_request_unit": ("AmazonDynamoDB", {"usagetype": "ReadRequestUnits"}),
    "athena_tb_scanned": ("AmazonAthena", {"usagetype": "USE1-DataScannedInTB"}),
    "glue_dpu_hour": ("AWSGlue", {"usagetype": "USE1-ETL-DPU-Hour"}),
    "nat_gateway_hour": ("AmazonEC2", {"usagetype": "NatGateway-Hours"}),
    "nat_gateway_gb": ("AmazonEC2", {"usagetype": "NatGateway-Bytes"}),
    "aurora_serverless_v2_acu_hour": ("AmazonRDS", {"usagetype": "Aurora:ServerlessV2Usage", "databaseEngine": "Aurora PostgreSQL"}),
    "kms_key_month": ("awskms", {"usagetype": "us-east-1-KMS-Keys"}),
    "kms_request": ("awskms", {"usagetype": "us-east-1-KMS-Requests"}),
    "http_api_request": ("AmazonApiGateway", {"usagetype": "USE1-ApiGatewayHttpRequest"}),
}


def resolve(client, service_code: str, attributes: dict[str, str]) -> list[dict[str, Any]]:
    filters = [{"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"}]
    filters.extend({"Type": "TERM_MATCH", "Field": key, "Value": value} for key, value in attributes.items())
    response = client.get_products(ServiceCode=service_code, Filters=filters, MaxResults=100)
    return [json.loads(item) for item in response.get("PriceList", [])]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=None)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile) if args.profile else boto3.Session()
    client = session.client("pricing", region_name="us-east-1")
    result = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "region": "us-east-1",
        "location": "US East (N. Virginia)",
        "price_source": "AWS Price List Query API",
        "matches": {
            key: resolve(client, service_code, attributes)
            for key, (service_code, attributes) in SPECS.items()
        },
    }
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

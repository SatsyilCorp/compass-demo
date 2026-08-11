"""Durable S3 and DynamoDB repository for document and MLOps receipts."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional


def _decimal_safe(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {str(key): _decimal_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decimal_safe(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


class AwsRepository:
    """Small persistence interface whose physical names stay server-side."""

    def __init__(self, *, s3_client=None, table=None):
        self.bucket = os.environ.get("DOCUMENT_LAKE_BUCKET", "")
        self.table_name = os.environ.get("DOCUMENT_ML_TABLE", "")
        if not self.bucket or not self.table_name:
            raise RuntimeError(
                "DOCUMENT_LAKE_BUCKET and DOCUMENT_ML_TABLE are required"
            )
        self._s3_client = s3_client
        self._table = table

    @property
    def s3(self):
        if self._s3_client is None:
            import boto3
            from botocore.config import Config

            self._s3_client = boto3.client(
                "s3",
                config=Config(signature_version="s3v4"),
            )
        return self._s3_client

    @property
    def table(self):
        if self._table is None:
            import boto3

            self._table = boto3.resource("dynamodb").Table(self.table_name)
        return self._table

    def put_json(
        self, key: str, value: Any, *, metadata: Optional[Mapping[str, str]] = None
    ) -> str:
        body = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            Metadata=dict(metadata or {}),
        )
        return f"lake://{key}"

    def get_json(self, key: str) -> Dict[str, Any]:
        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        return json.loads(response["Body"].read())

    def get_bytes(self, bucket: str, key: str) -> tuple[bytes, Dict[str, Any]]:
        response = self.s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read(), response

    def copy_object(
        self, source_bucket: str, source_key: str, destination_key: str
    ) -> str:
        self.s3.copy_object(
            Bucket=self.bucket,
            Key=destination_key,
            CopySource={"Bucket": source_bucket, "Key": source_key},
            MetadataDirective="COPY",
        )
        return f"lake://{destination_key}"

    def presign_upload(
        self, key: str, content_type: str, *, expires_in: int = 900
    ) -> str:
        return self.s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )

    def put_record(
        self, kind: str, record_id: str, value: Mapping[str, Any]
    ) -> Dict[str, Any]:
        item = {
            **dict(value),
            "pk": f"{kind.upper()}#{record_id}",
            "sk": "STATE",
            "gsi1pk": kind.upper(),
            "gsi1sk": f"{value.get('updated_at') or value.get('created_at') or ''}#{record_id}",
            "record_type": kind.lower(),
            "record_id": record_id,
        }
        self.table.put_item(Item=_decimal_safe(item))
        return dict(value)

    def get_record(self, kind: str, record_id: str) -> Optional[Dict[str, Any]]:
        response = self.table.get_item(
            Key={"pk": f"{kind.upper()}#{record_id}", "sk": "STATE"},
            ConsistentRead=True,
        )
        item = response.get("Item")
        return _json_safe(item) if item else None

    def merge_record(
        self, kind: str, record_id: str, patch: Mapping[str, Any]
    ) -> Dict[str, Any]:
        current = self.get_record(kind, record_id) or {}
        merged = {**current, **dict(patch)}
        for private_key in ("pk", "sk", "gsi1pk", "gsi1sk", "record_type", "record_id"):
            merged.pop(private_key, None)
        self.put_record(kind, record_id, merged)
        return merged

    def list_records(self, kind: str, *, limit: int = 25) -> List[Dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        response = self.table.query(
            IndexName="by-type",
            KeyConditionExpression=Key("gsi1pk").eq(kind.upper()),
            ScanIndexForward=False,
            Limit=max(1, min(100, int(limit))),
        )
        return [_json_safe(item) for item in response.get("Items", [])]

    def put_alias(
        self, alias: str, model_version: str, value: Mapping[str, Any]
    ) -> None:
        item = {
            **dict(value),
            "pk": f"MODEL_ALIAS#{alias}",
            "sk": "STATE",
            "model_version": model_version,
        }
        self.table.put_item(Item=_decimal_safe(item))

    def get_alias(self, alias: str = "champion") -> Optional[Dict[str, Any]]:
        response = self.table.get_item(
            Key={"pk": f"MODEL_ALIAS#{alias}", "sk": "STATE"},
            ConsistentRead=True,
        )
        item = response.get("Item")
        return _json_safe(item) if item else None

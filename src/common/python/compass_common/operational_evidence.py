"""Durable operational lineage and notification receipts.

This module is the narrow interface used by ingestion, public acquisition, and
MLOps implementations. Domain services commit their authoritative artifact
first, then call :func:`record_stage` or :func:`record_signal`. A failed
projection never rolls back the domain transaction, and the repairable warning
is emitted as structured log evidence.

The shared DynamoDB table is a projection, not a second data system. Stage
receipts contain logical locators and digests only. Raw records, physical
bucket names, account identifiers, tokens, and exception text are excluded.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional


MAX_TEXT = 500
ALLOWED_STATUSES = {
    "acknowledged",
    "completed",
    "failed",
    "open",
    "quarantined",
    "running",
    "skipped",
}
ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}

_TABLE = None
_SNS = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _safe_text(value: Any, *, maximum: int = MAX_TEXT) -> str:
    return " ".join(str(value or "").replace("\u2014", " - ").split())[:maximum]


def _safe_evidence_class(value: Any) -> str | None:
    normalized = _safe_text(value, maximum=80).lower().replace("_", "-").replace(" ", "-")
    return normalized or None


def _safe_detail(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    allowed = {
        "accepted_records",
        "added_records",
        "attempt",
        "changed_records",
        "confidence",
        "consumer",
        "delivery_channel",
        "delivery_status",
        "duration_ms",
        "evidence_class",
        "failed_records",
        "failure_code",
        "lag_seconds",
        "model_version",
        "quality_score",
        "record_count",
        "rejected_records",
        "not_observed_records",
        "pages_fetched",
        "profile",
        "requested_records",
        "response_bytes",
        "retry_count",
        "schema",
        "schema_version",
        "source_revision",
        "source_object_version",
        "threshold",
        "unchanged_records",
        "watermark",
        "field_mapping",
        "rules",
    }
    out: Dict[str, Any] = {}
    for key, item in dict(value or {}).items():
        if key not in allowed or item is None:
            continue
        if isinstance(item, (bool, int, float, Decimal)):
            out[key] = float(item) if isinstance(item, Decimal) else item
        elif isinstance(item, str):
            out[key] = _safe_text(item)
        elif isinstance(item, list):
            out[key] = [_safe_text(part, maximum=120) for part in item[:30]]
        elif isinstance(item, Mapping):
            out[key] = {
                _safe_text(child_key, maximum=80): _safe_text(child_value, maximum=160)
                for child_key, child_value in list(item.items())[:30]
            }
    return out


def _decimal_safe(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {str(key): _decimal_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decimal_safe(item) for item in value]
    return value


def _table():
    global _TABLE
    table_name = os.environ.get("OPERATIONS_TABLE", "").strip()
    if not table_name:
        return None
    if _TABLE is None:
        import boto3

        _TABLE = boto3.resource("dynamodb").Table(table_name)
    return _TABLE


def _sns():
    global _SNS
    if _SNS is None:
        import boto3

        _SNS = boto3.client("sns")
    return _SNS


def _write(item: Mapping[str, Any]) -> bool:
    table = _table()
    if table is None:
        return False
    table.put_item(Item=_decimal_safe(dict(item)))
    return True


def _write_once(item: Mapping[str, Any]) -> Optional[bool]:
    """Create an event once, returning False when its stable key already exists."""
    table = _table()
    if table is None:
        return None
    try:
        table.put_item(
            Item=_decimal_safe(dict(item)),
            ConditionExpression="attribute_not_exists(pk)",
        )
        return True
    except Exception as exc:  # noqa: BLE001 - avoid a botocore import in the layer
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code == "ConditionalCheckFailedException" or "ConditionalCheckFailed" in type(exc).__name__:
            return False
        raise


def record_stage(
    *,
    run_id: str,
    run_kind: str,
    sequence: int,
    stage_id: str,
    label: str,
    status: str,
    source: str | None = None,
    destination: str | None = None,
    source_sha256: str | None = None,
    input_sha256: str | None = None,
    output_sha256: str | None = None,
    actor: str = "system-workload",
    detail: Mapping[str, Any] | None = None,
    evidence_class: str | None = None,
    occurred_at: str | None = None,
) -> bool:
    """Upsert one idempotent stage receipt and return whether it was written."""
    if not run_id or not stage_id:
        return False
    normalized_status = status.lower()
    if normalized_status not in ALLOWED_STATUSES:
        normalized_status = "failed"
    timestamp = occurred_at or utc_now()
    safe_detail = _safe_detail(detail)
    safe_evidence_class = _safe_evidence_class(
        evidence_class or safe_detail.get("evidence_class")
    )
    receipt = {
        "contract": "compass.operational-stage.v1",
        "run_id": _safe_text(run_id, maximum=180),
        "run_kind": _safe_text(run_kind, maximum=80),
        "sequence": max(0, int(sequence)),
        "stage_id": _safe_text(stage_id, maximum=100),
        "label": _safe_text(label, maximum=160),
        "status": normalized_status,
        "source": _safe_text(source, maximum=300) if source else None,
        "destination": _safe_text(destination, maximum=300) if destination else None,
        "source_sha256": _safe_text(source_sha256, maximum=64) if source_sha256 else None,
        "input_sha256": _safe_text(input_sha256, maximum=64) if input_sha256 else None,
        "output_sha256": _safe_text(output_sha256, maximum=64) if output_sha256 else None,
        "actor": _safe_text(actor, maximum=160),
        "detail": safe_detail,
        "evidence_class": safe_evidence_class,
        "updated_at": timestamp,
    }
    receipt["receipt_sha256"] = canonical_digest(receipt)
    item = {
        **receipt,
        "pk": f"RUN#{receipt['run_id']}",
        "sk": f"STAGE#{receipt['sequence']:03d}#{receipt['stage_id']}",
        "gsi1pk": "LINEAGE",
        "gsi1sk": f"{timestamp}#{receipt['run_id']}#{receipt['sequence']:03d}",
        "record_type": "stage",
    }
    try:
        return _write(item)
    except Exception as exc:  # noqa: BLE001 - projection is repairable
        print(
            json.dumps(
                {
                    "event_type": "operational_stage_projection_failed",
                    "run_id": receipt["run_id"],
                    "stage_id": receipt["stage_id"],
                    "error_type": type(exc).__name__,
                }
            )
        )
        return False


def record_signal(
    *,
    category: str,
    severity: str,
    title: str,
    message: str,
    run_id: str | None = None,
    evidence_uri: str | None = None,
    detail: Mapping[str, Any] | None = None,
    evidence_class: str | None = None,
    event_id: str | None = None,
    occurred_at: str | None = None,
    publish: bool = True,
) -> Optional[str]:
    """Persist a safe, deduplicated operational signal and optionally publish it."""
    timestamp = occurred_at or utc_now()
    safe_category = _safe_text(category, maximum=80) or "operations"
    safe_run = _safe_text(run_id, maximum=180) if run_id else None
    stable_id = event_id or (
        "sig-"
        + canonical_digest(
            {
                "category": safe_category,
                "run_id": safe_run,
                "title": _safe_text(title, maximum=160),
            }
        )[:24]
    )
    safe_severity = severity.lower()
    if safe_severity not in ALLOWED_SEVERITIES:
        safe_severity = "medium"
    safe_detail = _safe_detail(detail)
    safe_evidence_class = _safe_evidence_class(
        evidence_class or safe_detail.get("evidence_class")
    )
    item = {
        "contract": "compass.operational-signal.v1",
        "pk": f"SIGNAL#{stable_id}",
        "sk": "STATE",
        "gsi1pk": "SIGNAL",
        "gsi1sk": f"{timestamp}#{stable_id}",
        "record_type": "signal",
        "event_id": stable_id,
        "category": safe_category,
        "severity": safe_severity,
        "title": _safe_text(title, maximum=160),
        "message": _safe_text(message, maximum=500),
        "run_id": safe_run,
        "evidence_uri": _safe_text(evidence_uri, maximum=300) if evidence_uri else None,
        "detail": safe_detail,
        "evidence_class": safe_evidence_class,
        "status": "open",
        "acknowledged_at": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "delivery": {
            "channel": "in-app",
            "status": "recorded",
        },
    }
    item["receipt_sha256"] = canonical_digest(item)
    try:
        created = _write_once(item)
        if created is None:
            return None
        if created is False:
            return stable_id
        topic = os.environ.get("OPERATIONS_TOPIC_ARN", "").strip()
        if publish and topic:
            payload = {
                key: item[key]
                for key in (
                    "contract",
                    "event_id",
                    "category",
                    "severity",
                    "title",
                    "message",
                    "run_id",
                    "evidence_uri",
                    "evidence_class",
                    "created_at",
                    "receipt_sha256",
                )
            }
            try:
                _sns().publish(
                    TopicArn=topic,
                    Subject=f"Compass {safe_severity.upper()}: {item['title']}"[:100],
                    Message=json.dumps(payload, sort_keys=True),
                    MessageAttributes={
                        "severity": {"DataType": "String", "StringValue": safe_severity},
                        "category": {"DataType": "String", "StringValue": safe_category},
                    },
                )
                item["delivery"] = {"channel": "sns", "status": "published"}
                item["updated_at"] = utc_now()
                item["receipt_sha256"] = canonical_digest(item)
                _write(item)
            except Exception as exc:  # noqa: BLE001 - in-app receipt remains durable
                print(
                    json.dumps(
                        {
                            "event_type": "operational_signal_publish_failed",
                            "event_id": stable_id,
                            "error_type": type(exc).__name__,
                        }
                    )
                )
        return stable_id
    except Exception as exc:  # noqa: BLE001 - never mask the domain result
        print(
            json.dumps(
                {
                    "event_type": "operational_signal_projection_failed",
                    "event_id": stable_id,
                    "error_type": type(exc).__name__,
                }
            )
        )
        return None

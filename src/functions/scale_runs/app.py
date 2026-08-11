"""Compass Scale Run control plane and durable orchestration actions.

HTTP operations are corporate-poweruser only. Step Functions invokes the same
Lambda with a fixed ``action`` field for dispatch, progress checks, Athena
conversion, and finalization. The browser never chooses a raw record count,
partition size, concurrency, retention, physical locator, or price.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from compass_common import http
from compass_common.scale_cost import (
    PriceCatalog,
    assert_cost_gate,
    estimate_incremental,
    modeled_quantities,
)
from compass_common.scale_workload import (
    CONTRACT_VERSION,
    DATASETS,
    DEFAULT_SEED,
    PROFILES,
    canonical_json_bytes,
    get_profile,
    iter_partition_specs,
    sha256_hex,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TERMINAL_STATES = {
    "completed",
    "completed_with_quarantine",
    "failed",
    "canceled",
}
ACTIVE_STATES = {
    "requested",
    "generating",
    "landing",
    "partitioning",
    "validating",
    "curating",
    "enriching",
    "aggregating",
    "canceling",
}
PLAN_TTL_MINUTES = 15
RUN_RETENTION_DAYS = 14
LOCK_TTL_HOURS = 3
DEFECT_RATE_BASIS_POINTS = 100
DEFAULT_EXPORT_RETENTION_HOURS = 24
CONTROL_EXPORT_GB_SECONDS = Decimal(150)

PUBLIC_STATUS = {
    "requested": "queued",
    "generating": "generating",
    "landing": "ingesting",
    "partitioning": "ingesting",
    "validating": "quality",
    "curating": "quality",
    "enriching": "intelligence",
    "aggregating": "intelligence",
    "canceling": "cancelling",
    "canceled": "cancelled",
    "completed_with_quarantine": "completed",
    "completed": "completed",
    "failed": "failed",
}
PUBLIC_STAGE = {
    "requested": "plan",
    "generating": "generate",
    "landing": "ingest",
    "partitioning": "ingest",
    "validating": "quality",
    "curating": "curate",
    "enriching": "intelligence",
    "aggregating": "intelligence",
    "canceling": "evidence",
    "canceled": "evidence",
    "completed_with_quarantine": "evidence",
    "completed": "evidence",
    "failed": "evidence",
}
PUBLIC_PLAN_STAGES = (
    ("plan", "Plan", "Bind the seed, profile, limits, and cost ceiling.", "Scale control"),
    ("buffer", "Buffer", "Absorb burst traffic and apply backpressure.", "Event queue"),
    ("generate", "Generate", "Create deterministic records inside bounded partition workers.", "Generator workers"),
    ("ingest", "Ingest", "Write immutable raw objects and validate manifests.", "Raw lake"),
    ("quality", "Quality", "Apply schema, completeness, and integrity gates.", "Quality workers"),
    ("curate", "Curate", "Publish partitioned governed JSON Lines datasets.", "Curated lake"),
    ("intelligence", "Intelligence", "Convert Parquet and merge full-corpus topics and anomalies.", "Athena and receipt merge"),
    ("export", "Export", "Seal a checksummed manifest over governed Parquet objects.", "Export worker"),
    ("evidence", "Evidence", "Seal metrics, cost, lineage, and audit receipts.", "Evidence ledger"),
)
PUBLIC_DATASETS = (
    ("grants", "Grant records", "Portfolio identity, award, and program attributes"),
    ("finance", "Financial events", "Obligations, expenditures, and forecast movements"),
    ("milestones", "Milestones", "Technical schedule, status, and delivery outcomes"),
    ("documents", "Documents", "Synthetic reports, metadata, and linked portfolio context"),
    ("licenses", "License records", "Entitlements, renewals, and utilization posture"),
    ("stream_events", "Stream events", "Ordered operational signals for burst and freshness analysis"),
)
COST_LABELS = {
    "lambda_arm_request": "Worker requests",
    "lambda_arm_gb_second": "Worker compute",
    "s3_standard_gb_month": "Lake storage",
    "s3_put_request": "Lake writes",
    "s3_get_request": "Lake reads",
    "sqs_standard_request": "Queue requests",
    "step_functions_transition": "Orchestration transitions",
    "dynamodb_write_request_unit": "Ledger writes",
    "dynamodb_read_request_unit": "Ledger reads",
    "dynamodb_storage_gb_month": "Ledger storage",
    "athena_tb_scanned": "Analytic query scan",
    "cloudwatch_log_ingest_gb": "Telemetry ingestion",
    "kms_request": "Encryption requests",
    "http_api_request": "Control interface requests",
}

_TABLE = None
_DDB_CLIENT = None
_SQS = None
_SFN = None
_ATHENA = None
_S3 = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _epoch(value: datetime) -> int:
    return int(value.timestamp())


def _table():
    global _TABLE
    if _TABLE is None:
        import boto3

        _TABLE = boto3.resource("dynamodb").Table(os.environ["SCALE_RUNS_TABLE"])
    return _TABLE


def _ddb_client():
    global _DDB_CLIENT
    if _DDB_CLIENT is None:
        import boto3

        _DDB_CLIENT = boto3.client("dynamodb")
    return _DDB_CLIENT


def _sqs():
    global _SQS
    if _SQS is None:
        import boto3

        _SQS = boto3.client("sqs")
    return _SQS


def _sfn():
    global _SFN
    if _SFN is None:
        import boto3

        _SFN = boto3.client("stepfunctions")
    return _SFN


def _athena():
    global _ATHENA
    if _ATHENA is None:
        import boto3

        _ATHENA = boto3.client("athena")
    return _ATHENA


def _s3():
    global _S3
    if _S3 is None:
        import boto3

        _S3 = boto3.client("s3")
    return _S3


def _serialize(item: Mapping[str, Any]) -> dict[str, Any]:
    from boto3.dynamodb.types import TypeSerializer

    serializer = TypeSerializer()
    return {key: serializer.serialize(value) for key, value in item.items()}


def _deserialize(item: Mapping[str, Any]) -> dict[str, Any]:
    from boto3.dynamodb.types import TypeDeserializer

    deserializer = TypeDeserializer()
    return {key: deserializer.deserialize(value) for key, value in item.items()}


def _max_records() -> int:
    return int(os.environ.get("SCALE_MAX_RECORDS", "100000"))


def _max_cost() -> Decimal:
    return Decimal(os.environ.get("SCALE_MAX_ESTIMATED_COST_USD", "10.00"))


def _max_concurrency() -> int:
    return int(os.environ.get("SCALE_MAX_CONCURRENCY", "4"))


def _feature_enabled() -> bool:
    return os.environ.get("SCALE_FEATURE_ENABLED", "false").lower() == "true"


def _actor(claims: http.Claims) -> str:
    return claims.username or claims.sub or "unknown-poweruser"


def _authorized(event: Mapping[str, Any]) -> tuple[http.Claims | None, dict[str, Any] | None]:
    claims = http.get_claims(dict(event))
    if not claims.is_authenticated:
        return None, http.unauthorized()
    if claims.role != "poweruser" or not claims.is_corporate:
        return None, http.forbidden("Scale Lab requires the corporate poweruser persona")
    return claims, None


def _capacity_state(profile_id: str) -> tuple[str, str | None]:
    profile = get_profile(profile_id)
    if not _feature_enabled():
        return "locked", "Scale Lab is disabled in this deployment"
    if profile.total_records > _max_records():
        return "locked", f"Deployment limit is {_max_records():,} records"
    if profile_id == "1m":
        proof = _table().get_item(
            Key={"pk": "PROOF#100k", "sk": "META"},
            ConsistentRead=True,
        ).get("Item")
        if not proof:
            return "locked", "Complete a successful 100k Scale Run first"
    return "ready", None


def _partition_count(profile) -> int:
    return sum(
        1 for dataset in DATASETS for _ in iter_partition_specs(profile, dataset)
    )


def _profile_payload(profile_id: str) -> dict[str, Any]:
    profile = get_profile(profile_id)
    capacity_state, locked_reason = _capacity_state(profile_id)
    partitions = _partition_count(profile)
    quantities = modeled_quantities(
        profile.total_records,
        profile.default_partition_size,
        partition_count=partitions,
    )
    estimate = estimate_incremental(
        profile_id,
        quantities,
        deployed_hard_cap_usd=_max_cost(),
    )
    expected_seconds = max(
        15,
        math.ceil(partitions / max(_max_concurrency(), 1)) * 30 + 45,
    )
    return {
        "id": profile_id,
        "label": {
            "1k": "Quick proof",
            "10k": "Evaluator run",
            "100k": "Prepared scale proof",
            "1m": "Capacity run",
        }[profile_id],
        "total_records": profile.total_records,
        "dataset_counts": profile.dataset_counts,
        "partition_records": profile.default_partition_size,
        "partitions": partitions,
        "defect_rate_basis_points": DEFECT_RATE_BASIS_POINTS,
        "max_concurrency": _max_concurrency(),
        "retention_days": 7,
        "expected_duration_seconds": expected_seconds,
        "estimated_cost_usd": estimate["estimated_cost_usd"],
        "maximum_cost_usd": estimate["maximum_cost_usd"],
        "capacity_state": capacity_state,
        "locked_reason": locked_reason,
        "synthetic_only": True,
    }


def _public_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    profile_id = str(profile["id"])
    total = int(profile["total_records"])
    locked_reason = profile.get("locked_reason")
    ready_notes = {
        "1k": "Runs inside the protected smoke-test capacity envelope.",
        "10k": "Recommended for a live demonstration.",
        "100k": "Uses the prepared scale-proof capacity envelope.",
        "1m": "Full capacity policy and a successful 100k proof are required.",
    }
    descriptions = {
        "1k": "Fast smoke run for validating every production path.",
        "10k": "Presenter-ready workload with visible parallel processing.",
        "100k": "Sustained scale run across partitioned ingestion and intelligence.",
        "1m": "Full production rehearsal with a cost and capacity gate.",
    }
    return {
        "id": profile_id,
        "label": f"{total:,} records",
        "short_label": profile_id.upper(),
        "total_records": total,
        "description": descriptions[profile_id],
        "capacity_state": str(profile["capacity_state"]),
        "capacity_note": str(locked_reason or ready_notes[profile_id]),
        "recommended": profile_id == "10k",
    }


def _profiles_response() -> dict[str, Any]:
    return {
        "generated_at": _iso(),
        "profiles": [
            _public_profile(_profile_payload(profile_id)) for profile_id in PROFILES
        ],
    }


def _create_plan(body: Mapping[str, Any], claims: http.Claims) -> dict[str, Any]:
    profile_id = str(body.get("profile_id") or "").strip().lower()
    profile = get_profile(profile_id)
    seed_raw = body.get("seed", DEFAULT_SEED)
    if isinstance(seed_raw, bool):
        raise TypeError("seed must be an integer")
    seed = int(seed_raw)
    if seed < 0 or seed > 9_999_999_999:
        raise ValueError("seed must be between 0 and 9999999999")
    capacity_state, locked_reason = _capacity_state(profile_id)
    partitions = _partition_count(profile)
    estimate = estimate_incremental(
        profile_id,
        modeled_quantities(
            profile.total_records,
            profile.default_partition_size,
            partition_count=partitions,
        ),
        deployed_hard_cap_usd=_max_cost(),
    )
    assert_cost_gate(estimate)
    created = _now()
    expires = created + timedelta(minutes=PLAN_TTL_MINUTES)
    plan_id = f"plan-{created:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:10]}"
    launch_allowed = capacity_state == "ready" and bool(estimate["within_envelope"])
    plan = {
        "pk": f"PLAN#{plan_id}",
        "sk": "META",
        "entity": "plan",
        "plan_id": plan_id,
        "profile_id": profile_id,
        "seed": seed,
        "profile": _profile_payload(profile_id),
        "cost": estimate,
        "launch_allowed": launch_allowed,
        "locked_reason": locked_reason,
        "created_at": _iso(created),
        "expires_at": _iso(expires),
        "expires_at_epoch": _epoch(expires),
        "created_by": _actor(claims),
        "synthetic_contract": CONTRACT_VERSION,
    }
    _table().put_item(Item=plan, ConditionExpression="attribute_not_exists(pk)")
    return _public_plan(plan)


def _public_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    profile = dict(plan["profile"])
    counts = dict(profile.get("dataset_counts") or {})
    total = int(profile["total_records"])
    public_counts = {
        "grants": int(counts.get("grants", 0)),
        "finance": int(counts.get("finance", 0)),
        "milestones": int(counts.get("milestones", 0)),
        "documents": int(counts.get("documents", 0)),
        "licenses": int(counts.get("licenses", 0)),
        "stream_events": int(counts.get("stream_events", 0)),
    }
    dataset_mix = [
        {
            "domain": domain,
            "label": label,
            "records": public_counts[domain],
            "percentage": round(public_counts[domain] * 100 / total, 2),
            "purpose": purpose,
        }
        for domain, label, purpose in PUBLIC_DATASETS
    ]
    return {
        "plan_id": str(plan["plan_id"]),
        "profile_id": str(plan["profile_id"]),
        "seed": int(plan["seed"]),
        "generated_at": str(plan["created_at"]),
        "capacity_state": str(profile["capacity_state"]),
        "total_records": total,
        "estimated_raw_bytes": total * 1_400,
        "target_duration_seconds": int(profile["expected_duration_seconds"]),
        "concurrency_limit": int(profile["max_concurrency"]),
        "partition_count": int(profile["partitions"]),
        "dataset_mix": dataset_mix,
        "stages": [
            {"id": stage_id, "label": label, "detail": detail, "resource": resource}
            for stage_id, label, detail, resource in PUBLIC_PLAN_STAGES
        ],
        "cost": _public_cost(plan["cost"]),
    }


def _as_number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _public_cost(estimate: Mapping[str, Any]) -> dict[str, Any]:
    line_items = []
    for item in estimate.get("line_items", []):
        key = str(item.get("key") or "unknown")
        quantity = str(item.get("quantity") or "0")
        unit = str(item.get("unit") or "units")
        rate = str(item.get("rate_usd") or "0")
        line_items.append(
            {
                "id": key,
                "label": COST_LABELS.get(key, key.replace("_", " ").title()),
                "estimated_usd": _as_number(item.get("cost_usd")),
                "basis": f"{quantity} {unit} at ${rate} per unit",
            }
        )
    return {
        "currency": "USD",
        "estimated_run_usd": _as_number(estimate.get("estimated_cost_usd")),
        "upper_bound_usd": _as_number(estimate.get("maximum_cost_usd")),
        "incremental_idle_monthly_usd": 0.0,
        "pricing_as_of": str(
            estimate.get("price_snapshot_captured_at")
            or estimate.get("generated_at")
            or _iso()
        ),
        "estimate_source": "aws_price_model",
        "disclaimer": str(
            estimate.get("disclosure")
            or "Actual billed cost can vary with retries, data shape, and log volume."
        ),
        "line_items": line_items,
    }


def _idempotency_digest(actor: str, value: str) -> str:
    return hashlib.sha256(f"{actor}|{value}".encode()).hexdigest()


def _is_transaction_condition_conflict(exc: Exception) -> bool:
    """Recognize only the lock or plan conditions in the four-item transaction."""

    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return False
    error = response.get("Error")
    if not isinstance(error, Mapping) or error.get("Code") != "TransactionCanceledException":
        return False
    reasons = response.get("CancellationReasons")
    if not isinstance(reasons, list) or len(reasons) != 4:
        return False
    saw_known_conflict = False
    for index, reason in enumerate(reasons):
        if not isinstance(reason, Mapping):
            return False
        code = reason.get("Code")
        if code in {None, "None"}:
            continue
        if index in {0, 1} and code == "ConditionalCheckFailed":
            saw_known_conflict = True
            continue
        return False
    return saw_known_conflict


def _aws_error_code(exc: Exception) -> str | None:
    """Read the stable botocore ClientError code without importing botocore."""

    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return None
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("Code")
    return str(code) if code else None


def _is_conditional_check_failure(exc: Exception) -> bool:
    return _aws_error_code(exc) == "ConditionalCheckFailedException"


def _create_run(body: Mapping[str, Any], claims: http.Claims) -> dict[str, Any]:
    plan_id = str(body.get("plan_id") or "").strip()
    key = str(body.get("idempotency_key") or "").strip()
    if not plan_id:
        raise ValueError("plan_id is required")
    if len(key) < 12 or len(key) > 128:
        raise ValueError("idempotency_key must be between 12 and 128 characters")
    actor = _actor(claims)
    digest = _idempotency_digest(actor, key)
    existing = _table().get_item(
        Key={"pk": f"IDEMP#{digest}", "sk": "META"},
        ConsistentRead=True,
    ).get("Item")
    if existing:
        return _get_run_snapshot(str(existing["run_id"]))

    plan = _table().get_item(
        Key={"pk": f"PLAN#{plan_id}", "sk": "META"},
        ConsistentRead=True,
    ).get("Item")
    if not plan:
        raise ValueError("Scale Plan was not found")
    if plan.get("created_by") != actor:
        raise PermissionError("Scale Plan belongs to a different actor")
    if plan.get("consumed_at"):
        raise ValueError("Scale Plan was already consumed")
    if _now() >= datetime.fromisoformat(str(plan["expires_at"])):
        raise ValueError("Scale Plan has expired")
    if not plan.get("launch_allowed"):
        raise ValueError(str(plan.get("locked_reason") or "Scale Plan is not launchable"))
    assert_cost_gate(plan["cost"])

    created = _now()
    run_id = f"scale-{created:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:10]}"
    deadline = created + timedelta(hours=LOCK_TTL_HOURS)
    expires = created + timedelta(days=RUN_RETENTION_DAYS)
    run = {
        "pk": f"RUN#{run_id}",
        "sk": "META",
        "entity": "run",
        "gsi1pk": "RUNS",
        "gsi1sk": f"{_iso(created)}#{run_id}",
        "run_id": run_id,
        "plan_id": plan_id,
        "profile_id": plan["profile_id"],
        "profile": plan["profile"],
        "seed": int(plan["seed"]),
        "synthetic_contract": CONTRACT_VERSION,
        "status": "requested",
        "created_at": _iso(created),
        "updated_at": _iso(created),
        "deadline_at": _iso(deadline),
        "expires_at_epoch": _epoch(expires),
        "requested_by": actor,
        "cost": plan["cost"],
        "total_partitions": 0,
        "running_partitions": 0,
        "completed_partitions": 0,
        "failed_partitions": 0,
        "generated_records": 0,
        "curated_records": 0,
        "quarantined_records": 0,
        "raw_bytes": 0,
        "curated_bytes": 0,
        "quarantine_bytes": 0,
        "parquet_bytes": 0,
        "retry_count": 0,
        "duplicate_replays": 0,
        "worker_duration_ms": 0,
        "idempotency_receipt": digest[:24],
    }
    lock = {
        "pk": "LOCK#ACTIVE",
        "sk": "META",
        "entity": "active_lock",
        "run_id": run_id,
        "profile_id": plan["profile_id"],
        "expires_at_epoch": _epoch(deadline),
    }
    idem = {
        "pk": f"IDEMP#{digest}",
        "sk": "META",
        "entity": "idempotency",
        "run_id": run_id,
        "expires_at_epoch": _epoch(expires),
    }
    try:
        _ddb_client().transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Item": _serialize(lock),
                        "ConditionExpression": "attribute_not_exists(pk) OR expires_at_epoch < :now",
                        "ExpressionAttributeValues": _serialize({":now": _epoch(created)}),
                    }
                },
                {
                    "Update": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Key": _serialize({"pk": f"PLAN#{plan_id}", "sk": "META"}),
                        "UpdateExpression": "SET consumed_at = :at, run_id = :run",
                        "ConditionExpression": "attribute_not_exists(consumed_at)",
                        "ExpressionAttributeValues": _serialize({":at": _iso(created), ":run": run_id}),
                    }
                },
                {
                    "Put": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Item": _serialize(run),
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                },
                {
                    "Put": {
                        "TableName": os.environ["SCALE_RUNS_TABLE"],
                        "Item": _serialize(idem),
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                },
            ]
        )
    except Exception as exc:
        if _is_transaction_condition_conflict(exc):
            raise ValueError("Another Scale Run is active or the plan was consumed") from exc
        raise

    try:
        execution = _sfn().start_execution(
            stateMachineArn=os.environ["SCALE_STATE_MACHINE_ARN"],
            name=run_id,
            input=json.dumps({"run_id": run_id}),
        )
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression="SET execution_started_at = :at, updated_at = :at",
            ExpressionAttributeValues={":at": _iso()},
        )
        logger.info("started Scale Run %s", run_id)
        del execution
    except Exception:
        logger.exception("failed to start Scale Run workflow")
        _fail_run(run_id, "workflow_start_failed")
        raise
    return _get_run_snapshot(run_id)


def _get_run_item(run_id: str) -> dict[str, Any]:
    item = _table().get_item(
        Key={"pk": f"RUN#{run_id}", "sk": "META"},
        ConsistentRead=True,
    ).get("Item")
    if not item:
        raise KeyError(run_id)
    return item


def _queue_evidence() -> dict[str, int]:
    try:
        response = _sqs().get_queue_attributes(
            QueueUrl=os.environ["SCALE_QUEUE_URL"],
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )
        values = response.get("Attributes", {})
        dlq = _sqs().get_queue_attributes(
            QueueUrl=os.environ["SCALE_DLQ_URL"],
            AttributeNames=["ApproximateNumberOfMessages"],
        ).get("Attributes", {})
        return {
            "queue_depth": int(values.get("ApproximateNumberOfMessages", 0)),
            "running_messages": int(values.get("ApproximateNumberOfMessagesNotVisible", 0)),
            "dlq_count": int(dlq.get("ApproximateNumberOfMessages", 0)),
        }
    except Exception:
        logger.exception("queue evidence unavailable")
        return {
            "queue_depth": 0,
            "running_messages": 0,
            "dlq_count": 0,
        }


def _partition_samples(run_id: str, limit: int = 60) -> list[dict[str, Any]]:
    response = _table().query(
        KeyConditionExpression="pk = :pk AND begins_with(sk, :part)",
        ExpressionAttributeValues={":pk": f"RUN#{run_id}", ":part": "PART#"},
        Limit=limit,
    )
    return [
        {
            "dataset": item.get("dataset"),
            "partition_id": item.get("partition_id"),
            "status": item.get("status"),
            "records": int(item.get("records", item.get("expected_records", 0))),
            "curated_records": int(item.get("curated_records", 0)),
            "quarantined_records": int(item.get("quarantined_records", 0)),
            "duration_ms": int(item.get("duration_ms", 0)),
            "receipt_sha256": item.get("receipt_sha256"),
        }
        for item in response.get("Items", [])
    ]


def _public_export(item: Mapping[str, Any]) -> dict[str, Any]:
    internal_status = str(item.get("status") or "queued")
    status = {
        "queued": "building",
        "running": "building",
        "building": "building",
        "completed": "ready",
        "ready": "ready",
        "canceled": "cancelled",
        "cancelled": "cancelled",
        "failed": "cancelled",
    }.get(internal_status, "building")
    run_id = str(item.get("run_id") or "")
    export_id = item.get("export_id")
    object_uri = item.get("object_uri")
    if not object_uri and item.get("manifest_key") and run_id and export_id:
        object_uri = f"lake://scale-runs/{run_id}/exports/{export_id}"
    return {
        "export_id": str(export_id) if export_id else None,
        "status": status,
        "format": "parquet",
        "row_count": int(item.get("rows", item.get("row_count", 0))),
        "bytes": int(item.get("bytes", 0)),
        "object_uri": str(object_uri) if object_uri else None,
        "download_url": str(item["download_url"])
        if item.get("download_url")
        else None,
        "expires_at": str(item["expires_at"]) if item.get("expires_at") else None,
        "sha256": str(item["manifest_sha256"])
        if item.get("manifest_sha256")
        else None,
    }


def _exports_for_run(run_id: str) -> list[dict[str, Any]]:
    response = _table().query(
        KeyConditionExpression="pk = :pk AND begins_with(sk, :export)",
        ExpressionAttributeValues={":pk": f"RUN#{run_id}", ":export": "EXPORT#"},
        ScanIndexForward=False,
        Limit=10,
    )
    return [_public_export(item) for item in response.get("Items", [])]


def _public_plan_from_run(item: Mapping[str, Any]) -> dict[str, Any]:
    return _public_plan(
        {
            "plan_id": item["plan_id"],
            "profile_id": item["profile_id"],
            "seed": item["seed"],
            "profile": item["profile"],
            "cost": item["cost"],
            "created_at": item["created_at"],
        }
    )


def _progress_percent(
    internal_status: str,
    completed_partitions: int,
    total_partitions: int,
) -> int:
    if internal_status in {"completed", "completed_with_quarantine", "failed"}:
        return 100
    ratio = completed_partitions / total_partitions if total_partitions else 0.0
    if internal_status in {"canceling", "canceled"}:
        return min(99, max(1, round(15 + ratio * 60)))
    base = {
        "requested": 0,
        "generating": 5,
        "landing": 10,
        "partitioning": round(15 + ratio * 55),
        "validating": 72,
        "curating": 78,
        "enriching": 84,
        "aggregating": 90,
    }
    return int(base.get(internal_status, 0))


def _public_progress(
    item: Mapping[str, Any],
    plan: Mapping[str, Any],
    elapsed: int,
) -> dict[str, Any]:
    internal_status = str(item["status"])
    terminal = internal_status in TERMINAL_STATES
    profile_partitions = int(item["profile"].get("partitions", 0))
    total = int(item.get("total_partitions", 0)) or profile_partitions
    completed = int(item.get("completed_partitions", 0))
    generated = int(item.get("generated_records", 0))
    throughput = generated / elapsed if elapsed > 0 else 0.0
    percent = _progress_percent(internal_status, completed, total)
    target_seconds = int(plan["target_duration_seconds"])
    return {
        "stage": PUBLIC_STAGE.get(internal_status, "evidence"),
        "percent": percent,
        "records_generated": generated,
        "records_ingested": generated,
        "records_curated": int(item.get("curated_records", 0)),
        "records_quarantined": int(item.get("quarantined_records", 0)),
        "bytes_written": sum(
            int(item.get(key, 0))
            for key in (
                "raw_bytes",
                "curated_bytes",
                "quarantine_bytes",
                "parquet_bytes",
            )
        ),
        "partitions_completed": completed,
        "partitions_total": total,
        "current_throughput_rps": 0.0 if terminal else round(throughput, 2),
        "peak_throughput_rps": round(
            max(throughput, _as_number(item.get("peak_throughput_rps"))),
            2,
        ),
        "elapsed_seconds": elapsed,
        "eta_seconds": 0 if terminal else max(0, target_seconds - elapsed),
    }


def _quality_rule(
    rule_id: str,
    label: str,
    generated: int,
    failed: int,
) -> dict[str, Any]:
    bounded_failed = min(generated, max(0, failed))
    passed = max(0, generated - bounded_failed)
    score = round(passed * 100 / generated, 2) if generated else 0.0
    return {
        "id": rule_id,
        "label": label,
        "score": score,
        "passed_records": passed,
        "failed_records": bounded_failed,
    }


def _public_quality(item: Mapping[str, Any]) -> dict[str, Any]:
    quality = dict(item.get("quality") or {})
    generated = int(item.get("generated_records", 0))
    passed = int(quality.get("valid_records", item.get("curated_records", 0)))
    failed = int(
        quality.get("invalid_records", item.get("quarantined_records", 0))
    )
    issues = dict(quality.get("issues_by_code") or {})
    basis_points = int(quality.get("quality_score_basis_points", 0))
    overall = basis_points / 100 if basis_points else (
        round(passed * 100 / generated, 2) if generated else 0.0
    )
    return {
        "overall_score": overall,
        "passed_records": passed,
        "failed_records": failed,
        "quarantined_records": int(item.get("quarantined_records", failed)),
        "rules": [
            _quality_rule("schema", "Schema conformance", generated, failed),
            _quality_rule(
                "required",
                "Required fields",
                generated,
                int(issues.get("required", 0)),
            ),
            _quality_rule(
                "referential",
                "Referential integrity",
                generated,
                int(issues.get("range", 0)),
            ),
            _quality_rule(
                "classification",
                "Classification policy",
                generated,
                int(issues.get("classification", 0)),
            ),
        ],
    }


def _public_intelligence(item: Mapping[str, Any]) -> dict[str, Any]:
    internal_status = str(item["status"])
    receipt = dict(item.get("intelligence") or {})
    if internal_status == "canceled":
        status = "cancelled"
    elif internal_status in {"completed", "completed_with_quarantine"}:
        status = "completed"
    elif internal_status in {"enriching", "aggregating"}:
        status = "running"
    else:
        status = "pending"
    dataset_records = dict(receipt.get("dataset_records") or {})
    grants = int(dataset_records.get("grants", 0))
    topics = []
    for topic in receipt.get("topics", []):
        count = int(topic.get("record_count", topic.get("documents", 0)))
        label = str(topic.get("label") or "Unlabeled topic")
        topics.append(
            {
                "label": label,
                "record_count": count,
                "confidence": round(
                    min(0.99, count / max(grants, 1)),
                    4,
                ),
                "terms": [
                    str(term)
                    for term in (
                        topic.get("terms")
                        or [value.lower() for value in label.split()[:3]]
                    )
                ],
            }
        )
    anomalies = sum(
        int(anomaly.get("records", 1)) for anomaly in receipt.get("anomalies", [])
    )
    result_sha = receipt.get("result_sha256")
    return {
        "status": status,
        "model_run_id": f"intelligence-{str(result_sha)[:16]}" if result_sha else None,
        "grants_analyzed": grants,
        "topic_count": len(topics),
        "anomalies_detected": anomalies,
        "processing_seconds": int(item["intelligence_processing_seconds"])
        if item.get("intelligence_processing_seconds") is not None
        else None,
        "top_topics": topics,
    }


def _pending_export() -> dict[str, Any]:
    return {
        "export_id": None,
        "status": "pending",
        "format": "parquet",
        "row_count": 0,
        "bytes": 0,
        "object_uri": None,
        "download_url": None,
        "expires_at": None,
        "sha256": None,
    }


def _stage_receipt(
    item: Mapping[str, Any],
    stage_id: str,
    export_receipt: Mapping[str, Any],
) -> str | None:
    evidence = dict(item.get("evidence") or {})
    if stage_id == "plan":
        return str(item["plan_id"])
    if stage_id == "ingest" and int(item.get("completed_partitions", 0)):
        return f"partition-receipts:{int(item.get('completed_partitions', 0))}"
    if stage_id == "quality" and item.get("manifest_sha256"):
        return f"quality:{str(item['manifest_sha256'])[:24]}"
    if stage_id == "intelligence" and evidence.get("intelligence_receipt"):
        return str(evidence["intelligence_receipt"])
    if stage_id == "export" and export_receipt.get("export_id"):
        return str(export_receipt["export_id"])
    if stage_id == "evidence" and evidence.get("run_manifest"):
        return str(evidence["run_manifest"])
    return None


def _public_evidence(
    item: Mapping[str, Any],
    queue: Mapping[str, int],
    export_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    internal_status = str(item["status"])
    current_stage = PUBLIC_STAGE.get(internal_status, "evidence")
    stage_ids = [stage[0] for stage in PUBLIC_PLAN_STAGES]
    current_index = stage_ids.index(current_stage)
    completed_run = internal_status in {"completed", "completed_with_quarantine"}
    cancelled_run = internal_status == "canceled"
    failed_run = internal_status == "failed"
    stages = []
    for index, (stage_id, label, _detail, _resource) in enumerate(PUBLIC_PLAN_STAGES):
        if completed_run:
            if stage_id == "export":
                stage_status = {
                    "ready": "completed",
                    "building": "running",
                    "cancelled": "cancelled",
                }.get(str(export_receipt["status"]), "pending")
            else:
                stage_status = "completed"
        elif cancelled_run:
            stage_status = "completed" if index < current_index else "cancelled"
        elif failed_run:
            stage_status = "completed" if index < current_index else (
                "failed" if index == current_index else "pending"
            )
        elif index < current_index:
            stage_status = "completed"
        elif index == current_index:
            stage_status = "running"
        else:
            stage_status = "pending"
        stages.append(
            {
                "id": stage_id,
                "label": label,
                "status": stage_status,
                "receipt": _stage_receipt(item, stage_id, export_receipt)
                if stage_status == "completed"
                else None,
                "recorded_at": str(item.get("updated_at") or item["created_at"])
                if stage_status == "completed"
                else None,
            }
        )
    evidence = dict(item.get("evidence") or {})
    return {
        "correlation_id": str(
            item.get("correlation_id") or f"run:{item['run_id']}"
        ),
        "audit_receipt": str(
            evidence.get("audit_receipt")
            or evidence.get("failure_receipt")
            or item.get("idempotency_receipt")
            or "pending"
        ),
        "manifest_uri": str(evidence.get("run_manifest") or "pending"),
        "manifest_sha256": str(item.get("manifest_sha256") or ""),
        "metrics_recorded_at": str(item.get("updated_at") or item["created_at"]),
        "recovery_queue_depth": int(queue.get("dlq_count", 0)),
        "duplicate_records_suppressed": int(item.get("duplicate_replays", 0)),
        "stages": stages,
    }


def _public_error(item: Mapping[str, Any]) -> dict[str, Any] | None:
    error = item.get("error")
    if not error:
        return None
    if not isinstance(error, Mapping):
        return {
            "code": "scale_run_failed",
            "message": str(error),
            "retryable": False,
        }
    return {
        "code": str(error.get("code") or "scale_run_failed"),
        "message": str(error.get("message") or "Scale Run failed"),
        "retryable": bool(error.get("retryable", False)),
    }


def _run_snapshot(item: Mapping[str, Any], *, include_partitions: bool = True) -> dict[str, Any]:
    del include_partitions
    elapsed = _elapsed_seconds(item)
    queue = _queue_evidence() if item.get("status") in ACTIVE_STATES else {
        "queue_depth": 0,
        "running_messages": 0,
        "dlq_count": int(item.get("dlq_count", 0)),
    }
    plan = _public_plan_from_run(item)
    exports = _exports_for_run(str(item["run_id"]))
    export_receipt = exports[0] if exports else _pending_export()
    progress = _public_progress(item, plan, elapsed)
    costs = _public_cost(item["cost"])
    metered = item["cost"].get("metered") if isinstance(item["cost"], Mapping) else None
    if isinstance(metered, Mapping):
        accrued = _as_number(metered.get("estimated_cost_usd"))
    else:
        accrued = costs["estimated_run_usd"] * progress["percent"] / 100
    costs["accrued_usd"] = round(accrued, 8)
    internal_status = str(item["status"])
    return {
        "run_id": str(item["run_id"]),
        "mode": "live",
        "status": PUBLIC_STATUS.get(internal_status, "failed"),
        "created_at": str(item["created_at"]),
        "started_at": str(item["execution_started_at"])
        if item.get("execution_started_at")
        else None,
        "updated_at": str(item.get("updated_at") or item["created_at"]),
        "completed_at": str(item["completed_at"])
        if item.get("completed_at")
        else None,
        "cancelled_at": str(item["completed_at"])
        if internal_status == "canceled" and item.get("completed_at")
        else None,
        "plan": plan,
        "progress": progress,
        "quality": _public_quality(item),
        "costs": costs,
        "intelligence": _public_intelligence(item),
        "export_receipt": export_receipt,
        "evidence": _public_evidence(item, queue, export_receipt),
        "error": _public_error(item),
    }


def _elapsed_seconds(item: Mapping[str, Any]) -> int:
    start = datetime.fromisoformat(str(item["created_at"]))
    finish_raw = item.get("completed_at")
    finish = datetime.fromisoformat(str(finish_raw)) if finish_raw else _now()
    return max(0, int((finish - start).total_seconds()))


def _get_run_snapshot(run_id: str) -> dict[str, Any]:
    return _run_snapshot(_get_run_item(run_id))


def _list_runs() -> dict[str, Any]:
    response = _table().query(
        IndexName="gsi1",
        KeyConditionExpression="gsi1pk = :pk",
        ExpressionAttributeValues={":pk": "RUNS"},
        ScanIndexForward=False,
        Limit=12,
    )
    return {
        "generated_at": _iso(),
        "runs": [_run_snapshot(item, include_partitions=False) for item in response.get("Items", [])],
    }


def _cancel_run(run_id: str, claims: http.Claims) -> dict[str, Any]:
    item = _get_run_item(run_id)
    if item["status"] in TERMINAL_STATES:
        return _run_snapshot(item)
    try:
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression=(
                "SET #status = :status, cancel_requested_at = :at, "
                "cancel_requested_by = :actor, updated_at = :at"
            ),
            ConditionExpression=(
                "#status <> :completed AND #status <> :completed_quarantine "
                "AND #status <> :failed AND #status <> :canceled"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "canceling",
                ":at": _iso(),
                ":actor": _actor(claims),
                ":completed": "completed",
                ":completed_quarantine": "completed_with_quarantine",
                ":failed": "failed",
                ":canceled": "canceled",
            },
        )
    except Exception as exc:
        if not _is_conditional_check_failure(exc):
            raise
        return _get_run_snapshot(run_id)
    return _get_run_snapshot(run_id)


def _create_export(run_id: str, body: Mapping[str, Any], claims: http.Claims) -> dict[str, Any]:
    run = _get_run_item(run_id)
    if run["status"] not in {"completed", "completed_with_quarantine"}:
        raise ValueError("Export Job requires a completed Scale Run")
    dataset = str(body.get("dataset") or "").strip().lower()
    if dataset != "curated_portfolio":
        raise ValueError("dataset must be curated_portfolio")
    output_format = str(body.get("format") or "").strip().lower()
    if output_format != "parquet":
        raise ValueError("format must be parquet")
    idem = str(body.get("idempotency_key") or "").strip()
    if len(idem) < 12 or len(idem) > 128:
        raise ValueError("idempotency_key must be between 12 and 128 characters")
    digest = hashlib.sha256(f"{run_id}|{dataset}|{output_format}|{idem}".encode()).hexdigest()
    deterministic_export_id = f"export-{digest[:20]}"
    existing = _table().get_item(
        Key={"pk": f"RUN#{run_id}", "sk": f"EXPORT#{deterministic_export_id}"},
        ConsistentRead=True,
    ).get("Item")
    if existing:
        return _public_export(existing)
    created = _now()
    expires = created + timedelta(hours=DEFAULT_EXPORT_RETENTION_HOURS)
    item = {
        "pk": f"RUN#{run_id}",
        "sk": f"EXPORT#{deterministic_export_id}",
        "entity": "export",
        "export_id": deterministic_export_id,
        "run_id": run_id,
        "dataset": dataset,
        "format": output_format,
        "status": "queued",
        "created_at": _iso(created),
        "expires_at": _iso(expires),
        "expires_at_epoch": _epoch(expires),
        "requested_by": _actor(claims),
        "synthetic_only": True,
        "rows": int(run.get("curated_records", 0)),
        "bytes": int(run.get("parquet_bytes", 0)),
    }
    _table().put_item(Item=item, ConditionExpression="attribute_not_exists(sk)")
    _sqs().send_message(
        QueueUrl=os.environ["SCALE_EXPORT_QUEUE_URL"],
        MessageBody=json.dumps({"run_id": run_id, "export_id": deterministic_export_id}),
    )
    return _public_export(item)


def _get_export(run_id: str, export_id: str) -> dict[str, Any]:
    item = _table().get_item(
        Key={"pk": f"RUN#{run_id}", "sk": f"EXPORT#{export_id}"},
        ConsistentRead=True,
    ).get("Item")
    if not item:
        raise KeyError(export_id)
    if item.get("status") in {"completed", "ready"} and item.get("manifest_key"):
        expires_at = datetime.fromisoformat(str(item["expires_at"]))
        if expires_at > _now():
            item["download_url"] = _s3().generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": os.environ["SCALE_LAKE_BUCKET"],
                    "Key": item["manifest_key"],
                },
                ExpiresIn=min(3600, max(60, int((expires_at - _now()).total_seconds()))),
            )
    return _public_export(item)


def _dispatch(run_id: str) -> dict[str, Any]:
    run = _get_run_item(run_id)
    if run["status"] in TERMINAL_STATES or run["status"] == "canceling":
        return {"run_id": run_id, "status": run["status"], "dispatched": False}
    profile = get_profile(str(run["profile_id"]))
    messages: list[dict[str, Any]] = []
    partition_items: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for spec in iter_partition_specs(profile, dataset):
            message = {
                "run_id": run_id,
                "profile_id": profile.name,
                "seed": int(run["seed"]),
                "dataset": dataset,
                "partition_id": spec.partition_id,
                "partition_ordinal": spec.ordinal,
                "start": spec.start,
                "stop": spec.stop,
                "defect_rate_basis_points": DEFECT_RATE_BASIS_POINTS,
            }
            messages.append(message)
            partition_items.append(
                {
                    "pk": f"RUN#{run_id}",
                    "sk": f"PART#{dataset}#{spec.partition_id}",
                    "entity": "partition",
                    "run_id": run_id,
                    "dataset": dataset,
                    "partition_id": spec.partition_id,
                    "partition_ordinal": spec.ordinal,
                    "start": spec.start,
                    "stop": spec.stop,
                    "expected_records": spec.record_count,
                    "status": "queued",
                    "dispatch_state": "queued",
                    "expires_at_epoch": int(run["expires_at_epoch"]),
                }
            )

    # Capture the pre-run DLQ depth before workers can redrive a message. This
    # lets progress checks distinguish poison work from retained evidence left
    # by an older run without consuming or mutating the DLQ.
    baseline_dlq_count = int(_queue_evidence().get("dlq_count", 0))
    initialized_at = _iso()
    try:
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression=(
                "SET total_partitions = :total, "
                "dlq_baseline_count = if_not_exists(dlq_baseline_count, :dlq), "
                "updated_at = :at"
            ),
            ConditionExpression="#status = :requested OR #status = :partitioning",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":total": len(messages),
                ":dlq": baseline_dlq_count,
                ":at": initialized_at,
                ":requested": "requested",
                ":partitioning": "partitioning",
            },
        )
    except Exception as exc:
        if not _is_conditional_check_failure(exc):
            raise
        current = _get_run_item(run_id)
        return {
            "run_id": run_id,
            "status": current["status"],
            "dispatched": False,
        }

    pending: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item, message in zip(partition_items, messages, strict=True):
        try:
            _table().put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(pk)",
            )
            current = item
        except Exception as exc:
            if not _is_conditional_check_failure(exc):
                raise
            current = _table().get_item(
                Key={"pk": item["pk"], "sk": item["sk"]},
                ConsistentRead=True,
            ).get("Item")
            if not current:
                raise RuntimeError("partition ledger disappeared during dispatch") from exc
            immutable_fields = (
                "run_id",
                "dataset",
                "partition_id",
                "partition_ordinal",
                "start",
                "stop",
                "expected_records",
            )
            if any(current.get(key) != item[key] for key in immutable_fields):
                raise RuntimeError("partition ledger conflicts with deterministic plan") from exc

        # Acknowledged, running, and completed rows prove that work was already
        # accepted. Retried workflow invocations must never reset or resend it.
        if current.get("dispatch_acknowledged_at"):
            continue
        if current.get("status") != "queued":
            continue
        dispatch_state = str(current.get("dispatch_state") or "queued")
        if dispatch_state == "dispatching":
            raise RuntimeError("partition dispatch outcome is uncertain")
        if dispatch_state != "queued":
            raise RuntimeError("partition dispatch ledger state is invalid")
        pending.append((message, item))

    queue_url = os.environ["SCALE_QUEUE_URL"]
    sent = 0
    for offset in range(0, len(pending), 10):
        batch_items = pending[offset : offset + 10]
        attempted_at = _iso()
        for _message, item in batch_items:
            _table().update_item(
                Key={"pk": item["pk"], "sk": item["sk"]},
                UpdateExpression=(
                    "SET dispatch_state = :dispatching, "
                    "dispatch_attempted_at = if_not_exists(dispatch_attempted_at, :at)"
                ),
                ConditionExpression=(
                    "#status = :queued AND "
                    "(attribute_not_exists(dispatch_state) OR dispatch_state = :queued)"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":dispatching": "dispatching",
                    ":queued": "queued",
                    ":at": attempted_at,
                },
            )
        entries = [
            {
                "Id": f"p{offset + index}",
                "MessageBody": json.dumps(message, separators=(",", ":")),
            }
            for index, (message, _item) in enumerate(batch_items)
        ]
        response = _sqs().send_message_batch(QueueUrl=queue_url, Entries=entries)
        successful = {
            str(result["Id"]): result
            for result in response.get("Successful", [])
            if result.get("Id") is not None
        }
        acknowledged_at = _iso()
        for entry, (_message, item) in zip(entries, batch_items, strict=True):
            result = successful.get(entry["Id"])
            if not result:
                continue
            _table().update_item(
                Key={"pk": item["pk"], "sk": item["sk"]},
                UpdateExpression=(
                    "SET dispatch_acknowledged_at = "
                    "if_not_exists(dispatch_acknowledged_at, :at), "
                    "dispatch_message_id = "
                    "if_not_exists(dispatch_message_id, :message_id), "
                    "dispatch_state = :acknowledged"
                ),
                ConditionExpression="attribute_exists(pk)",
                ExpressionAttributeValues={
                    ":at": acknowledged_at,
                    ":message_id": str(result.get("MessageId") or entry["Id"]),
                    ":acknowledged": "acknowledged",
                },
            )
            sent += 1
        failed = {
            str(result["Id"]): result
            for result in response.get("Failed", [])
            if result.get("Id") is not None
        }
        for entry, (_message, item) in zip(entries, batch_items, strict=True):
            result = failed.get(entry["Id"])
            if not result:
                continue
            _table().update_item(
                Key={"pk": item["pk"], "sk": item["sk"]},
                UpdateExpression=(
                    "SET dispatch_state = :queued, "
                    "last_dispatch_failure_code = :failure_code"
                ),
                ConditionExpression="dispatch_state = :dispatching",
                ExpressionAttributeValues={
                    ":queued": "queued",
                    ":dispatching": "dispatching",
                    ":failure_code": str(result.get("Code") or "unknown"),
                },
            )
        if response.get("Failed") or len(successful) != len(entries):
            raise RuntimeError("partition dispatch failed")
    at = _iso()
    try:
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression=(
                "SET #status = :next_status, total_partitions = :total, "
                "dispatched_at = if_not_exists(dispatched_at, :at), updated_at = :at"
            ),
            ConditionExpression="#status = :requested OR #status = :partitioning",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":next_status": "partitioning",
                ":requested": "requested",
                ":partitioning": "partitioning",
                ":total": len(messages),
                ":at": at,
            },
        )
    except Exception as exc:
        if not _is_conditional_check_failure(exc):
            raise
        current = _get_run_item(run_id)
        return {
            "run_id": run_id,
            "status": current["status"],
            "dispatched": False,
            "partitions": len(messages),
        }
    _emit_metrics(profile.name, "dispatch", "success", {"Partitions": len(messages)})
    return {
        "run_id": run_id,
        "status": "partitioning",
        "dispatched": sent > 0,
        "partitions": len(messages),
    }


def _check(run_id: str) -> dict[str, Any]:
    run = _get_run_item(run_id)
    status = str(run["status"])
    if status == "canceling":
        _complete_cancel(run_id)
        return {"run_id": run_id, "status": "canceled", "terminal": True}
    if status in TERMINAL_STATES:
        return {"run_id": run_id, "status": status, "terminal": True}
    if _now() >= datetime.fromisoformat(str(run["deadline_at"])):
        _fail_run(run_id, "run_deadline_exceeded")
        return {"run_id": run_id, "status": "failed", "terminal": True}
    failed = int(run.get("failed_partitions", 0))
    queue = _queue_evidence()
    dlq_count = int(queue.get("dlq_count", 0))
    dlq_baseline = int(run.get("dlq_baseline_count", 0))
    if failed > 0 or dlq_count > dlq_baseline:
        failure_code = (
            "partition_processing_exhausted"
            if failed > 0
            else "partition_dlq_detected"
        )
        _fail_run(run_id, failure_code)
        return {"run_id": run_id, "status": "failed", "terminal": True}
    total = int(run.get("total_partitions", 0))
    complete = int(run.get("completed_partitions", 0))
    if total > 0 and complete >= total:
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression="SET #status = :status, updated_at = :at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "aggregating", ":at": _iso()},
        )
        return {"run_id": run_id, "status": "aggregating", "ready_for_athena": True}
    return {
        "run_id": run_id,
        "status": status,
        "completed_partitions": complete,
        "total_partitions": total,
        "ready_for_athena": False,
    }


def _start_athena(run_id: str) -> dict[str, Any]:
    run = _get_run_item(run_id)
    status = str(run["status"])
    if status == "canceling":
        _complete_cancel(run_id)
        return {"run_id": run_id, "status": "canceled", "terminal": True}
    if status in TERMINAL_STATES:
        return {"run_id": run_id, "status": status, "terminal": True}
    if run.get("athena_queries"):
        return {"run_id": run_id, "status": "aggregating", "queries_started": True}
    database = os.environ["SCALE_GLUE_DATABASE"]
    workgroup = os.environ["SCALE_ATHENA_WORKGROUP"]
    bucket = os.environ["SCALE_LAKE_BUCKET"]
    queries: dict[str, str] = {}
    safe_run = str(run_id).replace("'", "''")
    for dataset in DATASETS:
        prefix = f"s3://{bucket}/parquet/{dataset}/run_id={run_id}/"
        query = (
            f'UNLOAD (SELECT * FROM "{database}"."scale_{dataset}" '
            f"WHERE run_id = '{safe_run}') TO '{prefix}' "
            "WITH (format='PARQUET', compression='SNAPPY')"
        )
        response = _athena().start_query_execution(
            QueryString=query,
            WorkGroup=workgroup,
            ClientRequestToken=hashlib.sha256(f"{run_id}|{dataset}|parquet-v1".encode()).hexdigest()[:64],
        )
        queries[dataset] = response["QueryExecutionId"]
    try:
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression=(
                "SET athena_queries = :queries, athena_started_at = :at, "
                "updated_at = :at"
            ),
            ConditionExpression="#status = :aggregating",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":queries": queries,
                ":at": _iso(),
                ":aggregating": "aggregating",
            },
        )
    except Exception as exc:
        if not _is_conditional_check_failure(exc):
            raise
        for query_id in queries.values():
            try:
                _athena().stop_query_execution(QueryExecutionId=query_id)
            except Exception:  # noqa: BLE001 - cancellation must still terminate
                logger.warning("Athena query could not be stopped for %s", run_id)
        current = _get_run_item(run_id)
        if current["status"] == "canceling":
            _complete_cancel(run_id)
            return {"run_id": run_id, "status": "canceled", "terminal": True}
        if current["status"] in TERMINAL_STATES:
            return {
                "run_id": run_id,
                "status": current["status"],
                "terminal": True,
            }
        raise RuntimeError("Scale Run left aggregation before Athena started") from exc
    return {"run_id": run_id, "status": "aggregating", "queries_started": True}


def _check_athena(run_id: str) -> dict[str, Any]:
    run = _get_run_item(run_id)
    queries = dict(run.get("athena_queries") or {})
    status = str(run["status"])
    if status == "canceling":
        for query_id in queries.values():
            try:
                _athena().stop_query_execution(QueryExecutionId=query_id)
            except Exception:  # noqa: BLE001 - cancellation must still terminate
                logger.warning("Athena query could not be stopped for %s", run_id)
        _complete_cancel(run_id)
        return {"run_id": run_id, "status": "canceled", "terminal": True}
    if status in TERMINAL_STATES:
        return {"run_id": run_id, "status": status, "terminal": True}
    if not queries:
        raise ValueError("Athena conversion has not started")
    states: dict[str, str] = {}
    total_scanned = 0
    for dataset, query_id in queries.items():
        execution = _athena().get_query_execution(QueryExecutionId=query_id)["QueryExecution"]
        state = execution["Status"]["State"]
        states[dataset] = state
        total_scanned += int(execution.get("Statistics", {}).get("DataScannedInBytes", 0))
        if state in {"FAILED", "CANCELLED"}:
            _fail_run(run_id, f"athena_{dataset}_{state.lower()}")
            return {"run_id": run_id, "status": "failed", "terminal": True}
    done = all(state == "SUCCEEDED" for state in states.values())
    if done:
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression="SET athena_scanned_bytes = :bytes, athena_completed_at = :at, updated_at = :at",
            ExpressionAttributeValues={":bytes": total_scanned, ":at": _iso()},
        )
    return {"run_id": run_id, "status": "aggregating", "athena_complete": done}


def _finalize(run_id: str) -> dict[str, Any]:
    run = _get_run_item(run_id)
    status_before_finalize = str(run["status"])
    if status_before_finalize == "canceling":
        _complete_cancel(run_id)
        return {"run_id": run_id, "status": "canceled", "terminal": True}
    if status_before_finalize in TERMINAL_STATES:
        return {
            "run_id": run_id,
            "status": status_before_finalize,
            "terminal": True,
        }
    parts = _all_partition_items(run_id)
    if len(parts) != int(run["total_partitions"]):
        raise RuntimeError("partition ledger is incomplete")
    if any(item.get("status") != "completed" for item in parts):
        raise RuntimeError("a partition is not terminal-complete")
    receipts = [_read_receipt(str(item["receipt_key"])) for item in parts]
    quality = _merge_quality(receipts)
    intelligence = _merge_intelligence(receipts)
    parquet_objects = _list_objects("parquet/", run_id=run_id)
    parquet_bytes = sum(int(item.get("Size", 0)) for item in parquet_objects)
    file_set = [
        {
            "logical_locator": _logical_object_locator(str(item["Key"]), run_id),
            "bytes": int(item.get("Size", 0)),
            "etag": str(item.get("ETag", "")).strip('"'),
        }
        for item in parquet_objects
    ]
    manifest = {
        "contract_version": "compass.scale-run-manifest.v1",
        "run_id": run_id,
        "profile_id": run["profile_id"],
        "seed": int(run["seed"]),
        "generator_contract": run["synthetic_contract"],
        "synthetic_only": True,
        "partition_receipts": [
            {
                "dataset": item["dataset"],
                "partition_id": item["partition_id"],
                "receipt_sha256": item["receipt_sha256"],
                "records": int(item["records"]),
            }
            for item in sorted(parts, key=lambda value: value["sk"])
        ],
        "quality": quality,
        "intelligence": intelligence,
        "parquet_files": file_set,
        "athena_scanned_bytes": int(run.get("athena_scanned_bytes", 0)),
    }
    encoded = canonical_json_bytes(manifest)
    manifest_sha = sha256_hex(encoded)
    manifest_key = f"evidence/run_id={run_id}/run-manifest.json"
    intelligence_key = f"evidence/run_id={run_id}/intelligence-receipt.json"
    _s3().put_object(
        Bucket=os.environ["SCALE_LAKE_BUCKET"],
        Key=manifest_key,
        Body=encoded,
        ContentType="application/json",
        Metadata={"sha256": manifest_sha, "synthetic-only": "true"},
    )
    intelligence_encoded = canonical_json_bytes(intelligence)
    intelligence_sha = sha256_hex(intelligence_encoded)
    _s3().put_object(
        Bucket=os.environ["SCALE_LAKE_BUCKET"],
        Key=intelligence_key,
        Body=intelligence_encoded,
        ContentType="application/json",
        Metadata={"sha256": intelligence_sha, "synthetic-only": "true"},
    )
    generated = int(run.get("generated_records", 0))
    curated = int(run.get("curated_records", 0))
    quarantined = int(run.get("quarantined_records", 0))
    if generated != curated + quarantined:
        _fail_run(run_id, "terminal_record_invariant_failed")
        raise RuntimeError("terminal record invariant failed")
    status = "completed_with_quarantine" if quarantined else "completed"
    completed_at = _iso()
    metered_cost = _metered_cost(run, parquet_bytes)
    try:
        _table().update_item(
            Key={"pk": f"RUN#{run_id}", "sk": "META"},
            UpdateExpression=(
                "SET #status = :status, completed_at = :at, updated_at = :at, "
                "parquet_bytes = :parquet, quality = :quality, intelligence = :intel, "
                "manifest_sha256 = :sha, manifest_key = :manifest, "
                "intelligence_key = :ikey, cost.metered = :metered, "
                "evidence = :evidence"
            ),
            ConditionExpression="#status = :aggregating",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":aggregating": "aggregating",
                ":at": completed_at,
                ":parquet": parquet_bytes,
                ":quality": quality,
                ":intel": intelligence,
                ":sha": manifest_sha,
                ":manifest": manifest_key,
                ":ikey": intelligence_key,
                ":metered": metered_cost,
                ":evidence": {
                    "run_manifest": f"lake://scale-runs/{run_id}/manifest",
                    "intelligence_receipt": f"lake://scale-runs/{run_id}/intelligence",
                    "partition_receipts": len(parts),
                    "parquet_objects": len(file_set),
                },
            },
        )
    except Exception as exc:
        if not _is_conditional_check_failure(exc):
            raise
        current = _get_run_item(run_id)
        if current["status"] == "canceling":
            _complete_cancel(run_id)
            return {"run_id": run_id, "status": "canceled", "terminal": True}
        if current["status"] in TERMINAL_STATES:
            return {
                "run_id": run_id,
                "status": current["status"],
                "terminal": True,
            }
        raise RuntimeError("Scale Run left aggregation during finalization") from exc
    _release_lock(run_id)
    if run["profile_id"] == "100k":
        _table().put_item(
            Item={
                "pk": "PROOF#100k",
                "sk": "META",
                "entity": "capacity_proof",
                "run_id": run_id,
                "manifest_sha256": manifest_sha,
                "completed_at": completed_at,
                "expires_at_epoch": _epoch(_now() + timedelta(days=RUN_RETENTION_DAYS)),
            }
        )
    _emit_metrics(str(run["profile_id"]), "finalize", "success", {"Records": generated})
    return {"run_id": run_id, "status": status, "terminal": True, "manifest_sha256": manifest_sha}


def _metered_cost(run: Mapping[str, Any], parquet_bytes: int) -> dict[str, Any]:
    profile = get_profile(str(run["profile_id"]))
    modeled = modeled_quantities(
        profile.total_records,
        profile.default_partition_size,
        partition_count=_partition_count(profile),
    )
    observed = modeled.__class__(
        records=int(run.get("generated_records", 0)),
        partitions=int(run.get("completed_partitions", 0)),
        retained_gb_month=(
            Decimal(int(run.get("raw_bytes", 0)) + int(run.get("curated_bytes", 0)) + parquet_bytes)
            / Decimal(1024**3)
            * Decimal(7)
            / Decimal(30)
        ),
        lambda_arm_requests=int(run.get("completed_partitions", 0)) + 12,
        lambda_arm_gb_seconds=(
            Decimal(int(run.get("worker_duration_ms", 0)))
            / Decimal(1000)
            * Decimal(2)
            + CONTROL_EXPORT_GB_SECONDS
        ),
        s3_put_requests=int(run.get("completed_partitions", 0)) * 4 + len(DATASETS) + 2,
        s3_get_requests=int(run.get("completed_partitions", 0)) + 24,
        sqs_requests=int(run.get("completed_partitions", 0)) * 4 + 4,
        step_functions_transitions=48,
        dynamodb_write_units=int(run.get("completed_partitions", 0)) * 8 + 20,
        dynamodb_read_units=int(run.get("completed_partitions", 0)) * 6 + 40,
        dynamodb_storage_gb_month=modeled.dynamodb_storage_gb_month,
        athena_tb_scanned=Decimal(int(run.get("athena_scanned_bytes", 0))) / Decimal(1024**4),
        cloudwatch_log_gb=modeled.cloudwatch_log_gb,
        kms_requests=modeled.kms_requests,
        http_api_requests=modeled.http_api_requests,
    )
    receipt = estimate_incremental(
        str(run["profile_id"]),
        observed,
        catalog=PriceCatalog.load(),
        deployed_hard_cap_usd=_max_cost(),
    )
    receipt["kind"] = "metered_usage_estimate"
    receipt["status"] = "metered_estimate"
    receipt["billed_reconciliation"] = "pending"
    return receipt


def _all_partition_items(run_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :part)",
        "ExpressionAttributeValues": {":pk": f"RUN#{run_id}", ":part": "PART#"},
    }
    while True:
        response = _table().query(**kwargs)
        items.extend(response.get("Items", []))
        key = response.get("LastEvaluatedKey")
        if not key:
            break
        kwargs["ExclusiveStartKey"] = key
    return items


def _read_receipt(key: str) -> dict[str, Any]:
    response = _s3().get_object(Bucket=os.environ["SCALE_LAKE_BUCKET"], Key=key)
    return json.loads(response["Body"].read())


def _merge_quality(receipts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    totals = {
        "generated_records": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "injected_defects": 0,
        "detected_injected_defects": 0,
        "unexpected_invalid_records": 0,
    }
    issue_counts: dict[str, int] = {}
    dataset_counts: dict[str, dict[str, int]] = {}
    for receipt in receipts:
        quality = receipt["quality"]
        dataset = str(receipt["dataset"])
        bucket = dataset_counts.setdefault(dataset, {key: 0 for key in totals})
        for key in totals:
            value = int(quality.get(key, 0))
            totals[key] += value
            bucket[key] += value
        for code, value in quality.get("issues_by_code", {}).items():
            issue_counts[code] = issue_counts.get(code, 0) + int(value)
    generated = totals["generated_records"]
    totals["quality_score_basis_points"] = (
        totals["valid_records"] * 10_000 // generated if generated else 10_000
    )
    totals["issues_by_code"] = dict(sorted(issue_counts.items()))
    totals["datasets"] = dataset_counts
    totals["invariant_passed"] = generated == totals["valid_records"] + totals["invalid_records"]
    return totals


def _merge_intelligence(receipts: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    dimensions: dict[str, dict[str, int]] = {}
    numeric_sums: dict[str, int] = {}
    dataset_records: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    for receipt in receipts:
        dataset = str(receipt["dataset"])
        aggregate = receipt["aggregate"]
        dataset_records[dataset] = dataset_records.get(dataset, 0) + int(aggregate["record_count"])
        for field, value in aggregate.get("numeric_sums", {}).items():
            key = f"{dataset}.{field}"
            numeric_sums[key] = numeric_sums.get(key, 0) + int(value)
        for field, counts in aggregate.get("dimensions", {}).items():
            key = f"{dataset}.{field}"
            merged = dimensions.setdefault(key, {})
            for value, count in counts.items():
                merged[value] = merged.get(value, 0) + int(count)
    for key, counts in sorted(dimensions.items()):
        if counts:
            value, count = max(counts.items(), key=lambda item: (item[1], item[0]))
            findings.append({"kind": "dominant_dimension", "field": key, "value": value, "records": count})
    topics = [
        {
            "label": label,
            "documents": count,
            "scope": "full_corpus_deterministic",
        }
        for label, count in sorted(
            dimensions.get("grants.program_area", {}).items(),
            key=lambda item: (-item[1], item[0]),
        )[:6]
    ]
    anomalies = []
    at_risk = dimensions.get("milestones.status", {}).get("at_risk", 0)
    expired = dimensions.get("licenses.status", {}).get("expired", 0)
    if at_risk:
        anomalies.append({"kind": "at_risk_milestones", "records": at_risk, "severity": "high"})
    if expired:
        anomalies.append({"kind": "expired_licenses", "records": expired, "severity": "medium"})
    payload = {
        "contract_version": "compass.intelligence-receipt.v1",
        "scope": "full_corpus",
        "coverage_records": sum(dataset_records.values()),
        "dataset_records": dataset_records,
        "numeric_sums": numeric_sums,
        "dimensions": dimensions,
        "topics": topics,
        "anomalies": anomalies,
        "top_findings": findings[:10],
        "embedding": {
            "status": "not_requested",
            "eligible_documents": dataset_records.get("documents", 0),
            "embedded_documents": 0,
            "coverage_pct": 0,
            "disclosure": "Full-corpus deterministic intelligence does not imply semantic embedding coverage.",
        },
    }
    payload["result_sha256"] = sha256_hex(canonical_json_bytes(payload))
    return payload


def _list_objects(prefix: str, *, run_id: str) -> list[dict[str, Any]]:
    bucket = os.environ["SCALE_LAKE_BUCKET"]
    objects: list[dict[str, Any]] = []
    for dataset in DATASETS:
        dataset_prefix = f"{prefix}{dataset}/run_id={run_id}/"
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": dataset_prefix}
            if token:
                kwargs["ContinuationToken"] = token
            response = _s3().list_objects_v2(**kwargs)
            objects.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
    return objects


def _logical_object_locator(key: str, run_id: str) -> str:
    marker = f"run_id={run_id}/"
    suffix = key.split(marker, 1)[-1]
    dataset = key.split("/", 2)[1] if "/" in key else "unknown"
    return f"lake://scale-runs/{run_id}/parquet/{dataset}/{suffix}"


def _release_lock(run_id: str) -> None:
    try:
        _table().delete_item(
            Key={"pk": "LOCK#ACTIVE", "sk": "META"},
            ConditionExpression="run_id = :run",
            ExpressionAttributeValues={":run": run_id},
        )
    except Exception:  # noqa: BLE001 - cleanup is idempotent and best effort
        logger.warning("active lock was already released for %s", run_id)


def _complete_cancel(run_id: str) -> None:
    at = _iso()
    _table().update_item(
        Key={"pk": f"RUN#{run_id}", "sk": "META"},
        UpdateExpression="SET #status = :status, completed_at = :at, updated_at = :at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "canceled", ":at": at},
    )
    _release_lock(run_id)


def _fail_run(run_id: str, code: str) -> None:
    at = _iso()
    _table().update_item(
        Key={"pk": f"RUN#{run_id}", "sk": "META"},
        UpdateExpression=(
            "SET #status = :status, completed_at = :at, updated_at = :at, "
            "error = :error, evidence = :evidence"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "failed",
            ":at": at,
            ":error": {
                "code": code,
                "message": "Scale Run stopped at a guarded terminal failure",
                "retryable": False,
            },
            ":evidence": {
                "failure_receipt": f"run://scale-runs/{run_id}/failure/{code}",
                "failure_code": code,
                "failed_at": at,
            },
        },
    )
    _release_lock(run_id)


def _fail_orchestration(run_id: str) -> dict[str, Any]:
    _fail_run(run_id, "orchestration_failure")
    return {"run_id": run_id, "status": "failed", "terminal": True}


def _emit_metrics(profile: str, stage: str, outcome: str, metrics: Mapping[str, int | float]) -> None:
    timestamp = int(time.time() * 1000)
    definitions = [{"Name": name, "Unit": "Count"} for name in metrics]
    payload: dict[str, Any] = {
        "_aws": {
            "Timestamp": timestamp,
            "CloudWatchMetrics": [
                {
                    "Namespace": "Compass/Scale",
                    "Dimensions": [["Profile", "Stage", "Outcome"]],
                    "Metrics": definitions,
                }
            ],
        },
        "Profile": profile,
        "Stage": stage,
        "Outcome": outcome,
    }
    payload.update(metrics)
    print(json.dumps(payload, sort_keys=True))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _orchestration_action(event: Mapping[str, Any]) -> dict[str, Any] | None:
    action = event.get("action")
    run_id = str(event.get("run_id") or "")
    if not action:
        return None
    if not run_id:
        raise ValueError("run_id is required")
    actions = {
        "dispatch": _dispatch,
        "check": _check,
        "start_athena": _start_athena,
        "check_athena": _check_athena,
        "finalize": _finalize,
        "fail": _fail_orchestration,
    }
    try:
        function = actions[str(action)]
    except KeyError as exc:
        raise ValueError("unknown orchestration action") from exc
    return function(run_id)


def handler(event, context):
    request = event or {}
    if request.get("action"):
        return _orchestration_action(request)
    try:
        claims, denied = _authorized(request)
        if denied:
            return denied
        assert claims is not None
        method = http.get_method(request) or ""
        path = http.get_path(request) or ""
        run_id = http.path_param(request, "run_id")
        export_id = http.path_param(request, "export_id")

        if method == "GET" and path == "/scale/profiles":
            return http.ok(_profiles_response())
        if method == "POST" and path == "/scale/plans":
            return http.created(_create_plan(http.parse_body(request), claims))
        if method == "GET" and path == "/scale/runs":
            return http.ok(_list_runs())
        if method == "POST" and path == "/scale/runs":
            return http.created(_create_run(http.parse_body(request), claims))
        if method == "GET" and run_id and not export_id and path.endswith(run_id):
            return http.ok(_get_run_snapshot(run_id))
        if method == "POST" and run_id and path.endswith("/cancel"):
            return http.ok(_cancel_run(run_id, claims))
        if method == "POST" and run_id and path.endswith("/exports"):
            return http.created(_create_export(run_id, http.parse_body(request), claims))
        if method == "GET" and run_id and export_id:
            return http.ok(_get_export(run_id, export_id))
        return http.not_found("unknown Scale Lab route")
    except PermissionError as exc:
        return http.forbidden(str(exc))
    except KeyError:
        return http.not_found("Scale Run or Export Job was not found")
    except (TypeError, ValueError) as exc:
        return http.bad_request(str(exc))
    except Exception:
        logger.exception("Scale Run handler failed")
        return http.server_error()

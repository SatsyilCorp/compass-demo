"""Protected operational evidence, lineage, and notification API.

The endpoint reads the compact DynamoDB projection written after authoritative
domain receipts commit. It exposes logical evidence locators and hashes only.
Physical AWS identifiers, raw source rows, account data, and exception text
never leave this service.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Mapping

from compass_common import http


MAX_SIGNALS = 100
MAX_STAGES = 100
_TABLE = None


def _table():
    global _TABLE
    if _TABLE is None:
        import boto3

        name = os.environ.get("OPERATIONS_TABLE", "").strip()
        if not name:
            raise RuntimeError("OPERATIONS_TABLE is required")
        _TABLE = boto3.resource("dynamodb").Table(name)
    return _TABLE


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _public(item: Mapping[str, Any]) -> Dict[str, Any]:
    hidden = {"pk", "sk", "gsi1pk", "gsi1sk", "record_type"}
    return {
        key: _json_safe(value)
        for key, value in item.items()
        if key not in hidden and value is not None
    }


def _query_index(kind: str, *, limit: int) -> List[Dict[str, Any]]:
    from boto3.dynamodb.conditions import Key

    response = _table().query(
        IndexName="by-type",
        KeyConditionExpression=Key("gsi1pk").eq(kind),
        ScanIndexForward=False,
        Limit=max(1, min(MAX_SIGNALS, int(limit))),
    )
    return [_public(item) for item in response.get("Items", [])]


def _query_run(run_id: str) -> List[Dict[str, Any]]:
    from boto3.dynamodb.conditions import Key

    response = _table().query(
        KeyConditionExpression=Key("pk").eq(f"RUN#{run_id}"),
        ScanIndexForward=True,
        Limit=MAX_STAGES,
    )
    return [_public(item) for item in response.get("Items", [])]


def _valid_identifier(value: str, *, prefix: str = "") -> bool:
    return bool(
        re.fullmatch(rf"{re.escape(prefix)}[A-Za-z0-9][A-Za-z0-9._:-]{{0,179}}", value)
    ) and ".." not in value


def list_signals(limit: int = 50) -> Dict[str, Any]:
    signals = _query_index("SIGNAL", limit=limit)
    return {
        "contract": "compass.operational-signals.v1",
        "mode": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "unacknowledged": sum(
            1 for item in signals if item.get("status") != "acknowledged"
        ),
        "delivery_disclosure": (
            "In-app evidence is authoritative. SNS means the event was published to "
            "the protected topic; email requires a separately confirmed subscription."
        ),
    }


def list_lineage(limit: int = 100) -> Dict[str, Any]:
    stages = _query_index("LINEAGE", limit=limit)
    grouped: Dict[str, Dict[str, Any]] = {}
    for stage in stages:
        run_id = str(stage.get("run_id") or "")
        if not run_id:
            continue
        run = grouped.setdefault(
            run_id,
            {
                "run_id": run_id,
                "run_kind": stage.get("run_kind") or "operational-run",
                "status": stage.get("status") or "running",
                "updated_at": stage.get("updated_at"),
                "stage_count": 0,
                "terminal_stage": stage.get("stage_id"),
                "source_sha256": stage.get("source_sha256"),
            },
        )
        run["stage_count"] += 1
        if str(stage.get("updated_at") or "") > str(run.get("updated_at") or ""):
            run["updated_at"] = stage.get("updated_at")
            run["status"] = stage.get("status") or "running"
            run["terminal_stage"] = stage.get("stage_id")
        if stage.get("source_sha256") and not run.get("source_sha256"):
            run["source_sha256"] = stage.get("source_sha256")
    runs = sorted(grouped.values(), key=lambda item: str(item.get("updated_at")), reverse=True)
    return {
        "contract": "compass.operational-lineage-list.v1",
        "mode": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": runs,
    }


def get_lineage(run_id: str) -> Dict[str, Any] | None:
    stages = sorted(_query_run(run_id), key=lambda item: int(item.get("sequence") or 0))
    if not stages:
        return None
    final = stages[-1]
    source = next((stage.get("source") for stage in stages if stage.get("source")), None)
    model = next(
        (
            stage.get("detail", {}).get("model_version")
            for stage in reversed(stages)
            if isinstance(stage.get("detail"), Mapping)
            and stage.get("detail", {}).get("model_version")
        ),
        None,
    )
    consumer = next(
        (
            stage.get("detail", {}).get("consumer")
            for stage in reversed(stages)
            if isinstance(stage.get("detail"), Mapping)
            and stage.get("detail", {}).get("consumer")
        ),
        None,
    )
    edges = [
        {"from": previous["stage_id"], "to": current["stage_id"]}
        for previous, current in zip(stages, stages[1:])
    ]
    return {
        "contract": "compass.operational-lineage.v1",
        "mode": "live",
        "run_id": run_id,
        "run_kind": final.get("run_kind") or "operational-run",
        "status": final.get("status") or "running",
        "source": source,
        "source_sha256": next(
            (stage.get("source_sha256") for stage in stages if stage.get("source_sha256")),
            None,
        ),
        "model": model,
        "consumer": consumer,
        "stages": stages,
        "edges": edges,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def summary() -> Dict[str, Any]:
    signals = list_signals(100)
    lineage = list_lineage(100)
    acquisitions = _query_index("ACQUISITION", limit=20)
    latest_attempt = acquisitions[0] if acquisitions else None
    latest_accepted = next(
        (
            acquisition
            for acquisition in acquisitions
            if str(acquisition.get("status") or "").lower() == "completed"
        ),
        None,
    )
    return {
        "contract": "compass.operational-summary.v1",
        "mode": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "lineage_runs": len(lineage["runs"]),
            "signals": len(signals["signals"]),
            "unacknowledged_signals": signals["unacknowledged"],
            "public_acquisitions": len(acquisitions),
        },
        "runs": lineage["runs"][:12],
        "latest_public_acquisition": latest_accepted,
        "latest_public_acquisition_attempt": latest_attempt,
        "proof": {
            "document_intake": "server-stage-receipts",
            "continuous_public_acquisition": (
                "scheduled-micro-batch" if latest_attempt else "configured-no-receipt"
            ),
            "notifications": "in-app-and-sns",
            "il4_il5": "target-architecture-only",
        },
        "disclosure": (
            "This commercial AWS environment processes synthetic and public data only. "
            "IL4/IL5 is a target architecture that requires a Government authorization boundary."
        ),
    }


def acknowledge(event_id: str, actor: str) -> Dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    response = _table().update_item(
        Key={"pk": f"SIGNAL#{event_id}", "sk": "STATE"},
        UpdateExpression=(
            "SET #status = :status, acknowledged_at = :at, acknowledged_by = :actor, "
            "updated_at = :at"
        ),
        ConditionExpression="attribute_exists(pk)",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "acknowledged",
            ":at": now,
            ":actor": actor[:160],
        },
        ReturnValues="ALL_NEW",
    )
    item = response.get("Attributes")
    return _public(item) if item else None


def _poweruser(event: Mapping[str, Any]):
    claims = http.get_claims(dict(event))
    allowed = claims.is_authenticated and claims.role == "poweruser" and claims.is_corporate
    return claims, allowed


def handler(event, context=None):
    event = event or {}
    claims, allowed = _poweruser(event)
    if not claims.is_authenticated:
        return http.unauthorized()
    if not allowed:
        return http.forbidden("operational evidence requires the corporate poweruser role")
    method = http.get_method(event) or ""
    path = http.get_path(event) or ""
    try:
        if method == "GET" and path.endswith("/operations/signals"):
            params = http.query_params(event)
            try:
                limit = int(params.get("limit", "50"))
            except (TypeError, ValueError):
                limit = 50
            return http.ok(list_signals(limit))
        if method == "GET" and path.endswith("/operations/lineage"):
            return http.ok(list_lineage())
        lineage_match = re.search(r"/operations/lineage/([^/]+)$", path)
        if method == "GET" and lineage_match:
            run_id = lineage_match.group(1)
            if not _valid_identifier(run_id):
                return http.bad_request("invalid run identifier")
            result = get_lineage(run_id)
            return http.ok(result) if result else http.not_found("lineage run not found")
        if method == "GET" and path.endswith("/operations/summary"):
            return http.ok(summary())
        signal_match = re.search(r"/operations/signals/([^/]+)/acknowledge$", path)
        if method == "POST" and signal_match:
            event_id = signal_match.group(1)
            if not _valid_identifier(event_id, prefix="sig-"):
                return http.bad_request("invalid event identifier")
            actor = claims.username or claims.email or claims.sub or "poweruser"
            try:
                result = acknowledge(event_id, actor)
            except Exception as exc:  # noqa: BLE001 - conditional miss is a 404
                if "ConditionalCheckFailed" in type(exc).__name__ or "ConditionalCheckFailed" in str(exc):
                    return http.not_found("operational signal not found")
                raise
            return http.ok(result) if result else http.not_found("operational signal not found")
        return http.not_found("unknown operational evidence route")
    except Exception:
        return http.server_error()

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


def _key(name: str):
    """Load the DynamoDB condition builder only in the AWS-backed adapter."""
    from boto3.dynamodb.conditions import Key

    return Key(name)


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
    response = _table().query(
        IndexName="by-type",
        KeyConditionExpression=_key("gsi1pk").eq(kind),
        ScanIndexForward=False,
        Limit=max(1, min(MAX_SIGNALS, int(limit))),
    )
    return [_public(item) for item in response.get("Items", [])]


def _query_run(run_id: str) -> List[Dict[str, Any]]:
    response = _table().query(
        KeyConditionExpression=_key("pk").eq(f"RUN#{run_id}"),
        ScanIndexForward=True,
        Limit=MAX_STAGES,
    )
    return [_public(item) for item in response.get("Items", [])]


def _valid_identifier(value: str, *, prefix: str = "") -> bool:
    return bool(
        re.fullmatch(rf"{re.escape(prefix)}[A-Za-z0-9][A-Za-z0-9._:-]{{0,179}}", value)
    ) and ".." not in value


def _needs_attention(item: Mapping[str, Any]) -> bool:
    if str(item.get("status") or "").lower() != "open":
        return False
    if str(item.get("severity") or "").lower() in {
        "critical",
        "high",
        "medium",
        "warning",
    }:
        return True
    delivery = item.get("delivery")
    return isinstance(delivery, Mapping) and str(
        delivery.get("status") or ""
    ).lower() == "failed"


def _normalized_evidence_class(value: Any) -> str | None:
    normalized = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    if not normalized or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,79}", normalized):
        return None
    return normalized


def _declared_evidence_class(item: Mapping[str, Any]) -> str | None:
    direct = _normalized_evidence_class(item.get("evidence_class"))
    if direct:
        return direct
    detail = item.get("detail")
    if isinstance(detail, Mapping):
        return _normalized_evidence_class(detail.get("evidence_class"))
    return None


def _known_synthetic_receipt(item: Mapping[str, Any]) -> bool:
    run_id = str(item.get("run_id") or "").lower()
    category = str(item.get("category") or "").lower().replace("_", "-")
    stream_kind = str(item.get("stream_kind") or "").lower()
    if run_id.startswith("run-live-") or category == "demo-stream":
        return True
    if stream_kind in {"continuous-synthetic", "accelerated-synthetic"}:
        return True
    explicit_text = " ".join(
        str(item.get(key) or "").lower()
        for key in ("source", "destination", "evidence_uri", "title", "message")
    )
    return "live-stream" in explicit_text or "synthetic" in explicit_text


def _inferred_evidence_class(
    item: Mapping[str, Any],
    *,
    fallback: str,
) -> str:
    if _known_synthetic_receipt(item):
        return "synthetic-demo"
    declared = _declared_evidence_class(item)
    if declared:
        return declared

    run_kind = str(item.get("run_kind") or "").lower().replace("_", "-")
    category = str(item.get("category") or "").lower().replace("_", "-")
    stage_id = str(item.get("stage_id") or "").lower().replace("_", "-")
    if run_kind == "public-acquisition" or category == "public-acquisition":
        return "public-observed"
    if run_kind in {"public-narrative-classification", "sagemaker-batch-inference"}:
        prediction_tokens = ("classif", "infer", "model", "predict", "publish", "score")
        if any(token in stage_id for token in prediction_tokens):
            return "public-predicted"
        return "public-observed"
    if "public" in category and any(
        token in category for token in ("model", "classif", "predict", "infer")
    ):
        return "public-predicted"
    if category.startswith("public"):
        return "public-observed"
    return fallback


def _run_evidence_class(stages: List[Mapping[str, Any]]) -> str:
    classes = {
        _inferred_evidence_class(stage, fallback="unclassified")
        for stage in stages
    }
    classes.discard("unclassified")
    if not classes:
        return "unclassified"
    if any(value.startswith("synthetic") for value in classes):
        return "synthetic-demo"
    if len(classes) == 1:
        return next(iter(classes))
    if all(value.startswith("public") for value in classes):
        return "public-derived"
    return "mixed-evidence"


def _is_live_public_evidence_class(value: Any) -> bool:
    evidence_class = _normalized_evidence_class(value)
    return bool(
        evidence_class == "operational-control"
        or evidence_class == "public"
        or (evidence_class and evidence_class.startswith("public-"))
    )


def _classify_lineage_stages(stages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_run: Dict[str, List[Dict[str, Any]]] = {}
    for stage in stages:
        run_id = str(stage.get("run_id") or "")
        if run_id:
            by_run.setdefault(run_id, []).append(stage)

    run_classes = {
        run_id: _run_evidence_class(run_stages)
        for run_id, run_stages in by_run.items()
    }
    classified = []
    for stage in stages:
        run_id = str(stage.get("run_id") or "")
        evidence_class = _inferred_evidence_class(stage, fallback="unclassified")
        if evidence_class == "unclassified":
            evidence_class = run_classes.get(run_id, "unclassified")
        classified.append({**stage, "evidence_class": evidence_class})
    return classified


def _classify_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **signal,
        "evidence_class": _inferred_evidence_class(
            signal,
            fallback="operational-control",
        ),
    }


def list_signals(limit: int = 50) -> Dict[str, Any]:
    signals = [
        _classify_signal(signal)
        for signal in _query_index("SIGNAL", limit=limit)
    ]
    unresolved_run_ids = {
        str(signal.get("run_id") or "")
        for signal in signals
        if signal.get("evidence_class") == "operational-control"
        and signal.get("run_id")
    }
    if unresolved_run_ids:
        lineage_stages = _classify_lineage_stages(
            _query_index("LINEAGE", limit=MAX_STAGES)
        )
        lineage_classes = {
            run_id: _run_evidence_class(
                [
                    stage
                    for stage in lineage_stages
                    if str(stage.get("run_id") or "") == run_id
                ]
            )
            for run_id in unresolved_run_ids
        }
        signals = [
            {
                **signal,
                "evidence_class": lineage_classes.get(
                    str(signal.get("run_id") or ""),
                    "operational-control",
                ),
            }
            if signal.get("evidence_class") == "operational-control"
            and lineage_classes.get(str(signal.get("run_id") or ""))
            not in {None, "unclassified"}
            else signal
            for signal in signals
        ]
    signals = [
        signal
        for signal in signals
        if _is_live_public_evidence_class(signal.get("evidence_class"))
    ]
    return {
        "contract": "compass.operational-signals.v1",
        "mode": "live",
        "evidence_scope": "public-only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "unacknowledged": sum(1 for item in signals if _needs_attention(item)),
        "delivery_disclosure": (
            "In-app evidence is authoritative. SNS means the event was published to "
            "the protected topic; email requires a separately confirmed subscription."
        ),
    }


def list_lineage(limit: int = 100) -> Dict[str, Any]:
    stages = _classify_lineage_stages(_query_index("LINEAGE", limit=limit))
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
                "evidence_class": "unclassified",
            },
        )
        run["stage_count"] += 1
        if str(stage.get("updated_at") or "") > str(run.get("updated_at") or ""):
            run["updated_at"] = stage.get("updated_at")
            run["status"] = stage.get("status") or "running"
            run["terminal_stage"] = stage.get("stage_id")
        if stage.get("source_sha256") and not run.get("source_sha256"):
            run["source_sha256"] = stage.get("source_sha256")
    for run_id, run in grouped.items():
        run["evidence_class"] = _run_evidence_class(
            [stage for stage in stages if str(stage.get("run_id") or "") == run_id]
        )
    runs = sorted(
        (
            run
            for run in grouped.values()
            if _is_live_public_evidence_class(run.get("evidence_class"))
        ),
        key=lambda item: str(item.get("updated_at")),
        reverse=True,
    )
    return {
        "contract": "compass.operational-lineage-list.v1",
        "mode": "live",
        "evidence_scope": "public-only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": runs,
    }


def get_lineage(run_id: str) -> Dict[str, Any] | None:
    stages = sorted(
        _classify_lineage_stages(_query_run(run_id)),
        key=lambda item: int(item.get("sequence") or 0),
    )
    if not stages:
        return None
    evidence_class = _run_evidence_class(stages)
    if not _is_live_public_evidence_class(evidence_class):
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
        "evidence_scope": "public-only",
        "run_id": run_id,
        "run_kind": final.get("run_kind") or "operational-run",
        "status": final.get("status") or "running",
        "evidence_class": evidence_class,
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
        "evidence_scope": "public-only",
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
    return _classify_signal(_public(item)) if item else None


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
                limit = int(params.get("limit", str(MAX_SIGNALS)))
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

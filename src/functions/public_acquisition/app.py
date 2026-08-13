"""Scheduled, provenance-bound USAspending acquisition for public ONR signals.

USAspending exposes a request API, not a push stream. Compass therefore uses a
bounded scheduled micro-batch poll, retains each response and canonical
projection, compares stable record digests, emits accepted change events onto
Kinesis, and records lineage and notification receipts. This is never described
as an authoritative inventory of ONR activity.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Mapping

from compass_common import http, operational_evidence


SOURCE_ID = "usaspending-onr-grants"
ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
CONTRACT = "compass.public-acquisition.v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_RECORDS = 100
AWARD_TYPES = ("02", "03", "04", "05", "F001", "F002")
FIELDS = (
    "Award ID",
    "Start Date",
    "End Date",
    "Award Amount",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Funding Agency",
    "Funding Sub Agency",
    "Award Type",
    "Description",
)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

_TABLE = None
_S3 = None
_KINESIS = None
_URL_OPEN = urllib.request.urlopen


class AcquisitionFailure(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(now: datetime | None = None) -> str:
    return (now or _now()).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


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


def _table():
    global _TABLE
    if _TABLE is None:
        import boto3

        _TABLE = boto3.resource("dynamodb").Table(os.environ["OPERATIONS_TABLE"])
    return _TABLE


def _s3():
    global _S3
    if _S3 is None:
        import boto3

        _S3 = boto3.client("s3")
    return _S3


def _kinesis():
    global _KINESIS
    if _KINESIS is None:
        import boto3

        _KINESIS = boto3.client("kinesis")
    return _KINESIS


def _query_body(now: datetime) -> Dict[str, Any]:
    start = (now - timedelta(days=550)).date().isoformat()
    end = now.date().isoformat()
    return {
        "filters": {
            "award_type_codes": list(AWARD_TYPES),
            "time_period": [{"start_date": start, "end_date": end}],
            "keywords": ["N00014"],
        },
        "fields": list(FIELDS),
        "page": 1,
        "limit": MAX_RECORDS,
        "sort": "Award ID",
        "order": "desc",
        "subawards": False,
    }


def _fetch(body: Mapping[str, Any]) -> tuple[Dict[str, Any], bytes]:
    request = urllib.request.Request(
        ENDPOINT,
        method="POST",
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Compass-Public-Evidence/1.0 contact@satsyil.com",
        },
    )
    try:
        with _URL_OPEN(request, timeout=25) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AcquisitionFailure(f"source request failed: {type(exc).__name__}") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise AcquisitionFailure("source response exceeded the configured byte limit")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise AcquisitionFailure("source response was not valid JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("results"), list):
        raise AcquisitionFailure("source response did not match the expected result contract")
    return value, raw


def _text(value: Any, maximum: int = 500) -> str | None:
    text = " ".join(str(value or "").replace("\u2014", " - ").split()).strip()
    text = EMAIL_PATTERN.sub("[redacted-email]", text)
    return text[:maximum] or None


def _canonical_record(raw: Mapping[str, Any]) -> Dict[str, Any] | None:
    award_id = _text(raw.get("Award ID"), 160)
    if not award_id:
        return None
    try:
        amount = float(raw.get("Award Amount")) if raw.get("Award Amount") is not None else None
    except (TypeError, ValueError):
        amount = None
    record = {
        "source_id": SOURCE_ID,
        "source_record_id": award_id,
        "record_type": "award",
        "start_date": _text(raw.get("Start Date"), 32),
        "end_date": _text(raw.get("End Date"), 32),
        "award_amount_usd": amount,
        "award_type": _text(raw.get("Award Type"), 120),
        "awarding_agency": _text(raw.get("Awarding Agency"), 160),
        "awarding_subagency": _text(raw.get("Awarding Sub Agency"), 160),
        "funding_agency": _text(raw.get("Funding Agency"), 160),
        "funding_subagency": _text(raw.get("Funding Sub Agency"), 160),
        "description": _text(raw.get("Description"), 1000),
        "source_url": ENDPOINT,
    }
    record["record_sha256"] = _digest(record)
    return record


def _put_bytes(key: str, payload: bytes, *, metadata: Mapping[str, str]) -> str:
    bucket = os.environ["PUBLIC_ACQUISITION_BUCKET"]
    response = _s3().put_object(
        Bucket=bucket,
        Key=key,
        Body=payload,
        ContentType="application/json",
        Metadata=dict(metadata),
    )
    version = response.get("VersionId")
    return f"public-evidence://{key}" + (f"?version={version}" if version else "")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )


def _get_alias() -> Dict[str, Any] | None:
    response = _table().get_item(
        Key={"pk": f"ACQUISITION_ALIAS#{SOURCE_ID}", "sk": "STATE"},
        ConsistentRead=True,
    )
    item = response.get("Item")
    return _json_safe(item) if item else None


def _put_acquisition(record: Mapping[str, Any]) -> None:
    item = {
        **dict(record),
        "pk": f"ACQUISITION#{record['run_id']}",
        "sk": "STATE",
        "gsi1pk": "ACQUISITION",
        "gsi1sk": f"{record['updated_at']}#{record['run_id']}",
        "record_type": "acquisition",
    }
    _table().put_item(Item=_decimal_safe(item))


def _put_alias(record: Mapping[str, Any], record_hashes: Mapping[str, str]) -> None:
    item = {
        "pk": f"ACQUISITION_ALIAS#{SOURCE_ID}",
        "sk": "STATE",
        "run_id": record["run_id"],
        "snapshot_sha256": record["snapshot_sha256"],
        "record_hashes": dict(record_hashes),
        "updated_at": record["updated_at"],
    }
    _table().put_item(Item=item)


def _diff(
    previous: Mapping[str, str], current: Mapping[str, str]
) -> tuple[List[str], List[str], List[str], List[str]]:
    added = sorted(set(current).difference(previous))
    changed = sorted(key for key in set(current).intersection(previous) if current[key] != previous[key])
    unchanged = sorted(key for key in set(current).intersection(previous) if current[key] == previous[key])
    not_observed = sorted(set(previous).difference(current))
    return added, changed, unchanged, not_observed


def _publish_stream(
    acquisition: Mapping[str, Any],
    records: List[Mapping[str, Any]],
    added: List[str],
    changed: List[str],
) -> None:
    stream = os.environ.get("STREAM_NAME", "").strip()
    if not stream:
        return
    change_by_id = {record_id: "added" for record_id in added}
    change_by_id.update({record_id: "changed" for record_id in changed})
    if not change_by_id:
        return
    records_by_id = {str(record["source_record_id"]): record for record in records}
    entries = []
    for source_record_id, change_kind in sorted(change_by_id.items()):
        source_record = records_by_id.get(source_record_id)
        if source_record is None:
            continue
        source_hash = str(source_record["record_sha256"])
        event = {
            "id": f"public-acquisition:{acquisition['run_id']}:{source_hash[:16]}",
            "at": acquisition["updated_at"],
            "kind": "public-feed",
            "message": f"USAspending public award {source_record_id} was {change_kind}",
            "grant_no": source_record_id,
            "org_unit": None,
            "run_id": acquisition["run_id"],
            "change_kind": change_kind,
            "source_record_sha256": source_hash,
        }
        entries.append(
            {
                "PartitionKey": source_record_id,
                "Data": json.dumps(event, separators=(",", ":")).encode("utf-8"),
            }
        )
    if not entries:
        return
    response = _kinesis().put_records(
        StreamName=stream,
        Records=entries,
    )
    failed = int(response.get("FailedRecordCount") or 0)
    if failed:
        raise AcquisitionFailure(f"{failed} public change events failed to publish")


def run_acquisition(*, actor: str = "compass-public-acquisition") -> Dict[str, Any]:
    now = _now()
    run_id = f"acq-{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    source = "public-api://usaspending/search/spending_by_award?scope=N00014-grants"
    body = _query_body(now)
    query_sha = _digest(body)
    operational_evidence.record_stage(
        run_id=run_id,
        run_kind="public-acquisition",
        sequence=1,
        stage_id="source-request",
        label="Bounded source request",
        status="running",
        source=source,
        input_sha256=query_sha,
        actor=actor,
        detail={"evidence_class": "public-observed", "record_count": MAX_RECORDS},
    )
    try:
        response, raw_bytes = _fetch(body)
        results = response.get("results") or []
        records = [record for raw in results if isinstance(raw, Mapping) for record in [_canonical_record(raw)] if record]
        if not records:
            raise AcquisitionFailure("source returned no valid records for the bounded scope")
        records.sort(key=lambda item: str(item["source_record_id"]))
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()
        snapshot_sha = _digest(records)
        prefix = f"public-intelligence/acquisitions/{run_id}"
        raw_uri = _put_bytes(
            f"{prefix}/raw-response.json",
            raw_bytes,
            metadata={"run-id": run_id, "stage": "raw", "sha256": raw_sha},
        )
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=2,
            stage_id="raw-retained",
            label="Immutable raw response retained",
            status="completed",
            source=source,
            destination=raw_uri,
            input_sha256=query_sha,
            output_sha256=raw_sha,
            actor=actor,
            detail={"record_count": len(results), "evidence_class": "public-observed"},
        )
        canonical_payload = _json_bytes(
            {
                "contract": "compass.public-acquisition-records.v1",
                "run_id": run_id,
                "retrieved_at": _iso(now),
                "records": records,
            }
        )
        canonical_object_sha = hashlib.sha256(canonical_payload).hexdigest()
        canonical_uri = _put_bytes(
            f"{prefix}/canonical-records.json",
            canonical_payload,
            metadata={
                "run-id": run_id,
                "stage": "canonical",
                "sha256": canonical_object_sha,
                "snapshot-sha256": snapshot_sha,
            },
        )
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=3,
            stage_id="canonicalized",
            label="PII-minimized canonical records",
            status="completed",
            source=raw_uri,
            destination=canonical_uri,
            input_sha256=raw_sha,
            output_sha256=canonical_object_sha,
            actor=actor,
            detail={"accepted_records": len(records), "schema": "public-award-v1"},
        )
        current_hashes = {
            str(record["source_record_id"]): str(record["record_sha256"])
            for record in records
        }
        previous_alias = _get_alias() or {}
        previous_hashes = previous_alias.get("record_hashes") or {}
        added, changed, unchanged, not_observed = _diff(previous_hashes, current_hashes)
        watermark = max(
            (str(item.get("start_date") or "") for item in records),
            default="",
        )
        accepted_at = _iso()
        has_next = bool((response.get("page_metadata") or {}).get("hasNext"))
        acquisition = {
            "contract": CONTRACT,
            "run_id": run_id,
            "source_id": SOURCE_ID,
            "source": source,
            "status": "completed",
            "stage": "accepted-snapshot",
            "started_at": _iso(now),
            "updated_at": accepted_at,
            "retrieved_at": accepted_at,
            "watermark": watermark or None,
            "query_sha256": query_sha,
            "source_response_sha256": raw_sha,
            "snapshot_sha256": snapshot_sha,
            "canonical_object_sha256": canonical_object_sha,
            "record_count": len(records),
            "added_records": len(added),
            "changed_records": len(changed),
            "unchanged_records": len(unchanged),
            "not_observed_records": len(not_observed),
            "has_more_source_pages": has_next,
            "raw_receipt_uri": raw_uri,
            "canonical_receipt_uri": canonical_uri,
            "evidence_class": "public-observed",
            "poll_mode": "scheduled-micro-batch",
            "scope_disclosure": (
                "Department of the Navy candidate grants matched by keyword N00014 within "
                "a bounded recent window. Not an authoritative inventory of ONR activity. "
                "Records absent from the next bounded page are not treated as source deletions."
            ),
        }
        _put_acquisition(acquisition)
        _put_alias(acquisition, current_hashes)
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=4,
            stage_id="change-detected",
            label="Snapshot change detection",
            status="completed",
            source=canonical_uri,
            input_sha256=str(previous_alias.get("snapshot_sha256") or query_sha),
            output_sha256=snapshot_sha,
            actor=actor,
            detail={
                "added_records": len(added),
                "changed_records": len(changed),
                "unchanged_records": len(unchanged),
                "not_observed_records": len(not_observed),
            },
        )
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=5,
            stage_id="accepted-snapshot",
            label="Accepted public evidence snapshot",
            status="completed",
            source=canonical_uri,
            destination="mission-workspace://public-intelligence/source-ledger",
            source_sha256=snapshot_sha,
            actor=actor,
            detail={
                "accepted_records": len(records),
                "consumer": "Public Intelligence and Kinesis activity",
                "evidence_class": "public-observed",
            },
        )
        if added or changed:
            operational_evidence.record_signal(
                category="public-acquisition",
                severity="info",
                title="USAspending acquisition completed",
                message=(
                    f"Accepted {len(records)} bounded public records with {len(added)} added "
                    f"and {len(changed)} changed records."
                ),
                run_id=run_id,
                evidence_uri=canonical_uri,
                detail={
                    "record_count": len(records),
                    "added_records": len(added),
                    "changed_records": len(changed),
                    "unchanged_records": len(unchanged),
                },
            )
        threshold = int(os.environ.get("PUBLIC_ACQUISITION_CHANGE_ALERT_THRESHOLD", "10"))
        if len(added) + len(changed) >= max(1, threshold):
            operational_evidence.record_signal(
                category="public-data-anomaly",
                severity="high",
                title="Public award change threshold crossed",
                message=(
                    f"{len(added) + len(changed)} added or changed records crossed the "
                    f"configured threshold of {threshold}. Analyst review is required."
                ),
                run_id=run_id,
                evidence_uri=canonical_uri,
                detail={
                    "added_records": len(added),
                    "changed_records": len(changed),
                    "threshold": threshold,
                },
            )
        try:
            _publish_stream(acquisition, records, added, changed)
        except Exception as exc:  # noqa: BLE001 - accepted snapshot remains authoritative
            print(
                json.dumps(
                    {
                        "event_type": "public_acquisition_stream_publish_failed",
                        "run_id": run_id,
                        "error_type": type(exc).__name__,
                    }
                )
            )
            operational_evidence.record_signal(
                category="public-acquisition-delivery",
                severity="high",
                title="Public change event delivery degraded",
                message=(
                    "The accepted public snapshot remains active, but one or more "
                    "Kinesis change envelopes were not delivered. Operator review is required."
                ),
                run_id=run_id,
                evidence_uri=canonical_uri,
                detail={
                    "added_records": len(added),
                    "changed_records": len(changed),
                },
            )
        return acquisition
    except Exception as exc:
        failed_at = _iso()
        failure = {
            "contract": CONTRACT,
            "run_id": run_id,
            "source_id": SOURCE_ID,
            "source": source,
            "status": "failed",
            "stage": "source-acquisition",
            "started_at": _iso(now),
            "updated_at": failed_at,
            "failure_code": type(exc).__name__,
            "scope_disclosure": "The source request failed before an accepted snapshot was published.",
        }
        _put_acquisition(failure)
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=99,
            stage_id="failed",
            label="Acquisition failed",
            status="failed",
            source=source,
            input_sha256=query_sha,
            actor=actor,
            detail={"retry_count": 0},
        )
        operational_evidence.record_signal(
            category="public-acquisition",
            severity="high",
            title="USAspending acquisition failed",
            message="No new public snapshot was accepted. The previous accepted snapshot remains active.",
            run_id=run_id,
            detail={"retry_count": 0},
        )
        raise AcquisitionFailure("public acquisition did not complete") from exc


def list_acquisitions(limit: int = 20) -> Dict[str, Any]:
    from boto3.dynamodb.conditions import Key

    response = _table().query(
        IndexName="by-type",
        KeyConditionExpression=Key("gsi1pk").eq("ACQUISITION"),
        ScanIndexForward=False,
        Limit=max(1, min(50, limit)),
    )
    records = []
    for item in response.get("Items", []):
        public = _json_safe(item)
        for hidden in ("pk", "sk", "gsi1pk", "gsi1sk", "record_type"):
            public.pop(hidden, None)
        records.append(public)
    return {
        "contract": "compass.public-acquisition-list.v1",
        "mode": "live",
        "generated_at": _iso(),
        "schedule": "rate(5 minutes)",
        "source_transport": "bounded HTTPS polling, then Kinesis change events",
        "acquisitions": records,
    }


def _poweruser(event: Mapping[str, Any]):
    claims = http.get_claims(dict(event))
    return claims, claims.is_authenticated and claims.role == "poweruser" and claims.is_corporate


def handler(event, context=None):
    event = event or {}
    if event.get("action") == "poll":
        return run_acquisition()
    if not (event.get("requestContext") or {}).get("http"):
        raise ValueError("expected a scheduled poll or an HTTP request")
    claims, allowed = _poweruser(event)
    if not claims.is_authenticated:
        return http.unauthorized()
    if not allowed:
        return http.forbidden("public acquisition control requires the corporate poweruser role")
    method = http.get_method(event) or ""
    path = http.get_path(event) or ""
    if method == "GET" and path.endswith("/public-intelligence/acquisitions"):
        return http.ok(list_acquisitions())
    if method == "POST" and path.endswith("/public-intelligence/acquisitions/run"):
        actor = claims.username or claims.email or claims.sub or "poweruser"
        try:
            return http.created(run_acquisition(actor=actor))
        except AcquisitionFailure:
            return http.error_response(
                502,
                "the public source poll failed; the previous accepted snapshot remains active",
            )
    return http.not_found("unknown public acquisition route")

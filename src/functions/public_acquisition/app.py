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
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Mapping

from compass_common import http, operational_evidence

import feed_sources


SOURCE_ID = "usaspending-onr-grants"
ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
CONTRACT = "compass.public-acquisition.v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PROFILE_CONFIG = {
    "quick": {"page_size": 25, "pages": 1},
    "standard": {"page_size": 100, "pages": 1},
    "deep": {"page_size": 100, "pages": 5},
}
AWARD_TYPES = ("02", "03", "04", "05", "F001", "F002")
FIELDS = (
    "Award ID",
    "Recipient Name",
    "recipient_id",
    "generated_internal_id",
    "Last Modified Date",
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
_LAMBDA = None
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


def _lambda():
    global _LAMBDA
    if _LAMBDA is None:
        import boto3

        _LAMBDA = boto3.client("lambda")
    return _LAMBDA


def _query_body(now: datetime, *, page: int = 1, limit: int = 100) -> Dict[str, Any]:
    start = (now - timedelta(days=550)).date().isoformat()
    end = now.date().isoformat()
    return {
        "filters": {
            "award_type_codes": list(AWARD_TYPES),
            "time_period": [{"start_date": start, "end_date": end}],
            "keywords": ["N00014"],
        },
        "fields": list(FIELDS),
        "page": page,
        "limit": limit,
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


def _open_json_request(
    request: urllib.request.Request, timeout: int
) -> tuple[Dict[str, Any], bytes]:
    try:
        with _URL_OPEN(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AcquisitionFailure(f"source request failed: {type(exc).__name__}") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise AcquisitionFailure("source response exceeded the configured byte limit")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise AcquisitionFailure("source response was not valid JSON") from exc
    if not isinstance(value, dict):
        raise AcquisitionFailure("source response did not match the expected object contract")
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
    generated_id = _text(raw.get("generated_internal_id"), 240)
    record = {
        "source_id": SOURCE_ID,
        "source_record_id": award_id,
        "record_type": "award",
        "recipient_name": _text(raw.get("Recipient Name"), 240),
        "recipient_id": _text(raw.get("recipient_id"), 240),
        "last_modified_at": _text(raw.get("Last Modified Date"), 64),
        "start_date": _text(raw.get("Start Date"), 32),
        "end_date": _text(raw.get("End Date"), 32),
        "award_amount_usd": amount,
        "award_type": _text(raw.get("Award Type"), 120),
        "awarding_agency": _text(raw.get("Awarding Agency"), 160),
        "awarding_subagency": _text(raw.get("Awarding Sub Agency"), 160),
        "funding_agency": _text(raw.get("Funding Agency"), 160),
        "funding_subagency": _text(raw.get("Funding Sub Agency"), 160),
        "description": _text(raw.get("Description"), 1000),
        "source_url": (
            f"https://www.usaspending.gov/award/{generated_id}"
            if generated_id
            else ENDPOINT
        ),
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


def _get_alias(source_id: str = SOURCE_ID) -> Dict[str, Any] | None:
    response = _table().get_item(
        Key={"pk": f"ACQUISITION_ALIAS#{source_id}", "sk": "STATE"},
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


def _put_alias(
    record: Mapping[str, Any], record_hashes: Mapping[str, str], source_id: str = SOURCE_ID
) -> None:
    item = {
        "pk": f"ACQUISITION_ALIAS#{source_id}",
        "sk": "STATE",
        "run_id": record["run_id"],
        "snapshot_sha256": record["snapshot_sha256"],
        "record_hashes": dict(record_hashes),
        "classification_summary": record.get("classification_summary"),
        "updated_at": record["updated_at"],
    }
    _table().put_item(Item=_decimal_safe(item))


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
            "message": (
                f"{acquisition.get('source_label') or acquisition.get('source_id') or 'Public source'} "
                f"record {source_record_id} was {change_kind}"
            ),
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


def _profile(value: str | None) -> tuple[str, Dict[str, int]]:
    name = str(value or "standard").strip().lower()
    if name not in PROFILE_CONFIG:
        raise ValueError("profile must be quick, standard, or deep")
    return name, PROFILE_CONFIG[name]


def _fetch_profile(now: datetime, profile: Mapping[str, int]) -> tuple[List[Dict[str, Any]], bytes, bool, int]:
    pages: List[Dict[str, Any]] = []
    total_bytes = 0
    has_next = False
    for page_number in range(1, int(profile["pages"]) + 1):
        body = _query_body(now, page=page_number, limit=int(profile["page_size"]))
        response, raw = _fetch(body)
        pages.append(response)
        total_bytes += len(raw)
        has_next = bool((response.get("page_metadata") or {}).get("hasNext"))
        if not has_next:
            break
    retained = _json_bytes(
        {
            "contract": "compass.public-acquisition-source-pages.v1",
            "endpoint": ENDPOINT,
            "pages": pages,
        }
    )
    return pages, retained, has_next, total_bytes


def _change_lookup(added: List[str], changed: List[str]) -> Dict[str, str]:
    result = {record_id: "added" for record_id in added}
    result.update({record_id: "changed" for record_id in changed})
    return result


def _review_flags(
    records: List[Mapping[str, Any]], added: List[str], changed: List[str]
) -> List[Dict[str, Any]]:
    changes = _change_lookup(added, changed)
    flags: List[Dict[str, Any]] = []
    ordered = sorted(
        records,
        key=lambda item: float(item.get("award_amount_usd") or 0),
        reverse=True,
    )
    for record in ordered:
        record_id = str(record["source_record_id"])
        amount = float(record.get("award_amount_usd") or 0)
        reasons = []
        if record_id in changes:
            reasons.append(f"source record {changes[record_id]}")
        if amount >= 5_000_000:
            reasons.append("high value award review")
        if not record.get("description"):
            reasons.append("missing narrative")
        if not reasons:
            continue
        flags.append(
            {
                "source_record_id": record_id,
                "recipient_name": record.get("recipient_name"),
                "award_amount_usd": record.get("award_amount_usd"),
                "last_modified_at": record.get("last_modified_at"),
                "source_url": record.get("source_url"),
                "reasons": reasons,
            }
        )
        if len(flags) >= 16:
            break
    return flags


def _record_preview(records: List[Mapping[str, Any]], limit: int = 24) -> List[Dict[str, Any]]:
    fields = (
        "source_id",
        "source_record_id",
        "record_type",
        "title",
        "description",
        "recipient_name",
        "award_amount_usd",
        "award_type",
        "published_date",
        "last_modified_at",
        "end_date",
        "organizations",
        "topics",
        "award_ids",
        "status",
        "citation_count",
        "source_url",
        "document_url",
        "document_title",
    )
    preview = []
    for record in records[: max(1, min(50, limit))]:
        item = {
                field: record.get(field)
                for field in fields
                if record.get(field) not in (None, "", [])
        }
        item["identity_keys"] = _identity_keys(record)
        preview.append(item)
    return preview


def _identity_keys(record: Mapping[str, Any]) -> List[str]:
    keys = []
    candidate_awards = [record.get("source_record_id"), *(record.get("award_ids") or [])]
    for value in candidate_awards:
        normalized = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
        if normalized.startswith("N00014") and len(normalized) >= 10:
            keys.append(f"AWARD#{normalized}")
    record_id = str(record.get("source_record_id") or "").strip().casefold()
    if record.get("record_type") == "publication" and record_id.startswith("10."):
        keys.append(f"DOI#{record_id}")
    recipient_id = str(record.get("recipient_id") or "").strip()
    if recipient_id:
        keys.append(f"RECIPIENT#{recipient_id}")
    return sorted(set(keys))[:12]


def _index_evidence_records(
    *, run_id: str, source_id: str, records: List[Mapping[str, Any]], observed_at: str
) -> Dict[str, Any]:
    indexed = 0
    keys = set()
    for record in records:
        identity_keys = _identity_keys(record)
        if not identity_keys:
            continue
        for identity_key in identity_keys:
            keys.add(identity_key)
            _table().put_item(
                Item=_decimal_safe(
                    {
                        "pk": f"EVIDENCE_ENTITY#{identity_key}",
                        "sk": f"SOURCE#{source_id}#{record['source_record_id']}",
                        "record_type": "evidence_identity",
                        "identity_key": identity_key,
                        "source_id": source_id,
                        "source_record_id": str(record["source_record_id"]),
                        "source_record_type": record.get("record_type"),
                        "title": _text(record.get("title") or record.get("description"), 240),
                        "source_url": record.get("source_url"),
                        "record_sha256": record.get("record_sha256"),
                        "run_id": run_id,
                        "updated_at": observed_at,
                        "link_method": "exact-public-identifier",
                        "link_confidence": 1.0,
                        "governance_owner": "Portfolio Data Product Owner",
                        "governance_steward": "Public Evidence Data Steward",
                        "classification": "PUBLIC",
                    }
                )
            )
        indexed += 1
    return {
        "indexed_records": indexed,
        "identity_key_count": len(keys),
        "link_method": "exact award number, DOI, or recipient source identifier",
        "governance_owner": "Portfolio Data Product Owner",
        "governance_steward": "Public Evidence Data Steward",
        "classification": "PUBLIC",
    }


def _classify_award_narratives(
    *,
    run_id: str,
    canonical_uri: str,
    canonical_sha256: str,
    records: List[Mapping[str, Any]],
    source_kind: str = "public-award-narratives",
) -> Dict[str, Any] | None:
    function_name = os.environ.get("PUBLIC_DOCUMENT_ML_FUNCTION", "").strip()
    if not function_name:
        return None
    payload = {
        "action": "classify_public_records",
        "acquisition_run_id": run_id,
        "source_kind": source_kind,
        "canonical_uri": canonical_uri,
        "canonical_sha256": canonical_sha256,
        "records": records[:500],
    }
    response = _lambda().invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=_json_bytes(payload),
    )
    body = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise AcquisitionFailure("the governed narrative classifier returned an error")
    if not isinstance(body, dict) or body.get("status") != "completed":
        raise AcquisitionFailure("the governed narrative classifier returned an invalid receipt")
    return body


def run_acquisition(
    *, actor: str = "compass-public-acquisition", profile: str = "standard"
) -> Dict[str, Any]:
    now = _now()
    started_clock = time.perf_counter()
    profile_name, profile_config = _profile(profile)
    run_id = f"acq-{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    source = "public-api://usaspending/search/spending_by_award?scope=N00014-grants"
    query_sha = _digest(
        {
            "profile": profile_name,
            "page_size": profile_config["page_size"],
            "pages": profile_config["pages"],
            "query": _query_body(now, limit=profile_config["page_size"]),
        }
    )
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
        detail={
            "evidence_class": "public-observed",
            "requested_records": profile_config["page_size"] * profile_config["pages"],
            "profile": profile_name,
        },
    )
    try:
        pages, raw_bytes, has_next, source_response_bytes = _fetch_profile(now, profile_config)
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=1,
            stage_id="source-request",
            label="Bounded source request",
            status="completed",
            source=source,
            input_sha256=query_sha,
            actor=actor,
            detail={
                "evidence_class": "public-observed",
                "pages_fetched": len(pages),
                "response_bytes": source_response_bytes,
                "profile": profile_name,
            },
        )
        results = [raw for page in pages for raw in (page.get("results") or [])]
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
            detail={
                "record_count": len(results),
                "pages_fetched": len(pages),
                "response_bytes": source_response_bytes,
                "evidence_class": "public-observed",
            },
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
            (str(item.get("last_modified_at") or item.get("start_date") or "") for item in records),
            default="",
        )
        accepted_at = _iso()
        duration_ms = max(0, round((time.perf_counter() - started_clock) * 1000))
        review_flags = _review_flags(records, added, changed)
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
            "profile": profile_name,
            "requested_records": profile_config["page_size"] * profile_config["pages"],
            "pages_fetched": len(pages),
            "source_response_bytes": source_response_bytes,
            "duration_ms": duration_ms,
            "added_records": len(added),
            "changed_records": len(changed),
            "unchanged_records": len(unchanged),
            "not_observed_records": len(not_observed),
            "has_more_source_pages": has_next,
            "review_flags": review_flags,
            "review_flag_count": len(review_flags),
            "record_preview": _record_preview(records),
            "raw_receipt_uri": raw_uri,
            "canonical_receipt_uri": canonical_uri,
            "evidence_class": "public-observed",
            "poll_mode": "scheduled-micro-batch",
            "scope_disclosure": (
                "Real public Department of the Navy candidate grants matched by keyword N00014 within "
                "a bounded recent window. Not an authoritative inventory of ONR activity. "
                "Records absent from the next bounded page are not treated as source deletions."
            ),
        }
        try:
            classification = _classify_award_narratives(
                run_id=run_id,
                canonical_uri=canonical_uri,
                canonical_sha256=canonical_object_sha,
                records=records,
            )
            acquisition["classification_status"] = (
                "completed" if classification else "not-configured"
            )
            if classification:
                acquisition["classification_summary"] = classification
                operational_evidence.record_stage(
                    run_id=run_id,
                    run_kind="public-acquisition",
                    sequence=5,
                    stage_id="narratives-classified",
                    label="Public award narratives classified",
                    status="completed",
                    source=canonical_uri,
                    destination=str(classification.get("artifact_uri") or "model-evidence://public-awards"),
                    input_sha256=canonical_object_sha,
                    output_sha256=str(classification.get("artifact_sha256") or "") or None,
                    actor=actor,
                    detail={
                        "record_count": classification.get("record_count"),
                        "model_version": classification.get("model_version"),
                    },
                )
        except Exception as exc:  # noqa: BLE001 - accepted source remains valid
            acquisition["classification_status"] = "degraded"
            acquisition["classification_failure_code"] = type(exc).__name__
            operational_evidence.record_stage(
                run_id=run_id,
                run_kind="public-acquisition",
                sequence=5,
                stage_id="narratives-classified",
                label="Public award narrative classification",
                status="failed",
                source=canonical_uri,
                input_sha256=canonical_object_sha,
                actor=actor,
                detail={"failure_code": type(exc).__name__},
            )
            operational_evidence.record_signal(
                category="public-narrative-classification",
                severity="high",
                title="Public narrative classification degraded",
                message="The public snapshot was accepted, but its narrative classification requires operator review.",
                run_id=run_id,
                evidence_uri=canonical_uri,
                detail={"failure_code": type(exc).__name__},
            )
        identity_summary = _index_evidence_records(
            run_id=run_id,
            source_id=SOURCE_ID,
            records=records,
            observed_at=accepted_at,
        )
        acquisition["identity_summary"] = identity_summary
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=6,
            stage_id="evidence-linked",
            label="Exact evidence identities indexed",
            status="completed",
            source=canonical_uri,
            destination="evidence-graph://public-identities",
            input_sha256=canonical_object_sha,
            actor=actor,
            detail={"record_count": identity_summary["indexed_records"]},
        )
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
            sequence=7,
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
        if review_flags:
            operational_evidence.record_signal(
                category="public-award-review",
                severity="medium",
                title="Public award review queue updated",
                message=f"{len(review_flags)} public award records matched transparent analyst review rules.",
                run_id=run_id,
                evidence_uri=canonical_uri,
                detail={"review_flag_count": len(review_flags)},
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
            "profile": profile_name,
            "duration_ms": max(0, round((time.perf_counter() - started_clock) * 1000)),
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


def run_feed_acquisition(
    source_id: str,
    *,
    actor: str = "compass-public-acquisition",
    profile: str = "standard",
) -> Dict[str, Any]:
    if source_id not in feed_sources.SOURCE_REGISTRY:
        raise ValueError(f"unknown public source: {source_id}")
    profile_name, profile_config = _profile(profile)
    spec = feed_sources.SOURCE_REGISTRY[source_id]
    now = _now()
    started_clock = time.perf_counter()
    run_id = (
        f"acq-{source_id}-{now.strftime('%Y%m%dT%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}"
    )
    source = f"public-api://{source_id}"
    query_sha = _digest(
        {
            "source_id": source_id,
            "profile": profile_name,
            "requested_records": profile_config["page_size"] * profile_config["pages"],
        }
    )
    operational_evidence.record_stage(
        run_id=run_id,
        run_kind="public-acquisition",
        sequence=1,
        stage_id="source-request",
        label=f"{spec['label']} request",
        status="running",
        source=source,
        input_sha256=query_sha,
        actor=actor,
        detail={"evidence_class": "public-observed", "profile": profile_name},
    )
    try:
        batch = feed_sources.fetch_source(source_id, profile_name, _open_json_request)
        raw_bytes = bytes(batch["raw"])
        records = []
        for raw_record in batch.get("records") or []:
            if not isinstance(raw_record, Mapping):
                continue
            record = _json_safe(dict(raw_record))
            record["record_sha256"] = _digest(record)
            records.append(record)
        if not records:
            raise AcquisitionFailure("source returned no valid records for the bounded scope")
        records.sort(key=lambda item: str(item["source_record_id"]))
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()
        snapshot_sha = _digest(records)
        prefix = f"public-intelligence/acquisitions/{source_id}/{run_id}"
        raw_uri = _put_bytes(
            f"{prefix}/raw-response.json",
            raw_bytes,
            metadata={"run-id": run_id, "stage": "raw", "sha256": raw_sha},
        )
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=1,
            stage_id="source-request",
            label=f"{spec['label']} request",
            status="completed",
            source=str(batch.get("source") or source),
            input_sha256=query_sha,
            output_sha256=raw_sha,
            actor=actor,
            detail={
                "record_count": len(records),
                "pages_fetched": int(batch.get("pages_fetched") or 1),
                "response_bytes": len(raw_bytes),
                "profile": profile_name,
                "evidence_class": "public-observed",
            },
        )
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=2,
            stage_id="raw-retained",
            label="Immutable public response retained",
            status="completed",
            source=str(batch.get("source") or source),
            destination=raw_uri,
            input_sha256=query_sha,
            output_sha256=raw_sha,
            actor=actor,
            detail={"record_count": len(records), "evidence_class": "public-observed"},
        )
        canonical_payload = _json_bytes(
            {
                "contract": "compass.public-source-records.v1",
                "source_id": source_id,
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
            detail={"accepted_records": len(records), "schema": "public-source-record-v1"},
        )
        current_hashes = {
            str(record["source_record_id"]): str(record["record_sha256"])
            for record in records
        }
        previous_alias = _get_alias(source_id) or {}
        previous_hashes = previous_alias.get("record_hashes") or {}
        added, changed, unchanged, not_observed = _diff(previous_hashes, current_hashes)
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=4,
            stage_id="change-detected",
            label="Source snapshot change detection",
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
        watermark = max(
            (
                str(
                    item.get("last_modified_at")
                    or item.get("published_date")
                    or ""
                )
                for item in records
            ),
            default="",
        )
        review_flags = _review_flags(records, added, changed)
        classification: Dict[str, Any] | None = None
        classification_status = "not-configured"
        try:
            classification = _classify_award_narratives(
                run_id=run_id,
                canonical_uri=canonical_uri,
                canonical_sha256=canonical_object_sha,
                records=records,
                source_kind=str(spec["data_kind"]),
            )
            classification_status = "completed" if classification else "not-configured"
            operational_evidence.record_stage(
                run_id=run_id,
                run_kind="public-acquisition",
                sequence=5,
                stage_id="narratives-classified",
                label="Public source narratives classified",
                status="completed" if classification else "skipped",
                source=canonical_uri,
                destination=(
                    str(classification.get("artifact_uri"))
                    if classification
                    else "model-evidence://not-configured"
                ),
                input_sha256=canonical_object_sha,
                output_sha256=(
                    str(classification.get("artifact_sha256") or "") or None
                    if classification
                    else None
                ),
                actor=actor,
                detail={
                    "record_count": len(records),
                    "model_version": classification.get("model_version") if classification else None,
                },
            )
        except Exception as exc:  # noqa: BLE001 - source snapshot remains valid
            classification_status = "degraded"
            operational_evidence.record_stage(
                run_id=run_id,
                run_kind="public-acquisition",
                sequence=5,
                stage_id="narratives-classified",
                label="Public source narrative classification",
                status="failed",
                source=canonical_uri,
                input_sha256=canonical_object_sha,
                actor=actor,
                detail={"failure_code": type(exc).__name__},
            )
        accepted_at = _iso()
        identity_summary = _index_evidence_records(
            run_id=run_id,
            source_id=source_id,
            records=records,
            observed_at=accepted_at,
        )
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=6,
            stage_id="evidence-linked",
            label="Exact evidence identities indexed",
            status="completed",
            source=canonical_uri,
            destination="evidence-graph://public-identities",
            input_sha256=canonical_object_sha,
            actor=actor,
            detail={"record_count": identity_summary["indexed_records"]},
        )
        acquisition = {
            "contract": CONTRACT,
            "run_id": run_id,
            "source_id": source_id,
            "source_label": spec["label"],
            "source": str(batch.get("source") or source),
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
            "total_available": int(batch.get("total_available") or len(records)),
            "profile": profile_name,
            "requested_records": profile_config["page_size"] * profile_config["pages"],
            "pages_fetched": int(batch.get("pages_fetched") or 1),
            "source_response_bytes": len(raw_bytes),
            "duration_ms": max(0, round((time.perf_counter() - started_clock) * 1000)),
            "added_records": len(added),
            "changed_records": len(changed),
            "unchanged_records": len(unchanged),
            "not_observed_records": len(not_observed),
            "has_more_source_pages": bool(batch.get("has_more")),
            "review_flags": review_flags,
            "review_flag_count": len(review_flags),
            "record_preview": _record_preview(records),
            "classification_status": classification_status,
            "classification_summary": classification,
            "identity_summary": identity_summary,
            "raw_receipt_uri": raw_uri,
            "canonical_receipt_uri": canonical_uri,
            "evidence_class": "public-observed",
            "poll_mode": "scheduled-micro-batch",
            "scope_disclosure": (
                f"Real public {spec['data_kind'].lower()} from {spec['authority']}. "
                "This bounded page is decision evidence, not an authoritative operational inventory."
            ),
        }
        _put_acquisition(acquisition)
        _put_alias(acquisition, current_hashes, source_id)
        operational_evidence.record_stage(
            run_id=run_id,
            run_kind="public-acquisition",
            sequence=7,
            stage_id="accepted-snapshot",
            label="Accepted public evidence snapshot",
            status="completed",
            source=canonical_uri,
            destination="mission-workspace://multi-source-intelligence",
            source_sha256=snapshot_sha,
            actor=actor,
            detail={"accepted_records": len(records), "consumer": "Multi-source intelligence"},
        )
        if added or changed or review_flags:
            operational_evidence.record_signal(
                category="multi-source-acquisition",
                severity="medium" if review_flags else "info",
                title=f"{spec['label']} acquisition completed",
                message=(
                    f"Accepted {len(records)} public records with {len(added)} added, "
                    f"{len(changed)} changed, and {len(review_flags)} review flags."
                ),
                run_id=run_id,
                evidence_uri=canonical_uri,
                detail={
                    "record_count": len(records),
                    "added_records": len(added),
                    "changed_records": len(changed),
                },
            )
        _publish_stream(acquisition, records, added, changed)
        return acquisition
    except Exception as exc:
        failure = {
            "contract": CONTRACT,
            "run_id": run_id,
            "source_id": source_id,
            "source_label": spec["label"],
            "source": source,
            "status": "failed",
            "stage": "source-acquisition",
            "started_at": _iso(now),
            "updated_at": _iso(),
            "profile": profile_name,
            "duration_ms": max(0, round((time.perf_counter() - started_clock) * 1000)),
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
            detail={"failure_code": type(exc).__name__},
        )
        operational_evidence.record_signal(
            category="multi-source-acquisition",
            severity="high",
            title=f"{spec['label']} acquisition failed",
            message="No new source snapshot was accepted. The previous accepted snapshot remains active.",
            run_id=run_id,
            detail={"failure_code": type(exc).__name__},
        )
        raise AcquisitionFailure("public source acquisition did not complete") from exc


def _source_health(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = _now()
    registry = {
        SOURCE_ID: {
            "label": "USAspending ONR candidate awards",
            "authority": "USAspending.gov",
            "endpoint": ENDPOINT,
            "cadence_seconds": 300,
            "data_kind": "Public award records and descriptions",
            "model_use": "Narrative routing, change detection, and review flags",
        },
        **feed_sources.SOURCE_REGISTRY,
    }
    health = []
    for source_id, spec in registry.items():
        attempts = [item for item in records if item.get("source_id") == source_id]
        latest = attempts[0] if attempts else None
        accepted = next((item for item in attempts if item.get("status") == "completed"), None)
        completed = sum(1 for item in attempts if item.get("status") == "completed")
        durations = [float(item.get("duration_ms") or 0) for item in attempts if item.get("duration_ms") is not None]
        last_at = str((latest or {}).get("updated_at") or "")
        try:
            age_seconds = max(0, int((now - datetime.fromisoformat(last_at.replace("Z", "+00:00"))).total_seconds()))
        except (TypeError, ValueError):
            age_seconds = None
        cadence = int(spec["cadence_seconds"])
        health.append(
            {
                "source_id": source_id,
                **spec,
                "status": (
                    "awaiting-first-run"
                    if latest is None
                    else "failed"
                    if latest.get("status") == "failed"
                    else "stale"
                    if age_seconds is not None and age_seconds > cadence * 2
                    else "healthy"
                ),
                "last_attempt_at": last_at or None,
                "last_accepted_at": (accepted or {}).get("updated_at"),
                "age_seconds": age_seconds,
                "success_rate": round(completed / len(attempts), 4) if attempts else None,
                "average_duration_ms": round(sum(durations) / len(durations)) if durations else None,
                "latest_run_id": (latest or {}).get("run_id"),
                "latest_record_count": (accepted or {}).get("record_count"),
                "latest_added_records": (accepted or {}).get("added_records"),
                "latest_changed_records": (accepted or {}).get("changed_records"),
                "latest_review_flag_count": (accepted or {}).get("review_flag_count"),
                "classification_status": (accepted or {}).get("classification_status"),
                "model_version": ((accepted or {}).get("classification_summary") or {}).get("model_version"),
                "has_more_source_pages": bool((accepted or {}).get("has_more_source_pages")),
            }
        )
    return health


_LINK_STOP_WORDS = {
    "agency",
    "award",
    "based",
    "both",
    "department",
    "federal",
    "from",
    "funded",
    "funder",
    "naval",
    "navy",
    "office",
    "opportunity",
    "program",
    "project",
    "public",
    "research",
    "that",
    "these",
    "this",
    "through",
    "using",
    "will",
    "with",
}


def _link_tokens(record: Mapping[str, Any]) -> set[str]:
    values = [
        record.get("title"),
        record.get("description"),
        record.get("recipient_name"),
        *(record.get("organizations") or []),
        *(record.get("topics") or []),
    ]
    text = " ".join(str(value or "") for value in values)
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text)
        if token.lower() not in _LINK_STOP_WORDS
    }


def _thread_fact(
    run: Mapping[str, Any],
    record: Mapping[str, Any],
) -> Dict[str, Any]:
    prediction = next(
        (
            item
            for item in ((run.get("classification_summary") or {}).get("preview") or [])
            if item.get("source_record_id") == record.get("source_record_id")
        ),
        None,
    )
    return {
        "source_id": run.get("source_id"),
        "source_label": run.get("source_label") or run.get("source_id"),
        "run_id": run.get("run_id"),
        "record_id": record.get("source_record_id"),
        "record_type": record.get("record_type") or "record",
        "title": record.get("title")
        or str(record.get("description") or "")[:160]
        or record.get("source_record_id"),
        "source_url": record.get("source_url"),
        "document_url": record.get("document_url"),
        "model_version": (run.get("classification_summary") or {}).get("model_version"),
        "document_class": (prediction or {}).get("document_class"),
    }


def _build_evidence_threads(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for run in records:
        source_id = str(run.get("source_id") or "")
        if run.get("status") == "completed" and source_id and source_id not in latest:
            latest[source_id] = run

    indexed: List[tuple[Dict[str, Any], Dict[str, Any], set[str]]] = []
    exact: Dict[str, List[Dict[str, Any]]] = {}
    for run in latest.values():
        for record in run.get("record_preview") or []:
            fact = _thread_fact(run, record)
            indexed.append((run, record, _link_tokens(record)))
            for identity in record.get("identity_keys") or []:
                if str(identity).startswith(("AWARD#", "DOI#")):
                    exact.setdefault(str(identity), []).append(fact)

    threads: List[Dict[str, Any]] = []
    exact_record_pairs: set[tuple[str, str]] = set()
    for key, facts in exact.items():
        if len({fact["source_id"] for fact in facts}) < 2:
            continue
        for left_index, left in enumerate(facts):
            for right in facts[left_index + 1 :]:
                exact_record_pairs.add(
                    tuple(sorted((str(left["record_id"]), str(right["record_id"]))))
                )
        threads.append(
            {
                "thread_id": f"exact-{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                "match_type": "exact-identity",
                "identity_key": key,
                "match_score": 1.0,
                "review_status": "verified-key",
                "explanation": "Two accepted source records carry the same exact governed identity key.",
                "shared_terms": [],
                "owner": "Portfolio Data Product Owner",
                "steward": "Public Evidence Data Steward",
                "facts": facts,
            }
        )

    candidates: List[Dict[str, Any]] = []
    for index, (left_run, left_record, left_tokens) in enumerate(indexed):
        for right_run, right_record, right_tokens in indexed[index + 1 :]:
            if left_run.get("source_id") == right_run.get("source_id"):
                continue
            record_pair = tuple(
                sorted(
                    (
                        str(left_record.get("source_record_id") or ""),
                        str(right_record.get("source_record_id") or ""),
                    )
                )
            )
            if record_pair in exact_record_pairs:
                continue
            shared = sorted(left_tokens & right_tokens)
            if len(shared) < 3:
                continue
            overlap = len(shared) / max(1, min(len(left_tokens), len(right_tokens)))
            if overlap < 0.18:
                continue
            stable_pair = "|".join(
                sorted(
                    (
                        f"{left_run.get('source_id')}:{left_record.get('source_record_id')}",
                        f"{right_run.get('source_id')}:{right_record.get('source_record_id')}",
                    )
                )
            )
            candidates.append(
                {
                    "thread_id": f"candidate-{hashlib.sha256(stable_pair.encode()).hexdigest()[:12]}",
                    "match_type": "explainable-candidate",
                    "identity_key": None,
                    "match_score": round(overlap, 4),
                    "review_status": "analyst-review",
                    "explanation": (
                        "The records share specific normalized terms. This is a candidate relationship, "
                        "not a verified identity match."
                    ),
                    "shared_terms": shared[:8],
                    "owner": "Portfolio Data Product Owner",
                    "steward": "Public Evidence Data Steward",
                    "facts": [
                        _thread_fact(left_run, left_record),
                        _thread_fact(right_run, right_record),
                    ],
                }
            )

    candidates.sort(
        key=lambda item: (item["match_score"], len(item["shared_terms"])),
        reverse=True,
    )
    threads.extend(candidates[:12])
    threads.sort(
        key=lambda item: (
            item["match_type"] == "exact-identity",
            item["match_score"],
        ),
        reverse=True,
    )
    return threads[:16]


def list_acquisitions(limit: int = 50) -> Dict[str, Any]:
    from boto3.dynamodb.conditions import Key

    response = _table().query(
        IndexName="by-type",
        KeyConditionExpression=Key("gsi1pk").eq("ACQUISITION"),
        ScanIndexForward=False,
        Limit=max(1, min(100, limit)),
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
        "source_transport": "source-specific bounded HTTPS polling, then accepted Kinesis change events",
        "display_refresh": "one-second operational projection",
        "source_health": _source_health(records),
        "evidence_threads": _build_evidence_threads(records),
        "acquisitions": records,
    }


def _poweruser(event: Mapping[str, Any]):
    claims = http.get_claims(dict(event))
    return claims, claims.is_authenticated and claims.role == "poweruser" and claims.is_corporate


def handler(event, context=None):
    event = event or {}
    if event.get("action") == "poll":
        return run_acquisition(profile=str(event.get("profile") or "standard"))
    if event.get("action") == "poll_source":
        return run_feed_acquisition(
            str(event.get("source_id") or ""),
            profile=str(event.get("profile") or "standard"),
        )
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
            body = http.parse_body(dict(event))
            return http.created(
                run_acquisition(actor=actor, profile=str(body.get("profile") or "standard"))
            )
        except ValueError as exc:
            return http.bad_request(str(exc))
        except AcquisitionFailure:
            return http.error_response(
                502,
                "the public source poll failed; the previous accepted snapshot remains active",
            )
    source_match = re.search(r"/public-intelligence/sources/([^/]+)/run$", path)
    if method == "POST" and source_match:
        actor = claims.username or claims.email or claims.sub or "poweruser"
        try:
            body = http.parse_body(dict(event))
            return http.created(
                run_feed_acquisition(
                    source_match.group(1),
                    actor=actor,
                    profile=str(body.get("profile") or "standard"),
                )
            )
        except ValueError as exc:
            return http.bad_request(str(exc))
        except AcquisitionFailure:
            return http.error_response(
                502,
                "the public source poll failed; the previous accepted snapshot remains active",
            )
    return http.not_found("unknown public acquisition route")

"""Build an authentic, leakage-bounded SBIR Phase I transition dataset."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import DATASET_CONTRACT, ROW_CONTRACT, digest_json


SOURCE_URI = "artifact://private/public-intelligence/canonical/sbir-navy.jsonl.gz"
PHASE_RE = re.compile(r"\bphase\s+(?:i{1,3}|1|2|3)\b", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _add_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(absolute, 12)
    month = month_index + 1
    days = (31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    return date(year, month, min(value.day, days[month - 1]))


def _phase(record: Mapping[str, Any]) -> str | None:
    for topic in record.get("topics") or []:
        if topic in {"Phase I", "Phase II", "Phase III"}:
            return str(topic)
    return None


def _organization(record: Mapping[str, Any]) -> str:
    values = record.get("organizations") or []
    return SPACE_RE.sub(" ", str(values[0] if values else "")).strip().upper()


def _topic_code(record: Mapping[str, Any]) -> str:
    identifiers = record.get("identifiers") or {}
    return SPACE_RE.sub("", str(identifiers.get("topic_code") or "")).upper()


def _public_text(record: Mapping[str, Any]) -> str:
    value = f"{record.get('title') or ''}. {record.get('abstract') or ''}"
    value = PHASE_RE.sub("phase", value)
    return SPACE_RE.sub(" ", value).strip()[:12_000]


def _iter_records(path: Path) -> Iterable[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_sbir_transition_records(
    source_path: Path,
    *,
    as_of_date: date,
    horizon_months: int = 36,
    source_uri: str = SOURCE_URI,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if horizon_months not in {24, 36}:
        raise ValueError("horizon_months must be 24 or 36")
    artifact_sha256 = _file_sha256(source_path)
    source_records = list(_iter_records(source_path))
    deduplicated: dict[str, dict[str, Any]] = {}
    for record in sorted(
        source_records,
        key=lambda value: (
            str(value.get("source_record_id") or ""),
            str((value.get("provenance") or {}).get("record_sha256") or ""),
        ),
    ):
        identifier = str(record.get("source_record_id") or "").strip()
        if identifier:
            deduplicated.setdefault(identifier, record)
    records = list(deduplicated.values())
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        organization = _organization(record)
        topic_code = _topic_code(record)
        event_date = _parse_date(record.get("start_date"))
        phase = _phase(record)
        if organization and topic_code and event_date and phase:
            groups[(organization, topic_code)].append(record)

    candidates: list[dict[str, Any]] = []
    for (organization, topic_code), items in groups.items():
        phase_i = sorted(
            (record for record in items if _phase(record) == "Phase I"),
            key=lambda record: (_parse_date(record.get("start_date")) or date.max, str(record.get("source_record_id") or "")),
        )
        if not phase_i:
            continue
        phase_i_record = phase_i[0]
        event_date = _parse_date(phase_i_record.get("start_date"))
        assert event_date is not None
        horizon_end = _add_months(event_date, horizon_months)
        if horizon_end > as_of_date:
            continue
        follow_ons = sorted(
            (
                record
                for record in items
                if _phase(record) in {"Phase II", "Phase III"}
                and (follow_on_date := _parse_date(record.get("start_date"))) is not None
                and event_date < follow_on_date <= horizon_end
            ),
            key=lambda record: (_parse_date(record.get("start_date")) or date.max, str(record.get("source_record_id") or "")),
        )
        follow_on = follow_ons[0] if follow_ons else None
        label_date = _parse_date(follow_on.get("start_date")) if follow_on else horizon_end
        assert label_date is not None
        event_time = datetime.combine(event_date, datetime.min.time(), tzinfo=timezone.utc)
        observed_time = datetime.combine(label_date, datetime.max.time(), tzinfo=timezone.utc)
        phase_i_id = str(phase_i_record.get("source_record_id") or "")
        record_sha = str((phase_i_record.get("provenance") or {}).get("record_sha256") or "")
        if len(record_sha) != 64:
            record_sha = digest_json(phase_i_record)
        amount_raw = phase_i_record.get("funding_amount")
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            amount = None
        text = _public_text(phase_i_record)
        features = {
            "phase_i_amount_usd": amount,
            "title_character_count": len(str(phase_i_record.get("title") or "")),
            "abstract_character_count": len(str(phase_i_record.get("abstract") or "")),
            "abstract_token_count": len(str(phase_i_record.get("abstract") or "").split()),
            "award_year": event_date.year,
            "topic_family": topic_code.split("-", 1)[0][:4] or "UNKNOWN",
            "public_text": text,
        }
        feature_lineage = [
            {
                "feature": feature,
                "source_record_ids": [phase_i_id],
                "max_available_at": _iso(event_time),
                "evidence_class": "public_observed",
            }
            for feature, value in features.items()
            if value is not None
        ]
        group_hash = hashlib.sha256(f"{organization}|{topic_code}".encode("utf-8")).hexdigest()
        follow_on_id = str(follow_on.get("source_record_id") or "") if follow_on else None
        candidates.append(
            {
                "record_type": "training_row",
                "contract": ROW_CONTRACT,
                "record_id": f"sbir-transition-{phase_i_id}",
                "event_time": _iso(event_time),
                "group_id": f"org-topic-{group_hash[:24]}",
                "features": features,
                "feature_lineage": feature_lineage,
                "label": {
                    "name": "sbir_transition_observed",
                    "status": "observed",
                    "value": int(follow_on is not None),
                    "authentic": True,
                    "source_uri": source_uri,
                    "source_record_ids": [follow_on_id] if follow_on_id else [],
                    "observed_at": _iso(observed_time),
                },
                "subgroups": {},
                "provenance": {
                    "evidence_set_id": f"sbir-navy-{artifact_sha256[:16]}",
                    "source_uri": source_uri,
                    "source_sha256": record_sha,
                    "authorized_for_training": True,
                    "rights": "public",
                    "pii_minimized": True,
                    "protected_features_excluded": True,
                    "test_fixture": False,
                },
            }
        )
    candidates.sort(key=lambda row: (row["event_time"], row["record_id"]))
    as_of_time = datetime.combine(as_of_date, datetime.max.time(), tzinfo=timezone.utc)
    manifest = {
        "record_type": "manifest",
        "contract": DATASET_CONTRACT,
        "model_kind": "sbir_transition",
        "dataset_id": "navy-sbir-phase-i-public-transition",
        "dataset_version": f"{as_of_date.isoformat()}-{artifact_sha256[:16]}",
        "created_at": _iso(as_of_time),
        "as_of_time": _iso(as_of_time),
        "evidence_set": {
            "kind": "public",
            "snapshot_id": f"sbir-navy-{artifact_sha256[:16]}",
            "as_of_at": _iso(as_of_time),
            "manifest_sha256": artifact_sha256,
        },
        "target": {
            "name": "sbir_transition_observed",
            "definition": f"A later public Navy SBIR Phase II or Phase III record for the same organization and topic within {horizon_months} months of its earliest Phase I record.",
            "authenticity_required": True,
        },
        "feature_schema": {
            "numeric": [
                "phase_i_amount_usd",
                "title_character_count",
                "abstract_character_count",
                "abstract_token_count",
                "award_year",
            ],
            "categorical": ["topic_family"],
            "text_field": "public_text",
        },
        "leakage_prohibited_features": [
            "phase_ii_award_id",
            "follow_on_date",
            "future_funding_amount",
        ],
        "subgroup_fields": [],
        "minimum_subgroup_size": 10,
        "outcome_horizon_months": horizon_months,
        "linkage_rule": "exact normalized organization plus exact topic code",
        "cohort_rule": "earliest eligible Phase I per organization-topic group",
        "text_safety": "Phase-number tokens are removed from model text before training.",
        "test_fixture": False,
    }
    positives = sum(int(row["label"]["value"]) for row in candidates)
    return [manifest, *candidates], {
        "source_records": len(source_records),
        "deduplicated_source_records": len(records),
        "eligible_rows": len(candidates),
        "positive_rows": positives,
        "negative_rows": len(candidates) - positives,
        "positive_rate": positives / len(candidates) if candidates else 0.0,
        "artifact_sha256": artifact_sha256,
        "horizon_months": horizon_months,
    }


def write_sbir_transition_jsonl(records: list[dict[str, Any]], output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")

#!/usr/bin/env python3
"""Prepare current public Navy SBIR Phase I records for governed scoring.

The output contains only features available at the Phase I event time. It
excludes outcome labels, follow-on awards, contact details, and protected
attributes. Records must occur after the training and evaluation cutoff so a
live scoring run is distinct from training-cohort execution proof.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CONTRACT = "compass.public-intelligence.inference-candidates.v1"
PHASE_PATTERN = re.compile(r"\bphase\s+(?:i{1,3}|1|2|3)\b", re.IGNORECASE)
SPACE_PATTERN = re.compile(r"\s+")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _iter_records(path: Path) -> Iterable[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                yield value


def _clean_text(value: Any) -> str:
    return SPACE_PATTERN.sub(
        " ", str(value or "").replace("\u2014", " - ").replace("\u2013", "-")
    ).strip()


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _phase(record: Mapping[str, Any]) -> str | None:
    for topic in record.get("topics") or []:
        if topic in {"Phase I", "Phase II", "Phase III"}:
            return str(topic)
    return None


def _organization(record: Mapping[str, Any]) -> str:
    organizations = record.get("organizations") or []
    return _clean_text(organizations[0] if organizations else "").upper()


def _topic_code(record: Mapping[str, Any]) -> str:
    identifiers = record.get("identifiers") or {}
    return _clean_text(identifiers.get("topic_code")).replace(" ", "").upper()


def _public_text(record: Mapping[str, Any]) -> str:
    value = f"{record.get('title') or ''}. {record.get('abstract') or ''}"
    return _clean_text(PHASE_PATTERN.sub("phase", value))[:12_000]


def _iso(value: date) -> str:
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def prepare_pool(
    source: Path,
    *,
    cutoff: date,
    as_of: date,
    limit: int,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    if cutoff >= as_of:
        raise ValueError("cutoff must be before as_of")

    source_sha256 = _file_sha256(source)
    deduplicated: dict[str, dict[str, Any]] = {}
    for record in sorted(
        _iter_records(source),
        key=lambda item: (
            str(item.get("source_record_id") or ""),
            str((item.get("provenance") or {}).get("record_sha256") or ""),
        ),
    ):
        source_id = _clean_text(record.get("source_record_id"))
        if source_id:
            deduplicated.setdefault(source_id, record)

    eligible: list[tuple[date, str, dict[str, Any]]] = []
    group_seen: set[tuple[str, str]] = set()
    for record in sorted(
        deduplicated.values(),
        key=lambda item: (
            _parse_date(item.get("start_date")) or date.max,
            str(item.get("source_record_id") or ""),
        ),
    ):
        event_date = _parse_date(record.get("start_date"))
        organization = _organization(record)
        topic_code = _topic_code(record)
        if (
            _phase(record) != "Phase I"
            or event_date is None
            or event_date <= cutoff
            or event_date > as_of
            or not organization
            or not topic_code
        ):
            continue
        group = (organization, topic_code)
        if group in group_seen:
            continue
        group_seen.add(group)

        source_id = _clean_text(record.get("source_record_id"))
        title = _clean_text(record.get("title"))
        abstract = _clean_text(record.get("abstract"))
        public_text = _public_text(record)
        if not source_id or not public_text or EMAIL_PATTERN.search(public_text):
            continue
        try:
            amount = float(record.get("funding_amount"))
        except (TypeError, ValueError):
            continue
        eligible.append(
            (
                event_date,
                source_id,
                {
                    "eventTime": _iso(event_date),
                    "recordId": f"sbir-transition-{source_id}",
                    "sourceRecordIds": [source_id],
                    "features": {
                        "phase_i_amount_usd": amount,
                        "title_character_count": len(title),
                        "abstract_character_count": len(abstract),
                        "abstract_token_count": len(abstract.split()),
                        "award_year": event_date.year,
                        "topic_family": topic_code.split("-", 1)[0][:4] or "UNKNOWN",
                        "public_text": public_text,
                    },
                },
            )
        )

    if len(eligible) < limit:
        raise ValueError("source does not contain enough current Phase I scoring records")
    selected = [item[2] for item in sorted(eligible, reverse=True)[:limit]]
    selected.sort(key=lambda item: str(item["recordId"]))
    snapshots = sorted(
        {
            _clean_text((record.get("provenance") or {}).get("snapshot_id"))
            for record in deduplicated.values()
            if _clean_text((record.get("provenance") or {}).get("snapshot_id"))
        }
    )
    return {
        "contract": CONTRACT,
        "version": 1,
        "createdAt": _iso(as_of),
        "dataBoundary": {
            "classification": "public",
            "containsCui": False,
            "piiMinimized": True,
            "labelsExcluded": True,
        },
        "modelKind": "sbir_transition",
        "sourceDataset": {
            "datasetId": "navy-sbir-current-phase-i-public-scoring",
            "datasetVersion": f"{as_of.isoformat()}-{source_sha256[:16]}",
            "sha256": source_sha256,
            "snapshotId": snapshots[-1] if snapshots else f"sbir-navy-{source_sha256[:16]}",
        },
        "selection": {
            "rule": "newest eligible public Phase I record per normalized organization and topic after the model evaluation cutoff",
            "cutoffExclusive": cutoff.isoformat(),
            "asOfInclusive": as_of.isoformat(),
            "recordCount": len(selected),
        },
        "records": selected,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date(2023, 12, 31))
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--limit", type=int, default=25)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pool = prepare_pool(
        args.source.resolve(),
        cutoff=args.cutoff,
        as_of=args.as_of,
        limit=args.limit,
    )
    encoded = json.dumps(pool, separators=(",", ":"), sort_keys=True).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(
        json.dumps(
            {
                "contract": CONTRACT,
                "recordCount": len(pool["records"]),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "sourceDatasetSha256": pool["sourceDataset"]["sha256"],
                "cutoffExclusive": pool["selection"]["cutoffExclusive"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

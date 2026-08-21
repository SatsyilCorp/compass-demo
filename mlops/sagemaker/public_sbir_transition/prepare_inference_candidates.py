#!/usr/bin/env python3
"""Prepare a bounded, PII-minimized public SBIR inference candidate pool.

The source is the exact canonical training dataset. Labels and post-event
features are intentionally omitted from the output so scoring cannot receive
future outcome information. The newest eligible rows are selected
deterministically and the resulting object is small enough for a Lambda to
verify before starting one bounded SageMaker Batch Transform validation run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


CONTRACT = "compass.public-intelligence.inference-candidates.v1"
REQUIRED_FEATURES = (
    "phase_i_amount_usd",
    "title_character_count",
    "abstract_character_count",
    "abstract_token_count",
    "award_year",
    "topic_family",
    "public_text",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean_text(value: Any) -> str:
    return " ".join(
        str(value or "").replace("\u2014", " - ").replace("\u2013", "-").split()
    )


def prepare_pool(dataset: Path, *, limit: int) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    rows: list[dict[str, Any]] = []
    manifest: dict[str, Any] | None = None
    with dataset.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} must be a JSON object")
            if value.get("record_type") == "manifest":
                if manifest is not None:
                    raise ValueError("dataset contains more than one manifest")
                manifest = value
                continue
            if value.get("record_type") != "training_row":
                continue
            features = value.get("features")
            if not isinstance(features, dict):
                raise ValueError(f"line {line_number} has no feature object")
            missing = [name for name in REQUIRED_FEATURES if name not in features]
            if missing:
                raise ValueError(
                    f"line {line_number} is missing features: {', '.join(missing)}"
                )
            event_time = _clean_text(value.get("event_time"))
            if not event_time:
                raise ValueError(f"line {line_number} has no event_time")
            rows.append(
                {
                    "eventTime": event_time,
                    "recordId": _clean_text(value.get("record_id")),
                    "sourceRecordIds": sorted(
                        {
                            _clean_text(source_id)
                            for lineage in value.get("feature_lineage") or []
                            if isinstance(lineage, dict)
                            for source_id in lineage.get("source_record_ids") or []
                            if _clean_text(source_id)
                        }
                    ),
                    "features": {
                        "phase_i_amount_usd": float(features["phase_i_amount_usd"]),
                        "title_character_count": int(features["title_character_count"]),
                        "abstract_character_count": int(features["abstract_character_count"]),
                        "abstract_token_count": int(features["abstract_token_count"]),
                        "award_year": int(features["award_year"]),
                        "topic_family": _clean_text(features["topic_family"]),
                        "public_text": _clean_text(features["public_text"]),
                    },
                }
            )
    if manifest is None:
        raise ValueError("dataset manifest is missing")
    if manifest.get("model_kind") != "sbir_transition":
        raise ValueError("dataset is not the SBIR transition contract")
    if len(rows) < limit:
        raise ValueError("dataset does not contain enough inference candidates")

    selected = sorted(
        rows,
        key=lambda row: (str(row["eventTime"]), str(row["recordId"])),
        reverse=True,
    )[:limit]
    selected.sort(key=lambda row: str(row["recordId"]))
    return {
        "contract": CONTRACT,
        "version": 1,
        "createdAt": _clean_text(manifest.get("as_of_time")),
        "dataBoundary": {
            "classification": "public",
            "containsCui": False,
            "piiMinimized": True,
            "labelsExcluded": True,
        },
        "modelKind": "sbir_transition",
        "sourceDataset": {
            "datasetId": _clean_text(manifest.get("dataset_id")),
            "datasetVersion": _clean_text(manifest.get("dataset_version")),
            "sha256": _sha256(dataset),
            "snapshotId": _clean_text(
                (manifest.get("evidence_set") or {}).get("snapshot_id")
            ),
        },
        "selection": {
            "rule": "newest eligible public Phase I cohorts, deterministic by event time and record ID",
            "recordCount": len(selected),
        },
        "records": selected,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=25)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    pool = prepare_pool(args.dataset.resolve(), limit=args.limit)
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
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

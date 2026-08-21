from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("prepare_current_scoring_candidates.py")
SPEC = importlib.util.spec_from_file_location(
    "compass_prepare_current_scoring_candidates", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
prepare_pool = MODULE.prepare_pool


def record(identifier: str, *, start: str, phase: str = "Phase I", topic: str = "N241-001"):
    return {
        "abstract": f"Public abstract for {identifier} with enough current research detail",
        "funding_amount": "139000",
        "identifiers": {"topic_code": topic},
        "organizations": [f"Organization {identifier}"],
        "provenance": {"record_sha256": identifier[0] * 64, "snapshot_id": "snapshot-current"},
        "source_record_id": identifier,
        "start_date": start,
        "title": f"Current {phase} research {identifier}",
        "topics": ["SBIR", phase, topic],
    }


def write_source(path, values):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for value in values:
            stream.write(json.dumps(value) + "\n")


def test_prepares_label_free_current_phase_i_pool(tmp_path):
    source = tmp_path / "sbir.jsonl.gz"
    write_source(
        source,
        [
            record("old", start="2023-12-31"),
            record("phase-two", start="2025-01-01", phase="Phase II"),
            record("new-a", start="2025-04-01"),
            record("new-b", start="2026-01-15", topic="N252-114"),
        ],
    )

    pool = prepare_pool(
        source,
        cutoff=date(2023, 12, 31),
        as_of=date(2026, 8, 12),
        limit=2,
    )

    assert pool["dataBoundary"]["labelsExcluded"] is True
    assert pool["selection"]["cutoffExclusive"] == "2023-12-31"
    assert {row["sourceRecordIds"][0] for row in pool["records"]} == {"new-a", "new-b"}
    assert all("label" not in row for row in pool["records"])
    assert all("phase i" not in row["features"]["public_text"].lower() for row in pool["records"])


def test_refuses_an_undersized_current_pool(tmp_path):
    source = tmp_path / "sbir.jsonl.gz"
    write_source(source, [record("old", start="2023-01-01")])

    with pytest.raises(ValueError, match="enough current"):
        prepare_pool(
            source,
            cutoff=date(2023, 12, 31),
            as_of=date(2026, 8, 12),
            limit=1,
        )

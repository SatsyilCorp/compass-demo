from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).with_name("prepare_inference_candidates.py")
SPEC = importlib.util.spec_from_file_location(
    "compass_prepare_inference_candidates", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
CONTRACT = MODULE.CONTRACT
prepare_pool = MODULE.prepare_pool


def _dataset(path: Path) -> Path:
    manifest = {
        "record_type": "manifest",
        "model_kind": "sbir_transition",
        "dataset_id": "public-sbir",
        "dataset_version": "v1",
        "as_of_time": "2026-08-12T00:00:00Z",
        "evidence_set": {"snapshot_id": "snapshot-1"},
    }
    rows = []
    for index in range(3):
        rows.append(
            {
                "record_type": "training_row",
                "record_id": f"record-{index}",
                "event_time": f"202{index}-01-01T00:00:00Z",
                "features": {
                    "phase_i_amount_usd": 100000,
                    "title_character_count": 20,
                    "abstract_character_count": 200,
                    "abstract_token_count": 30,
                    "award_year": 2020 + index,
                    "topic_family": "N20",
                    "public_text": "Public research text",
                },
                "label": {"value": index % 2},
                "feature_lineage": [
                    {"source_record_ids": [f"source-{index}"]}
                ],
            }
        )
    path.write_text(
        "\n".join(json.dumps(value) for value in [manifest, *rows]) + "\n",
        encoding="utf-8",
    )
    return path


def test_prepare_pool_is_deterministic_bounded_and_excludes_labels(tmp_path):
    dataset = _dataset(tmp_path / "dataset.jsonl")
    pool = prepare_pool(dataset, limit=2)

    assert pool["contract"] == CONTRACT
    assert pool["selection"]["recordCount"] == 2
    assert {record["recordId"] for record in pool["records"]} == {
        "record-1",
        "record-2",
    }
    assert pool["dataBoundary"]["labelsExcluded"] is True
    assert all("label" not in record for record in pool["records"])
    assert all("label" not in record["features"] for record in pool["records"])


def test_prepare_pool_rejects_missing_features(tmp_path):
    dataset = _dataset(tmp_path / "dataset.jsonl")
    values = [json.loads(line) for line in dataset.read_text().splitlines()]
    del values[1]["features"]["public_text"]
    dataset.write_text("\n".join(json.dumps(value) for value in values) + "\n")

    with pytest.raises(ValueError, match="missing features"):
        prepare_pool(dataset, limit=1)

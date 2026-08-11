from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_stig_controls import DEFAULT_MAPPING, validate_mapping


def test_source_backed_stig_evidence_index_is_complete():
    receipt = validate_mapping()

    assert receipt["status"] == "passed"
    assert receipt["controls"] >= 8
    assert receipt["evidence_pointers"] >= receipt["controls"]
    assert receipt["accreditation_claimed"] is False


def test_validator_refuses_an_accreditation_claim(tmp_path: Path):
    mapping = json.loads(DEFAULT_MAPPING.read_text(encoding="utf-8"))
    mapping["disclaimer"] = "Certified production system"
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")

    with pytest.raises(ValueError, match="non-accreditation disclaimer"):
        validate_mapping(path)

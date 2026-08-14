from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DEFINITION = ROOT / "statemachines" / "document_ml.asl.yaml"


def _state_block(name: str) -> str:
    source = DEFINITION.read_text(encoding="utf-8")
    match = re.search(
        rf"^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [A-Za-z][A-Za-z0-9]*:\n|\Z)",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"state {name} was not found"
    return match.group("body")


def test_document_workflow_propagates_evidence_class_to_every_terminal_path():
    for state in ("Quality", "Curate", "Quarantine"):
        assert "evidence_class.$: $.evidence_class" in _state_block(state)

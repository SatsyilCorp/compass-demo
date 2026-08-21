from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_NAMES = (
    "technical-report.txt",
    "grant-abstract.json",
    "financial-execution.csv",
    "patent-summary.md",
    "investment-brief.txt",
    "publication-summary.json",
    "quarantine-short.txt",
)


@pytest.mark.parametrize("name", DOCUMENT_NAMES)
def test_public_document_sample_matches_source_seed(name: str) -> None:
    source = ROOT / "seed" / "documents" / name
    public = ROOT / "frontend" / "public" / "demo-documents" / name

    assert public.read_bytes() == source.read_bytes()

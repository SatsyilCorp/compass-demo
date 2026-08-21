import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DOC = ROOT / "docs" / "PUBLIC_ONR_INTELLIGENCE.md"
PACKAGE_README = ROOT / "public_intelligence" / "README.md"
WORKSPACE = ROOT / "frontend" / "components" / "public-intelligence" / "intelligence-workspace.tsx"

EXPECTED_COUNTS = {
    "USAspending": 20_776,
    "SBA SBIR and STTR": 27_887,
    "Grants.gov": 286,
    "SAM.gov Opportunities": 5,
    "DataCite": 498,
    "Crossref": 48_747,
    "OpenAlex": 68_912,
    "PubMed": 1_595,
    "OSTI.GOV": 3_010,
    "USPTO ODP PatentsView": 5_388,
    "Federal Register": 91,
    "Official ONR website": 308,
}


def test_public_corpus_and_serving_projection_are_not_conflated():
    public_doc = PUBLIC_DOC.read_text(encoding="utf-8")
    package_readme = PACKAGE_README.read_text(encoding="utf-8")
    workspace = WORKSPACE.read_text(encoding="utf-8")
    normalized_doc = " ".join(public_doc.split())

    assert len(EXPECTED_COUNTS) == 12
    assert sum(EXPECTED_COUNTS.values()) == 177_503
    assert "177,503 minimized canonical records across 12 persisted public source families" in normalized_doc
    assert "1,096-record source sample plus two model-evidence records" in normalized_doc
    assert "for 1,098 indexed records" in normalized_doc
    assert "query-optimized sample size, not the corpus size" in normalized_doc

    for source_name, count in EXPECTED_COUNTS.items():
        row = rf"\| {re.escape(source_name)} \| {count:,}(?:\s|`)"
        assert re.search(row, public_doc), source_name

    assert "177,503 minimized canonical" in package_readme
    assert "12 persisted public source families" in package_readme
    assert "bounded sample" in package_readme
    assert "bounded serving projection records" in workspace
    assert "Accepted public corpus:" in workspace
    assert "formatExactCount(source.recordCount)" in workspace

    audited = "\n".join((public_doc, package_readme, workspace))
    assert "1,297" not in audited
    assert "1,097" not in audited
    assert "\u2014" not in audited

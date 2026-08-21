from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "src" / "functions" / "catalog" / "app.py"
TYPES = ROOT / "frontend" / "lib" / "types.ts"
PANEL = ROOT / "frontend" / "components" / "catalog" / "quality-panel.tsx"


def test_catalog_contract_distinguishes_owner_steward_and_dictionary() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    types = TYPES.read_text(encoding="utf-8")
    panel = PANEL.read_text(encoding="utf-8")

    assert '"owner": "Portfolio Data Product Owner (demo role)"' in backend
    assert '"steward": "Data Quality Steward (demo role)"' in backend
    assert '"data_dictionary": DATA_DICTIONARY' in backend
    assert "steward: string" in types
    assert "data_dictionary: CatalogFieldDefinition[]" in types
    assert "Business owner" in panel
    assert "Data steward" in panel
    assert "Open governed data dictionary" in panel


def test_catalog_governance_copy_has_no_em_dash() -> None:
    audited = "\n".join(
        path.read_text(encoding="utf-8") for path in (BACKEND, TYPES, PANEL)
    )
    assert "\u2014" not in audited

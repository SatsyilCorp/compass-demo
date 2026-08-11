from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]
SOURCE_TEMPLATE = ROOT / "template.yaml"
BUNDLED_TEMPLATE = ROOT / "src/functions/rmf_artifact/template.yaml"


def test_bundled_rmf_template_matches_deploy_template():
    assert BUNDLED_TEMPLATE.read_bytes() == SOURCE_TEMPLATE.read_bytes()


@pytest.mark.parametrize(
    "entrypoint",
    (
        "scripts/deploy.sh",
        "scripts/deploy_satsyil.sh",
        ".github/workflows/deploy.yml",
        ".github/workflows/quality.yml",
    ),
)
def test_backend_builds_stage_the_rmf_template(entrypoint):
    content = (ROOT / entrypoint).read_text(encoding="utf-8")
    sync_position = content.find("rmf_artifact/prepare_template.sh")
    build_match = re.search(r"(?m)^\s*(?:run:\s*)?sam build(?:\s|$)", content)

    assert sync_position >= 0, f"{entrypoint} does not stage the RMF template"
    assert build_match is not None, f"{entrypoint} does not build the SAM application"
    assert sync_position < build_match.start(), f"{entrypoint} stages the RMF template after building"

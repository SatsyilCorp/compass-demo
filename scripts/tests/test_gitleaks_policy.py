from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_gitleaks_allowlist_is_limited_to_the_public_rfc_totp_vector():
    policy = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")

    assert 'id = "generic-api-key"' in policy
    assert 'condition = "AND"' in policy
    assert "^GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ$" in policy
    assert "scripts/tests/test_provision_demo_identities\\.py" in policy
    assert "commits =" not in policy
    assert "stopwords =" not in policy


def test_devsecops_scan_uses_the_reviewed_policy():
    workflow = (ROOT / ".github/workflows/devsecops.yml").read_text(
        encoding="utf-8"
    )

    assert "--config=/repo/.gitleaks.toml" in workflow
    assert "--redact" in workflow

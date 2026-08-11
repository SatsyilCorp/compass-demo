from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_team_demo_user_pool_disables_all_mfa_configuration() -> None:
    template = (ROOT / "template.yaml").read_text(encoding="utf-8")
    user_pool = template.split("\n  UserPool:\n", 1)[1].split(
        "\n  UserPoolDomain:\n", 1
    )[0]

    assert 'MfaConfiguration: "OFF"' in user_pool
    assert "EnabledMfas:" not in user_pool
    assert "SOFTWARE_TOKEN_MFA" not in user_pool


def test_login_copy_separates_team_demo_access_from_production_mfa() -> None:
    login = (ROOT / "frontend/app/login/page.tsx").read_text(encoding="utf-8")

    assert "Team demo access" in login
    assert "Password only" in login
    assert "Production target" in login
    for stale_claim in (
        "MfaConfiguration: ON",
        "Password + TOTP",
        "then a TOTP code",
        "MFA is enforced pool-wide",
        "MFA-gated flow",
    ):
        assert stale_claim not in login

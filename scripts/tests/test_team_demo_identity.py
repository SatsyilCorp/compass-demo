from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_optional_mfa_keeps_team_accounts_password_only_and_supports_presenter_totp() -> (
    None
):
    template = (ROOT / "template.yaml").read_text(encoding="utf-8")
    user_pool = template.split("\n  UserPool:\n", 1)[1].split(
        "\n  UserPoolDomain:\n", 1
    )[0]

    assert "MfaConfiguration: OPTIONAL" in user_pool
    assert "EnabledMfas: [SOFTWARE_TOKEN_MFA]" in user_pool

    posture = (ROOT / "scripts" / "configure_demo_identity_posture.py").read_text(
        encoding="utf-8"
    )
    assert '"presenter@compass.demo"' in posture
    assert "TEAM_IDENTITIES" in posture
    assert '"Enabled": False' in posture
    assert '"PreferredMfa": False' in posture
    assert '"Enabled": True' in posture
    assert '"PreferredMfa": True' in posture


def test_login_copy_separates_team_demo_access_from_production_mfa() -> None:
    login = (ROOT / "frontend/app/login/page.tsx").read_text(encoding="utf-8")

    assert "Team demo access" in login
    assert "password-only" in login
    assert "Production target" in login
    for stale_claim in (
        "MfaConfiguration: ON",
        "Password + TOTP",
        "then a TOTP code",
        "MFA is enforced pool-wide",
        "MFA-gated flow",
    ):
        assert stale_claim not in login

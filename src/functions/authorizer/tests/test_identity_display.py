"""Human-safe display name selection for the authenticated identity card."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
COMMON = ROOT / "src" / "common" / "python"
APP_PATH = ROOT / "src" / "functions" / "authorizer" / "app.py"
sys.path.insert(0, str(COMMON))

SPEC = importlib.util.spec_from_file_location("authorizer_identity_app", APP_PATH)
authorizer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(authorizer)


def test_display_name_prefers_human_email_over_opaque_cognito_username() -> None:
    claims = {"cognito:username": "opaque-identity-value"}

    assert (
        authorizer._display_name(claims, "poweruser@compass.demo", "poweruser")
        == "poweruser"
    )


def test_display_name_prefers_explicit_name_claim() -> None:
    claims = {
        "name": "Portfolio Power User",
        "cognito:username": "opaque-identity-value",
    }

    assert (
        authorizer._display_name(claims, "poweruser@compass.demo", "poweruser")
        == "Portfolio Power User"
    )

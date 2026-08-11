from __future__ import annotations

import copy
from typing import Any

from scripts.configure_demo_identity_posture import (
    PRESENTER_IDENTITY,
    enroll_optional_presenter,
    set_team_password_only,
)
from scripts.provision_demo_identities import rfc6238_totp


FIXED_TIME = 120.0
SECRET = "JBSWY3DPEHPK3PXP"


class FakeStore:
    def __init__(self):
        self.saved = []

    def save(self, state):
        self.saved.append(copy.deepcopy(state))


class FakeAws:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.mfa = {}

    def call(self, service, operation, payload):
        assert service == "cognito-idp"
        self.calls.append((operation, copy.deepcopy(payload)))
        username = payload.get("Username")
        if operation == "initiate-auth":
            return {"AuthenticationResult": {"AccessToken": "protected-access-token"}}
        if operation == "associate-software-token":
            assert payload == {"AccessToken": "protected-access-token"}
            return {"SecretCode": SECRET}
        if operation == "verify-software-token":
            assert payload["AccessToken"] == "protected-access-token"
            assert payload["UserCode"] == rfc6238_totp(SECRET, FIXED_TIME)
            return {"Status": "SUCCESS"}
        if operation == "admin-set-user-mfa-preference":
            settings = payload["SoftwareTokenMfaSettings"]
            self.mfa[username] = settings["Enabled"]
            return {}
        if operation == "admin-get-user":
            return {
                "Enabled": True,
                "UserStatus": "CONFIRMED",
                "UserMFASettingList": ["SOFTWARE_TOKEN_MFA"]
                if self.mfa.get(username)
                else [],
            }
        raise AssertionError(operation)


def test_team_identity_is_explicitly_password_only():
    aws = FakeAws()
    aws.mfa["poweruser@compass.demo"] = True

    set_team_password_only(
        aws,
        user_pool_id="pool-redacted",
        username="poweruser@compass.demo",
    )

    preference = aws.calls[0][1]["SoftwareTokenMfaSettings"]
    assert preference == {"Enabled": False, "PreferredMfa": False}
    assert aws.mfa["poweruser@compass.demo"] is False


def test_formal_presenter_enrolls_and_prefers_totp_without_printing_material(capsys):
    aws = FakeAws()
    store = FakeStore()
    state = {
        "schema_version": 1,
        "status": "pending",
        "username": PRESENTER_IDENTITY[0],
        "group": PRESENTER_IDENTITY[1],
        "totp_secret": None,
    }

    enroll_optional_presenter(
        aws,
        user_pool_id="pool-redacted",
        client_id="client-redacted",
        shared_password="not-printed",
        state=state,
        store=store,
        clock=lambda: FIXED_TIME,
        sleeper=lambda _seconds: None,
    )

    assert state["status"] == "complete"
    assert state["totp_secret"] == SECRET
    preference_calls = [
        payload
        for operation, payload in aws.calls
        if operation == "admin-set-user-mfa-preference"
    ]
    assert preference_calls[-1]["SoftwareTokenMfaSettings"] == {
        "Enabled": True,
        "PreferredMfa": True,
    }
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert "protected-access-token" not in output.out + output.err

from __future__ import annotations

import copy
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.provision_demo_identities import (
    AWS_PROFILE,
    AWS_REGION,
    IDENTITY_CONTRACT,
    AwsCallError,
    AwsCli,
    CredentialStore,
    ProvisioningError,
    generate_strong_password,
    is_strong_password,
    provision_identities,
    rfc6238_totp,
)


EXPECTED_ACCOUNT = "0" * 12
POOL_VALUE = "pool-private-value"
CLIENT_VALUE = "client-private-value"
TOTP_SECRETS = (
    "JBSWY3DPEHPK3PXP",
    "KRSXG5DSNFXGOIDB",
    "MFRGGZDFMZTWQ2LK",
)
FIXED_TIME = 120.0


class FakeAws:
    def __init__(self, *, existing_mfa: bool = False) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.users: dict[str, dict[str, Any]] = {}
        self.initial_sessions: dict[str, str] = {}
        self.association_sessions: dict[str, tuple[str, str]] = {}
        self.verification_sessions: dict[str, str] = {}
        self.remaining_secrets = list(TOTP_SECRETS)
        self.client_deleted = False
        if existing_mfa:
            for username, group in IDENTITY_CONTRACT:
                self.users[username] = {
                    "enabled": True,
                    "status": "CONFIRMED",
                    "groups": {group},
                    "mfa": True,
                }

    def call(self, service: str, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((service, operation, copy.deepcopy(payload)))
        if operation == "get-caller-identity":
            return {"Account": EXPECTED_ACCOUNT}
        if operation == "describe-stacks":
            return {
                "Stacks": [
                    {
                        "Outputs": [
                            {"OutputKey": "UserPoolId", "OutputValue": POOL_VALUE}
                        ]
                    }
                ]
            }
        if operation == "admin-get-user":
            username = payload["Username"]
            user = self.users.get(username)
            if user is None:
                raise AwsCallError(operation, "UserNotFoundException")
            return {
                "Enabled": user["enabled"],
                "UserStatus": user["status"],
                "UserMFASettingList": ["SOFTWARE_TOKEN_MFA"] if user["mfa"] else [],
            }
        if operation == "admin-create-user":
            username = payload["Username"]
            self.users[username] = {
                "enabled": True,
                "status": "FORCE_CHANGE_PASSWORD",
                "groups": set(),
                "mfa": False,
            }
            return {"User": {"Enabled": True, "UserStatus": "FORCE_CHANGE_PASSWORD"}}
        if operation == "admin-enable-user":
            self.users[payload["Username"]]["enabled"] = True
            return {}
        if operation == "admin-update-user-attributes":
            return {}
        if operation == "admin-set-user-password":
            self.users[payload["Username"]]["status"] = "CONFIRMED"
            return {}
        if operation == "admin-list-groups-for-user":
            groups = self.users[payload["Username"]]["groups"]
            return {"Groups": [{"GroupName": group} for group in sorted(groups)]}
        if operation == "admin-remove-user-from-group":
            self.users[payload["Username"]]["groups"].discard(payload["GroupName"])
            return {}
        if operation == "admin-add-user-to-group":
            self.users[payload["Username"]]["groups"].add(payload["GroupName"])
            return {}
        if operation == "create-user-pool-client":
            return {
                "UserPoolClient": {
                    "ClientId": CLIENT_VALUE,
                    "GenerateSecret": False,
                    "ExplicitAuthFlows": ["ALLOW_USER_PASSWORD_AUTH"],
                }
            }
        if operation == "initiate-auth":
            username = payload["AuthParameters"]["USERNAME"]
            session_value = f"initial-session-{len(self.initial_sessions)}"
            self.initial_sessions[session_value] = username
            challenge = (
                "SOFTWARE_TOKEN_MFA" if self.users[username]["mfa"] else "MFA_SETUP"
            )
            return {"ChallengeName": challenge, "Session": session_value}
        if operation == "associate-software-token":
            username = self.initial_sessions[payload["Session"]]
            secret_value = self.remaining_secrets.pop(0)
            session_value = f"association-session-{len(self.association_sessions)}"
            self.association_sessions[session_value] = (username, secret_value)
            return {"SecretCode": secret_value, "Session": session_value}
        if operation == "verify-software-token":
            username, secret_value = self.association_sessions[payload["Session"]]
            assert payload["UserCode"] == rfc6238_totp(secret_value, FIXED_TIME)
            session_value = f"verification-session-{len(self.verification_sessions)}"
            self.verification_sessions[session_value] = username
            return {"Status": "SUCCESS", "Session": session_value}
        if operation == "respond-to-auth-challenge":
            if payload["ChallengeName"] == "MFA_SETUP":
                username = self.verification_sessions[payload["Session"]]
            else:
                username = self.initial_sessions[payload["Session"]]
                assert payload["ChallengeResponses"]["SOFTWARE_TOKEN_MFA_CODE"]
            return {
                "AuthenticationResult": {
                    "AccessToken": f"access-token-{username}",
                    "IdToken": f"identity-token-{username}",
                }
            }
        if operation == "admin-set-user-mfa-preference":
            settings = payload["SoftwareTokenMfaSettings"]
            assert settings == {"Enabled": True, "PreferredMfa": True}
            self.users[payload["Username"]]["mfa"] = True
            return {}
        if operation == "delete-user-pool-client":
            assert payload == {"UserPoolId": POOL_VALUE, "ClientId": CLIENT_VALUE}
            self.client_deleted = True
            return {}
        raise AssertionError(f"unexpected fake AWS operation: {service} {operation}")


class FailingVerificationAws(FakeAws):
    def call(self, service: str, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "verify-software-token":
            self.calls.append((service, operation, copy.deepcopy(payload)))
            raise AwsCallError(operation, "CodeMismatchException")
        return super().call(service, operation, payload)


def operation_names(fake_aws: FakeAws) -> list[str]:
    return [operation for _, operation, _ in fake_aws.calls]


def test_rfc6238_sha1_reference_vector() -> None:
    reference_secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert rfc6238_totp(reference_secret, 59, digits=8) == "94287082"


def test_generated_password_meets_contract() -> None:
    passwords = {generate_strong_password() for _ in range(20)}
    assert len(passwords) == 20
    assert all(len(password) == 32 for password in passwords)
    assert all(is_strong_password(password) for password in passwords)


def test_fresh_provisioning_completes_without_disclosing_material(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_aws = FakeAws()
    store = CredentialStore(tmp_path)

    provision_identities(
        fake_aws,
        store,
        stack_name="compass-demo",
        expected_account=EXPECTED_ACCOUNT,
        clock=lambda: FIXED_TIME,
        sleeper=lambda _seconds: None,
    )

    output = capsys.readouterr()
    protected_text = output.out + output.err
    document_text = store.path.read_text(encoding="utf-8")
    document = json.loads(document_text)
    password = document["shared_password"]
    sensitive_values = (
        EXPECTED_ACCOUNT,
        POOL_VALUE,
        CLIENT_VALUE,
        password,
        *TOTP_SECRETS,
        "initial-session",
        "association-session",
        "verification-session",
        "access-token",
        "identity-token",
    )
    assert all(value not in protected_text for value in sensitive_values)
    assert all(value not in document_text for value in (EXPECTED_ACCOUNT, POOL_VALUE, CLIENT_VALUE))
    assert document["status"] == "complete"
    assert set(document) == {
        "schema_version",
        "status",
        "shared_password",
        "identities",
    }
    assert {item["totp_secret"] for item in document["identities"]} == set(TOTP_SECRETS)
    assert all(item["enrollment_status"] == "complete" for item in document["identities"])
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.private_directory.stat().st_mode) == 0o700
    assert fake_aws.client_deleted is True
    assert operation_names(fake_aws)[-1] == "delete-user-pool-client"

    create_payload = next(
        payload
        for _, operation, payload in fake_aws.calls
        if operation == "create-user-pool-client"
    )
    assert create_payload["GenerateSecret"] is False
    assert create_payload["ExplicitAuthFlows"] == ["ALLOW_USER_PASSWORD_AUTH"]
    challenge_operations = [
        operation
        for operation in operation_names(fake_aws)
        if operation
        in {
            "initiate-auth",
            "associate-software-token",
            "verify-software-token",
            "respond-to-auth-challenge",
        }
    ]
    assert challenge_operations == [
        operation
        for _identity in IDENTITY_CONTRACT
        for operation in (
            "initiate-auth",
            "associate-software-token",
            "verify-software-token",
            "respond-to-auth-challenge",
        )
    ]


def test_failure_still_deletes_temporary_client(tmp_path: Path) -> None:
    fake_aws = FailingVerificationAws()

    with pytest.raises(AwsCallError, match="CodeMismatchException"):
        provision_identities(
            fake_aws,
            CredentialStore(tmp_path),
            stack_name="compass-demo",
            expected_account=EXPECTED_ACCOUNT,
            clock=lambda: FIXED_TIME,
            sleeper=lambda _seconds: None,
            reporter=lambda _message: None,
        )

    assert fake_aws.client_deleted is True
    assert operation_names(fake_aws)[-1] == "delete-user-pool-client"


def test_complete_rerun_reuses_factors_without_association(tmp_path: Path) -> None:
    store = CredentialStore(tmp_path)
    first_aws = FakeAws()
    provision_identities(
        first_aws,
        store,
        stack_name="compass-demo",
        expected_account=EXPECTED_ACCOUNT,
        clock=lambda: FIXED_TIME,
        sleeper=lambda _seconds: None,
        reporter=lambda _message: None,
    )
    first_document = store.path.read_text(encoding="utf-8")

    rerun_aws = FakeAws(existing_mfa=True)
    provision_identities(
        rerun_aws,
        store,
        stack_name="compass-demo",
        expected_account=EXPECTED_ACCOUNT,
        clock=lambda: FIXED_TIME,
        sleeper=lambda _seconds: None,
        reporter=lambda _message: None,
    )

    assert store.path.read_text(encoding="utf-8") == first_document
    assert "associate-software-token" not in operation_names(rerun_aws)
    assert "verify-software-token" not in operation_names(rerun_aws)
    assert operation_names(rerun_aws).count("respond-to-auth-challenge") == 3
    assert rerun_aws.client_deleted is True


def test_aws_cli_uses_literal_profile_and_protected_request_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    secret_payload = {
        "Password": "private-password-value",
        "Session": "private-session-value",
        "ClientId": "private-client-value",
    }

    def executor(command: list[str], **kwargs: Any) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        request_uri = command[command.index("--cli-input-json") + 1]
        request_path = Path(request_uri.removeprefix("file://"))
        captured["request_payload"] = json.loads(request_path.read_text())
        captured["request_mode"] = stat.S_IMODE(request_path.stat().st_mode)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ambient-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "ambient-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "ambient-token")
    monkeypatch.setenv("SATSYIL_EXPECTED_ACCOUNT_ID", EXPECTED_ACCOUNT)
    AwsCli(executor=executor).call("cognito-idp", "initiate-auth", secret_payload)

    command = captured["command"]
    environment = captured["env"]
    assert command[:5] == ["aws", "--profile", AWS_PROFILE, "--region", AWS_REGION]
    assert command[command.index("--cli-input-json") + 1].startswith("file://")
    assert all(str(value) not in command for value in secret_payload.values())
    assert captured["request_payload"] == secret_payload
    assert captured["request_mode"] == 0o600
    assert "input" not in captured
    assert environment["AWS_PROFILE"] == AWS_PROFILE
    assert environment["AWS_DEFAULT_PROFILE"] == AWS_PROFILE
    assert environment["AWS_REGION"] == AWS_REGION
    assert "AWS_ACCESS_KEY_ID" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "AWS_SESSION_TOKEN" not in environment
    assert "SATSYIL_EXPECTED_ACCOUNT_ID" not in environment


def test_store_rejects_a_symlink_target(tmp_path: Path) -> None:
    store = CredentialStore(tmp_path)
    store.private_directory.mkdir(parents=True)
    external = tmp_path / "external.json"
    external.write_text("unchanged", encoding="utf-8")
    os.symlink(external, store.path)

    with pytest.raises(ProvisioningError, match="symbolic link"):
        with store.locked():
            store.load_or_initialize()

    assert external.read_text(encoding="utf-8") == "unchanged"

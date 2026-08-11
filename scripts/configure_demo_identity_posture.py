#!/usr/bin/env python3
"""Configure password-only team users and one TOTP formal presenter.

The user pool is OPTIONAL MFA. This operator workflow explicitly disables MFA
preference for the three collaboration identities and enrolls a distinct
presenter identity for the formal Element 1 authentication demonstration. No
credential or TOTP value is printed. Protected material is written only under
the ignored, mode 0700 ``artifacts/private`` directory.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
from typing import Any, Callable, Dict, Mapping, MutableMapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.provision_demo_identities import (  # noqa: E402
    AwsApi,
    AwsCallError,
    AwsCli,
    CredentialStore,
    InterruptedProvisioning,
    ProvisioningError,
    ensure_user,
    normalize_totp_secret,
    resolve_user_pool,
    stable_totp,
    temporary_enrollment_client,
    termination_guard,
    verify_account,
)


TEAM_IDENTITIES = (
    ("poweruser@compass.demo", "compass-poweruser"),
    ("reviewer@compass.demo", "compass-poweruser"),
    ("viewer@compass.demo", "compass-viewer"),
)
PRESENTER_IDENTITY = ("presenter@compass.demo", "compass-poweruser")
PRESENTER_SCHEMA_VERSION = 1


def _validate_presenter_state(state: object) -> Dict[str, Any]:
    if not isinstance(state, dict) or set(state) != {
        "schema_version",
        "status",
        "username",
        "group",
        "totp_secret",
    }:
        raise ProvisioningError("The protected presenter artifact is invalid")
    if state.get("schema_version") != PRESENTER_SCHEMA_VERSION:
        raise ProvisioningError(
            "The protected presenter artifact has an unknown schema"
        )
    if state.get("status") not in {"pending", "complete"}:
        raise ProvisioningError("The protected presenter artifact is invalid")
    if (state.get("username"), state.get("group")) != PRESENTER_IDENTITY:
        raise ProvisioningError("The protected presenter artifact is invalid")
    secret_value = state.get("totp_secret")
    if secret_value is not None:
        state["totp_secret"] = normalize_totp_secret(secret_value)
    if state["status"] == "complete" and secret_value is None:
        raise ProvisioningError("The protected presenter artifact is inconsistent")
    return state


class PresenterStore:
    def __init__(self, repository_root: Path):
        self._credential_store = CredentialStore(repository_root)
        self.path = (
            self._credential_store.private_directory / "formal-demo-presenter.json"
        )

    def _prepare(self) -> None:
        self._credential_store._prepare_directory()
        self._credential_store._reject_symlink(self.path)

    def load_or_initialize(self) -> Dict[str, Any]:
        self._prepare()
        if not self.path.exists():
            state = {
                "schema_version": PRESENTER_SCHEMA_VERSION,
                "status": "pending",
                "username": PRESENTER_IDENTITY[0],
                "group": PRESENTER_IDENTITY[1],
                "totp_secret": None,
            }
            self.save(state)
            return state
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags)
        try:
            if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o600:
                raise ProvisioningError(
                    "The protected presenter artifact mode is not 0600"
                )
            with os.fdopen(descriptor, encoding="utf-8") as handle:
                descriptor = -1
                return _validate_presenter_state(json.load(handle))
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def save(self, state: MutableMapping[str, Any]) -> None:
        _validate_presenter_state(state)
        self._prepare()
        temporary = self.path.parent / f".{self.path.name}.{secrets.token_hex(8)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary.exists():
                temporary.unlink()


def set_team_password_only(aws: AwsApi, *, user_pool_id: str, username: str) -> None:
    aws.call(
        "cognito-idp",
        "admin-set-user-mfa-preference",
        {
            "UserPoolId": user_pool_id,
            "Username": username,
            "SoftwareTokenMfaSettings": {"Enabled": False, "PreferredMfa": False},
        },
    )
    user = aws.call(
        "cognito-idp",
        "admin-get-user",
        {"UserPoolId": user_pool_id, "Username": username},
    )
    if "SOFTWARE_TOKEN_MFA" in (user.get("UserMFASettingList") or []):
        raise ProvisioningError("A team identity still has an active MFA preference")


def _authentication_result(response: Mapping[str, Any]) -> Dict[str, Any]:
    result = response.get("AuthenticationResult")
    if not isinstance(result, dict):
        raise ProvisioningError("Cognito did not complete presenter authentication")
    return result


def enroll_optional_presenter(
    aws: AwsApi,
    *,
    user_pool_id: str,
    client_id: str,
    shared_password: str,
    state: MutableMapping[str, Any],
    store: PresenterStore,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    username = str(state["username"])
    initial = aws.call(
        "cognito-idp",
        "initiate-auth",
        {
            "ClientId": client_id,
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {"USERNAME": username, "PASSWORD": shared_password},
        },
    )
    if initial.get("ChallengeName") == "SOFTWARE_TOKEN_MFA":
        secret_value = state.get("totp_secret")
        session = initial.get("Session")
        if not secret_value or not isinstance(session, str):
            raise ProvisioningError(
                "The presenter MFA factor is missing protected state"
            )
        verified = aws.call(
            "cognito-idp",
            "respond-to-auth-challenge",
            {
                "ClientId": client_id,
                "ChallengeName": "SOFTWARE_TOKEN_MFA",
                "ChallengeResponses": {
                    "USERNAME": username,
                    "SOFTWARE_TOKEN_MFA_CODE": stable_totp(
                        secret_value, clock=clock, sleeper=sleeper
                    ),
                },
                "Session": session,
            },
        )
        _authentication_result(verified)
    elif initial.get("ChallengeName"):
        raise ProvisioningError("Cognito returned an unexpected presenter challenge")
    else:
        access_token = _authentication_result(initial).get("AccessToken")
        if not isinstance(access_token, str) or not access_token:
            raise ProvisioningError("Cognito did not return a presenter access token")
        association = aws.call(
            "cognito-idp",
            "associate-software-token",
            {"AccessToken": access_token},
        )
        secret_value = normalize_totp_secret(association.get("SecretCode"))
        state["totp_secret"] = secret_value
        store.save(state)
        verification = aws.call(
            "cognito-idp",
            "verify-software-token",
            {
                "AccessToken": access_token,
                "UserCode": stable_totp(secret_value, clock=clock, sleeper=sleeper),
                "FriendlyDeviceName": "Compass formal demo presenter",
            },
        )
        if verification.get("Status") != "SUCCESS":
            raise ProvisioningError("Cognito did not verify the presenter TOTP factor")

    aws.call(
        "cognito-idp",
        "admin-set-user-mfa-preference",
        {
            "UserPoolId": user_pool_id,
            "Username": username,
            "SoftwareTokenMfaSettings": {"Enabled": True, "PreferredMfa": True},
        },
    )
    user = aws.call(
        "cognito-idp",
        "admin-get-user",
        {"UserPoolId": user_pool_id, "Username": username},
    )
    if (
        user.get("Enabled") is not True
        or user.get("UserStatus") != "CONFIRMED"
        or "SOFTWARE_TOKEN_MFA" not in (user.get("UserMFASettingList") or [])
    ):
        raise ProvisioningError(
            "The formal presenter identity failed final verification"
        )
    state["status"] = "complete"
    store.save(state)


def configure_identity_posture(
    aws: AwsApi,
    *,
    repository_root: Path,
    stack_name: str,
    expected_account: str,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
    reporter: Callable[[str], None] = print,
) -> None:
    verify_account(aws, expected_account)
    user_pool_id = resolve_user_pool(aws, stack_name)
    team_store = CredentialStore(repository_root)
    presenter_store = PresenterStore(repository_root)
    with team_store.locked():
        team_state = team_store.load_or_initialize()
        shared_password = str(team_state["shared_password"])
        for index, (username, group) in enumerate(TEAM_IDENTITIES, start=1):
            ensure_user(
                aws,
                user_pool_id=user_pool_id,
                username=username,
                group=group,
                password=shared_password,
            )
            set_team_password_only(aws, user_pool_id=user_pool_id, username=username)
            reporter(
                f"Team identity {index} of {len(TEAM_IDENTITIES)} is password-only"
            )

        presenter_state = presenter_store.load_or_initialize()
        ensure_user(
            aws,
            user_pool_id=user_pool_id,
            username=PRESENTER_IDENTITY[0],
            group=PRESENTER_IDENTITY[1],
            password=shared_password,
        )
        with temporary_enrollment_client(
            aws, user_pool_id=user_pool_id, clock=clock
        ) as client_id:
            enroll_optional_presenter(
                aws,
                user_pool_id=user_pool_id,
                client_id=client_id,
                shared_password=shared_password,
                state=presenter_state,
                store=presenter_store,
                clock=clock,
                sleeper=sleeper,
            )
        reporter("Formal presenter identity is TOTP-enabled")


def _parse_args(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure Compass team and formal presenter identity posture"
    )
    parser.add_argument("--stack", default="compass-demo")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_args(arguments)
    expected_account = os.environ.pop("SATSYIL_EXPECTED_ACCOUNT_ID", "")
    repository_root = REPOSITORY_ROOT
    try:
        with termination_guard():
            configure_identity_posture(
                AwsCli(),
                repository_root=repository_root,
                stack_name=args.stack,
                expected_account=expected_account,
            )
    except (KeyboardInterrupt, InterruptedProvisioning):
        print("ERROR: secure identity configuration was interrupted", file=sys.stderr)
        return 130
    except (AwsCallError, ProvisioningError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: secure identity configuration failed safely", file=sys.stderr)
        return 1
    print("Secure identity posture is configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

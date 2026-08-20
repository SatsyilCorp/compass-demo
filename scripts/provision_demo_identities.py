#!/usr/bin/env python3
"""Low-level Cognito identity helpers and compatibility entrypoint.

AWS request bodies are sent through short-lived mode 0600 files so credentials
and transient challenge material never enter command arguments. The only
credential output is an ignored, mode 0600 artifact managed by
:class:`CredentialStore`.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import stat
import string
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any, Protocol


AWS_PROFILE = "satsyil"
AWS_REGION = "us-east-1"
CREDENTIAL_SCHEMA_VERSION = 1
MANAGED_GROUPS = frozenset({"compass-poweruser", "compass-viewer"})
IDENTITY_CONTRACT = (
    ("poweruser@compass.demo", "compass-poweruser"),
    ("reviewer@compass.demo", "compass-poweruser"),
    ("viewer@compass.demo", "compass-viewer"),
)
PASSWORD_SYMBOLS = "!#$%&()*+,-.:;<=>?@[]^_{|}~"
STACK_NAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9-]{0,127}")
ACCOUNT_ID_PATTERN = re.compile(r"[0-9]{12}")
BASE32_PATTERN = re.compile(r"[A-Z2-7]{16,128}")

_AWS_CREDENTIAL_ENVIRONMENT = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_SECURITY_TOKEN",
    "AWS_ROLE_ARN",
    "AWS_ROLE_SESSION_NAME",
    "AWS_WEB_IDENTITY_TOKEN_FILE",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "SATSYIL_EXPECTED_ACCOUNT_ID",
)


class ProvisioningError(RuntimeError):
    """A sanitized provisioning failure that is safe to show to an operator."""


class InterruptedProvisioning(ProvisioningError):
    """Raised on a termination request so temporary resources are cleaned up."""


class AwsCallError(ProvisioningError):
    """A sanitized AWS CLI failure without request or response material."""

    def __init__(self, operation: str, code: str = "UnknownError") -> None:
        self.operation = operation
        self.code = code
        super().__init__(f"AWS {operation} failed with {code}")


class AwsApi(Protocol):
    def call(
        self,
        service: str,
        operation: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]: ...


class CompletedProcessLike(Protocol):
    returncode: int
    stdout: str
    stderr: str


Executor = Callable[..., CompletedProcessLike]


def _aws_error_code(stderr: str) -> str:
    match = re.search(r"\(([A-Za-z0-9_.-]+)\) when calling", stderr)
    return match.group(1) if match else "UnknownError"


class AwsCli:
    """Run AWS CLI calls with a literal profile and protected request files."""

    def __init__(self, executor: Executor = subprocess.run) -> None:
        self._executor = executor

    @staticmethod
    def _environment() -> dict[str, str]:
        environment = os.environ.copy()
        for name in _AWS_CREDENTIAL_ENVIRONMENT:
            environment.pop(name, None)
        environment.update(
            {
                "AWS_PROFILE": AWS_PROFILE,
                "AWS_DEFAULT_PROFILE": AWS_PROFILE,
                "AWS_REGION": AWS_REGION,
                "AWS_DEFAULT_REGION": AWS_REGION,
            }
        )
        return environment

    def call(
        self,
        service: str,
        operation: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        request_json = json.dumps(payload, separators=(",", ":"))
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="compass-aws-request-",
                suffix=".json",
            ) as request_file:
                os.chmod(request_file.name, 0o600)
                request_file.write(request_json)
                request_file.flush()
                command = [
                    "aws",
                    "--profile",
                    AWS_PROFILE,
                    "--region",
                    AWS_REGION,
                    service,
                    operation,
                    "--cli-input-json",
                    Path(request_file.name).resolve().as_uri(),
                    "--output",
                    "json",
                    "--no-cli-pager",
                ]
                result = self._executor(
                    command,
                    text=True,
                    capture_output=True,
                    check=False,
                    env=self._environment(),
                )
        except OSError as error:
            raise AwsCallError(operation, "CliUnavailable") from error

        if result.returncode != 0:
            raise AwsCallError(operation, _aws_error_code(result.stderr))
        if not result.stdout.strip():
            return {}
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise AwsCallError(operation, "InvalidResponse") from error
        if not isinstance(response, dict):
            raise AwsCallError(operation, "InvalidResponse")
        return response


def generate_strong_password(length: int = 32) -> str:
    """Return a strong password with every required character category."""

    if length < 16:
        raise ValueError("password length must be at least 16")
    random_source = secrets.SystemRandom()
    characters = [
        random_source.choice(string.ascii_uppercase),
        random_source.choice(string.ascii_lowercase),
        random_source.choice(string.digits),
        random_source.choice(PASSWORD_SYMBOLS),
    ]
    alphabet = string.ascii_letters + string.digits + PASSWORD_SYMBOLS
    characters.extend(random_source.choice(alphabet) for _ in range(length - 4))
    random_source.shuffle(characters)
    return "".join(characters)


def is_strong_password(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) >= 16
        and any(character.isupper() for character in value)
        and any(character.islower() for character in value)
        and any(character.isdigit() for character in value)
        and any(character in PASSWORD_SYMBOLS for character in value)
    )


def normalize_totp_secret(value: object) -> str:
    if not isinstance(value, str):
        raise ProvisioningError("Cognito returned invalid TOTP setup material")
    normalized = value.strip().replace(" ", "").rstrip("=").upper()
    if not BASE32_PATTERN.fullmatch(normalized):
        raise ProvisioningError("Cognito returned invalid TOTP setup material")
    padded = normalized + "=" * ((8 - len(normalized) % 8) % 8)
    try:
        base64.b32decode(padded, casefold=True)
    except ValueError as error:
        raise ProvisioningError("Cognito returned invalid TOTP setup material") from error
    return normalized


def rfc6238_totp(
    secret: str,
    timestamp: float,
    *,
    digits: int = 6,
    period_seconds: int = 30,
) -> str:
    """Calculate an RFC 6238 SHA-1 TOTP without an external dependency."""

    normalized = normalize_totp_secret(secret)
    padded = normalized + "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    counter = int(timestamp) // period_seconds
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10**digits)).zfill(digits)


def stable_totp(
    secret: str,
    *,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
    minimum_validity_seconds: float = 5.0,
) -> str:
    """Avoid sending a TOTP that is about to cross its 30 second boundary."""

    now = clock()
    remaining = 30.0 - (now % 30.0)
    if remaining <= minimum_validity_seconds:
        sleeper(remaining + 0.25)
        now = clock()
    return rfc6238_totp(secret, now)


def _new_state() -> dict[str, Any]:
    return {
        "schema_version": CREDENTIAL_SCHEMA_VERSION,
        "status": "in_progress",
        "shared_password": generate_strong_password(),
        "identities": [
            {
                "username": username,
                "group": group,
                "totp_secret": None,
                "enrollment_status": "pending",
            }
            for username, group in IDENTITY_CONTRACT
        ],
    }


def _validate_state(state: object) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ProvisioningError("The protected credential artifact is invalid")
    if set(state) != {
        "schema_version",
        "status",
        "shared_password",
        "identities",
    }:
        raise ProvisioningError("The protected credential artifact has unknown fields")
    if state.get("schema_version") != CREDENTIAL_SCHEMA_VERSION:
        raise ProvisioningError("The protected credential artifact has an unknown schema")
    if state.get("status") not in {"in_progress", "complete"}:
        raise ProvisioningError("The protected credential artifact is invalid")
    if not is_strong_password(state.get("shared_password")):
        raise ProvisioningError("The protected credential artifact is invalid")

    identities = state.get("identities")
    if not isinstance(identities, list) or len(identities) != len(IDENTITY_CONTRACT):
        raise ProvisioningError("The protected credential artifact is invalid")

    seen_secrets: set[str] = set()
    completed = 0
    for identity, (expected_username, expected_group) in zip(
        identities,
        IDENTITY_CONTRACT,
        strict=True,
    ):
        if not isinstance(identity, dict):
            raise ProvisioningError("The protected credential artifact is invalid")
        if set(identity) != {
            "username",
            "group",
            "totp_secret",
            "enrollment_status",
        }:
            raise ProvisioningError("The protected credential artifact has unknown fields")
        if identity.get("username") != expected_username:
            raise ProvisioningError("The protected credential artifact is invalid")
        if identity.get("group") != expected_group:
            raise ProvisioningError("The protected credential artifact is invalid")
        enrollment_status = identity.get("enrollment_status")
        if enrollment_status not in {"pending", "complete"}:
            raise ProvisioningError("The protected credential artifact is invalid")
        secret_value = identity.get("totp_secret")
        if secret_value is not None:
            normalized = normalize_totp_secret(secret_value)
            identity["totp_secret"] = normalized
            if normalized in seen_secrets:
                raise ProvisioningError("TOTP factors in the credential artifact are not unique")
            seen_secrets.add(normalized)
        if enrollment_status == "complete":
            if secret_value is None:
                raise ProvisioningError("The protected credential artifact is invalid")
            completed += 1

    all_complete = completed == len(IDENTITY_CONTRACT)
    if (state.get("status") == "complete") != all_complete:
        raise ProvisioningError("The protected credential artifact is inconsistent")
    return state


class CredentialStore:
    """Manage the fixed ignored credential artifact with safe file modes."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.private_directory = self.repository_root / "artifacts" / "private"
        self.path = self.private_directory / "demo-identities.json"
        self.lock_path = self.private_directory / ".provision.lock"

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if os.path.lexists(path) and path.is_symlink():
            raise ProvisioningError("A protected artifact path is a symbolic link")

    def _prepare_directory(self) -> None:
        artifacts_directory = self.repository_root / "artifacts"
        self._reject_symlink(artifacts_directory)
        artifacts_directory.mkdir(mode=0o700, exist_ok=True)
        if not artifacts_directory.is_dir():
            raise ProvisioningError("The artifact parent is not a directory")

        self._reject_symlink(self.private_directory)
        self.private_directory.mkdir(mode=0o700, exist_ok=True)
        if not self.private_directory.is_dir():
            raise ProvisioningError("The protected artifact parent is not a directory")
        # 0o700 is owner-only - the restrictive mode the rule asks for.
        os.chmod(self.private_directory, 0o700)  # nosemgrep

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        self._prepare_directory()
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.lock_path, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def load_or_initialize(self) -> dict[str, Any]:
        self._reject_symlink(self.path)
        if not self.path.exists():
            state = _new_state()
            self.save(state)
            return state

        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags)
        try:
            mode = stat.S_IMODE(os.fstat(descriptor).st_mode)
            if mode != 0o600:
                raise ProvisioningError("The protected credential artifact mode is not 0600")
            with os.fdopen(descriptor, encoding="utf-8") as credential_file:
                descriptor = -1
                try:
                    state = json.load(credential_file)
                except json.JSONDecodeError as error:
                    raise ProvisioningError(
                        "The protected credential artifact is not valid JSON"
                    ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return _validate_state(state)

    def save(self, state: MutableMapping[str, Any]) -> None:
        _validate_state(state)
        self._prepare_directory()
        self._reject_symlink(self.path)
        temporary_path = self.private_directory / (
            f".{self.path.name}.{secrets.token_hex(8)}.tmp"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as credential_file:
                descriptor = -1
                json.dump(state, credential_file, indent=2, sort_keys=True)
                credential_file.write("\n")
                credential_file.flush()
                os.fsync(credential_file.fileno())
            os.replace(temporary_path, self.path)
            os.chmod(self.path, 0o600)
            directory_descriptor = os.open(self.private_directory, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path.exists():
                temporary_path.unlink()


def _require_mapping(response: Mapping[str, Any], key: str, operation: str) -> dict[str, Any]:
    value = response.get(key)
    if not isinstance(value, dict):
        raise AwsCallError(operation, "InvalidResponse")
    return value


def verify_account(aws: AwsApi, expected_account: str) -> None:
    if not ACCOUNT_ID_PATTERN.fullmatch(expected_account):
        raise ProvisioningError(
            "SATSYIL_EXPECTED_ACCOUNT_ID must be a protected 12-digit value"
        )
    response = aws.call("sts", "get-caller-identity", {})
    if response.get("Account") != expected_account:
        raise ProvisioningError("The satsyil profile resolved to an unexpected account")


def resolve_user_pool(aws: AwsApi, stack_name: str) -> str:
    if not STACK_NAME_PATTERN.fullmatch(stack_name):
        raise ProvisioningError("The stack name is invalid")
    response = aws.call(
        "cloudformation",
        "describe-stacks",
        {"StackName": stack_name},
    )
    stacks = response.get("Stacks")
    if not isinstance(stacks, list) or len(stacks) != 1 or not isinstance(stacks[0], dict):
        raise ProvisioningError("The target stack could not be resolved")
    outputs = stacks[0].get("Outputs")
    if not isinstance(outputs, list):
        raise ProvisioningError("The target stack has no usable outputs")
    matches = [
        output.get("OutputValue")
        for output in outputs
        if isinstance(output, dict) and output.get("OutputKey") == "UserPoolId"
    ]
    if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0]:
        raise ProvisioningError("The target stack has no usable identity output")
    return matches[0]


def ensure_user(
    aws: AwsApi,
    *,
    user_pool_id: str,
    username: str,
    group: str,
    password: str,
) -> None:
    try:
        existing = aws.call(
            "cognito-idp",
            "admin-get-user",
            {"UserPoolId": user_pool_id, "Username": username},
        )
    except AwsCallError as error:
        if error.code != "UserNotFoundException":
            raise
        try:
            existing = aws.call(
                "cognito-idp",
                "admin-create-user",
                {
                    "UserPoolId": user_pool_id,
                    "Username": username,
                    "UserAttributes": [
                        {"Name": "email", "Value": username},
                        {"Name": "email_verified", "Value": "true"},
                    ],
                    "MessageAction": "SUPPRESS",
                },
            ).get("User", {})
        except AwsCallError as create_error:
            if create_error.code != "UsernameExistsException":
                raise
            existing = aws.call(
                "cognito-idp",
                "admin-get-user",
                {"UserPoolId": user_pool_id, "Username": username},
            )

    if isinstance(existing, dict) and existing.get("Enabled") is False:
        aws.call(
            "cognito-idp",
            "admin-enable-user",
            {"UserPoolId": user_pool_id, "Username": username},
        )
    aws.call(
        "cognito-idp",
        "admin-update-user-attributes",
        {
            "UserPoolId": user_pool_id,
            "Username": username,
            "UserAttributes": [
                {"Name": "email", "Value": username},
                {"Name": "email_verified", "Value": "true"},
            ],
        },
    )
    aws.call(
        "cognito-idp",
        "admin-set-user-password",
        {
            "UserPoolId": user_pool_id,
            "Username": username,
            "Password": password,
            "Permanent": True,
        },
    )
    memberships = aws.call(
        "cognito-idp",
        "admin-list-groups-for-user",
        {"UserPoolId": user_pool_id, "Username": username, "Limit": 60},
    ).get("Groups", [])
    if not isinstance(memberships, list):
        raise AwsCallError("admin-list-groups-for-user", "InvalidResponse")
    group_names = {
        membership.get("GroupName")
        for membership in memberships
        if isinstance(membership, dict)
    }
    for wrong_group in sorted((group_names & MANAGED_GROUPS) - {group}):
        aws.call(
            "cognito-idp",
            "admin-remove-user-from-group",
            {
                "UserPoolId": user_pool_id,
                "Username": username,
                "GroupName": wrong_group,
            },
        )
    aws.call(
        "cognito-idp",
        "admin-add-user-to-group",
        {"UserPoolId": user_pool_id, "Username": username, "GroupName": group},
    )


@contextlib.contextmanager
def temporary_enrollment_client(
    aws: AwsApi,
    *,
    user_pool_id: str,
    clock: Callable[[], float] = time.time,
) -> Iterator[str]:
    response = aws.call(
        "cognito-idp",
        "create-user-pool-client",
        {
            "UserPoolId": user_pool_id,
            "ClientName": (
                f"compass-demo-enrollment-{int(clock())}-{secrets.token_hex(6)}"
            ),
            "GenerateSecret": False,
            "ExplicitAuthFlows": ["ALLOW_USER_PASSWORD_AUTH"],
            "PreventUserExistenceErrors": "ENABLED",
            "AuthSessionValidity": 3,
        },
    )
    client = _require_mapping(response, "UserPoolClient", "create-user-pool-client")
    client_id = client.get("ClientId")
    if not isinstance(client_id, str) or not client_id:
        raise AwsCallError("create-user-pool-client", "InvalidResponse")

    try:
        if "ClientSecret" in client:
            raise ProvisioningError("The temporary enrollment client returned a secret")
        if client.get("GenerateSecret") not in {None, False}:
            raise ProvisioningError("The temporary enrollment client is not public")
        if client.get("ExplicitAuthFlows") != ["ALLOW_USER_PASSWORD_AUTH"]:
            raise ProvisioningError("The temporary enrollment client has unsafe auth flows")
        yield client_id
    finally:
        try:
            aws.call(
                "cognito-idp",
                "delete-user-pool-client",
                {"UserPoolId": user_pool_id, "ClientId": client_id},
            )
        except Exception as error:
            raise ProvisioningError(
                "The temporary enrollment client could not be removed"
            ) from error


def _require_session(response: Mapping[str, Any], operation: str) -> str:
    session_value = response.get("Session")
    if not isinstance(session_value, str) or not session_value:
        raise AwsCallError(operation, "InvalidResponse")
    return session_value


def _require_authentication_result(response: Mapping[str, Any]) -> None:
    if not isinstance(response.get("AuthenticationResult"), dict):
        raise ProvisioningError("Cognito did not complete the authentication challenge")


def enroll_identity(
    aws: AwsApi,
    *,
    user_pool_id: str,
    client_id: str,
    identity: MutableMapping[str, Any],
    shared_password: str,
    state: MutableMapping[str, Any],
    store: CredentialStore,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    username = identity["username"]
    initial = aws.call(
        "cognito-idp",
        "initiate-auth",
        {
            "ClientId": client_id,
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {"USERNAME": username, "PASSWORD": shared_password},
        },
    )
    challenge = initial.get("ChallengeName")
    if challenge == "MFA_SETUP":
        initial_session = _require_session(initial, "initiate-auth")
        association = aws.call(
            "cognito-idp",
            "associate-software-token",
            {"Session": initial_session},
        )
        secret_value = normalize_totp_secret(association.get("SecretCode"))
        other_secrets = {
            item.get("totp_secret")
            for item in state["identities"]
            if item is not identity and item.get("totp_secret") is not None
        }
        if secret_value in other_secrets:
            raise ProvisioningError("Cognito returned a duplicate TOTP factor")
        association_session = _require_session(
            association,
            "associate-software-token",
        )
        identity["totp_secret"] = secret_value
        identity["enrollment_status"] = "pending"
        state["status"] = "in_progress"
        store.save(state)

        verification = aws.call(
            "cognito-idp",
            "verify-software-token",
            {
                "Session": association_session,
                "UserCode": stable_totp(
                    secret_value,
                    clock=clock,
                    sleeper=sleeper,
                ),
                "FriendlyDeviceName": "Compass demo",
            },
        )
        if verification.get("Status") != "SUCCESS":
            raise ProvisioningError("Cognito did not verify a TOTP factor")
        verification_session = _require_session(
            verification,
            "verify-software-token",
        )
        completed = aws.call(
            "cognito-idp",
            "respond-to-auth-challenge",
            {
                "ClientId": client_id,
                "ChallengeName": "MFA_SETUP",
                "ChallengeResponses": {"USERNAME": username},
                "Session": verification_session,
            },
        )
        _require_authentication_result(completed)
    elif challenge == "SOFTWARE_TOKEN_MFA":
        existing_secret = identity.get("totp_secret")
        if existing_secret is None:
            raise ProvisioningError(
                "An existing MFA factor has no matching protected credential"
            )
        challenge_session = _require_session(initial, "initiate-auth")
        completed = aws.call(
            "cognito-idp",
            "respond-to-auth-challenge",
            {
                "ClientId": client_id,
                "ChallengeName": "SOFTWARE_TOKEN_MFA",
                "ChallengeResponses": {
                    "USERNAME": username,
                    "SOFTWARE_TOKEN_MFA_CODE": stable_totp(
                        existing_secret,
                        clock=clock,
                        sleeper=sleeper,
                    ),
                },
                "Session": challenge_session,
            },
        )
        _require_authentication_result(completed)
    else:
        raise ProvisioningError("Cognito returned an unexpected authentication state")

    aws.call(
        "cognito-idp",
        "admin-set-user-mfa-preference",
        {
            "UserPoolId": user_pool_id,
            "Username": username,
            "SoftwareTokenMfaSettings": {
                "Enabled": True,
                "PreferredMfa": True,
            },
        },
    )
    verified_user = aws.call(
        "cognito-idp",
        "admin-get-user",
        {"UserPoolId": user_pool_id, "Username": username},
    )
    mfa_settings = verified_user.get("UserMFASettingList", [])
    if (
        verified_user.get("Enabled") is not True
        or verified_user.get("UserStatus") != "CONFIRMED"
        or not isinstance(mfa_settings, list)
        or "SOFTWARE_TOKEN_MFA" not in mfa_settings
    ):
        raise ProvisioningError("The enrolled identity did not pass final verification")

    identity["enrollment_status"] = "complete"
    state["status"] = (
        "complete"
        if all(
            item.get("enrollment_status") == "complete"
            for item in state["identities"]
        )
        else "in_progress"
    )
    store.save(state)


def provision_identities(
    aws: AwsApi,
    store: CredentialStore,
    *,
    stack_name: str,
    expected_account: str,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
    reporter: Callable[[str], None] = print,
) -> None:
    verify_account(aws, expected_account)
    user_pool_id = resolve_user_pool(aws, stack_name)

    with store.locked():
        state = store.load_or_initialize()
        shared_password = state["shared_password"]
        for index, identity in enumerate(state["identities"], start=1):
            reporter(f"Preparing identity {index} of {len(IDENTITY_CONTRACT)}")
            ensure_user(
                aws,
                user_pool_id=user_pool_id,
                username=identity["username"],
                group=identity["group"],
                password=shared_password,
            )

        with temporary_enrollment_client(
            aws,
            user_pool_id=user_pool_id,
            clock=clock,
        ) as client_id:
            for index, identity in enumerate(state["identities"], start=1):
                enroll_identity(
                    aws,
                    user_pool_id=user_pool_id,
                    client_id=client_id,
                    identity=identity,
                    shared_password=shared_password,
                    state=state,
                    store=store,
                    clock=clock,
                    sleeper=sleeper,
                )
                reporter(f"Identity {index} of {len(IDENTITY_CONTRACT)} is ready")

        _validate_state(state)
        if state["status"] != "complete":
            raise ProvisioningError("Identity provisioning did not reach a complete state")


@contextlib.contextmanager
def termination_guard() -> Iterator[None]:
    def interrupt(_signum: int, _frame: object) -> None:
        raise InterruptedProvisioning("Provisioning was interrupted")

    previous_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def _parse_args(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision the protected Compass demo identities",
    )
    parser.add_argument("--stack", default="compass-demo")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Route legacy direct execution to the current optional-MFA posture."""
    repository_root = Path(__file__).resolve().parents[1]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.configure_demo_identity_posture import main as posture_main

    return posture_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())

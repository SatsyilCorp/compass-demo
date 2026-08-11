#!/usr/bin/env python3
"""Prepare, verify, or release fixed synthetic fixtures for the Compass demo.

This operator tool uses only the AWS CLI and the Python standard library. It
never creates a Cognito user, changes a password, changes group membership, or
displays a physical bucket name. All database writes run through the private
migrator Lambda and are bounded by its source-controlled synthetic allowlists.

Examples:

  python3 scripts/prepare_demo.py prepare --stack compass-demo \
    --confirm-synthetic-reset --receipt artifacts/demo-preflight.json

  python3 scripts/prepare_demo.py check --stack compass-demo \
    --receipt artifacts/demo-preflight.json

  python3 scripts/prepare_demo.py release-drop good --stack compass-demo
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATOR_DIR = REPO_ROOT / "src" / "functions" / "migrator"
sys.path.insert(0, str(MIGRATOR_DIR))
import demo_prep as contract  # noqa: E402


LOCAL_FIXTURES: Mapping[str, Path] = {
    "portfolio": REPO_ROOT / "seed" / "grants_portfolio.json",
    "licenses": REPO_ROOT / "seed" / "licenses.json",
    "drop_good": REPO_ROOT / "seed" / "drops" / "drop_good.json",
    "drop_compatible": REPO_ROOT / "seed" / "drops" / "drop_compatible_variant.json",
    "drop_bad": REPO_ROOT / "seed" / "drops" / "drop_incompatible_bad.json",
}

DROP_NAMES: Mapping[str, tuple[str, str]] = {
    "good": (contract.STAGED_FIXTURES["drop_good"], "drops/drop_good.json"),
    "compatible": (
        contract.STAGED_FIXTURES["drop_compatible"],
        "drops/drop_compatible_variant.json",
    ),
    "bad": (contract.STAGED_FIXTURES["drop_bad"], "drops/drop_incompatible_bad.json"),
}

EXPECTED_IDENTITIES: Mapping[str, str] = {
    "poweruser@compass.demo": "compass-poweruser",
    "reviewer@compass.demo": "compass-poweruser",
    "viewer@compass.demo": "compass-viewer",
}
SUPPORTED_GROUPS = frozenset(EXPECTED_IDENTITIES.values())
CONFIRMATION = "RESET_FIXED_SYNTHETIC_DEMO_DATA"


class OperatorError(RuntimeError):
    """Safe-to-display operator failure without raw AWS identifiers."""

    def __init__(self, message: str, *, stage: str):
        super().__init__(message)
        self.stage = stage


def _aws(
    args: Sequence[str],
    *,
    region: str,
    stage: str,
    expect_json: bool = True,
) -> Any:
    command = ["aws", *args, "--region", region, "--no-cli-pager"]
    env = dict(os.environ)
    env["AWS_PAGER"] = ""
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OperatorError("AWS CLI is not installed", stage=stage) from exc
    if completed.returncode:
        raise OperatorError(f"AWS operation failed during {stage}", stage=stage)
    if not expect_json or not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise OperatorError(f"AWS returned an invalid response during {stage}", stage=stage) from exc


def _stack_resources(stack: str, region: str) -> Dict[str, str]:
    response = _aws(
        [
            "cloudformation",
            "describe-stacks",
            "--stack-name",
            stack,
            "--output",
            "json",
        ],
        region=region,
        stage="stack discovery",
    )
    stacks = response.get("Stacks") or []
    if len(stacks) != 1:
        raise OperatorError("deployed stack was not found uniquely", stage="stack discovery")
    outputs = {
        item.get("OutputKey"): item.get("OutputValue")
        for item in stacks[0].get("Outputs", [])
    }
    output_contract = {
        "RawBucket": "RawBucketName",
        "UserPool": "UserPoolId",
        "MigratorFunction": "MigratorFunctionName",
        "AnalyticsFunction": "AnalyticsFunctionName",
    }
    missing = [
        output_key
        for output_key in output_contract.values()
        if not outputs.get(output_key)
    ]
    if missing:
        raise OperatorError(
            "deployed stack is missing required demo preparation outputs",
            stage="stack discovery",
        )
    return {
        logical_name: str(outputs[output_key])
        for logical_name, output_key in output_contract.items()
    }


def _load_local_fixtures() -> Dict[str, Dict[str, Any]]:
    loaded: Dict[str, Dict[str, Any]] = {}
    for logical_name, path in LOCAL_FIXTURES.items():
        if not path.is_file():
            raise OperatorError(f"missing local fixture {path.relative_to(REPO_ROOT)}", stage="fixture validation")
        body = path.read_bytes()
        try:
            payload = json.loads(body)
            contract.validate_fixture(logical_name, payload)
        except (json.JSONDecodeError, contract.DemoPreparationError) as exc:
            raise OperatorError(f"local fixture {logical_name} failed its synthetic contract", stage="fixture validation") from exc
        loaded[logical_name] = {
            "path": path,
            "payload": payload,
            "sha256": hashlib.sha256(body).hexdigest(),
            "size_bytes": len(body),
        }
    return loaded


def _verify_identities(user_pool_id: str, region: str) -> list[Dict[str, Any]]:
    receipts = []
    for username, expected_group in EXPECTED_IDENTITIES.items():
        user = _aws(
            [
                "cognito-idp",
                "admin-get-user",
                "--user-pool-id",
                user_pool_id,
                "--username",
                username,
                "--output",
                "json",
            ],
            region=region,
            stage=f"identity verification for {username}",
        )
        group_response = _aws(
            [
                "cognito-idp",
                "admin-list-groups-for-user",
                "--user-pool-id",
                user_pool_id,
                "--username",
                username,
                "--output",
                "json",
            ],
            region=region,
            stage=f"group verification for {username}",
        )
        supported_memberships = {
            group.get("GroupName")
            for group in group_response.get("Groups", [])
            if group.get("GroupName") in SUPPORTED_GROUPS
        }
        mfa_settings = set(user.get("UserMFASettingList") or [])
        ready = (
            user.get("Enabled") is True
            and user.get("UserStatus") == "CONFIRMED"
            and supported_memberships == {expected_group}
            and "SOFTWARE_TOKEN_MFA" in mfa_settings
        )
        receipts.append(
            {
                "username": username,
                "status": "ready" if ready else "not_ready",
                "enabled": user.get("Enabled") is True,
                "confirmed": user.get("UserStatus") == "CONFIRMED",
                "expected_group": expected_group,
                "supported_groups": sorted(supported_memberships),
                "totp_enrolled": "SOFTWARE_TOKEN_MFA" in mfa_settings,
            }
        )
    if not all(item["status"] == "ready" for item in receipts):
        raise OperatorError(
            "one or more fixed demo identities are not confirmed, uniquely grouped, and TOTP-enabled",
            stage="identity verification",
        )
    return receipts


def _stage_fixtures(
    bucket: str,
    local: Mapping[str, Mapping[str, Any]],
    region: str,
) -> list[Dict[str, Any]]:
    receipts = []
    for logical_name, key in contract.STAGED_FIXTURES.items():
        fixture = local[logical_name]
        metadata = json.dumps(
            {
                "fixture-sha256": fixture["sha256"],
                "synthetic-only": "true",
                "fixture-contract": contract.FIXTURE_CONTRACT,
            },
            separators=(",", ":"),
        )
        _aws(
            [
                "s3api",
                "put-object",
                "--bucket",
                bucket,
                "--key",
                key,
                "--body",
                str(fixture["path"]),
                "--content-type",
                "application/json",
                "--metadata",
                metadata,
                "--output",
                "json",
            ],
            region=region,
            stage=f"staging {logical_name}",
        )
        receipts.append(
            {
                "logical_name": logical_name,
                "logical_locator": f"staged://{logical_name}",
                "sha256": fixture["sha256"],
                "size_bytes": fixture["size_bytes"],
                "status": "staged",
            }
        )
    return receipts


def _object_exists(bucket: str, key: str, region: str, *, stage: str) -> bool:
    command = [
        "aws",
        "s3api",
        "head-object",
        "--bucket",
        bucket,
        "--key",
        key,
        "--region",
        region,
        "--no-cli-pager",
        "--output",
        "json",
    ]
    env = dict(os.environ)
    env["AWS_PAGER"] = ""
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OperatorError("AWS CLI is not installed", stage=stage) from exc
    if completed.returncode == 0:
        return True
    stderr = completed.stderr.lower()
    if "not found" in stderr or "404" in stderr or "nosuchkey" in stderr:
        return False
    raise OperatorError(f"AWS operation failed during {stage}", stage=stage)


def _clear_live_drop_keys(bucket: str, region: str) -> None:
    objects = [{"Key": target_key} for _, target_key in DROP_NAMES.values()]
    _aws(
        [
            "s3api",
            "delete-objects",
            "--bucket",
            bucket,
            "--delete",
            json.dumps({"Objects": objects, "Quiet": True}, separators=(",", ":")),
            "--output",
            "json",
        ],
        region=region,
        stage="clearing fixed live drop keys",
    )


def _live_drop_receipts(bucket: str, region: str) -> list[Dict[str, Any]]:
    receipts = []
    for name, (_, target_key) in DROP_NAMES.items():
        exists = _object_exists(
            bucket,
            target_key,
            region,
            stage=f"checking live {name} drop",
        )
        receipts.append(
            {
                "name": name,
                "logical_locator": f"landing://{target_key}",
                "status": "present" if exists else "absent",
                "not_ingested_before_recording": not exists,
            }
        )
    return receipts


def _invoke(function_name: str, payload: Mapping[str, Any], region: str, *, stage: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="compass-demo-invoke-") as tmp:
        payload_path = Path(tmp) / "payload.json"
        response_path = Path(tmp) / "response.json"
        payload_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        meta = _aws(
            [
                "lambda",
                "invoke",
                "--function-name",
                function_name,
                "--payload",
                f"fileb://{payload_path}",
                "--cli-binary-format",
                "raw-in-base64-out",
                str(response_path),
                "--output",
                "json",
            ],
            region=region,
            stage=stage,
        )
        if meta.get("StatusCode") != 200 or meta.get("FunctionError"):
            raise OperatorError(f"Lambda failed during {stage}", stage=stage)
        try:
            response = json.loads(response_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OperatorError(f"Lambda returned an invalid response during {stage}", stage=stage) from exc
        if not isinstance(response, dict) or response.get("status") == "error":
            raise OperatorError(f"Lambda rejected the {stage} operation", stage=stage)
        return response


def _migrate(migrator: str, region: str) -> Dict[str, Any]:
    response = _invoke(migrator, {"migrate": "all"}, region, stage="database migrations")
    if response.get("status") != "ok" or (response.get("role_bootstrap") or {}).get("status") != "granted":
        raise OperatorError("database migrations did not establish the runtime role", stage="database migrations")
    return {
        "status": "ready",
        "applied": response.get("applied"),
        "total": response.get("total"),
        "runtime_role": "granted",
    }


def _analytics_event() -> Dict[str, Any]:
    return {
        "action": "prepare_demo_baseline",
        "k": 8,
        "seed": contract.GENERATOR_SEED,
    }


def _run_analytics(analytics_function: str, region: str) -> Dict[str, Any]:
    raw = _invoke(
        analytics_function,
        _analytics_event(),
        region,
        stage="baseline analytics",
    )
    if raw.get("status") != "ok":
        raise OperatorError("baseline analytics did not complete", stage="baseline analytics")
    body = raw.get("analytics") or {}
    metrics = body.get("metrics") or {}
    if (
        body.get("status") != "completed"
        or metrics.get("n_docs") != contract.BASELINE_RECORD_COUNT
        or metrics.get("k") != 8
        or not body.get("run_id")
    ):
        raise OperatorError("baseline analytics did not model the fixed baseline", stage="baseline analytics")
    return {
        "run_id": body["run_id"],
        "status": "completed",
        "n_docs": metrics["n_docs"],
        "k": metrics["k"],
        "topics_returned": len(body.get("topics") or []),
    }


def _compare_fixture_receipts(
    local: Mapping[str, Mapping[str, Any]],
    remote: Sequence[Mapping[str, Any]],
) -> bool:
    by_name = {str(item.get("logical_name")): item for item in remote}
    return all(
        by_name.get(name, {}).get("status") == "validated"
        and by_name[name].get("sha256") == fixture["sha256"]
        for name, fixture in local.items()
    )


def _base_receipt(args, command: str) -> Dict[str, Any]:
    return {
        "schema_version": contract.PREFLIGHT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "stack": args.stack,
        "region": args.region,
        "status": "not_ready",
        "ready": False,
        "storage_disclosure": "logical locators only",
    }


def _write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare(args) -> Dict[str, Any]:
    if args.confirm_synthetic_reset != CONFIRMATION:
        raise OperatorError(
            f"prepare requires --confirm-synthetic-reset {CONFIRMATION}",
            stage="confirmation",
        )
    local = _load_local_fixtures()
    resources = _stack_resources(args.stack, args.region)
    identities = _verify_identities(resources["UserPool"], args.region)
    staged = _stage_fixtures(resources["RawBucket"], local, args.region)
    _clear_live_drop_keys(resources["RawBucket"], args.region)
    live_drop_keys = _live_drop_receipts(resources["RawBucket"], args.region)
    if not all(item["status"] == "absent" for item in live_drop_keys):
        raise OperatorError("one or more fixed live drop keys remain present", stage="drop staging")

    migrations = _migrate(resources["MigratorFunction"], args.region)
    baseline = _invoke(
        resources["MigratorFunction"],
        {"demo_action": "prepare"},
        args.region,
        stage="synthetic baseline reseed",
    )
    analytics = _run_analytics(resources["AnalyticsFunction"], args.region)
    finalized = _invoke(
        resources["MigratorFunction"],
        {"demo_action": "finalize", "analytics_run_id": analytics["run_id"]},
        args.region,
        stage="analytics finalization",
    )
    preflight = _invoke(
        resources["MigratorFunction"],
        {"demo_action": "preflight"},
        args.region,
        stage="database preflight",
    )
    fixtures_match = _compare_fixture_receipts(local, preflight.get("fixtures") or [])
    ready = (
        preflight.get("ready") is True
        and fixtures_match
        and all(item["status"] == "ready" for item in identities)
        and all(item["status"] == "absent" for item in live_drop_keys)
        and finalized.get("status") == "analytics_ready"
    )
    receipt = _base_receipt(args, "prepare")
    receipt.update(
        {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "fixture_contract": contract.FIXTURE_CONTRACT,
            "identities": identities,
            "staged_fixtures": staged,
            "live_drop_keys": live_drop_keys,
            "migrations": migrations,
            "baseline": baseline,
            "analytics": {
                **analytics,
                "topics_persisted": finalized.get("topics"),
                "topic_assignments": finalized.get("topic_assignments"),
            },
            "checks": preflight.get("checks") or [],
            "fixture_hashes_match": fixtures_match,
        }
    )
    return receipt


def _check_only(args) -> Dict[str, Any]:
    local = _load_local_fixtures()
    resources = _stack_resources(args.stack, args.region)
    identities = _verify_identities(resources["UserPool"], args.region)
    live_drop_keys = _live_drop_receipts(resources["RawBucket"], args.region)
    preflight = _invoke(
        resources["MigratorFunction"],
        {"demo_action": "preflight"},
        args.region,
        stage="database preflight",
    )
    fixtures_match = _compare_fixture_receipts(local, preflight.get("fixtures") or [])
    ready = (
        preflight.get("ready") is True
        and fixtures_match
        and all(item["status"] == "ready" for item in identities)
        and all(item["status"] == "absent" for item in live_drop_keys)
    )
    receipt = _base_receipt(args, "check")
    receipt.update(
        {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "fixture_contract": contract.FIXTURE_CONTRACT,
            "identities": identities,
            "staged_fixtures": preflight.get("fixtures") or [],
            "live_drop_keys": live_drop_keys,
            "analytics_run_id": preflight.get("analytics_run_id"),
            "checks": preflight.get("checks") or [],
            "fixture_hashes_match": fixtures_match,
        }
    )
    return receipt


def _release_drop(args) -> Dict[str, Any]:
    local = _load_local_fixtures()
    resources = _stack_resources(args.stack, args.region)
    source_key, target_key = DROP_NAMES[args.drop_name]
    bucket = resources["RawBucket"]
    if _object_exists(bucket, target_key, args.region, stage="release guard") and not args.allow_redrop:
        raise OperatorError(
            "live drop key already exists; run prepare or pass --allow-redrop for a deliberate retry",
            stage="release guard",
        )
    logical_name = {
        "good": "drop_good",
        "compatible": "drop_compatible",
        "bad": "drop_bad",
    }[args.drop_name]
    fixture = local[logical_name]
    metadata = json.dumps(
        {
            "fixture-sha256": fixture["sha256"],
            "synthetic-only": "true",
            "fixture-contract": contract.FIXTURE_CONTRACT,
        },
        separators=(",", ":"),
    )
    with tempfile.TemporaryDirectory(prefix="compass-demo-release-") as tmp:
        staged_path = Path(tmp) / "staged.fixture"
        staged_response = _aws(
            [
                "s3api",
                "get-object",
                "--bucket",
                bucket,
                "--key",
                source_key,
                str(staged_path),
                "--output",
                "json",
            ],
            region=args.region,
            stage=f"validating staged {args.drop_name} drop",
        )
        staged_bytes = staged_path.read_bytes()
        staged_hash = hashlib.sha256(staged_bytes).hexdigest()
        staged_metadata = staged_response.get("Metadata") or {}
        try:
            staged_payload = json.loads(staged_bytes)
            contract.validate_fixture(logical_name, staged_payload)
        except (json.JSONDecodeError, contract.DemoPreparationError) as exc:
            raise OperatorError(
                "staged drop failed its synthetic fixture contract",
                stage="release integrity check",
            ) from exc
        if (
            staged_hash != fixture["sha256"]
            or staged_metadata.get("fixture-sha256") != staged_hash
            or staged_metadata.get("synthetic-only") != "true"
        ):
            raise OperatorError(
                "staged drop no longer matches the validated local fixture",
                stage="release integrity check",
            )
        release_args = [
            "s3api",
            "put-object",
            "--bucket",
            bucket,
            "--key",
            target_key,
            "--body",
            str(staged_path),
            "--metadata",
            metadata,
            "--content-type",
            "application/json",
        ]
        if not args.allow_redrop:
            release_args.extend(["--if-none-match", "*"])
        release_args.extend(["--output", "json"])
        _aws(
            release_args,
            region=args.region,
            stage=f"releasing {args.drop_name} drop",
        )
    return {
        "schema_version": contract.PREFLIGHT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": "release-drop",
        "stack": args.stack,
        "region": args.region,
        "status": "released",
        "drop": args.drop_name,
        "logical_source": f"staged://{logical_name}",
        "logical_target": f"landing://{target_key}",
        "sha256": fixture["sha256"],
        "redrop": bool(args.allow_redrop),
        "storage_disclosure": "logical locators only",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--stack", default="compass-demo", help="CloudFormation stack name")
    common.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    common.add_argument(
        "--receipt",
        type=Path,
        default=REPO_ROOT / "artifacts" / "demo-preflight.json",
        help="redacted machine-readable receipt path",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", parents=[common], help="reset and reseed fixed synthetic demo state")
    prepare.add_argument(
        "--confirm-synthetic-reset",
        metavar="CONFIRMATION",
        help=f"required exact value: {CONFIRMATION}",
    )
    subparsers.add_parser("check", parents=[common], help="read-only demo readiness check")
    release = subparsers.add_parser("release-drop", parents=[common], help="release one staged fixture into the live ingest prefix")
    release.add_argument("drop_name", choices=sorted(DROP_NAMES))
    release.add_argument(
        "--allow-redrop",
        action="store_true",
        help="deliberately copy over an existing live drop key",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            receipt = _prepare(args)
        elif args.command == "check":
            receipt = _check_only(args)
        else:
            receipt = _release_drop(args)
        if args.command != "release-drop":
            _write_receipt(args.receipt, receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt.get("status") in {"ready", "released"} else 1
    except OperatorError as exc:
        receipt = _base_receipt(args, args.command)
        receipt.update(
            {
                "status": "error",
                "ready": False,
                "failed_stage": exc.stage,
                "error": str(exc),
            }
        )
        if args.command != "release-drop":
            _write_receipt(args.receipt, receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

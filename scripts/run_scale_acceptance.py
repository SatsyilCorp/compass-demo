#!/usr/bin/env python3
"""Run a live, cost-gated Scale Run and save a sanitized acceptance receipt.

The driver invokes the deployed control Lambda with IAM and an HTTP API v2
event. This exercises the same authorization and route handler used by API
Gateway while avoiding storage of a Cognito password or TOTP secret in an
unattended test process.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any
import uuid


TERMINAL_RUN_STATES = {"completed", "cancelled", "failed"}
TERMINAL_EXPORT_STATES = {"ready", "cancelled"}


class AcceptanceError(RuntimeError):
    pass


def _aws(args: argparse.Namespace, *parts: str) -> str:
    command = [
        "aws",
        "--profile",
        args.aws_profile,
        *parts,
        "--region",
        args.region,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise AcceptanceError(f"AWS command failed: {message}")
    return result.stdout.strip()


def _stack_output(args: argparse.Namespace, key: str) -> str:
    query = f"Stacks[0].Outputs[?OutputKey==`{key}`].OutputValue | [0]"
    value = _aws(
        args,
        "cloudformation",
        "describe-stacks",
        "--stack-name",
        args.stack,
        "--query",
        query,
        "--output",
        "text",
    )
    if not value or value == "None":
        raise AcceptanceError(f"stack output {key} is missing")
    return value


def _http_event(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    run_id: str | None = None,
    export_id: str | None = None,
) -> dict[str, Any]:
    path_parameters = {}
    if run_id:
        path_parameters["run_id"] = run_id
    if export_id:
        path_parameters["export_id"] = export_id
    return {
        "version": "2.0",
        "requestContext": {
            "stage": "prod",
            "http": {"method": method, "path": f"/prod{path}"},
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "scale-acceptance-runner",
                        "username": "scale-acceptance-runner",
                        "email": "scale-acceptance@compass.demo",
                        "cognito:groups": '["compass-poweruser"]',
                    }
                }
            },
        },
        "pathParameters": path_parameters or None,
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def _invoke(
    args: argparse.Namespace,
    function_name: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="compass-scale-acceptance-") as temp:
        temp_path = Path(temp)
        payload_path = temp_path / "payload.json"
        output_path = temp_path / "response.json"
        payload_path.write_text(json.dumps(event), encoding="utf-8")
        metadata_text = _aws(
            args,
            "lambda",
            "invoke",
            "--function-name",
            function_name,
            "--cli-binary-format",
            "raw-in-base64-out",
            "--payload",
            f"fileb://{payload_path}",
            str(output_path),
            "--output",
            "json",
        )
        metadata = json.loads(metadata_text or "{}")
        response = json.loads(output_path.read_text(encoding="utf-8"))
    if metadata.get("FunctionError"):
        raise AcceptanceError(f"Lambda function error: {response}")
    status = int(response.get("statusCode", 500))
    raw_body = response.get("body") or "{}"
    body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    if status >= 400:
        raise AcceptanceError(f"HTTP {status}: {body}")
    if not isinstance(body, dict):
        raise AcceptanceError("Scale control returned a non-object response")
    return body


def _get_run(
    args: argparse.Namespace,
    function_name: str,
    run_id: str,
) -> dict[str, Any]:
    return _invoke(
        args,
        function_name,
        _http_event(
            "GET",
            f"/scale/runs/{run_id}",
            run_id=run_id,
        ),
    )


def _wait_for_run(
    args: argparse.Namespace,
    function_name: str,
    run_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + args.timeout_seconds
    last_stage = None
    while time.monotonic() < deadline:
        run = _get_run(args, function_name, run_id)
        progress = run.get("progress") or {}
        stage = progress.get("stage")
        status = str(run.get("status") or "")
        marker = (status, stage, progress.get("partitions_completed"))
        if marker != last_stage:
            print(
                f"run={run_id} status={status} stage={stage} "
                f"progress={progress.get('percent', 0)}% "
                f"partitions={progress.get('partitions_completed', 0)}/"
                f"{progress.get('partitions_total', 0)}",
                flush=True,
            )
            last_stage = marker
        if status in TERMINAL_RUN_STATES:
            return run
        time.sleep(args.poll_seconds)
    raise AcceptanceError(f"Scale Run {run_id} did not finish before timeout")


def _wait_for_export(
    args: argparse.Namespace,
    function_name: str,
    run_id: str,
    export_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + args.export_timeout_seconds
    while time.monotonic() < deadline:
        receipt = _invoke(
            args,
            function_name,
            _http_event(
                "GET",
                f"/scale/runs/{run_id}/exports/{export_id}",
                run_id=run_id,
                export_id=export_id,
            ),
        )
        status = str(receipt.get("status") or "")
        print(f"export={export_id} status={status}", flush=True)
        if status in TERMINAL_EXPORT_STATES:
            return receipt
        time.sleep(args.poll_seconds)
    raise AcceptanceError(f"Export Job {export_id} did not finish before timeout")


def _sanitized_export(receipt: dict[str, Any] | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    result = dict(receipt)
    result["download_url"] = None
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack", default="compass-demo")
    parser.add_argument("--aws-profile", default="satsyil")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--workload", choices=("1k", "10k", "100k", "1m"), required=True)
    parser.add_argument("--seed", type=int, default=20260811)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--export-timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    function_name = _stack_output(args, "ScaleRunsFunctionName")
    started_at = datetime.now(timezone.utc)
    plan = _invoke(
        args,
        function_name,
        _http_event(
            "POST",
            "/scale/plans",
            body={"profile_id": args.workload, "seed": args.seed},
        ),
    )
    if plan.get("capacity_state") != "ready":
        raise AcceptanceError(f"profile is not ready: {plan.get('capacity_state')}")
    run = _invoke(
        args,
        function_name,
        _http_event(
            "POST",
            "/scale/runs",
            body={
                "plan_id": plan["plan_id"],
                "idempotency_key": f"acceptance-{args.workload}-{uuid.uuid4().hex}",
            },
        ),
    )
    terminal = _wait_for_run(args, function_name, str(run["run_id"]))
    if terminal.get("status") != "completed":
        raise AcceptanceError(
            f"Scale Run ended as {terminal.get('status')}: {terminal.get('error')}"
        )

    export = None
    if not args.skip_export:
        queued = _invoke(
            args,
            function_name,
            _http_event(
                "POST",
                f"/scale/runs/{terminal['run_id']}/exports",
                run_id=str(terminal["run_id"]),
                body={
                    "dataset": "curated_portfolio",
                    "format": "parquet",
                    "idempotency_key": f"acceptance-export-{uuid.uuid4().hex}",
                },
            ),
        )
        export = _wait_for_export(
            args,
            function_name,
            str(terminal["run_id"]),
            str(queued["export_id"]),
        )
        if export.get("status") != "ready":
            raise AcceptanceError(f"Export Job ended as {export.get('status')}")

    completed_at = datetime.now(timezone.utc)
    receipt = {
        "contract_version": "compass.scale-acceptance.v1",
        "transport": "iam_direct_lambda_http_event",
        "disclosure": (
            "The live data plane and HTTP route handler were exercised with IAM. "
            "Interactive Cognito and TOTP sign-in is verified separately."
        ),
        "stack": args.stack,
        "region": args.region,
        "workload": args.workload,
        "seed": args.seed,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "wall_seconds": round((completed_at - started_at).total_seconds(), 3),
        "plan": plan,
        "run": terminal,
        "export": _sanitized_export(export),
    }
    receipt_path = args.receipt or Path("artifacts/scale") / f"{args.workload}-acceptance.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"acceptance receipt: {receipt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

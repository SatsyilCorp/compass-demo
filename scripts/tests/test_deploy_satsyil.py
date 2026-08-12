from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def make_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_fresh_ha_deployment_uses_recoverable_then_protected_pass(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    fake_bin = tmp_path / "bin"
    deploy_log = tmp_path / "sam-deploy.jsonl"
    (repository / "scripts").mkdir(parents=True)
    fake_bin.mkdir()
    shutil.copy2(
        REPOSITORY_ROOT / "scripts" / "deploy_satsyil.sh",
        repository / "scripts" / "deploy_satsyil.sh",
    )
    (repository / "samconfig-satsyil.toml").write_text(
        "version = 0.1\n",
        encoding="utf-8",
    )

    successful_stub = "#!/usr/bin/env sh\nset -eu\nexit 0\n"
    for relative_path in (
        "src/functions/migrator/prepare_migrations.sh",
        "src/functions/rmf_artifact/prepare_template.sh",
        "scripts/migrate.sh",
        "scripts/build-frontend.sh",
        "scripts/upload-to-cloudfront.sh",
    ):
        make_executable(repository / relative_path, successful_stub)

    make_executable(
        fake_bin / "aws",
        """#!/usr/bin/env python3
import os
import sys

arguments = sys.argv[1:]
joined = " ".join(arguments)
if "get-caller-identity" in arguments:
    print(os.environ["DEPLOY_TEST_ACCOUNT"])
elif "describe-stacks" in arguments and "Stacks[0].StackStatus" in arguments:
    print(
        "An error occurred (ValidationError) when calling the DescribeStacks "
        "operation: stack does not exist",
        file=sys.stderr,
    )
    raise SystemExit(255)
elif "describe-stacks" in arguments:
    print("demo.invalid")
elif "describe-vpcs" in arguments or "describe-addresses" in arguments:
    print("0")
elif "get-service-quota" in arguments:
    print("5")
else:
    raise SystemExit(f"unexpected AWS mock call: {joined}")
""",
    )
    make_executable(
        fake_bin / "sam",
        """#!/usr/bin/env python3
import json
import os
import sys

if sys.argv[1] == "deploy":
    with open(os.environ["DEPLOY_TEST_LOG"], "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(sys.argv[1:]) + "\\n")
""",
    )
    make_executable(fake_bin / "docker", successful_stub)
    make_executable(
        fake_bin / "git",
        """#!/usr/bin/env python3
import os
import sys

arguments = sys.argv[1:]
if arguments == ["rev-parse", "--verify", "HEAD"]:
    print(os.environ["DEPLOY_TEST_REVISION"])
elif arguments == ["status", "--porcelain=v1", "--untracked-files=all"]:
    status = os.environ.get("DEPLOY_TEST_STATUS", "")
    if status:
        print(status)
else:
    raise SystemExit(f"unexpected Git mock call: {' '.join(arguments)}")
""",
    )

    expected_account = "0" * 12
    expected_revision = "a" * 40
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "AWS_PROFILE": "satsyil",
            "AWS_REGION": "us-east-1",
            "SATSYIL_EXPECTED_ACCOUNT_ID": expected_account,
            "DEPLOY_TEST_ACCOUNT": expected_account,
            "DEPLOY_TEST_LOG": str(deploy_log),
            "DEPLOY_TEST_REVISION": expected_revision,
                "DEPLOY_REVISION": expected_revision,
                "PUBLIC_SBIR_EXECUTION_ENABLED": "false",
            "DATABASE_MODE": "ha",
            "WEB_CUSTOM_DOMAIN_NAME": "compass.example",
            "WEB_CERTIFICATE_ARN": "arn:aws:acm:us-east-1:000000000000:certificate/00000000-0000-0000-0000-000000000000",
            "WEB_HOSTED_ZONE_ID": "ZDEMO123456789",
        }
    )
    result = subprocess.run(
        [str(repository / "scripts" / "deploy_satsyil.sh")],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    deploy_calls = [json.loads(line) for line in deploy_log.read_text().splitlines()]
    assert len(deploy_calls) == 2
    assert "DatabaseResilienceMode=demo" in deploy_calls[0]
    assert "DatabaseResilienceMode=ha" in deploy_calls[1]
    assert f"DeployRevision={expected_revision}" in deploy_calls[0]
    assert f"DeployRevision={expected_revision}" in deploy_calls[1]
    assert "PublicSbirExecutionEnabled=false" in deploy_calls[0]
    assert "PublicSbirExecutionEnabled=false" in deploy_calls[1]
    assert "CognitoDomainPrefix=satsyil-compass-demo" in deploy_calls[0]
    assert "CognitoDomainPrefix=satsyil-compass-demo" in deploy_calls[1]
    assert not any(value.startswith("WebOrigin=") for value in deploy_calls[0])
    assert "WebOrigin=https://demo.invalid" in deploy_calls[1]
    assert "WebCallbackUrl=https://compass.example/login/" in deploy_calls[1]
    assert "WebLogoutUrl=https://compass.example/login/" in deploy_calls[1]

    template_text = (REPOSITORY_ROOT / "template.yaml").read_text(encoding="utf-8")
    assert "EnableDatabaseHa: !Equals [!Ref DatabaseResilienceMode, ha]" in template_text
    assert "DeletionProtection: !If [EnableDatabaseHa, true, false]" in template_text


def _run_provenance_rejection(
    tmp_path: Path,
    *,
    head_revision: str,
    supplied_revision: str,
    status: str = "",
) -> subprocess.CompletedProcess[str]:
    repository = tmp_path / "repository"
    fake_bin = tmp_path / "bin"
    (repository / "scripts").mkdir(parents=True)
    fake_bin.mkdir()
    shutil.copy2(
        REPOSITORY_ROOT / "scripts" / "deploy_satsyil.sh",
        repository / "scripts" / "deploy_satsyil.sh",
    )
    make_executable(
        fake_bin / "git",
        """#!/usr/bin/env python3
import os
import sys

arguments = sys.argv[1:]
if arguments == ["rev-parse", "--verify", "HEAD"]:
    print(os.environ["DEPLOY_TEST_REVISION"])
elif arguments == ["status", "--porcelain=v1", "--untracked-files=all"]:
    status = os.environ.get("DEPLOY_TEST_STATUS", "")
    if status:
        print(status)
else:
    raise SystemExit(f"unexpected Git mock call: {' '.join(arguments)}")
""",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "DEPLOY_TEST_REVISION": head_revision,
            "DEPLOY_TEST_STATUS": status,
            "DEPLOY_REVISION": supplied_revision,
        }
    )
    return subprocess.run(
        [str(repository / "scripts" / "deploy_satsyil.sh")],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )


def test_deploy_rejects_revision_that_is_not_exact_head(tmp_path: Path) -> None:
    result = _run_provenance_rejection(
        tmp_path,
        head_revision="a" * 40,
        supplied_revision="b" * 40,
    )

    assert result.returncode != 0
    assert "must exactly equal the full Git commit SHA at HEAD" in result.stderr


def test_deploy_rejects_dirty_source_tree(tmp_path: Path) -> None:
    revision = "a" * 40
    result = _run_provenance_rejection(
        tmp_path,
        head_revision=revision,
        supplied_revision=revision,
        status=" M template.yaml",
    )

    assert result.returncode != 0
    assert "deployment requires a clean Git source tree" in result.stderr
    assert "M template.yaml" in result.stderr


def test_custom_domain_is_managed_by_cloudformation_and_deploy_entrypoint() -> None:
    template_text = (REPOSITORY_ROOT / "template.yaml").read_text(encoding="utf-8")
    deploy_text = (
        REPOSITORY_ROOT / "scripts" / "deploy_satsyil.sh"
    ).read_text(encoding="utf-8")

    assert "WebCustomDomainName:" in template_text
    assert "WebCertificateArn:" in template_text
    assert "WebHostedZoneId:" in template_text
    assert "MinimumProtocolVersion: TLSv1.2_2021" in template_text
    assert "Type: AWS::Route53::RecordSet" in template_text
    assert "HostedZoneId: Z2FDTNDATAQYW2" in template_text
    assert '!Sub "https://${WebCustomDomainName}"' in template_text
    assert '"WebCustomDomainName=$WEB_CUSTOM_DOMAIN_NAME"' in deploy_text
    assert '"WebCertificateArn=$WEB_CERTIFICATE_ARN"' in deploy_text
    assert '"WebHostedZoneId=$WEB_HOSTED_ZONE_ID"' in deploy_text
    assert "must be supplied together" in deploy_text


def test_public_sbir_preflight_uses_the_full_model_package_arn() -> None:
    deploy_text = (
        REPOSITORY_ROOT / "scripts" / "deploy_satsyil.sh"
    ).read_text(encoding="utf-8")

    assert (
        'public_sbir_package_arn="arn:aws:sagemaker:$AWS_REGION:'
        '$SATSYIL_ACCOUNT_ID:model-package/${STACK_NAME}-public-sbir-transition/2"'
        in deploy_text
    )
    assert '--model-package-name "$public_sbir_package_arn"' in deploy_text
    assert '--model-package-name "${STACK_NAME}-public-sbir-transition/2"' not in deploy_text
    assert "sam build \\\n  --use-container \\\n  --no-cached" in deploy_text


def test_lambda_cors_includes_the_configured_custom_domain() -> None:
    template_paths = (
        REPOSITORY_ROOT / "template.yaml",
        REPOSITORY_ROOT / "src" / "functions" / "rmf_artifact" / "template.yaml",
    )
    for template_path in template_paths:
        template_text = template_path.read_text(encoding="utf-8")
        lambda_cors_block = template_text.split(
            "        CORS_ALLOW_ORIGINS:", 1
        )[1].split("\n\nResources:", 1)[0]

        assert "HasWebOrigin" in lambda_cors_block, template_path
        assert "HasWebCustomDomain" in lambda_cors_block, template_path
        assert "${WebOrigin}" in lambda_cors_block, template_path
        assert "https://${WebCustomDomainName}" in lambda_cors_block, template_path
        for expected_allowlist in (
            "http://localhost:3000,http://127.0.0.1:3000",
            "http://localhost:3000,http://127.0.0.1:3000,${WebOrigin}",
            "http://localhost:3000,http://127.0.0.1:3000,https://${WebCustomDomainName}",
            "http://localhost:3000,http://127.0.0.1:3000,${WebOrigin},https://${WebCustomDomainName}",
        ):
            assert expected_allowlist in lambda_cors_block, template_path

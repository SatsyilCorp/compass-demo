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
        "#!/usr/bin/env sh\nset -eu\nprintf '%s\\n' mockrevision\n",
    )

    expected_account = "0" * 12
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "AWS_PROFILE": "satsyil",
            "AWS_REGION": "us-east-1",
            "SATSYIL_EXPECTED_ACCOUNT_ID": expected_account,
            "DEPLOY_TEST_ACCOUNT": expected_account,
            "DEPLOY_TEST_LOG": str(deploy_log),
            "DATABASE_MODE": "ha",
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
    assert "CognitoDomainPrefix=satsyil-compass-demo" in deploy_calls[0]
    assert "CognitoDomainPrefix=satsyil-compass-demo" in deploy_calls[1]
    assert not any(value.startswith("WebOrigin=") for value in deploy_calls[0])
    assert "WebOrigin=https://demo.invalid" in deploy_calls[1]

    template_text = (REPOSITORY_ROOT / "template.yaml").read_text(encoding="utf-8")
    assert "EnableDatabaseHa: !Equals [!Ref DatabaseResilienceMode, ha]" in template_text
    assert "DeletionProtection: !If [EnableDatabaseHa, true, false]" in template_text


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

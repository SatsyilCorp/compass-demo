from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]
SOURCE_TEMPLATE = ROOT / "template.yaml"
BUNDLED_TEMPLATE = ROOT / "src/functions/rmf_artifact/template.yaml"


def test_bundled_rmf_template_matches_deploy_template():
    assert BUNDLED_TEMPLATE.read_bytes() == SOURCE_TEMPLATE.read_bytes()


def test_public_funding_registry_can_reference_an_external_group_without_adoption():
    content = SOURCE_TEMPLATE.read_text(encoding="utf-8")

    assert "ExistingPublicFundingModelPackageGroupArn:" in content
    assert (
        'CreatePublicFundingModelPackageGroup: !Equals '
        '[!Ref ExistingPublicFundingModelPackageGroupArn, ""]' in content
    )
    resource_start = content.index("  PublicFundingModelPackageGroup:\n")
    resource_end = content.index("\n  DocumentSageMakerExecutionRole:", resource_start)
    resource = content[resource_start:resource_end]
    assert "Condition: CreatePublicFundingModelPackageGroup" in resource

    output_start = content.index("  PublicFundingModelPackageGroupName:\n")
    output_end = content.index("\n  DocumentMlFunctionName:", output_start)
    output = content[output_start:output_end]
    assert "CreatePublicFundingModelPackageGroup" in output
    assert "ExistingPublicFundingModelPackageGroupArn" in output


def test_satsyil_deploy_preserves_external_public_funding_registry_reference():
    content = (ROOT / "scripts/deploy_satsyil.sh").read_text(encoding="utf-8")

    assert "EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN" in content
    assert "ExistingPublicFundingModelPackageGroupArn" in content
    assert "describe-model-package-group" in content


def test_operations_topic_policy_is_publish_only():
    content = SOURCE_TEMPLATE.read_text(encoding="utf-8")
    start = content.index("  OperationsTopicPolicy:\n")
    end = content.index("\n  OperationsEmailSubscription:", start)
    policy = content[start:end]

    assert "Action: sns:*" not in policy
    assert policy.count("Action: sns:Publish") == 2


def test_operational_ledger_roles_can_use_its_customer_managed_key():
    content = SOURCE_TEMPLATE.read_text(encoding="utf-8")
    acquisition_start = content.index("  PublicAcquisitionFunction:\n")
    acquisition_end = content.index("\n  PublicAcquisitionScheduleDeadLetterAlarm:", acquisition_start)
    acquisition = content[acquisition_start:acquisition_end]
    operations_start = content.index("  OperationsFunction:\n")
    operations_end = content.index("\n  # --- quality_gate:", operations_start)
    operations = content[operations_start:operations_end]

    for role in (acquisition, operations):
        assert "kms:Decrypt" in role
        assert "kms:GenerateDataKey" in role
        assert "Resource: !GetAtt AppKey.Arn" in role


def test_frontend_publish_paths_exclude_macos_metadata():
    local_deploy = (ROOT / "scripts/upload-to-cloudfront.sh").read_text(encoding="utf-8")
    controlled_deploy = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")

    for entrypoint in (local_deploy, controlled_deploy):
        assert '--exclude ".DS_Store"' in entrypoint
        assert '--exclude "*/.DS_Store"' in entrypoint


@pytest.mark.parametrize(
    "entrypoint",
    (
        "scripts/deploy.sh",
        "scripts/deploy_satsyil.sh",
        ".github/workflows/deploy.yml",
        ".github/workflows/quality.yml",
    ),
)
def test_backend_builds_stage_the_rmf_template(entrypoint):
    content = (ROOT / entrypoint).read_text(encoding="utf-8")
    sync_position = content.find("rmf_artifact/prepare_template.sh")
    build_match = re.search(r"(?m)^\s*(?:run:\s*)?sam build(?:\s|$)", content)

    assert sync_position >= 0, f"{entrypoint} does not stage the RMF template"
    assert build_match is not None, f"{entrypoint} does not build the SAM application"
    assert sync_position < build_match.start(), f"{entrypoint} stages the RMF template after building"

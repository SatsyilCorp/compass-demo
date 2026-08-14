from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_arm_lambda_packages_build_on_a_native_arm_runner() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )
    backend_job = workflow.split("  source-and-backend:", 1)[1].split(
        "\n  frontend:", 1
    )[0]

    assert "runs-on: ubuntu-24.04-arm" in backend_job
    assert "sam build --use-container --cached" in backend_job
    assert "runs-on: ubuntu-latest" not in backend_job


def test_backend_contract_job_installs_the_aws_runtime_sdk_for_test_collection() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )
    backend_job = workflow.split("  source-and-backend:", 1)[1].split(
        "\n  frontend:", 1
    )[0]

    assert "python -m pip install boto3" in backend_job


def test_deployment_binds_the_frontend_to_the_exact_quality_receipt() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )

    assert "--json databaseId,headSha,status,conclusion,url" in workflow
    assert 'handle.write("QUALITY_STATUS=success\\n")' in workflow
    assert 'handle.write(f"QUALITY_RUN_URL={quality_url}\\n")' in workflow
    assert "NEXT_PUBLIC_SOURCE_REVISION: ${{ env.DEPLOY_REVISION }}" in workflow
    assert "NEXT_PUBLIC_QUALITY_STATUS: ${{ env.QUALITY_STATUS }}" in workflow
    assert "NEXT_PUBLIC_QUALITY_RUN_URL: ${{ env.QUALITY_RUN_URL }}" in workflow

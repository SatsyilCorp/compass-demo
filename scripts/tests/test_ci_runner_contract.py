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

from pathlib import Path

from scripts.run_document_ml_demo import run


ROOT = Path(__file__).resolve().parents[2]


def test_local_adapter_uses_same_model_and_never_claims_sagemaker():
    receipt = run(
        [
            ROOT / "seed" / "documents" / "technical-report.txt",
            ROOT / "seed" / "documents" / "grant-abstract.json",
            ROOT / "seed" / "documents" / "quarantine-short.txt",
        ]
    )

    assert receipt["adapter"] == "deterministic-local-demo"
    assert receipt["sagemaker_job_claimed"] is False
    assert receipt["metrics"]["evaluation_document_count"] == 6
    by_name = {item["filename"]: item for item in receipt["document_runs"]}
    assert (
        by_name["technical-report.txt"]["classification"]["label"] == "technical_report"
    )
    assert by_name["grant-abstract.json"]["classification"]["label"] == "grant_abstract"
    assert by_name["quarantine-short.txt"]["quality"]["gate"] == "quarantine"

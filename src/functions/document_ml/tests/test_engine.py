from __future__ import annotations

import json
from pathlib import Path
import sys


FUNCTION_DIR = Path(__file__).resolve().parents[1]
if str(FUNCTION_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTION_DIR))

import engine  # noqa: E402


def test_extracts_semi_structured_json_and_builds_quality_receipt():
    payload = json.dumps(
        [
            {
                "award_number": "N00014-26-1-0001",
                "title": "Resilient undersea sensing research",
                "abstract": "A university team evaluates acoustic sensing and autonomy.",
            }
        ]
    ).encode("utf-8")

    extracted = engine.extract_document("grant.json", "application/json", payload)
    receipt = engine.quality_receipt(extracted)

    assert extracted["schema"]["shape"] == "records"
    assert extracted["schema"]["record_count"] == 1
    assert extracted["schema"]["fields"] == ["abstract", "award_number", "title"]
    assert extracted["sha256"] == engine.sha256_bytes(payload)
    assert receipt["gate"] == "pass"
    assert receipt["score"] == 100.0


def test_extracts_unstructured_text_and_flags_patterns_without_exposing_values():
    payload = (
        "Technical report for autonomous maritime sensing. "
        "Controlled contact analyst@example.test and tracking value 123-45-6789."
    ).encode("utf-8")

    extracted = engine.extract_document("report.txt", "text/plain", payload)

    assert extracted["schema"]["shape"] == "unstructured"
    assert extracted["classification_marking"] == "CUI-Mock"
    assert extracted["sensitive_pattern_counts"] == {
        "email": 1,
        "ssn_pattern": 1,
        "phone": 0,
    }
    assert "analyst@example.test" not in json.dumps(
        extracted["sensitive_pattern_counts"]
    )


def test_classical_model_is_reproducible_and_evaluated():
    samples = engine.default_training_samples()

    first_model, first_metrics = engine.train_and_evaluate(samples)
    second_model, second_metrics = engine.train_and_evaluate(list(reversed(samples)))

    assert first_model == second_model
    assert first_metrics == second_metrics
    assert first_model["labels"] == list(engine.DOCUMENT_TAXONOMY)
    assert first_metrics["accuracy"] >= 0.75
    assert first_metrics["macro_f1"] >= 0.75
    prediction = engine.predict(
        first_model,
        "The peer reviewed technical paper reports methods, experiments, results, and citations.",
    )
    assert prediction["label"] == "publication_summary"
    assert 0.0 <= prediction["confidence"] <= 1.0
    assert prediction["review_required"] is False

    weak_prediction = engine.predict(first_model, "generic unrelated content")
    assert weak_prediction["review_required"] is True


def test_csv_schema_terms_support_financial_execution_classification():
    payload = (
        "synthetic_only,program,fiscal_year,budget_authority,obligations,"
        "expenditures,variance,forecast\n"
        "true,Autonomy,2026,12000000,8100000,6400000,-250000,11800000\n"
    ).encode("utf-8")
    extracted = engine.extract_document("financial-execution.csv", "text/csv", payload)
    model, _metrics = engine.train_and_evaluate(engine.default_training_samples())

    prediction = engine.predict(model, extracted["extracted_text"])

    assert engine.DOCUMENT_TAXONOMY == (
        "grant_abstract",
        "technical_report",
        "publication_summary",
        "patent_summary",
        "investment_brief",
        "financial_execution",
    )
    assert prediction["label"] == "financial_execution"


def test_drift_receipt_has_an_actionable_threshold_verdict():
    train, _test = engine.split_samples(engine.default_training_samples())
    model = engine.train_classifier(train)
    shifted = [
        "Cryptocurrency retail promotion unrelated vocabulary galaxy football recipe."
        for _ in range(8)
    ]

    receipt = engine.drift_receipt(model, shifted, threshold=0.20)

    assert receipt["documents_observed"] == 8
    assert receipt["drift_detected"] is True
    assert receipt["recommended_action"] == "retrain-and-review"
    assert receipt["out_of_vocabulary_rate"] > 0.5

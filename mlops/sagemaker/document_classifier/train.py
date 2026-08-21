#!/usr/bin/env python3
"""Train the Compass six-class document classifier in SageMaker AI.

The script is intentionally compatible with the AWS managed Scikit-learn
framework container. SageMaker mounts the immutable training channel under
``SM_CHANNEL_TRAIN`` and collects everything written to ``SM_MODEL_DIR`` into
the resulting ``model.tar.gz`` artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.linear_model import LogisticRegression


TAXONOMY = (
    "grant_abstract",
    "technical_report",
    "publication_summary",
    "patent_summary",
    "investment_brief",
    "financial_execution",
)
SPLIT_SEED = 20260811
REVIEW_THRESHOLD = 0.62
MIN_ACCURACY = 0.90
MIN_MACRO_F1 = 0.88


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _load_dataset(channel_dir: Path) -> tuple[list[dict[str, str]], str]:
    dataset_path = channel_dir / "dataset.jsonl"
    if not dataset_path.is_file():
        raise RuntimeError(f"missing SageMaker training input {dataset_path}")
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ordered = sorted(
        rows,
        key=lambda row: (str(row["split"]), str(row["label"]), str(row["sample_id"])),
    )
    for index, row in enumerate(ordered):
        if set(row) != {"sample_id", "label", "text", "split"}:
            raise RuntimeError(f"training record {index} has an invalid shape")
        if row["label"] not in TAXONOMY:
            raise RuntimeError(f"training record {index} has an invalid label")
        if row["split"] not in {"train", "evaluation"}:
            raise RuntimeError(f"training record {index} has an invalid split")
        if len(str(row["text"]).strip()) < 20:
            raise RuntimeError(f"training record {index} has insufficient text")
    rendered = "".join(_stable_json(row) + "\n" for row in ordered).encode("utf-8")
    return ordered, hashlib.sha256(rendered).hexdigest()


def _validate_contract(rows: list[dict[str, str]]) -> None:
    all_counts = Counter(row["label"] for row in rows)
    train_counts = Counter(row["label"] for row in rows if row["split"] == "train")
    evaluation_counts = Counter(
        row["label"] for row in rows if row["split"] == "evaluation"
    )
    expected_all = {label: 6 for label in TAXONOMY}
    expected_train = {label: 5 for label in TAXONOMY}
    expected_evaluation = {label: 1 for label in TAXONOMY}
    if dict(all_counts) != expected_all:
        raise RuntimeError(f"expected six records per class, observed {dict(all_counts)}")
    if dict(train_counts) != expected_train:
        raise RuntimeError(
            f"expected five training records per class, observed {dict(train_counts)}"
        )
    if dict(evaluation_counts) != expected_evaluation:
        raise RuntimeError(
            "expected one evaluation record per class, observed "
            + str(dict(evaluation_counts))
        )


def _pipeline() -> Pipeline:
    word_features = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        min_df=1,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b",
    )
    character_features = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        min_df=1,
    )
    classifier = LogisticRegression(
        C=2.0,
        class_weight="balanced",
        max_iter=2_000,
        multi_class="multinomial",
        random_state=SPLIT_SEED,
        solver="lbfgs",
    )
    return Pipeline(
        [
            (
                "features",
                FeatureUnion(
                    [
                        ("word_tfidf", word_features),
                        ("character_tfidf", character_features),
                    ]
                ),
            ),
            ("classifier", classifier),
        ]
    )


def _metrics(
    model: Pipeline,
    train_texts: list[str],
    train_labels: list[str],
    evaluation_texts: list[str],
    evaluation_labels: list[str],
    dataset_digest: str,
) -> dict[str, Any]:
    cv = RepeatedStratifiedKFold(
        n_splits=5,
        n_repeats=3,
        random_state=SPLIT_SEED,
    )
    cv_scores = cross_val_score(
        model,
        train_texts,
        train_labels,
        cv=cv,
        scoring="f1_macro",
        n_jobs=1,
    )
    model.fit(train_texts, train_labels)
    predictions = model.predict(evaluation_texts)
    probabilities = model.predict_proba(evaluation_texts)
    accuracy = float(accuracy_score(evaluation_labels, predictions))
    macro_f1 = float(f1_score(evaluation_labels, predictions, average="macro"))
    report = classification_report(
        evaluation_labels,
        predictions,
        labels=list(TAXONOMY),
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(
        evaluation_labels,
        predictions,
        labels=list(TAXONOMY),
    ).tolist()
    return {
        "contract": "compass.sagemaker-document-metrics.v1",
        "algorithm": "word-char-tfidf-logistic-regression",
        "accuracy": round(accuracy, 6),
        "macro_f1": round(macro_f1, 6),
        "cv_macro_f1_mean": round(float(cv_scores.mean()), 6),
        "cv_macro_f1_std": round(float(cv_scores.std()), 6),
        "cv_folds": len(cv_scores),
        "training_document_count": len(train_texts),
        "evaluation_document_count": len(evaluation_texts),
        "training_split_seed": SPLIT_SEED,
        "evaluation_strategy": (
            "one deterministic holdout per class plus five-fold repeated "
            "stratified cross-validation on training records"
        ),
        "dataset_digest": dataset_digest,
        "taxonomy": list(TAXONOMY),
        "class_report": {
            label: {
                key: round(float(value), 6)
                for key, value in report[label].items()
                if key in {"precision", "recall", "f1-score", "support"}
            }
            for label in TAXONOMY
        },
        "confusion_matrix": {
            actual: {
                predicted: int(matrix[actual_index][predicted_index])
                for predicted_index, predicted in enumerate(TAXONOMY)
            }
            for actual_index, actual in enumerate(TAXONOMY)
        },
        "predictions": [
            {
                "actual": actual,
                "predicted": str(predicted),
                "confidence": round(float(max(row)), 6),
            }
            for actual, predicted, row in zip(
                evaluation_labels,
                predictions,
                probabilities,
            )
        ],
        "promotion_gate": {
            "minimum_accuracy": MIN_ACCURACY,
            "minimum_macro_f1": MIN_MACRO_F1,
            "passed": accuracy >= MIN_ACCURACY and macro_f1 >= MIN_MACRO_F1,
        },
    }


def main() -> None:
    channel_dir = Path(os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    model_dir = Path(os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    output_dir = Path(os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data"))
    expected_digest = os.environ.get("COMPASS_DATASET_DIGEST", "")
    trainer_digest = os.environ.get("COMPASS_TRAINER_DIGEST", "")
    model_version = os.environ.get("COMPASS_MODEL_VERSION", "")

    rows, dataset_digest = _load_dataset(channel_dir)
    _validate_contract(rows)
    if not expected_digest or expected_digest != dataset_digest:
        raise RuntimeError("training dataset digest does not match the submitted manifest")
    if not trainer_digest or not model_version:
        raise RuntimeError("trainer digest and model version are required")

    train_rows = [row for row in rows if row["split"] == "train"]
    evaluation_rows = [row for row in rows if row["split"] == "evaluation"]
    train_texts = [row["text"] for row in train_rows]
    train_labels = [row["label"] for row in train_rows]
    evaluation_texts = [row["text"] for row in evaluation_rows]
    evaluation_labels = [row["label"] for row in evaluation_rows]

    model = _pipeline()
    metrics = _metrics(
        model,
        train_texts,
        train_labels,
        evaluation_texts,
        evaluation_labels,
        dataset_digest,
    )
    metrics["model_version"] = model_version
    metrics["trainer_digest"] = trainer_digest

    model_card = {
        "contract": "compass.model-card.v1",
        "model_version": model_version,
        "algorithm": metrics["algorithm"],
        "intended_use": (
            "Route sanitized synthetic documents into the six Compass operational classes."
        ),
        "not_intended_for": (
            "Autonomous adjudication, classification markings, production validation, "
            "or use with unapproved Government data."
        ),
        "training_data": {
            "synthetic_only": True,
            "dataset_digest": dataset_digest,
            "training_records": len(train_rows),
            "evaluation_records": len(evaluation_rows),
            "split_seed": SPLIT_SEED,
        },
        "evaluation": metrics,
        "governance": {
            "review_threshold": REVIEW_THRESHOLD,
            "registry_approval": "PendingManualApproval",
            "champion_change": "not-performed-by-training",
        },
        "limitations": [
            "The source corpus contains only six synthetic examples per class.",
            "Metrics prove pipeline execution and do not establish production accuracy.",
            "A separate approved corpus and independent validation are required before production use.",
        ],
    }

    model_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    code_dir = model_dir / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / "model.joblib")
    (model_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (model_dir / "model-card.json").write_text(
        json.dumps(model_card, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (model_dir / "taxonomy.json").write_text(
        json.dumps(list(TAXONOMY), indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(Path(__file__).with_name("inference.py"), code_dir / "inference.py")
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"validation:accuracy={metrics['accuracy']}")
    print(f"validation:macro_f1={metrics['macro_f1']}")
    print(f"cv:macro_f1_mean={metrics['cv_macro_f1_mean']}")
    print(f"cv:macro_f1_std={metrics['cv_macro_f1_std']}")
    print(f"compass:model_version={model_version}")


if __name__ == "__main__":
    main()

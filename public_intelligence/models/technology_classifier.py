"""Reviewed-taxonomy technology text classifier."""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from typing import Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

from .common import (
    TrainingOutput,
    assert_split_integrity,
    base_model_card,
    multiclass_metrics,
    split_evidence,
    subgroup_metrics,
    training_receipt,
)
from .contracts import (
    RANDOM_SEED,
    CanonicalDataset,
    CanonicalRow,
    TrainingRefusal,
    count_labels,
    parse_time,
    require_target,
)


SPACE_RE = re.compile(r"\s+")


def _normalized_text(row: CanonicalRow, text_field: str) -> str:
    raw = row.features.get(text_field)
    if not isinstance(raw, str) or len(raw.strip()) < 40:
        raise TrainingRefusal(
            "invalid_feature", "technology text must contain at least 40 characters"
        )
    return SPACE_RE.sub(" ", raw).strip()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.casefold().encode("utf-8")).hexdigest()


def _taxonomy(dataset: CanonicalDataset) -> tuple[str, ...]:
    raw = dataset.manifest.get("taxonomy")
    if not isinstance(raw, dict) or raw.get("reviewed") is not True:
        raise TrainingRefusal(
            "taxonomy_not_reviewed",
            "technology taxonomy must have explicit review evidence",
        )
    labels = raw.get("labels")
    if (
        not isinstance(labels, list)
        or len(labels) < 2
        or any(not isinstance(value, str) or not value.strip() for value in labels)
        or len(labels) != len(set(labels))
    ):
        raise TrainingRefusal(
            "invalid_taxonomy", "reviewed taxonomy must contain unique non-empty labels"
        )
    for field in ("review_id", "reviewed_by", "reviewed_at"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise TrainingRefusal(
                "taxonomy_not_reviewed", f"taxonomy.{field} is required"
            )
    parse_time(raw["reviewed_at"], field="taxonomy.reviewed_at")
    return tuple(labels)


def _stratified_text_group_split(
    dataset: CanonicalDataset, text_field: str, labels: Sequence[str]
) -> tuple[list[CanonicalRow], list[CanonicalRow]]:
    by_hash: dict[str, list[CanonicalRow]] = defaultdict(list)
    hash_label: dict[str, str] = {}
    for row in dataset.rows:
        text_hash = _text_hash(_normalized_text(row, text_field))
        label = str(row.label_value)
        previous = hash_label.setdefault(text_hash, label)
        if previous != label:
            raise TrainingRefusal(
                "conflicting_duplicate_label",
                "identical normalized text has conflicting reviewed taxonomy labels",
            )
        by_hash[text_hash].append(row)
    train_hashes: set[str] = set()
    test_hashes: set[str] = set()
    for label in labels:
        groups = sorted(key for key, value in hash_label.items() if value == label)
        if len(groups) < 8:
            raise TrainingRefusal(
                "insufficient_label_support",
                f"taxonomy label {label!r} requires at least eight unique texts",
            )
        test_count = max(2, math.ceil(len(groups) * 0.25))
        test_hashes.update(groups[-test_count:])
        train_hashes.update(groups[:-test_count])
    train_rows = sorted(
        [row for key in train_hashes for row in by_hash[key]],
        key=lambda row: (row.event_time, row.record_id),
    )
    test_rows = sorted(
        [row for key in test_hashes for row in by_hash[key]],
        key=lambda row: (row.event_time, row.record_id),
    )
    assert_split_integrity(
        (train_rows, test_rows), require_groups=False, require_temporal=False
    )
    return train_rows, test_rows


def _subgroup_metrics(actual: Sequence[str], predicted: Sequence[str]):
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 8),
        "macro_f1": round(
            float(f1_score(actual, predicted, average="macro", zero_division=0)), 8
        ),
    }


def train_technology_classifier(dataset: CanonicalDataset) -> TrainingOutput:
    require_target(dataset, "technology_taxonomy_label")
    labels = _taxonomy(dataset)
    schema = dataset.manifest["feature_schema"]
    text_field = schema.get("text_field")
    if not isinstance(text_field, str) or not text_field:
        raise TrainingRefusal(
            "missing_features", "technology classifier requires one reviewed text_field"
        )
    observed = [str(row.label_value) for row in dataset.rows]
    unknown = sorted(set(observed) - set(labels))
    missing = sorted(set(labels) - set(observed))
    if unknown or missing:
        raise TrainingRefusal(
            "taxonomy_label_mismatch",
            f"labels outside taxonomy: {unknown}; taxonomy labels without evidence: {missing}",
        )
    train_rows, test_rows = _stratified_text_group_split(dataset, text_field, labels)
    train_text = [_normalized_text(row, text_field) for row in train_rows]
    test_text = [_normalized_text(row, text_field) for row in test_rows]
    train_y = [str(row.label_value) for row in train_rows]
    test_y = [str(row.label_value) for row in test_rows]
    estimator = Pipeline(
        [
            (
                "features",
                FeatureUnion(
                    [
                        (
                            "word",
                            TfidfVectorizer(
                                lowercase=True,
                                strip_accents="unicode",
                                ngram_range=(1, 2),
                                min_df=2,
                                sublinear_tf=True,
                            ),
                        ),
                        (
                            "character",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                lowercase=True,
                                strip_accents="unicode",
                                ngram_range=(3, 5),
                                min_df=2,
                                sublinear_tf=True,
                            ),
                        ),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=2.0,
                    class_weight="balanced",
                    max_iter=2_000,
                    random_state=RANDOM_SEED,
                    solver="lbfgs",
                ),
            ),
        ]
    )
    estimator.fit(train_text, train_y)
    predictions = estimator.predict(test_text)
    raw_probabilities = estimator.predict_proba(test_text)
    classes = list(estimator.classes_)
    probabilities = np.column_stack(
        [raw_probabilities[:, classes.index(label)] for label in labels]
    )
    metrics = {
        "holdout": multiclass_metrics(test_y, predictions, probabilities, labels),
        "label_counts": count_labels(observed),
        "subgroups": subgroup_metrics(
            test_rows,
            test_y,
            predictions,
            subgroup_fields=dataset.subgroup_fields,
            minimum_size=dataset.minimum_subgroup_size,
            metric_fn=_subgroup_metrics,
        ),
    }
    split = split_evidence({"train": train_rows, "test": test_rows}, grouped=False)
    card = base_model_card(
        dataset,
        model_kind="technology_classifier",
        algorithm="word-character-tfidf-logistic-regression",
        intended_use="Route public text into the explicitly reviewed technology taxonomy.",
        prohibited_uses=(
            "Creating taxonomy labels from model output without human review.",
            "Treating the assigned label as an authoritative security or mission classification.",
        ),
        split=split,
        metrics=metrics,
        limitations=(
            "Results are constrained to the reviewed taxonomy supplied with this evidence set.",
            "Language, terminology, and publication practices can drift over time.",
        ),
        output_semantics="Probability distribution across reviewed taxonomy labels.",
    )
    card["taxonomy"] = {
        "labels": list(labels),
        "review_id": dataset.manifest["taxonomy"]["review_id"],
        "reviewed_by": dataset.manifest["taxonomy"]["reviewed_by"],
        "reviewed_at": dataset.manifest["taxonomy"]["reviewed_at"],
    }
    return TrainingOutput(
        estimator=estimator,
        model_card=card,
        receipt=training_receipt(dataset, card, accepted_rows=len(dataset.rows)),
    )

"""Reviewed anomaly rules combined with Isolation Forest review signals."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.base import BaseEstimator, OutlierMixin
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, f1_score
from sklearn.metrics import balanced_accuracy_score, precision_score, recall_score

from .common import (
    TrainingOutput,
    base_model_card,
    split_evidence,
    subgroup_metrics,
    tabular_feature_names,
    tabular_matrix,
    tabular_preprocessor,
    temporal_two_way_split,
    training_receipt,
)
from .contracts import (
    RANDOM_SEED,
    CanonicalDataset,
    TrainingRefusal,
    require_binary_labels,
    require_minimum,
    require_target,
)


OPERATORS = {
    "lt": lambda left, right: left < right,
    "lte": lambda left, right: left <= right,
    "gt": lambda left, right: left > right,
    "gte": lambda left, right: left >= right,
    "eq": lambda left, right: left == right,
    "neq": lambda left, right: left != right,
}


class HybridAnomalyDetector(OutlierMixin, BaseEstimator):
    """Scikit-learn compatible detector returning review flags, not accusations."""

    def __init__(
        self,
        *,
        numeric_fields: Sequence[str],
        categorical_fields: Sequence[str],
        rules: Sequence[Mapping[str, Any]],
        contamination: float,
    ):
        self.numeric_fields = numeric_fields
        self.categorical_fields = categorical_fields
        self.rules = rules
        self.contamination = contamination

    def fit(self, X, y=None):
        self.preprocessor_ = tabular_preprocessor(
            self.numeric_fields, self.categorical_fields
        )
        transformed = self.preprocessor_.fit_transform(X)
        self.isolation_forest_ = IsolationForest(
            n_estimators=240,
            contamination=self.contamination,
            random_state=RANDOM_SEED,
            n_jobs=1,
        ).fit(transformed)
        return self

    def _rule_flags(self, X) -> tuple[np.ndarray, list[list[str]]]:
        flags = np.zeros(len(X), dtype=bool)
        matched: list[list[str]] = [[] for _ in X]
        positions = {name: index for index, name in enumerate(self.numeric_fields)}
        for rule in self.rules:
            position = positions[str(rule["feature"])]
            operation = OPERATORS[str(rule["operator"])]
            threshold = float(rule["value"])
            for index, row in enumerate(X):
                value = row[position]
                if value is not None and operation(float(value), threshold):
                    flags[index] = True
                    matched[index].append(str(rule["rule_id"]))
        return flags, matched

    def predict(self, X):
        rule_flags, _ = self._rule_flags(X)
        transformed = self.preprocessor_.transform(X)
        isolation_flags = self.isolation_forest_.predict(transformed) == -1
        return np.where(rule_flags | isolation_flags, -1, 1)

    def decision_function(self, X):
        transformed = self.preprocessor_.transform(X)
        return self.isolation_forest_.decision_function(transformed)

    def predict_details(self, X) -> list[dict[str, Any]]:
        rule_flags, matched = self._rule_flags(X)
        transformed = self.preprocessor_.transform(X)
        isolation_flags = self.isolation_forest_.predict(transformed) == -1
        scores = self.isolation_forest_.decision_function(transformed)
        return [
            {
                "review_required": bool(rule_flag or isolation_flag),
                "rule_flag": bool(rule_flag),
                "isolation_flag": bool(isolation_flag),
                "matched_rule_ids": rule_ids,
                "isolation_score": round(float(score), 8),
                "semantics": "analyst review signal only",
            }
            for rule_flag, isolation_flag, rule_ids, score in zip(
                rule_flags, isolation_flags, matched, scores
            )
        ]


def _reviewed_rules(dataset: CanonicalDataset, numeric: Sequence[str]):
    raw = dataset.manifest.get("anomaly_rules")
    if not isinstance(raw, list) or not raw:
        raise TrainingRefusal(
            "rules_not_reviewed",
            "anomaly detection requires at least one reviewed rule",
        )
    result = []
    identifiers: set[str] = set()
    for index, rule in enumerate(raw):
        if not isinstance(rule, Mapping) or rule.get("reviewed") is not True:
            raise TrainingRefusal(
                "rules_not_reviewed", f"anomaly rule {index} lacks review evidence"
            )
        rule_id = str(rule.get("rule_id") or "").strip()
        feature = str(rule.get("feature") or "").strip()
        operator = str(rule.get("operator") or "").strip()
        value = rule.get("value")
        if not rule_id or rule_id in identifiers:
            raise TrainingRefusal("invalid_rule", "anomaly rule IDs must be unique")
        if feature not in numeric or operator not in OPERATORS:
            raise TrainingRefusal(
                "invalid_rule",
                f"anomaly rule {rule_id!r} has an invalid feature or operator",
            )
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise TrainingRefusal(
                "invalid_rule", f"anomaly rule {rule_id!r} requires a finite threshold"
            )
        for field in ("reviewed_by", "review_id", "reviewed_at"):
            if not isinstance(rule.get(field), str) or not str(rule[field]).strip():
                raise TrainingRefusal(
                    "rules_not_reviewed", f"anomaly rule {rule_id!r} lacks {field}"
                )
        identifiers.add(rule_id)
        result.append(dict(rule))
    return result


def _subgroup_metrics(actual: Sequence[int], predicted: Sequence[int]):
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 8),
        "f1": round(float(f1_score(actual, predicted, zero_division=0)), 8),
    }


def train_anomaly_detector(dataset: CanonicalDataset) -> TrainingOutput:
    require_target(dataset, "reviewed_anomaly")
    require_minimum(dataset, 100)
    require_binary_labels(dataset)
    contamination = dataset.manifest.get("isolation_contamination")
    if (
        isinstance(contamination, bool)
        or not isinstance(contamination, (int, float))
        or not 0.001 <= float(contamination) <= 0.20
    ):
        raise TrainingRefusal(
            "invalid_contract", "isolation_contamination must be between 0.001 and 0.20"
        )
    numeric, categorical = tabular_feature_names(dataset)
    if not numeric:
        raise TrainingRefusal(
            "missing_features", "anomaly rules require at least one numeric feature"
        )
    rules = _reviewed_rules(dataset, numeric)
    train_rows, test_rows = temporal_two_way_split(
        dataset.rows,
        minimum_train=70,
        minimum_test=25,
        fraction=0.75,
    )
    normal_train_rows = [row for row in train_rows if int(bool(row.label_value)) == 0]
    if len(normal_train_rows) < 50:
        raise TrainingRefusal(
            "insufficient_normal_samples",
            "Isolation Forest requires at least 50 authentically reviewed normal training rows",
        )
    test_y = [int(bool(row.label_value)) for row in test_rows]
    if min(test_y.count(0), test_y.count(1)) < 5:
        raise TrainingRefusal(
            "insufficient_label_support",
            "anomaly holdout requires at least five reviewed rows for each class",
        )
    estimator = HybridAnomalyDetector(
        numeric_fields=numeric,
        categorical_fields=categorical,
        rules=rules,
        contamination=float(contamination),
    ).fit(tabular_matrix(normal_train_rows, numeric, categorical))
    test_X = tabular_matrix(test_rows, numeric, categorical)
    details = estimator.predict_details(test_X)
    predictions = [int(item["review_required"]) for item in details]
    metrics = {
        "holdout": {
            "accuracy": round(float(accuracy_score(test_y, predictions)), 8),
            "balanced_accuracy": round(
                float(balanced_accuracy_score(test_y, predictions)), 8
            ),
            "precision": round(
                float(precision_score(test_y, predictions, zero_division=0)), 8
            ),
            "recall": round(
                float(recall_score(test_y, predictions, zero_division=0)), 8
            ),
            "f1": round(float(f1_score(test_y, predictions, zero_division=0)), 8),
            "probability_metrics_reported": False,
            "probability_metrics_reason": (
                "Isolation Forest scores are not calibrated probabilities."
            ),
        },
        "operational_counts": {
            "rule_flags": sum(int(item["rule_flag"]) for item in details),
            "isolation_flags": sum(int(item["isolation_flag"]) for item in details),
            "combined_review_flags": sum(predictions),
        },
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
    split["normal_rows_used_to_fit_isolation_forest"] = len(normal_train_rows)
    card = base_model_card(
        dataset,
        model_kind="anomaly_detection",
        algorithm="reviewed-rules-plus-isolation-forest",
        intended_use="Prioritize unusual public records for analyst review.",
        prohibited_uses=(
            "Calling a flagged record fraud, waste, abuse, failure, or wrongdoing.",
            "Taking an adverse action without source review and independent validation.",
        ),
        split=split,
        metrics=metrics,
        limitations=(
            "Isolation scores are relative to the fitted evidence set and are not probabilities of misconduct.",
            "Reviewed rules can become stale when source reporting practices change.",
        ),
        output_semantics="Combined rule and Isolation Forest signal for analyst review only.",
    )
    card["reviewed_rules"] = [
        {
            "rule_id": rule["rule_id"],
            "feature": rule["feature"],
            "operator": rule["operator"],
            "value": rule["value"],
            "review_id": rule["review_id"],
        }
        for rule in rules
    ]
    return TrainingOutput(
        estimator=estimator,
        model_card=card,
        receipt=training_receipt(dataset, card, accepted_rows=len(dataset.rows)),
    )

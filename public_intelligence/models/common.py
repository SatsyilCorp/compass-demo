"""Shared splitting, feature, metric, and evidence utilities."""

from __future__ import annotations

import bisect
import math
import platform
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import sklearn
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_pinball_loss,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression

from .contracts import (
    RANDOM_SEED,
    CanonicalDataset,
    CanonicalRow,
    TrainingRefusal,
    digest_json,
)


SUITE_VERSION = "1.0.0"


@dataclass(frozen=True)
class TrainingOutput:
    estimator: Any
    model_card: dict[str, Any]
    receipt: dict[str, Any]


class HeldoutSigmoidCalibrator(ClassifierMixin, BaseEstimator):
    """Platt-style calibration fitted only on a held-out chronological split."""

    classes_ = np.asarray([0, 1])

    def __init__(self, base_estimator: Any, calibrator: Any):
        self.base_estimator = base_estimator
        self.calibrator = calibrator

    def _scores(self, X) -> np.ndarray:
        if hasattr(self.base_estimator, "decision_function"):
            values = self.base_estimator.decision_function(X)
        else:
            values = self.base_estimator.predict_proba(X)[:, 1]
        return np.asarray(values, dtype=float).reshape(-1, 1)

    def predict_proba(self, X) -> np.ndarray:
        return self.calibrator.predict_proba(self._scores(X))

    def predict(self, X) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def decision_function(self, X) -> np.ndarray:
        probabilities = np.clip(self.predict_proba(X)[:, 1], 1e-12, 1 - 1e-12)
        return np.log(probabilities / (1 - probabilities))


def fit_heldout_sigmoid_calibrator(
    base_estimator: Any, calibration_X: Sequence[Any], calibration_y: Sequence[int]
) -> HeldoutSigmoidCalibrator:
    if hasattr(base_estimator, "decision_function"):
        scores = base_estimator.decision_function(calibration_X)
    else:
        scores = base_estimator.predict_proba(calibration_X)[:, 1]
    calibrator = LogisticRegression(
        C=1.0,
        max_iter=1_000,
        random_state=RANDOM_SEED,
        solver="liblinear",
    ).fit(np.asarray(scores, dtype=float).reshape(-1, 1), calibration_y)
    return HeldoutSigmoidCalibrator(base_estimator, calibrator)


def tabular_feature_names(
    dataset: CanonicalDataset,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    schema = dataset.manifest["feature_schema"]
    numeric = tuple(str(value) for value in schema.get("numeric", []))
    categorical = tuple(str(value) for value in schema.get("categorical", []))
    if not numeric and not categorical:
        raise TrainingRefusal(
            "missing_features", f"{dataset.model_kind} requires tabular features"
        )
    return numeric, categorical


def tabular_matrix(
    rows: Sequence[CanonicalRow],
    numeric: Sequence[str],
    categorical: Sequence[str],
) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in rows:
        result.append(
            [row.features.get(field) for field in numeric]
            + [row.features.get(field) for field in categorical]
        )
    return result


def tabular_preprocessor(
    numeric: Sequence[str], categorical: Sequence[str]
) -> ColumnTransformer:
    transformers: list[tuple[str, Any, list[int]]] = []
    if numeric:
        numeric_pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]
        )
        transformers.append(("numeric", numeric_pipe, list(range(len(numeric)))))
    if categorical:
        start = len(numeric)
        categorical_pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="most_frequent")),
                (
                    "one_hot",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ),
            ]
        )
        transformers.append(
            (
                "categorical",
                categorical_pipe,
                list(range(start, start + len(categorical))),
            )
        )
    return ColumnTransformer(transformers, remainder="drop", sparse_threshold=0.0)


def _strict_boundaries(rows: Sequence[CanonicalRow]) -> list[int]:
    return [
        index
        for index in range(1, len(rows))
        if rows[index - 1].event_time < rows[index].event_time
    ]


def _nearest_boundary(
    boundaries: Sequence[int], target: int, *, lower: int, upper: int
) -> int:
    candidates = [value for value in boundaries if lower <= value <= upper]
    if not candidates:
        raise TrainingRefusal(
            "temporal_split_unavailable",
            "timestamps cannot form strict chronological partitions with the required sizes",
        )
    return min(candidates, key=lambda value: (abs(value - target), value))


def temporal_three_way_split(
    rows: Sequence[CanonicalRow],
    *,
    minimum_fit: int,
    minimum_calibration: int,
    minimum_test: int,
    fractions: tuple[float, float] = (0.60, 0.80),
) -> tuple[list[CanonicalRow], list[CanonicalRow], list[CanonicalRow]]:
    ordered = sorted(rows, key=lambda row: (row.event_time, row.record_id))
    boundaries = _strict_boundaries(ordered)
    first = _nearest_boundary(
        boundaries,
        round(len(ordered) * fractions[0]),
        lower=minimum_fit,
        upper=len(ordered) - minimum_calibration - minimum_test,
    )
    second = _nearest_boundary(
        boundaries,
        round(len(ordered) * fractions[1]),
        lower=first + minimum_calibration,
        upper=len(ordered) - minimum_test,
    )
    partitions = (ordered[:first], ordered[first:second], ordered[second:])
    assert_split_integrity(partitions, require_groups=False, require_temporal=True)
    return partitions


def temporal_two_way_split(
    rows: Sequence[CanonicalRow],
    *,
    minimum_train: int,
    minimum_test: int,
    fraction: float = 0.75,
) -> tuple[list[CanonicalRow], list[CanonicalRow]]:
    ordered = sorted(rows, key=lambda row: (row.event_time, row.record_id))
    boundary = _nearest_boundary(
        _strict_boundaries(ordered),
        round(len(ordered) * fraction),
        lower=minimum_train,
        upper=len(ordered) - minimum_test,
    )
    partitions = (ordered[:boundary], ordered[boundary:])
    assert_split_integrity(partitions, require_groups=False, require_temporal=True)
    return partitions


def grouped_temporal_three_way_split(
    rows: Sequence[CanonicalRow],
    *,
    minimum_groups: tuple[int, int, int] = (6, 3, 3),
) -> tuple[list[CanonicalRow], list[CanonicalRow], list[CanonicalRow]]:
    grouped: dict[str, list[CanonicalRow]] = defaultdict(list)
    for row in rows:
        if not row.group_id:
            raise TrainingRefusal(
                "missing_split_group",
                "grouped temporal training requires group_id on every row",
            )
        grouped[row.group_id].append(row)
    if len(grouped) < sum(minimum_groups):
        raise TrainingRefusal(
            "insufficient_groups",
            f"grouped temporal training requires at least {sum(minimum_groups)} groups",
        )
    groups = sorted(
        (
            min(items, key=lambda row: row.event_time).event_time,
            max(items, key=lambda row: row.event_time).event_time,
            group_id,
            items,
        )
        for group_id, items in grouped.items()
    )
    prefix_max: list[datetime] = []
    current = groups[0][1]
    for item in groups:
        current = max(current, item[1])
        prefix_max.append(current)
    suffix_min: list[datetime] = [groups[-1][0]] * len(groups)
    current = groups[-1][0]
    for index in range(len(groups) - 1, -1, -1):
        current = min(current, groups[index][0])
        suffix_min[index] = current
    valid = [
        index
        for index in range(1, len(groups))
        if prefix_max[index - 1] < suffix_min[index]
    ]
    fit_min, calibration_min, test_min = minimum_groups
    first_candidates = [
        value
        for value in valid
        if fit_min <= value <= len(groups) - calibration_min - test_min
    ]
    if not first_candidates:
        raise TrainingRefusal(
            "group_temporal_overlap",
            "group histories overlap and cannot form a leakage-free temporal split",
        )
    target_first = round(len(groups) * 0.60)
    target_second = round(len(groups) * 0.80)
    best: tuple[float, int, int] | None = None
    for first in first_candidates:
        start = bisect.bisect_left(valid, first + calibration_min)
        second_candidates = [
            value for value in valid[start:] if value <= len(groups) - test_min
        ]
        if not second_candidates:
            continue
        second = min(
            second_candidates,
            key=lambda value: (abs(value - target_second), value),
        )
        score = abs(first - target_first) + abs(second - target_second)
        candidate = (float(score), first, second)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise TrainingRefusal(
            "group_temporal_overlap",
            "groups cannot form fit, calibration, and test periods without overlap",
        )
    _, first, second = best
    partitions = []
    for selected in (groups[:first], groups[first:second], groups[second:]):
        partitions.append(
            sorted(
                [row for _, _, _, items in selected for row in items],
                key=lambda row: (row.event_time, row.record_id),
            )
        )
    result = tuple(partitions)
    assert_split_integrity(result, require_groups=True, require_temporal=True)
    return result  # type: ignore[return-value]


def assert_split_integrity(
    partitions: Sequence[Sequence[CanonicalRow]],
    *,
    require_groups: bool,
    require_temporal: bool,
) -> None:
    seen_ids: set[str] = set()
    source_owners: dict[str, int] = {}
    group_owners: dict[str, int] = {}
    for partition_index, partition in enumerate(partitions):
        if not partition:
            raise TrainingRefusal("empty_split", "a training split is empty")
        for row in partition:
            if row.record_id in seen_ids:
                raise TrainingRefusal(
                    "split_leakage", "record_id appears in multiple splits"
                )
            seen_ids.add(row.record_id)
            owner = source_owners.setdefault(row.source_sha256, partition_index)
            if owner != partition_index:
                raise TrainingRefusal(
                    "source_leakage",
                    "the same source SHA-256 appears in multiple splits",
                )
            if require_groups:
                if not row.group_id:
                    raise TrainingRefusal("missing_split_group", "group_id is required")
                group_owner = group_owners.setdefault(row.group_id, partition_index)
                if group_owner != partition_index:
                    raise TrainingRefusal(
                        "group_leakage", "the same group_id appears in multiple splits"
                    )
    if require_temporal:
        for earlier, later in zip(partitions, partitions[1:]):
            if max(row.event_time for row in earlier) >= min(
                row.event_time for row in later
            ):
                raise TrainingRefusal(
                    "temporal_leakage",
                    "training partitions are not strictly ordered in time",
                )


def require_class_support(
    phases: Mapping[str, Sequence[int]], minimum: Mapping[str, int]
) -> None:
    for phase, labels in phases.items():
        counts = {value: list(labels).count(value) for value in set(labels)}
        if set(counts) != {0, 1} or min(counts.values()) < minimum[phase]:
            raise TrainingRefusal(
                "insufficient_label_support",
                f"{phase} split requires both classes with at least {minimum[phase]} rows each",
            )


def split_evidence(
    partitions: Mapping[str, Sequence[CanonicalRow]], *, grouped: bool
) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for name, rows in partitions.items():
        evidence[name] = {
            "records": len(rows),
            "groups": len({row.group_id for row in rows}) if grouped else None,
            "event_time_min": min(row.event_time for row in rows).isoformat(),
            "event_time_max": max(row.event_time for row in rows).isoformat(),
            "record_set_digest": digest_json(sorted(row.record_id for row in rows)),
            "source_set_digest": digest_json(
                sorted({row.source_sha256 for row in rows})
            ),
        }
    return evidence


def regression_metrics(
    actual: Sequence[float], predicted: Sequence[float]
) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(actual, predicted)), 8),
        "rmse": round(float(math.sqrt(mean_squared_error(actual, predicted))), 8),
    }


def binary_metrics(
    actual: Sequence[int], predicted: Sequence[int], probabilities: Sequence[float]
) -> dict[str, float]:
    result = {
        "accuracy": round(float(accuracy_score(actual, predicted)), 8),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(actual, predicted)), 8
        ),
        "precision": round(
            float(precision_score(actual, predicted, zero_division=0)), 8
        ),
        "recall": round(float(recall_score(actual, predicted, zero_division=0)), 8),
        "f1": round(float(f1_score(actual, predicted, zero_division=0)), 8),
        "brier_score": round(float(brier_score_loss(actual, probabilities)), 8),
        "log_loss": round(float(log_loss(actual, probabilities, labels=[0, 1])), 8),
    }
    if len(set(actual)) == 2:
        result["roc_auc"] = round(float(roc_auc_score(actual, probabilities)), 8)
    return result


def multiclass_metrics(
    actual: Sequence[str],
    predicted: Sequence[str],
    probabilities: np.ndarray,
    labels: Sequence[str],
) -> dict[str, Any]:
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 8),
        "balanced_accuracy": round(
            float(balanced_accuracy_score(actual, predicted)), 8
        ),
        "macro_f1": round(
            float(
                f1_score(
                    actual, predicted, labels=labels, average="macro", zero_division=0
                )
            ),
            8,
        ),
        "log_loss": round(float(log_loss(actual, probabilities, labels=labels)), 8),
        "per_class_f1": {
            label: round(float(value), 8)
            for label, value in zip(
                labels,
                f1_score(
                    actual, predicted, labels=labels, average=None, zero_division=0
                ),
            )
        },
    }


def subgroup_metrics(
    rows: Sequence[CanonicalRow],
    actual: Sequence[Any],
    predicted: Sequence[Any],
    *,
    subgroup_fields: Sequence[str],
    minimum_size: int,
    metric_fn: Callable[[Sequence[Any], Sequence[Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in subgroup_fields:
        buckets: dict[str, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            value = row.subgroups.get(field)
            if value is not None:
                buckets[value].append(index)
        reported: dict[str, Any] = {}
        suppressed: dict[str, int] = {}
        for value, indexes in sorted(buckets.items()):
            if len(indexes) < minimum_size:
                suppressed[value] = len(indexes)
                continue
            reported[value] = {
                "records": len(indexes),
                "metrics": dict(
                    metric_fn(
                        [actual[index] for index in indexes],
                        [predicted[index] for index in indexes],
                    )
                ),
            }
        result[field] = {
            "minimum_reportable_records": minimum_size,
            "reported": reported,
            "suppressed_counts": suppressed,
        }
    return result


def interval_metrics(
    actual: Sequence[float], lower: Sequence[float], upper: Sequence[float]
) -> dict[str, float]:
    if any(low > high for low, high in zip(lower, upper)):
        raise TrainingRefusal(
            "invalid_interval", "prediction interval bounds are reversed"
        )
    coverage = np.mean(
        [low <= observed <= high for observed, low, high in zip(actual, lower, upper)]
    )
    widths = [high - low for low, high in zip(lower, upper)]
    return {
        "empirical_coverage": round(float(coverage), 8),
        "mean_interval_width": round(float(np.mean(widths)), 8),
    }


def pinball_metrics(
    actual: Sequence[float], predictions: Mapping[float, Sequence[float]]
) -> dict[str, float]:
    return {
        f"pinball_loss_q{int(quantile * 100):02d}": round(
            float(mean_pinball_loss(actual, values, alpha=quantile)), 8
        )
        for quantile, values in sorted(predictions.items())
    }


def base_model_card(
    dataset: CanonicalDataset,
    *,
    model_kind: str,
    algorithm: str,
    intended_use: str,
    prohibited_uses: Sequence[str],
    split: Mapping[str, Any],
    metrics: Mapping[str, Any],
    limitations: Sequence[str],
    output_semantics: str,
) -> dict[str, Any]:
    return {
        "contract": "compass.public-intelligence.model-card.v1",
        "suite_version": SUITE_VERSION,
        "model_id": f"{model_kind}-{dataset.dataset_digest[:16]}",
        "model_kind": model_kind,
        "algorithm": algorithm,
        "random_seed": RANDOM_SEED,
        "dataset": {
            "dataset_id": dataset.manifest["dataset_id"],
            "dataset_version": dataset.manifest["dataset_version"],
            "dataset_digest": dataset.dataset_digest,
            "records_received": len(dataset.rows),
            "test_fixture": dataset.test_fixture,
            "target_name": dataset.target_name,
            "target_definition": dataset.manifest["target"]["definition"],
        },
        "intended_use": intended_use,
        "prohibited_uses": list(prohibited_uses),
        "output_semantics": output_semantics,
        "split_evidence": dict(split),
        "evaluation": dict(metrics),
        "subgroup_policy": {
            "fields": list(dataset.subgroup_fields),
            "minimum_reportable_records": dataset.minimum_subgroup_size,
        },
        "limitations": list(limitations),
        "runtime": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
        },
    }


def training_receipt(
    dataset: CanonicalDataset,
    card: Mapping[str, Any],
    *,
    accepted_rows: int,
    excluded_rows: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "contract": "compass.public-intelligence.training-receipt.v1",
        "model_id": card["model_id"],
        "model_kind": dataset.model_kind,
        "dataset_digest": dataset.dataset_digest,
        "rows_received": len(dataset.rows),
        "rows_accepted": accepted_rows,
        "rows_excluded": dict(excluded_rows or {}),
        "authentic_labels_required": True,
        "training_authorization_required": True,
        "test_fixture": dataset.test_fixture,
        "random_seed": RANDOM_SEED,
        "status": "trained",
    }

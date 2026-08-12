"""Funding forecast with chronological backtests and conformal intervals."""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline

from .common import (
    TrainingOutput,
    base_model_card,
    interval_metrics,
    regression_metrics,
    split_evidence,
    subgroup_metrics,
    tabular_feature_names,
    tabular_matrix,
    tabular_preprocessor,
    temporal_three_way_split,
    training_receipt,
)
from .contracts import (
    RANDOM_SEED,
    CanonicalDataset,
    TrainingRefusal,
    require_minimum,
    require_numeric_labels,
    require_target,
)


class ConformalFundingRegressor(RegressorMixin, BaseEstimator):
    """A fitted point estimator with one held-out conformal interval radius."""

    def __init__(self, estimator: Any, interval_radius: float, coverage: float):
        self.estimator = estimator
        self.interval_radius = interval_radius
        self.coverage = coverage

    def predict(self, X):
        return np.maximum(0.0, self.estimator.predict(X))

    def predict_interval(self, X) -> np.ndarray:
        point = self.predict(X)
        return np.column_stack(
            [
                np.maximum(0.0, point - self.interval_radius),
                point + self.interval_radius,
            ]
        )


def _point_pipeline(numeric: Sequence[str], categorical: Sequence[str]) -> Pipeline:
    return Pipeline(
        [
            ("features", tabular_preprocessor(numeric, categorical)),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=240,
                    min_samples_leaf=3,
                    random_state=RANDOM_SEED,
                    n_jobs=1,
                ),
            ),
        ]
    )


def train_funding_forecast(dataset: CanonicalDataset) -> TrainingOutput:
    require_target(dataset, "funding_amount")
    require_minimum(dataset, 60)
    labels = require_numeric_labels(dataset)
    if any(value < 0 for value in labels):
        raise TrainingRefusal(
            "invalid_label", "funding_amount cannot contain negative observed amounts"
        )
    coverage = dataset.manifest.get("prediction_interval_coverage", 0.90)
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)):
        raise TrainingRefusal(
            "invalid_contract", "prediction_interval_coverage must be numeric"
        )
    coverage = float(coverage)
    if coverage not in {0.80, 0.90, 0.95}:
        raise TrainingRefusal(
            "invalid_contract",
            "prediction interval coverage must be 0.80, 0.90, or 0.95",
        )
    fit_rows, calibration_rows, test_rows = temporal_three_way_split(
        dataset.rows,
        minimum_fit=30,
        minimum_calibration=12,
        minimum_test=12,
    )
    numeric, categorical = tabular_feature_names(dataset)
    point_template = _point_pipeline(numeric, categorical)

    pretest = sorted(
        [*fit_rows, *calibration_rows],
        key=lambda row: (row.event_time, row.record_id),
    )
    backtests = []
    splitter = TimeSeriesSplit(n_splits=3)
    pretest_X = tabular_matrix(pretest, numeric, categorical)
    pretest_y = [float(row.label_value) for row in pretest]
    for fold, (train_index, validation_index) in enumerate(
        splitter.split(pretest_X), start=1
    ):
        train_rows = [pretest[index] for index in train_index]
        validation_rows = [pretest[index] for index in validation_index]
        if max(row.event_time for row in train_rows) >= min(
            row.event_time for row in validation_rows
        ):
            raise TrainingRefusal(
                "temporal_leakage",
                "funding backtest timestamps overlap at a fold boundary",
            )
        estimator = clone(point_template)
        estimator.fit(
            [pretest_X[index] for index in train_index],
            [pretest_y[index] for index in train_index],
        )
        predictions = estimator.predict(
            [pretest_X[index] for index in validation_index]
        )
        backtests.append(
            {
                "fold": fold,
                "train_records": len(train_index),
                "validation_records": len(validation_index),
                "train_through": max(row.event_time for row in train_rows).isoformat(),
                "validation_from": min(
                    row.event_time for row in validation_rows
                ).isoformat(),
                "metrics": regression_metrics(
                    [pretest_y[index] for index in validation_index], predictions
                ),
            }
        )

    fit_X = tabular_matrix(fit_rows, numeric, categorical)
    fit_y = [float(row.label_value) for row in fit_rows]
    calibration_X = tabular_matrix(calibration_rows, numeric, categorical)
    calibration_y = np.asarray(
        [float(row.label_value) for row in calibration_rows], dtype=float
    )
    point = clone(point_template).fit(fit_X, fit_y)
    calibration_predictions = np.maximum(0.0, point.predict(calibration_X))
    residuals = np.abs(calibration_y - calibration_predictions)
    finite_sample_quantile = min(
        1.0, math.ceil((len(residuals) + 1) * coverage) / len(residuals)
    )
    radius = float(np.quantile(residuals, finite_sample_quantile, method="higher"))
    estimator = ConformalFundingRegressor(point, radius, coverage)

    test_X = tabular_matrix(test_rows, numeric, categorical)
    test_y = [float(row.label_value) for row in test_rows]
    test_predictions = estimator.predict(test_X)
    intervals = estimator.predict_interval(test_X)
    aggregate = {
        **regression_metrics(test_y, test_predictions),
        **interval_metrics(test_y, intervals[:, 0], intervals[:, 1]),
        "nominal_interval_coverage": coverage,
        "conformal_radius": round(radius, 8),
        "rolling_backtests": backtests,
    }
    subgroup = subgroup_metrics(
        test_rows,
        test_y,
        test_predictions,
        subgroup_fields=dataset.subgroup_fields,
        minimum_size=dataset.minimum_subgroup_size,
        metric_fn=regression_metrics,
    )
    metrics = {"holdout": aggregate, "subgroups": subgroup}
    split = split_evidence(
        {"fit": fit_rows, "calibration": calibration_rows, "test": test_rows},
        grouped=False,
    )
    card = base_model_card(
        dataset,
        model_kind="funding_forecast",
        algorithm="tabular-random-forest-with-heldout-conformal-interval",
        intended_use="Forecast an externally observed public funding amount for planning review.",
        prohibited_uses=(
            "Representing a forecast as an appropriation, obligation, or authoritative budget decision.",
            "Using future, post-outcome, protected, or non-public features.",
        ),
        split=split,
        metrics=metrics,
        limitations=(
            "Intervals reflect held-out residuals in this evidence set and are not guarantees.",
            "Structural policy changes outside the historical evidence can invalidate the forecast.",
        ),
        output_semantics="Non-negative point estimate with a held-out conformal prediction interval.",
    )
    return TrainingOutput(
        estimator=estimator,
        model_card=card,
        receipt=training_receipt(dataset, card, accepted_rows=len(dataset.rows)),
    )

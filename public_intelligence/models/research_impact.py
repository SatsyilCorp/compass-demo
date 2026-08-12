"""Temporally censored research-impact quantile estimation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline

from .common import (
    TrainingOutput,
    base_model_card,
    interval_metrics,
    pinball_metrics,
    regression_metrics,
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
    parse_time,
    require_target,
)


QUANTILES = (0.10, 0.50, 0.90)


class ResearchImpactQuantileEstimator(RegressorMixin, BaseEstimator):
    """Three fitted quantile pipelines with monotonic prediction output."""

    def __init__(self, estimators: Mapping[float, Any]):
        self.estimators = estimators

    def predict_quantiles(self, X) -> dict[float, np.ndarray]:
        raw = np.column_stack(
            [self.estimators[quantile].predict(X) for quantile in QUANTILES]
        )
        ordered = np.sort(raw, axis=1)
        return {quantile: ordered[:, index] for index, quantile in enumerate(QUANTILES)}

    def predict(self, X):
        return self.predict_quantiles(X)[0.50]


def _quantile_pipeline(
    numeric: Sequence[str], categorical: Sequence[str], quantile: float
) -> Pipeline:
    return Pipeline(
        [
            ("features", tabular_preprocessor(numeric, categorical)),
            (
                "regressor",
                GradientBoostingRegressor(
                    loss="quantile",
                    alpha=quantile,
                    n_estimators=180,
                    max_depth=3,
                    min_samples_leaf=5,
                    learning_rate=0.04,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def train_research_impact_quantiles(dataset: CanonicalDataset) -> TrainingOutput:
    require_target(dataset, "research_impact_score")
    cutoff_raw = dataset.manifest.get("outcome_observation_cutoff")
    cutoff = parse_time(cutoff_raw, field="manifest.outcome_observation_cutoff")
    accepted = []
    excluded = {"explicitly_censored": 0, "observed_after_cutoff": 0}
    for row in dataset.rows:
        if row.label_status == "censored":
            excluded["explicitly_censored"] += 1
            continue
        if row.label_observed_at > cutoff:
            excluded["observed_after_cutoff"] += 1
            continue
        value = row.label_value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TrainingRefusal(
                "invalid_label",
                "research_impact_score must contain numeric observed labels",
            )
        if not np.isfinite(float(value)):
            raise TrainingRefusal(
                "invalid_label", "research_impact_score labels must be finite"
            )
        accepted.append(row)
    if len(accepted) < 80:
        raise TrainingRefusal(
            "insufficient_uncensored_samples",
            "research impact requires at least 80 authentic labels observed by the cutoff",
        )
    if len({float(row.label_value) for row in accepted}) < 5:
        raise TrainingRefusal(
            "insufficient_label_support",
            "research impact requires at least five distinct observed target values",
        )
    train_rows, test_rows = temporal_two_way_split(
        accepted,
        minimum_train=55,
        minimum_test=20,
        fraction=0.75,
    )
    numeric, categorical = tabular_feature_names(dataset)
    train_X = tabular_matrix(train_rows, numeric, categorical)
    train_y = [float(row.label_value) for row in train_rows]
    estimators = {
        quantile: _quantile_pipeline(numeric, categorical, quantile).fit(
            train_X, train_y
        )
        for quantile in QUANTILES
    }
    estimator = ResearchImpactQuantileEstimator(estimators)
    test_X = tabular_matrix(test_rows, numeric, categorical)
    test_y = [float(row.label_value) for row in test_rows]
    raw_predictions = np.column_stack(
        [estimators[quantile].predict(test_X) for quantile in QUANTILES]
    )
    crossing_rate = float(
        np.mean(
            (raw_predictions[:, 0] > raw_predictions[:, 1])
            | (raw_predictions[:, 1] > raw_predictions[:, 2])
        )
    )
    predictions = estimator.predict_quantiles(test_X)
    aggregate = {
        **regression_metrics(test_y, predictions[0.50]),
        **pinball_metrics(test_y, predictions),
        **interval_metrics(test_y, predictions[0.10], predictions[0.90]),
        "raw_quantile_crossing_rate": round(crossing_rate, 8),
        "interval_quantiles": [0.10, 0.90],
    }
    metrics = {
        "holdout": aggregate,
        "subgroups": subgroup_metrics(
            test_rows,
            test_y,
            predictions[0.50],
            subgroup_fields=dataset.subgroup_fields,
            minimum_size=dataset.minimum_subgroup_size,
            metric_fn=regression_metrics,
        ),
    }
    split = split_evidence({"train": train_rows, "test": test_rows}, grouped=False)
    split["censoring"] = {
        "cutoff": cutoff.isoformat(),
        "rows_received": len(dataset.rows),
        "rows_accepted": len(accepted),
        "rows_excluded": excluded,
    }
    card = base_model_card(
        dataset,
        model_kind="research_impact_quantiles",
        algorithm="gradient-boosted-quantile-regression",
        intended_use="Estimate a distribution for the explicitly defined public research-impact signal.",
        prohibited_uses=(
            "Claiming causal mission impact, program success, or an internal ONR outcome.",
            "Treating censored or not-yet-observed outcomes as zero-valued labels.",
        ),
        split=split,
        metrics=metrics,
        limitations=(
            "Public impact signals can be delayed, incomplete, and field-dependent.",
            "Independent quantile models are monotonically ordered at prediction time and raw crossing is reported.",
        ),
        output_semantics="Estimated 10th, 50th, and 90th quantiles of the reviewed public impact signal.",
    )
    return TrainingOutput(
        estimator=estimator,
        model_card=card,
        receipt=training_receipt(
            dataset,
            card,
            accepted_rows=len(accepted),
            excluded_rows=excluded,
        ),
    )

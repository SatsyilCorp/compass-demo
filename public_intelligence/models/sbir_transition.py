"""Calibrated SBIR transition classifier with group-safe temporal evidence."""

from __future__ import annotations

from typing import Sequence

from sklearn.compose import ColumnTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .common import (
    TrainingOutput,
    base_model_card,
    binary_metrics,
    fit_heldout_sigmoid_calibrator,
    grouped_temporal_three_way_split,
    require_class_support,
    split_evidence,
    subgroup_metrics,
    tabular_feature_names,
    tabular_matrix,
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


def _labels(rows) -> list[int]:
    return [int(bool(row.label_value)) for row in rows]


def _subgroup_classification(actual: Sequence[int], predicted: Sequence[int]):
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 8),
        "f1": round(float(f1_score(actual, predicted, zero_division=0)), 8),
    }


def transition_feature_names(
    dataset: CanonicalDataset,
) -> tuple[tuple[str, ...], tuple[str, ...], str | None]:
    numeric, categorical = tabular_feature_names(dataset)
    raw_text = dataset.manifest["feature_schema"].get("text_field")
    text_field = str(raw_text) if isinstance(raw_text, str) and raw_text else None
    return numeric, categorical, text_field


def transition_matrix(rows, numeric, categorical, text_field):
    values = tabular_matrix(rows, numeric, categorical)
    if text_field:
        for row_values, row in zip(values, rows):
            raw = row.features.get(text_field)
            row_values.append(str(raw or ""))
    return values


def _gradient_boosting_pipeline(numeric, categorical, text_field):
    transformers = []
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                list(range(len(numeric))),
            )
        )
    if categorical:
        start = len(numeric)
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "one_hot",
                            OneHotEncoder(
                                handle_unknown="infrequent_if_exist",
                                min_frequency=10,
                                sparse_output=False,
                            ),
                        ),
                    ]
                ),
                list(range(start, start + len(categorical))),
            )
        )
    if text_field:
        transformers.append(
            (
                "text",
                Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                lowercase=True,
                                strip_accents="unicode",
                                ngram_range=(1, 2),
                                min_df=5,
                                max_df=0.98,
                                max_features=12_000,
                                sublinear_tf=True,
                            ),
                        ),
                        (
                            "semantic_components",
                            TruncatedSVD(n_components=48, random_state=RANDOM_SEED),
                        ),
                    ]
                ),
                len(numeric) + len(categorical),
            )
        )
    return Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    transformers,
                    remainder="drop",
                    sparse_threshold=0.0,
                ),
            ),
            (
                "classifier",
                HistGradientBoostingClassifier(
                    learning_rate=0.05,
                    max_iter=240,
                    max_leaf_nodes=31,
                    max_depth=8,
                    min_samples_leaf=24,
                    l2_regularization=1.0,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def train_sbir_transition(dataset: CanonicalDataset) -> TrainingOutput:
    require_target(dataset, "sbir_transition_observed")
    require_minimum(dataset, 80)
    require_binary_labels(dataset)
    horizon = dataset.manifest.get("outcome_horizon_months")
    if horizon not in {24, 36}:
        raise TrainingRefusal(
            "invalid_contract",
            "SBIR transition horizon must be exactly 24 or 36 months",
        )
    for row in dataset.rows:
        if row.label_observed_at <= row.event_time:
            raise TrainingRefusal(
                "temporal_cutoff_violation",
                "SBIR outcome observation must occur after prediction time",
            )
    fit_rows, calibration_rows, test_rows = grouped_temporal_three_way_split(
        dataset.rows,
        minimum_groups=(6, 3, 3),
    )
    phases = {
        "fit": _labels(fit_rows),
        "calibration": _labels(calibration_rows),
        "test": _labels(test_rows),
    }
    require_class_support(
        phases,
        minimum={"fit": 10, "calibration": 4, "test": 4},
    )
    numeric, categorical, text_field = transition_feature_names(dataset)
    base = _gradient_boosting_pipeline(numeric, categorical, text_field)
    base.fit(
        transition_matrix(fit_rows, numeric, categorical, text_field),
        phases["fit"],
    )
    calibrated = fit_heldout_sigmoid_calibrator(
        base,
        transition_matrix(calibration_rows, numeric, categorical, text_field),
        phases["calibration"],
    )
    test_X = transition_matrix(test_rows, numeric, categorical, text_field)
    probabilities = calibrated.predict_proba(test_X)[:, 1]
    predictions = calibrated.predict(test_X)
    aggregate = binary_metrics(phases["test"], predictions, probabilities)
    metrics = {
        "holdout": aggregate,
        "subgroups": subgroup_metrics(
            test_rows,
            phases["test"],
            predictions,
            subgroup_fields=dataset.subgroup_fields,
            minimum_size=dataset.minimum_subgroup_size,
            metric_fn=_subgroup_classification,
        ),
    }
    split = split_evidence(
        {"fit": fit_rows, "calibration": calibration_rows, "test": test_rows},
        grouped=True,
    )
    card = base_model_card(
        dataset,
        model_kind="sbir_transition",
        algorithm="calibrated-histogram-gradient-boosting-with-tfidf-svd",
        intended_use=(
            "Estimate the probability of the explicitly observed public SBIR transition "
            f"label within the reviewed {horizon}-month horizon."
        ),
        prohibited_uses=(
            "Calling the output commercialization, mission success, or an internal ONR decision.",
            "Using Phase II or follow-on information that was unavailable at prediction time.",
            "Using one organization or topic group in more than one split.",
        ),
        split=split,
        metrics=metrics,
        limitations=(
            "The target represents an observed public transition record only.",
            "Unlinked or late-published public records can create false negatives.",
            "The model does not estimate internal ONR mission success or causation.",
        ),
        output_semantics="Calibrated probability of the reviewed public transition label.",
    )
    return TrainingOutput(
        estimator=calibrated,
        model_card=card,
        receipt=training_receipt(dataset, card, accepted_rows=len(dataset.rows)),
    )

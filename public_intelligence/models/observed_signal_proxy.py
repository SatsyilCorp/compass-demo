"""Observed public-signal proxy with an explicit non-success claim boundary."""

from __future__ import annotations

from typing import Sequence

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline

from .common import (
    TrainingOutput,
    base_model_card,
    binary_metrics,
    fit_heldout_sigmoid_calibrator,
    require_class_support,
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
    parse_time,
    require_binary_labels,
    require_minimum,
    require_target,
)


PROHIBITED_CLAIMS = (
    "internal onr success",
    "mission success",
    "program success",
    "onr success",
)


def _labels(rows) -> list[int]:
    return [int(bool(row.label_value)) for row in rows]


def _subgroup_metrics(actual: Sequence[int], predicted: Sequence[int]):
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 8),
        "f1": round(float(f1_score(actual, predicted, zero_division=0)), 8),
    }


def _reviewed_signal_contract(dataset: CanonicalDataset) -> dict:
    signal = dataset.manifest.get("observed_signal")
    if not isinstance(signal, dict) or signal.get("reviewed") is not True:
        raise TrainingRefusal(
            "signal_definition_not_reviewed",
            "observed public signal requires explicit review evidence",
        )
    for field in (
        "signal_name",
        "definition",
        "review_id",
        "reviewed_by",
        "reviewed_at",
    ):
        if not isinstance(signal.get(field), str) or not signal[field].strip():
            raise TrainingRefusal(
                "signal_definition_not_reviewed", f"observed_signal.{field} is required"
            )
    if signal["signal_name"] != dataset.target_name:
        raise TrainingRefusal(
            "signal_definition_mismatch", "observed signal name must match the target"
        )
    sources = signal.get("public_source_classes")
    if (
        not isinstance(sources, list)
        or not sources
        or any(not isinstance(value, str) or not value.strip() for value in sources)
    ):
        raise TrainingRefusal(
            "signal_definition_not_reviewed", "public source classes are required"
        )
    definition = signal["definition"].casefold()
    if "public" not in definition or "observed" not in definition:
        raise TrainingRefusal(
            "unsupported_internal_outcome_claim",
            "signal definition must describe an externally observed public signal",
        )
    if any(value in definition for value in PROHIBITED_CLAIMS):
        raise TrainingRefusal(
            "unsupported_internal_outcome_claim",
            "the model cannot train against an internal ONR success claim",
        )
    parse_time(signal["reviewed_at"], field="observed_signal.reviewed_at")
    return signal


def train_observed_signal_proxy(dataset: CanonicalDataset) -> TrainingOutput:
    require_target(dataset, "observed_public_success_signal")
    require_minimum(dataset, 80)
    require_binary_labels(dataset)
    signal = _reviewed_signal_contract(dataset)
    for row in dataset.rows:
        if row.label_observed_at <= row.event_time:
            raise TrainingRefusal(
                "temporal_cutoff_violation",
                "observed public signal must be recorded after prediction time",
            )
    fit_rows, calibration_rows, test_rows = temporal_three_way_split(
        dataset.rows,
        minimum_fit=40,
        minimum_calibration=16,
        minimum_test=16,
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
    numeric, categorical = tabular_feature_names(dataset)
    base = Pipeline(
        [
            ("features", tabular_preprocessor(numeric, categorical)),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=2_000,
                    random_state=RANDOM_SEED,
                    solver="liblinear",
                ),
            ),
        ]
    )
    base.fit(tabular_matrix(fit_rows, numeric, categorical), phases["fit"])
    estimator = fit_heldout_sigmoid_calibrator(
        base,
        tabular_matrix(calibration_rows, numeric, categorical),
        phases["calibration"],
    )
    test_X = tabular_matrix(test_rows, numeric, categorical)
    probabilities = estimator.predict_proba(test_X)[:, 1]
    predictions = estimator.predict(test_X)
    metrics = {
        "holdout": binary_metrics(phases["test"], predictions, probabilities),
        "subgroups": subgroup_metrics(
            test_rows,
            phases["test"],
            predictions,
            subgroup_fields=dataset.subgroup_fields,
            minimum_size=dataset.minimum_subgroup_size,
            metric_fn=_subgroup_metrics,
        ),
    }
    split = split_evidence(
        {"fit": fit_rows, "calibration": calibration_rows, "test": test_rows},
        grouped=False,
    )
    card = base_model_card(
        dataset,
        model_kind="observed_signal_proxy",
        algorithm="calibrated-logistic-regression",
        intended_use="Estimate the probability of the reviewed externally observed public signal.",
        prohibited_uses=(
            "Calling the output internal ONR success, program success, mission success, or causation.",
            "Using the output as a substitute for an ONR decision, evaluation, or authoritative record.",
        ),
        split=split,
        metrics=metrics,
        limitations=(
            "The target is an external public observation and can be missing or delayed.",
            "The proxy can reflect publication and reporting behavior rather than underlying outcomes.",
        ),
        output_semantics=(
            "Calibrated likelihood of the named observed public signal. It is never an "
            "estimate of internal ONR success."
        ),
    )
    card["observed_signal_contract"] = {
        "signal_name": signal["signal_name"],
        "definition": signal["definition"],
        "public_source_classes": list(signal["public_source_classes"]),
        "review_id": signal["review_id"],
    }
    return TrainingOutput(
        estimator=estimator,
        model_card=card,
        receipt=training_receipt(dataset, card, accepted_rows=len(dataset.rows)),
    )

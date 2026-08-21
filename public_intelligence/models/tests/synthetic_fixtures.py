"""Clearly labeled synthetic fixtures. Never accepted by the production CLI."""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from public_intelligence.models.contracts import dataset_from_records


FIXTURE_START = datetime(2018, 1, 1, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def manifest(
    model_kind: str,
    target_name: str,
    target_definition: str,
    *,
    numeric: list[str] | None = None,
    categorical: list[str] | None = None,
    text_field: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "numeric": list(numeric or []),
        "categorical": list(categorical or []),
    }
    if text_field:
        schema["text_field"] = text_field
    result = {
        "record_type": "manifest",
        "contract": "compass.public-intelligence.dataset.v1",
        "model_kind": model_kind,
        "dataset_id": f"synthetic-test-{model_kind}",
        "dataset_version": "test-v1",
        "created_at": "2026-08-11T12:00:00Z",
        "as_of_time": "2026-08-11T12:00:00Z",
        "evidence_set": {
            "kind": "synthetic_test_fixture",
            "snapshot_id": f"synthetic-test-{model_kind}-snapshot",
            "as_of_at": "2026-08-11T12:00:00Z",
            "manifest_sha256": _digest(f"synthetic-test-{model_kind}-manifest"),
        },
        "target": {
            "name": target_name,
            "definition": target_definition,
            "authenticity_required": True,
        },
        "feature_schema": schema,
        "subgroup_fields": ["organization_type"],
        "minimum_subgroup_size": 5,
        "test_fixture": True,
    }
    result.update(dict(extra or {}))
    return result


def row(
    dataset_manifest: Mapping[str, Any],
    index: int,
    *,
    features: Mapping[str, Any],
    label_value: Any,
    event_time: datetime | None = None,
    group_id: str | None = None,
    label_status: str = "observed",
    label_authentic: bool | None = None,
    label_observed_at: datetime | None = None,
) -> dict[str, Any]:
    event = event_time or FIXTURE_START + timedelta(days=index * 7)
    observed = label_observed_at or event + timedelta(days=365)
    if label_authentic is None:
        label_authentic = label_status == "observed"
    record_id = f"synthetic-test-record-{index:05d}"
    return {
        "record_type": "training_row",
        "contract": "compass.public-intelligence.training-row.v1",
        "record_id": record_id,
        "event_time": _iso(event),
        "group_id": group_id,
        "features": dict(features),
        "feature_lineage": [
            {
                "feature": feature,
                "source_record_ids": [f"synthetic-source-{index}-{feature}"],
                "max_available_at": _iso(event - timedelta(days=1)),
                "evidence_class": "synthetic_test_fixture",
            }
            for feature, value in features.items()
            if value is not None
        ],
        "label": {
            "name": dataset_manifest["target"]["name"],
            "status": label_status,
            "value": label_value,
            "authentic": label_authentic,
            "source_uri": f"fixture://labels/{record_id}",
            "observed_at": _iso(observed),
        },
        "subgroups": {
            "organization_type": "academic" if index % 2 == 0 else "industry"
        },
        "provenance": {
            "evidence_set_id": dataset_manifest["evidence_set"]["snapshot_id"],
            "source_uri": f"fixture://records/{record_id}",
            "source_sha256": _digest(record_id),
            "authorized_for_training": True,
            "rights": "synthetic_test_fixture",
            "pii_minimized": True,
            "protected_features_excluded": True,
            "test_fixture": True,
        },
    }


def dataset(records: list[dict[str, Any]]):
    return dataset_from_records(records, allow_test_fixtures=True)


def funding_fixture(count: int = 90):
    head = manifest(
        "funding_forecast",
        "funding_amount",
        "Synthetic fixture funding amount used only for offline algorithm tests.",
        numeric=["prior_amount", "award_age_months"],
        categorical=["program_area"],
        extra={"prediction_interval_coverage": 0.90},
    )
    rows = [head]
    for index in range(count):
        prior = 100_000 + index * 2_500
        amount = prior * 1.08 + (index % 5) * 1_000
        rows.append(
            row(
                head,
                index,
                features={
                    "prior_amount": prior,
                    "award_age_months": index % 36,
                    "program_area": "autonomy" if index % 2 else "materials",
                },
                label_value=amount,
            )
        )
    return dataset(rows)


def sbir_fixture(groups: int = 18, rows_per_group: int = 6):
    head = manifest(
        "sbir_transition",
        "sbir_transition_observed",
        "Synthetic fixture public SBIR transition observation for algorithm tests.",
        numeric=["prior_awards", "prior_obligation"],
        categorical=["topic_family"],
        extra={"outcome_horizon_months": 36},
    )
    rows = [head]
    index = 0
    for group in range(groups):
        group_start = FIXTURE_START + timedelta(days=group * 30)
        for within in range(rows_per_group):
            label = within % 2
            rows.append(
                row(
                    head,
                    index,
                    event_time=group_start + timedelta(days=within),
                    group_id=f"synthetic-group-{group:03d}",
                    features={
                        "prior_awards": within + label * 2,
                        "prior_obligation": 25_000 + group * 500 + label * 10_000,
                        "topic_family": "sensing" if group % 2 else "autonomy",
                    },
                    label_value=label,
                )
            )
            index += 1
    return dataset(rows)


def technology_fixture(labels: tuple[str, ...] = ("autonomy", "materials", "sensing")):
    head = manifest(
        "technology_classifier",
        "technology_taxonomy_label",
        "Synthetic fixture reviewed technology label for algorithm tests.",
        text_field="abstract_text",
        extra={
            "taxonomy": {
                "labels": list(labels),
                "reviewed": True,
                "review_id": "synthetic-test-review",
                "reviewed_by": "offline-test-reviewer",
                "reviewed_at": "2026-08-11T11:00:00Z",
            }
        },
    )
    vocabulary = {
        "autonomy": "autonomous navigation planning maritime vehicle control mission routing",
        "materials": "advanced composite thermal material manufacturing coating durability",
        "sensing": "distributed sensor signal detection radar imaging measurement array",
    }
    rows = [head]
    index = 0
    for label in labels:
        for example in range(10):
            text = (
                f"{vocabulary[label]} synthetic fixture example {example}. "
                f"This paragraph contains enough reviewed test language for class {label}."
            )
            rows.append(
                row(
                    head,
                    index,
                    features={"abstract_text": text},
                    label_value=label,
                )
            )
            index += 1
    return dataset(rows)


def impact_fixture(count: int = 120, censored: int = 12):
    head = manifest(
        "research_impact_quantiles",
        "research_impact_score",
        "Synthetic fixture public research-impact score for algorithm tests.",
        numeric=["publication_count", "patent_count"],
        categorical=["field"],
        extra={"outcome_observation_cutoff": "2026-08-11T12:00:00Z"},
    )
    rows = [head]
    for index in range(count):
        is_censored = index >= count - censored
        rows.append(
            row(
                head,
                index,
                features={
                    "publication_count": index % 20,
                    "patent_count": index % 4,
                    "field": "engineering" if index % 2 else "physical_science",
                },
                label_value=None
                if is_censored
                else float(index % 20 + (index % 4) * 2),
                label_status="censored" if is_censored else "observed",
                label_authentic=not is_censored,
            )
        )
    return dataset(rows)


def anomaly_fixture(count: int = 120):
    head = manifest(
        "anomaly_detection",
        "reviewed_anomaly",
        "Synthetic fixture analyst-reviewed anomaly flag for algorithm tests.",
        numeric=["amount_ratio", "schedule_variance"],
        categorical=["peer_group"],
        extra={
            "isolation_contamination": 0.10,
            "anomaly_rules": [
                {
                    "rule_id": "synthetic-high-ratio",
                    "feature": "amount_ratio",
                    "operator": "gt",
                    "value": 3.0,
                    "reviewed": True,
                    "reviewed_by": "offline-test-reviewer",
                    "review_id": "synthetic-rule-review",
                    "reviewed_at": "2026-08-11T11:00:00Z",
                }
            ],
        },
    )
    rows = [head]
    for index in range(count):
        flagged = index % 5 == 0
        rows.append(
            row(
                head,
                index,
                features={
                    "amount_ratio": 5.0 if flagged else 1.0 + (index % 7) / 20,
                    "schedule_variance": 1.5 if flagged else (index % 5) / 10,
                    "peer_group": "large" if index % 2 else "small",
                },
                label_value=int(flagged),
            )
        )
    return dataset(rows)


def observed_signal_fixture(count: int = 100, *, internal_claim: bool = False):
    definition = (
        "Internal ONR success for a program."
        if internal_claim
        else "Externally observed public follow-on signal in reviewed public records."
    )
    head = manifest(
        "observed_signal_proxy",
        "observed_public_success_signal",
        definition,
        numeric=["publications_before_cutoff", "patents_before_cutoff"],
        categorical=["technology_family"],
        extra={
            "observed_signal": {
                "signal_name": "observed_public_success_signal",
                "definition": definition,
                "public_source_classes": ["publications", "patents"],
                "reviewed": True,
                "review_id": "synthetic-signal-review",
                "reviewed_by": "offline-test-reviewer",
                "reviewed_at": "2026-08-11T11:00:00Z",
            }
        },
    )
    rows = [head]
    for index in range(count):
        label = index % 2
        rows.append(
            row(
                head,
                index,
                features={
                    "publications_before_cutoff": index % 8 + label * 2,
                    "patents_before_cutoff": index % 3 + label,
                    "technology_family": "energy" if index % 2 else "autonomy",
                },
                label_value=label,
            )
        )
    return dataset(rows)


def clone_records(dataset_value) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(dataset_value.manifest),
        *(copy.deepcopy(row.raw) for row in dataset_value.rows),
    ]

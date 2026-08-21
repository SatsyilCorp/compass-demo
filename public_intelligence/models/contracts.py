"""Canonical dataset contracts and refusal gates for the model suite."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DATASET_CONTRACT = "compass.public-intelligence.dataset.v1"
ROW_CONTRACT = "compass.public-intelligence.training-row.v1"
MODEL_KINDS = {
    "funding_forecast",
    "sbir_transition",
    "technology_classifier",
    "research_impact_quantiles",
    "anomaly_detection",
    "observed_signal_proxy",
}
RANDOM_SEED = 20260811
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class TrainingRefusal(ValueError):
    """Raised when evidence is insufficient or unsafe for model training."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _refuse(code: str, message: str) -> None:
    raise TrainingRefusal(code, message)


def parse_time(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        _refuse("invalid_timestamp", f"{field} must be a non-empty ISO-8601 timestamp")
    rendered = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(rendered)
    except ValueError as exc:
        raise TrainingRefusal(
            "invalid_timestamp", f"{field} must be a valid ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        _refuse("invalid_timestamp", f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CanonicalRow:
    record_id: str
    event_time: datetime
    group_id: str | None
    features: Mapping[str, Any]
    label_name: str
    label_value: Any
    label_status: str
    label_authentic: bool
    label_source_uri: str
    label_observed_at: datetime
    subgroups: Mapping[str, str]
    source_uri: str
    source_sha256: str
    authorized_for_training: bool
    test_fixture: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class CanonicalDataset:
    manifest: Mapping[str, Any]
    rows: tuple[CanonicalRow, ...]
    dataset_digest: str
    test_fixture: bool

    @property
    def model_kind(self) -> str:
        return str(self.manifest["model_kind"])

    @property
    def target_name(self) -> str:
        return str(self.manifest["target"]["name"])

    @property
    def subgroup_fields(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self.manifest.get("subgroup_fields", []))

    @property
    def minimum_subgroup_size(self) -> int:
        return int(self.manifest.get("minimum_subgroup_size", 10))


def _required_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _refuse("invalid_contract", f"{field} must be an object")
    return value


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _refuse("invalid_contract", f"{field} must be a non-empty string")
    return value.strip()


def _validate_manifest(raw: Mapping[str, Any], *, allow_test_fixtures: bool) -> bool:
    if raw.get("record_type") != "manifest" or raw.get("contract") != DATASET_CONTRACT:
        _refuse(
            "invalid_contract", "the first JSONL record must be the canonical manifest"
        )
    model_kind = _required_string(raw.get("model_kind"), "manifest.model_kind")
    if model_kind not in MODEL_KINDS:
        _refuse("unsupported_model", f"unsupported model_kind {model_kind!r}")
    for field in ("dataset_id", "dataset_version", "created_at", "as_of_time"):
        _required_string(raw.get(field), f"manifest.{field}")
    parse_time(raw["created_at"], field="manifest.created_at")
    parse_time(raw["as_of_time"], field="manifest.as_of_time")
    evidence_set = _required_mapping(raw.get("evidence_set"), "manifest.evidence_set")
    for field in ("snapshot_id", "as_of_at", "manifest_sha256"):
        _required_string(evidence_set.get(field), f"manifest.evidence_set.{field}")
    parse_time(evidence_set["as_of_at"], field="manifest.evidence_set.as_of_at")
    if not SHA256_RE.fullmatch(str(evidence_set["manifest_sha256"]).lower()):
        _refuse("invalid_provenance", "manifest evidence-set digest is invalid")
    target = _required_mapping(raw.get("target"), "manifest.target")
    _required_string(target.get("name"), "manifest.target.name")
    _required_string(target.get("definition"), "manifest.target.definition")
    if target.get("authenticity_required") is not True:
        _refuse(
            "authentic_labels_required",
            "manifest.target.authenticity_required must be true",
        )
    schema = _required_mapping(raw.get("feature_schema"), "manifest.feature_schema")
    numeric = schema.get("numeric", [])
    categorical = schema.get("categorical", [])
    if not isinstance(numeric, list) or not isinstance(categorical, list):
        _refuse("invalid_contract", "feature_schema lists must be arrays")
    names = [str(value).strip() for value in [*numeric, *categorical]]
    text_field = schema.get("text_field")
    if text_field is not None:
        names.append(_required_string(text_field, "manifest.feature_schema.text_field"))
    if not names or any(not value for value in names) or len(names) != len(set(names)):
        _refuse("invalid_contract", "feature names must be non-empty and unique")
    target_name = str(target["name"])
    prohibited = {
        target_name.casefold(),
        "label",
        "target",
        *(
            str(value).casefold()
            for value in raw.get("leakage_prohibited_features", [])
        ),
    }
    leaked = sorted(value for value in names if value.casefold() in prohibited)
    if leaked:
        _refuse(
            "label_leakage",
            "feature schema contains prohibited outcome fields: " + ", ".join(leaked),
        )
    subgroup_fields = raw.get("subgroup_fields", [])
    if not isinstance(subgroup_fields, list) or any(
        not isinstance(value, str) or not value.strip() for value in subgroup_fields
    ):
        _refuse("invalid_contract", "subgroup_fields must be an array of names")
    minimum_subgroup_size = raw.get("minimum_subgroup_size", 10)
    if (
        isinstance(minimum_subgroup_size, bool)
        or not isinstance(minimum_subgroup_size, int)
        or minimum_subgroup_size < 5
    ):
        _refuse("invalid_contract", "minimum_subgroup_size must be at least 5")
    test_fixture = raw.get("test_fixture") is True
    if test_fixture and not allow_test_fixtures:
        _refuse(
            "test_fixture_forbidden",
            "synthetic test fixtures are not accepted by the production trainer",
        )
    expected_kind = "synthetic_test_fixture" if test_fixture else "public"
    if evidence_set.get("kind") != expected_kind:
        _refuse(
            "evidence_set_mixed",
            f"evidence_set.kind must be {expected_kind!r} for this dataset",
        )
    return test_fixture


def _validate_row(
    raw: Mapping[str, Any],
    *,
    index: int,
    manifest: Mapping[str, Any],
    test_fixture: bool,
) -> CanonicalRow:
    prefix = f"row[{index}]"
    if raw.get("record_type") != "training_row" or raw.get("contract") != ROW_CONTRACT:
        _refuse(
            "invalid_contract", f"{prefix} does not match the canonical row contract"
        )
    record_id = _required_string(raw.get("record_id"), f"{prefix}.record_id")
    event_time = parse_time(raw.get("event_time"), field=f"{prefix}.event_time")
    group_id = raw.get("group_id")
    if group_id is not None:
        group_id = _required_string(group_id, f"{prefix}.group_id")
    features = _required_mapping(raw.get("features"), f"{prefix}.features")
    schema = manifest["feature_schema"]
    allowed_features = {
        *(str(value) for value in schema.get("numeric", [])),
        *(str(value) for value in schema.get("categorical", [])),
    }
    if schema.get("text_field") is not None:
        allowed_features.add(str(schema["text_field"]))
    unknown = sorted(set(features) - allowed_features)
    if unknown:
        _refuse(
            "unexpected_feature",
            f"{prefix} contains features outside the reviewed schema: "
            + ", ".join(unknown),
        )
    lineage = raw.get("feature_lineage")
    if not isinstance(lineage, list):
        _refuse("invalid_contract", f"{prefix}.feature_lineage must be an array")
    lineage_by_feature: dict[str, Mapping[str, Any]] = {}
    for lineage_index, item in enumerate(lineage):
        entry = _required_mapping(item, f"{prefix}.feature_lineage[{lineage_index}]")
        feature = _required_string(
            entry.get("feature"), f"{prefix}.feature_lineage[{lineage_index}].feature"
        )
        if feature in lineage_by_feature:
            _refuse(
                "invalid_contract", f"{prefix} repeats feature lineage for {feature}"
            )
        available_at = parse_time(
            entry.get("max_available_at"),
            field=f"{prefix}.feature_lineage[{lineage_index}].max_available_at",
        )
        source_record_ids = entry.get("source_record_ids")
        if not isinstance(source_record_ids, list) or not source_record_ids:
            _refuse(
                "invalid_provenance", f"{prefix} feature lineage needs source records"
            )
        if available_at > event_time:
            _refuse(
                "temporal_cutoff_violation",
                f"{prefix} feature {feature!r} was not available by prediction time",
            )
        lineage_by_feature[feature] = entry
    present_features = {field for field, value in features.items() if value is not None}
    if set(lineage_by_feature) != present_features:
        _refuse(
            "feature_lineage_mismatch",
            f"{prefix} must provide lineage for every present feature and no others",
        )
    for field in schema.get("numeric", []):
        value = features.get(str(field))
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            _refuse(
                "invalid_feature",
                f"{prefix}.features.{field} must be finite numeric data",
            )
    label = _required_mapping(raw.get("label"), f"{prefix}.label")
    label_name = _required_string(label.get("name"), f"{prefix}.label.name")
    target_name = str(manifest["target"]["name"])
    if label_name != target_name:
        _refuse(
            "label_contract_mismatch",
            f"{prefix} label {label_name!r} does not match target {target_name!r}",
        )
    label_status = _required_string(label.get("status"), f"{prefix}.label.status")
    if label_status not in {"observed", "censored"}:
        _refuse("invalid_label", f"{prefix}.label.status is unsupported")
    if (
        label_status == "censored"
        and manifest.get("model_kind") != "research_impact_quantiles"
    ):
        _refuse("target_censored", f"{prefix} has a censored label for this model")
    label_authentic = label.get("authentic") is True
    if label_status == "observed" and not label_authentic:
        _refuse("authentic_labels_required", f"{prefix} lacks an authentic label")
    if label_status == "censored" and label.get("value") is not None:
        _refuse("target_censored", f"{prefix} censored labels cannot contain a value")
    if label_status == "censored" and label_authentic:
        _refuse(
            "target_censored",
            f"{prefix} censored labels cannot be marked as observed authentic labels",
        )
    label_source_uri = _required_string(
        label.get("source_uri"), f"{prefix}.label.source_uri"
    )
    label_observed_at = parse_time(
        label.get("observed_at"), field=f"{prefix}.label.observed_at"
    )
    subgroups_raw = _required_mapping(raw.get("subgroups", {}), f"{prefix}.subgroups")
    subgroups: dict[str, str] = {}
    for field in manifest.get("subgroup_fields", []):
        value = subgroups_raw.get(str(field))
        if value is not None:
            subgroups[str(field)] = _required_string(
                value, f"{prefix}.subgroups.{field}"
            )
    provenance = _required_mapping(raw.get("provenance"), f"{prefix}.provenance")
    expected_evidence_set = str(manifest["evidence_set"]["snapshot_id"])
    if provenance.get("evidence_set_id") != expected_evidence_set:
        _refuse("evidence_set_mixed", f"{prefix} references another evidence set")
    source_uri = _required_string(
        provenance.get("source_uri"), f"{prefix}.provenance.source_uri"
    )
    source_sha256 = _required_string(
        provenance.get("source_sha256"), f"{prefix}.provenance.source_sha256"
    ).lower()
    if not SHA256_RE.fullmatch(source_sha256):
        _refuse("invalid_provenance", f"{prefix} source_sha256 is invalid")
    authorized = provenance.get("authorized_for_training") is True
    if not authorized:
        _refuse("training_not_authorized", f"{prefix} is not authorized for training")
    row_test_fixture = provenance.get("test_fixture") is True
    if row_test_fixture != test_fixture:
        _refuse(
            "fixture_mismatch", f"{prefix} fixture marking does not match the manifest"
        )
    expected_rights = "synthetic_test_fixture" if test_fixture else "public"
    if provenance.get("rights") != expected_rights:
        _refuse("rights_not_permitted", f"{prefix} has unapproved data rights")
    if provenance.get("pii_minimized") is not True:
        _refuse("pii_not_minimized", f"{prefix} lacks PII-minimization evidence")
    if provenance.get("protected_features_excluded") is not True:
        _refuse(
            "protected_feature_present",
            f"{prefix} lacks protected-feature exclusion evidence",
        )
    return CanonicalRow(
        record_id=record_id,
        event_time=event_time,
        group_id=group_id,
        features=features,
        label_name=label_name,
        label_value=label.get("value"),
        label_status=label_status,
        label_authentic=label_authentic,
        label_source_uri=label_source_uri,
        label_observed_at=label_observed_at,
        subgroups=subgroups,
        source_uri=source_uri,
        source_sha256=source_sha256,
        authorized_for_training=authorized,
        test_fixture=row_test_fixture,
        raw=raw,
    )


def dataset_from_records(
    records: Sequence[Mapping[str, Any]], *, allow_test_fixtures: bool = False
) -> CanonicalDataset:
    if len(records) < 2:
        _refuse("insufficient_samples", "canonical JSONL requires a manifest and rows")
    manifest = records[0]
    test_fixture = _validate_manifest(manifest, allow_test_fixtures=allow_test_fixtures)
    rows = tuple(
        _validate_row(
            raw,
            index=index,
            manifest=manifest,
            test_fixture=test_fixture,
        )
        for index, raw in enumerate(records[1:], start=1)
    )
    record_ids = [row.record_id for row in rows]
    if len(record_ids) != len(set(record_ids)):
        _refuse("duplicate_record_id", "record_id values must be unique")
    dataset_digest = digest_json([manifest, *(row.raw for row in rows)])
    return CanonicalDataset(
        manifest=dict(manifest),
        rows=rows,
        dataset_digest=dataset_digest,
        test_fixture=test_fixture,
    )


def load_canonical_jsonl(
    path: str | Path, *, allow_test_fixtures: bool = False
) -> CanonicalDataset:
    source = Path(path)
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TrainingRefusal("dataset_unreadable", f"cannot read {source}") from exc
    records: list[Mapping[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TrainingRefusal(
                "invalid_jsonl", f"line {number} is not valid JSON"
            ) from exc
        if not isinstance(value, Mapping):
            _refuse("invalid_jsonl", f"line {number} must contain a JSON object")
        records.append(value)
    return dataset_from_records(records, allow_test_fixtures=allow_test_fixtures)


def require_minimum(dataset: CanonicalDataset, count: int) -> None:
    if len(dataset.rows) < count:
        _refuse(
            "insufficient_samples",
            f"{dataset.model_kind} requires at least {count} authentic labeled rows",
        )


def require_target(dataset: CanonicalDataset, expected: str) -> None:
    if dataset.target_name != expected:
        _refuse(
            "unsupported_target",
            f"{dataset.model_kind} requires target {expected!r}, not {dataset.target_name!r}",
        )


def require_binary_labels(dataset: CanonicalDataset) -> tuple[int, ...]:
    values: list[int] = []
    for row in dataset.rows:
        value = row.label_value
        if isinstance(value, bool):
            values.append(int(value))
        elif value in (0, 1):
            values.append(int(value))
        else:
            _refuse(
                "invalid_label", f"{dataset.target_name} must contain binary labels"
            )
    if set(values) != {0, 1}:
        _refuse(
            "insufficient_label_support", "binary target requires both observed classes"
        )
    return tuple(values)


def require_numeric_labels(dataset: CanonicalDataset) -> tuple[float, ...]:
    values: list[float] = []
    for row in dataset.rows:
        value = row.label_value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _refuse(
                "invalid_label", f"{dataset.target_name} must contain numeric labels"
            )
        rendered = float(value)
        if not math.isfinite(rendered):
            _refuse("invalid_label", f"{dataset.target_name} labels must be finite")
        values.append(rendered)
    if len(set(values)) < 3:
        _refuse(
            "insufficient_label_support",
            "numeric target requires at least three values",
        )
    return tuple(values)


def count_labels(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))

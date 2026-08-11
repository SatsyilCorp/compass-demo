"""Deterministic synthetic workload generation for Compass scale exercises.

The generation interface is intentionally independent of AWS and database
clients. A record is a pure function of the workload profile, seed, dataset,
and record index. As a result, workers can generate disjoint partitions in any
order, retry one partition, or replay a prior run and receive identical bytes.

Profiles describe total records across six linked datasets. The profile total
is divided using fixed ratios, and all child records reference grants in the
same profile. Records are clearly marked as synthetic and contain no real
people, organizations, awards, or controlled information.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import re
from typing import Any, BinaryIO


CONTRACT_VERSION = "compass.synthetic-scale.v1"
DEFAULT_SEED = 20260811
REFERENCE_INSTANT = datetime(2026, 8, 11, tzinfo=timezone.utc)
REFERENCE_DATE = REFERENCE_INSTANT.date()

DATASETS = (
    "grants",
    "finance",
    "milestones",
    "documents",
    "licenses",
    "stream_events",
)

# Ratios total 100. A profile name always means total physical records, not
# the count in each dataset.
_DATASET_RATIOS = {
    "grants": 20,
    "finance": 30,
    "milestones": 20,
    "documents": 10,
    "licenses": 2,
    "stream_events": 18,
}


@dataclass(frozen=True)
class WorkloadProfile:
    """A fixed, bounded workload size and its default partition size."""

    name: str
    total_records: int
    default_partition_size: int

    @property
    def dataset_counts(self) -> dict[str, int]:
        counts = {
            dataset: self.total_records * ratio // 100
            for dataset, ratio in _DATASET_RATIOS.items()
        }
        # Ratios are exact for current profile sizes. Keep the final correction
        # so future profiles cannot silently lose records to integer rounding.
        counts[DATASETS[-1]] += self.total_records - sum(counts.values())
        return counts


PROFILES: dict[str, WorkloadProfile] = {
    "1k": WorkloadProfile("1k", 1_000, 1_000),
    "10k": WorkloadProfile("10k", 10_000, 5_000),
    "100k": WorkloadProfile("100k", 100_000, 10_000),
    "1m": WorkloadProfile("1m", 1_000_000, 25_000),
}


def get_profile(profile: str | WorkloadProfile) -> WorkloadProfile:
    """Resolve a fixed profile, rejecting unbounded caller supplied counts."""

    if isinstance(profile, WorkloadProfile):
        canonical = PROFILES.get(profile.name)
        if canonical != profile:
            raise ValueError("only fixed workload profiles are supported")
        return canonical
    key = str(profile).strip().lower()
    try:
        return PROFILES[key]
    except KeyError as exc:
        choices = ", ".join(PROFILES)
        raise ValueError(f"unknown workload profile {profile!r}; choose {choices}") from exc


def _require_dataset(dataset: str) -> str:
    if dataset not in DATASETS:
        choices = ", ".join(DATASETS)
        raise ValueError(f"unknown dataset {dataset!r}; choose {choices}")
    return dataset


def _require_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    if seed < 0 or seed > 9_999_999_999:
        raise ValueError("seed must be between 0 and 9999999999")
    return seed


def _counter_u64(seed: int, dataset: str, index: int, slot: str) -> int:
    """Return a stable pseudorandom integer without shared mutable state."""

    payload = f"{CONTRACT_VERSION}|{seed}|{dataset}|{index}|{slot}".encode("utf-8")
    digest = hashlib.blake2b(
        payload,
        digest_size=8,
        person=b"compass-scale-v1",
    ).digest()
    return int.from_bytes(digest, "big")


def _choice(
    values: Sequence[Any], seed: int, dataset: str, index: int, slot: str
) -> Any:
    return values[_counter_u64(seed, dataset, index, slot) % len(values)]


def _seed_tag(seed: int) -> str:
    return hashlib.sha256(str(seed).encode("ascii")).hexdigest()[:8]


def _record_id(kind: str, seed: int, index: int) -> str:
    return f"syn-{kind}-{_seed_tag(seed)}-{index:09d}"


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


PROGRAM_AREAS = (
    "AI and Machine Learning",
    "Autonomy",
    "Undersea Systems",
    "Directed Energy",
    "Quantum Science",
    "Cyber Resilience",
    "Advanced Materials",
    "Biotechnology",
)
PROGRAM_CODES = ("AIML", "AUTO", "USEA", "DEWX", "QNTM", "CYBR", "MATL", "BIOT")
ORG_UNITS = ("ONR-Corporate", "Code-30", "Code-31", "Code-32", "Code-34", "Code-35")
PERFORMERS = (
    "Fictional Bluewater Research LLC",
    "Fictional Meridian Systems Institute",
    "Fictional Northgate Applied Sciences",
    "Fictional Harborlight Technology Group",
    "Fictional Cascade Research Cooperative",
    "Fictional Cobalt Engineering Laboratory",
)
RESEARCH_TOPICS = (
    "Adaptive sensing for contested environments",
    "Resilient human machine mission planning",
    "Low latency multi-platform coordination",
    "Field deployable decision support",
    "Trustworthy edge analytics",
    "Energy efficient autonomous operations",
)


def _common(seed: int) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_VERSION,
        "synthetic": True,
        "synthetic_seed": seed,
        "source_system": "COMPASS-SYNTHETIC-SCALE",
    }


def _grant_record(seed: int, index: int) -> dict[str, Any]:
    program_number = _counter_u64(seed, "grants", index, "program") % len(PROGRAM_AREAS)
    program_area = PROGRAM_AREAS[program_number]
    fiscal_year = 2019 + _counter_u64(seed, "grants", index, "fiscal_year") % 8
    start = date(fiscal_year - 1, 10, 1) + timedelta(
        days=_counter_u64(seed, "grants", index, "start_day") % 365
    )
    duration_days = 365 + _counter_u64(seed, "grants", index, "duration") % 1_096
    end = start + timedelta(days=duration_days)
    if end < REFERENCE_DATE:
        status = "completed"
    elif start > REFERENCE_DATE:
        status = "planned"
    else:
        status = "active"
    grant_no = f"SYN-{fiscal_year}-{PROGRAM_CODES[program_number]}-{index:07d}"
    record = _common(seed)
    record.update(
        {
            "grant_id": _record_id("grant", seed, index),
            "grant_no": grant_no,
            "title": _choice(RESEARCH_TOPICS, seed, "grants", index, "title"),
            "program_area": program_area,
            "org_unit": _choice(ORG_UNITS, seed, "grants", index, "org_unit"),
            "performer": _choice(PERFORMERS, seed, "grants", index, "performer"),
            "fiscal_year": fiscal_year,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "award_amount_usd": 250_000
            + _counter_u64(seed, "grants", index, "award") % 24_750_001,
            "status": status,
            "classification": "UNCLASSIFIED-SYNTHETIC",
        }
    )
    return record


def _grant_reference(
    profile: WorkloadProfile, seed: int, dataset: str, index: int
) -> tuple[int, dict[str, Any]]:
    grant_count = profile.dataset_counts["grants"]
    grant_index = _counter_u64(seed, dataset, index, "grant_reference") % grant_count
    return grant_index, _grant_record(seed, grant_index)


def _finance_record(
    profile: WorkloadProfile, seed: int, index: int
) -> dict[str, Any]:
    _, grant = _grant_reference(profile, seed, "finance", index)
    start = date.fromisoformat(grant["start_date"])
    end = min(date.fromisoformat(grant["end_date"]), REFERENCE_DATE)
    span = max((end - start).days, 0)
    transaction_date = start + timedelta(
        days=_counter_u64(seed, "finance", index, "transaction_day") % (span + 1)
    )
    transaction_type = _choice(
        ("obligation", "expenditure", "commitment", "deobligation"),
        seed,
        "finance",
        index,
        "transaction_type",
    )
    amount = 10_000 + _counter_u64(seed, "finance", index, "amount") % 1_990_001
    if transaction_type == "deobligation":
        amount = -min(amount, 250_000)
    record = _common(seed)
    record.update(
        {
            "transaction_id": _record_id("finance", seed, index),
            "grant_id": grant["grant_id"],
            "grant_no": grant["grant_no"],
            "transaction_date": transaction_date.isoformat(),
            "fiscal_year": transaction_date.year
            + (1 if transaction_date.month >= 10 else 0),
            "transaction_type": transaction_type,
            "amount_usd": amount,
            "currency": "USD",
            "status": _choice(
                ("posted", "pending", "reconciled"),
                seed,
                "finance",
                index,
                "status",
            ),
            "appropriation": _choice(
                ("6.1", "6.2", "6.3", "6.4"),
                seed,
                "finance",
                index,
                "appropriation",
            ),
        }
    )
    return record


def _milestone_record(
    profile: WorkloadProfile, seed: int, index: int
) -> dict[str, Any]:
    _, grant = _grant_reference(profile, seed, "milestones", index)
    start = date.fromisoformat(grant["start_date"])
    end = date.fromisoformat(grant["end_date"])
    span = max((end - start).days, 1)
    due = start + timedelta(
        days=_counter_u64(seed, "milestones", index, "due_day") % (span + 1)
    )
    completion = _counter_u64(seed, "milestones", index, "completion") % 101
    if completion == 100:
        status = "complete"
    elif due < REFERENCE_DATE and completion < 80:
        status = "at_risk"
    elif completion > 0:
        status = "in_progress"
    else:
        status = "not_started"
    record = _common(seed)
    record.update(
        {
            "milestone_id": _record_id("milestone", seed, index),
            "grant_id": grant["grant_id"],
            "grant_no": grant["grant_no"],
            "milestone_type": _choice(
                ("design_review", "prototype", "field_test", "transition_review"),
                seed,
                "milestones",
                index,
                "milestone_type",
            ),
            "name": _choice(
                (
                    "Synthetic concept review",
                    "Synthetic prototype checkpoint",
                    "Synthetic integration assessment",
                    "Synthetic transition decision",
                ),
                seed,
                "milestones",
                index,
                "name",
            ),
            "due_date": due.isoformat(),
            "status": status,
            "completion_percent": completion,
            "risk_level": _choice(
                ("low", "moderate", "high"),
                seed,
                "milestones",
                index,
                "risk_level",
            ),
        }
    )
    return record


def _document_record(
    profile: WorkloadProfile, seed: int, index: int
) -> dict[str, Any]:
    _, grant = _grant_reference(profile, seed, "documents", index)
    start = datetime.combine(
        date.fromisoformat(grant["start_date"]), datetime.min.time(), tzinfo=timezone.utc
    )
    upper = max(int((REFERENCE_INSTANT - start).total_seconds()), 0)
    created = start + timedelta(
        seconds=_counter_u64(seed, "documents", index, "created") % (upper + 1)
    )
    document_id = _record_id("document", seed, index)
    document_type = _choice(
        ("technical_report", "milestone_evidence", "financial_report", "data_management_plan"),
        seed,
        "documents",
        index,
        "document_type",
    )
    record = _common(seed)
    record.update(
        {
            "document_id": document_id,
            "grant_id": grant["grant_id"],
            "grant_no": grant["grant_no"],
            "document_type": document_type,
            "title": f"Synthetic {document_type.replace('_', ' ')}",
            "mime_type": _choice(
                ("application/pdf", "application/json", "text/csv"),
                seed,
                "documents",
                index,
                "mime_type",
            ),
            "size_bytes": 4_096
            + _counter_u64(seed, "documents", index, "size") % 24_995_905,
            "content_sha256": hashlib.sha256(
                f"synthetic-document|{seed}|{index}".encode("ascii")
            ).hexdigest(),
            "created_at": _iso_z(created),
            "classification": "UNCLASSIFIED-SYNTHETIC",
        }
    )
    return record


def _license_record(seed: int, index: int) -> dict[str, Any]:
    start = date(2024, 1, 1) + timedelta(
        days=_counter_u64(seed, "licenses", index, "start") % 730
    )
    renewal = start + timedelta(
        days=365 * (1 + _counter_u64(seed, "licenses", index, "term") % 3)
    )
    status = "active" if renewal >= REFERENCE_DATE else "expired"
    record = _common(seed)
    record.update(
        {
            "license_id": _record_id("license", seed, index),
            "data_product": _choice(
                (
                    "Fictional Maritime Signals Feed",
                    "Fictional Research Citation Graph",
                    "Fictional Materials Property Index",
                    "Fictional Technology Market Monitor",
                ),
                seed,
                "licenses",
                index,
                "data_product",
            ),
            "vendor": _choice(
                (
                    "Fictional Atlas Data Cooperative",
                    "Fictional Pelican Information LLC",
                    "Fictional Northstar Data Works",
                ),
                seed,
                "licenses",
                index,
                "vendor",
            ),
            "owning_org": _choice(ORG_UNITS, seed, "licenses", index, "owning_org"),
            "start_date": start.isoformat(),
            "renewal_date": renewal.isoformat(),
            "status": status,
            "seats": 5 + _counter_u64(seed, "licenses", index, "seats") % 496,
            "annual_cost_usd": 5_000
            + _counter_u64(seed, "licenses", index, "annual_cost") % 495_001,
            "usage_ratio_basis_points": _counter_u64(
                seed, "licenses", index, "usage_ratio"
            )
            % 10_001,
            "permitted_uses": ["portfolio_analysis", "mission_briefing"],
        }
    )
    return record


def _stream_event_record(
    profile: WorkloadProfile, seed: int, index: int
) -> dict[str, Any]:
    _, grant = _grant_reference(profile, seed, "stream_events", index)
    event_type = _choice(
        ("financial_update", "milestone_update", "document_added", "quality_signal"),
        seed,
        "stream_events",
        index,
        "event_type",
    )
    event_time = REFERENCE_INSTANT - timedelta(
        seconds=_counter_u64(seed, "stream_events", index, "event_time")
        % (180 * 24 * 60 * 60)
    )
    record = _common(seed)
    record.update(
        {
            "event_id": _record_id("event", seed, index),
            "grant_id": grant["grant_id"],
            "grant_no": grant["grant_no"],
            "event_type": event_type,
            "event_time": _iso_z(event_time),
            "sequence": index,
            "partition_key": grant["grant_id"],
            "payload": {
                "metric": _choice(
                    ("freshness_hours", "quality_score", "cost_variance_basis_points"),
                    seed,
                    "stream_events",
                    index,
                    "metric",
                ),
                "value": _counter_u64(seed, "stream_events", index, "value") % 10_001,
                "correlation_id": _record_id("correlation", seed, index // 4),
            },
        }
    )
    return record


def generate_record(
    profile: str | WorkloadProfile,
    dataset: str,
    index: int,
    *,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Generate one valid record from its stable counter coordinates."""

    resolved = get_profile(profile)
    dataset = _require_dataset(dataset)
    seed = _require_seed(seed)
    count = resolved.dataset_counts[dataset]
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("record index must be an integer")
    if index < 0 or index >= count:
        raise IndexError(f"record index must be between 0 and {count - 1}")
    if dataset == "grants":
        return _grant_record(seed, index)
    if dataset == "finance":
        return _finance_record(resolved, seed, index)
    if dataset == "milestones":
        return _milestone_record(resolved, seed, index)
    if dataset == "documents":
        return _document_record(resolved, seed, index)
    if dataset == "licenses":
        return _license_record(seed, index)
    return _stream_event_record(resolved, seed, index)


@dataclass(frozen=True)
class FieldSpec:
    types: tuple[type, ...]
    allowed: frozenset[Any] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    pattern: str | None = None
    format: str | None = None


def _field(
    *types: type,
    allowed: Iterable[Any] | None = None,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
    pattern: str | None = None,
    format: str | None = None,
) -> FieldSpec:
    return FieldSpec(
        types=types,
        allowed=frozenset(allowed) if allowed is not None else None,
        minimum=minimum,
        maximum=maximum,
        pattern=pattern,
        format=format,
    )


_COMMON_SCHEMA = {
    "schema_version": _field(str, allowed=(CONTRACT_VERSION,)),
    "synthetic": _field(bool, allowed=(True,)),
    "synthetic_seed": _field(int, minimum=0, maximum=9_999_999_999),
    "source_system": _field(str, allowed=("COMPASS-SYNTHETIC-SCALE",)),
}
_GRANT_ID_PATTERN = r"syn-grant-[0-9a-f]{8}-[0-9]{9}"
_GRANT_NO_PATTERN = r"SYN-[0-9]{4}-[A-Z0-9]{4}-[0-9]{7}"

SCHEMAS: dict[str, dict[str, FieldSpec]] = {
    "grants": {
        **_COMMON_SCHEMA,
        "grant_id": _field(str, pattern=_GRANT_ID_PATTERN),
        "grant_no": _field(str, pattern=_GRANT_NO_PATTERN),
        "title": _field(str),
        "program_area": _field(str, allowed=PROGRAM_AREAS),
        "org_unit": _field(str, allowed=ORG_UNITS),
        "performer": _field(str, allowed=PERFORMERS),
        "fiscal_year": _field(int, minimum=2019, maximum=2026),
        "start_date": _field(str, format="date"),
        "end_date": _field(str, format="date"),
        "award_amount_usd": _field(int, minimum=0),
        "status": _field(str, allowed=("active", "completed", "planned")),
        "classification": _field(str, allowed=("UNCLASSIFIED-SYNTHETIC",)),
    },
    "finance": {
        **_COMMON_SCHEMA,
        "transaction_id": _field(
            str, pattern=r"syn-finance-[0-9a-f]{8}-[0-9]{9}"
        ),
        "grant_id": _field(str, pattern=_GRANT_ID_PATTERN),
        "grant_no": _field(str, pattern=_GRANT_NO_PATTERN),
        "transaction_date": _field(str, format="date"),
        "fiscal_year": _field(int, minimum=2019, maximum=2027),
        "transaction_type": _field(
            str, allowed=("obligation", "expenditure", "commitment", "deobligation")
        ),
        "amount_usd": _field(int, minimum=-250_000, maximum=2_000_000),
        "currency": _field(str, allowed=("USD",)),
        "status": _field(str, allowed=("posted", "pending", "reconciled")),
        "appropriation": _field(str, allowed=("6.1", "6.2", "6.3", "6.4")),
    },
    "milestones": {
        **_COMMON_SCHEMA,
        "milestone_id": _field(
            str, pattern=r"syn-milestone-[0-9a-f]{8}-[0-9]{9}"
        ),
        "grant_id": _field(str, pattern=_GRANT_ID_PATTERN),
        "grant_no": _field(str, pattern=_GRANT_NO_PATTERN),
        "milestone_type": _field(
            str,
            allowed=("design_review", "prototype", "field_test", "transition_review"),
        ),
        "name": _field(str),
        "due_date": _field(str, format="date"),
        "status": _field(
            str, allowed=("complete", "at_risk", "in_progress", "not_started")
        ),
        "completion_percent": _field(int, minimum=0, maximum=100),
        "risk_level": _field(str, allowed=("low", "moderate", "high")),
    },
    "documents": {
        **_COMMON_SCHEMA,
        "document_id": _field(
            str, pattern=r"syn-document-[0-9a-f]{8}-[0-9]{9}"
        ),
        "grant_id": _field(str, pattern=_GRANT_ID_PATTERN),
        "grant_no": _field(str, pattern=_GRANT_NO_PATTERN),
        "document_type": _field(
            str,
            allowed=(
                "technical_report",
                "milestone_evidence",
                "financial_report",
                "data_management_plan",
            ),
        ),
        "title": _field(str),
        "mime_type": _field(
            str, allowed=("application/pdf", "application/json", "text/csv")
        ),
        "size_bytes": _field(int, minimum=1, maximum=25_000_000),
        "content_sha256": _field(str, pattern=r"[0-9a-f]{64}"),
        "created_at": _field(str, format="datetime"),
        "classification": _field(str, allowed=("UNCLASSIFIED-SYNTHETIC",)),
    },
    "licenses": {
        **_COMMON_SCHEMA,
        "license_id": _field(
            str, pattern=r"syn-license-[0-9a-f]{8}-[0-9]{9}"
        ),
        "data_product": _field(str),
        "vendor": _field(str),
        "owning_org": _field(str, allowed=ORG_UNITS),
        "start_date": _field(str, format="date"),
        "renewal_date": _field(str, format="date"),
        "status": _field(str, allowed=("active", "expired")),
        "seats": _field(int, minimum=1, maximum=500),
        "annual_cost_usd": _field(int, minimum=1, maximum=500_000),
        "usage_ratio_basis_points": _field(int, minimum=0, maximum=10_000),
        "permitted_uses": _field(list),
    },
    "stream_events": {
        **_COMMON_SCHEMA,
        "event_id": _field(str, pattern=r"syn-event-[0-9a-f]{8}-[0-9]{9}"),
        "grant_id": _field(str, pattern=_GRANT_ID_PATTERN),
        "grant_no": _field(str, pattern=_GRANT_NO_PATTERN),
        "event_type": _field(
            str,
            allowed=(
                "financial_update",
                "milestone_update",
                "document_added",
                "quality_signal",
            ),
        ),
        "event_time": _field(str, format="datetime"),
        "sequence": _field(int, minimum=0),
        "partition_key": _field(str, pattern=_GRANT_ID_PATTERN),
        "payload": _field(dict),
    },
}


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _valid_formatted_value(value: str, format_name: str) -> bool:
    try:
        if format_name == "date":
            date.fromisoformat(value)
        elif format_name == "datetime":
            if not value.endswith("Z"):
                return False
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return False
    except ValueError:
        return False
    return True


def _matches_types(value: Any, expected: tuple[type, ...]) -> bool:
    if isinstance(value, bool) and bool not in expected:
        return False
    return isinstance(value, expected)


def validate_record(dataset: str, record: Mapping[str, Any]) -> tuple[ValidationIssue, ...]:
    """Validate one record against the strict synthetic dataset contract."""

    dataset = _require_dataset(dataset)
    if not isinstance(record, Mapping):
        return (
            ValidationIssue("$", "invalid_record", "record must be a mapping"),
        )
    schema = SCHEMAS[dataset]
    issues: list[ValidationIssue] = []
    for field_name, spec in schema.items():
        if field_name not in record:
            issues.append(
                ValidationIssue(field_name, "required", "required field is missing")
            )
            continue
        value = record[field_name]
        if not _matches_types(value, spec.types):
            expected = ", ".join(item.__name__ for item in spec.types)
            issues.append(
                ValidationIssue(field_name, "type", f"value must be {expected}")
            )
            continue
        if spec.allowed is not None and value not in spec.allowed:
            issues.append(
                ValidationIssue(field_name, "enum", "value is outside the allowed set")
            )
        if spec.minimum is not None and value < spec.minimum:
            issues.append(
                ValidationIssue(field_name, "minimum", "value is below the minimum")
            )
        if spec.maximum is not None and value > spec.maximum:
            issues.append(
                ValidationIssue(field_name, "maximum", "value is above the maximum")
            )
        if spec.pattern is not None and re.fullmatch(spec.pattern, value) is None:
            issues.append(
                ValidationIssue(field_name, "pattern", "value has an invalid format")
            )
        if spec.format is not None and not _valid_formatted_value(value, spec.format):
            issues.append(
                ValidationIssue(field_name, "format", f"value is not a valid {spec.format}")
            )
    for field_name in record.keys() - schema.keys():
        issues.append(
            ValidationIssue(str(field_name), "unexpected", "field is not in the schema")
        )

    if dataset == "grants" and not any(
        item.field in {"start_date", "end_date"} for item in issues
    ):
        if date.fromisoformat(record["end_date"]) < date.fromisoformat(record["start_date"]):
            issues.append(
                ValidationIssue("end_date", "range", "end_date precedes start_date")
            )
    if dataset == "licenses" and not any(
        item.field in {"start_date", "renewal_date"} for item in issues
    ):
        if date.fromisoformat(record["renewal_date"]) <= date.fromisoformat(
            record["start_date"]
        ):
            issues.append(
                ValidationIssue(
                    "renewal_date", "range", "renewal_date must follow start_date"
                )
            )
    if dataset == "stream_events" and not any(
        item.field == "payload" for item in issues
    ):
        payload = record["payload"]
        required_payload = {"metric", "value", "correlation_id"}
        if not required_payload.issubset(payload):
            issues.append(
                ValidationIssue("payload", "required", "payload fields are missing")
            )
        elif (
            not isinstance(payload["metric"], str)
            or isinstance(payload["value"], bool)
            or not isinstance(payload["value"], int)
            or not isinstance(payload["correlation_id"], str)
        ):
            issues.append(
                ValidationIssue("payload", "type", "payload values have invalid types")
            )
    return tuple(issues)


DEFECT_KINDS = (
    "missing_required",
    "invalid_type",
    "invalid_enum",
    "invalid_format",
    "out_of_range",
)


@dataclass(frozen=True)
class DefectPolicy:
    """A deterministic bounded error rate expressed in basis points."""

    rate_basis_points: int = 0
    kinds: tuple[str, ...] = DEFECT_KINDS

    def __post_init__(self) -> None:
        if (
            isinstance(self.rate_basis_points, bool)
            or not isinstance(self.rate_basis_points, int)
            or not 0 <= self.rate_basis_points <= 10_000
        ):
            raise ValueError("defect rate must be an integer from 0 to 10000")
        if not self.kinds or any(kind not in DEFECT_KINDS for kind in self.kinds):
            raise ValueError("defect kinds must be a non-empty supported subset")


_PRIMARY_ID_FIELD = {
    "grants": "grant_id",
    "finance": "transaction_id",
    "milestones": "milestone_id",
    "documents": "document_id",
    "licenses": "license_id",
    "stream_events": "event_id",
}
_NUMERIC_FIELD = {
    "grants": "award_amount_usd",
    "finance": "fiscal_year",
    "milestones": "completion_percent",
    "documents": "size_bytes",
    "licenses": "seats",
    "stream_events": "sequence",
}
_ENUM_FIELD = {
    "grants": "status",
    "finance": "status",
    "milestones": "risk_level",
    "documents": "document_type",
    "licenses": "status",
    "stream_events": "event_type",
}
_OUT_OF_RANGE_VALUE = {
    "grants": -1,
    "finance": 1900,
    "milestones": 101,
    "documents": 0,
    "licenses": 0,
    "stream_events": -1,
}


def inject_defect(
    dataset: str,
    record: Mapping[str, Any],
    *,
    seed: int,
    index: int,
    policy: DefectPolicy,
) -> tuple[dict[str, Any], str | None]:
    """Return a copy with at most one reproducible schema defect."""

    dataset = _require_dataset(dataset)
    seed = _require_seed(seed)
    copied = dict(record)
    selected = _counter_u64(seed, dataset, index, "defect_selected") % 10_000
    if selected >= policy.rate_basis_points:
        return copied, None
    kind = policy.kinds[
        _counter_u64(seed, dataset, index, "defect_kind") % len(policy.kinds)
    ]
    primary_id = _PRIMARY_ID_FIELD[dataset]
    numeric_field = _NUMERIC_FIELD[dataset]
    enum_field = _ENUM_FIELD[dataset]
    if kind == "missing_required":
        copied.pop(primary_id, None)
    elif kind == "invalid_type":
        copied[numeric_field] = "not-an-integer"
    elif kind == "invalid_enum":
        copied[enum_field] = "invalid-synthetic-enum"
    elif kind == "invalid_format":
        copied[primary_id] = "invalid-synthetic-id"
    else:
        copied[numeric_field] = _OUT_OF_RANGE_VALUE[dataset]
    return copied, kind


@dataclass(frozen=True)
class RecordResult:
    dataset: str
    index: int
    record: dict[str, Any]
    injected_defect: str | None
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def _resolve_range(
    count: int, start: int, stop: int | None
) -> tuple[int, int]:
    if isinstance(start, bool) or not isinstance(start, int):
        raise TypeError("start must be an integer")
    if stop is not None and (isinstance(stop, bool) or not isinstance(stop, int)):
        raise TypeError("stop must be an integer")
    resolved_stop = count if stop is None else stop
    if start < 0 or resolved_stop < start or resolved_stop > count:
        raise ValueError(f"range must satisfy 0 <= start <= stop <= {count}")
    return start, resolved_stop


def iter_record_results(
    profile: str | WorkloadProfile,
    dataset: str,
    *,
    seed: int = DEFAULT_SEED,
    start: int = 0,
    stop: int | None = None,
    defect_policy: DefectPolicy | None = None,
) -> Iterator[RecordResult]:
    """Stream records, injected defect metadata, and validation outcomes."""

    resolved = get_profile(profile)
    dataset = _require_dataset(dataset)
    seed = _require_seed(seed)
    start, stop = _resolve_range(resolved.dataset_counts[dataset], start, stop)
    policy = defect_policy or DefectPolicy()
    for index in range(start, stop):
        valid_record = generate_record(resolved, dataset, index, seed=seed)
        record, defect = inject_defect(
            dataset,
            valid_record,
            seed=seed,
            index=index,
            policy=policy,
        )
        yield RecordResult(
            dataset=dataset,
            index=index,
            record=record,
            injected_defect=defect,
            issues=validate_record(dataset, record),
        )


def iter_records(
    profile: str | WorkloadProfile,
    dataset: str,
    *,
    seed: int = DEFAULT_SEED,
    start: int = 0,
    stop: int | None = None,
    defect_policy: DefectPolicy | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream record mappings without retaining a dataset in memory."""

    for result in iter_record_results(
        profile,
        dataset,
        seed=seed,
        start=start,
        stop=stop,
        defect_policy=defect_policy,
    ):
        yield result.record


@dataclass(frozen=True)
class PartitionSpec:
    profile: str
    dataset: str
    ordinal: int
    partition_id: str
    start: int
    stop: int

    @property
    def record_count(self) -> int:
        return self.stop - self.start


def iter_partition_specs(
    profile: str | WorkloadProfile,
    dataset: str,
    *,
    partition_size: int | None = None,
) -> Iterator[PartitionSpec]:
    """Yield stable half-open ranges for parallel or local generation."""

    resolved = get_profile(profile)
    dataset = _require_dataset(dataset)
    size = resolved.default_partition_size if partition_size is None else partition_size
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("partition_size must be a positive integer")
    count = resolved.dataset_counts[dataset]
    for ordinal, start in enumerate(range(0, count, size)):
        yield PartitionSpec(
            profile=resolved.name,
            dataset=dataset,
            ordinal=ordinal,
            partition_id=f"part-{ordinal:05d}",
            start=start,
            stop=min(start + size, count),
        )


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON with stable key order, spacing, Unicode, and number rules."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_line(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def deterministic_gzip_bytes(value: bytes, *, compresslevel: int = 9) -> bytes:
    """Compress bytes with a fixed timestamp and no source filename."""

    output = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        compresslevel=compresslevel,
        fileobj=output,
        mtime=0,
    ) as compressed:
        compressed.write(value)
    return output.getvalue()


def deterministic_gunzip_bytes(value: bytes) -> bytes:
    return gzip.decompress(value)


@dataclass(frozen=True)
class GzipObjectReceipt:
    record_count: int
    uncompressed_bytes: int
    compressed_bytes: int
    content_sha256: str
    object_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _DigestingWriter:
    def __init__(self, destination: BinaryIO):
        self.destination = destination
        self.hasher = hashlib.sha256()
        self.byte_count = 0

    def write(self, value: bytes) -> int:
        self.hasher.update(value)
        self.byte_count += len(value)
        return self.destination.write(value)

    def flush(self) -> None:
        self.destination.flush()


class DeterministicGzipJsonlWriter:
    """Stream canonical JSON Lines into deterministic gzip bytes."""

    def __init__(self, destination: BinaryIO, *, compresslevel: int = 9):
        self._sink = _DigestingWriter(destination)
        self._content_hasher = hashlib.sha256()
        self._uncompressed_bytes = 0
        self._record_count = 0
        self._closed = False
        self._gzip = gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=compresslevel,
            fileobj=self._sink,
            mtime=0,
        )

    def write(self, record: Mapping[str, Any]) -> None:
        if self._closed:
            raise ValueError("writer is closed")
        line = canonical_json_line(record)
        self._content_hasher.update(line)
        self._uncompressed_bytes += len(line)
        self._record_count += 1
        self._gzip.write(line)

    def close(self) -> GzipObjectReceipt:
        if not self._closed:
            self._gzip.close()
            self._sink.flush()
            self._closed = True
        return self.receipt

    @property
    def receipt(self) -> GzipObjectReceipt:
        if not self._closed:
            raise RuntimeError("receipt is available only after close")
        return GzipObjectReceipt(
            record_count=self._record_count,
            uncompressed_bytes=self._uncompressed_bytes,
            compressed_bytes=self._sink.byte_count,
            content_sha256=self._content_hasher.hexdigest(),
            object_sha256=self._sink.hasher.hexdigest(),
        )

    def __enter__(self) -> DeterministicGzipJsonlWriter:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


_NUMERIC_AGGREGATES = {
    "grants": ("award_amount_usd",),
    "finance": ("amount_usd",),
    "milestones": ("completion_percent",),
    "documents": ("size_bytes",),
    "licenses": ("annual_cost_usd", "seats"),
    "stream_events": ("sequence",),
}
_DIMENSION_AGGREGATES = {
    "grants": ("status", "program_area", "org_unit"),
    "finance": ("status", "transaction_type", "appropriation"),
    "milestones": ("status", "risk_level", "milestone_type"),
    "documents": ("document_type", "mime_type"),
    "licenses": ("status", "owning_org"),
    "stream_events": ("event_type",),
}
_TIME_AGGREGATE = {
    "grants": "start_date",
    "finance": "transaction_date",
    "milestones": "due_date",
    "documents": "created_at",
    "licenses": "renewal_date",
    "stream_events": "event_time",
}


class PartitionReceiptBuilder:
    """Incrementally build aggregate and quality evidence for one partition."""

    def __init__(
        self,
        spec: PartitionSpec,
        *,
        seed: int,
        defect_policy: DefectPolicy | None = None,
    ):
        self.spec = spec
        self.seed = _require_seed(seed)
        self.defect_policy = defect_policy or DefectPolicy()
        self.generated = 0
        self.valid = 0
        self.injected = 0
        self.detected_injected = 0
        self.issue_counts: Counter[str] = Counter()
        self.defect_counts: Counter[str] = Counter()
        self.numeric_sums: Counter[str] = Counter()
        self.dimensions: dict[str, Counter[str]] = defaultdict(Counter)
        self.minimum_time: str | None = None
        self.maximum_time: str | None = None
        self.content_hasher = hashlib.sha256()
        self.canonical_bytes = 0
        self._next_index = spec.start

    def observe(self, result: RecordResult) -> None:
        if result.dataset != self.spec.dataset:
            raise ValueError("record result dataset does not match partition")
        if result.index != self._next_index or result.index >= self.spec.stop:
            raise ValueError("record results must arrive once in partition index order")
        self._next_index += 1
        self.generated += 1
        line = canonical_json_line(result.record)
        self.content_hasher.update(line)
        self.canonical_bytes += len(line)
        if result.valid:
            self.valid += 1
        for issue in result.issues:
            self.issue_counts[issue.code] += 1
        if result.injected_defect is not None:
            self.injected += 1
            self.defect_counts[result.injected_defect] += 1
            if result.issues:
                self.detected_injected += 1

        for field_name in _NUMERIC_AGGREGATES[self.spec.dataset]:
            value = result.record.get(field_name)
            if isinstance(value, int) and not isinstance(value, bool):
                self.numeric_sums[field_name] += value
        for field_name in _DIMENSION_AGGREGATES[self.spec.dataset]:
            value = result.record.get(field_name)
            if isinstance(value, str):
                self.dimensions[field_name][value] += 1
        time_value = result.record.get(_TIME_AGGREGATE[self.spec.dataset])
        if isinstance(time_value, str):
            if self.minimum_time is None or time_value < self.minimum_time:
                self.minimum_time = time_value
            if self.maximum_time is None or time_value > self.maximum_time:
                self.maximum_time = time_value

    def finish(self) -> dict[str, Any]:
        if self.generated != self.spec.record_count:
            raise ValueError(
                f"partition expected {self.spec.record_count} records, observed {self.generated}"
            )
        invalid = self.generated - self.valid
        unexpected_invalid = max(invalid - self.detected_injected, 0)
        undetected_injected = self.injected - self.detected_injected
        score = self.valid * 10_000 // self.generated if self.generated else 10_000
        return {
            "contract_version": CONTRACT_VERSION,
            "profile": self.spec.profile,
            "dataset": self.spec.dataset,
            "partition_id": self.spec.partition_id,
            "partition_ordinal": self.spec.ordinal,
            "range": {"start": self.spec.start, "stop": self.spec.stop},
            "seed": self.seed,
            "aggregate": {
                "record_count": self.generated,
                "numeric_sums": dict(sorted(self.numeric_sums.items())),
                "dimensions": {
                    field_name: dict(sorted(counts.items()))
                    for field_name, counts in sorted(self.dimensions.items())
                },
                "time_range": {
                    "field": _TIME_AGGREGATE[self.spec.dataset],
                    "minimum": self.minimum_time,
                    "maximum": self.maximum_time,
                },
            },
            "quality": {
                "generated_records": self.generated,
                "valid_records": self.valid,
                "invalid_records": invalid,
                "quality_score_basis_points": score,
                "injected_defects": self.injected,
                "detected_injected_defects": self.detected_injected,
                "undetected_injected_defects": undetected_injected,
                "unexpected_invalid_records": unexpected_invalid,
                "defects_by_kind": dict(sorted(self.defect_counts.items())),
                "issues_by_code": dict(sorted(self.issue_counts.items())),
                "status": (
                    "pass"
                    if invalid == 0
                    else "expected_defects_detected"
                    if unexpected_invalid == 0 and undetected_injected == 0
                    else "fail"
                ),
            },
            "content": {
                "canonical_bytes": self.canonical_bytes,
                "content_sha256": self.content_hasher.hexdigest(),
            },
        }


def build_partition_receipt(
    spec: PartitionSpec,
    *,
    seed: int = DEFAULT_SEED,
    defect_policy: DefectPolicy | None = None,
) -> dict[str, Any]:
    """Generate one partition and return its aggregate and quality receipt."""

    policy = defect_policy or DefectPolicy()
    builder = PartitionReceiptBuilder(spec, seed=seed, defect_policy=policy)
    for result in iter_record_results(
        spec.profile,
        spec.dataset,
        seed=seed,
        start=spec.start,
        stop=spec.stop,
        defect_policy=policy,
    ):
        builder.observe(result)
    return builder.finish()

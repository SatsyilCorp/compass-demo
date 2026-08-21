"""Build a leakage-safe funding dataset from the approved USAspending snapshot."""

from __future__ import annotations

import json
import math
import os
import statistics
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import (
    DATASET_CONTRACT,
    ROW_CONTRACT,
    SHA256_RE,
    TrainingRefusal,
    digest_json,
)


APPROVED_SOURCE = "USAspending spending_over_time"
DEFAULT_SOURCE_URI = (
    "artifact://private/public-intelligence/usaspending-quarterly-obligations.json"
)
NUMERIC_FEATURES = (
    "time_index",
    "lag_1_obligations_usd",
    "lag_4_obligations_usd",
    "rolling_4_mean_obligations_usd",
    "rolling_4_std_obligations_usd",
)
CATEGORICAL_FEATURES = ("quarter",)


def _refuse(code: str, message: str) -> None:
    raise TrainingRefusal(code, message)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _quarter_bounds(fiscal_year: int, quarter: int) -> tuple[datetime, datetime]:
    if quarter == 1:
        start = datetime(fiscal_year - 1, 10, 1, tzinfo=timezone.utc)
    elif quarter == 2:
        start = datetime(fiscal_year, 1, 1, tzinfo=timezone.utc)
    elif quarter == 3:
        start = datetime(fiscal_year, 4, 1, tzinfo=timezone.utc)
    elif quarter == 4:
        start = datetime(fiscal_year, 7, 1, tzinfo=timezone.utc)
    else:
        _refuse("invalid_source", "quarter must be an integer from 1 through 4")
    if quarter == 4:
        next_start = datetime(fiscal_year, 10, 1, tzinfo=timezone.utc)
    else:
        next_quarter = quarter + 1
        if next_quarter == 2:
            next_start = datetime(fiscal_year, 1, 1, tzinfo=timezone.utc)
        elif next_quarter == 3:
            next_start = datetime(fiscal_year, 4, 1, tzinfo=timezone.utc)
        else:
            next_start = datetime(fiscal_year, 7, 1, tzinfo=timezone.utc)
    return start, next_start - timedelta(seconds=1)


def _as_of_date(value: Any) -> date:
    if not isinstance(value, str):
        _refuse("invalid_source", "as_of_date must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise TrainingRefusal(
            "invalid_source", "as_of_date must use YYYY-MM-DD"
        ) from exc


def _source_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if payload.get("source") != APPROVED_SOURCE:
        _refuse(
            "unapproved_source",
            f"source must be the approved {APPROVED_SOURCE!r} aggregate",
        )
    scope = payload.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        _refuse("invalid_source", "scope must be a non-empty string")
    values = payload.get("values")
    if not isinstance(values, list) or not values:
        _refuse("invalid_source", "values must be a non-empty array")
    rows: list[dict[str, Any]] = []
    seen_periods: set[tuple[int, int]] = set()
    for index, raw in enumerate(values):
        if not isinstance(raw, Mapping):
            _refuse("invalid_source", f"values[{index}] must be an object")
        fiscal_year = raw.get("fiscal_year")
        quarter = raw.get("quarter")
        amount = raw.get("observed_obligations_usd")
        if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int):
            _refuse("invalid_source", f"values[{index}].fiscal_year is invalid")
        if isinstance(quarter, bool) or not isinstance(quarter, int):
            _refuse("invalid_source", f"values[{index}].quarter is invalid")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(float(amount))
            or float(amount) < 0
        ):
            _refuse(
                "invalid_source",
                f"values[{index}].observed_obligations_usd must be finite and non-negative",
            )
        period = f"FY{fiscal_year} Q{quarter}"
        if raw.get("period") != period:
            _refuse(
                "invalid_source",
                f"values[{index}].period must match fiscal_year and quarter",
            )
        key = (fiscal_year, quarter)
        if key in seen_periods:
            _refuse("duplicate_source_period", f"duplicate source period {period}")
        seen_periods.add(key)
        start, end = _quarter_bounds(fiscal_year, quarter)
        rows.append(
            {
                "fiscal_year": fiscal_year,
                "quarter": quarter,
                "period": period,
                "observed_obligations_usd": float(amount),
                "start": start,
                "end": end,
                "source_value": {
                    "fiscal_year": fiscal_year,
                    "quarter": quarter,
                    "period": period,
                    "observed_obligations_usd": float(amount),
                },
            }
        )
    rows.sort(key=lambda row: row["start"])
    for earlier, later in zip(rows, rows[1:]):
        if earlier["end"] + timedelta(seconds=1) != later["start"]:
            _refuse(
                "source_period_gap",
                f"source periods are not consecutive after {earlier['period']}",
            )
    return rows


def _source_record_id(row: Mapping[str, Any], artifact_sha256: str) -> str:
    digest = digest_json(
        {
            "artifact_sha256": artifact_sha256,
            "source_value": row["source_value"],
        }
    )
    return f"usaspending-{row['period'].lower().replace(' ', '-')}-{digest[:16]}"


def _source_record_sha256(row: Mapping[str, Any], artifact_sha256: str) -> str:
    return digest_json(
        {
            "artifact_sha256": artifact_sha256,
            "source_record": row["source_value"],
        }
    )


def _lineage(
    feature: str,
    source_record_ids: Sequence[str],
    max_available_at: datetime,
    *,
    evidence_class: str,
) -> dict[str, Any]:
    return {
        "feature": feature,
        "source_record_ids": list(source_record_ids),
        "max_available_at": _iso(max_available_at),
        "evidence_class": evidence_class,
    }


def build_funding_records(
    payload: Mapping[str, Any],
    *,
    artifact_sha256: str,
    source_uri: str = DEFAULT_SOURCE_URI,
    test_fixture: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convert one reviewed source snapshot into canonical funding records.

    ``test_fixture`` exists only so offline unit tests can remain clearly marked.
    The public CLI does not expose it.
    """

    if not SHA256_RE.fullmatch(artifact_sha256.lower()):
        _refuse("invalid_provenance", "source artifact SHA-256 is invalid")
    if not isinstance(source_uri, str) or not source_uri.strip():
        _refuse("invalid_provenance", "source_uri must be a non-empty string")
    as_of = _as_of_date(payload.get("as_of_date"))
    all_rows = _source_rows(payload)
    complete_rows = [row for row in all_rows if row["end"].date() <= as_of]
    incomplete_rows = [row for row in all_rows if row["end"].date() > as_of]
    if len(complete_rows) < 64:
        _refuse(
            "insufficient_complete_periods",
            "funding builder requires at least 64 complete consecutive quarters",
        )
    record_ids = {
        row["period"]: _source_record_id(row, artifact_sha256) for row in complete_rows
    }
    snapshot_id = f"usaspending-quarterly-{artifact_sha256[:16]}"
    evidence_kind = "synthetic_test_fixture" if test_fixture else "public"
    rights = "synthetic_test_fixture" if test_fixture else "public"
    as_of_time = datetime.combine(as_of, time(23, 59, 59), tzinfo=timezone.utc)
    manifest: dict[str, Any] = {
        "record_type": "manifest",
        "contract": DATASET_CONTRACT,
        "model_kind": "funding_forecast",
        "dataset_id": "usaspending-quarterly-obligations-funding-forecast",
        "dataset_version": f"{as_of.isoformat()}-{artifact_sha256[:16]}",
        "created_at": _iso(as_of_time),
        "as_of_time": _iso(as_of_time),
        "evidence_set": {
            "kind": evidence_kind,
            "snapshot_id": snapshot_id,
            "as_of_at": _iso(as_of_time),
            "manifest_sha256": artifact_sha256.lower(),
        },
        "target": {
            "name": "funding_amount",
            "definition": (
                "Observed USAspending quarterly obligations in USD for the source "
                "scope, measured after the forecast quarter closes."
            ),
            "authenticity_required": True,
        },
        "feature_schema": {
            "numeric": list(NUMERIC_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
        },
        "leakage_prohibited_features": [
            "observed_obligations_usd",
            "current_quarter_obligations_usd",
        ],
        "subgroup_fields": [],
        "minimum_subgroup_size": 10,
        "prediction_interval_coverage": 0.90,
        "test_fixture": test_fixture,
        "source_snapshot": {
            "source": payload["source"],
            "scope": payload["scope"],
            "source_uri": source_uri,
            "artifact_sha256": artifact_sha256.lower(),
            "periods_received": len(all_rows),
            "complete_periods": len(complete_rows),
            "incomplete_periods_excluded": [row["period"] for row in incomplete_rows],
        },
        "feature_engineering": {
            "forecast_time": "start of each federal fiscal quarter",
            "lag_policy": "only completed earlier quarters",
            "rolling_window": "four completed earlier quarters",
            "rolling_std_definition": "population standard deviation",
            "warmup_periods_excluded": 4,
        },
    }
    if test_fixture:
        manifest["test_fixture_note"] = (
            "Synthetic source values used only to verify the builder offline."
        )

    training_rows: list[dict[str, Any]] = []
    for index, current in enumerate(complete_rows):
        if index < 4:
            continue
        previous = complete_rows[index - 1]
        prior_year = complete_rows[index - 4]
        rolling = complete_rows[index - 4 : index]
        rolling_amounts = [float(row["observed_obligations_usd"]) for row in rolling]
        calendar_available_at = current["start"] - timedelta(seconds=1)
        prior_available_at = previous["end"]
        current_source_id = record_ids[current["period"]]
        rolling_ids = [record_ids[row["period"]] for row in rolling]
        features = {
            "time_index": index,
            "lag_1_obligations_usd": previous["observed_obligations_usd"],
            "lag_4_obligations_usd": prior_year["observed_obligations_usd"],
            "rolling_4_mean_obligations_usd": statistics.fmean(rolling_amounts),
            "rolling_4_std_obligations_usd": statistics.pstdev(rolling_amounts),
            "quarter": f"Q{current['quarter']}",
        }
        source_fragment = f"{source_uri}#period={current['period'].replace(' ', '%20')}"
        training_rows.append(
            {
                "record_type": "training_row",
                "contract": ROW_CONTRACT,
                "record_id": f"funding-forecast-{current_source_id}",
                "event_time": _iso(current["start"]),
                "group_id": None,
                "features": features,
                "feature_lineage": [
                    _lineage(
                        "time_index",
                        [f"federal-fiscal-calendar-{current['period']}"],
                        calendar_available_at,
                        evidence_class="public_calendar",
                    ),
                    _lineage(
                        "lag_1_obligations_usd",
                        [record_ids[previous["period"]]],
                        previous["end"],
                        evidence_class="public_aggregate",
                    ),
                    _lineage(
                        "lag_4_obligations_usd",
                        [record_ids[prior_year["period"]]],
                        prior_year["end"],
                        evidence_class="public_aggregate",
                    ),
                    _lineage(
                        "rolling_4_mean_obligations_usd",
                        rolling_ids,
                        prior_available_at,
                        evidence_class="public_aggregate",
                    ),
                    _lineage(
                        "rolling_4_std_obligations_usd",
                        rolling_ids,
                        prior_available_at,
                        evidence_class="public_aggregate",
                    ),
                    _lineage(
                        "quarter",
                        [f"federal-fiscal-calendar-{current['period']}"],
                        calendar_available_at,
                        evidence_class="public_calendar",
                    ),
                ],
                "label": {
                    "name": "funding_amount",
                    "status": "observed",
                    "value": current["observed_obligations_usd"],
                    "authentic": True,
                    "source_uri": source_fragment,
                    "observed_at": _iso(current["end"]),
                },
                "subgroups": {},
                "provenance": {
                    "evidence_set_id": snapshot_id,
                    "source_uri": source_fragment,
                    "source_sha256": _source_record_sha256(current, artifact_sha256),
                    "source_artifact_sha256": artifact_sha256.lower(),
                    "source_record_id": current_source_id,
                    "authorized_for_training": True,
                    "rights": rights,
                    "pii_minimized": True,
                    "protected_features_excluded": True,
                    "test_fixture": test_fixture,
                },
            }
        )
    summary = {
        "source_artifact_sha256": artifact_sha256.lower(),
        "periods_received": len(all_rows),
        "complete_periods": len(complete_rows),
        "incomplete_periods_excluded": [row["period"] for row in incomplete_rows],
        "warmup_periods_excluded": 4,
        "training_rows": len(training_rows),
        "first_training_period": training_rows[0]["record_id"],
        "last_training_period": training_rows[-1]["record_id"],
    }
    return [manifest, *training_rows], summary


def build_funding_jsonl(
    source_path: str | Path,
    output_path: str | Path,
    *,
    source_uri: str = DEFAULT_SOURCE_URI,
) -> dict[str, Any]:
    """Read the approved artifact and create a new canonical JSONL file."""

    source = Path(source_path)
    output = Path(output_path)
    if output.exists():
        _refuse("output_exists", f"refusing to overwrite existing output {output}")
    try:
        source_bytes = source.read_bytes()
    except OSError as exc:
        raise TrainingRefusal(
            "source_unreadable", f"cannot read source artifact {source}"
        ) from exc
    import hashlib

    artifact_sha256 = hashlib.sha256(source_bytes).hexdigest()
    try:
        payload = json.loads(source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainingRefusal(
            "invalid_source", "source artifact is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        _refuse("invalid_source", "source artifact must contain a JSON object")
    records, summary = build_funding_records(
        payload,
        artifact_sha256=artifact_sha256,
        source_uri=source_uri,
        test_fixture=False,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_name, output)
    except FileExistsError as exc:
        raise TrainingRefusal(
            "output_exists", f"refusing to overwrite existing output {output}"
        ) from exc
    except OSError as exc:
        raise TrainingRefusal(
            "output_unwritable", f"cannot create canonical JSONL at {output}"
        ) from exc
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass
    return {"output": str(output.resolve()), **summary}

"""SageMaker inference contract for the public SBIR transition candidate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib


NUMERIC_FIELDS = (
    "phase_i_amount_usd",
    "title_character_count",
    "abstract_character_count",
    "abstract_token_count",
    "award_year",
)
CATEGORICAL_FIELDS = ("topic_family",)
TEXT_FIELD = "public_text"


def model_fn(model_dir: str):
    return joblib.load(Path(model_dir) / "model.joblib")


def input_fn(request_body: str | bytes, content_type: str) -> list[dict[str, Any]]:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise ValueError("content type must be application/json")
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    parsed = json.loads(request_body)
    if isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
        records = parsed["records"]
    elif isinstance(parsed, dict):
        records = [parsed]
    elif isinstance(parsed, list):
        records = parsed
    else:
        raise ValueError("input must be a record, a record list, or an object with records")
    if not records or any(not isinstance(record, dict) for record in records):
        raise ValueError("records must be a non-empty list of objects")
    for record in records:
        missing = [field for field in (*NUMERIC_FIELDS, *CATEGORICAL_FIELDS, TEXT_FIELD) if field not in record]
        if missing:
            raise ValueError("record is missing required fields: " + ", ".join(missing))
    return records


def _matrix(records: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [record[field] for field in NUMERIC_FIELDS]
        + [record[field] for field in CATEGORICAL_FIELDS]
        + [str(record[TEXT_FIELD])]
        for record in records
    ]


def predict_fn(records: list[dict[str, Any]], model) -> list[dict[str, Any]]:
    matrix = _matrix(records)
    probabilities = model.predict_proba(matrix)[:, 1]
    predictions = model.predict(matrix)
    return [
        {
            "observed_public_transition_probability": round(float(probability), 8),
            "candidate_label": int(prediction),
            "semantics": "public SBIR transition signal, not ONR mission success",
            "human_review_required": True,
        }
        for prediction, probability in zip(predictions, probabilities)
    ]


def output_fn(prediction: list[dict[str, Any]], accept: str) -> tuple[str, str]:
    media_type = accept.split(";", 1)[0].strip().lower()
    if media_type not in {"application/json", "*/*"}:
        raise ValueError("accept must allow application/json")
    return json.dumps({"predictions": prediction}, sort_keys=True), "application/json"

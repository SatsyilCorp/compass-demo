"""SageMaker-compatible inference functions for the Compass classifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib


REVIEW_THRESHOLD = 0.62


def model_fn(model_dir: str):
    return joblib.load(Path(model_dir) / "model.joblib")


def input_fn(request_body: str | bytes, content_type: str) -> list[str]:
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "text/plain":
        values = [request_body.strip()]
    elif media_type == "application/json":
        parsed = json.loads(request_body)
        if isinstance(parsed, str):
            values = [parsed]
        elif isinstance(parsed, list):
            values = [str(value) for value in parsed]
        elif isinstance(parsed, dict) and isinstance(parsed.get("documents"), list):
            values = [str(value) for value in parsed["documents"]]
        elif isinstance(parsed, dict) and parsed.get("text") is not None:
            values = [str(parsed["text"])]
        else:
            raise ValueError("JSON input must contain text or documents")
    else:
        raise ValueError(f"unsupported inference content type {content_type}")
    if not values or any(len(value.strip()) < 1 for value in values):
        raise ValueError("inference input must contain non-empty text")
    return values


def predict_fn(documents: list[str], model) -> list[dict[str, Any]]:
    labels = model.predict(documents)
    probabilities = model.predict_proba(documents)
    classes = [str(label) for label in model.classes_]
    results = []
    for label, row in zip(labels, probabilities):
        scores = {
            class_name: round(float(probability), 6)
            for class_name, probability in zip(classes, row)
        }
        confidence = max(scores.values())
        results.append(
            {
                "label": str(label),
                "confidence": confidence,
                "review_required": confidence < REVIEW_THRESHOLD,
                "probabilities": scores,
            }
        )
    return results


def output_fn(prediction: list[dict[str, Any]], accept: str) -> tuple[str, str]:
    media_type = accept.split(";", 1)[0].strip().lower()
    if media_type not in {"application/json", "*/*"}:
        raise ValueError(f"unsupported response content type {accept}")
    return json.dumps({"predictions": prediction}, sort_keys=True), "application/json"

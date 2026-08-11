#!/usr/bin/env python3
"""Run the exact document and classical ML contracts without AWS services."""

from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FUNCTION_DIR = ROOT / "src" / "functions" / "document_ml"
if str(FUNCTION_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTION_DIR))

import engine  # noqa: E402


def run(paths: list[Path], *, drift_threshold: float = 0.25) -> dict:
    model, metrics = engine.train_and_evaluate(engine.default_training_samples())
    documents = []
    runs = []
    for path in paths:
        payload = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            extracted = engine.extract_document(path.name, content_type, payload)
            quality = engine.quality_receipt(extracted)
            classification = (
                engine.predict(model, extracted["extracted_text"])
                if quality["gate"] == "pass"
                else None
            )
            documents.append(extracted["extracted_text"])
            runs.append(
                {
                    "filename": path.name,
                    "sha256": extracted["sha256"],
                    "schema": extracted["schema"],
                    "quality": quality,
                    "classification": classification,
                }
            )
        except (UnicodeDecodeError, ValueError) as exc:
            runs.append(
                {
                    "filename": path.name,
                    "quality": {
                        "gate": "quarantine",
                        "blocking_failures": ["inspect"],
                    },
                    "classification": None,
                    "reason": str(exc),
                }
            )
    drift = (
        engine.drift_receipt(model, documents, threshold=drift_threshold)
        if documents
        else None
    )
    return {
        "adapter": "deterministic-local-demo",
        "sagemaker_job_claimed": False,
        "model_version": model["model_version"],
        "taxonomy": model["taxonomy"],
        "metrics": metrics,
        "document_runs": runs,
        "drift": drift,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--drift-threshold", type=float, default=0.25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    missing = [path for path in args.paths if not path.is_file()]
    if missing:
        parser.error("missing input file: " + ", ".join(str(path) for path in missing))
    receipt = run(args.paths, drift_threshold=args.drift_threshold)
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

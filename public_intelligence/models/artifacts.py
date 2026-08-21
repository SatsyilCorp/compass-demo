"""Digest-bound model artifact and model-card serialization."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import joblib

from .common import TrainingOutput
from .contracts import TrainingRefusal, stable_json


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(stable_json(value) + "\n", encoding="utf-8")


def save_training_output(
    output: TrainingOutput, output_dir: str | Path
) -> dict[str, Any]:
    target = Path(output_dir)
    if target.exists() and any(target.iterdir()):
        raise TrainingRefusal(
            "artifact_path_not_empty",
            f"refusing to overwrite existing artifacts in {target}",
        )
    target.mkdir(parents=True, exist_ok=True)
    model_path = target / "model.joblib"
    card_path = target / "model-card.json"
    receipt_path = target / "training-receipt.json"
    manifest_path = target / "artifact-manifest.json"

    temporary_model = target / ".model.joblib.tmp"
    joblib.dump(output.estimator, temporary_model, compress=3)
    os.replace(temporary_model, model_path)
    model_digest = _sha256(model_path)

    card = dict(output.model_card)
    card["artifact"] = {
        "file": model_path.name,
        "sha256": model_digest,
        "format": "joblib",
        "deployment_state": "candidate_only",
    }
    _write_json(card_path, card)
    card_digest = _sha256(card_path)

    receipt = dict(output.receipt)
    receipt["artifact_sha256"] = model_digest
    receipt["model_card_sha256"] = card_digest
    receipt["deployment_state"] = "not_deployed"
    _write_json(receipt_path, receipt)
    receipt_digest = _sha256(receipt_path)

    manifest = {
        "contract": "compass.public-intelligence.artifact-manifest.v1",
        "model_id": card["model_id"],
        "files": {
            model_path.name: model_digest,
            card_path.name: card_digest,
            receipt_path.name: receipt_digest,
        },
        "claims": {
            "trained": True,
            "registered": False,
            "approved": False,
            "deployed": False,
        },
    }
    _write_json(manifest_path, manifest)
    return {
        "model_id": card["model_id"],
        "output_dir": str(target),
        "artifact_manifest": str(manifest_path),
        "checksums": manifest["files"],
    }


def load_estimator(model_path: str | Path):
    """Load an artifact only after its caller validates the manifest digest."""
    return joblib.load(Path(model_path))

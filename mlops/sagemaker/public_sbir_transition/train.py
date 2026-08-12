#!/usr/bin/env python3
"""SageMaker entry point for the authentic public SBIR transition candidate."""

from __future__ import annotations

import json
import hashlib
import os
import platform
from pathlib import Path


def main() -> None:
    import sklearn

    from public_intelligence.models.artifacts import save_training_output
    from public_intelligence.models.contracts import load_canonical_jsonl
    from public_intelligence.models.sbir_transition import train_sbir_transition

    channel = Path(os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    model_dir = Path(os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    print(
        json.dumps(
            {
                "event": "training_environment",
                "python": platform.python_version(),
                "scikit_learn": sklearn.__version__,
                "channel": str(channel),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    candidates = sorted(channel.glob("*.jsonl"))
    if len(candidates) != 1:
        raise RuntimeError("training channel must contain exactly one canonical JSONL dataset")
    expected_dataset_sha256 = os.environ.get("COMPASS_DATASET_SHA256")
    dataset_sha256 = hashlib.sha256(candidates[0].read_bytes()).hexdigest()
    if expected_dataset_sha256 and dataset_sha256 != expected_dataset_sha256:
        raise RuntimeError("training dataset digest does not match the submitted receipt")
    dataset = load_canonical_jsonl(candidates[0], allow_test_fixtures=False)
    if dataset.model_kind != "sbir_transition":
        raise RuntimeError("training dataset must declare model_kind sbir_transition")
    output = train_sbir_transition(dataset)
    result = save_training_output(output, model_dir)
    holdout = output.model_card["evaluation"]["holdout"]
    print(
        json.dumps(
            {
                "contract": "compass.sagemaker-public-sbir-transition.v1",
                "model_id": result["model_id"],
                "rows": len(dataset.rows),
                "dataset_sha256": dataset_sha256,
                "source_sha256": os.environ.get("COMPASS_SOURCE_SHA256"),
                "roc_auc": holdout["roc_auc"],
                "brier_score": holdout["brier_score"],
                "f1": holdout["f1"],
                "deployment_state": "candidate_only",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

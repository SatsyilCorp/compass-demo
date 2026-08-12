from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

import joblib

from public_intelligence.models.artifacts import save_training_output
from public_intelligence.models.cli import main
from public_intelligence.models.funding_forecast import train_funding_forecast

from .synthetic_fixtures import clone_records, funding_fixture


class ArtifactAndCliTests(unittest.TestCase):
    def test_artifacts_are_digest_bound_and_candidate_only(self):
        output = train_funding_forecast(funding_fixture())
        with tempfile.TemporaryDirectory() as directory:
            result = save_training_output(output, Path(directory) / "candidate")
            manifest = json.loads(Path(result["artifact_manifest"]).read_text())
            artifact_dir = Path(result["output_dir"])
            for name, expected in manifest["files"].items():
                observed = hashlib.sha256(
                    (artifact_dir / name).read_bytes()
                ).hexdigest()
                self.assertEqual(observed, expected)
            self.assertFalse(manifest["claims"]["approved"])
            self.assertFalse(manifest["claims"]["deployed"])
            restored = joblib.load(artifact_dir / "model.joblib")
            self.assertTrue(hasattr(restored, "predict_interval"))

    def test_cli_refuses_synthetic_fixture(self):
        records = clone_records(funding_fixture())
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "fixture.jsonl"
            input_path.write_text(
                "".join(
                    json.dumps(record, sort_keys=True) + "\n" for record in records
                ),
                encoding="utf-8",
            )
            error = StringIO()
            with redirect_stderr(error):
                code = main(
                    [
                        "train",
                        "--input",
                        str(input_path),
                        "--output",
                        str(Path(directory) / "artifacts"),
                    ]
                )
            self.assertEqual(code, 2)
            receipt = json.loads(error.getvalue())
            self.assertEqual(receipt["decision"], "refuse")
            self.assertEqual(receipt["reason_code"], "test_fixture_forbidden")


if __name__ == "__main__":
    unittest.main()

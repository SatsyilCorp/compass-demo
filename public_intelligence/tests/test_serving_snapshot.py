from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_serving_snapshot.py"
SPEC = importlib.util.spec_from_file_location("build_serving_snapshot", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ServingSnapshotTests(unittest.TestCase):
    def test_compact_record_removes_em_dash_and_keeps_https_citation(self) -> None:
        record = module.compact_record(
            {
                "source_record_id": "A-1",
                "title": "Naval research\u2014public evidence",
                "abstract": "Observed\u2014not predicted",
                "links": ["http://unsafe.example", "https://example.test/A-1"],
                "provenance": {"record_sha256": "a" * 64},
            },
            "crossref",
        )
        self.assertNotIn("\u2014", json.dumps(record, ensure_ascii=False))
        self.assertEqual(record["source_url"], "https://example.test/A-1")
        self.assertEqual(record["evidence_class"], "observed")

    def test_reservoir_is_bounded_and_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text("".join(json.dumps({"id": index}) + "\n" for index in range(50)))
            first = module.reservoir(path, 7, 42)
            second = module.reservoir(path, 7, 42)
            self.assertEqual(first, second)
            self.assertEqual(len(first), 7)

    def test_transition_model_record_reports_measured_candidate_without_success_claim(self) -> None:
        card = {
            "model_id": "sbir_transition-test",
            "algorithm": "calibrated-gradient-boosting",
            "dataset": {"records_received": 11287, "dataset_digest": "a" * 64},
            "evaluation": {
                "holdout": {
                    "roc_auc": 0.6148,
                    "brier_score": 0.2629,
                    "precision": 0.4298,
                    "recall": 0.8374,
                }
            },
        }
        receipt = {"artifact_sha256": "b" * 64}
        record = module.transition_model_record(card, receipt)
        self.assertEqual(record["evidence_class"], "predicted")
        self.assertIn("11287 authentic public examples", record["summary"])
        self.assertIn("does not measure ONR mission success", record["summary"])
        self.assertNotIn("PendingManualApproval", record["summary"])

        registered = module.transition_model_evidence(
            card,
            receipt,
            registration={"model_package_arn": "arn:aws:sagemaker:test"},
        )
        self.assertEqual(registered["state"], "PendingManualApproval")
        self.assertFalse(registered["approved"])
        self.assertFalse(registered["deployed"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from public_intelligence.models.contracts import dataset_from_records, digest_json
from public_intelligence.models.sbir_transition_dataset import build_sbir_transition_records


def _record(identifier: str, phase: str, start: str, organization: str, topic: str):
    record = {
        "source_id": "sbir",
        "source_record_id": identifier,
        "title": f"Public {phase} research record",
        "abstract": f"Public technical summary for {phase} with enough decision-time text for testing.",
        "start_date": start,
        "funding_amount": "150000",
        "identifiers": {"topic_code": topic, "award_id": identifier},
        "organizations": [organization, "Navy"],
        "topics": ["SBIR", phase, topic],
    }
    record["provenance"] = {"record_sha256": digest_json(record)}
    return record


class SbirTransitionDatasetBuilderTests(unittest.TestCase):
    def test_builder_uses_complete_horizons_and_exact_org_topic_links(self):
        rows = [
            _record("phase-i-positive", "Phase I", "2018-01-01", "Acme", "N18-001"),
            _record("phase-ii-positive", "Phase II", "2019-06-01", "Acme", "N18-001"),
            _record("phase-i-negative", "Phase I", "2018-02-01", "Beta", "N18-002"),
            _record("phase-ii-wrong-topic", "Phase II", "2019-05-01", "Beta", "N18-999"),
            _record("phase-i-censored", "Phase I", "2025-01-01", "Gamma", "N25-001"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sbir.jsonl.gz"
            with gzip.open(source, "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
            records, summary = build_sbir_transition_records(
                source,
                as_of_date=date(2026, 8, 11),
                horizon_months=36,
            )

        dataset = dataset_from_records(records)
        self.assertEqual(summary["eligible_rows"], 2)
        self.assertEqual(summary["positive_rows"], 1)
        self.assertEqual([row.label_value for row in dataset.rows], [1, 0])
        self.assertTrue(all("Phase II" not in row.features["public_text"] for row in dataset.rows))
        self.assertTrue(all(row.group_id.startswith("org-topic-") for row in dataset.rows))
        self.assertTrue(all(row.authorized_for_training for row in dataset.rows))


if __name__ == "__main__":
    unittest.main()

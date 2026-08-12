from __future__ import annotations

import unittest
from datetime import timedelta

from public_intelligence.models.contracts import TrainingRefusal, dataset_from_records
from public_intelligence.models.funding_forecast import train_funding_forecast

from .synthetic_fixtures import clone_records, funding_fixture


class CanonicalContractTests(unittest.TestCase):
    def test_production_loader_refuses_synthetic_test_fixture(self):
        records = clone_records(funding_fixture())
        with self.assertRaisesRegex(
            TrainingRefusal, "synthetic test fixtures"
        ) as raised:
            dataset_from_records(records, allow_test_fixtures=False)
        self.assertEqual(raised.exception.code, "test_fixture_forbidden")

    def test_missing_authentic_label_is_rejected(self):
        records = clone_records(funding_fixture())
        records[1]["label"]["authentic"] = False
        with self.assertRaises(TrainingRefusal) as raised:
            dataset_from_records(records, allow_test_fixtures=True)
        self.assertEqual(raised.exception.code, "authentic_labels_required")

    def test_feature_available_after_prediction_is_rejected(self):
        records = clone_records(funding_fixture())
        event = records[1]["event_time"].replace("Z", "+00:00")
        from datetime import datetime

        future = datetime.fromisoformat(event) + timedelta(seconds=1)
        records[1]["feature_lineage"][0]["max_available_at"] = future.isoformat()
        with self.assertRaises(TrainingRefusal) as raised:
            dataset_from_records(records, allow_test_fixtures=True)
        self.assertEqual(raised.exception.code, "temporal_cutoff_violation")

    def test_same_source_cannot_cross_temporal_splits(self):
        records = clone_records(funding_fixture())
        records[-1]["provenance"]["source_sha256"] = records[1]["provenance"][
            "source_sha256"
        ]
        data = dataset_from_records(records, allow_test_fixtures=True)
        with self.assertRaises(TrainingRefusal) as raised:
            train_funding_forecast(data)
        self.assertEqual(raised.exception.code, "source_leakage")

    def test_target_named_as_feature_is_rejected(self):
        records = clone_records(funding_fixture())
        records[0]["feature_schema"]["numeric"].append("funding_amount")
        with self.assertRaises(TrainingRefusal) as raised:
            dataset_from_records(records, allow_test_fixtures=True)
        self.assertEqual(raised.exception.code, "label_leakage")

    def test_minimum_sample_gate_refuses_small_dataset(self):
        records = clone_records(funding_fixture())[:31]
        data = dataset_from_records(records, allow_test_fixtures=True)
        with self.assertRaises(TrainingRefusal) as raised:
            train_funding_forecast(data)
        self.assertEqual(raised.exception.code, "insufficient_samples")


if __name__ == "__main__":
    unittest.main()

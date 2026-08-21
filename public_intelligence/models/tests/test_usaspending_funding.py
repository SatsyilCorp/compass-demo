from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from public_intelligence.models.contracts import dataset_from_records
from public_intelligence.models.usaspending_funding import build_funding_records


def _fixture_payload() -> dict:
    values = []
    for offset in range(65):
        fiscal_year = 2010 + offset // 4
        quarter = offset % 4 + 1
        values.append(
            {
                "fiscal_year": fiscal_year,
                "quarter": quarter,
                "period": f"FY{fiscal_year} Q{quarter}",
                "observed_obligations_usd": float(100_000 + offset * 1_000),
            }
        )
    return {
        "source": "USAspending spending_over_time",
        "scope": "Clearly synthetic builder test scope",
        "as_of_date": "2025-11-15",
        "values": values,
    }


class UsaSpendingFundingBuilderTests(unittest.TestCase):
    def test_builder_excludes_partial_period_and_warmup_without_future_leakage(self):
        payload = _fixture_payload()
        digest = hashlib.sha256(b"clearly-synthetic-builder-test").hexdigest()
        records, summary = build_funding_records(
            payload,
            artifact_sha256=digest,
            source_uri="fixture://usaspending-builder-test",
            test_fixture=True,
        )
        self.assertEqual(summary["periods_received"], 65)
        self.assertEqual(summary["complete_periods"], 64)
        self.assertEqual(summary["incomplete_periods_excluded"], ["FY2026 Q1"])
        self.assertEqual(summary["training_rows"], 60)
        dataset = dataset_from_records(records, allow_test_fixtures=True)
        first = dataset.rows[0]
        self.assertEqual(first.raw["label"]["value"], 104_000.0)
        self.assertEqual(first.features["lag_1_obligations_usd"], 103_000.0)
        self.assertEqual(first.features["lag_4_obligations_usd"], 100_000.0)
        self.assertEqual(first.features["rolling_4_mean_obligations_usd"], 101_500.0)
        for row in dataset.rows:
            for lineage in row.raw["feature_lineage"]:
                available = datetime.fromisoformat(
                    lineage["max_available_at"].replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                self.assertLessEqual(available, row.event_time)

    def test_each_quarter_has_a_distinct_split_source_digest(self):
        payload = _fixture_payload()
        digest = hashlib.sha256(b"clearly-synthetic-builder-test").hexdigest()
        records, _ = build_funding_records(
            payload,
            artifact_sha256=digest,
            source_uri="fixture://usaspending-builder-test",
            test_fixture=True,
        )
        source_digests = [row["provenance"]["source_sha256"] for row in records[1:]]
        self.assertEqual(len(source_digests), len(set(source_digests)))


if __name__ == "__main__":
    unittest.main()

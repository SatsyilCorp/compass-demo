from __future__ import annotations

import unittest
import json
from pathlib import Path

from public_intelligence.contracts import CanonicalRecord
from public_intelligence.pii import redact_text, sanitize_mapping
from public_intelligence.provenance import sha256_json


class ContractAndPiiTests(unittest.TestCase):
    def test_public_award_identifier_is_not_redacted_as_a_phone_number(self) -> None:
        rendered, count = redact_text(
            "Agency tracking N252-114 and award N68335-26-C-0082"
        )
        self.assertEqual(
            rendered, "Agency tracking N252-114 and award N68335-26-C-0082"
        )
        self.assertEqual(count, 0)

    def test_supported_phone_shapes_are_redacted(self) -> None:
        rendered, count = redact_text(
            "Call (301) 555-0100, 301-555-0101, or +1 301 555 0102"
        )
        self.assertNotIn("301", rendered)
        self.assertEqual(count, 3)

    def _record(self, retrieved_at: str, snapshot_id: str) -> CanonicalRecord:
        payload = {"id": "A-1", "title": "Stable title"}
        return CanonicalRecord.create(
            source_id="fixture",
            source_record_id="A-1",
            record_type="award",
            title="Stable title",
            source_url="https://example.org/records/A-1",
            retrieved_at=retrieved_at,
            snapshot_id=snapshot_id,
            source_payload_sha256=sha256_json(payload),
            organizations=["Research Lab", "Research Lab"],
            funding_amount="$1,250.00",
        )

    def test_record_hash_excludes_collection_time_and_snapshot(self) -> None:
        first = self._record("2026-08-11T12:00:00Z", "snapshot-one")
        second = self._record("2026-08-12T12:00:00Z", "snapshot-two")
        self.assertEqual(
            first.provenance.record_sha256, second.provenance.record_sha256
        )
        self.assertEqual(first.funding_amount, "1250")
        self.assertEqual(first.organizations, ("Research Lab",))

    def test_pii_policy_drops_fields_and_redacts_retained_text(self) -> None:
        sanitized, report = sanitize_mapping(
            {
                "Contact Name": "Jane Example",
                "Contact Email": "jane@example.org",
                "Contact Phone": "202-555-0188",
                "Abstract": "Email analyst@example.org or call 301-555-0100. SSN 123-45-6789.",
                "Company": "Public Research LLC",
            }
        )
        rendered = str(sanitized)
        self.assertNotIn("Jane Example", rendered)
        self.assertNotIn("jane@example.org", rendered)
        self.assertNotIn("analyst@example.org", rendered)
        self.assertNotIn("301-555-0100", rendered)
        self.assertNotIn("123-45-6789", rendered)
        self.assertEqual(sanitized["Company"], "Public Research LLC")
        self.assertEqual(report.dropped_fields, 3)
        self.assertEqual(report.redacted_values, 3)

    def test_machine_readable_contract_matches_dataclass_version(self) -> None:
        schema_path = (
            Path(__file__).parents[1] / "schemas" / "canonical-record.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], "1.0")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("provenance", schema["required"])
        self.assertIn(
            "regulatory_notice",
            schema["properties"]["record_type"]["enum"],
        )
        self.assertIn("web_page", schema["properties"]["record_type"]["enum"])
        self.assertIn("patent", schema["properties"]["record_type"]["enum"])


if __name__ == "__main__":
    unittest.main()

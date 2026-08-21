from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from public_intelligence.cli import main
from public_intelligence.registry import (
    AccessMode,
    create_connector,
    get_source,
    list_sources,
)

from fakes import FIXTURES, FakeHttp


class RegistryAndCliTests(unittest.TestCase):
    def test_registry_distinguishes_implemented_and_gated_sources(self) -> None:
        sources = {source.source_id: source for source in list_sources()}
        self.assertEqual(
            len([source for source in sources.values() if source.implemented]),
            12,
        )
        self.assertTrue(sources["usaspending"].implemented)
        self.assertTrue(sources["grants_gov"].implemented)
        self.assertTrue(sources["datacite"].implemented)
        self.assertTrue(sources["federal_register"].implemented)
        self.assertTrue(sources["uspto_patents"].implemented)
        self.assertEqual(sources["uspto_patents"].access_mode, AccessMode.GATED_API)
        self.assertIn(
            "USPTO_ODP_API_KEY at collection time",
            sources["uspto_patents"].requirements,
        )
        self.assertTrue(sources["sam_gov"].implemented)
        self.assertTrue(sources["onr_website"].implemented)
        self.assertEqual(
            sources["onr_website"].access_mode,
            AccessMode.PUBLIC_WEBSITE,
        )
        self.assertEqual(sources["sam_gov"].access_mode, AccessMode.GATED_API)
        self.assertEqual(sources["sbir"].access_mode, AccessMode.PUBLIC_DOWNLOAD)
        self.assertFalse(sources["advana"].implemented)
        self.assertIn("government-furnished access", sources["advana"].requirements)
        self.assertFalse(sources["pulse"].implemented)
        self.assertIn("government-furnished access", sources["pulse"].requirements)
        with self.assertRaises(RuntimeError):
            create_connector("advana")
        self.assertEqual(create_connector("grants_gov").agency, "DOD-ONR")
        self.assertEqual(
            create_connector("datacite").funder_ror,
            "https://ror.org/00rk2pe57",
        )
        self.assertEqual(create_connector("federal_register").agency, "navy-department")
        self.assertFalse(sources["navy_budget_materials"].implemented)
        self.assertIn(
            "approved direct-document manifest or manual transfer",
            sources["navy_budget_materials"].requirements,
        )
        for source_id in (
            "startup_investment_licensed",
            "company_intelligence_licensed",
            "informal_literature_licensed",
        ):
            self.assertFalse(sources[source_id].implemented)
            self.assertEqual(sources[source_id].access_mode, AccessMode.LICENSED)
            self.assertIn(
                "government-provided or approved license",
                sources[source_id].requirements,
            )
        for source_id in (
            "government_structured_reports",
            "government_unstructured_reports",
        ):
            self.assertFalse(sources[source_id].implemented)
            self.assertEqual(
                sources[source_id].access_mode,
                AccessMode.MANUAL_TRANSFER,
            )
            self.assertIn("approved transfer", sources[source_id].requirements)
        excluded = sources["restricted_opportunity_documents"]
        self.assertFalse(excluded.implemented)
        self.assertEqual(excluded.access_mode, AccessMode.EXCLUDED)
        self.assertIn("protected attachments", excluded.notes)
        self.assertIn("not fetched", excluded.notes)
        self.assertEqual(
            create_connector("sam_gov", sam_api_key="fixture-key").organization_code,
            "017.1700.ONR",
        )
        with self.assertRaisesRegex(ValueError, "SAM_GOV_API_KEY"):
            create_connector("sam_gov")
        self.assertEqual(
            create_connector(
                "uspto_patents",
                uspto_odp_api_key="fixture-key",
            ).product_id,
            "PVGPATDIS",
        )
        with self.assertRaisesRegex(ValueError, "USPTO_ODP_API_KEY"):
            create_connector("uspto_patents")
        with self.assertRaisesRegex(ValueError, "only to api.uspto.gov"):
            create_connector(
                "uspto_patents",
                uspto_odp_api_key="fixture-key",
                endpoint="https://example.org/files",
            )

    def test_cli_streams_fixture_to_gzip_with_checkpoint(self) -> None:
        fake = FakeHttp(stream_path=FIXTURES / "sbir.csv")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "navy.jsonl.gz"
            stdout = io.StringIO()
            with patch("public_intelligence.cli.RetryHttpClient", return_value=fake):
                with redirect_stdout(stdout):
                    result = main(
                        [
                            "collect",
                            "sbir",
                            "--output",
                            str(output),
                            "--gzip",
                            "--max-records",
                            "2",
                            "--batch-size",
                            "1",
                        ]
                    )
            self.assertEqual(result, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["records_written"], 2)
            self.assertTrue(output.exists())
            self.assertTrue(Path(str(output) + ".checkpoint.json").exists())
            self.assertEqual(fake.calls[0][0], "STREAM")

    def test_cli_requires_sam_key_from_environment(self) -> None:
        self.assertTrue(get_source("sam_gov").implemented)
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit):
                main(["collect", "sam_gov", "--output", "ignored.jsonl"])

    def test_cli_requires_uspto_key_from_environment(self) -> None:
        self.assertTrue(get_source("uspto_patents").implemented)
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(SystemExit):
                main(["collect", "uspto_patents", "--output", "ignored.jsonl"])


if __name__ == "__main__":
    unittest.main()

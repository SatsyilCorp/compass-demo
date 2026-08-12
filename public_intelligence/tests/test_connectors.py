from __future__ import annotations

import json
import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any, Mapping

from public_intelligence.connectors import (
    CollectionRequest,
    CrossrefConnector,
    DataCiteConnector,
    FederalRegisterConnector,
    GrantsGovConnector,
    OpenAlexConnector,
    OnrWebsiteConnector,
    OstiConnector,
    PubMedConnector,
    SamGovConnector,
    SbirFullCsvConnector,
    UsaSpendingConnector,
    UsptoPatentsConnector,
)

from fakes import FIXTURES, FakeHttp, json_fixture


class FakeUsptoHttp:
    def __init__(self, tables: Mapping[str, tuple[list[str], list[list[str]]]]) -> None:
        self.tables = dict(tables)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def download(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> Path:
        filename = url.rsplit("/", 1)[-1]
        fields, rows = self.tables[filename]
        text = io.StringIO(newline="")
        writer = csv.writer(text, delimiter="\t", lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(filename.removesuffix(".zip"), text.getvalue())
        payload = memory.getvalue()
        if len(payload) > max_bytes:
            raise RuntimeError("fixture exceeds byte limit")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        self.calls.append(
            (
                "DOWNLOAD",
                url,
                {"max_bytes": max_bytes, "header_names": sorted(headers or {})},
            )
        )
        return destination


def request(max_records: int = 10, page_size: int = 10) -> CollectionRequest:
    return CollectionRequest(
        max_records=max_records,
        page_size=page_size,
        snapshot_id="offline-fixture",
        retrieved_at="2026-08-11T12:00:00Z",
        from_date="2025-01-01",
        to_date="2026-08-11",
    )


class ConnectorTests(unittest.TestCase):
    def test_onr_website_obeys_robots_and_collects_only_safe_index_headings(
        self,
    ) -> None:
        robots = (FIXTURES / "onr_robots.txt").read_text(encoding="utf-8")
        sitemap = (FIXTURES / "onr_sitemap.html").read_text(encoding="utf-8")
        http = FakeHttp(text_responses=[robots, sitemap])

        connector = OnrWebsiteConnector()
        records = list(connector.collect(http, request(max_records=10)))

        self.assertTrue(connector.exhausted)
        self.assertEqual(
            [item.record.title for item in records],
            [
                "Organization",
                "C5ISRT",
                "Mathematical Data Science",
                "Funding Opportunities",
            ],
        )
        research = records[2].record
        self.assertEqual(research.record_type, "web_page")
        self.assertEqual(research.identifiers["drupal_node_id"], "3701")
        self.assertEqual(research.attributes["department_code"], "31")
        self.assertEqual(
            research.attributes["site_hierarchy"],
            ["Organization", "C5ISRT", "Mathematical Data Science"],
        )
        self.assertFalse(research.attributes["linked_page_fetched"])
        self.assertFalse(research.attributes["document_content_fetched"])
        rendered = json.dumps([item.record.to_dict() for item in records])
        for forbidden in (
            "Code 31 Contacts",
            "person@example.org",
            "example-announcement",
            "example.org/external",
            "/search/results",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertEqual(http.calls[0][1], "https://www.onr.navy.mil/robots.txt")
        self.assertEqual(http.calls[1][1], "https://www.onr.navy.mil/sitemap")

    def test_onr_website_refuses_disallowed_sitemap(self) -> None:
        http = FakeHttp(
            text_responses=[
                "User-agent: *\nDisallow: /sitemap\n",
                (FIXTURES / "onr_sitemap.html").read_text(encoding="utf-8"),
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "robots.txt disallows"):
            list(OnrWebsiteConnector().collect(http, request(max_records=10)))
        self.assertEqual(len(http.calls), 1)

    def test_onr_website_rejects_non_official_endpoints(self) -> None:
        with self.assertRaisesRegex(ValueError, "official"):
            OnrWebsiteConnector(sitemap_endpoint="https://example.org/sitemap")
        with self.assertRaisesRegex(ValueError, "official"):
            OnrWebsiteConnector(robots_endpoint="https://example.org/robots.txt")

    def test_onr_website_resume_requires_same_sitemap_digest(self) -> None:
        robots = (FIXTURES / "onr_robots.txt").read_text(encoding="utf-8")
        sitemap = (FIXTURES / "onr_sitemap.html").read_text(encoding="utf-8")
        first_http = FakeHttp(text_responses=[robots, sitemap])
        first = list(OnrWebsiteConnector().collect(first_http, request(max_records=1)))
        self.assertEqual(first[0].checkpoint["offset"], 1)

        changed_http = FakeHttp(text_responses=[robots, sitemap + "\n<!-- changed -->"])
        with self.assertRaisesRegex(RuntimeError, "sitemap changed"):
            list(
                OnrWebsiteConnector().collect(
                    changed_http,
                    request(max_records=10),
                    checkpoint=first[0].checkpoint,
                )
            )

    def test_uspto_patents_joins_exact_onr_scope_and_omits_people(self) -> None:
        tables = {
            "g_gov_interest_contracts.tsv.zip": (
                ["patent_id", "contract_award_number"],
                [
                    ["1111111", "N-00014-25-1-0001"],
                    ["2222222", "OTHER-100"],
                    ["3333333", "N00014-20-C-0002"],
                ],
            ),
            "g_gov_interest_org.tsv.zip": (
                [
                    "patent_id",
                    "gi_organization_id",
                    "fedagency_name",
                    "level_one",
                    "level_two",
                    "level_three",
                ],
                [
                    [
                        "2222222",
                        "179",
                        "Office of Naval Research",
                        "Department of Defense",
                        "Navy",
                        "Office of Naval Research",
                    ],
                    [
                        "3333333",
                        "1",
                        "Air Force",
                        "Department of Defense",
                        "Air Force",
                        "Air Force",
                    ],
                ],
            ),
            "g_gov_interest.tsv.zip": (
                ["patent_id", "gi_statement"],
                [
                    [
                        "1111111",
                        "N00014 support. Contact inventor@example.org or 301-555-0100.",
                    ],
                    ["2222222", "Supported by the Office of Naval Research."],
                    ["3333333", "Old ONR grant."],
                ],
            ),
            "g_patent.tsv.zip": (
                ["patent_id", "patent_type", "patent_date", "patent_title", "withdrawn"],
                [
                    ["1111111", "utility", "2025-02-01", "Autonomy\u2014at sea", "0"],
                    ["2222222", "utility", "2025-03-02", "Quantum sensing", "0"],
                    ["3333333", "utility", "2019-01-01", "Outside window", "0"],
                ],
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            http = FakeUsptoHttp(tables)
            connector = UsptoPatentsConnector(
                api_key="fixture-secret",
                endpoint="https://example.org/files",
                cache_dir=Path(directory),
                allow_non_official_endpoint_for_testing=True,
            )
            records = list(connector.collect(http, request()))

        self.assertEqual(
            [item.record.source_record_id for item in records],
            ["1111111", "2222222"],
        )
        first = records[0].record
        self.assertEqual(first.record_type, "patent")
        self.assertEqual(first.title, "Autonomy - at sea")
        self.assertEqual(
            first.identifiers["government_interest_award_numbers"],
            ["N-00014-25-1-0001"],
        )
        self.assertIn("exact_n00014_award_prefix", first.attributes["match_basis"])
        self.assertTrue(first.attributes["government_interest_statement_available"])
        self.assertFalse(first.attributes["government_interest_statement_collected"])
        self.assertEqual(first.attributes["pii_redacted_values"], 2)
        rendered = json.dumps([item.record.to_dict() for item in records])
        self.assertNotIn("inventor@example.org", rendered)
        self.assertNotIn("301-555-0100", rendered)
        self.assertNotIn("fixture-secret", json.dumps(http.calls))
        self.assertEqual(
            {call[2]["header_names"][0] for call in http.calls},
            {"X-API-Key"},
        )
        self.assertTrue(connector.exhausted)

    def test_uspto_patents_resume_rejects_changed_source_files(self) -> None:
        tables = {
            "g_gov_interest_contracts.tsv.zip": (
                ["patent_id", "contract_award_number"],
                [["1111111", "N00014-25-1-0001"]],
            ),
            "g_gov_interest_org.tsv.zip": (
                ["patent_id", "fedagency_name", "level_one", "level_two", "level_three"],
                [],
            ),
            "g_gov_interest.tsv.zip": (
                ["patent_id", "gi_statement"],
                [["1111111", "ONR support"]],
            ),
            "g_patent.tsv.zip": (
                ["patent_id", "patent_type", "patent_date", "patent_title"],
                [["1111111", "utility", "2025-02-01", "Autonomy"]],
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            connector = UsptoPatentsConnector(
                api_key="fixture-secret",
                endpoint="https://example.org/files",
                cache_dir=Path(directory),
                allow_non_official_endpoint_for_testing=True,
            )
            with self.assertRaisesRegex(RuntimeError, "source files changed"):
                list(
                    connector.collect(
                        FakeUsptoHttp(tables),
                        request(),
                        checkpoint={
                            "record_offset": 1,
                            "source_files_sha256": {"changed": "0" * 64},
                        },
                    )
                )

    def test_api_page_budget_stops_cyclic_collection(self) -> None:
        response = json_fixture("usaspending.json")
        response["results"] = [None]
        response["page_metadata"]["hasNext"] = True
        http = FakeHttp(post_responses=[response])
        bounded = request(max_records=10)
        bounded = CollectionRequest(**{**bounded.__dict__, "max_pages": 1})
        with self.assertRaisesRegex(RuntimeError, "page budget"):
            list(UsaSpendingConnector().collect(http, bounded))

    def test_usaspending_normalizes_and_resumes_inside_page(self) -> None:
        response = json_fixture("usaspending.json")
        first_http = FakeHttp(post_responses=[response])
        first = list(UsaSpendingConnector().collect(first_http, request(max_records=1)))
        self.assertEqual(first[0].record.source_record_id, "N00014-26-1-0001")
        self.assertEqual(first[0].record.funding_amount, "1250000")
        self.assertEqual(first[0].checkpoint, {"page": 1, "offset": 1})

        second_http = FakeHttp(post_responses=[response])
        second = list(
            UsaSpendingConnector().collect(
                second_http,
                request(),
                checkpoint=first[0].checkpoint,
            )
        )
        self.assertEqual(
            [item.record.source_record_id for item in second], ["N00014-26-1-0002"]
        )

    def test_sbir_streams_navy_only_and_removes_direct_pii(self) -> None:
        http = FakeHttp(stream_path=FIXTURES / "sbir.csv")
        records = list(SbirFullCsvConnector().collect(http, request()))
        self.assertEqual(
            [item.record.source_record_id for item in records], ["N26-001", "N26-003"]
        )
        rendered = json.dumps([item.record.to_dict() for item in records])
        for forbidden in (
            "navy.pi@example.org",
            "202-555-0188",
            "Jordan Example",
            "123-45-6789",
            "100 Main Street",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("[REDACTED_EMAIL]", rendered)
        self.assertIn("[REDACTED_SSN]", rendered)
        self.assertEqual(http.calls[0][0], "STREAM")

    def test_sbir_resume_uses_source_row_not_retained_row(self) -> None:
        first_http = FakeHttp(stream_path=FIXTURES / "sbir.csv")
        first = list(SbirFullCsvConnector().collect(first_http, request(max_records=1)))
        self.assertEqual(first[0].checkpoint["row_index"], 1)
        second_http = FakeHttp(stream_path=FIXTURES / "sbir.csv")
        second = list(
            SbirFullCsvConnector().collect(
                second_http,
                request(),
                checkpoint=first[0].checkpoint,
            )
        )
        self.assertEqual([item.record.source_record_id for item in second], ["N26-003"])

    def test_crossref_uses_cursor_and_omits_author_identity(self) -> None:
        http = FakeHttp(get_responses=[json_fixture("crossref.json")])
        records = list(
            CrossrefConnector(mailto="team@example.org").collect(http, request())
        )
        self.assertEqual(len(records), 1)
        record = records[0].record
        self.assertEqual(record.source_record_id, "10.5555/naval.001")
        self.assertEqual(record.attributes["author_count"], 1)
        self.assertIsNone(record.abstract)
        self.assertTrue(record.attributes["abstract_available"])
        self.assertEqual(record.attributes["reference_count"], 18)
        self.assertEqual(record.identifiers["funding_award_ids"], ["N00014-25-1-0001"])
        rendered = json.dumps(record.to_dict())
        self.assertNotIn("Jane", rendered)
        self.assertNotIn("author@example.org", rendered)
        self.assertIn("Naval Research University", record.organizations)
        self.assertEqual(http.calls[0][2]["cursor"], "*")

    def test_crossref_same_cursor_token_can_advance_server_scroll(self) -> None:
        first = json_fixture("crossref.json")
        second = json_fixture("crossref.json")
        second["message"]["items"][0]["DOI"] = "10.5555/naval.002"
        first["message"]["next-cursor"] = "stable-scroll-token"
        second["message"]["next-cursor"] = "stable-scroll-token"
        exhausted = {"message": {"next-cursor": "stable-scroll-token", "items": []}}
        http = FakeHttp(get_responses=[first, second, exhausted])
        records = list(
            CrossrefConnector(mailto="team@example.org").collect(
                http, request(max_records=3, page_size=1)
            )
        )
        self.assertEqual(
            [item.record.source_record_id for item in records],
            ["10.5555/naval.001", "10.5555/naval.002"],
        )

    def test_openalex_rebuilds_abstract_without_author_identity(self) -> None:
        http = FakeHttp(get_responses=[json_fixture("openalex.json")])
        records = list(
            OpenAlexConnector(api_key="fixture-key").collect(http, request())
        )
        self.assertEqual(len(records), 1)
        record = records[0].record
        self.assertEqual(record.source_record_id, "W1234567890")
        self.assertEqual(record.abstract, "Resilient autonomy supports missions")
        self.assertEqual(record.identifiers["funding_award_ids"], ["N00014-25-1-0001"])
        self.assertEqual(record.attributes["open_access_status"], "gold")
        self.assertIn("Maritime Technology Institute", record.organizations)
        self.assertNotIn("A Public Scholar", json.dumps(record.to_dict()))
        self.assertEqual(http.calls[0][2]["api_key"], "fixture-key")

    def test_openalex_redacts_pii_stored_as_abstract_tokens(self) -> None:
        response = json_fixture("openalex.json")
        response["results"][0]["abstract_inverted_index"].update(
            {
                "analyst@example.org": [4],
                "(301) 555-0100": [5],
            }
        )
        http = FakeHttp(get_responses=[response])

        records = list(OpenAlexConnector().collect(http, request()))

        record = records[0].record
        self.assertEqual(
            record.abstract,
            "Resilient autonomy supports missions [REDACTED_EMAIL] [REDACTED_PHONE]",
        )
        self.assertEqual(record.attributes["pii_redacted_values"], 2)
        rendered = json.dumps(record.to_dict())
        self.assertNotIn("analyst@example.org", rendered)
        self.assertNotIn("301", rendered)

    def test_pubmed_uses_exact_grant_scope_and_omits_people_and_abstracts(self) -> None:
        http = FakeHttp(
            get_responses=[json_fixture("pubmed_search.json")],
            text_responses=[(FIXTURES / "pubmed.xml").read_text(encoding="utf-8")],
        )
        records = list(PubMedConnector(email="team@example.org").collect(http, request()))
        self.assertEqual(len(records), 1)
        first = records[0].record
        self.assertEqual(first.source_record_id, "40100101")
        self.assertEqual(first.published_date, "2025-06-03")
        self.assertEqual(first.identifiers["grant_ids"], ["N00014-24-1-0001"])
        self.assertTrue(first.attributes["abstract_available"])
        self.assertIsNone(first.abstract)
        rendered = json.dumps(first.to_dict())
        self.assertNotIn("Copyrighted abstract", rendered)
        self.assertNotIn("Alex", rendered)
        self.assertNotIn("Example", rendered)
        self.assertIn("Autonomous Systems", first.topics)
        search_params = http.calls[0][2]
        self.assertEqual(search_params["term"], "N00014[Grant Number]")
        self.assertEqual(search_params["retmax"], 10)
        self.assertEqual(http.calls[1][0], "GET_TEXT")

    def test_osti_uses_exact_sponsor_and_omits_people_and_description(self) -> None:
        http = FakeHttp(get_responses=[json_fixture("osti.json")])
        records = list(OstiConnector().collect(http, request(max_records=10)))
        self.assertEqual(len(records), 1)
        record = records[0].record
        self.assertEqual(record.source_record_id, "3398572")
        self.assertEqual(record.identifiers["contract_numbers"], ["N00014-22-1-2202"])
        self.assertIsNone(record.abstract)
        self.assertTrue(record.attributes["description_available"])
        rendered = json.dumps(record.to_dict())
        self.assertNotIn("Researcher, Riley", rendered)
        self.assertNotIn("Publisher abstract", rendered)
        self.assertIn("Office of Naval Research", record.organizations)
        self.assertEqual(http.calls[0][2]["sponsor_org"], "Office of Naval Research")
        self.assertEqual(http.calls[0][2]["rows"], 10)

    def test_sam_gov_uses_exact_onr_scope_and_omits_sensitive_content(self) -> None:
        response = json_fixture("sam_gov.json")
        first_http = FakeHttp(get_responses=[response])
        first = list(
            SamGovConnector(api_key="fixture-key").collect(
                first_http,
                request(max_records=1, page_size=2),
            )
        )
        self.assertEqual(len(first), 1)
        record = first[0].record
        self.assertEqual(record.source_record_id, "sam-onr-notice-001")
        self.assertEqual(record.record_type, "solicitation")
        self.assertEqual(record.published_date, "2025-05-01")
        self.assertEqual(record.end_date, "2025-06-01")
        self.assertEqual(
            record.identifiers["organization_path_code"],
            "017.1700.ONR.ONR NRL.N00173",
        )
        self.assertEqual(record.attributes["contact_records_omitted"], 1)
        self.assertEqual(record.attributes["attachment_links_omitted"], 1)
        self.assertFalse(record.attributes["contacts_collected"])
        self.assertFalse(record.attributes["description_collected"])
        self.assertFalse(record.attributes["attachments_collected"])
        rendered = json.dumps(record.to_dict())
        for forbidden in (
            "fixture-key",
            "Taylor Example",
            "taylor.example@example.mil",
            "202-555-0101",
            "4555 Overlook",
            "100 Research Way",
            "secret-attachment",
            "noticedesc",
        ):
            self.assertNotIn(forbidden, rendered)
        params = first_http.calls[0][2]
        self.assertEqual(params["api_key"], "fixture-key")
        self.assertEqual(params["organizationCode"], "017.1700.ONR")
        self.assertEqual(params["postedFrom"], "01/01/2025")
        self.assertEqual(params["postedTo"], "12/31/2025")
        self.assertEqual(
            first[0].checkpoint,
            {"window_index": 0, "api_offset": 0, "item_offset": 1},
        )

        second_http = FakeHttp(get_responses=[response])
        second = list(
            SamGovConnector(api_key="fixture-key").collect(
                second_http,
                request(max_records=1, page_size=2),
                checkpoint=first[0].checkpoint,
            )
        )
        self.assertEqual(second[0].record.source_record_id, "sam-onr-notice-002")
        self.assertEqual(second[0].record.record_type, "award")
        self.assertEqual(second[0].record.funding_amount, "2500000")
        self.assertEqual(
            second[0].record.organizations[-1], "Ocean Systems Corporation"
        )

    def test_sam_gov_rejects_records_outside_onr_hierarchy(self) -> None:
        response = json_fixture("sam_gov.json")
        response["opportunitiesData"][0]["fullParentPathCode"] = "017.1700.NAVSEA"
        http = FakeHttp(get_responses=[response])
        with self.assertRaisesRegex(RuntimeError, "outside the requested"):
            list(
                SamGovConnector(api_key="fixture-key").collect(
                    http,
                    request(max_records=1, page_size=2),
                )
            )

    def test_sam_gov_rejects_records_outside_requested_dates(self) -> None:
        response = json_fixture("sam_gov.json")
        response["opportunitiesData"][0]["postedDate"] = "2024-12-31"
        http = FakeHttp(get_responses=[response])
        with self.assertRaisesRegex(RuntimeError, "outside the requested date"):
            list(
                SamGovConnector(api_key="fixture-key").collect(
                    http,
                    request(max_records=1, page_size=2),
                )
            )

    def test_grants_gov_fetches_onr_details_and_removes_contact_pii(self) -> None:
        http = FakeHttp(
            post_responses=[
                json_fixture("grants_search.json"),
                json_fixture("grants_detail_1.json"),
            ]
        )
        records = list(GrantsGovConnector().collect(http, request(max_records=1)))
        self.assertEqual(len(records), 1)
        record = records[0].record
        self.assertEqual(record.source_record_id, "N00014-25-S-F001")
        self.assertEqual(record.record_type, "solicitation")
        self.assertEqual(record.published_date, "2025-01-15")
        self.assertEqual(record.end_date, "2025-04-15")
        self.assertEqual(record.identifiers["aln"], ["12.300"])
        self.assertEqual(record.attributes["agency_scope"], "DOD-ONR")
        self.assertEqual(record.attributes["award_ceiling"], "2500000")
        rendered = json.dumps(record.to_dict())
        for forbidden in (
            "Taylor Example",
            "grants.poc@example.mil",
            "703-555-0101",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("[REDACTED_EMAIL]", rendered)
        self.assertIn("[REDACTED_PHONE]", rendered)
        self.assertEqual(records[0].checkpoint, {"start_record": 0, "offset": 1})
        self.assertEqual(http.calls[0][2]["agencies"], "DOD-ONR")
        self.assertEqual(http.calls[0][2]["sortBy"], "openDate|asc")
        self.assertEqual(http.calls[1][2], {"opportunityId": 350001})

    def test_grants_gov_resume_skips_committed_hit_and_fetches_next_detail(
        self,
    ) -> None:
        http = FakeHttp(
            post_responses=[
                json_fixture("grants_search.json"),
                json_fixture("grants_detail_2.json"),
            ]
        )
        records = list(
            GrantsGovConnector().collect(
                http,
                request(),
                checkpoint={"start_record": 0, "offset": 1},
            )
        )
        self.assertEqual(
            [item.record.source_record_id for item in records], ["N00014-26-S-F002"]
        )
        self.assertEqual(http.calls[1][2], {"opportunityId": 350002})
        self.assertTrue(GrantsGovConnector(fetch_details=False).fetch_details is False)

    def test_datacite_filters_by_onr_ror_and_omits_researcher_identity(self) -> None:
        http = FakeHttp(get_responses=[json_fixture("datacite.json")])
        records = list(DataCiteConnector().collect(http, request(max_records=1)))
        self.assertEqual(len(records), 1)
        record = records[0].record
        self.assertEqual(record.source_record_id, "10.5281/zenodo.100001")
        self.assertEqual(record.record_type, "dataset")
        self.assertEqual(record.published_date, "2025-05-20")
        self.assertEqual(record.identifiers["award_numbers"], ["N00014-24-1-0001"])
        self.assertIn("Ocean Research Institute", record.organizations)
        self.assertEqual(record.attributes["creator_count"], 1)
        rendered = json.dumps(record.to_dict())
        for forbidden in (
            "Researcher, Riley",
            "0000-0001-2345-6789",
            "data@example.org",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("[REDACTED_EMAIL]", rendered)
        params = http.calls[0][2]
        self.assertEqual(params["funded-by"], "https://ror.org/00rk2pe57")
        self.assertEqual(params["page[cursor]"], "1")
        self.assertIn("publicationYear:[2025 TO 2026]", params["query"])

    def test_datacite_resume_uses_page_cursor_and_offset(self) -> None:
        http = FakeHttp(get_responses=[json_fixture("datacite.json")])
        records = list(
            DataCiteConnector().collect(
                http,
                request(),
                checkpoint={"cursor": "1", "offset": 1},
            )
        )
        self.assertEqual(
            [item.record.source_record_id for item in records],
            ["10.5555/article.100002"],
        )
        self.assertEqual(records[0].record.record_type, "publication")

    def test_federal_register_maps_official_links_and_removes_contact_pii(self) -> None:
        http = FakeHttp(
            get_responses=[
                json_fixture("federal_register_search.json"),
                json_fixture("federal_register_detail_1.json"),
            ]
        )
        records = list(FederalRegisterConnector().collect(http, request(max_records=1)))
        self.assertEqual(len(records), 1)
        record = records[0].record
        self.assertEqual(record.source_record_id, "2026-10001")
        self.assertEqual(record.record_type, "regulatory_notice")
        self.assertEqual(record.published_date, "2026-05-01")
        self.assertEqual(record.end_date, "2026-06-01")
        self.assertEqual(
            record.identifiers["docket_ids"], ["Docket ID: USN-2026-HQ-0001"]
        )
        self.assertEqual(record.identifiers["cfr_references"], ["32 CFR 700"])
        self.assertIn(
            "https://www.govinfo.gov/content/pkg/FR-2026-05-01/pdf/2026-10001.pdf",
            record.links,
        )
        rendered = json.dumps(record.to_dict())
        for forbidden in ("analyst@example.mil", "202-555-0101", "Public Contact"):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("[REDACTED_EMAIL]", rendered)
        self.assertIn("[REDACTED_PHONE]", rendered)
        self.assertFalse(record.attributes["content_collected"])
        self.assertEqual(records[0].checkpoint, {"page": 1, "offset": 1})
        params = http.calls[0][2]
        self.assertEqual(params["conditions[agencies][]"], "navy-department")
        self.assertEqual(params["conditions[term]"], '"Office of Naval Research"')
        self.assertEqual(params["order"], "oldest")
        self.assertEqual(
            http.calls[1][1],
            "https://www.federalregister.gov/api/v1/documents/2026-10001.json",
        )

    def test_federal_register_resume_skips_committed_document(self) -> None:
        http = FakeHttp(
            get_responses=[
                json_fixture("federal_register_search.json"),
                json_fixture("federal_register_detail_2.json"),
            ]
        )
        records = list(
            FederalRegisterConnector().collect(
                http,
                request(),
                checkpoint={"page": 1, "offset": 1},
            )
        )
        self.assertEqual(
            [item.record.source_record_id for item in records],
            ["2026-10002"],
        )
        self.assertEqual(len(http.calls), 2)
        self.assertTrue(
            FederalRegisterConnector(fetch_details=False).fetch_details is False
        )


if __name__ == "__main__":
    unittest.main()

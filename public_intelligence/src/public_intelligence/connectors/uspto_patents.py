"""USPTO PatentsView patent grants with exact ONR government-interest links."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import urlsplit

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import redact_text
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest, normalize_public_date


DEFAULT_PRODUCT_ID = "PVGPATDIS"
DEFAULT_FILE_ENDPOINT = "https://api.uspto.gov/api/v1/datasets/products/files"
DEFAULT_CACHE_DIR = Path(".cache/uspto-patentsview")
DEFAULT_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
OFFICIAL_ODP_HOST = "api.uspto.gov"
ONR_ORGANIZATION = "Office of Naval Research"
DATASET_URL = "https://data.uspto.gov/support/transition-guide/patentsview"
TABLE_FILES = (
    "g_gov_interest_contracts.tsv.zip",
    "g_gov_interest_org.tsv.zip",
    "g_gov_interest.tsv.zip",
    "g_patent.tsv.zip",
)


def _clean_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = " ".join(str(value).replace("\u2014", " - ").split()).strip()
    if not text:
        return None
    cleaned, _ = redact_text(text)
    return cleaned


def _normalized_award(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _is_onr_award(value: Any) -> bool:
    """Match the canonical N00014 sponsor prefix after punctuation folding."""

    normalized = _normalized_award(value)
    return normalized.startswith("N00014") and len(normalized) > len("N00014")


def _is_onr_organization(row: Mapping[str, Any]) -> bool:
    expected = ONR_ORGANIZATION.casefold()
    return any(
        str(row.get(field) or "").strip().casefold() == expected
        for field in ("fedagency_name", "level_three")
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.casefold().endswith(".tsv")]
        if len(names) != 1:
            raise RuntimeError(f"{path.name} must contain exactly one TSV table")
        with archive.open(names[0]) as binary:
            text = io.TextIOWrapper(
                binary,
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            )
            reader = csv.DictReader(text, delimiter="\t")
            if not reader.fieldnames:
                raise RuntimeError(f"{path.name} has no TSV header")
            for row in reader:
                yield {str(key): str(value or "") for key, value in row.items() if key}


def _patent_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    patent_id = str(row.get("patent_id") or "")
    try:
        return int(patent_id), patent_id
    except ValueError:
        return 2**63 - 1, patent_id


class UsptoPatentsConnector:
    """Join bounded official PatentsView bulk tables into minimized patent records.

    The connector selects a patent only when PatentsView reports either an exact
    Office of Naval Research government organization or a contract or award
    number whose punctuation-folded value starts with N00014. It never reads or
    retains inventor, attorney, applicant, assignee-person, or address tables.
    Government-interest statement text is not persisted. Its sanitized digest
    is retained only to support source reconciliation.
    """

    source_id = "uspto_patents"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = DEFAULT_FILE_ENDPOINT,
        product_id: str = DEFAULT_PRODUCT_ID,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
        refresh_cache: bool = False,
        allow_non_official_endpoint_for_testing: bool = False,
    ) -> None:
        if not api_key.strip():
            raise ValueError("USPTO_ODP_API_KEY is required")
        if not endpoint.startswith("https://"):
            raise ValueError("USPTO ODP file endpoint must use HTTPS")
        if (
            urlsplit(endpoint).hostname != OFFICIAL_ODP_HOST
            and not allow_non_official_endpoint_for_testing
        ):
            raise ValueError("USPTO ODP API keys may be sent only to api.uspto.gov")
        if not product_id.strip():
            raise ValueError("USPTO ODP product identifier is required")
        self.api_key = api_key.strip()
        self.endpoint = endpoint.rstrip("/")
        self.product_id = product_id.strip()
        self.cache_dir = Path(cache_dir)
        self.max_download_bytes = max_download_bytes
        self.refresh_cache = refresh_cache
        self.exhausted = False

    def _table_url(self, filename: str) -> str:
        return f"{self.endpoint}/{self.product_id}/{filename}"

    def _download_tables(self, http: HttpTransport) -> dict[str, Path]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        for filename in TABLE_FILES:
            destination = self.cache_dir / filename
            if self.refresh_cache and destination.exists():
                destination.unlink()
            paths[filename] = http.download(
                self._table_url(filename),
                destination,
                max_bytes=self.max_download_bytes,
                headers={"X-API-Key": self.api_key},
            )
        return paths

    @staticmethod
    def _scope(
        paths: Mapping[str, Path],
    ) -> tuple[
        dict[str, set[str]],
        dict[str, list[dict[str, str]]],
        dict[str, dict[str, Any]],
    ]:
        awards: dict[str, set[str]] = defaultdict(set)
        organizations: dict[str, list[dict[str, str]]] = defaultdict(list)
        match_basis: dict[str, set[str]] = defaultdict(set)

        for row in _rows(paths["g_gov_interest_contracts.tsv.zip"]):
            patent_id = row.get("patent_id", "").strip()
            award = _clean_text(row.get("contract_award_number"))
            if patent_id and award and _is_onr_award(award):
                awards[patent_id].add(award)
                match_basis[patent_id].add("exact_n00014_award_prefix")

        for row in _rows(paths["g_gov_interest_org.tsv.zip"]):
            patent_id = row.get("patent_id", "").strip()
            if not patent_id or not _is_onr_organization(row):
                continue
            safe = {
                key: value
                for key in ("fedagency_name", "level_one", "level_two", "level_three")
                if (value := _clean_text(row.get(key)))
            }
            if safe not in organizations[patent_id]:
                organizations[patent_id].append(safe)
            match_basis[patent_id].add("exact_office_of_naval_research_organization")

        selected = set(match_basis)
        statements: dict[str, dict[str, Any]] = {}
        for row in _rows(paths["g_gov_interest.tsv.zip"]):
            patent_id = row.get("patent_id", "").strip()
            if patent_id not in selected:
                continue
            statement, redactions = redact_text(str(row.get("gi_statement") or ""))
            statements[patent_id] = {
                "available": bool(statement.strip()),
                "sanitized_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest()
                if statement.strip()
                else None,
                "pii_redacted_values": redactions,
            }
        return awards, organizations, {
            patent_id: {
                "match_basis": sorted(bases),
                "statement": statements.get(
                    patent_id,
                    {
                        "available": False,
                        "sanitized_sha256": None,
                        "pii_redacted_values": 0,
                    },
                ),
            }
            for patent_id, bases in match_basis.items()
        }

    @staticmethod
    def _patent_rows(
        path: Path,
        selected: set[str],
        from_date: str | None,
        to_date: str | None,
    ) -> list[dict[str, str]]:
        output: list[dict[str, str]] = []
        for row in _rows(path):
            patent_id = row.get("patent_id", "").strip()
            if patent_id not in selected:
                continue
            patent_date = normalize_public_date(row.get("patent_date"))
            if from_date and (not patent_date or patent_date < from_date):
                continue
            if to_date and (not patent_date or patent_date > to_date):
                continue
            output.append(row)
        output.sort(key=_patent_sort_key)
        return output

    def _record(
        self,
        row: Mapping[str, Any],
        request: CollectionRequest,
        awards: Mapping[str, set[str]],
        organizations: Mapping[str, list[dict[str, str]]],
        scope: Mapping[str, Mapping[str, Any]],
        source_files_sha256: Mapping[str, str],
    ) -> CanonicalRecord:
        patent_id = str(row.get("patent_id") or "").strip()
        patent_title = _clean_text(row.get("patent_title")) or f"US Patent {patent_id}"
        patent_date = normalize_public_date(row.get("patent_date"))
        patent_type = _clean_text(row.get("patent_type"))
        award_numbers = sorted(awards.get(patent_id, set()))
        organization_rows = organizations.get(patent_id, [])
        organization_names = [
            value
            for item in organization_rows
            for key in ("fedagency_name", "level_one", "level_two", "level_three")
            if (value := item.get(key))
        ]
        scope_row = scope[patent_id]
        statement = scope_row["statement"]
        safe_payload = {
            "patent_id": patent_id,
            "patent_title": patent_title,
            "patent_date": patent_date,
            "patent_type": patent_type,
            "withdrawn": _clean_text(row.get("withdrawn")),
            "award_numbers": award_numbers,
            "government_organizations": organization_rows,
            "match_basis": scope_row["match_basis"],
            "government_interest_statement_available": statement["available"],
            "government_interest_statement_sanitized_sha256": statement[
                "sanitized_sha256"
            ],
        }
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=patent_id,
            record_type="patent",
            title=patent_title,
            published_date=patent_date,
            organizations=[ONR_ORGANIZATION, *organization_names],
            topics=[patent_type, "government-funded patent"],
            links=[
                (
                    "https://ppubs.uspto.gov/pubwebapp/external.html"
                    f"?q=({patent_id}).pn.&db=USPAT&type=ids"
                ),
                DATASET_URL,
            ],
            identifiers={
                "us_patent_number": patent_id,
                "government_interest_award_numbers": award_numbers,
            },
            attributes={
                "match_basis": scope_row["match_basis"],
                "government_organizations": organization_rows,
                "government_interest_statement_available": statement["available"],
                "government_interest_statement_collected": False,
                "government_interest_statement_sanitized_sha256": statement[
                    "sanitized_sha256"
                ],
                "pii_redacted_values": statement["pii_redacted_values"],
                "people_and_addresses_collected": False,
                "source_product_id": self.product_id,
                "source_data_through": "2025-12-31",
                "source_files_sha256": dict(source_files_sha256),
                "license": "CC BY 4.0",
                "quality_note": (
                    "PatentsView extracts government organizations and award numbers "
                    "from USPTO government-interest statements. Exact matches remain "
                    "subject to source extraction error and analyst review."
                ),
            },
            source_url=DATASET_URL,
            retrieved_at=request.retrieved_at,
            snapshot_id=request.snapshot_id,
            source_payload_sha256=sha256_json(safe_payload),
        )

    def collect(
        self,
        http: HttpTransport,
        request: CollectionRequest,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> Iterator[CollectedRecord]:
        self.exhausted = False
        paths = self._download_tables(http)
        source_files_sha256 = {
            filename: _sha256_file(path) for filename, path in sorted(paths.items())
        }
        state = dict(checkpoint or {})
        prior_digests = state.get("source_files_sha256")
        if prior_digests and prior_digests != source_files_sha256:
            raise RuntimeError(
                "USPTO source files changed after collection began; start a fresh snapshot"
            )

        awards, organizations, scope = self._scope(paths)
        rows = self._patent_rows(
            paths["g_patent.tsv.zip"],
            set(scope),
            request.from_date,
            request.to_date,
        )
        start_offset = max(0, int(state.get("record_offset", 0)))
        emitted = 0
        for offset, row in enumerate(rows):
            if offset < start_offset:
                continue
            if emitted >= request.max_records:
                return
            emitted += 1
            yield CollectedRecord(
                record=self._record(
                    row,
                    request,
                    awards,
                    organizations,
                    scope,
                    source_files_sha256,
                ),
                checkpoint={
                    "record_offset": offset + 1,
                    "source_files_sha256": source_files_sha256,
                    "selected_records": len(rows),
                },
            )
        self.exhausted = True

"""Streaming connector for the official full SBIR and STTR award CSV."""

from __future__ import annotations

import csv
import io
from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import normalize_key, sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest


DEFAULT_ARCHIVE_URL = "https://data.www.sbir.gov/mod_awarddatapublic/award_data.csv"
DEFAULT_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


def _index_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {normalize_key(str(key)): value for key, value in row.items()}


def _value(row: Mapping[str, Any], *aliases: str) -> Any:
    indexed = _index_row(row)
    for alias in aliases:
        value = indexed.get(normalize_key(alias))
        if value not in (None, ""):
            return value
    return None


class SbirFullCsvConnector:
    """Read the remote CSV once per run without retaining the raw archive.

    Resume uses the committed source-row ordinal. A resumed run reopens the
    stream and skips prior rows. This favors low disk use and PII minimization
    over network efficiency. ETag or Last-Modified protects a partial snapshot
    from silently spanning source versions when the server supplies one.
    """

    source_id = "sbir"

    def __init__(
        self,
        *,
        archive_url: str = DEFAULT_ARCHIVE_URL,
        max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
        branch_filter: str | None = "navy",
    ) -> None:
        self.archive_url = archive_url
        self.max_download_bytes = max_download_bytes
        self.branch_filter = branch_filter.casefold().strip() if branch_filter else None
        self.exhausted = False

    def _matches_filter(self, row: Mapping[str, Any]) -> bool:
        if not self.branch_filter:
            return True
        agency_and_branch = " ".join(
            str(value or "")
            for value in (
                _value(row, "Agency"),
                _value(row, "Branch"),
                _value(row, "Awarding Agency"),
            )
        ).casefold()
        return self.branch_filter in agency_and_branch

    def _record(
        self,
        raw: Mapping[str, Any],
        request: CollectionRequest,
        source_version: str | None,
    ) -> CanonicalRecord:
        sanitized, report = sanitize_mapping(raw)
        award_id = _value(
            sanitized,
            "Award ID",
            "Award Number",
            "Contract",
            "Contract Number",
        ) or sha256_json(sanitized)[:24]
        title = _value(sanitized, "Award Title", "Title", "Project Title") or str(award_id)
        link = _value(sanitized, "Award Link", "URL", "Award URL")
        state = _value(sanitized, "State", "Company State")
        country = _value(sanitized, "Country", "Company Country")
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(award_id),
            record_type="award",
            title=title,
            abstract=_value(sanitized, "Abstract", "Award Abstract", "Project Abstract"),
            published_date=_value(sanitized, "Award Year", "Year"),
            start_date=_value(sanitized, "Proposal Award Date", "Award Start Date", "Start Date"),
            end_date=_value(sanitized, "Award End Date", "End Date"),
            organizations=[
                _value(sanitized, "Company", "Company Name", "Firm"),
                _value(sanitized, "Agency"),
                _value(sanitized, "Branch"),
                _value(sanitized, "Research Institution"),
            ],
            topics=[
                _value(sanitized, "Program"),
                _value(sanitized, "Phase"),
                _value(sanitized, "Topic Code"),
            ],
            links=[link],
            identifiers={
                "award_id": str(award_id),
                "topic_code": _value(sanitized, "Topic Code"),
            },
            geography={"state": state, "country": country},
            funding_amount=_value(sanitized, "Award Amount", "Amount"),
            funding_currency="USD",
            attributes={
                "agency_tracking_number": _value(sanitized, "Agency Tracking Number"),
                "source_version": source_version,
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=self.archive_url,
            retrieved_at=request.retrieved_at,
            snapshot_id=request.snapshot_id,
            source_payload_sha256=sha256_json(sanitized),
        )

    def collect(
        self,
        http: HttpTransport,
        request: CollectionRequest,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> Iterator[CollectedRecord]:
        self.exhausted = False
        state = dict(checkpoint or {})
        start_index = max(0, int(state.get("row_index", 0)))
        emitted = 0
        with http.open_stream(self.archive_url, max_bytes=self.max_download_bytes) as opened:
            previous_version = state.get("source_version")
            if previous_version and opened.source_version and previous_version != opened.source_version:
                raise RuntimeError(
                    "the SBIR source version changed after collection began; start a fresh snapshot"
                )
            text_stream = io.TextIOWrapper(
                io.BufferedReader(opened.stream),
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            )
            reader = csv.DictReader(text_stream)
            if not reader.fieldnames:
                raise RuntimeError("SBIR archive has no CSV header")
            for index, row in enumerate(reader):
                if index < start_index or not self._matches_filter(row):
                    continue
                if emitted >= request.max_records:
                    return
                emitted += 1
                yield CollectedRecord(
                    record=self._record(row, request, opened.source_version),
                    checkpoint={
                        "row_index": index + 1,
                        "source_version": opened.source_version,
                    },
                )
        self.exhausted = True

"""Crossref Works connector using cursor pagination."""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest, date_parts, first_value


DEFAULT_ENDPOINT = "https://api.crossref.org/works"


def _first_text(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value not in (None, "") else None


class CrossrefConnector:
    source_id = "crossref"

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT, *, mailto: str | None = None) -> None:
        self.endpoint = endpoint
        self.mailto = mailto
        self.exhausted = False

    def _params(self, request: CollectionRequest, cursor: str) -> dict[str, Any]:
        filters: list[str] = []
        if request.from_date:
            filters.append(f"from-pub-date:{request.from_date}")
        if request.to_date:
            filters.append(f"until-pub-date:{request.to_date}")
        return {
            "cursor": cursor,
            "rows": min(request.page_size, 1000),
            "query": request.query,
            "filter": ",".join(filters) if filters else None,
            "mailto": self.mailto,
        }

    def _record(self, raw: Mapping[str, Any], request: CollectionRequest) -> CanonicalRecord:
        sanitized, report = sanitize_mapping(raw)
        doi = first_value(sanitized, "DOI", "doi") or sha256_json(sanitized)[:24]
        institutions: list[str] = []
        for author in sanitized.get("author") or []:
            if not isinstance(author, Mapping):
                continue
            for affiliation in author.get("affiliation") or []:
                if isinstance(affiliation, Mapping) and affiliation.get("name"):
                    institutions.append(str(affiliation["name"]))
        funder_items = [
            item for item in sanitized.get("funder") or [] if isinstance(item, Mapping)
        ]
        funders = [item.get("name") for item in funder_items if item.get("name")]
        funder_ids = sorted(
            {
                str(item.get("DOI") or item.get("doi")).strip()
                for item in funder_items
                if item.get("DOI") or item.get("doi")
            }
        )
        funding_award_ids = sorted(
            {
                str(award).strip()
                for item in funder_items
                for award in item.get("award") or []
                if str(award).strip()
            }
        )
        subjects = [str(item) for item in sanitized.get("subject") or []]
        resource_url = first_value(sanitized, "URL") or f"https://doi.org/{doi}"
        license_urls = sorted(
            {
                str(item.get("URL")).strip()
                for item in sanitized.get("license") or []
                if isinstance(item, Mapping) and item.get("URL")
            }
        )
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(doi).lower(),
            record_type="publication",
            title=_first_text(first_value(sanitized, "title")) or str(doi),
            # Crossref abstracts can contain publisher-supplied text with
            # separate reuse rights. Persist metadata and links, not the text.
            abstract=None,
            published_date=date_parts(
                first_value(sanitized, "published-print", "published-online", "published", "created")
            ),
            organizations=[*institutions, *funders, first_value(sanitized, "publisher")],
            topics=subjects,
            links=[resource_url],
            identifiers={
                "doi": str(doi).lower(),
                "issn": list(sanitized.get("ISSN") or []),
                "funder_ids": funder_ids,
                "funding_award_ids": funding_award_ids,
            },
            attributes={
                "type": first_value(sanitized, "type"),
                "author_count": len(sanitized.get("author") or []),
                "reference_count": first_value(
                    sanitized, "references-count", "reference-count"
                ),
                "citation_count": first_value(sanitized, "is-referenced-by-count"),
                "abstract_available": bool(first_value(sanitized, "abstract")),
                "license_urls": license_urls,
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=self.endpoint,
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
        cursor = str(state.get("cursor", "*"))
        offset = max(0, int(state.get("offset", 0)))
        emitted = 0
        pages_read = 0
        while emitted < request.max_records:
            if pages_read >= request.max_pages:
                raise RuntimeError("Crossref page budget exhausted before the record limit")
            response = http.get_json(self.endpoint, params=self._params(request, cursor))
            pages_read += 1
            message = response.get("message") or {}
            items = list(message.get("items") or [])
            if not items:
                self.exhausted = True
                return
            next_cursor = message.get("next-cursor")
            for index in range(offset, len(items)):
                if emitted >= request.max_records:
                    return
                raw = items[index]
                if not isinstance(raw, Mapping):
                    continue
                emitted += 1
                yield CollectedRecord(
                    record=self._record(raw, request),
                    checkpoint={"cursor": cursor, "offset": index + 1},
                )
            # Crossref can return the same opaque cursor token while advancing
            # server-side scroll state, so cursor equality is not exhaustion.
            if len(items) < min(request.page_size, 1000) or not next_cursor:
                self.exhausted = True
                return
            cursor = str(next_cursor)
            offset = 0

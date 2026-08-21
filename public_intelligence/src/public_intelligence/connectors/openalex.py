"""OpenAlex Works connector using cursor pagination."""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import redact_text, sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest, first_value, inverted_abstract


DEFAULT_ENDPOINT = "https://api.openalex.org/works"


class OpenAlexConnector:
    source_id = "openalex"

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        mailto: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.mailto = mailto
        self.api_key = api_key
        self.exhausted = False

    def _params(self, request: CollectionRequest, cursor: str) -> dict[str, Any]:
        filters: list[str] = []
        if request.from_date:
            filters.append(f"from_publication_date:{request.from_date}")
        if request.to_date:
            filters.append(f"to_publication_date:{request.to_date}")
        return {
            "cursor": cursor,
            "per-page": min(request.page_size, 200),
            "search": request.query,
            "filter": ",".join(filters) if filters else None,
            "mailto": self.mailto,
            "api_key": self.api_key,
        }

    def _record(self, raw: Mapping[str, Any], request: CollectionRequest) -> CanonicalRecord:
        sanitized, report = sanitize_mapping(raw)
        abstract, abstract_redactions = redact_text(
            inverted_abstract(sanitized.get("abstract_inverted_index")) or ""
        )
        openalex_id = first_value(sanitized, "id") or sha256_json(sanitized)[:24]
        institutions: list[str] = []
        authorships = sanitized.get("authorships") or []
        for authorship in authorships:
            if not isinstance(authorship, Mapping):
                continue
            for institution in authorship.get("institutions") or []:
                if isinstance(institution, Mapping) and institution.get("display_name"):
                    institutions.append(str(institution["display_name"]))
        concepts = [
            concept.get("display_name")
            for concept in sanitized.get("concepts") or []
            if isinstance(concept, Mapping) and concept.get("display_name")
        ]
        topics = [
            topic.get("display_name")
            for topic in sanitized.get("topics") or []
            if isinstance(topic, Mapping) and topic.get("display_name")
        ]
        ids = sanitized.get("ids") if isinstance(sanitized.get("ids"), Mapping) else {}
        doi = first_value(ids, "doi") if isinstance(ids, Mapping) else None
        awards = [
            item for item in sanitized.get("awards") or [] if isinstance(item, Mapping)
        ]
        funding_award_ids = sorted(
            {
                str(item.get("funder_award_id")).strip()
                for item in awards
                if item.get("funder_award_id")
            }
        )
        funder_ids = sorted(
            {
                str(item.get("funder_id")).strip()
                for item in awards
                if item.get("funder_id")
            }
        )
        primary_location = sanitized.get("primary_location")
        primary_url = None
        if isinstance(primary_location, Mapping):
            primary_url = first_value(primary_location, "landing_page_url", "pdf_url")
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(openalex_id).rsplit("/", 1)[-1],
            record_type="publication",
            title=first_value(sanitized, "display_name", "title") or str(openalex_id),
            abstract=abstract or None,
            published_date=first_value(sanitized, "publication_date"),
            organizations=institutions,
            topics=[*topics, *concepts],
            links=[primary_url, first_value(sanitized, "id"), doi],
            identifiers={
                "openalex": openalex_id,
                "doi": doi,
                "funder_ids": funder_ids,
                "funding_award_ids": funding_award_ids,
            },
            attributes={
                "type": first_value(sanitized, "type"),
                "author_count": len(authorships),
                "citation_count": first_value(sanitized, "cited_by_count"),
                "open_access_status": (sanitized.get("open_access") or {}).get(
                    "oa_status"
                )
                if isinstance(sanitized.get("open_access"), Mapping)
                else None,
                "is_open_access": (sanitized.get("open_access") or {}).get("is_oa")
                if isinstance(sanitized.get("open_access"), Mapping)
                else None,
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values + abstract_redactions,
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
                raise RuntimeError("OpenAlex page budget exhausted before the record limit")
            response = http.get_json(self.endpoint, params=self._params(request, cursor))
            pages_read += 1
            results = list(response.get("results") or [])
            if not results:
                self.exhausted = True
                return
            next_cursor = (response.get("meta") or {}).get("next_cursor")
            for index in range(offset, len(results)):
                if emitted >= request.max_records:
                    return
                raw = results[index]
                if not isinstance(raw, Mapping):
                    continue
                emitted += 1
                yield CollectedRecord(
                    record=self._record(raw, request),
                    checkpoint={"cursor": cursor, "offset": index + 1},
                )
            if len(results) < min(request.page_size, 200) or not next_cursor or next_cursor == cursor:
                self.exhausted = True
                return
            cursor = str(next_cursor)
            offset = 0

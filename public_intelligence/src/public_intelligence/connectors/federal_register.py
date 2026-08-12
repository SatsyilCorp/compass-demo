"""Federal Register connector for public Navy and ONR notices."""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import sanitize_mapping
from ..provenance import sha256_json
from .base import (
    CollectedRecord,
    CollectionRequest,
    first_value,
    normalize_public_date,
    plain_text,
)


DEFAULT_SEARCH_ENDPOINT = "https://www.federalregister.gov/api/v1/documents.json"
DEFAULT_DETAIL_ENDPOINT = "https://www.federalregister.gov/api/v1/documents"
DEFAULT_AGENCY = "navy-department"
DEFAULT_TERM = '"Office of Naval Research"'


def _strings(values: Any, *keys: str) -> list[str]:
    output: list[str] = []
    for value in values or []:
        if isinstance(value, Mapping):
            item = first_value(value, *keys)
        else:
            item = value
        if item not in (None, ""):
            output.append(str(item))
    return output


def _cfr_references(values: Any) -> list[str]:
    references: list[str] = []
    for value in values or []:
        if not isinstance(value, Mapping):
            continue
        title = first_value(value, "title")
        part = first_value(value, "part")
        if title not in (None, "") and part not in (None, ""):
            references.append(f"{title} CFR {part}")
    return references


class FederalRegisterConnector:
    """Collect Navy Federal Register metadata without downloading document bodies."""

    source_id = "federal_register"

    def __init__(
        self,
        search_endpoint: str = DEFAULT_SEARCH_ENDPOINT,
        detail_endpoint: str = DEFAULT_DETAIL_ENDPOINT,
        *,
        agency: str = DEFAULT_AGENCY,
        term: str = DEFAULT_TERM,
        fetch_details: bool = True,
    ) -> None:
        if not agency.strip():
            raise ValueError("a Federal Register agency slug is required")
        if not term.strip():
            raise ValueError("a Federal Register search term is required")
        self.search_endpoint = search_endpoint
        self.detail_endpoint = detail_endpoint.rstrip("/")
        self.agency = agency.strip()
        self.term = term.strip()
        self.fetch_details = fetch_details
        self.exhausted = False

    def _params(self, request: CollectionRequest, page: int) -> dict[str, Any]:
        return {
            "per_page": min(request.page_size, 1000),
            "page": page,
            "order": "oldest",
            "conditions[agencies][]": self.agency,
            "conditions[term]": request.query or self.term,
            "conditions[publication_date][gte]": request.from_date,
            "conditions[publication_date][lte]": request.to_date,
        }

    @staticmethod
    def _unwrap(response: Any, operation: str) -> Mapping[str, Any]:
        if not isinstance(response, Mapping):
            raise RuntimeError(
                f"Federal Register {operation} returned an invalid response"
            )
        return response

    def _detail(self, http: HttpTransport, hit: Mapping[str, Any]) -> Mapping[str, Any]:
        document_number = first_value(hit, "document_number")
        if not self.fetch_details or document_number in (None, ""):
            return {}
        response = http.get_json(f"{self.detail_endpoint}/{document_number}.json")
        return self._unwrap(response, "document detail")

    @staticmethod
    def _matches_date_range(
        hit: Mapping[str, Any],
        detail: Mapping[str, Any],
        request: CollectionRequest,
    ) -> bool:
        published = normalize_public_date(
            first_value(detail, "publication_date")
            or first_value(hit, "publication_date")
        )
        if published and request.from_date and published < request.from_date:
            return False
        if published and request.to_date and published > request.to_date:
            return False
        return True

    def _record(
        self,
        hit: Mapping[str, Any],
        detail: Mapping[str, Any],
        request: CollectionRequest,
    ) -> CanonicalRecord:
        combined = {**hit, **detail}
        sanitized, report = sanitize_mapping(combined)
        document_number = (
            first_value(sanitized, "document_number") or sha256_json(sanitized)[:24]
        )
        agencies = _strings(sanitized.get("agencies"), "name", "raw_name", "slug")
        agency_slugs = _strings(sanitized.get("agencies"), "slug")
        if agency_slugs and self.agency.casefold() not in {
            value.casefold() for value in agency_slugs
        }:
            raise RuntimeError(
                "Federal Register returned a record outside the requested agency scope"
            )

        document_type = first_value(sanitized, "type")
        subtype = first_value(sanitized, "subtype")
        topics = _strings(sanitized.get("topics"), "name", "title")
        docket_ids = _strings(sanitized.get("docket_ids"))
        regulation_ids = _strings(sanitized.get("regulation_id_numbers"))
        cfr_references = _cfr_references(sanitized.get("cfr_references"))
        published_date = normalize_public_date(
            first_value(sanitized, "publication_date")
        )
        comments_close_on = normalize_public_date(
            first_value(sanitized, "comments_close_on")
        )
        effective_on = normalize_public_date(first_value(sanitized, "effective_on"))
        html_url = first_value(sanitized, "html_url")
        pdf_url = first_value(sanitized, "pdf_url")
        regulations_url = first_value(sanitized, "regulations_dot_gov_url")
        json_url = first_value(sanitized, "json_url")

        safe_payload = {
            "document_number": document_number,
            "title": plain_text(first_value(sanitized, "title")),
            "abstract": plain_text(first_value(sanitized, "abstract")),
            "publication_date": published_date,
            "comments_close_on": comments_close_on,
            "effective_on": effective_on,
            "agencies": agencies,
            "agency_slugs": agency_slugs,
            "document_type": document_type,
            "subtype": subtype,
            "topics": topics,
            "docket_ids": docket_ids,
            "regulation_id_numbers": regulation_ids,
            "cfr_references": cfr_references,
            "citation": first_value(sanitized, "citation"),
            "action": plain_text(first_value(sanitized, "action")),
            "volume": first_value(sanitized, "volume"),
            "start_page": first_value(sanitized, "start_page"),
            "end_page": first_value(sanitized, "end_page"),
            "page_length": first_value(sanitized, "page_length"),
            "significant": first_value(sanitized, "significant"),
            "html_url": html_url,
            "pdf_url": pdf_url,
            "regulations_url": regulations_url,
            "json_url": json_url,
        }
        safe_payload, safe_report = sanitize_mapping(safe_payload)
        report = report.add(safe_report)

        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(document_number),
            record_type="regulatory_notice",
            title=first_value(safe_payload, "title") or str(document_number),
            abstract=first_value(safe_payload, "abstract"),
            published_date=published_date,
            end_date=comments_close_on or effective_on,
            organizations=safe_payload.get("agencies") or [],
            topics=[document_type, subtype, *(safe_payload.get("topics") or [])],
            links=[html_url, pdf_url, regulations_url],
            identifiers={
                "federal_register_document_number": document_number,
                "citation": safe_payload.get("citation"),
                "docket_ids": safe_payload.get("docket_ids") or [],
                "regulation_id_numbers": safe_payload.get("regulation_id_numbers")
                or [],
                "cfr_references": safe_payload.get("cfr_references") or [],
            },
            attributes={
                "document_type": document_type,
                "subtype": subtype,
                "action": safe_payload.get("action"),
                "comments_close_on": comments_close_on,
                "effective_on": effective_on,
                "volume": safe_payload.get("volume"),
                "start_page": safe_payload.get("start_page"),
                "end_page": safe_payload.get("end_page"),
                "page_length": safe_payload.get("page_length"),
                "significant": safe_payload.get("significant"),
                "agency_scope": self.agency,
                "query_scope": request.query or self.term,
                "detail_fetched": bool(detail),
                "content_collected": False,
                "rights_note": (
                    "Federal Register metadata and U.S. government work. "
                    "Use the linked GovInfo PDF for legal reliance."
                ),
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=str(json_url or html_url or self.search_endpoint),
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
        state = dict(checkpoint or {})
        page = max(1, int(state.get("page", 1)))
        offset = max(0, int(state.get("offset", 0)))
        emitted = 0
        pages_read = 0
        page_size = min(request.page_size, 1000)

        while emitted < request.max_records:
            if pages_read >= request.max_pages:
                raise RuntimeError(
                    "Federal Register page budget exhausted before the record limit"
                )
            response = self._unwrap(
                http.get_json(self.search_endpoint, params=self._params(request, page)),
                "document search",
            )
            pages_read += 1
            results = response.get("results")
            if not isinstance(results, list):
                raise RuntimeError("Federal Register search omitted results")
            if not results:
                self.exhausted = True
                return

            for index in range(offset, len(results)):
                if emitted >= request.max_records:
                    return
                hit = results[index]
                if not isinstance(hit, Mapping):
                    continue
                detail = self._detail(http, hit)
                if not self._matches_date_range(hit, detail, request):
                    continue
                emitted += 1
                yield CollectedRecord(
                    record=self._record(hit, detail, request),
                    checkpoint={"page": page, "offset": index + 1},
                )

            total_pages = response.get("total_pages")
            try:
                final_page = page >= int(total_pages)
            except (TypeError, ValueError):
                final_page = (
                    not response.get("next_page_url") or len(results) < page_size
                )
            if final_page or not response.get("next_page_url"):
                self.exhausted = True
                return
            page += 1
            offset = 0

"""Grants.gov opportunity search and detail connector for public ONR notices."""

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


DEFAULT_SEARCH_ENDPOINT = "https://api.grants.gov/v1/api/search2"
DEFAULT_DETAIL_ENDPOINT = "https://api.grants.gov/v1/api/fetchOpportunity"
DEFAULT_AGENCY = "DOD-ONR"
DEFAULT_STATUSES = "forecasted|posted|closed|archived"


def _descriptions(values: Any) -> list[str]:
    descriptions: list[str] = []
    for value in values or []:
        if isinstance(value, Mapping):
            text = first_value(value, "description", "programTitle", "label", "id")
        else:
            text = value
        if text not in (None, ""):
            descriptions.append(str(text))
    return descriptions


def _identifiers(values: Any, *keys: str) -> list[str]:
    identifiers: list[str] = []
    for value in values or []:
        if isinstance(value, Mapping):
            item = first_value(value, *keys)
        else:
            item = value
        if item not in (None, ""):
            identifiers.append(str(item))
    return identifiers


class GrantsGovConnector:
    """Collect public DOD-ONR opportunities with contact data removed."""

    source_id = "grants_gov"

    def __init__(
        self,
        search_endpoint: str = DEFAULT_SEARCH_ENDPOINT,
        detail_endpoint: str = DEFAULT_DETAIL_ENDPOINT,
        *,
        agency: str = DEFAULT_AGENCY,
        fetch_details: bool = True,
    ) -> None:
        if not agency.strip():
            raise ValueError("a Grants.gov agency code is required")
        self.search_endpoint = search_endpoint
        self.detail_endpoint = detail_endpoint
        self.agency = agency.strip()
        self.fetch_details = fetch_details
        self.exhausted = False

    def _body(self, request: CollectionRequest, start_record: int) -> dict[str, Any]:
        return {
            "rows": min(request.page_size, 1000),
            "keyword": request.query or "",
            "oppNum": "",
            "eligibilities": "",
            "agencies": self.agency,
            "oppStatuses": DEFAULT_STATUSES,
            "aln": "",
            "fundingCategories": "",
            "sortBy": "openDate|asc",
            "startRecordNum": start_record,
        }

    @staticmethod
    def _unwrap(response: Any, operation: str) -> Mapping[str, Any]:
        if not isinstance(response, Mapping):
            raise RuntimeError(f"Grants.gov {operation} returned an invalid response")
        error_code = response.get("errorcode")
        if error_code not in (None, 0, "0"):
            message = response.get("msg") or "unknown API error"
            raise RuntimeError(f"Grants.gov {operation} failed: {message}")
        data = response.get("data")
        if not isinstance(data, Mapping):
            raise RuntimeError(f"Grants.gov {operation} omitted response data")
        errors = data.get("errorMsgs")
        if errors:
            raise RuntimeError(f"Grants.gov {operation} reported errors: {errors}")
        return data

    def _detail(self, http: HttpTransport, hit: Mapping[str, Any]) -> Mapping[str, Any]:
        opportunity_id = first_value(hit, "id", "opportunityId")
        if not self.fetch_details or opportunity_id in (None, ""):
            return {}
        try:
            normalized_id: str | int = int(str(opportunity_id))
        except ValueError:
            normalized_id = str(opportunity_id)
        response = http.post_json(
            self.detail_endpoint,
            {"opportunityId": normalized_id},
        )
        return self._unwrap(response, "fetchOpportunity")

    def _matches_date_range(
        self,
        hit: Mapping[str, Any],
        detail: Mapping[str, Any],
        request: CollectionRequest,
    ) -> bool:
        synopsis = detail.get("synopsis") if isinstance(detail.get("synopsis"), Mapping) else {}
        forecast = detail.get("forecast") if isinstance(detail.get("forecast"), Mapping) else {}
        published = normalize_public_date(
            first_value(
                synopsis,
                "postingDateStr",
                "postingDate",
                "createTimeStampStr",
                "createdDate",
            )
            or first_value(forecast, "postingDateStr", "postingDate")
            or first_value(hit, "openDate")
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
        sanitized_hit, hit_report = sanitize_mapping(hit)
        sanitized_detail, detail_report = sanitize_mapping(detail)
        report = hit_report.add(detail_report)

        synopsis = (
            sanitized_detail.get("synopsis")
            if isinstance(sanitized_detail.get("synopsis"), Mapping)
            else {}
        )
        forecast = (
            sanitized_detail.get("forecast")
            if isinstance(sanitized_detail.get("forecast"), Mapping)
            else {}
        )
        agency_details = (
            sanitized_detail.get("agencyDetails")
            if isinstance(sanitized_detail.get("agencyDetails"), Mapping)
            else {}
        )
        top_agency_details = (
            sanitized_detail.get("topAgencyDetails")
            if isinstance(sanitized_detail.get("topAgencyDetails"), Mapping)
            else {}
        )
        opportunity_id = first_value(sanitized_detail, "id") or first_value(
            sanitized_hit, "id", "opportunityId"
        )
        opportunity_number = first_value(
            sanitized_detail, "opportunityNumber"
        ) or first_value(sanitized_hit, "number", "opportunityNumber")
        source_record_id = opportunity_number or opportunity_id or sha256_json(sanitized_hit)[:24]
        agency_code = first_value(
            sanitized_detail, "owningAgencyCode"
        ) or first_value(sanitized_hit, "agencyCode")
        if agency_code and str(agency_code).casefold() != self.agency.casefold():
            raise RuntimeError(
                f"Grants.gov returned agency {agency_code} outside requested scope {self.agency}"
            )

        alns = sanitized_detail.get("alns") or sanitized_detail.get("cfdas") or []
        if not alns:
            alns = sanitized_hit.get("alnist") or sanitized_hit.get("cfdaList") or []
        aln_numbers = _identifiers(alns, "alnNumber", "cfdaNumber", "number", "id")
        program_titles = _descriptions(alns)
        instruments = _descriptions(
            synopsis.get("fundingInstruments") or forecast.get("fundingInstruments")
        )
        activity_categories = _descriptions(
            synopsis.get("fundingActivityCategories")
            or forecast.get("fundingActivityCategories")
        )
        applicant_types = _descriptions(
            synopsis.get("applicantTypes") or forecast.get("applicantTypes")
        )
        published_date = normalize_public_date(
            first_value(
                synopsis,
                "postingDateStr",
                "postingDate",
                "createTimeStampStr",
                "createdDate",
            )
            or first_value(forecast, "postingDateStr", "postingDate")
            or first_value(sanitized_hit, "openDate")
        )
        close_date = normalize_public_date(
            first_value(synopsis, "responseDateStr", "responseDate")
            or first_value(forecast, "responseDateStr", "responseDate")
            or first_value(sanitized_hit, "closeDate")
        )
        abstract = plain_text(
            first_value(synopsis, "synopsisDesc")
            or first_value(forecast, "forecastDesc", "synopsisDesc")
        )
        agency_names = [
            first_value(agency_details, "agencyName"),
            first_value(top_agency_details, "agencyName"),
            first_value(synopsis, "agencyName"),
            first_value(sanitized_hit, "agency", "agencyName"),
        ]
        detail_page = (
            f"https://www.grants.gov/search-results-detail/{opportunity_id}"
            if opportunity_id not in (None, "")
            else None
        )
        funding_url = first_value(
            synopsis, "fundingDescLinkUrl"
        ) or first_value(forecast, "fundingDescLinkUrl")
        attachment_count = sum(
            len(folder.get("synopsisAttachments") or [])
            for folder in sanitized_detail.get("synopsisAttachmentFolders") or []
            if isinstance(folder, Mapping)
        )
        related_count = len(sanitized_detail.get("relatedOpps") or [])
        opportunity_category = sanitized_detail.get("opportunityCategory")
        if isinstance(opportunity_category, Mapping):
            opportunity_category = first_value(opportunity_category, "description", "category")

        safe_payload = {
            "id": opportunity_id,
            "opportunity_number": opportunity_number,
            "title": first_value(sanitized_detail, "opportunityTitle")
            or first_value(sanitized_hit, "title"),
            "owning_agency_code": agency_code,
            "agency_names": agency_names,
            "opportunity_status": first_value(sanitized_hit, "oppStatus"),
            "document_type": first_value(sanitized_detail, "docType")
            or first_value(sanitized_hit, "docType"),
            "published_date": published_date,
            "close_date": close_date,
            "synopsis": abstract,
            "aln_numbers": aln_numbers,
            "program_titles": program_titles,
            "funding_instruments": instruments,
            "funding_activity_categories": activity_categories,
            "applicant_types": applicant_types,
            "cost_sharing": first_value(synopsis, "costSharing")
            if first_value(synopsis, "costSharing") is not None
            else first_value(forecast, "costSharing"),
            "award_floor": first_value(synopsis, "awardFloor")
            or first_value(forecast, "awardFloor"),
            "award_ceiling": first_value(synopsis, "awardCeiling")
            or first_value(forecast, "awardCeiling"),
            "opportunity_category": opportunity_category,
            "funding_url": funding_url,
            "attachment_count": attachment_count,
            "related_opportunity_count": related_count,
        }
        safe_payload, safe_report = sanitize_mapping(safe_payload)
        report = report.add(safe_report)
        agency_names = list(safe_payload.get("agency_names") or [])
        program_titles = list(safe_payload.get("program_titles") or [])
        activity_categories = list(safe_payload.get("funding_activity_categories") or [])
        instruments = list(safe_payload.get("funding_instruments") or [])
        applicant_types = list(safe_payload.get("applicant_types") or [])
        aln_numbers = list(safe_payload.get("aln_numbers") or [])
        funding_url = safe_payload.get("funding_url")
        opportunity_category = safe_payload.get("opportunity_category")

        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(source_record_id),
            record_type="solicitation",
            title=first_value(safe_payload, "title") or str(source_record_id),
            abstract=first_value(safe_payload, "synopsis"),
            published_date=published_date,
            start_date=published_date,
            end_date=close_date,
            organizations=agency_names,
            topics=[
                *program_titles,
                *activity_categories,
                *instruments,
                first_value(sanitized_hit, "oppStatus"),
            ],
            links=[detail_page, funding_url],
            identifiers={
                "opportunity_id": str(opportunity_id) if opportunity_id is not None else None,
                "opportunity_number": str(opportunity_number)
                if opportunity_number is not None
                else None,
                "aln": aln_numbers,
            },
            attributes={
                "agency_scope": self.agency,
                "opportunity_status": first_value(safe_payload, "opportunity_status"),
                "document_type": first_value(safe_payload, "document_type"),
                "opportunity_category": opportunity_category,
                "funding_instruments": instruments,
                "funding_activity_categories": activity_categories,
                "applicant_types": applicant_types,
                "cost_sharing": safe_payload.get("cost_sharing"),
                "award_floor": safe_payload.get("award_floor"),
                "award_ceiling": safe_payload.get("award_ceiling"),
                "attachment_count": attachment_count,
                "related_opportunity_count": related_count,
                "detail_fetched": bool(sanitized_detail),
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=self.detail_endpoint if sanitized_detail else self.search_endpoint,
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
        start_record = max(0, int(state.get("start_record", 0)))
        offset = max(0, int(state.get("offset", 0)))
        emitted = 0
        pages_read = 0

        while emitted < request.max_records:
            if pages_read >= request.max_pages:
                raise RuntimeError("Grants.gov page budget exhausted before the record limit")
            response = http.post_json(self.search_endpoint, self._body(request, start_record))
            data = self._unwrap(response, "search2")
            pages_read += 1
            hits = list(data.get("oppHits") or [])
            if not hits:
                self.exhausted = True
                return
            for index in range(offset, len(hits)):
                if emitted >= request.max_records:
                    return
                hit = hits[index]
                if not isinstance(hit, Mapping):
                    continue
                if not self._matches_date_range(hit, {}, request):
                    continue
                detail = self._detail(http, hit)
                if not self._matches_date_range(hit, detail, request):
                    continue
                emitted += 1
                yield CollectedRecord(
                    record=self._record(hit, detail, request),
                    checkpoint={"start_record": start_record, "offset": index + 1},
                )
            hit_count = int(data.get("hitCount") or 0)
            next_start = start_record + len(hits)
            if next_start >= hit_count or len(hits) < min(request.page_size, 1000):
                self.exhausted = True
                return
            start_record = next_start
            offset = 0

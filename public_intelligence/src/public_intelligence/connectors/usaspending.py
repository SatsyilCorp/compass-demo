"""USAspending Advanced Award Search connector."""

from __future__ import annotations

from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest, first_value


DEFAULT_ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DEFAULT_AWARD_TYPES = (
    "A",
    "B",
    "C",
    "D",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
)
FIELDS = (
    "Award ID",
    "Recipient Name",
    "Start Date",
    "End Date",
    "Award Amount",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Funding Agency",
    "Funding Sub Agency",
    "Award Type",
    "Description",
    "CFDA Number",
)


class UsaSpendingConnector:
    source_id = "usaspending"

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT) -> None:
        self.endpoint = endpoint
        self.exhausted = False

    def _body(self, request: CollectionRequest, page: int) -> dict[str, Any]:
        filters: dict[str, Any] = {
            "award_type_codes": list(request.options.get("award_types") or DEFAULT_AWARD_TYPES),
        }
        if request.from_date and request.to_date:
            filters["time_period"] = [
                {"start_date": request.from_date, "end_date": request.to_date}
            ]
        agencies = request.options.get("agencies")
        if agencies:
            filters["agencies"] = list(agencies)
        if request.query:
            filters["keywords"] = [request.query]
        return {
            "filters": filters,
            "fields": list(FIELDS),
            "page": page,
            "limit": min(request.page_size, 100),
            "sort": "Award ID",
            "order": "asc",
            "subawards": False,
        }

    def _record(
        self,
        raw: Mapping[str, Any],
        request: CollectionRequest,
    ) -> CanonicalRecord:
        sanitized, pii_report = sanitize_mapping(raw)
        record_id = first_value(
            sanitized,
            "Award ID",
            "generated_internal_id",
            "internal_id",
        ) or sha256_json(sanitized)[:24]
        internal_id = first_value(sanitized, "generated_internal_id", "internal_id")
        link = f"https://www.usaspending.gov/award/{internal_id}" if internal_id else None
        organizations = [
            first_value(sanitized, "Recipient Name"),
            first_value(sanitized, "Awarding Agency"),
            first_value(sanitized, "Awarding Sub Agency"),
            first_value(sanitized, "Funding Agency"),
            first_value(sanitized, "Funding Sub Agency"),
        ]
        topics = [
            first_value(sanitized, "Award Type"),
            first_value(sanitized, "CFDA Number"),
        ]
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(record_id),
            record_type="award",
            title=first_value(sanitized, "Description", "Award ID") or str(record_id),
            abstract=first_value(sanitized, "Description"),
            start_date=first_value(sanitized, "Start Date"),
            end_date=first_value(sanitized, "End Date"),
            organizations=organizations,
            topics=topics,
            links=[link],
            identifiers={"award_id": str(record_id)},
            funding_amount=first_value(sanitized, "Award Amount"),
            funding_currency="USD",
            attributes={
                "award_type": first_value(sanitized, "Award Type"),
                "pii_dropped_fields": pii_report.dropped_fields,
                "pii_redacted_values": pii_report.redacted_values,
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
        page = max(1, int(state.get("page", 1)))
        offset = max(0, int(state.get("offset", 0)))
        emitted = 0
        pages_read = 0
        while emitted < request.max_records:
            if pages_read >= request.max_pages:
                raise RuntimeError("USAspending page budget exhausted before the record limit")
            response = http.post_json(self.endpoint, self._body(request, page))
            pages_read += 1
            results = list(response.get("results") or [])
            if not results:
                self.exhausted = True
                return
            for index in range(offset, len(results)):
                if emitted >= request.max_records:
                    return
                raw = results[index]
                if not isinstance(raw, Mapping):
                    continue
                emitted += 1
                yield CollectedRecord(
                    record=self._record(raw, request),
                    checkpoint={"page": page, "offset": index + 1},
                )
            has_next = bool((response.get("page_metadata") or {}).get("hasNext"))
            if not has_next:
                self.exhausted = True
                return
            page += 1
            offset = 0

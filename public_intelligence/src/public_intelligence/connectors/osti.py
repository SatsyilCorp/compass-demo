"""OSTI.GOV connector for records sponsored by the Office of Naval Research."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest, first_value, normalize_public_date


DEFAULT_ENDPOINT = "https://www.osti.gov/api/v1/records"
DEFAULT_SPONSOR = "Office of Naval Research"
DATASET_TYPES = {"dataset", "software", "computer program", "data"}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _https_links(raw: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for link in _list(raw.get("links")):
        if isinstance(link, Mapping):
            candidate = first_value(link, "href")
        else:
            candidate = link
        if str(candidate or "").startswith("https://"):
            values.append(str(candidate))
    return values


def _date_parameter(value: str | None) -> str | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")


class OstiConnector:
    """Collect public OSTI metadata with exact sponsor-organization filtering."""

    source_id = "osti"

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        sponsor_org: str = DEFAULT_SPONSOR,
    ) -> None:
        if not sponsor_org.strip():
            raise ValueError("sponsor_org is required")
        self.endpoint = endpoint
        self.sponsor_org = sponsor_org.strip()
        self.exhausted = False

    def _params(self, request: CollectionRequest, page: int) -> dict[str, Any]:
        return {
            "sponsor_org": self.sponsor_org,
            "q": request.query,
            "publication_date_start": _date_parameter(request.from_date),
            "publication_date_end": _date_parameter(request.to_date),
            "page": page,
            "rows": min(request.page_size, 1000),
        }

    def _matches_date_range(
        self, raw: Mapping[str, Any], request: CollectionRequest
    ) -> bool:
        published = normalize_public_date(first_value(raw, "publication_date"))
        if published and request.from_date and published < request.from_date:
            return False
        if published and request.to_date and published > request.to_date:
            return False
        return True

    def _record(
        self, raw: Mapping[str, Any], request: CollectionRequest
    ) -> CanonicalRecord:
        osti_id = str(first_value(raw, "osti_id") or sha256_json(raw)[:24])
        title = first_value(raw, "title") or f"OSTI {osti_id}"
        product_type = str(first_value(raw, "product_type") or "publication")
        links = _https_links(raw)
        citation_url = f"https://www.osti.gov/biblio/{osti_id}"
        doi = first_value(raw, "doi")
        contracts = [
            value
            for key in (
                "contract_number",
                "doe_contract_number",
                "nondoe_contract_number",
                "identifier",
            )
            if (value := first_value(raw, key))
        ]
        safe_payload = {
            "osti_id": osti_id,
            "title": title,
            "publication_date": normalize_public_date(
                first_value(raw, "publication_date")
            ),
            "entry_date": normalize_public_date(first_value(raw, "entry_date")),
            "doi": doi,
            "product_type": product_type,
            "article_type": first_value(raw, "article_type"),
            "journal_name": first_value(raw, "journal_name"),
            "journal_volume": first_value(raw, "journal_volume"),
            "journal_issue": first_value(raw, "journal_issue"),
            "publisher": first_value(raw, "publisher"),
            "language": first_value(raw, "language"),
            "country_publication": first_value(raw, "country_publication"),
            "report_number": first_value(raw, "report_number"),
            "contracts": contracts,
            "sponsor_orgs": _list(raw.get("sponsor_orgs")),
            "research_orgs": _list(raw.get("research_orgs")),
            "subjects": _list(raw.get("subjects")),
            "links": links,
            "author_count": len(_list(raw.get("authors"))),
            "description_available": bool(first_value(raw, "description")),
            "description_omitted_for_rights_review": True,
            "sponsor_scope": self.sponsor_org,
        }
        safe_payload, report = sanitize_mapping(safe_payload)
        record_type = (
            "dataset"
            if product_type.casefold() in DATASET_TYPES
            else "publication"
        )
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=osti_id,
            record_type=record_type,
            title=str(safe_payload["title"]),
            published_date=safe_payload.get("publication_date"),
            organizations=[
                *safe_payload.get("sponsor_orgs", []),
                *safe_payload.get("research_orgs", []),
                safe_payload.get("journal_name"),
                safe_payload.get("publisher"),
            ],
            topics=safe_payload.get("subjects", []),
            links=[citation_url, *safe_payload.get("links", [])],
            identifiers={
                "osti_id": osti_id,
                "doi": doi,
                "report_number": safe_payload.get("report_number"),
                "contract_numbers": safe_payload.get("contracts", []),
            },
            attributes={
                "product_type": product_type,
                "article_type": safe_payload.get("article_type"),
                "journal_volume": safe_payload.get("journal_volume"),
                "journal_issue": safe_payload.get("journal_issue"),
                "language": safe_payload.get("language"),
                "country_publication": safe_payload.get("country_publication"),
                "entry_date": safe_payload.get("entry_date"),
                "author_count": safe_payload.get("author_count", 0),
                "researcher_identities_omitted": safe_payload.get("author_count", 0),
                "description_available": safe_payload.get("description_available", False),
                "description_omitted_for_rights_review": True,
                "sponsor_scope": self.sponsor_org,
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=citation_url,
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
        while emitted < request.max_records:
            if pages_read >= request.max_pages:
                raise RuntimeError("OSTI page budget exhausted before the record limit")
            response = http.get_json(self.endpoint, params=self._params(request, page))
            pages_read += 1
            if not isinstance(response, list):
                raise RuntimeError("OSTI returned an invalid response")
            records = [item for item in response if isinstance(item, Mapping)]
            if not records:
                self.exhausted = True
                return
            for index in range(offset, len(records)):
                if emitted >= request.max_records:
                    return
                raw = records[index]
                if not self._matches_date_range(raw, request):
                    continue
                yield CollectedRecord(
                    record=self._record(raw, request),
                    checkpoint={"page": page, "offset": index + 1},
                )
                emitted += 1
            if len(records) < min(request.page_size, 1000):
                self.exhausted = True
                return
            page += 1
            offset = 0

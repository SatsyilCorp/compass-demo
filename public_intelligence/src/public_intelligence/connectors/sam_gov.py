"""SAM.gov connector for public ONR contract opportunities."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest, first_value, normalize_public_date


DEFAULT_ENDPOINT = "https://api.sam.gov/opportunities/v2/search"
DEFAULT_ORGANIZATION_CODE = "017.1700.ONR"
DEFAULT_ORGANIZATION_NAME = "OFFICE OF NAVAL RESEARCH"
MAX_WINDOW_DAYS = 365


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return " ".join(str(value).replace("\u2014", " - ").split()) or None


def _date_windows(from_date: str, to_date: str) -> list[tuple[str, str]]:
    """Split an inclusive interval into API-safe windows of at most 365 days."""

    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    if start > end:
        raise ValueError("from_date cannot be after to_date")
    windows: list[tuple[str, str]] = []
    while start <= end:
        stop = min(end, start + timedelta(days=MAX_WINDOW_DAYS - 1))
        windows.append((start.strftime("%m/%d/%Y"), stop.strftime("%m/%d/%Y")))
        start = stop + timedelta(days=1)
    return windows


def _path_in_scope(path_code: Any, organization_code: str) -> bool:
    path = str(path_code or "").strip().casefold()
    scope = organization_code.strip().casefold()
    return bool(path and (path == scope or path.startswith(f"{scope}.")))


class SamGovConnector:
    """Collect public SAM.gov notices under the ONR organization hierarchy.

    The public API key is used only in memory. Canonical records omit contacts,
    description bodies, attachment URLs, street addresses, and API self links.
    """

    source_id = "sam_gov"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        organization_code: str = DEFAULT_ORGANIZATION_CODE,
        organization_name: str = DEFAULT_ORGANIZATION_NAME,
    ) -> None:
        if not api_key.strip():
            raise ValueError("SAM_GOV_API_KEY is required")
        if not organization_code.strip():
            raise ValueError("a SAM.gov organization code is required")
        if not organization_name.strip():
            raise ValueError("a SAM.gov organization name is required")
        self.api_key = api_key.strip()
        self.endpoint = endpoint
        self.organization_code = organization_code.strip()
        self.organization_name = organization_name.strip()
        self.exhausted = False

    def _params(
        self,
        request: CollectionRequest,
        posted_from: str,
        posted_to: str,
        offset: int,
    ) -> dict[str, Any]:
        return {
            "api_key": self.api_key,
            "organizationCode": self.organization_code,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "limit": min(request.page_size, 1000),
            "offset": offset,
            "title": request.query,
        }

    @staticmethod
    def _unwrap(response: Any) -> Mapping[str, Any]:
        if not isinstance(response, Mapping):
            raise RuntimeError(
                "SAM.gov opportunity search returned an invalid response"
            )
        opportunities = response.get("opportunitiesData")
        if opportunities is not None and not isinstance(opportunities, list):
            raise RuntimeError("SAM.gov opportunity search omitted opportunitiesData")
        return response

    def _record(
        self,
        raw: Mapping[str, Any],
        request: CollectionRequest,
    ) -> CanonicalRecord:
        path_code = first_value(raw, "fullParentPathCode")
        if not _path_in_scope(path_code, self.organization_code):
            raise RuntimeError(
                "SAM.gov returned a record outside the requested organization scope"
            )

        notice_id = str(first_value(raw, "noticeId") or sha256_json(raw)[:24])
        award = _mapping(raw.get("award"))
        awardee = _mapping(award.get("awardee"))
        place = _mapping(raw.get("placeOfPerformance"))
        city = _mapping(place.get("city"))
        state = _mapping(place.get("state"))
        country = _mapping(place.get("country"))
        opportunity_type = _text(first_value(raw, "type"))
        base_type = _text(first_value(raw, "baseType"))
        organization_path = _text(first_value(raw, "fullParentPathName"))
        posted_date = normalize_public_date(first_value(raw, "postedDate"))
        response_deadline = normalize_public_date(
            first_value(raw, "responseDeadLine", "reponseDeadLine")
        )
        award_date = normalize_public_date(first_value(award, "date"))
        solicitation_number = _text(first_value(raw, "solicitationNumber"))
        canonical_url = f"https://sam.gov/opp/{notice_id}/view"
        contacts = _list(raw.get("pointOfContact"))
        attachments = _list(raw.get("resourceLinks"))

        safe_payload = {
            "notice_id": notice_id,
            "title": _text(first_value(raw, "title")),
            "solicitation_number": solicitation_number,
            "organization_path_name": organization_path,
            "organization_path_code": _text(path_code),
            "posted_date": posted_date,
            "response_deadline": response_deadline,
            "opportunity_type": opportunity_type,
            "base_type": base_type,
            "archive_type": _text(first_value(raw, "archiveType")),
            "archive_date": normalize_public_date(first_value(raw, "archiveDate")),
            "active": _text(first_value(raw, "active")),
            "set_aside": _text(
                first_value(raw, "typeOfSetAsideDescription", "setAside")
            ),
            "set_aside_code": _text(first_value(raw, "typeOfSetAside", "setAsideCode")),
            "naics_code": _text(first_value(raw, "naicsCode")),
            "classification_code": _text(first_value(raw, "classificationCode")),
            "award_number": _text(first_value(award, "number")),
            "award_amount": first_value(award, "amount"),
            "award_date": award_date,
            "awardee_name": _text(first_value(awardee, "name")),
            "awardee_uei": _text(first_value(awardee, "ueiSAM")),
            "place_city": _text(first_value(city, "name")),
            "place_state": _text(first_value(state, "code", "name")),
            "place_country": _text(first_value(country, "code", "name")),
            "canonical_url": canonical_url,
            "contact_records_omitted": len(contacts),
            "attachment_links_omitted": len(attachments),
            "description_body_omitted": bool(first_value(raw, "description")),
        }
        safe_payload, report = sanitize_mapping(safe_payload)
        award_notice = "award" in str(opportunity_type or "").casefold()

        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=notice_id,
            record_type="award" if award_notice else "solicitation",
            title=first_value(safe_payload, "title")
            or solicitation_number
            or notice_id,
            published_date=posted_date,
            end_date=response_deadline or award_date,
            organizations=[
                _text(self.organization_name),
                organization_path,
                first_value(safe_payload, "awardee_name"),
            ],
            topics=[
                opportunity_type,
                base_type,
                first_value(safe_payload, "set_aside"),
                first_value(safe_payload, "naics_code"),
                first_value(safe_payload, "classification_code"),
            ],
            links=[canonical_url],
            identifiers={
                "sam_notice_id": notice_id,
                "solicitation_number": solicitation_number,
                "organization_path_code": safe_payload.get("organization_path_code"),
                "naics_code": safe_payload.get("naics_code"),
                "classification_code": safe_payload.get("classification_code"),
                "award_number": safe_payload.get("award_number"),
                "awardee_uei": safe_payload.get("awardee_uei"),
            },
            geography={
                "city": safe_payload.get("place_city"),
                "state": safe_payload.get("place_state"),
                "country": safe_payload.get("place_country"),
            },
            funding_amount=safe_payload.get("award_amount"),
            funding_currency="USD" if safe_payload.get("award_amount") else None,
            attributes={
                "opportunity_type": opportunity_type,
                "base_type": base_type,
                "active": safe_payload.get("active"),
                "archive_type": safe_payload.get("archive_type"),
                "archive_date": safe_payload.get("archive_date"),
                "set_aside": safe_payload.get("set_aside"),
                "set_aside_code": safe_payload.get("set_aside_code"),
                "organization_scope_code": self.organization_code,
                "organization_scope_name": self.organization_name,
                "organization_scope_confirmed": True,
                "title_query": _text(request.query),
                "collection_route": str(
                    request.options.get("collection_route") or "sam_gov_public_api"
                ),
                "source_cache_cutoff": request.options.get("source_cache_cutoff"),
                "contacts_collected": False,
                "contact_records_omitted": safe_payload.get(
                    "contact_records_omitted", 0
                ),
                "description_collected": False,
                "description_body_omitted": safe_payload.get(
                    "description_body_omitted", False
                ),
                "attachments_collected": False,
                "attachment_links_omitted": safe_payload.get(
                    "attachment_links_omitted", 0
                ),
                "rights_note": (
                    "Public SAM.gov opportunity metadata. Linked descriptions and "
                    "attachments were not collected."
                ),
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=canonical_url,
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
        if not request.from_date or not request.to_date:
            raise ValueError("SAM.gov collection requires from_date and to_date")
        windows = _date_windows(request.from_date, request.to_date)
        state = dict(checkpoint or {})
        window_index = max(0, int(state.get("window_index", 0)))
        api_offset = max(0, int(state.get("api_offset", 0)))
        item_offset = max(0, int(state.get("item_offset", 0)))
        emitted = 0
        pages_read = 0
        self.exhausted = False

        while window_index < len(windows) and emitted < request.max_records:
            posted_from, posted_to = windows[window_index]
            if pages_read >= request.max_pages:
                raise RuntimeError(
                    "SAM.gov page budget exhausted before the record limit"
                )
            response = self._unwrap(
                http.get_json(
                    self.endpoint,
                    params=self._params(
                        request,
                        posted_from,
                        posted_to,
                        api_offset,
                    ),
                )
            )
            pages_read += 1
            opportunities = response.get("opportunitiesData") or []
            total_records = int(response.get("totalRecords") or 0)
            if item_offset > len(opportunities):
                raise RuntimeError("SAM.gov checkpoint is beyond the resumed page")

            for index in range(item_offset, len(opportunities)):
                raw = opportunities[index]
                if not isinstance(raw, Mapping):
                    continue
                published = normalize_public_date(first_value(raw, "postedDate"))
                if not published:
                    raise RuntimeError(
                        "SAM.gov returned a record without a posted date"
                    )
                if published < request.from_date or published > request.to_date:
                    raise RuntimeError(
                        "SAM.gov returned a record outside the requested date scope"
                    )
                record = self._record(raw, request)
                yield CollectedRecord(
                    record=record,
                    checkpoint={
                        "window_index": window_index,
                        "api_offset": api_offset,
                        "item_offset": index + 1,
                    },
                )
                emitted += 1
                if emitted >= request.max_records:
                    return

            next_offset = api_offset + len(opportunities)
            if not opportunities or next_offset >= total_records:
                window_index += 1
                api_offset = 0
                item_offset = 0
            else:
                api_offset = next_offset
                item_offset = 0

        self.exhausted = window_index >= len(windows)

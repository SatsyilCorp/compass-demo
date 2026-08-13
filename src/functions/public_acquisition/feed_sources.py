"""Bounded adapters for public ONR-adjacent source APIs.

Each adapter returns a source envelope plus a small canonical projection. The
callers retain both forms, hash every projection, compare it with the prior
accepted page, and publish only accepted changes. These are scheduled source
polls, not push streams.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Mapping


JsonOpen = Callable[[urllib.request.Request, int], tuple[Dict[str, Any], bytes]]


SOURCE_REGISTRY = {
    "grants-gov-onr": {
        "label": "Grants.gov ONR opportunities",
        "authority": "Grants.gov",
        "endpoint": "https://api.grants.gov/v1/api/search2",
        "cadence_seconds": 900,
        "data_kind": "Public funding opportunities",
        "model_use": "Narrative routing and analyst review",
    },
    "federal-register-onr": {
        "label": "Federal Register ONR notices",
        "authority": "FederalRegister.gov and GovInfo",
        "endpoint": "https://www.federalregister.gov/api/v1/documents.json",
        "cadence_seconds": 1800,
        "data_kind": "Public regulatory notices",
        "model_use": "Narrative routing and deadline review",
    },
    "crossref-onr": {
        "label": "Crossref ONR-funded works",
        "authority": "Crossref",
        "endpoint": "https://api.crossref.org/v1/funders/100000006/works",
        "cadence_seconds": 3600,
        "data_kind": "Publication metadata linked to the ONR funder DOI",
        "model_use": "Publication routing and award linkage",
    },
}


def _text(value: Any, maximum: int = 1000) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = " ".join(text.replace("\u2014", " - ").split()).strip()
    return text[:maximum] or None


def _safe_grants_detail(value: Mapping[str, Any]) -> Dict[str, Any]:
    synopsis = value.get("synopsis") if isinstance(value.get("synopsis"), Mapping) else {}
    forecast = value.get("forecast") if isinstance(value.get("forecast"), Mapping) else {}
    safe_synopsis = {
        key: synopsis.get(key)
        for key in (
            "synopsisDesc",
            "responseDateStr",
            "postingDateStr",
            "archiveDateStr",
            "lastUpdatedDate",
            "fundingDescLinkUrl",
            "numberOfAwards",
            "awardCeiling",
            "awardFloor",
            "costSharing",
            "fundingInstruments",
            "fundingActivityCategories",
        )
        if synopsis.get(key) not in (None, "")
    }
    safe_forecast = {
        key: forecast.get(key)
        for key in (
            "forecastDesc",
            "synopsisDesc",
            "responseDateStr",
            "postingDateStr",
            "archiveDateStr",
            "estimatedFunding",
            "estimatedNumberOfAwards",
            "fundingInstruments",
            "fundingActivityCategories",
        )
        if forecast.get(key) not in (None, "")
    }
    attachments = []
    for folder in value.get("synopsisAttachmentFolders") or []:
        if not isinstance(folder, Mapping):
            continue
        for attachment in folder.get("synopsisAttachments") or []:
            if not isinstance(attachment, Mapping):
                continue
            attachments.append(
                {
                    key: attachment.get(key)
                    for key in ("id", "mimeType", "fileName", "fileDescription", "fileLobSize", "lastUpdatedDate")
                    if attachment.get(key) not in (None, "")
                }
            )
    return {
        "id": value.get("id"),
        "opportunityNumber": value.get("opportunityNumber"),
        "opportunityTitle": value.get("opportunityTitle"),
        "owningAgencyCode": value.get("owningAgencyCode"),
        "opportunityCategory": value.get("opportunityCategory"),
        "docType": value.get("docType"),
        "synopsis": safe_synopsis,
        "forecast": safe_forecast,
        "agencyDetails": value.get("agencyDetails"),
        "topAgencyDetails": value.get("topAgencyDetails"),
        "attachments": attachments,
        "cfdas": value.get("cfdas") or [],
    }


def _date_parts(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return _text(value, 32)
    parts = value.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    values = [int(part) for part in parts[0][:3]]
    if not values:
        return None
    return "-".join(
        [str(values[0]), *(f"{part:02d}" for part in values[1:])]
    )


def _profile_limit(profile: str) -> int:
    return {"quick": 10, "standard": 50, "deep": 100}.get(profile, 50)


def _get_json(open_json: JsonOpen, endpoint: str, params: Mapping[str, Any]) -> tuple[Dict[str, Any], bytes]:
    query = urllib.parse.urlencode(
        [(str(key), str(value)) for key, value in params.items() if value not in (None, "")]
    )
    request = urllib.request.Request(
        f"{endpoint}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Compass-Public-Evidence/1.0 contact@satsyil.com"},
    )
    return open_json(request, 25)


def _post_json(open_json: JsonOpen, endpoint: str, body: Mapping[str, Any]) -> tuple[Dict[str, Any], bytes]:
    request = urllib.request.Request(
        endpoint,
        method="POST",
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Compass-Public-Evidence/1.0 contact@satsyil.com",
        },
    )
    return open_json(request, 25)


def _grants_gov(open_json: JsonOpen, profile: str) -> Dict[str, Any]:
    spec = SOURCE_REGISTRY["grants-gov-onr"]
    limit = _profile_limit(profile)
    response, _search_raw = _post_json(
        open_json,
        spec["endpoint"],
        {
            "rows": limit,
            "keyword": "",
            "oppNum": "",
            "eligibilities": "",
            "agencies": "DOD-ONR",
            "oppStatuses": "forecasted|posted|closed|archived",
            "aln": "",
            "fundingCategories": "",
            "sortBy": "openDate|desc",
            "startRecordNum": 0,
        },
    )
    data = response.get("data") if isinstance(response.get("data"), Mapping) else {}
    hits = data.get("oppHits") if isinstance(data.get("oppHits"), list) else []
    records = []
    detail_limit = {"quick": 5, "standard": 10, "deep": 25}.get(profile, 10)
    retained_details: List[Mapping[str, Any]] = []
    for index, item in enumerate(hits):
        if not isinstance(item, Mapping) or str(item.get("agencyCode") or "").upper() != "DOD-ONR":
            continue
        opportunity_id = _text(item.get("id"), 80)
        opportunity_number = _text(item.get("number"), 160) or opportunity_id
        if not opportunity_number:
            continue
        detail: Mapping[str, Any] = {}
        if opportunity_id and index < detail_limit:
            try:
                detail_response, _detail_raw = _post_json(
                    open_json,
                    "https://api.grants.gov/v1/api/fetchOpportunity",
                    {"opportunityId": int(opportunity_id)},
                )
                candidate = detail_response.get("data")
                if isinstance(candidate, Mapping):
                    detail = _safe_grants_detail(candidate)
                    retained_details.append(detail)
            except (OSError, RuntimeError, ValueError):
                detail = {}
        synopsis = detail.get("synopsis") if isinstance(detail.get("synopsis"), Mapping) else {}
        forecast = detail.get("forecast") if isinstance(detail.get("forecast"), Mapping) else {}
        attachments = detail.get("attachments") if isinstance(detail.get("attachments"), list) else []
        first_attachment = next(
            (attachment for attachment in attachments if isinstance(attachment, Mapping) and attachment.get("id")),
            None,
        )
        title = _text(detail.get("opportunityTitle") or item.get("title"), 1000)
        narrative = _text(
            synopsis.get("synopsisDesc")
            or forecast.get("forecastDesc")
            or forecast.get("synopsisDesc")
            or title,
            3000,
        )
        funding_ceiling = synopsis.get("awardCeiling") or forecast.get("estimatedFunding")
        try:
            amount = float(str(funding_ceiling).replace(",", "")) if funding_ceiling not in (None, "") else None
        except ValueError:
            amount = None
        records.append(
            {
                "source_id": "grants-gov-onr",
                "source_record_id": opportunity_number,
                "record_type": "funding_opportunity",
                "title": title,
                "description": narrative,
                "award_amount_usd": amount,
                "published_date": _text(item.get("openDate"), 32),
                "end_date": _text(item.get("closeDate"), 32),
                "last_modified_at": _text(item.get("openDate"), 32),
                "organizations": [_text(item.get("agency"), 160) or "Office of Naval Research"],
                "topics": [str(value) for value in (item.get("cfdaList") or [])][:20],
                "status": _text(item.get("oppStatus"), 80),
                "detail_fetched": bool(detail),
                "source_url": (
                    f"https://www.grants.gov/search-results-detail/{opportunity_id}"
                    if opportunity_id
                    else "https://www.grants.gov/search-results-detail"
                ),
                "document_url": (
                    f"https://apply07.grants.gov/grantsws/rest/opportunity/att/download/{first_attachment['id']}"
                    if first_attachment
                    else None
                ),
                "document_title": _text((first_attachment or {}).get("fileName"), 300),
            }
        )
    safe_search = {
        key: value
        for key, value in response.items()
        if key.casefold() not in {"token", "access_token", "refresh_token"}
    }
    raw = json.dumps(
        {
            "contract": "compass.grants-gov-source-envelope.v1",
            "search": safe_search,
            "details": retained_details,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "source_id": "grants-gov-onr",
        "source": "public-api://grants.gov/search2?agency=DOD-ONR",
        "raw": raw,
        "records": records,
        "has_more": int(data.get("hitCount") or 0) > len(hits),
        "total_available": int(data.get("hitCount") or 0),
        "pages_fetched": 1 + len(retained_details),
    }


def _federal_register(open_json: JsonOpen, profile: str) -> Dict[str, Any]:
    spec = SOURCE_REGISTRY["federal-register-onr"]
    limit = _profile_limit(profile)
    response, raw = _get_json(
        open_json,
        spec["endpoint"],
        {
            "per_page": limit,
            "page": 1,
            "order": "newest",
            "conditions[agencies][]": "navy-department",
            "conditions[term]": '"Office of Naval Research"',
        },
    )
    hits = response.get("results") if isinstance(response.get("results"), list) else []
    records = []
    for item in hits:
        if not isinstance(item, Mapping):
            continue
        record_id = _text(item.get("document_number"), 120)
        if not record_id:
            continue
        agencies = [
            _text(agency.get("name"), 160)
            for agency in (item.get("agencies") or [])
            if isinstance(agency, Mapping)
        ]
        records.append(
            {
                "source_id": "federal-register-onr",
                "source_record_id": record_id,
                "record_type": "regulatory_notice",
                "title": _text(item.get("title"), 1000),
                "description": _text(item.get("abstract"), 2000),
                "published_date": _text(item.get("publication_date"), 32),
                "last_modified_at": _text(item.get("publication_date"), 32),
                "organizations": [value for value in agencies if value],
                "topics": [_text(item.get("type"), 120)],
                "source_url": _text(item.get("html_url"), 500),
                "document_url": _text(item.get("pdf_url"), 500),
            }
        )
    return {
        "source_id": "federal-register-onr",
        "source": "public-api://federalregister.gov/navy?term=Office+of+Naval+Research",
        "raw": raw,
        "records": records,
        "has_more": int(response.get("count") or 0) > len(hits),
        "total_available": int(response.get("count") or 0),
        "pages_fetched": 1,
    }


def _crossref(open_json: JsonOpen, profile: str) -> Dict[str, Any]:
    spec = SOURCE_REGISTRY["crossref-onr"]
    limit = _profile_limit(profile)
    from_date = (datetime.now(timezone.utc) - timedelta(days=550)).date().isoformat()
    exact_endpoint = "https://api.crossref.org/v1/funders/100000006/works"
    response, raw = _get_json(
        open_json,
        exact_endpoint,
        {
            "rows": limit,
            "filter": f"from-update-date:{from_date}T00:00:00",
            "select": "DOI,title,published,funder,subject,URL,is-referenced-by-count,type,publisher",
            "mailto": "contact@satsyil.com",
        },
    )
    message = response.get("message") if isinstance(response.get("message"), Mapping) else {}
    hits = message.get("items") if isinstance(message.get("items"), list) else []
    records = []
    for item in hits:
        if not isinstance(item, Mapping):
            continue
        doi = _text(item.get("DOI"), 240)
        if not doi:
            continue
        funders = [entry for entry in (item.get("funder") or []) if isinstance(entry, Mapping)]
        exact_onr = [
            entry
            for entry in funders
            if str(entry.get("DOI") or entry.get("doi") or "").casefold()
            == "10.13039/100000006"
        ]
        if not exact_onr:
            continue
        award_ids = sorted(
            {
                str(award).strip()
                for funder in exact_onr
                for award in (funder.get("award") or [])
                if str(award).strip()
            }
        )
        title = _text(item.get("title"), 1000)
        subjects = [str(value) for value in (item.get("subject") or [])][:30]
        published = _date_parts(item.get("published"))
        records.append(
            {
                "source_id": "crossref-onr",
                "source_record_id": doi.casefold(),
                "record_type": "publication",
                "title": title,
                "description": " ".join([title or "", *subjects, *award_ids]).strip(),
                "published_date": published,
                "last_modified_at": published,
                "organizations": [
                    *[_text(value.get("name"), 160) for value in exact_onr],
                    _text(item.get("publisher"), 160),
                ],
                "topics": subjects,
                "award_ids": award_ids,
                "citation_count": int(item.get("is-referenced-by-count") or 0),
                "source_url": _text(item.get("URL"), 500) or f"https://doi.org/{doi}",
            }
        )
    total = int(message.get("total-results") or 0)
    return {
        "source_id": "crossref-onr",
        "source": "public-api://crossref/funders/100000006/works",
        "raw": raw,
        "records": records,
        "has_more": total > len(hits),
        "total_available": total,
        "pages_fetched": 1,
    }


def fetch_source(source_id: str, profile: str, open_json: JsonOpen) -> Dict[str, Any]:
    adapters = {
        "grants-gov-onr": _grants_gov,
        "federal-register-onr": _federal_register,
        "crossref-onr": _crossref,
    }
    adapter = adapters.get(source_id)
    if adapter is None:
        raise ValueError(f"unknown public source: {source_id}")
    return adapter(open_json, profile)

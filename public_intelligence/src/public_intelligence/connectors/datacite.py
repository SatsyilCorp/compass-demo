"""DataCite DOI connector for public outputs funded by ONR."""

from __future__ import annotations

import urllib.parse
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


DEFAULT_ENDPOINT = "https://api.datacite.org/dois"
DEFAULT_ONR_ROR = "https://ror.org/00rk2pe57"
DATASET_RESOURCE_TYPES = {
    "audiovisual",
    "collection",
    "computationalnotebook",
    "dataset",
    "event",
    "image",
    "instrument",
    "interactiveresource",
    "model",
    "outputmanagementplan",
    "physicalobject",
    "sample",
    "service",
    "software",
    "sound",
    "standard",
    "workflow",
}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_title(attributes: Mapping[str, Any]) -> str | None:
    for title in _list(attributes.get("titles")):
        if isinstance(title, Mapping):
            value = first_value(title, "title")
        else:
            value = title
        if value not in (None, ""):
            return plain_text(value)
    return None


def _abstract(attributes: Mapping[str, Any]) -> str | None:
    descriptions = _list(attributes.get("descriptions"))
    for description in descriptions:
        if not isinstance(description, Mapping):
            continue
        if str(description.get("descriptionType") or "").casefold() == "abstract":
            return plain_text(description.get("description"))
    return None


def _affiliations(attributes: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for role in ("creators", "contributors"):
        for person in _list(attributes.get(role)):
            if not isinstance(person, Mapping):
                continue
            for affiliation in _list(person.get("affiliation")):
                if isinstance(affiliation, Mapping):
                    name = first_value(affiliation, "name")
                else:
                    name = affiliation
                if name not in (None, ""):
                    values.append(str(name))
    return values


def _subjects(attributes: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for subject in _list(attributes.get("subjects")):
        if isinstance(subject, Mapping):
            value = first_value(subject, "subject")
        else:
            value = subject
        if value not in (None, ""):
            values.append(str(value))
    return values


def _published_date(attributes: Mapping[str, Any]) -> str | None:
    direct = normalize_public_date(first_value(attributes, "published"))
    if direct:
        return direct
    dates = _list(attributes.get("dates"))
    priority = ("issued", "available", "created", "submitted", "updated")
    for date_type in priority:
        for item in dates:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("dateType") or "").casefold() != date_type:
                continue
            normalized = normalize_public_date(item.get("date"))
            if normalized:
                return normalized
    return normalize_public_date(first_value(attributes, "publicationYear"))


def _funding_references(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for item in _list(attributes.get("fundingReferences")):
        if not isinstance(item, Mapping):
            continue
        references.append(
            {
                "funder_name": first_value(item, "funderName"),
                "funder_identifier": first_value(item, "funderIdentifier"),
                "funder_identifier_type": first_value(item, "funderIdentifierType"),
                "award_number": first_value(item, "awardNumber"),
                "award_title": first_value(item, "awardTitle"),
                "award_uri": first_value(item, "awardUri"),
            }
        )
    return references


def _related_identifiers(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    for item in _list(attributes.get("relatedIdentifiers")):
        if not isinstance(item, Mapping):
            continue
        related.append(
            {
                "identifier": first_value(item, "relatedIdentifier"),
                "identifier_type": first_value(item, "relatedIdentifierType"),
                "relation_type": first_value(item, "relationType"),
                "resource_type": first_value(item, "resourceTypeGeneral"),
            }
        )
    return related


def _rights(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    rights: list[dict[str, Any]] = []
    for item in _list(attributes.get("rightsList")):
        if not isinstance(item, Mapping):
            continue
        rights.append(
            {
                "name": first_value(item, "rights"),
                "identifier": first_value(item, "rightsIdentifier"),
                "uri": first_value(item, "rightsUri"),
                "scheme": first_value(item, "rightsIdentifierScheme"),
            }
        )
    return rights


class DataCiteConnector:
    """Collect ONR-funded DataCite records without researcher identities."""

    source_id = "datacite"

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        funder_ror: str = DEFAULT_ONR_ROR,
    ) -> None:
        if not funder_ror.startswith("https://ror.org/"):
            raise ValueError("funder_ror must be a canonical https://ror.org/ identifier")
        self.endpoint = endpoint
        self.funder_ror = funder_ror
        self.exhausted = False

    def _query(self, request: CollectionRequest) -> str | None:
        clauses: list[str] = []
        if request.query:
            clauses.append(f"({request.query})")
        if request.from_date or request.to_date:
            start_year = request.from_date[:4] if request.from_date else "0000"
            end_year = request.to_date[:4] if request.to_date else "9999"
            clauses.append(f"publicationYear:[{start_year} TO {end_year}]")
        return " AND ".join(clauses) or None

    def _params(self, request: CollectionRequest, cursor: str) -> dict[str, Any]:
        return {
            "funded-by": self.funder_ror,
            "page[size]": min(request.page_size, 1000),
            "page[cursor]": cursor,
            "query": self._query(request),
        }

    @staticmethod
    def _next_cursor(response: Mapping[str, Any]) -> str | None:
        links = response.get("links")
        if not isinstance(links, Mapping) or not links.get("next"):
            return None
        query = urllib.parse.urlparse(str(links["next"])).query
        values = urllib.parse.parse_qs(query).get("page[cursor]")
        return values[0] if values else None

    def _matches_date_range(
        self,
        attributes: Mapping[str, Any],
        request: CollectionRequest,
    ) -> bool:
        published = _published_date(attributes)
        if published and request.from_date and published < request.from_date:
            return False
        if published and request.to_date and published > request.to_date:
            return False
        return True

    def _record(self, raw: Mapping[str, Any], request: CollectionRequest) -> CanonicalRecord:
        attributes = raw.get("attributes")
        if not isinstance(attributes, Mapping):
            attributes = {}
        doi = first_value(attributes, "doi") or first_value(raw, "id") or sha256_json(raw)[:24]
        title = _first_title(attributes) or str(doi)
        resource_types = (
            attributes.get("types") if isinstance(attributes.get("types"), Mapping) else {}
        )
        resource_type = first_value(resource_types, "resourceTypeGeneral", "resourceType")
        record_type = (
            "dataset"
            if str(resource_type or "").replace(" ", "").casefold() in DATASET_RESOURCE_TYPES
            else "publication"
        )
        affiliations = _affiliations(attributes)
        funders = _funding_references(attributes)
        subjects = _subjects(attributes)
        related = _related_identifiers(attributes)
        rights = _rights(attributes)
        published_date = _published_date(attributes)
        publisher = first_value(attributes, "publisher")
        if isinstance(publisher, Mapping):
            publisher = first_value(publisher, "name")
        abstract = _abstract(attributes)
        creators = _list(attributes.get("creators"))
        contributors = _list(attributes.get("contributors"))
        doi_url = f"https://doi.org/{str(doi).lower()}"
        content_url = attributes.get("contentUrl")
        content_urls = [str(value) for value in content_url] if isinstance(content_url, list) else [content_url]

        safe_payload = {
            "doi": str(doi).lower(),
            "title": title,
            "abstract": abstract,
            "published_date": published_date,
            "publisher": publisher,
            "resource_type": resource_type,
            "resource_type_schema_org": first_value(resource_types, "schemaOrg"),
            "subjects": subjects,
            "affiliations": affiliations,
            "funding_references": funders,
            "related_identifiers": related,
            "rights": rights,
            "url": first_value(attributes, "url"),
            "content_urls": content_urls,
            "citation_count": first_value(attributes, "citationCount"),
            "reference_count": first_value(attributes, "referenceCount"),
            "view_count": first_value(attributes, "viewCount"),
            "download_count": first_value(attributes, "downloadCount"),
            "state": first_value(attributes, "state"),
            "is_active": first_value(attributes, "isActive"),
            "creator_count": len(creators),
            "contributor_count": len(contributors),
        }
        safe_payload, report = sanitize_mapping(safe_payload)
        title = str(safe_payload["title"])
        abstract = safe_payload.get("abstract")
        affiliations = list(safe_payload.get("affiliations") or [])
        funders = list(safe_payload.get("funding_references") or [])
        subjects = list(safe_payload.get("subjects") or [])
        related = list(safe_payload.get("related_identifiers") or [])
        rights = list(safe_payload.get("rights") or [])
        publisher = safe_payload.get("publisher")
        content_urls = list(safe_payload.get("content_urls") or [])
        award_numbers = [
            str(item["award_number"])
            for item in funders
            if isinstance(item, Mapping) and item.get("award_number") not in (None, "")
        ]
        funder_ids = [
            str(item["funder_identifier"])
            for item in funders
            if isinstance(item, Mapping)
            and item.get("funder_identifier") not in (None, "")
        ]
        funder_names = [
            str(item["funder_name"])
            for item in funders
            if isinstance(item, Mapping) and item.get("funder_name") not in (None, "")
        ]

        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(doi).lower(),
            record_type=record_type,
            title=title,
            abstract=abstract,
            published_date=published_date,
            organizations=[*affiliations, *funder_names, publisher],
            topics=[*subjects, resource_type],
            links=[safe_payload.get("url"), doi_url, *content_urls],
            identifiers={
                "doi": str(doi).lower(),
                "award_numbers": award_numbers,
                "funder_identifiers": funder_ids,
                "related_identifiers": related,
            },
            attributes={
                "resource_type": resource_type,
                "citation_count": first_value(attributes, "citationCount"),
                "reference_count": first_value(attributes, "referenceCount"),
                "view_count": first_value(attributes, "viewCount"),
                "download_count": first_value(attributes, "downloadCount"),
                "rights": rights,
                "state": first_value(attributes, "state"),
                "is_active": first_value(attributes, "isActive"),
                "creator_count": len(creators),
                "contributor_count": len(contributors),
                "identity_records_omitted": len(creators) + len(contributors),
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=self.endpoint,
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
        cursor = str(state.get("cursor", "1"))
        offset = max(0, int(state.get("offset", 0)))
        emitted = 0
        pages_read = 0

        while emitted < request.max_records:
            if pages_read >= request.max_pages:
                raise RuntimeError("DataCite page budget exhausted before the record limit")
            response = http.get_json(self.endpoint, params=self._params(request, cursor))
            pages_read += 1
            if not isinstance(response, Mapping):
                raise RuntimeError("DataCite returned an invalid response")
            if response.get("errors"):
                raise RuntimeError(f"DataCite reported errors: {response['errors']}")
            items = list(response.get("data") or [])
            if not items:
                self.exhausted = True
                return
            next_cursor = self._next_cursor(response)
            for index in range(offset, len(items)):
                if emitted >= request.max_records:
                    return
                raw = items[index]
                if not isinstance(raw, Mapping):
                    continue
                attributes = raw.get("attributes")
                if not isinstance(attributes, Mapping):
                    attributes = {}
                if not self._matches_date_range(attributes, request):
                    continue
                emitted += 1
                yield CollectedRecord(
                    record=self._record(raw, request),
                    checkpoint={"cursor": cursor, "offset": index + 1},
                )
            if not next_cursor or next_cursor == cursor:
                self.exhausted = True
                return
            cursor = next_cursor
            offset = 0

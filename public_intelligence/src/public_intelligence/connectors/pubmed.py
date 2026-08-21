"""PubMed connector for publications carrying ONR contract identifiers."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest


DEFAULT_SEARCH_ENDPOINT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
DEFAULT_FETCH_ENDPOINT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DEFAULT_QUERY = "N00014[Grant Number]"
YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).replace("\u2014", " - ").split())
    return value or None


def _date(article: ET.Element) -> str | None:
    pub_date = article.find(".//JournalIssue/PubDate")
    year = _text(pub_date.find("Year")) if pub_date is not None else None
    if not year and pub_date is not None:
        medline = _text(pub_date.find("MedlineDate"))
        match = YEAR.search(medline or "")
        year = match.group(0) if match else None
    if not year:
        completed = article.find(".//DateCompleted")
        year = _text(completed.find("Year")) if completed is not None else None
        month = _text(completed.find("Month")) if completed is not None else None
        day = _text(completed.find("Day")) if completed is not None else None
    else:
        month = _text(pub_date.find("Month")) if pub_date is not None else None
        day = _text(pub_date.find("Day")) if pub_date is not None else None
    if not year:
        return None
    month_number = 1
    if month:
        try:
            month_number = int(month)
        except ValueError:
            names = {
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            }
            month_number = names.get(month[:3].casefold(), 1)
    day_number = int(day) if day and day.isdigit() else 1
    return f"{int(year):04d}-{month_number:02d}-{day_number:02d}"


def _values(article: ET.Element, path: str) -> list[str]:
    return [value for item in article.findall(path) if (value := _text(item))]


class PubMedConnector:
    """Collect a public biomedical subset with exact N00014 grant indexing."""

    source_id = "pubmed"

    def __init__(
        self,
        search_endpoint: str = DEFAULT_SEARCH_ENDPOINT,
        *,
        fetch_endpoint: str = DEFAULT_FETCH_ENDPOINT,
        email: str | None = None,
        api_key: str | None = None,
        grant_query: str = DEFAULT_QUERY,
    ) -> None:
        self.search_endpoint = search_endpoint
        self.fetch_endpoint = fetch_endpoint
        self.email = email
        self.api_key = api_key
        self.grant_query = grant_query
        self.exhausted = False

    def _common(self) -> dict[str, Any]:
        return {
            "tool": "compass_public_intelligence",
            "email": self.email,
            "api_key": self.api_key,
        }

    def _search_params(
        self, request: CollectionRequest, retstart: int
    ) -> dict[str, Any]:
        query = request.query or self.grant_query
        return {
            **self._common(),
            "db": "pubmed",
            "retmode": "json",
            "term": query,
            "retstart": retstart,
            "retmax": min(request.page_size, 200),
            "datetype": "pdat",
            "mindate": request.from_date.replace("-", "/") if request.from_date else None,
            "maxdate": request.to_date.replace("-", "/") if request.to_date else None,
        }

    def _fetch_params(self, identifiers: list[str]) -> dict[str, Any]:
        return {
            **self._common(),
            "db": "pubmed",
            "id": ",".join(identifiers),
            "retmode": "xml",
            "rettype": "medline",
        }

    def _record(
        self, article: ET.Element, request: CollectionRequest
    ) -> CanonicalRecord:
        pmid = _text(article.find(".//PMID"))
        if not pmid:
            raise RuntimeError("PubMed record is missing PMID")
        title = _text(article.find(".//ArticleTitle")) or f"PubMed {pmid}"
        journal = _text(article.find(".//Journal/Title"))
        doi = None
        pmc = None
        for identifier in article.findall(".//ArticleId"):
            kind = str(identifier.attrib.get("IdType") or "").casefold()
            if kind == "doi":
                doi = _text(identifier)
            elif kind == "pmc":
                pmc = _text(identifier)
        grants: list[dict[str, str | None]] = []
        for grant in article.findall(".//GrantList/Grant"):
            grants.append(
                {
                    "grant_id": _text(grant.find("GrantID")),
                    "agency": _text(grant.find("Agency")),
                    "country": _text(grant.find("Country")),
                }
            )
        safe_payload = {
            "pmid": pmid,
            "title": title,
            "journal": journal,
            "published_date": _date(article),
            "doi": doi,
            "pmc": pmc,
            "grants": grants,
            "mesh_terms": _values(article, ".//MeshHeading/DescriptorName"),
            "keywords": _values(article, ".//KeywordList/Keyword"),
            "publication_types": _values(article, ".//PublicationTypeList/PublicationType"),
            "languages": _values(article, ".//Article/Language"),
            "author_count": len(article.findall(".//AuthorList/Author")),
            "abstract_available": article.find(".//Abstract/AbstractText") is not None,
            "copyrighted_abstract_omitted": True,
            "search_scope": request.query or self.grant_query,
        }
        safe_payload, report = sanitize_mapping(safe_payload)
        grant_ids = sorted(
            {
                str(item["grant_id"])
                for item in safe_payload["grants"]
                if isinstance(item, Mapping) and item.get("grant_id")
            }
        )
        agencies = sorted(
            {
                str(item["agency"])
                for item in safe_payload["grants"]
                if isinstance(item, Mapping) and item.get("agency")
            }
        )
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        links = [pubmed_url]
        if doi:
            links.append(f"https://doi.org/{doi}")
        if pmc:
            links.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc}/")
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=pmid,
            record_type="publication",
            title=str(safe_payload["title"]),
            published_date=safe_payload.get("published_date"),
            organizations=[journal, *agencies],
            topics=[
                *safe_payload.get("mesh_terms", []),
                *safe_payload.get("keywords", []),
            ],
            links=links,
            identifiers={"pmid": pmid, "pmc": pmc, "doi": doi, "grant_ids": grant_ids},
            attributes={
                "journal": journal,
                "publication_types": safe_payload.get("publication_types", []),
                "languages": safe_payload.get("languages", []),
                "author_count": safe_payload.get("author_count", 0),
                "researcher_identities_omitted": safe_payload.get("author_count", 0),
                "abstract_available": safe_payload.get("abstract_available", False),
                "copyrighted_abstract_omitted": True,
                "search_scope": safe_payload.get("search_scope"),
                "pii_dropped_fields": report.dropped_fields,
                "pii_redacted_values": report.redacted_values,
            },
            source_url=pubmed_url,
            retrieved_at=request.retrieved_at,
            snapshot_id=request.snapshot_id,
            source_payload_sha256=sha256_json(safe_payload),
        )

    @staticmethod
    def _matches_date_range(article: ET.Element, request: CollectionRequest) -> bool:
        published = _date(article)
        if published and request.from_date and published < request.from_date:
            return False
        if published and request.to_date and published > request.to_date:
            return False
        return True

    def collect(
        self,
        http: HttpTransport,
        request: CollectionRequest,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> Iterator[CollectedRecord]:
        self.exhausted = False
        state = dict(checkpoint or {})
        retstart = max(0, int(state.get("retstart", 0)))
        offset = max(0, int(state.get("offset", 0)))
        emitted = 0
        pages_read = 0
        while emitted < request.max_records:
            if pages_read >= request.max_pages:
                raise RuntimeError("PubMed page budget exhausted before the record limit")
            result = http.get_json(
                self.search_endpoint,
                params=self._search_params(request, retstart),
            )
            pages_read += 1
            search = result.get("esearchresult") if isinstance(result, Mapping) else None
            identifiers = list(search.get("idlist") or []) if isinstance(search, Mapping) else []
            total = int(search.get("count") or 0) if isinstance(search, Mapping) else 0
            if not identifiers or retstart >= total:
                self.exhausted = True
                return
            xml_text = http.get_text(
                self.fetch_endpoint,
                params=self._fetch_params([str(value) for value in identifiers]),
            )
            try:
                articles = ET.fromstring(xml_text).findall(".//PubmedArticle")
            except ET.ParseError as error:
                raise RuntimeError("PubMed returned invalid XML") from error
            if len(articles) != len(identifiers):
                raise RuntimeError("PubMed search and fetch counts do not reconcile")
            for index in range(offset, len(articles)):
                if emitted >= request.max_records:
                    return
                if not self._matches_date_range(articles[index], request):
                    continue
                yield CollectedRecord(
                    record=self._record(articles[index], request),
                    checkpoint={"retstart": retstart, "offset": index + 1},
                )
                emitted += 1
            retstart += len(identifiers)
            offset = 0
            if retstart >= total:
                self.exhausted = True
                return

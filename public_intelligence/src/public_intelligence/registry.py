"""Source catalog with explicit access and implementation status."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .connectors import (
    CrossrefConnector,
    DataCiteConnector,
    FederalRegisterConnector,
    GrantsGovConnector,
    OpenAlexConnector,
    OnrWebsiteConnector,
    OstiConnector,
    PubMedConnector,
    SamGovConnector,
    SbirFullCsvConnector,
    UsaSpendingConnector,
    UsptoPatentsConnector,
)


class AccessMode(str, Enum):
    PUBLIC_API = "public_api"
    PUBLIC_DOWNLOAD = "public_download"
    GATED_API = "gated_api"
    LICENSED = "licensed"
    MANUAL_TRANSFER = "manual_transfer"
    PUBLIC_WEBSITE = "public_website"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class SourceDescriptor:
    source_id: str
    name: str
    authority: str
    access_mode: AccessMode
    homepage: str
    implemented: bool
    requirements: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["access_mode"] = self.access_mode.value
        value["requirements"] = list(self.requirements)
        return value


_SOURCES = (
    SourceDescriptor(
        source_id="onr_website",
        name="Official ONR website index",
        authority="Office of Naval Research",
        access_mode=AccessMode.PUBLIC_WEBSITE,
        homepage="https://www.onr.navy.mil/sitemap",
        implemented=True,
        notes=(
            "Robots-aware collection of page headings from the public HTML sitemap. "
            "Linked pages, documents, staff names, and contact details are not collected."
        ),
    ),
    SourceDescriptor(
        source_id="osti",
        name="OSTI.GOV ONR-sponsored records",
        authority="U.S. Department of Energy Office of Scientific and Technical Information",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://www.osti.gov/api/v1/docs",
        implemented=True,
        notes=(
            "Exact sponsor organization filter. Researcher identities and description "
            "text are omitted while rights are reviewed."
        ),
    ),
    SourceDescriptor(
        source_id="pubmed",
        name="PubMed ONR-indexed publications",
        authority="U.S. National Library of Medicine",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://www.ncbi.nlm.nih.gov/home/develop/api/",
        implemented=True,
        requirements=("registered tool email recommended",),
        notes=(
            "Exact N00014 Grant Number search. Author identities and copyrighted "
            "abstract text are omitted."
        ),
    ),
    SourceDescriptor(
        source_id="usaspending",
        name="USAspending Awards",
        authority="U.S. Department of the Treasury",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://api.usaspending.gov/",
        implemented=True,
        notes="Advanced Award Search API. No API key is required.",
    ),
    SourceDescriptor(
        source_id="sbir",
        name="SBIR and STTR Awards",
        authority="U.S. Small Business Administration",
        access_mode=AccessMode.PUBLIC_DOWNLOAD,
        homepage="https://www.sbir.gov/data-resources",
        implemented=True,
        notes="Monthly full award CSV with abstract content. Direct contact PII is removed.",
    ),
    SourceDescriptor(
        source_id="crossref",
        name="Crossref Works",
        authority="Crossref",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://api.crossref.org/",
        implemented=True,
        requirements=("mailto recommended",),
        notes="Cursor-based scholarly metadata collection.",
    ),
    SourceDescriptor(
        source_id="openalex",
        name="OpenAlex Works",
        authority="OurResearch",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://docs.openalex.org/",
        implemented=True,
        requirements=("API key may be required for sustained collection",),
        notes="Cursor-based research graph metadata collection.",
    ),
    SourceDescriptor(
        source_id="grants_gov",
        name="Grants.gov ONR Opportunities",
        authority="U.S. Department of Health and Human Services",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://www.grants.gov/api",
        implemented=True,
        notes=(
            "Public DOD-ONR opportunity search and detail APIs. Direct contact fields are removed."
        ),
    ),
    SourceDescriptor(
        source_id="datacite",
        name="DataCite Research Outputs",
        authority="DataCite",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://api.datacite.org/",
        implemented=True,
        notes=(
            "ONR-funded records selected by ROR. Metadata is CC0; linked content rights vary."
        ),
    ),
    SourceDescriptor(
        source_id="federal_register",
        name="Federal Register Navy Notices",
        authority="Office of the Federal Register and U.S. Government Publishing Office",
        access_mode=AccessMode.PUBLIC_API,
        homepage="https://www.federalregister.gov/developers/documentation/api/v1",
        implemented=True,
        notes=(
            "Navy Department notices selected by an exact ONR phrase by default. "
            "Official GovInfo PDF links are retained for legal reliance."
        ),
    ),
    SourceDescriptor(
        source_id="uspto_patents",
        name="USPTO PatentsView ONR-linked patent grants",
        authority="United States Patent and Trademark Office",
        access_mode=AccessMode.GATED_API,
        homepage="https://data.uspto.gov/support/transition-guide/patentsview",
        implemented=True,
        requirements=("USPTO_ODP_API_KEY at collection time",),
        notes=(
            "Exact Office of Naval Research government-interest organization or "
            "punctuation-folded N00014 award prefix. Inventor identities, people, "
            "addresses, abstracts, and statement text are omitted."
        ),
    ),
    SourceDescriptor(
        source_id="navy_budget_materials",
        name="Department of the Navy Budget Materials",
        authority="Department of the Navy, Financial Management and Comptroller",
        access_mode=AccessMode.MANUAL_TRANSFER,
        homepage="https://www.secnav.navy.mil/fmc/fmb/Pages/default.aspx",
        implemented=False,
        requirements=(
            "approved direct-document manifest or manual transfer",
            "document-level provenance review",
        ),
        notes=(
            "Declared only. The public SharePoint edge currently rejects automated "
            "collection, so Compass does not bypass it."
        ),
    ),
    SourceDescriptor(
        source_id="sam_gov",
        name="SAM.gov Contract Opportunities",
        authority="U.S. General Services Administration",
        access_mode=AccessMode.GATED_API,
        homepage="https://open.gsa.gov/api/get-opportunities-public-api/",
        implemented=True,
        requirements=(
            "SAM_GOV_API_KEY at collection time",
            "source-owner-approved quota window",
        ),
        notes=(
            "Public ONR hierarchy metadata. Contacts, descriptions, attachment URLs, "
            "street addresses, and API-key-bearing links are omitted."
        ),
    ),
    SourceDescriptor(
        source_id="advana",
        name="Advana governed data products",
        authority="U.S. Department of Defense",
        access_mode=AccessMode.MANUAL_TRANSFER,
        homepage="https://advana.data.mil/",
        implemented=False,
        requirements=("government-furnished access", "approved data-use agreement"),
        notes="Declared only. Data must enter through an authorized government transfer.",
    ),
    SourceDescriptor(
        source_id="pulse",
        name="Pulse governed data products",
        authority="U.S. Department of Defense",
        access_mode=AccessMode.MANUAL_TRANSFER,
        homepage="",
        implemented=False,
        requirements=(
            "government-furnished access",
            "approved data-use agreement",
            "source-owner-approved transfer",
        ),
        notes="Declared integration target only. No live Pulse connection is claimed.",
    ),
    SourceDescriptor(
        source_id="scopus",
        name="Scopus",
        authority="Elsevier",
        access_mode=AccessMode.LICENSED,
        homepage="https://dev.elsevier.com/",
        implemented=False,
        requirements=("institutional license", "API key", "license review"),
        notes="Declared only. OpenAlex and Crossref are the public baseline.",
    ),
    SourceDescriptor(
        source_id="startup_investment_licensed",
        name="Startup investment intelligence",
        authority="Commercial source to be selected",
        access_mode=AccessMode.LICENSED,
        homepage="",
        implemented=False,
        requirements=(
            "government-provided or approved license",
            "API or export rights",
            "data-use, retention, and redistribution review",
        ),
        notes="Declared acquisition category only. No vendor is selected and no records are collected.",
    ),
    SourceDescriptor(
        source_id="company_intelligence_licensed",
        name="Company ownership, profile, and financial intelligence",
        authority="Commercial source to be selected",
        access_mode=AccessMode.LICENSED,
        homepage="",
        implemented=False,
        requirements=(
            "government-provided or approved license",
            "API or export rights",
            "data-use, retention, and redistribution review",
        ),
        notes="Declared acquisition category only. No vendor is selected and no records are collected.",
    ),
    SourceDescriptor(
        source_id="informal_literature_licensed",
        name="Informal literature, commercial news, and market research",
        authority="Commercial source to be selected",
        access_mode=AccessMode.LICENSED,
        homepage="",
        implemented=False,
        requirements=(
            "government-provided or approved license",
            "API or export rights",
            "data-use, retention, and redistribution review",
        ),
        notes="Declared acquisition category only. No vendor is selected and no records are collected.",
    ),
    SourceDescriptor(
        source_id="dtic_restricted",
        name="DTIC restricted collections",
        authority="Defense Technical Information Center",
        access_mode=AccessMode.MANUAL_TRANSFER,
        homepage="https://discover.dtic.mil/",
        implemented=False,
        requirements=("authorized account", "distribution review", "manual promotion"),
        notes="Declared only. Public and restricted content must not be mixed automatically.",
    ),
    SourceDescriptor(
        source_id="government_structured_reports",
        name="Structured Government acquisition and scientific reports",
        authority="Government source owner",
        access_mode=AccessMode.MANUAL_TRANSFER,
        homepage="",
        implemented=False,
        requirements=(
            "government-furnished access",
            "approved transfer",
            "distribution or CUI review",
            "source-specific schema and rights review",
        ),
        notes="Declared acquisition category only. No Government report records are collected.",
    ),
    SourceDescriptor(
        source_id="government_unstructured_reports",
        name="Unstructured Government reports and documents",
        authority="Government source owner",
        access_mode=AccessMode.MANUAL_TRANSFER,
        homepage="",
        implemented=False,
        requirements=(
            "government-furnished access",
            "approved transfer",
            "distribution or CUI review",
            "document-rights and marking review",
        ),
        notes="Declared acquisition category only. No Government report documents are collected.",
    ),
    SourceDescriptor(
        source_id="restricted_opportunity_documents",
        name="Restricted opportunity documents and controlled attachments",
        authority="Government source owner",
        access_mode=AccessMode.EXCLUDED,
        homepage="https://sam.gov/",
        implemented=False,
        requirements=(
            "explicit source-owner authorization",
            "distribution review",
            "approved Government processing boundary",
        ),
        notes=(
            "Intentionally excluded from the current collection. Public opportunity "
            "metadata remains separate; protected attachments and controlled documents "
            "are not fetched, indexed, embedded, or used for training."
        ),
    ),
)

SOURCE_REGISTRY = {source.source_id: source for source in _SOURCES}


def list_sources() -> tuple[SourceDescriptor, ...]:
    return _SOURCES


def get_source(source_id: str) -> SourceDescriptor:
    try:
        return SOURCE_REGISTRY[source_id]
    except KeyError as error:
        raise KeyError(f"unknown source: {source_id}") from error


def create_connector(source_id: str, **options: Any) -> Any:
    descriptor = get_source(source_id)
    if not descriptor.implemented:
        requirements = ", ".join(descriptor.requirements) or "source approval"
        raise RuntimeError(
            f"{source_id} is declared but not enabled; required: {requirements}"
        )
    if source_id == "usaspending":
        return (
            UsaSpendingConnector(endpoint=options.get("endpoint") or None)
            if options.get("endpoint")
            else UsaSpendingConnector()
        )
    if source_id == "sbir":
        return SbirFullCsvConnector(
            archive_url=options.get("archive_url")
            or "https://data.www.sbir.gov/mod_awarddatapublic/award_data.csv",
            max_download_bytes=int(
                options.get("max_download_bytes") or 512 * 1024 * 1024
            ),
            branch_filter=options.get("branch_filter", "navy"),
        )
    if source_id == "crossref":
        kwargs = {"mailto": options.get("mailto")}
        if options.get("endpoint"):
            kwargs["endpoint"] = options["endpoint"]
        return CrossrefConnector(**kwargs)
    if source_id == "openalex":
        kwargs = {"mailto": options.get("mailto"), "api_key": options.get("api_key")}
        if options.get("endpoint"):
            kwargs["endpoint"] = options["endpoint"]
        return OpenAlexConnector(**kwargs)
    if source_id == "pubmed":
        kwargs = {
            "email": options.get("mailto"),
            "api_key": options.get("ncbi_api_key"),
            "grant_query": options.get("grant_query") or "N00014[Grant Number]",
        }
        if options.get("endpoint"):
            kwargs["search_endpoint"] = options["endpoint"]
        if options.get("detail_endpoint"):
            kwargs["fetch_endpoint"] = options["detail_endpoint"]
        return PubMedConnector(**kwargs)
    if source_id == "osti":
        kwargs = {"sponsor_org": options.get("sponsor_org") or "Office of Naval Research"}
        if options.get("endpoint"):
            kwargs["endpoint"] = options["endpoint"]
        return OstiConnector(**kwargs)
    if source_id == "onr_website":
        kwargs = {}
        if options.get("endpoint"):
            kwargs["sitemap_endpoint"] = options["endpoint"]
        if options.get("robots_endpoint"):
            kwargs["robots_endpoint"] = options["robots_endpoint"]
        return OnrWebsiteConnector(**kwargs)
    if source_id == "sam_gov":
        kwargs = {
            "api_key": options.get("sam_api_key") or "",
            "organization_code": options.get("organization_code")
            or "017.1700.ONR",
            "organization_name": options.get("organization_name")
            or "OFFICE OF NAVAL RESEARCH",
        }
        if options.get("endpoint"):
            kwargs["endpoint"] = options["endpoint"]
        return SamGovConnector(**kwargs)
    if source_id == "uspto_patents":
        kwargs = {
            "api_key": options.get("uspto_odp_api_key") or "",
            "product_id": options.get("uspto_product_id") or "PVGPATDIS",
            "cache_dir": options.get("uspto_cache_dir")
            or ".cache/uspto-patentsview",
            "max_download_bytes": int(
                options.get("max_download_bytes") or 512 * 1024 * 1024
            ),
            "refresh_cache": bool(options.get("uspto_refresh_cache")),
        }
        if options.get("endpoint"):
            kwargs["endpoint"] = options["endpoint"]
        return UsptoPatentsConnector(**kwargs)
    if source_id == "grants_gov":
        kwargs = {
            "agency": options.get("agency") or "DOD-ONR",
            "fetch_details": options.get("fetch_details", True),
        }
        if options.get("endpoint"):
            kwargs["search_endpoint"] = options["endpoint"]
        if options.get("detail_endpoint"):
            kwargs["detail_endpoint"] = options["detail_endpoint"]
        return GrantsGovConnector(**kwargs)
    if source_id == "datacite":
        kwargs = {
            "funder_ror": options.get("funder_ror") or "https://ror.org/00rk2pe57"
        }
        if options.get("endpoint"):
            kwargs["endpoint"] = options["endpoint"]
        return DataCiteConnector(**kwargs)
    if source_id == "federal_register":
        kwargs = {
            "agency": options.get("agency") or "navy-department",
            "term": options.get("term") or '"Office of Naval Research"',
            "fetch_details": options.get("fetch_details", True),
        }
        if options.get("endpoint"):
            kwargs["search_endpoint"] = options["endpoint"]
        if options.get("detail_endpoint"):
            kwargs["detail_endpoint"] = options["detail_endpoint"]
        return FederalRegisterConnector(**kwargs)
    raise AssertionError(f"implemented source has no connector: {source_id}")

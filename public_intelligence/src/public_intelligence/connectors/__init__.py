"""Authoritative public-source connectors."""

from .base import CollectedRecord, CollectionRequest, SourceConnector
from .crossref import CrossrefConnector
from .datacite import DataCiteConnector
from .federal_register import FederalRegisterConnector
from .grants_gov import GrantsGovConnector
from .openalex import OpenAlexConnector
from .onr_website import OnrWebsiteConnector
from .osti import OstiConnector
from .pubmed import PubMedConnector
from .sam_gov import SamGovConnector
from .sbir import SbirFullCsvConnector
from .usaspending import UsaSpendingConnector
from .uspto_patents import UsptoPatentsConnector

__all__ = [
    "CollectedRecord",
    "CollectionRequest",
    "CrossrefConnector",
    "DataCiteConnector",
    "FederalRegisterConnector",
    "GrantsGovConnector",
    "OpenAlexConnector",
    "OnrWebsiteConnector",
    "OstiConnector",
    "PubMedConnector",
    "SamGovConnector",
    "SbirFullCsvConnector",
    "SourceConnector",
    "UsaSpendingConnector",
    "UsptoPatentsConnector",
]

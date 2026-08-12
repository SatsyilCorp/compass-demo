"""Compass public intelligence collection package."""

from .contracts import CanonicalRecord, Provenance
from .registry import AccessMode, SourceDescriptor, get_source, list_sources

__all__ = [
    "AccessMode",
    "CanonicalRecord",
    "Provenance",
    "SourceDescriptor",
    "get_source",
    "list_sources",
]

__version__ = "0.1.0"

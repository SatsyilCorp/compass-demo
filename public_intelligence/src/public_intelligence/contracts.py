"""Canonical contracts shared by every public source connector."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

from .provenance import canonical_record_hash


SCHEMA_VERSION = "1.0"
RECORD_TYPES = {
    "award",
    "publication",
    "dataset",
    "solicitation",
    "regulatory_notice",
    "organization",
    "patent",
    "web_page",
}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def _clean_strings(values: Iterable[Any]) -> tuple[str, ...]:
    unique: dict[str, None] = {}
    for value in values:
        text = _clean_text(value)
        if text:
            unique[text] = None
    return tuple(unique)


def _clean_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return {str(key): item for key, item in sorted(value.items()) if item is not None}


def parse_amount(value: Any) -> str | None:
    """Return a normalized decimal string without introducing float errors."""

    if value in (None, ""):
        return None
    raw = str(value).replace("$", "").replace(",", "").strip()
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None
    return format(amount.normalize(), "f")


@dataclass(frozen=True)
class Provenance:
    source_url: str
    retrieved_at: str
    snapshot_id: str
    source_payload_sha256: str
    record_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.source_url.startswith(("https://", "file://")):
            raise ValueError("source_url must use https:// or file://")
        parsed = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        for label, value in (
            ("snapshot_id", self.snapshot_id),
            ("source_payload_sha256", self.source_payload_sha256),
        ):
            if not value:
                raise ValueError(f"{label} is required")
        if len(self.source_payload_sha256) != 64:
            raise ValueError("source_payload_sha256 must be a SHA-256 hex digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "snapshot_id": self.snapshot_id,
            "source_payload_sha256": self.source_payload_sha256,
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True)
class CanonicalRecord:
    source_id: str
    source_record_id: str
    record_type: str
    title: str
    provenance: Provenance
    abstract: str | None = None
    published_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    organizations: tuple[str, ...] = field(default_factory=tuple)
    topics: tuple[str, ...] = field(default_factory=tuple)
    links: tuple[str, ...] = field(default_factory=tuple)
    identifiers: Mapping[str, Any] = field(default_factory=dict)
    geography: Mapping[str, Any] = field(default_factory=dict)
    funding_amount: str | None = None
    funding_currency: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_record_id:
            raise ValueError("source_id and source_record_id are required")
        if self.record_type not in RECORD_TYPES:
            raise ValueError(f"unsupported record_type: {self.record_type}")
        if not _clean_text(self.title):
            raise ValueError("title is required")

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_record_id: str,
        record_type: str,
        title: str,
        source_url: str,
        retrieved_at: str,
        snapshot_id: str,
        source_payload_sha256: str,
        abstract: str | None = None,
        published_date: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        organizations: Iterable[Any] = (),
        topics: Iterable[Any] = (),
        links: Iterable[Any] = (),
        identifiers: Mapping[str, Any] | None = None,
        geography: Mapping[str, Any] | None = None,
        funding_amount: Any = None,
        funding_currency: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> "CanonicalRecord":
        provenance = Provenance(
            source_url=source_url,
            retrieved_at=retrieved_at,
            snapshot_id=snapshot_id,
            source_payload_sha256=source_payload_sha256,
        )
        record = cls(
            source_id=source_id,
            source_record_id=str(source_record_id),
            record_type=record_type,
            title=_clean_text(title) or "Untitled record",
            abstract=_clean_text(abstract),
            published_date=_clean_text(published_date),
            start_date=_clean_text(start_date),
            end_date=_clean_text(end_date),
            organizations=_clean_strings(organizations),
            topics=_clean_strings(topics),
            links=_clean_strings(links),
            identifiers=_clean_mapping(identifiers),
            geography=_clean_mapping(geography),
            funding_amount=parse_amount(funding_amount),
            funding_currency=_clean_text(funding_currency),
            attributes=_clean_mapping(attributes),
            provenance=provenance,
        )
        digest = canonical_record_hash(record.to_dict())
        return cls(
            **{
                **record.__dict__,
                "provenance": Provenance(
                    **{**provenance.__dict__, "record_sha256": digest}
                ),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_record_id": self.source_record_id,
            "record_type": self.record_type,
            "title": self.title,
            "abstract": self.abstract,
            "published_date": self.published_date,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "organizations": list(self.organizations),
            "topics": list(self.topics),
            "links": list(self.links),
            "identifiers": dict(self.identifiers),
            "geography": dict(self.geography),
            "funding_amount": self.funding_amount,
            "funding_currency": self.funding_currency,
            "attributes": dict(self.attributes),
            "provenance": self.provenance.to_dict(),
        }

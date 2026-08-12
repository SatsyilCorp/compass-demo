"""Connector protocols and shared collection controls."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Iterator, Mapping, Protocol

from ..contracts import CanonicalRecord
from ..http import HttpTransport


@dataclass(frozen=True)
class CollectionRequest:
    max_records: int
    page_size: int
    snapshot_id: str
    retrieved_at: str
    max_pages: int = 10_000
    query: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_records <= 0:
            raise ValueError("max_records must be positive")
        if not 1 <= self.page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000")
        if not 1 <= self.max_pages <= 100_000:
            raise ValueError("max_pages must be between 1 and 100000")
        if not self.snapshot_id:
            raise ValueError("snapshot_id is required")


@dataclass(frozen=True)
class CollectedRecord:
    record: CanonicalRecord
    checkpoint: Mapping[str, Any]


class SourceConnector(Protocol):
    source_id: str
    exhausted: bool

    def collect(
        self,
        http: HttpTransport,
        request: CollectionRequest,
        checkpoint: Mapping[str, Any] | None = None,
    ) -> Iterator[CollectedRecord]: ...


def first_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def date_parts(value: Any) -> str | None:
    """Normalize Crossref-style date-parts or scalar dates."""

    if not value:
        return None
    if isinstance(value, Mapping):
        parts = value.get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list):
            values = parts[0]
            if values:
                year = int(values[0])
                month = int(values[1]) if len(values) > 1 else 1
                day = int(values[2]) if len(values) > 2 else 1
                return f"{year:04d}-{month:02d}-{day:02d}"
    text = str(value).strip()
    return text or None


def inverted_abstract(index: Mapping[str, Any] | None) -> str | None:
    """Rebuild an OpenAlex inverted abstract without retaining token positions."""

    if not index:
        return None
    positioned: list[tuple[int, str]] = []
    for token, positions in index.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            try:
                positioned.append((int(position), str(token)))
            except (TypeError, ValueError):
                continue
    positioned.sort(key=lambda item: item[0])
    return " ".join(token for _, token in positioned) or None


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: Any) -> str | None:
    """Convert public HTML fragments to compact text safe for downstream UIs."""

    if value in (None, ""):
        return None
    parser = _PlainTextParser()
    try:
        parser.feed(str(value))
        parser.close()
    except (ValueError, AssertionError):
        return " ".join(str(value).split()) or None
    return " ".join(" ".join(parser.parts).split()) or None


def normalize_public_date(value: Any) -> str | None:
    """Normalize common public API date forms to an ISO calendar date."""

    if value in (None, ""):
        return None
    text = " ".join(str(value).split()).strip()
    if len(text) >= 10:
        prefix = text[:10]
        try:
            return datetime.strptime(prefix, "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    for pattern in (
        "%m/%d/%Y",
        "%b %d, %Y",
        "%b %d, %Y %I:%M:%S %p %Z",
        "%b %d, %Y %I:%M:%S %p",
        "%Y",
    ):
        candidate = text
        if pattern == "%b %d, %Y %I:%M:%S %p" and text.rsplit(" ", 1)[-1].isalpha():
            candidate = text.rsplit(" ", 1)[0]
        try:
            return datetime.strptime(candidate, pattern).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None

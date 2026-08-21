"""Bounded connector for the official ONR public HTML sitemap."""

from __future__ import annotations

import hashlib
import re
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser
from typing import Any, Iterator, Mapping

from ..contracts import CanonicalRecord
from ..http import HttpTransport
from ..pii import sanitize_mapping
from ..provenance import sha256_json
from .base import CollectedRecord, CollectionRequest, plain_text


DEFAULT_ORIGIN = "https://www.onr.navy.mil"
DEFAULT_SITEMAP_ENDPOINT = f"{DEFAULT_ORIGIN}/sitemap"
DEFAULT_ROBOTS_ENDPOINT = f"{DEFAULT_ORIGIN}/robots.txt"
ALLOWED_HOST = "www.onr.navy.mil"
EXCLUDED_EXTENSIONS = (
    ".ashx",
    ".doc",
    ".docx",
    ".pdf",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".zip",
)
EXCLUDED_PATH_PARTS = (
    "/admin/",
    "/career-job-opportunity/",
    "/contact",
    "/employment-global",
    "/global-locations",
    "/locations-global/",
    "/media/document/",
    "/our-program-officers",
    "/science-directors",
    "/search",
    "/visit-onr",
    "/work-with-us/careers",
    "/work-with-us/manage-your-award/administration-lookup",
)
EXCLUDED_TITLE_TERMS = (
    "administration lookup",
    "career",
    "code 31 contacts",
    "code 32 contacts",
    "code 33 contacts",
    "code 34 contacts",
    "code 35 contacts",
    "employment opportunities",
    "media inquiries",
    "onr program managers",
    "vacancy announcements",
    "visiting onr",
)


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return " ".join(str(value).replace("\u2014", " - ").split()) or None


def _canonical_url(href: str, origin: str) -> str | None:
    absolute = urllib.parse.urljoin(f"{origin.rstrip('/')}/", href)
    parsed = urllib.parse.urlsplit(absolute)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if parsed.username or parsed.password or port not in (None, 443):
        return None
    if parsed.query or parsed.fragment:
        return None
    path = parsed.path or "/"
    if path.casefold().endswith(EXCLUDED_EXTENSIONS):
        return None
    lowered = path.casefold()
    if any(part in lowered for part in EXCLUDED_PATH_PARTS):
        return None
    return urllib.parse.urlunsplit(("https", ALLOWED_HOST, path, "", ""))


def _page_kind(path: str) -> str:
    if path.startswith("/organization/departments/"):
        return "research_program"
    if path.startswith("/work-with-us/funding-opportunities"):
        return "funding_opportunity"
    if path.startswith("/education-outreach/sponsored-research"):
        return "sponsored_research"
    if path.startswith("/media-center/news-releases"):
        return "news_release_index"
    if path.startswith("/organization/"):
        return "organization"
    if path.startswith("/work-with-us/"):
        return "industry_engagement"
    if path.startswith("/education-outreach/"):
        return "education_outreach"
    if path.startswith("/about-onr/"):
        return "institutional_information"
    return "official_site_page"


class _SitemapParser(HTMLParser):
    """Extract only anchors inside Drupal's main-menu sitemap block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_sitemap = False
        self.sitemap_div_depth = 0
        self.li_stack: list[str | None] = []
        self.anchor: dict[str, Any] | None = None
        self.entries: list[dict[str, Any]] = []

    @staticmethod
    def _attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self._attributes(attrs)
        if tag == "div":
            classes = set(values.get("class", "").split())
            if not self.in_sitemap and "sitemap-item--menu-main" in classes:
                self.in_sitemap = True
                self.sitemap_div_depth = 1
                return
            if self.in_sitemap:
                self.sitemap_div_depth += 1
        if not self.in_sitemap:
            return
        if tag == "li":
            self.li_stack.append(None)
        elif tag == "a" and self.li_stack:
            self.anchor = {
                "href": values.get("href", ""),
                "node_path": values.get("data-drupal-link-system-path", ""),
                "parts": [],
            }

    def handle_data(self, data: str) -> None:
        if self.anchor is not None:
            self.anchor["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.in_sitemap:
            return
        if tag == "a" and self.anchor is not None:
            title = plain_text("".join(self.anchor["parts"]))
            if title and self.li_stack:
                hierarchy = [value for value in self.li_stack[:-1] if value]
                self.li_stack[-1] = title
                self.entries.append(
                    {
                        "href": self.anchor["href"],
                        "node_path": self.anchor["node_path"],
                        "title": title,
                        "hierarchy": [*hierarchy, title],
                    }
                )
            self.anchor = None
        elif tag == "li" and self.li_stack:
            self.li_stack.pop()
        elif tag == "div":
            self.sitemap_div_depth -= 1
            if self.sitemap_div_depth <= 0:
                self.in_sitemap = False


class OnrWebsiteConnector:
    """Collect page headings from the official ONR sitemap without page crawling."""

    source_id = "onr_website"

    def __init__(
        self,
        sitemap_endpoint: str = DEFAULT_SITEMAP_ENDPOINT,
        *,
        robots_endpoint: str = DEFAULT_ROBOTS_ENDPOINT,
    ) -> None:
        self.origin = DEFAULT_ORIGIN
        self.sitemap_endpoint = sitemap_endpoint
        self.robots_endpoint = robots_endpoint
        for label, endpoint, expected_path in (
            ("sitemap", sitemap_endpoint, "/sitemap"),
            ("robots", robots_endpoint, "/robots.txt"),
        ):
            parsed = urllib.parse.urlsplit(endpoint)
            if (
                parsed.scheme != "https"
                or parsed.hostname != ALLOWED_HOST
                or parsed.path != expected_path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    f"ONR {label} endpoint must be the official {DEFAULT_ORIGIN}{expected_path} URL"
                )
        self.exhausted = False

    def _robot_policy(self, robots_text: str) -> urllib.robotparser.RobotFileParser:
        policy = urllib.robotparser.RobotFileParser()
        policy.set_url(self.robots_endpoint)
        policy.parse(robots_text.splitlines())
        return policy

    @staticmethod
    def _node_id(value: Any) -> str | None:
        match = re.fullmatch(r"node/(\d+)", str(value or ""))
        return match.group(1) if match else None

    def _record(
        self,
        entry: Mapping[str, Any],
        *,
        canonical_url: str,
        sitemap_sha256: str,
        robots_sha256: str,
        request: CollectionRequest,
    ) -> CanonicalRecord:
        parsed = urllib.parse.urlsplit(canonical_url)
        path = parsed.path
        title = _text(entry.get("title")) or path
        hierarchy = [_text(value) for value in entry.get("hierarchy") or []]
        hierarchy = [value for value in hierarchy if value]
        page_kind = _page_kind(path)
        department_match = re.search(r"/departments/code-(\d+)", path)
        department_code = department_match.group(1) if department_match else None
        safe_payload = {
            "title": title,
            "canonical_url": canonical_url,
            "path": path,
            "node_id": self._node_id(entry.get("node_path")),
            "hierarchy": hierarchy,
            "page_kind": page_kind,
            "department_code": department_code,
            "sitemap_sha256": sitemap_sha256,
            "robots_sha256": robots_sha256,
        }
        safe_payload, report = sanitize_mapping(safe_payload)
        return CanonicalRecord.create(
            source_id=self.source_id,
            source_record_id=str(
                safe_payload.get("node_id")
                or hashlib.sha256(path.encode()).hexdigest()[:24]
            ),
            record_type="web_page",
            title=str(safe_payload["title"]),
            organizations=["Office of Naval Research"],
            topics=[page_kind, department_code, *hierarchy[:-1]],
            links=[canonical_url],
            identifiers={
                "onr_site_path": path,
                "drupal_node_id": safe_payload.get("node_id"),
            },
            attributes={
                "page_kind": page_kind,
                "department_code": department_code,
                "site_hierarchy": hierarchy,
                "content_date_available": False,
                "linked_page_fetched": False,
                "document_content_fetched": False,
                "personnel_and_contact_pages_excluded": True,
                "robots_checked": True,
                "robots_sha256": robots_sha256,
                "sitemap_sha256": sitemap_sha256,
                "rights_note": (
                    "Official U.S. Navy public website index metadata. Linked page "
                    "bodies and documents were not collected."
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
        self.exhausted = False
        robots_text = http.get_text(self.robots_endpoint)
        policy = self._robot_policy(robots_text)
        user_agent = "CompassPublicIntelligence"
        if not policy.can_fetch(user_agent, self.sitemap_endpoint):
            raise RuntimeError("ONR robots.txt disallows the public sitemap")

        sitemap_text = http.get_text(self.sitemap_endpoint)
        parser = _SitemapParser()
        parser.feed(sitemap_text)
        parser.close()
        if not parser.entries:
            raise RuntimeError(
                "ONR public sitemap did not contain indexed page headings"
            )

        sitemap_sha256 = hashlib.sha256(sitemap_text.encode("utf-8")).hexdigest()
        robots_sha256 = hashlib.sha256(robots_text.encode("utf-8")).hexdigest()
        state = dict(checkpoint or {})
        previous_digest = state.get("sitemap_sha256")
        if previous_digest and previous_digest != sitemap_sha256:
            raise RuntimeError("ONR sitemap changed since the checkpoint; use --fresh")

        offset = max(0, int(state.get("offset", 0)))
        emitted = 0
        seen: set[str] = set()
        for index, entry in enumerate(parser.entries):
            canonical_url = _canonical_url(str(entry.get("href") or ""), self.origin)
            if not canonical_url:
                continue
            if canonical_url in seen:
                continue
            seen.add(canonical_url)
            title = str(entry.get("title") or "").casefold()
            if any(term in title for term in EXCLUDED_TITLE_TERMS):
                continue
            if not policy.can_fetch(user_agent, canonical_url):
                continue
            if index < offset:
                continue
            if emitted >= request.max_records:
                return
            emitted += 1
            yield CollectedRecord(
                record=self._record(
                    entry,
                    canonical_url=canonical_url,
                    sitemap_sha256=sitemap_sha256,
                    robots_sha256=robots_sha256,
                    request=request,
                ),
                checkpoint={"offset": index + 1, "sitemap_sha256": sitemap_sha256},
            )
        self.exhausted = True

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Mapping

from public_intelligence.http import OpenedStream


FIXTURES = Path(__file__).parent / "fixtures"


def json_fixture(name: str) -> Any:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class FakeHttp:
    def __init__(
        self,
        *,
        get_responses: list[Any] | None = None,
        text_responses: list[str] | None = None,
        post_responses: list[Any] | None = None,
        stream_path: Path | None = None,
        source_version: str = '"fixture-v1"',
    ) -> None:
        self.get_responses = list(get_responses or [])
        self.text_responses = list(text_responses or [])
        self.post_responses = list(post_responses or [])
        self.stream_path = stream_path
        self.source_version = source_version
        self.calls: list[tuple[str, str, Any]] = []

    def get_json(self, url: str, *, params: Mapping[str, Any] | None = None) -> Any:
        self.calls.append(("GET", url, dict(params or {})))
        if not self.get_responses:
            raise AssertionError("unexpected GET")
        return self.get_responses.pop(0)

    def get_text(self, url: str, *, params: Mapping[str, Any] | None = None) -> str:
        self.calls.append(("GET_TEXT", url, dict(params or {})))
        if not self.text_responses:
            raise AssertionError("unexpected GET_TEXT")
        return self.text_responses.pop(0)

    def post_json(self, url: str, body: Mapping[str, Any]) -> Any:
        self.calls.append(("POST", url, dict(body)))
        if not self.post_responses:
            raise AssertionError("unexpected POST")
        return self.post_responses.pop(0)

    def open_stream(
        self,
        url: str,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> OpenedStream:
        self.calls.append(
            (
                "STREAM",
                url,
                {"max_bytes": max_bytes, "header_names": sorted(headers or {})},
            )
        )
        if self.stream_path is None:
            raise AssertionError("unexpected stream")
        payload = self.stream_path.read_bytes()
        if len(payload) > max_bytes:
            raise RuntimeError("fixture exceeds byte cap")
        return OpenedStream(io.BytesIO(payload), {"ETag": self.source_version}, url)

    def download(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> Path:
        raise AssertionError("raw downloads are not permitted in connector tests")

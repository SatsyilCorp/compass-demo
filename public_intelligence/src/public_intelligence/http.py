"""Rate-limited HTTP with bounded retries and resumable downloads."""

from __future__ import annotations

import email.utils
import http.client
import io
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping, Protocol


RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api-key",
    "api_key",
    "apikey",
    "key",
    "token",
}


class HttpFailure(RuntimeError):
    pass


class HttpTransport(Protocol):
    def get_json(self, url: str, *, params: Mapping[str, Any] | None = None) -> Any: ...

    def get_text(self, url: str, *, params: Mapping[str, Any] | None = None) -> str: ...

    def post_json(self, url: str, body: Mapping[str, Any]) -> Any: ...

    def download(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> Path: ...

    def open_stream(
        self,
        url: str,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> "OpenedStream": ...


class BoundedBinaryStream(io.RawIOBase):
    """Readable raw stream that enforces a response byte limit."""

    def __init__(self, stream: BinaryIO, max_bytes: int) -> None:
        super().__init__()
        self._stream = stream
        self._max_bytes = max_bytes
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        chunk = self._stream.read(len(buffer))
        if not chunk:
            return 0
        self.bytes_read += len(chunk)
        if self.bytes_read > self._max_bytes:
            raise HttpFailure("stream exceeded the configured byte limit")
        buffer[: len(chunk)] = chunk
        return len(chunk)

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            super().close()


class OpenedStream:
    def __init__(self, stream: BinaryIO, headers: Mapping[str, str], url: str) -> None:
        self.stream = stream
        self.headers = headers
        self.url = url

    @property
    def source_version(self) -> str | None:
        lowered = {str(key).casefold(): value for key, value in self.headers.items()}
        return lowered.get("etag") or lowered.get("last-modified")

    def __enter__(self) -> "OpenedStream":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.stream.close()


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 5
    initial_backoff_seconds: float = 1.0
    maximum_backoff_seconds: float = 30.0
    jitter_ratio: float = 0.2

    def backoff(self, attempt: int) -> float:
        base = min(self.maximum_backoff_seconds, self.initial_backoff_seconds * (2**attempt))
        jitter = base * self.jitter_ratio * random.random()
        return base + jitter


class RateLimiter:
    def __init__(
        self,
        requests_per_second: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self._minimum_interval = 1.0 / requests_per_second
        self._clock = clock
        self._sleeper = sleeper
        self._last_request: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last_request is not None:
            delay = self._minimum_interval - (now - self._last_request)
            if delay > 0:
                self._sleeper(delay)
                now = self._clock()
        self._last_request = now


class RetryHttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        requests_per_second: float = 2.0,
        timeout_seconds: float = 60.0,
        retry_policy: RetryPolicy | None = None,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("a descriptive user agent is required")
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self._opener = opener
        self._sleeper = sleeper
        self._limiter = RateLimiter(requests_per_second, sleeper=sleeper)

    @staticmethod
    def _with_params(url: str, params: Mapping[str, Any] | None) -> str:
        if not params:
            return url
        values = {key: value for key, value in params.items() if value is not None}
        parsed = urllib.parse.urlsplit(url)
        existing = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        merged = [*existing, *values.items()]
        return urllib.parse.urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urllib.parse.urlencode(merged, doseq=True),
                parsed.fragment,
            )
        )

    @staticmethod
    def _safe_url(url: str) -> str:
        """Redact credentials from URLs before they enter errors or logs."""

        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        safe_query = [
            (key, "[REDACTED]" if key.casefold() in SENSITIVE_QUERY_KEYS else value)
            for key, value in query
        ]
        return urllib.parse.urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                urllib.parse.urlencode(safe_query, doseq=True),
                parsed.fragment,
            )
        )

    def _retry_after(self, headers: Mapping[str, str] | None) -> float | None:
        if not headers:
            return None
        raw = headers.get("Retry-After")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            try:
                retry_at = email.utils.parsedate_to_datetime(raw)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                return None

    def _open_with_retry(self, request: urllib.request.Request) -> Any:
        last_error: Exception | None = None
        safe_url = self._safe_url(request.full_url)
        for attempt in range(self.retry_policy.attempts):
            self._limiter.wait()
            try:
                return self._opener(request, timeout=self.timeout_seconds)
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in RETRYABLE_STATUS or attempt + 1 >= self.retry_policy.attempts:
                    raise HttpFailure(f"HTTP {error.code} for {safe_url}") from None
                retry_after = self._retry_after(error.headers)
                delay = retry_after if retry_after is not None else self.retry_policy.backoff(attempt)
                error.close()
                self._sleeper(delay)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                last_error = error
                if attempt + 1 >= self.retry_policy.attempts:
                    raise HttpFailure(
                        f"request failed for {safe_url}: {type(error).__name__}"
                    ) from None
                self._sleeper(self.retry_policy.backoff(attempt))
        error_name = type(last_error).__name__ if last_error else "unknown error"
        raise HttpFailure(f"request failed for {safe_url}: {error_name}")

    def _json_request(
        self,
        url: str,
        *,
        method: str,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            method=method,
            data=encoded,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
        )
        response = self._open_with_retry(request)
        try:
            payload = response.read()
        finally:
            response.close()
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HttpFailure(f"invalid JSON from {self._safe_url(url)}") from error

    def get_json(self, url: str, *, params: Mapping[str, Any] | None = None) -> Any:
        return self._json_request(self._with_params(url, params), method="GET")

    def get_text(self, url: str, *, params: Mapping[str, Any] | None = None) -> str:
        resolved = self._with_params(url, params)
        safe_url = self._safe_url(resolved)
        payload: bytes | None = None
        last_error: Exception | None = None
        for attempt in range(self.retry_policy.attempts):
            request = urllib.request.Request(
                resolved,
                method="GET",
                headers={
                    "Accept": "application/xml,text/xml,text/plain",
                    "User-Agent": self.user_agent,
                },
            )
            response = self._open_with_retry(request)
            try:
                chunks: list[bytes] = []
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 32 * 1024 * 1024:
                        raise HttpFailure("text response exceeded the 32 MiB limit")
                    chunks.append(chunk)
                payload = b"".join(chunks)
                break
            except (http.client.IncompleteRead, ConnectionError, OSError) as error:
                last_error = error
                if attempt + 1 >= self.retry_policy.attempts:
                    raise HttpFailure(f"incomplete text response from {safe_url}") from error
                self._sleeper(self.retry_policy.backoff(attempt))
            finally:
                response.close()
        if payload is None:
            error_name = type(last_error).__name__ if last_error else "unknown error"
            raise HttpFailure(f"text request failed for {safe_url}: {error_name}")
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise HttpFailure(f"invalid UTF-8 text from {safe_url}") from error

    def post_json(self, url: str, body: Mapping[str, Any]) -> Any:
        return self._json_request(url, method="POST", body=body)

    def download(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> Path:
        """Download to a cache file, resuming a partial file when supported."""

        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.stat().st_size > max_bytes:
                raise HttpFailure("cached file exceeds the configured byte limit")
            return destination

        partial = destination.with_suffix(destination.suffix + ".part")
        last_error: Exception | None = None
        for attempt in range(self.retry_policy.attempts):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > max_bytes:
                raise HttpFailure("partial download exceeds the configured byte limit")
            request_headers = {
                "Accept": "text/csv,application/zip,*/*",
                "User-Agent": self.user_agent,
                **dict(headers or {}),
            }
            if offset:
                request_headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(
                url,
                method="GET",
                headers=request_headers,
            )
            response = None
            try:
                response = self._open_with_retry(request)
                status = int(getattr(response, "status", response.getcode()))
                append = offset > 0 and status == 206
                if offset > 0 and not append:
                    offset = 0
                content_length = response.headers.get("Content-Length")
                if content_length and offset + int(content_length) > max_bytes:
                    raise HttpFailure("remote file exceeds the configured byte limit")
                mode = "ab" if append else "wb"
                total = offset
                with partial.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise HttpFailure("download exceeded the configured byte limit")
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(partial, destination)
                return destination
            except HttpFailure:
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
                last_error = error
                if attempt + 1 >= self.retry_policy.attempts:
                    break
                self._sleeper(self.retry_policy.backoff(attempt))
            finally:
                if response is not None:
                    response.close()
        error_name = type(last_error).__name__ if last_error else "unknown error"
        raise HttpFailure(
            f"download failed for {self._safe_url(url)}: {error_name}"
        )

    def open_stream(
        self,
        url: str,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> OpenedStream:
        """Open a bounded response without writing it to local storage."""

        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "text/csv,*/*",
                "User-Agent": self.user_agent,
                **dict(headers or {}),
            },
        )
        response = self._open_with_retry(request)
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            response.close()
            raise HttpFailure("remote stream exceeds the configured byte limit")
        headers = {str(key): str(value) for key, value in response.headers.items()}
        return OpenedStream(BoundedBinaryStream(response, max_bytes), headers, url)

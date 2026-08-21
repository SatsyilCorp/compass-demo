from __future__ import annotations

import gzip
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from public_intelligence.contracts import CanonicalRecord
from public_intelligence.http import BoundedBinaryStream, HttpFailure, RetryHttpClient, RetryPolicy
from public_intelligence.provenance import sha256_json
from public_intelligence.writers import GzipJsonlWriter, JsonlWriter, WriterDependencyError, create_writer


class FakeResponse:
    def __init__(self, value: bytes, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._value = io.BytesIO(value)
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self, size: int = -1) -> bytes:
        return self._value.read(size)

    def close(self) -> None:
        self._value.close()

    def getcode(self) -> int:
        return self.status


def record(identifier: str) -> CanonicalRecord:
    payload = {"id": identifier}
    return CanonicalRecord.create(
        source_id="fixture",
        source_record_id=identifier,
        record_type="dataset",
        title=f"Record {identifier}",
        source_url=f"https://example.org/{identifier}",
        retrieved_at="2026-08-11T12:00:00Z",
        snapshot_id="writer-test",
        source_payload_sha256=sha256_json(payload),
    )


class HttpAndWriterTests(unittest.TestCase):
    def test_http_retries_429_and_honors_retry_after(self) -> None:
        calls = []
        sleeps = []

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "rate limited",
                    {"Retry-After": "0"},
                    None,
                )
            return FakeResponse(b'{"ok": true}')

        client = RetryHttpClient(
            user_agent="offline-test",
            requests_per_second=1000,
            retry_policy=RetryPolicy(attempts=2, initial_backoff_seconds=0, jitter_ratio=0),
            opener=opener,
            sleeper=sleeps.append,
        )
        self.assertEqual(client.get_json("https://example.org/api"), {"ok": True})
        self.assertEqual(len(calls), 2)

    def test_http_merges_params_with_an_existing_query(self) -> None:
        rendered = RetryHttpClient._with_params(
            "https://example.org/works?filter=funder:ONR",
            {"cursor": "*", "per-page": 200},
        )
        self.assertEqual(
            rendered,
            "https://example.org/works?filter=funder%3AONR&cursor=%2A&per-page=200",
        )

    def test_http_redacts_api_key_from_failure_messages(self) -> None:
        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                403,
                "forbidden",
                {},
                None,
            )

        client = RetryHttpClient(
            user_agent="offline-test",
            requests_per_second=1000,
            retry_policy=RetryPolicy(attempts=1),
            opener=opener,
        )
        with self.assertRaises(HttpFailure) as raised:
            client.get_json(
                "https://example.org/api",
                params={"api_key": "fixture-secret", "organizationCode": "ONR"},
            )
        message = str(raised.exception)
        self.assertNotIn("fixture-secret", message)
        self.assertIn("api_key=%5BREDACTED%5D", message)
        self.assertIsNone(raised.exception.__cause__)

    def test_download_applies_api_key_header_without_putting_it_in_url(self) -> None:
        captured = []

        def opener(request, timeout):
            captured.append(request)
            return FakeResponse(b"zip", headers={"Content-Length": "3"})

        client = RetryHttpClient(
            user_agent="offline-test",
            requests_per_second=1000,
            opener=opener,
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source.zip"
            client.download(
                "https://example.org/source.zip",
                destination,
                max_bytes=10,
                headers={"X-API-Key": "fixture-secret"},
            )
        self.assertEqual(captured[0].get_header("X-api-key"), "fixture-secret")
        self.assertNotIn("fixture-secret", captured[0].full_url)

    def test_bounded_stream_fails_before_returning_overage(self) -> None:
        stream = BoundedBinaryStream(io.BytesIO(b"123456"), max_bytes=5)
        buffered = io.BufferedReader(stream)
        with self.assertRaises(HttpFailure):
            buffered.read()

    def test_plain_jsonl_truncates_uncheckpointed_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            writer = JsonlWriter(path)
            writer.prepare_resume(0)
            writer.write_batch([record("1"), record("2")])
            writer.write_batch([record("3")])
            writer.prepare_resume(2)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)

    def test_gzip_jsonl_is_readable_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl.gz"
            writer = GzipJsonlWriter(path)
            writer.prepare_resume(0)
            writer.write_batch([record("1"), record("2")])
            writer.write_batch([record("3")])
            writer.prepare_resume(2)
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                values = [json.loads(line) for line in handle]
            self.assertEqual([value["source_record_id"] for value in values], ["1", "2"])
            writer.write_batch([record("3")])
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                self.assertEqual(len(list(handle)), 3)

    def test_parquet_has_clear_optional_dependency_error(self) -> None:
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(WriterDependencyError):
                    create_writer(Path(directory) / "dataset", "parquet")


if __name__ == "__main__":
    unittest.main()

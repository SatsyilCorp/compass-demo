"""Resumable JSONL, gzip JSONL, and Parquet dataset writers."""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Protocol

from .contracts import CanonicalRecord
from .provenance import canonical_json_bytes


class WriterDependencyError(RuntimeError):
    pass


class RecordWriter(Protocol):
    records_written: int

    def prepare_resume(self, expected_records: int) -> None: ...

    def write_batch(self, records: Iterable[CanonicalRecord]) -> int: ...


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.records_written = 0

    def prepare_resume(self, expected_records: int) -> None:
        if expected_records < 0:
            raise ValueError("expected_records cannot be negative")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            if expected_records:
                raise RuntimeError("checkpoint references a missing JSONL output")
            self.path.touch()
            self.records_written = 0
            return
        line_count = 0
        truncate_at = 0
        with self.path.open("rb") as handle:
            while line_count < expected_records:
                line = handle.readline()
                if not line:
                    raise RuntimeError("JSONL output contains fewer records than its checkpoint")
                line_count += 1
                truncate_at = handle.tell()
            if expected_records == 0:
                truncate_at = 0
        with self.path.open("r+b") as handle:
            handle.truncate(truncate_at)
        self.records_written = expected_records

    def write_batch(self, records: Iterable[CanonicalRecord]) -> int:
        values = list(records)
        if not values:
            return 0
        with self.path.open("ab") as handle:
            for record in values:
                handle.write(canonical_json_bytes(record.to_dict()))
                handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.records_written += len(values)
        return len(values)


class GzipJsonlWriter:
    """Append one deterministic gzip member per committed batch.

    A sidecar manifest stores the byte boundary for every committed member.
    Resume truncates data and manifest back to the checkpoint, including after
    a process exits between data fsync and checkpoint save.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.manifest_path = path.with_suffix(path.suffix + ".manifest.json")
        self.records_written = 0
        self._parts: list[dict[str, int]] = []

    def _load_manifest(self) -> list[dict[str, int]]:
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if value.get("version") != 1:
            raise RuntimeError("unsupported gzip JSONL manifest version")
        return [dict(part) for part in value.get("parts") or []]

    def _save_manifest(self) -> None:
        _atomic_json(self.manifest_path, {"version": 1, "parts": self._parts})

    def prepare_resume(self, expected_records: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        parts = self._load_manifest()
        retained = [part for part in parts if int(part["end_record"]) <= expected_records]
        retained_count = int(retained[-1]["end_record"]) if retained else 0
        if retained_count != expected_records:
            if expected_records:
                raise RuntimeError("gzip JSONL checkpoint is not at a committed batch boundary")
        byte_end = int(retained[-1]["byte_end"]) if retained else 0
        if not self.path.exists():
            if expected_records:
                raise RuntimeError("checkpoint references a missing gzip JSONL output")
            self.path.touch()
        with self.path.open("r+b") as handle:
            handle.truncate(byte_end)
        self._parts = retained
        self.records_written = expected_records
        self._save_manifest()

    def write_batch(self, records: Iterable[CanonicalRecord]) -> int:
        values = list(records)
        if not values:
            return 0
        raw = b"".join(canonical_json_bytes(record.to_dict()) + b"\n" for record in values)
        member = gzip.compress(raw, compresslevel=6, mtime=0)
        start = self.records_written
        with self.path.open("ab") as handle:
            handle.write(member)
            handle.flush()
            os.fsync(handle.fileno())
            byte_end = handle.tell()
        self.records_written += len(values)
        self._parts.append(
            {
                "start_record": start,
                "end_record": self.records_written,
                "byte_end": byte_end,
            }
        )
        self._save_manifest()
        return len(values)


class ParquetDatasetWriter:
    """Write one atomic Parquet part per committed batch."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.manifest_path = directory / "manifest.json"
        self.records_written = 0
        self._parts: list[dict[str, Any]] = []
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as error:
            raise WriterDependencyError(
                "Parquet output requires the optional pyarrow dependency"
            ) from error
        self._pa = pa
        self._pq = pq
        self._schema = pa.schema(
            [
                ("schema_version", pa.string()),
                ("source_id", pa.string()),
                ("source_record_id", pa.string()),
                ("record_type", pa.string()),
                ("title", pa.string()),
                ("abstract", pa.string()),
                ("published_date", pa.string()),
                ("start_date", pa.string()),
                ("end_date", pa.string()),
                ("funding_amount", pa.string()),
                ("funding_currency", pa.string()),
                ("organizations_json", pa.string()),
                ("topics_json", pa.string()),
                ("links_json", pa.string()),
                ("identifiers_json", pa.string()),
                ("geography_json", pa.string()),
                ("attributes_json", pa.string()),
                ("provenance_json", pa.string()),
            ]
        )

    def _load_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if value.get("version") != 1:
            raise RuntimeError("unsupported Parquet manifest version")
        return [dict(part) for part in value.get("parts") or []]

    def _save_manifest(self) -> None:
        _atomic_json(self.manifest_path, {"version": 1, "parts": self._parts})

    def prepare_resume(self, expected_records: int) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        parts = self._load_manifest()
        retained = [part for part in parts if int(part["end_record"]) <= expected_records]
        retained_count = int(retained[-1]["end_record"]) if retained else 0
        if retained_count != expected_records:
            if expected_records:
                raise RuntimeError("Parquet checkpoint is not at a committed batch boundary")
        retained_names = {str(part["file"]) for part in retained}
        for path in self.directory.glob("part-*.parquet"):
            if path.name not in retained_names:
                path.unlink()
        self._parts = retained
        self.records_written = expected_records
        self._save_manifest()

    @staticmethod
    def _flatten(record: CanonicalRecord) -> dict[str, Any]:
        value = record.to_dict()
        return {
            "schema_version": value["schema_version"],
            "source_id": value["source_id"],
            "source_record_id": value["source_record_id"],
            "record_type": value["record_type"],
            "title": value["title"],
            "abstract": value["abstract"],
            "published_date": value["published_date"],
            "start_date": value["start_date"],
            "end_date": value["end_date"],
            "funding_amount": value["funding_amount"],
            "funding_currency": value["funding_currency"],
            "organizations_json": json.dumps(value["organizations"], sort_keys=True),
            "topics_json": json.dumps(value["topics"], sort_keys=True),
            "links_json": json.dumps(value["links"], sort_keys=True),
            "identifiers_json": json.dumps(value["identifiers"], sort_keys=True),
            "geography_json": json.dumps(value["geography"], sort_keys=True),
            "attributes_json": json.dumps(value["attributes"], sort_keys=True),
            "provenance_json": json.dumps(value["provenance"], sort_keys=True),
        }

    def write_batch(self, records: Iterable[CanonicalRecord]) -> int:
        values = list(records)
        if not values:
            return 0
        start = self.records_written
        end = start + len(values)
        filename = f"part-{start:012d}-{end:012d}.parquet"
        destination = self.directory / filename
        temporary = destination.with_suffix(".parquet.tmp")
        table = self._pa.Table.from_pylist(
            [self._flatten(record) for record in values], schema=self._schema
        )
        self._pq.write_table(table, temporary, compression="zstd")
        os.replace(temporary, destination)
        self.records_written = end
        self._parts.append(
            {"file": filename, "start_record": start, "end_record": end, "rows": len(values)}
        )
        self._save_manifest()
        return len(values)


def create_writer(output: Path, output_format: str, gzip_enabled: bool = False) -> RecordWriter:
    if output_format == "parquet":
        if gzip_enabled:
            raise ValueError("--gzip cannot be combined with Parquet output")
        return ParquetDatasetWriter(output)
    if output_format != "jsonl":
        raise ValueError(f"unsupported output format: {output_format}")
    if gzip_enabled or output.name.endswith(".gz"):
        return GzipJsonlWriter(output)
    return JsonlWriter(output)

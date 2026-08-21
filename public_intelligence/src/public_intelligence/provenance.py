"""Deterministic serialization and provenance hashing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, BinaryIO, Mapping


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON-compatible value with a stable byte representation."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def sha256_stream(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return sha256_stream(handle)


def canonical_record_hash(record: Mapping[str, Any]) -> str:
    """Hash stable record content while excluding run-specific provenance."""

    value = dict(record)
    provenance = dict(value.get("provenance") or {})
    provenance.pop("retrieved_at", None)
    provenance.pop("snapshot_id", None)
    provenance.pop("record_sha256", None)
    value["provenance"] = provenance
    return sha256_json(value)


def config_fingerprint(config: Mapping[str, Any]) -> str:
    return sha256_json(config)

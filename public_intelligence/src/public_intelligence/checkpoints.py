"""Atomic collection checkpoint storage."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass
class Checkpoint:
    source_id: str
    config_fingerprint: str
    snapshot_id: str
    retrieved_at: str
    records_written: int = 0
    connector_state: dict[str, Any] = field(default_factory=dict)
    complete: bool = False
    limit_reached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "source_id": self.source_id,
            "config_fingerprint": self.config_fingerprint,
            "snapshot_id": self.snapshot_id,
            "retrieved_at": self.retrieved_at,
            "records_written": self.records_written,
            "connector_state": self.connector_state,
            "complete": self.complete,
            "limit_reached": self.limit_reached,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Checkpoint":
        if value.get("version") != 1:
            raise ValueError("unsupported checkpoint version")
        return cls(
            source_id=str(value["source_id"]),
            config_fingerprint=str(value["config_fingerprint"]),
            snapshot_id=str(value["snapshot_id"]),
            retrieved_at=str(value["retrieved_at"]),
            records_written=int(value.get("records_written", 0)),
            connector_state=dict(value.get("connector_state") or {}),
            complete=bool(value.get("complete", False)),
            limit_reached=bool(value.get("limit_reached", False)),
        )


class CheckpointStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Checkpoint | None:
        if not self.path.exists():
            return None
        with self.path.open("r", encoding="utf-8") as handle:
            return Checkpoint.from_dict(json.load(handle))

    def save(self, checkpoint: Checkpoint) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(checkpoint.to_dict(), handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def remove(self) -> None:
        if self.path.exists():
            self.path.unlink()

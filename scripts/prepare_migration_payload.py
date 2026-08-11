#!/usr/bin/env python3
"""Build a bounded direct-invoke payload for expand-before-code migrations."""

from __future__ import annotations

import json
from pathlib import Path
import sys


MAX_DIRECT_INVOKE_BYTES = 5_500_000


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_migration_payload.py OUTPUT.json")

    repo = Path(__file__).resolve().parents[1]
    migration_root = repo / "db" / "migrations"
    migrations = [
        {"name": path.stem, "sql": path.read_text(encoding="utf-8")}
        for path in sorted(migration_root.glob("*.sql"))
    ]
    if not migrations:
        raise SystemExit("no source migrations found")

    encoded = json.dumps(
        {"migrate": "all", "migrations": migrations},
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_DIRECT_INVOKE_BYTES:
        raise SystemExit(
            f"migration payload is {len(encoded)} bytes and exceeds the release bound"
        )

    Path(sys.argv[1]).write_bytes(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

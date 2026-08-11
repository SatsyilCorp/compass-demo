#!/usr/bin/env python3
"""Fail when repository text contains the forbidden U+2014 code point."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


FORBIDDEN = chr(0x2014)


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    return [Path(item) for item in result.stdout.decode().split("\0") if item]


def main() -> int:
    findings: list[str] = []
    for path in repository_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN in line:
                findings.append(f"{path}:{line_number}")

    if findings:
        print("Forbidden U+2014 code point found:")
        print("\n".join(findings))
        return 1
    print("OK repository contains no U+2014 code points")
    return 0


if __name__ == "__main__":
    sys.exit(main())

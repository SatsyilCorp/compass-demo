#!/usr/bin/env python3
"""Validate the source-backed STIG-aligned evidence index.

The script proves that every listed control points to committed implementation
evidence. It deliberately does not produce a DISA checklist score or claim an
accreditation decision.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = ROOT / "security" / "stig" / "control-mapping.json"


def validate_mapping(mapping_path: Path = DEFAULT_MAPPING) -> Dict[str, Any]:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    controls = mapping.get("controls")
    if not isinstance(controls, list) or not controls:
        raise ValueError("control mapping must contain at least one control")
    if "not a DISA checklist result" not in str(mapping.get("disclaimer", "")):
        raise ValueError("control mapping must retain the non-accreditation disclaimer")

    seen = set()
    failures: List[str] = []
    evidence_count = 0
    for control in controls:
        control_id = str(control.get("id") or "")
        if not control_id or control_id in seen:
            failures.append(f"duplicate or empty control id {control_id!r}")
            continue
        seen.add(control_id)
        if not str(control.get("implementation") or "").strip():
            failures.append(f"{control_id}: missing implementation narrative")
        if not str(control.get("verification") or "").strip():
            failures.append(f"{control_id}: missing verification command")
        evidence = control.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            failures.append(f"{control_id}: missing evidence")
            continue
        for item in evidence:
            relative = Path(str(item.get("path") or ""))
            if relative.is_absolute() or ".." in relative.parts:
                failures.append(f"{control_id}: unsafe evidence path")
                continue
            path = ROOT / relative
            if not path.is_file():
                failures.append(f"{control_id}: missing {relative}")
                continue
            text = path.read_text(encoding="utf-8")
            tokens = item.get("contains")
            if not isinstance(tokens, list) or not tokens:
                failures.append(f"{control_id}: {relative} has no evidence tokens")
                continue
            for token in tokens:
                if str(token) not in text:
                    failures.append(f"{control_id}: {relative} lacks {token!r}")
            evidence_count += 1

    if failures:
        raise ValueError("; ".join(failures))
    return {
        "status": "passed",
        "profile": mapping["profile"],
        "controls": len(controls),
        "evidence_pointers": evidence_count,
        "accreditation_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = validate_mapping(args.mapping.resolve())
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

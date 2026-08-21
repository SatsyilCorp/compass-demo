"""Single canonical-JSONL command-line trainer for the model suite."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from .artifacts import save_training_output
from .contracts import TrainingRefusal, load_canonical_jsonl
from .registry import train_dataset
from .usaspending_funding import DEFAULT_SOURCE_URI, build_funding_jsonl
from .sbir_transition_dataset import build_sbir_transition_records, write_sbir_transition_jsonl


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="compass-public-models",
        description=(
            "Train one production-honest public intelligence model from canonical JSONL."
        ),
    )
    subcommands = root.add_subparsers(dest="command", required=True)
    train = subcommands.add_parser(
        "train", help="validate, train, evaluate, and serialize"
    )
    train.add_argument(
        "--input", required=True, type=Path, help="canonical JSONL dataset"
    )
    train.add_argument(
        "--output", required=True, type=Path, help="new or empty artifact directory"
    )
    build_funding = subcommands.add_parser(
        "build-funding",
        help="build canonical JSONL from an approved USAspending aggregate",
    )
    build_funding.add_argument(
        "--input", required=True, type=Path, help="USAspending source snapshot"
    )
    build_sbir = subcommands.add_parser(
        "build-sbir-transition",
        help="build an authentic transition dataset from the minimized Navy SBIR snapshot",
    )
    build_sbir.add_argument("--input", required=True, type=Path)
    build_sbir.add_argument("--output", required=True, type=Path)
    build_sbir.add_argument("--as-of-date", required=True, type=date.fromisoformat)
    build_sbir.add_argument("--horizon-months", type=int, choices=(24, 36), default=36)
    build_funding.add_argument(
        "--output", required=True, type=Path, help="new canonical JSONL path"
    )
    build_funding.add_argument(
        "--source-uri",
        default=DEFAULT_SOURCE_URI,
        help="stable evidence URI recorded in row provenance",
    )
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "build-funding":
            result = build_funding_jsonl(
                args.input,
                args.output,
                source_uri=args.source_uri,
            )
            decision = "built"
        elif args.command == "build-sbir-transition":
            records, result = build_sbir_transition_records(
                args.input,
                as_of_date=args.as_of_date,
                horizon_months=args.horizon_months,
            )
            write_sbir_transition_jsonl(records, args.output)
            result = {**result, "output": str(args.output)}
            decision = "built"
        else:
            dataset = load_canonical_jsonl(args.input, allow_test_fixtures=False)
            output = train_dataset(dataset)
            result = save_training_output(output, args.output)
            decision = "trained"
    except TrainingRefusal as exc:
        print(
            json.dumps(
                {
                    "contract": "compass.public-intelligence.training-refusal.v1",
                    "decision": "refuse",
                    "stage": args.command,
                    "reason_code": exc.code,
                    "message": exc.message,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"decision": decision, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

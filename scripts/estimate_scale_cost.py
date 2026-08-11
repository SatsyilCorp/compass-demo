#!/usr/bin/env python3
"""Print a Price List-backed Scale Run or monthly idle estimate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "common" / "python"))

from compass_common.scale_cost import (  # noqa: E402
    estimate_idle_month,
    estimate_incremental,
    modeled_quantities,
)
from compass_common.scale_workload import (  # noqa: E402
    DATASETS,
    get_profile,
    iter_partition_specs,
)


PROFILE_RECORDS = {"1k": 1_000, "10k": 10_000, "100k": 100_000, "1m": 1_000_000}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILE_RECORDS))
    parser.add_argument("--idle-month", action="store_true")
    parser.add_argument(
        "--database-mode",
        choices=("demo", "ha"),
        default="demo",
        help="idle estimate uses one Aurora instance for demo and two for ha",
    )
    args = parser.parse_args()
    if args.idle_month == bool(args.profile):
        parser.error("choose exactly one of --profile or --idle-month")
    if args.idle_month:
        receipt = estimate_idle_month(
            aurora_instance_count=2 if args.database_mode == "ha" else 1
        )
    else:
        profile_id = str(args.profile)
        profile = get_profile(profile_id)
        partition_count = sum(
            1
            for dataset in DATASETS
            for _ in iter_partition_specs(profile, dataset)
        )
        receipt = estimate_incremental(
            profile_id,
            modeled_quantities(
                PROFILE_RECORDS[profile_id],
                profile.default_partition_size,
                partition_count=partition_count,
            ),
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate a deterministic, partitioned Compass synthetic scale workload.

Example:

  python3 scripts/generate_scale_data.py 10k --target artifacts/scale-10k

The target must be absent or empty. Each partition is canonical JSON Lines in
deterministic gzip form. A receipt records aggregates, quality results, and
both content and object hashes. The top-level manifest binds every object and
receipt to the fixed profile and seed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_PYTHON = REPO_ROOT / "src" / "common" / "python"
sys.path.insert(0, str(COMMON_PYTHON))

from compass_common.scale_workload import (  # noqa: E402
    CONTRACT_VERSION,
    DATASETS,
    DEFAULT_SEED,
    PROFILES,
    DefectPolicy,
    DeterministicGzipJsonlWriter,
    PartitionReceiptBuilder,
    canonical_json_bytes,
    iter_partition_specs,
    iter_record_results,
    sha256_hex,
)


def _write_canonical_json(path: Path, value: Any) -> str:
    payload = canonical_json_bytes(value) + b"\n"
    path.write_bytes(payload)
    return sha256_hex(payload)


def _empty_target(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError("target exists and is not a directory")
    if path.exists() and any(path.iterdir()):
        raise ValueError("target must be absent or empty")
    path.mkdir(parents=True, exist_ok=True)


def _selected_datasets(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return DATASETS
    requested = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not requested:
        raise ValueError("at least one dataset must be selected")
    unknown = sorted(set(requested) - set(DATASETS))
    if unknown:
        raise ValueError(f"unsupported datasets: {', '.join(unknown)}")
    if len(requested) != len(set(requested)):
        raise ValueError("dataset selection contains duplicates")
    return requested


def generate(args: argparse.Namespace) -> dict[str, Any]:
    target = args.target.resolve()
    _empty_target(target)
    datasets = _selected_datasets(args.datasets)
    profile = PROFILES[args.profile]
    policy = DefectPolicy(rate_basis_points=args.defect_rate_basis_points)
    partition_size = args.partition_size or profile.default_partition_size

    objects: list[dict[str, Any]] = []
    dataset_summary: dict[str, dict[str, int]] = {}
    for dataset in datasets:
        data_dir = target / "data" / dataset
        receipt_dir = target / "receipts" / dataset
        data_dir.mkdir(parents=True, exist_ok=True)
        receipt_dir.mkdir(parents=True, exist_ok=True)
        generated = valid = invalid = injected = 0
        for spec in iter_partition_specs(
            profile, dataset, partition_size=partition_size
        ):
            data_path = data_dir / f"{spec.partition_id}.jsonl.gz"
            receipt_path = receipt_dir / f"{spec.partition_id}.receipt.json"
            builder = PartitionReceiptBuilder(spec, seed=args.seed, defect_policy=policy)
            with data_path.open("wb") as raw_output:
                writer = DeterministicGzipJsonlWriter(raw_output)
                for result in iter_record_results(
                    profile,
                    dataset,
                    seed=args.seed,
                    start=spec.start,
                    stop=spec.stop,
                    defect_policy=policy,
                ):
                    writer.write(result.record)
                    builder.observe(result)
                object_receipt = writer.close()
            partition_receipt = builder.finish()
            if (
                object_receipt.content_sha256
                != partition_receipt["content"]["content_sha256"]
            ):
                raise RuntimeError("writer and partition receipt hashes disagree")
            partition_receipt["object"] = object_receipt.to_dict()
            receipt_sha256 = _write_canonical_json(receipt_path, partition_receipt)
            quality = partition_receipt["quality"]
            generated += quality["generated_records"]
            valid += quality["valid_records"]
            invalid += quality["invalid_records"]
            injected += quality["injected_defects"]
            objects.append(
                {
                    "dataset": dataset,
                    "partition_id": spec.partition_id,
                    "range": {"start": spec.start, "stop": spec.stop},
                    "data_path": data_path.relative_to(target).as_posix(),
                    "receipt_path": receipt_path.relative_to(target).as_posix(),
                    "record_count": object_receipt.record_count,
                    "uncompressed_bytes": object_receipt.uncompressed_bytes,
                    "compressed_bytes": object_receipt.compressed_bytes,
                    "content_sha256": object_receipt.content_sha256,
                    "object_sha256": object_receipt.object_sha256,
                    "receipt_sha256": receipt_sha256,
                }
            )
            print(
                f"generated {dataset}/{spec.partition_id}: "
                f"{object_receipt.record_count} records"
            )
        dataset_summary[dataset] = {
            "generated_records": generated,
            "valid_records": valid,
            "invalid_records": invalid,
            "injected_defects": injected,
        }

    run_coordinates = {
        "contract_version": CONTRACT_VERSION,
        "profile": profile.name,
        "profile_total_records": profile.total_records,
        "selected_records": sum(
            profile.dataset_counts[dataset] for dataset in datasets
        ),
        "dataset_counts": {
            dataset: profile.dataset_counts[dataset] for dataset in datasets
        },
        "seed": args.seed,
        "partition_size": partition_size,
        "defect_policy": asdict(policy),
        "datasets": list(datasets),
    }
    manifest = {
        **run_coordinates,
        "synthetic_data_notice": (
            "All records are invented, unclassified, and generated for testing."
        ),
        "run_id": hashlib.sha256(canonical_json_bytes(run_coordinates)).hexdigest()[:24],
        "dataset_summary": dataset_summary,
        "objects": objects,
    }
    manifest_path = target / "manifest.json"
    manifest_sha256 = _write_canonical_json(manifest_path, manifest)
    (target / "manifest.sha256").write_text(
        f"{manifest_sha256}  manifest.json\n", encoding="ascii"
    )
    print(f"manifest: {manifest_path}")
    print(f"manifest sha256: {manifest_sha256}")
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=tuple(PROFILES))
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--partition-size",
        type=int,
        help="records per object; fixed profile default is used when omitted",
    )
    parser.add_argument(
        "--defect-rate-basis-points",
        type=int,
        default=100,
        help="deterministic injected schema defect rate; 100 means 1 percent",
    )
    parser.add_argument(
        "--datasets",
        help=f"comma-separated subset of: {', '.join(DATASETS)}",
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        generate(args)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

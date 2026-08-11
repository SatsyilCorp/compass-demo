"""Focused tests for the deterministic Compass scale workload interface."""
from __future__ import annotations

import gzip
import io

import pytest

from compass_common.scale_workload import (
    DATASETS,
    PROFILES,
    DefectPolicy,
    DeterministicGzipJsonlWriter,
    PartitionReceiptBuilder,
    build_partition_receipt,
    canonical_json_line,
    deterministic_gzip_bytes,
    generate_record,
    iter_partition_specs,
    iter_record_results,
    iter_records,
    validate_record,
)


def test_fixed_profiles_have_exact_total_counts() -> None:
    assert tuple(PROFILES) == ("1k", "10k", "100k", "1m")
    for profile in PROFILES.values():
        assert tuple(profile.dataset_counts) == DATASETS
        assert sum(profile.dataset_counts.values()) == profile.total_records
        assert all(count > 0 for count in profile.dataset_counts.values())


def test_generation_is_counter_deterministic_and_seeded() -> None:
    first = generate_record("10k", "grants", 27, seed=42)
    replay = generate_record("10k", "grants", 27, seed=42)
    different_seed = generate_record("10k", "grants", 27, seed=43)
    assert first == replay
    assert first != different_seed
    assert first["synthetic"] is True
    assert first["classification"] == "UNCLASSIFIED-SYNTHETIC"


def test_partitioned_iteration_matches_unpartitioned_iteration() -> None:
    expected = list(iter_records("1k", "finance", seed=7))
    actual = []
    for spec in iter_partition_specs("1k", "finance", partition_size=37):
        actual.extend(
            iter_records(
                "1k", "finance", seed=7, start=spec.start, stop=spec.stop
            )
        )
    assert actual == expected


@pytest.mark.parametrize("dataset", DATASETS)
def test_generated_records_pass_strict_schema(dataset: str) -> None:
    for record in iter_records("1k", dataset, seed=99, stop=12):
        assert validate_record(dataset, record) == ()


@pytest.mark.parametrize(
    "dataset", ("finance", "milestones", "documents", "stream_events")
)
def test_child_records_reference_a_grant_in_the_same_profile(dataset: str) -> None:
    grants = {
        row["grant_id"]: row["grant_no"] for row in iter_records("1k", "grants")
    }
    for child in iter_records("1k", dataset, stop=50):
        assert grants[child["grant_id"]] == child["grant_no"]


@pytest.mark.parametrize("dataset", DATASETS)
def test_every_defect_kind_is_detected(dataset: str) -> None:
    for kind in (
        "missing_required",
        "invalid_type",
        "invalid_enum",
        "invalid_format",
        "out_of_range",
    ):
        results = list(
            iter_record_results(
                "1k",
                dataset,
                seed=13,
                stop=1,
                defect_policy=DefectPolicy(10_000, (kind,)),
            )
        )
        assert results[0].injected_defect == kind
        assert results[0].issues


def test_defect_selection_is_replayable() -> None:
    policy = DefectPolicy(275)
    first = list(
        iter_record_results("1k", "grants", seed=123, defect_policy=policy)
    )
    replay = list(
        iter_record_results("1k", "grants", seed=123, defect_policy=policy)
    )
    assert [item.injected_defect for item in first] == [
        item.injected_defect for item in replay
    ]
    assert [item.record for item in first] == [item.record for item in replay]


def test_partition_receipt_binds_aggregate_quality_and_content() -> None:
    spec = next(iter_partition_specs("1k", "finance", partition_size=83))
    policy = DefectPolicy(1_000)
    builder = PartitionReceiptBuilder(spec, seed=51, defect_policy=policy)
    results = list(
        iter_record_results(
            "1k",
            "finance",
            seed=51,
            start=spec.start,
            stop=spec.stop,
            defect_policy=policy,
        )
    )
    for result in results:
        builder.observe(result)
    receipt = builder.finish()
    assert receipt == build_partition_receipt(spec, seed=51, defect_policy=policy)
    assert receipt["aggregate"]["record_count"] == 83
    assert receipt["quality"]["generated_records"] == 83
    assert receipt["quality"]["injected_defects"] > 0
    assert receipt["quality"]["unexpected_invalid_records"] == 0
    assert receipt["quality"]["undetected_injected_defects"] == 0
    expected_bytes = sum(len(canonical_json_line(item.record)) for item in results)
    assert receipt["content"]["canonical_bytes"] == expected_bytes


def test_deterministic_gzip_bytes_have_fixed_header_and_payload() -> None:
    payload = b'{"a":1}\n{"a":2}\n'
    first = deterministic_gzip_bytes(payload)
    second = deterministic_gzip_bytes(payload)
    assert first == second
    assert gzip.decompress(first) == payload
    assert first[4:8] == b"\x00\x00\x00\x00"


def test_streaming_gzip_receipt_matches_replay() -> None:
    records = list(iter_records("1k", "licenses", seed=8, stop=10))

    def render() -> tuple[bytes, object]:
        output = io.BytesIO()
        writer = DeterministicGzipJsonlWriter(output)
        for record in records:
            writer.write(record)
        receipt = writer.close()
        return output.getvalue(), receipt

    first_bytes, first_receipt = render()
    second_bytes, second_receipt = render()
    assert first_bytes == second_bytes
    assert first_receipt == second_receipt
    assert first_receipt.record_count == 10
    assert gzip.decompress(first_bytes) == b"".join(
        canonical_json_line(record) for record in records
    )


def test_unbounded_counts_and_invalid_ranges_are_rejected() -> None:
    with pytest.raises(ValueError, match="fixed workload profiles"):
        list(iter_records(type(PROFILES["1k"])("custom", 3, 1), "grants"))
    with pytest.raises(ValueError, match="range"):
        list(iter_records("1k", "grants", start=20, stop=10))
    with pytest.raises(IndexError):
        generate_record("1k", "grants", PROFILES["1k"].dataset_counts["grants"])

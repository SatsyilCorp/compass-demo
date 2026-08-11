from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from compass_common.scale_cost import (
    PriceCatalog,
    assert_cost_gate,
    estimate_idle_month,
    estimate_incremental,
    modeled_quantities,
)


def test_profile_estimates_are_bounded_and_monotonic():
    catalog = PriceCatalog.load()
    estimates = []
    for profile_id, records in (("1k", 1_000), ("10k", 10_000), ("100k", 100_000), ("1m", 1_000_000)):
        estimate = estimate_incremental(profile_id, modeled_quantities(records), catalog=catalog)
        assert estimate["within_envelope"] is True
        assert estimate["free_tier_applied"] is False
        assert estimate["line_items"]
        assert_cost_gate(estimate)
        estimates.append(Decimal(estimate["estimated_cost_usd"]))
    assert estimates == sorted(estimates)


def test_each_line_item_retains_official_price_evidence():
    estimate = estimate_incremental("10k", modeled_quantities(10_000))
    for item in estimate["line_items"]:
        assert item["service_code"]
        assert item["sku"]
        assert item["rate_code"]
        assert item["publication_date"]
        assert item["source_url"].startswith("https://aws.amazon.com/")


def test_cost_gate_rejects_non_estimate_and_excess():
    with pytest.raises(ValueError, match="pre-run"):
        assert_cost_gate({"kind": "metered", "within_envelope": True})
    with pytest.raises(ValueError, match="exceeds"):
        assert_cost_gate(
            {
                "kind": "pre_run_estimate",
                "price_snapshot_fresh": True,
                "within_envelope": False,
            }
        )


def test_cost_gate_rejects_stale_or_future_price_snapshot():
    with pytest.raises(ValueError, match="snapshot"):
        assert_cost_gate(
            {
                "kind": "pre_run_estimate",
                "price_snapshot_fresh": False,
                "within_envelope": True,
            }
        )


def test_catalog_snapshot_age_is_timezone_aware():
    catalog = PriceCatalog.load()
    age = catalog.snapshot_age_days(datetime(2026, 8, 11, 6, tzinfo=timezone.utc))
    assert Decimal("0") <= age < Decimal("1")


def test_idle_estimate_identifies_major_fixed_costs():
    estimate = estimate_idle_month()
    keys = {item["key"] for item in estimate["line_items"]}
    assert {"nat_gateway_hour", "aurora_serverless_v2_acu_hour", "kinesis_on_demand_stream_hour"} <= keys
    assert Decimal(estimate["estimated_cost_usd"]) > Decimal("100")


def test_ha_idle_estimate_includes_two_aurora_instances():
    demo = estimate_idle_month(aurora_instance_count=1)
    ha = estimate_idle_month(aurora_instance_count=2)
    assert Decimal(ha["estimated_cost_usd"]) > Decimal(demo["estimated_cost_usd"])


def test_quantity_model_rejects_unbounded_partition_size():
    with pytest.raises(ValueError):
        modeled_quantities(10_000, partition_records=50_000)


def test_quantity_model_accounts_for_multi_dataset_partition_overhead():
    quantities = modeled_quantities(10_000, partition_records=5_000)
    assert quantities.partitions == 7

    exact = modeled_quantities(
        10_000,
        partition_records=5_000,
        partition_count=6,
    )
    assert exact.partitions == 6


def test_quantity_model_rejects_impossible_partition_count():
    with pytest.raises(ValueError, match="pooled minimum"):
        modeled_quantities(10_000, partition_records=5_000, partition_count=1)
    with pytest.raises(ValueError, match="exceed records"):
        modeled_quantities(10_000, partition_count=10_001)

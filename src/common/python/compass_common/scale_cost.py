"""Price List-backed cost evidence for bounded Compass Scale Runs."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping


SNAPSHOT_PATH = Path(__file__).with_name("aws_prices_us_east_1.json")
PROFILE_ENVELOPES_USD = {
    "1k": Decimal("0.10"),
    "10k": Decimal("0.25"),
    "100k": Decimal("1.00"),
    "1m": Decimal("10.00"),
}


@dataclass(frozen=True)
class Rate:
    key: str
    service_code: str
    sku: str
    rate_code: str
    usage_type: str
    unit: str
    usd: Decimal
    publication_date: str
    source_url: str


class PriceCatalog:
    def __init__(self, payload: Mapping[str, Any]):
        self.region = str(payload["region"])
        self.location = str(payload["location"])
        self.captured_at = str(payload["captured_at"])
        self.price_source = str(payload["price_source"])
        self._sources = dict(payload["source_urls"])
        self._rates = dict(payload["rates"])

    @classmethod
    def load(cls, path: Path | str = SNAPSHOT_PATH) -> "PriceCatalog":
        with Path(path).open(encoding="utf-8") as handle:
            return cls(json.load(handle))

    def rate(self, key: str) -> Rate:
        raw = self._rates[key]
        service = str(raw["service_code"])
        source_key = {
            "AWSLambda": "lambda",
            "AmazonS3": "s3",
            "AWSQueueService": "sqs",
            "AmazonStates": "step_functions",
            "AmazonDynamoDB": "dynamodb",
            "AmazonAthena": "athena",
            "AWSGlue": "glue",
            "AmazonCloudWatch": "cloudwatch",
            "AmazonEC2": "vpc",
            "AmazonVPC": "vpc",
            "AmazonRDS": "aurora",
            "awskms": "kms",
            "AmazonApiGateway": "api_gateway",
            "AmazonKinesis": "kinesis",
            "AWSSecretsManager": "secrets_manager",
            "awswaf": "waf",
        }[service]
        return Rate(
            key=key,
            service_code=service,
            sku=str(raw["sku"]),
            rate_code=str(raw["rate_code"]),
            usage_type=str(raw["usage_type"]),
            unit=str(raw["unit"]),
            usd=Decimal(str(raw["usd"])),
            publication_date=str(raw["publication_date"]),
            source_url=str(self._sources[source_key]),
        )

    def snapshot_age_days(self, now: datetime | None = None) -> Decimal:
        captured = datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))
        if captured.tzinfo is None:
            raise ValueError("price snapshot captured_at must include a timezone")
        observed = now or datetime.now(timezone.utc)
        if observed.tzinfo is None:
            raise ValueError("price snapshot comparison time must include a timezone")
        seconds = Decimal(str((observed - captured).total_seconds()))
        return seconds / Decimal(24 * 60 * 60)


@dataclass(frozen=True)
class ScaleQuantities:
    records: int
    partitions: int
    retained_gb_month: Decimal
    lambda_arm_requests: int
    lambda_arm_gb_seconds: Decimal
    s3_put_requests: int
    s3_get_requests: int
    sqs_requests: int
    step_functions_transitions: int
    dynamodb_write_units: int
    dynamodb_read_units: int
    dynamodb_storage_gb_month: Decimal
    athena_tb_scanned: Decimal
    cloudwatch_log_gb: Decimal
    kms_requests: int
    http_api_requests: int


def modeled_quantities(
    records: int,
    partition_records: int = 10_000,
    *,
    partition_count: int | None = None,
) -> ScaleQuantities:
    if records <= 0:
        raise ValueError("records must be positive")
    if partition_records <= 0 or partition_records > 25_000:
        raise ValueError("partition_records must be between 1 and 25000")
    minimum_partitions = math.ceil(records / partition_records)
    if partition_count is None:
        # Scale profiles span six datasets. Treating the corpus as one dataset
        # undercounts request, ledger, and worker overhead. Splitting a total
        # across six datasets adds at most five partitions to the pooled count,
        # so this is a conservative default when exact profile counts are not
        # supplied by the caller.
        partitions = minimum_partitions + 5
    else:
        if partition_count < minimum_partitions:
            raise ValueError("partition_count cannot be below the pooled minimum")
        if partition_count > records:
            raise ValueError("partition_count cannot exceed records")
        partitions = partition_count
    raw_gb = Decimal(records * 1400) / Decimal(1024**3)
    curated_gb = raw_gb * Decimal("0.78")
    parquet_gb = curated_gb * Decimal("0.32")
    retained_gb_month = (raw_gb + curated_gb + parquet_gb) * Decimal(7) / Decimal(30)
    # Conservative duration includes generation, validation, compression, S3,
    # receipt commit, orchestration, and Athena polling. It is a planning
    # quantity, not a performance claim.
    worker_seconds = Decimal(partitions * 30)
    # The deployed partition worker uses 2 GB. Control and export use 1 GB.
    # Include 150 one-GB seconds for planning, polling, finalization, and one
    # export so the pre-run estimate matches the configured memory envelope.
    control_and_export_gb_seconds = Decimal(150)
    return ScaleQuantities(
        records=records,
        partitions=partitions,
        retained_gb_month=retained_gb_month,
        lambda_arm_requests=partitions + 12,
        lambda_arm_gb_seconds=(worker_seconds * Decimal(2))
        + control_and_export_gb_seconds,
        s3_put_requests=partitions * 9 + 24,
        s3_get_requests=partitions * 7 + 24,
        sqs_requests=partitions * 4 + 4,
        step_functions_transitions=48 + partitions // 2,
        dynamodb_write_units=partitions * 8 + 20,
        dynamodb_read_units=partitions * 6 + 40,
        dynamodb_storage_gb_month=Decimal(partitions * 10_000) / Decimal(1024**3),
        athena_tb_scanned=max(
            Decimal("0.000048828125"),
            (curated_gb * Decimal(5)) / Decimal(1024),
        ),
        cloudwatch_log_gb=Decimal(partitions) * Decimal("0.0015") + Decimal("0.003"),
        kms_requests=partitions * 8 + 32,
        http_api_requests=120,
    )


def _line_item(catalog: PriceCatalog, key: str, quantity: Decimal | int) -> dict[str, Any]:
    rate = catalog.rate(key)
    q = Decimal(quantity)
    cost = q * rate.usd
    return {
        "key": key,
        "service_code": rate.service_code,
        "sku": rate.sku,
        "rate_code": rate.rate_code,
        "usage_type": rate.usage_type,
        "quantity": _decimal_text(q),
        "unit": rate.unit,
        "rate_usd": _decimal_text(rate.usd),
        "cost_usd": _decimal_text(cost),
        "publication_date": rate.publication_date,
        "source_url": rate.source_url,
    }


def estimate_incremental(
    profile_id: str,
    quantities: ScaleQuantities,
    *,
    catalog: PriceCatalog | None = None,
    deployed_hard_cap_usd: Decimal | str = Decimal("10.00"),
    contingency_pct: Decimal | str = Decimal("25"),
    price_snapshot_max_age_days: Decimal | str = Decimal("30"),
) -> dict[str, Any]:
    catalog = catalog or PriceCatalog.load()
    profile_cap = PROFILE_ENVELOPES_USD.get(profile_id)
    if profile_cap is None:
        raise ValueError("unknown workload profile")
    hard_cap = Decimal(str(deployed_hard_cap_usd))
    maximum = min(profile_cap, hard_cap)
    contingency = Decimal(str(contingency_pct))
    maximum_age = Decimal(str(price_snapshot_max_age_days))
    snapshot_age = catalog.snapshot_age_days()
    snapshot_fresh = Decimal("-1") <= snapshot_age <= maximum_age
    mapping = (
        ("lambda_arm_request", quantities.lambda_arm_requests),
        ("lambda_arm_gb_second", quantities.lambda_arm_gb_seconds),
        ("s3_standard_gb_month", quantities.retained_gb_month),
        ("s3_put_request", quantities.s3_put_requests),
        ("s3_get_request", quantities.s3_get_requests),
        ("sqs_standard_request", quantities.sqs_requests),
        ("step_functions_transition", quantities.step_functions_transitions),
        ("dynamodb_write_request_unit", quantities.dynamodb_write_units),
        ("dynamodb_read_request_unit", quantities.dynamodb_read_units),
        ("dynamodb_storage_gb_month", quantities.dynamodb_storage_gb_month),
        ("athena_tb_scanned", quantities.athena_tb_scanned),
        ("cloudwatch_log_ingest_gb", quantities.cloudwatch_log_gb),
        ("kms_request", quantities.kms_requests),
        ("http_api_request", quantities.http_api_requests),
    )
    items = [_line_item(catalog, key, quantity) for key, quantity in mapping]
    subtotal = sum((Decimal(item["cost_usd"]) for item in items), Decimal(0))
    contingency_cost = subtotal * contingency / Decimal(100)
    estimated = subtotal + contingency_cost
    return {
        "kind": "pre_run_estimate",
        "status": "estimated",
        "profile_id": profile_id,
        "region": catalog.region,
        "currency": "USD",
        "price_source": catalog.price_source,
        "price_snapshot_captured_at": catalog.captured_at,
        "price_snapshot_age_days": _decimal_text(snapshot_age),
        "price_snapshot_max_age_days": _decimal_text(maximum_age),
        "price_snapshot_fresh": snapshot_fresh,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quantities": _jsonable(asdict(quantities)),
        "line_items": items,
        "subtotal_usd": _decimal_text(subtotal),
        "contingency_pct": _decimal_text(contingency),
        "contingency_usd": _decimal_text(contingency_cost),
        "estimated_cost_usd": _decimal_text(estimated),
        "maximum_cost_usd": _decimal_text(maximum),
        "within_envelope": estimated <= maximum,
        "free_tier_applied": False,
        "disclosure": "Estimate excludes free tier and discounts. Billed cost is reconciled later.",
    }


def estimate_idle_month(
    *,
    catalog: PriceCatalog | None = None,
    hours: Decimal | str = Decimal("730"),
    aurora_min_acu: Decimal | str = Decimal("0.5"),
    aurora_instance_count: int = 1,
    alarm_count: int = 10,
    waf_rule_count: int = 3,
) -> dict[str, Any]:
    catalog = catalog or PriceCatalog.load()
    if aurora_instance_count not in {1, 2}:
        raise ValueError("aurora_instance_count must be 1 or 2")
    month_hours = Decimal(str(hours))
    mapping = (
        ("nat_gateway_hour", month_hours),
        ("public_ipv4_hour", month_hours),
        (
            "aurora_serverless_v2_acu_hour",
            month_hours
            * Decimal(str(aurora_min_acu))
            * Decimal(aurora_instance_count),
        ),
        ("kinesis_on_demand_stream_hour", month_hours),
        ("kms_key_month", 1),
        ("secrets_manager_secret_month", 1),
        ("waf_web_acl_month", 1),
        ("waf_rule_month", waf_rule_count),
        ("cloudwatch_standard_alarm_month", alarm_count),
    )
    items = [_line_item(catalog, key, quantity) for key, quantity in mapping]
    total = sum((Decimal(item["cost_usd"]) for item in items), Decimal(0))
    return {
        "kind": "monthly_idle_estimate",
        "status": "estimated",
        "region": catalog.region,
        "currency": "USD",
        "price_source": catalog.price_source,
        "price_snapshot_captured_at": catalog.captured_at,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "line_items": items,
        "estimated_cost_usd": _decimal_text(total),
        "free_tier_applied": False,
        "disclosure": (
            "Core fixed resources only. Storage, traffic, model usage, security services, "
            "tax, discounts, and account-level free tier are excluded."
        ),
    }


def assert_cost_gate(estimate: Mapping[str, Any]) -> None:
    if estimate.get("kind") != "pre_run_estimate":
        raise ValueError("Run Gate requires a pre-run estimate")
    if estimate.get("price_snapshot_fresh") is not True:
        raise ValueError("AWS price snapshot is missing, stale, or dated in the future")
    if not bool(estimate.get("within_envelope")):
        raise ValueError("estimated run cost exceeds the Cost Envelope")


def _decimal_text(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value

"""Command line entry point for bounded public-source snapshots."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .checkpoints import Checkpoint, CheckpointStore
from .connectors import CollectionRequest
from .http import RetryHttpClient, RetryPolicy
from .provenance import config_fingerprint
from .registry import create_connector, get_source, list_sources
from .writers import WriterDependencyError, create_writer


DEFAULT_MAX_RECORDS = 10_000
HARD_MAX_RECORDS = 2_000_000
DEFAULT_MAX_STREAM_MIB = 512


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from error


def _checkpoint_path(output: Path, output_format: str) -> Path:
    if output_format == "parquet":
        return output / "collection.checkpoint.json"
    return output.with_suffix(output.suffix + ".checkpoint.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compass-public-intel",
        description="Collect bounded, provenance-rich public intelligence snapshots.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list-sources", help="List implemented and gated sources"
    )
    list_parser.add_argument("--json", action="store_true", dest="as_json")

    collect = subparsers.add_parser("collect", help="Collect a bounded source snapshot")
    collect.add_argument("source_id")
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--format", choices=("jsonl", "parquet"), default="jsonl")
    collect.add_argument(
        "--gzip", action="store_true", help="Compress JSONL as resumable gzip members"
    )
    collect.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    collect.add_argument("--page-size", type=int, default=100)
    collect.add_argument("--max-pages", type=int, default=10_000)
    collect.add_argument("--batch-size", type=int, default=500)
    collect.add_argument("--query")
    collect.add_argument("--from-date", type=_parse_iso_date, default="2020-01-01")
    collect.add_argument(
        "--to-date",
        type=_parse_iso_date,
        default=datetime.now(timezone.utc).date().isoformat(),
    )
    collect.add_argument("--mailto")
    collect.add_argument("--api-key", help="OpenAlex API key. Prefer OPENALEX_API_KEY.")
    collect.add_argument("--ncbi-api-key", help="NCBI API key. Prefer NCBI_API_KEY.")
    collect.add_argument(
        "--endpoint", help="Override the official endpoint for controlled testing"
    )
    collect.add_argument(
        "--detail-endpoint",
        help="Override a source detail endpoint for controlled testing",
    )
    collect.add_argument(
        "--robots-endpoint",
        help="Override the ONR robots endpoint for controlled testing",
    )
    collect.add_argument(
        "--grants-agency",
        default="DOD-ONR",
        help="Exact Grants.gov agency code. Defaults to DOD-ONR.",
    )
    collect.add_argument(
        "--grants-skip-details",
        action="store_true",
        help="Collect Grants.gov search summaries without detail calls",
    )
    collect.add_argument(
        "--datacite-funder-ror",
        default="https://ror.org/00rk2pe57",
        help="Canonical ROR identifier used by DataCite funded-by filtering",
    )
    collect.add_argument(
        "--federal-register-agency",
        default="navy-department",
        help="Exact Federal Register agency slug. Defaults to navy-department.",
    )
    collect.add_argument(
        "--federal-register-term",
        default='"Office of Naval Research"',
        help="Default Federal Register term. The quoted default is an exact phrase.",
    )
    collect.add_argument(
        "--osti-sponsor-org",
        default="Office of Naval Research",
        help="Exact OSTI sponsor organization. Defaults to Office of Naval Research.",
    )
    collect.add_argument(
        "--sam-organization-code",
        default="017.1700.ONR",
        help="Exact SAM.gov ONR hierarchy code. Defaults to 017.1700.ONR.",
    )
    collect.add_argument(
        "--sam-organization-name",
        default="OFFICE OF NAVAL RESEARCH",
        help="Canonical organization label retained with SAM.gov records.",
    )
    collect.add_argument(
        "--uspto-product-id",
        default="PVGPATDIS",
        help="Official ODP PatentsView granted-patent product identifier.",
    )
    collect.add_argument(
        "--uspto-cache-dir",
        type=Path,
        default=Path(".cache/uspto-patentsview"),
        help="Local resumable cache for the four required USPTO bulk tables.",
    )
    collect.add_argument(
        "--uspto-refresh-cache",
        action="store_true",
        help="Refresh cached USPTO bulk tables before collection.",
    )
    collect.add_argument(
        "--federal-register-skip-details",
        action="store_true",
        help="Collect Federal Register search summaries without detail calls",
    )
    collect.add_argument("--sbir-url", help="Override the official SBIR CSV URL")
    collect.add_argument(
        "--sbir-branch-filter",
        default="navy",
        help="Case-insensitive agency or branch filter. Use 'all' to disable.",
    )
    collect.add_argument("--max-stream-mib", type=int, default=DEFAULT_MAX_STREAM_MIB)
    collect.add_argument("--requests-per-second", type=float, default=2.0)
    collect.add_argument("--timeout-seconds", type=float, default=60.0)
    collect.add_argument("--retry-attempts", type=int, default=5)
    collect.add_argument("--checkpoint", type=Path)
    collect.add_argument("--snapshot-id")
    collect.add_argument(
        "--fresh", action="store_true", help="Replace a prior partial snapshot"
    )
    return parser


def _list_sources(as_json: bool) -> int:
    sources = [source.to_dict() for source in list_sources()]
    if as_json:
        print(json.dumps(sources, indent=2, sort_keys=True))
        return 0
    for source in sources:
        status = "implemented" if source["implemented"] else "declared"
        requirements = ", ".join(source["requirements"]) or "none"
        print(
            f"{source['source_id']:18} {status:11} {source['access_mode']:16} "
            f"requirements: {requirements}"
        )
    return 0


def _validate_collect(args: argparse.Namespace) -> None:
    descriptor = get_source(args.source_id)
    if not descriptor.implemented:
        requirements = ", ".join(descriptor.requirements) or "source approval"
        raise ValueError(f"{args.source_id} is not enabled; required: {requirements}")
    if not 1 <= args.max_records <= HARD_MAX_RECORDS:
        raise ValueError(f"max-records must be between 1 and {HARD_MAX_RECORDS}")
    if not 1 <= args.page_size <= 1000:
        raise ValueError("page-size must be between 1 and 1000")
    if not 1 <= args.max_pages <= 100_000:
        raise ValueError("max-pages must be between 1 and 100000")
    if not 1 <= args.batch_size <= 10_000:
        raise ValueError("batch-size must be between 1 and 10000")
    if not 1 <= args.max_stream_mib <= 2048:
        raise ValueError("max-stream-mib must be between 1 and 2048")
    if args.retry_attempts < 1 or args.retry_attempts > 10:
        raise ValueError("retry-attempts must be between 1 and 10")
    if args.from_date and args.to_date and args.from_date > args.to_date:
        raise ValueError("from-date cannot be after to-date")
    if args.source_id == "sam_gov" and not os.environ.get("SAM_GOV_API_KEY"):
        raise ValueError(
            "sam_gov requires SAM_GOV_API_KEY; command-line key arguments are not accepted"
        )
    if args.source_id == "uspto_patents" and not os.environ.get(
        "USPTO_ODP_API_KEY"
    ):
        raise ValueError(
            "uspto_patents requires USPTO_ODP_API_KEY; command-line key arguments are not accepted"
        )


def _collect(args: argparse.Namespace) -> int:
    _validate_collect(args)
    api_key = args.api_key or os.environ.get("OPENALEX_API_KEY")
    ncbi_api_key = args.ncbi_api_key or os.environ.get("NCBI_API_KEY")
    sam_api_key = os.environ.get("SAM_GOV_API_KEY")
    uspto_odp_api_key = os.environ.get("USPTO_ODP_API_KEY")
    branch_filter = (
        None if args.sbir_branch_filter.casefold() == "all" else args.sbir_branch_filter
    )
    connector_options: dict[str, Any] = {
        "endpoint": args.endpoint,
        "detail_endpoint": args.detail_endpoint,
        "robots_endpoint": args.robots_endpoint,
        "archive_url": args.sbir_url,
        "mailto": args.mailto,
        "api_key": api_key,
        "ncbi_api_key": ncbi_api_key,
        "sam_api_key": sam_api_key,
        "uspto_odp_api_key": uspto_odp_api_key,
        "max_download_bytes": args.max_stream_mib * 1024 * 1024,
        "branch_filter": branch_filter,
        "funder_ror": args.datacite_funder_ror,
        "agency": args.federal_register_agency
        if args.source_id == "federal_register"
        else args.grants_agency,
        "term": args.federal_register_term,
        "fetch_details": not (
            args.federal_register_skip_details
            if args.source_id == "federal_register"
            else args.grants_skip_details
        ),
        "sponsor_org": args.osti_sponsor_org,
        "organization_code": args.sam_organization_code,
        "organization_name": args.sam_organization_name,
        "uspto_product_id": args.uspto_product_id,
        "uspto_cache_dir": args.uspto_cache_dir,
        "uspto_refresh_cache": args.uspto_refresh_cache,
    }
    stable_config = {
        "schema_version": 1,
        "source_id": args.source_id,
        "format": args.format,
        "gzip": bool(args.gzip or args.output.name.endswith(".gz")),
        "query": args.query,
        "from_date": args.from_date,
        "to_date": args.to_date,
        "page_size": args.page_size,
        "max_pages": args.max_pages,
        "endpoint": args.endpoint,
        "detail_endpoint": args.detail_endpoint,
        "robots_endpoint": args.robots_endpoint,
        "grants_agency": args.grants_agency,
        "grants_skip_details": bool(args.grants_skip_details),
        "datacite_funder_ror": args.datacite_funder_ror,
        "sbir_url": args.sbir_url,
        "sbir_branch_filter": branch_filter,
        "max_stream_mib": args.max_stream_mib,
        "mailto": args.mailto,
        "api_key_present": bool(api_key),
        "ncbi_api_key_present": bool(ncbi_api_key),
        "osti_sponsor_org": args.osti_sponsor_org,
        "sam_api_key_present": bool(sam_api_key),
        "sam_organization_code": args.sam_organization_code,
        "sam_organization_name": args.sam_organization_name,
        "uspto_odp_api_key_present": bool(uspto_odp_api_key),
        "uspto_product_id": args.uspto_product_id,
    }
    if args.source_id == "federal_register":
        stable_config.update(
            {
                "federal_register_agency": args.federal_register_agency,
                "federal_register_term": args.federal_register_term,
                "federal_register_skip_details": bool(
                    args.federal_register_skip_details
                ),
            }
        )
    fingerprint = config_fingerprint(stable_config)
    checkpoint_path = args.checkpoint or _checkpoint_path(args.output, args.format)
    store = CheckpointStore(checkpoint_path)
    if args.fresh:
        store.remove()
        checkpoint = None
    else:
        checkpoint = store.load()
    if checkpoint:
        if (
            checkpoint.source_id != args.source_id
            or checkpoint.config_fingerprint != fingerprint
        ):
            raise ValueError(
                "checkpoint does not match this source configuration; use --fresh"
            )
    else:
        retrieved_at = _utc_now()
        snapshot_id = args.snapshot_id or (
            f"{args.source_id}-{retrieved_at[:10].replace('-', '')}-{fingerprint[:12]}"
        )
        checkpoint = Checkpoint(
            source_id=args.source_id,
            config_fingerprint=fingerprint,
            snapshot_id=snapshot_id,
            retrieved_at=retrieved_at,
        )

    writer = create_writer(args.output, args.format, gzip_enabled=args.gzip)
    writer.prepare_resume(checkpoint.records_written)
    if checkpoint.complete or checkpoint.records_written >= args.max_records:
        print(json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True))
        return 0

    remaining = args.max_records - checkpoint.records_written
    connector = create_connector(args.source_id, **connector_options)
    http = RetryHttpClient(
        user_agent=f"CompassPublicIntelligence/{__version__}",
        requests_per_second=args.requests_per_second,
        timeout_seconds=args.timeout_seconds,
        retry_policy=RetryPolicy(attempts=args.retry_attempts),
    )
    request = CollectionRequest(
        max_records=remaining,
        page_size=args.page_size,
        max_pages=args.max_pages,
        snapshot_id=checkpoint.snapshot_id,
        retrieved_at=checkpoint.retrieved_at,
        query=args.query,
        from_date=args.from_date,
        to_date=args.to_date,
    )
    batch = []
    batch_checkpoint: dict[str, Any] | None = None

    def commit() -> None:
        nonlocal batch, batch_checkpoint
        if not batch or batch_checkpoint is None:
            return
        count = writer.write_batch(batch)
        checkpoint.records_written += count
        checkpoint.connector_state = dict(batch_checkpoint)
        checkpoint.complete = False
        checkpoint.limit_reached = checkpoint.records_written >= args.max_records
        store.save(checkpoint)
        batch = []
        batch_checkpoint = None

    for collected in connector.collect(http, request, checkpoint.connector_state):
        batch.append(collected.record)
        batch_checkpoint = dict(collected.checkpoint)
        if len(batch) >= args.batch_size:
            commit()
    commit()
    checkpoint.complete = bool(connector.exhausted)
    checkpoint.limit_reached = (
        checkpoint.records_written >= args.max_records and not checkpoint.complete
    )
    store.save(checkpoint)
    print(json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list-sources":
            return _list_sources(args.as_json)
        if args.command == "collect":
            return _collect(args)
    except (KeyError, ValueError, RuntimeError, WriterDependencyError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    sys.exit(main())

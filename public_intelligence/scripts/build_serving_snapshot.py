#!/usr/bin/env python3
"""Build a compact, digest-bound serving index from governed source snapshots."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SOURCE_URLS = {
    "usaspending": "https://api.usaspending.gov/docs/endpoints",
    "sbir": "https://www.sbir.gov/data-resources",
    "grants_gov": "https://www.grants.gov/api",
    "sam_gov": "https://open.gsa.gov/api/get-opportunities-public-api/",
    "datacite": "https://support.datacite.org/docs/api",
    "crossref": "https://www.crossref.org/documentation/funder-registry/funder-data-via-the-api/",
    "openalex": "https://docs.openalex.org/api-entities/works",
    "pubmed": "https://www.ncbi.nlm.nih.gov/home/develop/api/",
    "osti": "https://www.osti.gov/api/v1/docs",
    "federal_register": "https://www.federalregister.gov/developers/documentation/api/v1",
    "uspto_patents": "https://data.uspto.gov/support/transition-guide/patentsview",
    "onr_website": "https://www.onr.navy.mil/sitemap",
}

SOURCE_FILES = {
    "usaspending": "usaspending-n00014-awards.jsonl.gz",
    "sbir": "canonical/sbir-navy.jsonl.gz",
    "grants_gov": "canonical/grants-gov-onr.jsonl.gz",
    "sam_gov": "canonical/sam-gov-onr.jsonl.gz",
    "datacite": "canonical/datacite-onr.jsonl.gz",
    "crossref": "canonical/crossref-onr.jsonl.gz",
    "openalex": "canonical/openalex-onr.jsonl.gz",
    "pubmed": "canonical/pubmed-n00014.jsonl.gz",
    "osti": "canonical/osti-onr.jsonl.gz",
    "federal_register": "canonical/federal-register-onr.jsonl.gz",
    "uspto_patents": "canonical/uspto-patents-onr.jsonl.gz",
    "onr_website": "canonical/onr-website-index.jsonl.gz",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--records-per-source", type=int, default=100)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def reservoir(path: Path, limit: int, seed: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    rng = random.Random(seed)
    for index, record in enumerate(iter_jsonl(path)):
        if index < limit:
            selected.append(record)
            continue
        replacement = rng.randint(0, index)
        if replacement < limit:
            selected[replacement] = record
    return selected


def clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").replace("\u2014", " - ").split())[:limit]


def https_url(record: dict[str, Any], source_id: str) -> str:
    candidates = [record.get("source_url")]
    provenance = record.get("provenance")
    if isinstance(provenance, dict):
        candidates.append(provenance.get("source_url"))
    links = record.get("links")
    if isinstance(links, list):
        candidates = [*links, *candidates]
    for candidate in candidates:
        if str(candidate or "").startswith("https://"):
            return str(candidate)
    return SOURCE_URLS[source_id]


def record_digest(record: dict[str, Any]) -> str:
    provenance = record.get("provenance")
    value = provenance.get("record_sha256") if isinstance(provenance, dict) else None
    value = value or record.get("record_sha256")
    if isinstance(value, str) and len(value) == 64:
        return value
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compact_record(record: dict[str, Any], source_id: str) -> dict[str, Any]:
    identifier = record.get("source_record_id") or record.get("award_id") or record.get("id")
    title = record.get("title") or record.get("description") or identifier or "Public record"
    summary = record.get("abstract") or record.get("summary") or record.get("description") or ""
    organizations = record.get("organizations")
    if not organizations and record.get("recipient_name"):
        organizations = [record["recipient_name"]]
    return {
        "record_id": f"{source_id}:{clean_text(identifier, 180)}",
        "source_id": source_id,
        "title": clean_text(title, 500),
        "summary": clean_text(summary, 500),
        "source_url": https_url(record, source_id),
        "evidence_class": "observed",
        "model_run_id": None,
        "uncertainty": None,
        "record_sha256": record_digest(record),
        "topics": [clean_text(item, 120) for item in (record.get("topics") or [])[:12]],
        "organizations": [clean_text(item, 180) for item in (organizations or [])[:8]],
        "identifiers": record.get("identifiers") or {"source_record_id": identifier},
        "classification": "public",
    }


def funding_model_record(run: dict[str, Any]) -> dict[str, Any]:
    measured = run["measured_holdout"]
    model = run["model"]
    run_id = run["run_id"]
    digest = hashlib.sha256(
        json.dumps(run, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "record_id": f"model:{model['model_id']}",
        "source_id": "sagemaker_model_registry",
        "title": "Funding flow forecast candidate evidence",
        "summary": (
            f"A {model['algorithm']} candidate used {run['dataset']['authentic_training_rows']} "
            f"authentic quarterly rows. Chronological holdout MAE was "
            f"${measured['mae_usd']:,.2f}; empirical interval coverage was "
            f"{measured['empirical_interval_coverage']:.2%}. The package is "
            "PendingManualApproval with no endpoint."
        ),
        "source_url": "https://compass.aws.satsyil.com/intelligence/",
        "evidence_class": "predicted",
        "model_run_id": run_id,
        "uncertainty": {
            "nominal_interval_coverage": measured["nominal_interval_coverage"],
            "empirical_interval_coverage": measured["empirical_interval_coverage"],
            "mean_interval_width_usd": measured["mean_interval_width_usd"],
        },
        "record_sha256": digest,
        "classification": "public",
    }


def transition_model_record(
    card: dict[str, Any],
    receipt: dict[str, Any],
    *,
    registration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdout = card["evaluation"]["holdout"]
    model_id = card["model_id"]
    digest = hashlib.sha256(
        json.dumps(
            {"model_card": card, "training_receipt": receipt},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    registered = bool(registration and registration.get("model_package_arn"))
    state = "PendingManualApproval" if registered else "trained candidate"
    return {
        "record_id": f"model:{model_id}",
        "source_id": "sagemaker_model_registry",
        "title": "Public SBIR transition candidate evidence",
        "summary": (
            f"A {card['algorithm']} candidate used {card['dataset']['records_received']} "
            f"authentic public examples. Chronological holdout ROC AUC was "
            f"{holdout['roc_auc']:.3f}; Brier score was {holdout['brier_score']:.3f}. "
            f"The candidate is {state} with no endpoint and does not measure ONR mission success."
        ),
        "source_url": "https://compass.aws.satsyil.com/intelligence/",
        "evidence_class": "predicted",
        "model_run_id": model_id,
        "uncertainty": {
            "roc_auc": holdout["roc_auc"],
            "brier_score": holdout["brier_score"],
            "precision": holdout["precision"],
            "recall": holdout["recall"],
        },
        "record_sha256": digest,
        "classification": "public",
    }


def transition_model_evidence(
    card: dict[str, Any],
    receipt: dict[str, Any],
    *,
    registration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = "PendingManualApproval" if registration and registration.get("model_package_arn") else "Candidate"
    return {
        "model_id": card["model_id"],
        "model_run_id": card["model_id"],
        "state": state,
        "approved": False,
        "deployed": False,
        "endpoint": None,
        "source_sha256": card["dataset"]["dataset_digest"],
        "model_sha256": receipt["artifact_sha256"],
        "holdout": card["evaluation"]["holdout"],
        "training_records": card["dataset"]["records_received"],
        "model_package_arn": (registration or {}).get("model_package_arn"),
    }


def main() -> int:
    args = parse_args()
    if not 1 <= args.records_per_source <= 500:
        raise SystemExit("records-per-source must be between 1 and 500")
    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    counts_doc = read_json(args.artifact_root / "source-counts.json")
    summary = read_json(args.artifact_root / "usaspending-summary.json")
    funding = read_json(args.artifact_root / "usaspending-obligations.json")
    run_path = next((args.artifact_root / "models" / "funding-forecast").glob("*/run-summary.json"))
    model_run = read_json(run_path)
    transition_dir = args.artifact_root / "models" / "sbir-transition" / "candidate-2026-08-12"
    transition_card_path = transition_dir / "model-card.json"
    transition_receipt_path = transition_dir / "training-receipt.json"
    transition_registration_path = transition_dir / "sagemaker-registration.json"
    transition_card = read_json(transition_card_path) if transition_card_path.is_file() else None
    transition_receipt = read_json(transition_receipt_path) if transition_receipt_path.is_file() else None
    transition_registration = (
        read_json(transition_registration_path) if transition_registration_path.is_file() else None
    )

    records: list[dict[str, Any]] = []
    persisted: list[dict[str, Any]] = []
    for position, source in enumerate(counts_doc["counts"]):
        source_id = source["source_id"]
        path = args.artifact_root / SOURCE_FILES.get(source_id, "")
        state = source["state"]
        if state == "persisted" and path.is_file():
            selected = reservoir(path, args.records_per_source, seed=20260811 + position)
            records.extend(compact_record(record, source_id) for record in selected)
            persisted.append({**source, "url": SOURCE_URLS[source_id]})
        else:
            persisted.append({**source, "url": SOURCE_URLS.get(source_id)})
    records.append(funding_model_record(model_run))
    if transition_card is not None and transition_receipt is not None:
        records.append(
            transition_model_record(
                transition_card,
                transition_receipt,
                registration=transition_registration,
            )
        )

    source_counts = {item["source_id"]: item["count"] for item in counts_doc["counts"]}
    index = {
        "contract": "compass.public-intelligence.evidence-index.v1",
        "version": 1,
        "snapshot_id": args.snapshot_id,
        "snapshot": {
            "as_of_date": counts_doc["as_of_date"],
            "candidate_scope": {
                "award_records": summary["records"],
                "grants": summary["grants"],
                "contracts": summary["contracts"],
                "summed_award_amount_usd": summary["amount_usd"],
                "disclosure": "Department of the Navy plus keyword N00014 candidate scope, not an authoritative inventory of all ONR activity.",
            },
            "source_counts": source_counts,
            "observed_annual_obligations": funding["values"],
            "serving_index_records": len(records),
            "full_records_remain_in_lake": True,
        },
        "sources": persisted,
        "records": records,
    }
    index_bytes = json.dumps(index, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8") + b"\n"
    index_digest = hashlib.sha256(index_bytes).hexdigest()
    manifest = {
        "contract": "compass.public-intelligence.provenance-manifest.v1",
        "version": 1,
        "snapshot_id": args.snapshot_id,
        "generated_at": generated_at,
        "as_of_at": f"{counts_doc['as_of_date']}T23:59:59Z",
        "evidence_class": "public_evidence",
        "data_boundary": {
            "classification": "public",
            "contains_cui": False,
            "pii_minimized": True,
        },
        "evidence_index": {
            "key": f"public-intelligence/snapshots/{args.snapshot_id}/evidence-index.json",
            "sha256": index_digest,
        },
        "sources": persisted,
        "models": [
            {
                "model_id": model_run["model"]["model_id"],
                "model_run_id": model_run["run_id"],
                "state": "PendingManualApproval",
                "approved": False,
                "deployed": False,
                "endpoint": None,
                "source_sha256": model_run["source"]["artifact_sha256"],
                "model_sha256": model_run["model"]["model_sha256"],
                "holdout": model_run["measured_holdout"],
            },
            *(
                [
                    transition_model_evidence(
                        transition_card,
                        transition_receipt,
                        registration=transition_registration,
                    )
                ]
                if transition_card is not None and transition_receipt is not None
                else []
            ),
        ],
    }

    snapshot_dir = args.output_root / "snapshots" / args.snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "evidence-index.json").write_bytes(index_bytes)
    current = args.output_root / "current"
    current.mkdir(parents=True, exist_ok=True)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8") + b"\n"
    (current / "manifest.json").write_bytes(manifest_bytes)
    print(json.dumps({
        "snapshot_id": args.snapshot_id,
        "records": len(records),
        "index_bytes": len(index_bytes),
        "index_sha256": index_digest,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

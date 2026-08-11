"""Bounded preparation and verification for the synthetic Compass demo.

This module runs only through the directly invoked migrator Lambda. It is not
an HTTP API and does not accept caller-selected table names, batch ids, object
keys, users, or license identities. Every mutable scope is a source-controlled
constant below.

The preparation workflow is intentionally split into three operations:

``prepare``
    Validate the five staged synthetic fixtures, refuse to run beside any
    non-demo curated grant, remove only allowlisted demo state, then load the
    baseline grants, licenses, quality receipts, and lineage receipts.

``finalize``
    Bind one completed analytics run to this baseline after the operator has
    invoked the real Analytics Lambda. Only a run requested by the fixed demo
    poweruser, over exactly the baseline record count, can be tagged.

``preflight``
    Re-validate staged objects and database invariants and return a redacted,
    machine-readable receipt. Physical bucket names never appear in results or
    structured log summaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import os
import re
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


FIXTURE_CONTRACT = "compass.synthetic.v1"
PREFLIGHT_SCHEMA = "compass.demo-preflight.v1"
GENERATOR_SEED = 20260810

BASELINE_BATCH_ID = "seed-initial-2026"
BASELINE_RUN_ID = f"run-{BASELINE_BATCH_ID}"
DROP_BATCH_IDS = (
    "drop-good-2026-08",
    "drop-compat-2026-08",
    "drop-bad-2026-08",
)
DEMO_BATCH_IDS = (BASELINE_BATCH_ID, *DROP_BATCH_IDS)
DEMO_RUN_IDS = tuple(f"run-{batch_id}" for batch_id in DEMO_BATCH_IDS)

DEMO_POWERUSER = "poweruser@compass.demo"
DEMO_ANALYTICS_ACTOR = "compass-demo-preparer"
DEMO_USERS = (
    DEMO_POWERUSER,
    "reviewer@compass.demo",
    "viewer@compass.demo",
)
DEMO_MODEL_ACTORS = (*DEMO_USERS, DEMO_ANALYTICS_ACTOR, "system")

STAGED_FIXTURES: Mapping[str, str] = {
    # The ``.fixture`` suffix is deliberately non-ingestible even against an
    # older EventBridge rule that still forwards every created object.
    "portfolio": "demo-stage/baseline/grants_portfolio.fixture",
    "licenses": "demo-stage/baseline/licenses.fixture",
    "drop_good": "demo-stage/drops/drop_good.fixture",
    "drop_compatible": "demo-stage/drops/drop_compatible_variant.fixture",
    "drop_bad": "demo-stage/drops/drop_incompatible_bad.fixture",
}

EXPECTED_DROP_CONTRACTS: Mapping[str, Tuple[str, str, int]] = {
    "drop_good": ("drop-good-2026-08", "canonical", 40),
    "drop_compatible": ("drop-compat-2026-08", "compatible-renamed", 40),
    "drop_bad": ("drop-bad-2026-08", "incompatible-malformed", 60),
}

EXPECTED_LICENSES = frozenset(
    {
        ("Clarivate Web of Science", "Web of Science Core Collection"),
        ("Dimensions", "Dimensions Analytics"),
        ("Crunchbase", "Crunchbase Pro API"),
        ("Lens.org", "Lens.org Patent & Scholarly Search"),
        ("Elsevier", "Scopus & SciVal"),
        ("PitchBook Data", "PitchBook Platform"),
        ("CB Insights", "CB Insights Platform"),
        ("GovTribe", "GovTribe Federal Intelligence"),
    }
)
EXPECTED_ORG_UNITS = frozenset(
    {"ONR-Corporate", "Code-30", "Code-31", "Code-32", "Code-34", "Code-35"}
)
EXPECTED_CLASSIFICATION_BANDS = frozenset({"CUI-Mock", "Public-Mock"})
EXPECTED_PROGRAM_AREAS = frozenset(
    {"AI/ML", "Autonomy", "Undersea", "Directed Energy", "Quantum", "Cyber", "Materials", "Biotech"}
)

BASELINE_RECORD_COUNT = 400
LICENSE_RECORD_COUNT = 8
MAX_FIXTURE_BYTES = 8 * 1024 * 1024
ANALYTICS_RUN_PATTERN = re.compile(r"^tm-[A-Za-z0-9-]{8,80}$")


class DemoPreparationError(ValueError):
    """Raised when the synthetic-only preparation contract is violated."""


@dataclass(frozen=True)
class LoadedFixture:
    logical_name: str
    key: str
    payload: Dict[str, Any]
    sha256: str
    size_bytes: int

    def receipt(self) -> Dict[str, Any]:
        return {
            "logical_name": self.logical_name,
            "logical_locator": f"staged://{self.logical_name}",
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "status": "validated",
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DemoPreparationError(message)


def _fixture_header(payload: Mapping[str, Any], logical_name: str) -> None:
    _require(isinstance(payload, dict), f"{logical_name} must be a JSON object")
    _require(
        payload.get("fixture_contract") == FIXTURE_CONTRACT,
        f"{logical_name} has the wrong fixture contract",
    )
    _require(
        payload.get("synthetic_only") is True,
        f"{logical_name} is not explicitly marked synthetic-only",
    )
    _require(
        payload.get("generator_seed") == GENERATOR_SEED,
        f"{logical_name} has the wrong deterministic generator seed",
    )


def validate_portfolio(payload: Mapping[str, Any]) -> Sequence[Dict[str, Any]]:
    _fixture_header(payload, "portfolio")
    _require(payload.get("batch_id") == BASELINE_BATCH_ID, "portfolio batch id is not allowlisted")
    grants = payload.get("grants")
    _require(isinstance(grants, list), "portfolio grants must be a list")
    _require(
        payload.get("record_count") == BASELINE_RECORD_COUNT == len(grants),
        "portfolio must contain exactly 400 records",
    )

    grant_numbers = set()
    required = {
        "grant_no",
        "title",
        "abstract",
        "program_area",
        "fiscal_year",
        "amount_usd",
        "awardee",
        "org_unit",
        "classification_band",
        "batch_id",
        "created_at",
    }
    for index, grant in enumerate(grants):
        _require(isinstance(grant, dict), f"portfolio record {index} must be an object")
        _require(required.issubset(grant), f"portfolio record {index} is missing required fields")
        grant_no = grant.get("grant_no")
        _require(
            isinstance(grant_no, str) and grant_no.startswith("ONRD-"),
            f"portfolio record {index} does not use the invented ONRD identifier",
        )
        _require(grant_no not in grant_numbers, f"duplicate synthetic grant number {grant_no}")
        grant_numbers.add(grant_no)
        _require(grant.get("batch_id") == BASELINE_BATCH_ID, f"portfolio record {index} changed batch")
        _require(grant.get("org_unit") in EXPECTED_ORG_UNITS, f"portfolio record {index} has unknown org")
        _require(
            grant.get("classification_band") in EXPECTED_CLASSIFICATION_BANDS,
            f"portfolio record {index} is not mock-classified",
        )
        _require(
            grant.get("program_area") in EXPECTED_PROGRAM_AREAS,
            f"portfolio record {index} has unknown program area",
        )
        fiscal_year = grant.get("fiscal_year")
        _require(isinstance(fiscal_year, int) and 2019 <= fiscal_year <= 2026, f"portfolio record {index} has invalid fiscal year")
        amount = grant.get("amount_usd")
        _require(
            isinstance(amount, (int, float)) and not isinstance(amount, bool) and 0 < amount <= 100_000_000,
            f"portfolio record {index} has invalid synthetic amount",
        )
        _require(bool(str(grant.get("title") or "").strip()), f"portfolio record {index} has no title")
        _require(bool(str(grant.get("abstract") or "").strip()), f"portfolio record {index} has no abstract")
        try:
            datetime.fromisoformat(str(grant.get("created_at")).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise DemoPreparationError(f"portfolio record {index} has invalid created_at") from exc
    return grants


def validate_licenses(payload: Mapping[str, Any]) -> Sequence[Dict[str, Any]]:
    _fixture_header(payload, "licenses")
    licenses = payload.get("licenses")
    _require(isinstance(licenses, list), "licenses must be a list")
    _require(
        payload.get("record_count") == LICENSE_RECORD_COUNT == len(licenses),
        "license fixture must contain exactly 8 records",
    )
    identities = set()
    for index, item in enumerate(licenses):
        _require(isinstance(item, dict), f"license record {index} must be an object")
        identity = (str(item.get("vendor") or ""), str(item.get("product") or ""))
        identities.add(identity)
        _require(identity in EXPECTED_LICENSES, f"license record {index} is not allowlisted")
        seats_used = item.get("seats_used")
        seats_total = item.get("seats_total")
        _require(
            isinstance(seats_used, int)
            and isinstance(seats_total, int)
            and 0 <= seats_used <= seats_total <= 1000,
            f"license record {index} has invalid seat counts",
        )
        _require(item.get("status") == "active", f"license record {index} must be active")
        try:
            date.fromisoformat(str(item.get("renews_on")))
        except (TypeError, ValueError) as exc:
            raise DemoPreparationError(f"license record {index} has invalid renewal date") from exc
    _require(identities == EXPECTED_LICENSES, "license identities do not match the fixed synthetic set")
    return licenses


def validate_drop(payload: Mapping[str, Any], logical_name: str) -> Sequence[Any]:
    _fixture_header(payload, logical_name)
    expected_batch, expected_variant, expected_count = EXPECTED_DROP_CONTRACTS[logical_name]
    _require(payload.get("batch_id") == expected_batch, f"{logical_name} batch id is not allowlisted")
    _require(payload.get("schema_variant") == expected_variant, f"{logical_name} schema variant changed")
    records = payload.get("records")
    _require(isinstance(records, list), f"{logical_name} records must be a list")
    _require(
        payload.get("record_count") == expected_count == len(records),
        f"{logical_name} record count changed",
    )
    _require(all(isinstance(record, dict) for record in records), f"{logical_name} contains a non-object record")
    return records


def validate_fixture(logical_name: str, payload: Mapping[str, Any]) -> None:
    if logical_name == "portfolio":
        validate_portfolio(payload)
    elif logical_name == "licenses":
        validate_licenses(payload)
    elif logical_name in EXPECTED_DROP_CONTRACTS:
        validate_drop(payload, logical_name)
    else:
        raise DemoPreparationError(f"unknown fixture {logical_name!r}")


def _default_s3():
    import boto3

    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def load_staged_fixtures(s3=None) -> Dict[str, LoadedFixture]:
    """Load and validate every fixed staged object without returning a bucket."""
    bucket = os.environ.get("DEMO_FIXTURE_BUCKET")
    if not bucket:
        raise DemoPreparationError("DEMO_FIXTURE_BUCKET is not configured")
    s3 = s3 or _default_s3()
    loaded: Dict[str, LoadedFixture] = {}
    for logical_name, key in STAGED_FIXTURES.items():
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
        except Exception:  # noqa: BLE001 - redact the physical locator
            raise DemoPreparationError(
                f"{logical_name} staged fixture is unavailable"
            ) from None
        body = response["Body"].read(MAX_FIXTURE_BYTES + 1)
        _require(len(body) <= MAX_FIXTURE_BYTES, f"{logical_name} exceeds the fixture size limit")
        metadata = response.get("Metadata") or {}
        digest = hashlib.sha256(body).hexdigest()
        _require(
            metadata.get("fixture-sha256") == digest,
            f"{logical_name} staged hash metadata does not match its bytes",
        )
        _require(metadata.get("synthetic-only") == "true", f"{logical_name} lacks staged synthetic metadata")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DemoPreparationError(f"{logical_name} is not valid UTF-8 JSON") from exc
        validate_fixture(logical_name, payload)
        loaded[logical_name] = LoadedFixture(
            logical_name=logical_name,
            key=key,
            payload=dict(payload),
            sha256=digest,
            size_bytes=len(body),
        )
    return loaded


def _record_count(cur, name: str, counts: Dict[str, int]) -> None:
    counts[name] = max(0, int(cur.rowcount or 0))


def _license_predicate() -> Tuple[str, list[str]]:
    clauses = []
    params: list[str] = []
    for vendor, product in sorted(EXPECTED_LICENSES):
        clauses.append("(vendor = %s AND product = %s)")
        params.extend([vendor, product])
    return "(" + " OR ".join(clauses) + ")", params


def _ensure_no_non_demo_state(cur) -> None:
    """Refuse to reset beside state not owned by the fixed demo contract."""
    checks = [
        (
            "curated grants",
            "SELECT count(*) FROM grants_curated "
            "WHERE batch_id IS NULL OR NOT (batch_id = ANY(%s))",
            (list(DEMO_BATCH_IDS),),
        ),
        (
            "raw grants",
            "SELECT count(*) FROM grants_raw "
            "WHERE batch_id IS NULL OR NOT (batch_id = ANY(%s))",
            (list(DEMO_BATCH_IDS),),
        ),
        (
            "quality receipts",
            "SELECT count(*) FROM grant_quality "
            "WHERE batch_id IS NULL OR NOT (batch_id = ANY(%s))",
            (list(DEMO_BATCH_IDS),),
        ),
        (
            "approvals",
            "SELECT count(*) FROM approvals "
            "WHERE requested_by IS NULL OR NOT (requested_by = ANY(%s))",
            (list(DEMO_USERS),),
        ),
        (
            "model runs",
            "SELECT count(*) FROM model_runs WHERE NOT COALESCE(("
            "params_jsonb->>'demo_baseline' = 'true' "
            "OR params_jsonb->>'requested_by' = ANY(%s) "
            "OR params_jsonb->>'actor' = ANY(%s)), false)",
            (list(DEMO_MODEL_ACTORS), list(DEMO_MODEL_ACTORS)),
        ),
        (
            "anomalies",
            "SELECT count(*) FROM anomalies WHERE NOT COALESCE(("
            "grant_id IN (SELECT id FROM grants_curated WHERE batch_id = ANY(%s)) "
            "OR (kind IN ('quality_violation', 'batch_quarantined') "
            "AND reason LIKE ANY(%s))), false)",
            (
                list(DEMO_BATCH_IDS),
                [f"[{batch_id}]%" for batch_id in DEMO_BATCH_IDS],
            ),
        ),
        (
            "lineage nodes",
            "SELECT count(*) FROM lineage_nodes WHERE NOT ("
            "run_id = ANY(%s) OR run_id IN (SELECT run_id FROM model_runs))",
            (list(DEMO_RUN_IDS),),
        ),
        (
            "lineage edges",
            "SELECT count(*) FROM lineage_edges WHERE NOT ("
            "run_id = ANY(%s) OR run_id IN (SELECT run_id FROM model_runs))",
            (list(DEMO_RUN_IDS),),
        ),
        (
            "topics",
            "SELECT count(*) FROM topics "
            "WHERE run_id NOT IN (SELECT run_id FROM model_runs)",
            None,
        ),
        (
            "topic assignments",
            "SELECT count(*) FROM grant_topics WHERE "
            "run_id NOT IN (SELECT run_id FROM model_runs) "
            "OR grant_id NOT IN (SELECT id FROM grants_curated WHERE batch_id = ANY(%s))",
            (list(DEMO_BATCH_IDS),),
        ),
    ]
    license_sql, license_params = _license_predicate()
    checks.append(
        (
            "licenses",
            f"SELECT count(*) FROM licenses WHERE NOT {license_sql}",
            tuple(license_params),
        )
    )

    unexpected = []
    for label, query, params in checks:
        cur.execute(query, params)
        count = int(cur.fetchone()[0])
        if count:
            unexpected.append({"scope": label, "rows": count})
    if unexpected:
        labels = ", ".join(item["scope"] for item in unexpected)
        raise DemoPreparationError(
            f"synthetic reset refused because non-demo state is present: {labels}"
        )


def reset_synthetic_state(cur) -> Dict[str, int]:
    """Delete only fixed demo identities after the non-demo guard has passed."""
    _ensure_no_non_demo_state(cur)
    counts: Dict[str, int] = {}

    cur.execute(
        "SELECT run_id FROM model_runs "
        "WHERE params_jsonb->>'demo_baseline' = 'true' "
        "   OR params_jsonb->>'requested_by' = ANY(%s) "
        "   OR params_jsonb->>'actor' = ANY(%s)",
        (list(DEMO_MODEL_ACTORS), list(DEMO_MODEL_ACTORS)),
    )
    analytics_run_ids = [str(row[0]) for row in cur.fetchall()]

    cur.execute(
        "DELETE FROM grant_topics "
        "WHERE grant_id IN (SELECT id FROM grants_curated WHERE batch_id = ANY(%s)) "
        "   OR run_id = ANY(%s)",
        (list(DEMO_BATCH_IDS), analytics_run_ids),
    )
    _record_count(cur, "grant_topics", counts)

    cur.execute("DELETE FROM topics WHERE run_id = ANY(%s)", (analytics_run_ids,))
    _record_count(cur, "topics", counts)

    cur.execute(
        "DELETE FROM lineage_edges WHERE run_id = ANY(%s)",
        (list(DEMO_RUN_IDS) + analytics_run_ids,),
    )
    _record_count(cur, "lineage_edges", counts)
    cur.execute(
        "DELETE FROM lineage_nodes WHERE run_id = ANY(%s)",
        (list(DEMO_RUN_IDS) + analytics_run_ids,),
    )
    _record_count(cur, "lineage_nodes", counts)

    cur.execute("DELETE FROM model_runs WHERE run_id = ANY(%s)", (analytics_run_ids,))
    _record_count(cur, "model_runs", counts)

    cur.execute(
        "DELETE FROM anomalies "
        "WHERE grant_id IN (SELECT id FROM grants_curated WHERE batch_id = ANY(%s)) "
        "   OR (kind IN ('quality_violation', 'batch_quarantined') "
        "       AND reason LIKE ANY(%s))",
        (
            list(DEMO_BATCH_IDS),
            [f"[{batch_id}]%" for batch_id in DEMO_BATCH_IDS],
        ),
    )
    _record_count(cur, "anomalies", counts)

    cur.execute("DELETE FROM grant_quality WHERE batch_id = ANY(%s)", (list(DEMO_BATCH_IDS),))
    _record_count(cur, "grant_quality", counts)
    cur.execute("DELETE FROM grants_raw WHERE batch_id = ANY(%s)", (list(DEMO_BATCH_IDS),))
    _record_count(cur, "grants_raw", counts)
    cur.execute("DELETE FROM grants_curated WHERE batch_id = ANY(%s)", (list(DEMO_BATCH_IDS),))
    _record_count(cur, "grants_curated", counts)

    license_deleted = 0
    for vendor, product in sorted(EXPECTED_LICENSES):
        cur.execute(
            "DELETE FROM licenses WHERE vendor = %s AND product = %s",
            (vendor, product),
        )
        license_deleted += max(0, int(cur.rowcount or 0))
    counts["licenses"] = license_deleted

    cur.execute(
        "DELETE FROM approvals "
        "WHERE subject_type = 'export' AND requested_by = ANY(%s)",
        (list(DEMO_USERS),),
    )
    _record_count(cur, "approvals", counts)
    return counts


def _insert_baseline(cur, fixtures: Mapping[str, LoadedFixture]) -> Dict[str, int]:
    grants = validate_portfolio(fixtures["portfolio"].payload)
    licenses = validate_licenses(fixtures["licenses"].payload)

    grant_values = [
        (
            grant["grant_no"],
            grant["title"],
            grant["abstract"],
            grant["program_area"],
            grant["fiscal_year"],
            grant["amount_usd"],
            grant["awardee"],
            grant["org_unit"],
            grant["classification_band"],
            BASELINE_BATCH_ID,
            grant["created_at"],
        )
        for grant in grants
    ]
    cur.executemany(
        "INSERT INTO grants_curated "
        "(grant_no, title, abstract, program_area, fiscal_year, amount_usd, "
        " awardee, org_unit, classification_band, batch_id, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz)",
        grant_values,
    )

    license_values = [
        (
            item["vendor"],
            item["product"],
            item.get("datasets") or [],
            item.get("entitlements"),
            item.get("seats_used"),
            item.get("seats_total"),
            item.get("renews_on"),
            item.get("owner"),
            item.get("status"),
        )
        for item in licenses
    ]
    cur.executemany(
        "INSERT INTO licenses "
        "(vendor, product, datasets, entitlements, seats_used, seats_total, renews_on, owner, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::date, %s, %s)",
        license_values,
    )

    quality_rules = (
        "fixture_contract",
        "required_fields",
        "unique_grant_no",
        "recognized_org_unit",
        "mock_classification",
    )
    details = json.dumps(
        {
            "fixture_contract": FIXTURE_CONTRACT,
            "score_formula": "passed_rows / checked_rows * 100",
            "source": "staged://portfolio",
            "synthetic_only": True,
        }
    )
    cur.executemany(
        "INSERT INTO grant_quality "
        "(batch_id, run_id, rule, passed_rows, failed_rows, score, details_jsonb) "
        "VALUES (%s, %s, %s, %s, 0, 100.00, %s::jsonb) "
        "ON CONFLICT (run_id, rule) DO UPDATE SET "
        "batch_id = EXCLUDED.batch_id, passed_rows = EXCLUDED.passed_rows, "
        "failed_rows = 0, score = 100.00, details_jsonb = EXCLUDED.details_jsonb, "
        "created_at = now()",
        [
            (BASELINE_BATCH_ID, BASELINE_RUN_ID, rule, BASELINE_RECORD_COUNT, details)
            for rule in quality_rules
        ],
    )

    lineage_nodes = [
        (
            BASELINE_RUN_ID,
            "src-fixture",
            "source",
            "Synthetic baseline fixture",
            {
                "record_count": BASELINE_RECORD_COUNT,
                "fixture_contract": FIXTURE_CONTRACT,
                "synthetic_only": True,
            },
        ),
        (
            BASELINE_RUN_ID,
            "baseline-validation",
            "stage",
            "Baseline contract validation",
            {"decision": "pass", "rows_checked": BASELINE_RECORD_COUNT, "rows_passed": BASELINE_RECORD_COUNT},
        ),
        (
            BASELINE_RUN_ID,
            "curated",
            "table",
            "grants_curated",
            {"batch_id": BASELINE_BATCH_ID, "rows": BASELINE_RECORD_COUNT, "rls": "FORCE ROW LEVEL SECURITY on org_unit"},
        ),
        (
            BASELINE_RUN_ID,
            "exec-dashboard",
            "dashboard",
            "Executive dashboard",
            {"batch_id": BASELINE_BATCH_ID},
        ),
    ]
    cur.executemany(
        "INSERT INTO lineage_nodes (run_id, node_id, kind, label, meta_jsonb) "
        "VALUES (%s, %s, %s, %s, %s::jsonb) "
        "ON CONFLICT (run_id, node_id) DO UPDATE SET "
        "kind = EXCLUDED.kind, label = EXCLUDED.label, meta_jsonb = EXCLUDED.meta_jsonb",
        [(run_id, node_id, kind, label, json.dumps(meta)) for run_id, node_id, kind, label, meta in lineage_nodes],
    )
    cur.executemany(
        "INSERT INTO lineage_edges (run_id, from_node, to_node) VALUES (%s, %s, %s) "
        "ON CONFLICT (run_id, from_node, to_node) DO NOTHING",
        [
            (BASELINE_RUN_ID, "src-fixture", "baseline-validation"),
            (BASELINE_RUN_ID, "baseline-validation", "curated"),
            (BASELINE_RUN_ID, "curated", "exec-dashboard"),
        ],
    )

    cur.execute(
        "INSERT INTO audit_log (actor, action, resource, detail_jsonb) "
        "VALUES (%s, 'demo_reseed', %s, %s::jsonb)",
        (
            "compass-demo-preparer",
            f"synthetic-batch:{BASELINE_BATCH_ID}",
            json.dumps(
                {
                    "fixture_contract": FIXTURE_CONTRACT,
                    "portfolio_sha256": fixtures["portfolio"].sha256,
                    "licenses_sha256": fixtures["licenses"].sha256,
                    "drop_good_sha256": fixtures["drop_good"].sha256,
                    "drop_compatible_sha256": fixtures["drop_compatible"].sha256,
                    "drop_bad_sha256": fixtures["drop_bad"].sha256,
                    "grants_loaded": len(grants),
                    "licenses_loaded": len(licenses),
                    "status": "baseline_loaded",
                }
            ),
        ),
    )
    return {
        "grants": len(grants),
        "licenses": len(licenses),
        "quality_receipts": len(quality_rules),
        "lineage_nodes": len(lineage_nodes),
        "lineage_edges": 3,
    }


def _transaction(conn, operation):
    previous = conn.autocommit
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            result = operation(cur)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = previous


def prepare(conn, s3=None) -> Dict[str, Any]:
    fixtures = load_staged_fixtures(s3=s3)

    def operation(cur):
        removed = reset_synthetic_state(cur)
        loaded = _insert_baseline(cur, fixtures)
        return {"removed": removed, "loaded": loaded}

    result = _transaction(conn, operation)
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "baseline_ready",
        "next_action": "run_baseline_analytics",
        "fixtures": [fixtures[name].receipt() for name in STAGED_FIXTURES],
        **result,
    }


def finalize_analytics(conn, run_id: Any) -> Dict[str, Any]:
    run_id = str(run_id or "")
    _require(bool(ANALYTICS_RUN_PATTERN.fullmatch(run_id)), "analytics run id is invalid")

    def operation(cur):
        cur.execute(
            "SELECT kind, params_jsonb, metrics_jsonb FROM model_runs WHERE run_id = %s",
            (run_id,),
        )
        row = cur.fetchone()
        _require(row is not None, "analytics run does not exist")
        kind, params, metrics = row
        params = params or {}
        metrics = metrics or {}
        _require(kind == "topic_model", "analytics run has the wrong kind")
        _require(
            params.get("requested_by") == DEMO_ANALYTICS_ACTOR,
            "analytics run used the wrong service actor",
        )
        _require(params.get("org_unit") == "ONR-Corporate", "analytics run used the wrong organization")
        _require(metrics.get("n_docs") == BASELINE_RECORD_COUNT, "analytics run did not model exactly the baseline")
        _require(metrics.get("k") == 8, "analytics run did not use the baseline topic count")
        cur.execute(
            "UPDATE model_runs SET params_jsonb = COALESCE(params_jsonb, '{}'::jsonb) || %s::jsonb "
            "WHERE run_id = %s",
            (
                json.dumps(
                    {
                        "demo_baseline": True,
                        "fixture_contract": FIXTURE_CONTRACT,
                        "baseline_batch_id": BASELINE_BATCH_ID,
                    }
                ),
                run_id,
            ),
        )
        cur.execute("SELECT count(*) FROM topics WHERE run_id = %s", (run_id,))
        topics = int(cur.fetchone()[0])
        cur.execute("SELECT count(*) FROM grant_topics WHERE run_id = %s", (run_id,))
        assignments = int(cur.fetchone()[0])
        _require(topics == 8, "analytics run did not persist exactly 8 topics")
        _require(assignments >= BASELINE_RECORD_COUNT, "analytics run has incomplete topic assignments")
        cur.execute(
            "INSERT INTO audit_log (actor, action, resource, detail_jsonb) "
            "VALUES (%s, 'demo_analytics_ready', %s, %s::jsonb)",
            (
                "compass-demo-preparer",
                f"model_run:{run_id}",
                json.dumps({"run_id": run_id, "topics": topics, "status": "baseline_ready"}),
            ),
        )
        return {"run_id": run_id, "topics": topics, "topic_assignments": assignments}

    result = _transaction(conn, operation)
    return {"schema_version": PREFLIGHT_SCHEMA, "status": "analytics_ready", **result}


def _check(checks: list, check_id: str, observed: Any, expected: Any, passed: bool) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "pass" if passed else "fail",
            "observed": observed,
            "expected": expected,
        }
    )


def _database_checks(
    cur,
    expected_fixture_hashes: Optional[Mapping[str, str]] = None,
) -> Tuple[list, Optional[str]]:
    checks = []
    cur.execute(
        "SELECT count(*), count(DISTINCT grant_no), count(DISTINCT org_unit) "
        "FROM grants_curated WHERE batch_id = %s",
        (BASELINE_BATCH_ID,),
    )
    total, unique_grants, org_units = (int(value) for value in cur.fetchone())
    _check(checks, "database.baseline_grants", total, BASELINE_RECORD_COUNT, total == BASELINE_RECORD_COUNT)
    _check(checks, "database.unique_grants", unique_grants, BASELINE_RECORD_COUNT, unique_grants == BASELINE_RECORD_COUNT)
    _check(checks, "database.org_coverage", org_units, len(EXPECTED_ORG_UNITS), org_units == len(EXPECTED_ORG_UNITS))

    cur.execute(
        "SELECT count(*) FROM grants_curated "
        "WHERE batch_id IS NULL OR NOT (batch_id = ANY(%s))",
        (list(DEMO_BATCH_IDS),),
    )
    non_demo = int(cur.fetchone()[0])
    _check(checks, "database.synthetic_only", non_demo, 0, non_demo == 0)

    if expected_fixture_hashes is not None:
        cur.execute(
            "SELECT detail_jsonb FROM audit_log "
            "WHERE actor = 'compass-demo-preparer' AND action = 'demo_reseed' "
            "ORDER BY at DESC LIMIT 1"
        )
        row = cur.fetchone()
        detail = (row[0] if row else None) or {}
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except json.JSONDecodeError:
                detail = {}
        hash_fields = {
            "portfolio": "portfolio_sha256",
            "licenses": "licenses_sha256",
            "drop_good": "drop_good_sha256",
            "drop_compatible": "drop_compatible_sha256",
            "drop_bad": "drop_bad_sha256",
        }
        observed_hashes = {
            name: detail.get(field) for name, field in hash_fields.items()
        }
        hashes_match = all(
            observed_hashes.get(name) == expected_fixture_hashes.get(name)
            for name in hash_fields
        )
        _check(
            checks,
            "database.fixture_hash_receipt",
            observed_hashes,
            dict(expected_fixture_hashes),
            hashes_match,
        )

    cur.execute("SELECT count(*) FROM grants_raw")
    raw_total = int(cur.fetchone()[0])
    _check(checks, "database.raw_landing_pristine", raw_total, 0, raw_total == 0)

    cur.execute(
        "SELECT count(*), COALESCE(min(score), 0) FROM grant_quality WHERE batch_id = %s",
        (BASELINE_BATCH_ID,),
    )
    quality_count, min_score = cur.fetchone()
    _check(checks, "database.quality_receipts", int(quality_count), 5, int(quality_count) == 5 and float(min_score) == 100.0)
    cur.execute("SELECT count(*) FROM grant_quality")
    quality_total = int(cur.fetchone()[0])
    _check(checks, "database.quality_receipts_total", quality_total, 5, quality_total == 5)

    cur.execute("SELECT count(*) FROM lineage_nodes WHERE run_id = %s", (BASELINE_RUN_ID,))
    lineage_nodes = int(cur.fetchone()[0])
    cur.execute("SELECT count(*) FROM lineage_edges WHERE run_id = %s", (BASELINE_RUN_ID,))
    lineage_edges = int(cur.fetchone()[0])
    _check(checks, "database.baseline_lineage", {"nodes": lineage_nodes, "edges": lineage_edges}, {"nodes": 4, "edges": 3}, lineage_nodes == 4 and lineage_edges == 3)

    license_sql, license_params = _license_predicate()
    cur.execute(
        "SELECT count(*) FROM licenses WHERE " + license_sql,
        tuple(license_params),
    )
    licenses = int(cur.fetchone()[0])
    _check(checks, "database.licenses", licenses, LICENSE_RECORD_COUNT, licenses == LICENSE_RECORD_COUNT)
    cur.execute("SELECT count(*) FROM licenses")
    license_total = int(cur.fetchone()[0])
    _check(checks, "database.licenses_total", license_total, LICENSE_RECORD_COUNT, license_total == LICENSE_RECORD_COUNT)

    cur.execute("SELECT count(*) FROM approvals")
    approvals = int(cur.fetchone()[0])
    _check(checks, "database.approval_inbox_pristine", approvals, 0, approvals == 0)

    cur.execute(
        "SELECT count(*) FROM anomalies WHERE "
        "kind <> 'funding_zscore' OR grant_id IS NULL OR grant_id NOT IN ("
        "SELECT id FROM grants_curated WHERE batch_id = %s)",
        (BASELINE_BATCH_ID,),
    )
    unrelated_anomalies = int(cur.fetchone()[0])
    _check(checks, "database.anomalies_bound_to_baseline", unrelated_anomalies, 0, unrelated_anomalies == 0)

    cur.execute(
        "SELECT "
        "  (SELECT count(*) FROM grants_raw WHERE batch_id = ANY(%s)), "
        "  (SELECT count(*) FROM grants_curated WHERE batch_id = ANY(%s)), "
        "  (SELECT count(*) FROM grant_quality WHERE batch_id = ANY(%s))",
        (list(DROP_BATCH_IDS), list(DROP_BATCH_IDS), list(DROP_BATCH_IDS)),
    )
    raw_drops, curated_drops, quality_drops = (int(value) for value in cur.fetchone())
    drop_residue = {"raw": raw_drops, "curated": curated_drops, "quality": quality_drops}
    _check(checks, "database.demo_drops_not_ingested", drop_residue, {"raw": 0, "curated": 0, "quality": 0}, not any(drop_residue.values()))

    cur.execute(
        "SELECT run_id, metrics_jsonb FROM model_runs "
        "WHERE params_jsonb->>'demo_baseline' = 'true' ORDER BY created_at DESC",
    )
    analytics_rows = cur.fetchall()
    analytics_run_id = str(analytics_rows[0][0]) if len(analytics_rows) == 1 else None
    analytics_metrics = analytics_rows[0][1] if len(analytics_rows) == 1 else {}
    analytics_ok = (
        len(analytics_rows) == 1
        and analytics_metrics.get("n_docs") == BASELINE_RECORD_COUNT
        and analytics_metrics.get("k") == 8
    )
    _check(
        checks,
        "database.baseline_analytics",
        {"runs": len(analytics_rows), "run_id": analytics_run_id, "metrics": analytics_metrics},
        {"runs": 1, "n_docs": BASELINE_RECORD_COUNT, "k": 8},
        analytics_ok,
    )

    cur.execute("SELECT count(*) FROM model_runs")
    model_run_total = int(cur.fetchone()[0])
    _check(checks, "database.model_runs_total", model_run_total, 1, model_run_total == 1)

    cur.execute("SELECT count(*) FROM topics")
    topic_total = int(cur.fetchone()[0])
    _check(checks, "database.topics_total", topic_total, 8, topic_total == 8)

    if analytics_run_id:
        cur.execute(
            "SELECT count(*) FROM grant_topics WHERE run_id <> %s OR grant_id NOT IN ("
            "SELECT id FROM grants_curated WHERE batch_id = %s)",
            (analytics_run_id, BASELINE_BATCH_ID),
        )
        unrelated_assignments = int(cur.fetchone()[0])
    else:
        unrelated_assignments = -1
    _check(
        checks,
        "database.topic_assignments_bound",
        unrelated_assignments,
        0,
        unrelated_assignments == 0,
    )

    cur.execute("SELECT count(*) FROM lineage_nodes")
    lineage_node_total = int(cur.fetchone()[0])
    cur.execute("SELECT count(*) FROM lineage_edges")
    lineage_edge_total = int(cur.fetchone()[0])
    _check(
        checks,
        "database.lineage_total",
        {"nodes": lineage_node_total, "edges": lineage_edge_total},
        {"nodes": 9, "edges": 8},
        lineage_node_total == 9 and lineage_edge_total == 8,
    )
    return checks, analytics_run_id


def preflight(conn, s3=None) -> Dict[str, Any]:
    fixtures = load_staged_fixtures(s3=s3)

    def operation(cur):
        return _database_checks(
            cur,
            {name: fixture.sha256 for name, fixture in fixtures.items()},
        )

    checks, analytics_run_id = _transaction(conn, operation)
    fixture_checks = [fixture.receipt() for fixture in fixtures.values()]
    ready = all(check["status"] == "pass" for check in checks)
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "fixture_contract": FIXTURE_CONTRACT,
        "fixtures": fixture_checks,
        "checks": checks,
        "analytics_run_id": analytics_run_id,
        "storage_disclosure": "logical locators only",
    }

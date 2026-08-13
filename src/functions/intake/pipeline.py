"""Ingest pipeline stages: S3 → ``grants_raw`` (Fetch) → ``grants_curated`` (Persist).

These are the two intake-owned states of ``statemachines/intake.asl.yaml``. The
quality gate sits between them and is a separate Lambda.

Data flow
---------
``Fetch`` reads the dropped object, parses and normalizes it
(``normalize.py``), and upserts one ``grants_raw`` row per source record. It
returns only a small manifest - batch id, run id, counts - never the records
themselves, so the Step Functions payload stays far below the 256 KB state
limit no matter how large the drop is. Every later stage re-reads the rows it
needs from ``grants_raw`` by ``batch_id``.

``Persist`` curates the rows the quality gate marked ``passed``, optionally
embedding each abstract with Titan v2 for the RAG route, and inserts them into
``grants_curated``.

Identity and RLS
----------------
This is machine-to-machine work with no end user, so the pipeline runs under
the corporate org context (``compass.org_unit = 'ONR-Corporate'``). That is the
one context the ``grants_curated`` INSERT policy accepts for rows belonging to
*any* unit - a batch legitimately contains Code-30, Code-32 and Code-34 awards.
It is still the real policy doing the work: the connection is
``compass_app`` (``compass_common.db`` sets the role), the table is
``FORCE ROW LEVEL SECURITY``, and the GUC is set with ``SET LOCAL`` inside the
transaction so it cannot leak to the next invocation. The corporate context is
also what makes ``INSERT … RETURNING id`` legal here - under RLS, ``RETURNING``
reads the new row back through the SELECT policy, which a unit context would
refuse for another unit's award.

Idempotency
-----------
The batch id is deterministic (from the drop envelope, else derived from the
object key), and every write is an upsert keyed on ``(batch_id, row_index)``
for raw rows, ``grant_no`` for curated rows, and the primary keys for lineage.
Re-dropping the same file therefore re-runs the same batch instead of doubling
it - which matters, because a demo drops the same file more than once.
"""
from __future__ import annotations

import json
import hashlib
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from compass_common import audit, config, db, operational_evidence

import normalize

PIPELINE_ORG_UNIT = config.CORPORATE_ORG_UNIT     # "ONR-Corporate"
PIPELINE_ACTOR = "compass-intake-pipeline"

# EventBridge is restricted to ``drops/``. The skip list remains as defense in
# depth for direct function or state-machine invocations with another key.
DEFAULT_SKIP_PREFIXES = "demo-stage/,exports/,rmf/,quarantine/,tmp/,athena-results/"
INGESTIBLE_SUFFIXES = (".json", ".jsonl", ".ndjson")
DEFAULT_MAX_OBJECT_BYTES = 8 * 1024 * 1024

_S3 = None


def run_id_for(batch_id: str) -> str:
    """``run-<batch_id>`` - the convention the catalog and lineage routes join on."""
    return f"run-{batch_id}"


def _s3():
    global _S3
    if _S3 is None:
        import boto3

        _S3 = boto3.client("s3", region_name=config.aws_region())
    return _S3


def _skip_prefixes() -> Tuple[str, ...]:
    raw = os.environ.get("INGEST_SKIP_PREFIXES", DEFAULT_SKIP_PREFIXES)
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def is_ingestible(key: str, size: Optional[int] = None) -> Tuple[bool, str]:
    """Should this object start an ingest run? Returns (ok, reason)."""
    if not key:
        return False, "empty object key"
    if key.endswith("/"):
        return False, "object key is a folder marker"
    for prefix in _skip_prefixes():
        if key.startswith(prefix):
            return False, f"key is under the non-ingest prefix {prefix!r}"
    if not key.lower().endswith(INGESTIBLE_SUFFIXES):
        return False, f"unsupported extension (expected one of {', '.join(INGESTIBLE_SUFFIXES)})"
    max_bytes = int(os.environ.get("INGEST_MAX_OBJECT_BYTES", DEFAULT_MAX_OBJECT_BYTES))
    if size is not None and size > max_bytes:
        return False, f"object is {size} bytes, above the {max_bytes}-byte ingest limit"
    return True, "ingestible"


def read_object(bucket: str, key: str) -> str:
    """Read an S3 object as UTF-8 text.

    EventBridge S3 events deliver the key unencoded, but the older notification
    shape URL-encodes it; if the first GET 404s on a key containing escapes we
    retry with the decoded form rather than failing a real drop.
    """
    from urllib.parse import unquote_plus

    client = _s3()
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
    except client.exceptions.NoSuchKey:
        decoded = unquote_plus(key)
        if decoded == key:
            raise
        obj = client.get_object(Bucket=bucket, Key=decoded)
    return obj["Body"].read().decode("utf-8")


# --------------------------------------------------------------------------- #
# Lineage
# --------------------------------------------------------------------------- #
def upsert_lineage_nodes(cur, run_id: str, nodes: Sequence[Dict[str, Any]]) -> None:
    """Write ``lineage_nodes`` for this run (upsert - a re-run refreshes meta)."""
    for node in nodes:
        cur.execute(
            "INSERT INTO lineage_nodes (run_id, node_id, kind, label, meta_jsonb) "
            "VALUES (%s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (run_id, node_id) DO UPDATE "
            "SET kind = EXCLUDED.kind, label = EXCLUDED.label, "
            "    meta_jsonb = EXCLUDED.meta_jsonb",
            (
                run_id,
                node["node_id"],
                node["kind"],
                node["label"],
                json.dumps(node.get("meta") or {}, default=str),
            ),
        )


def upsert_lineage_edges(cur, run_id: str, edges: Sequence[Tuple[str, str]]) -> None:
    for from_node, to_node in edges:
        cur.execute(
            "INSERT INTO lineage_edges (run_id, from_node, to_node) VALUES (%s, %s, %s) "
            "ON CONFLICT (run_id, from_node, to_node) DO NOTHING",
            (run_id, from_node, to_node),
        )


# --------------------------------------------------------------------------- #
# Fetch stage
# --------------------------------------------------------------------------- #
def _upsert_raw_rows(
    cur, batch_id: str, source_file: str, envelopes: Sequence[Dict[str, Any]]
) -> Tuple[int, int]:
    """Upsert one ``grants_raw`` row per record, keyed (batch_id, row_index).

    ``grants_raw`` has no natural key and ``compass_app`` holds no DELETE grant,
    so re-ingest is an explicit update-then-insert per row. Batches here are
    tens to hundreds of rows; a bulk loader would need a real unique index.
    """
    inserted = updated = 0
    for env in envelopes:
        payload = json.dumps(env, default=str)
        row_index = str(env["meta"]["row_index"])
        cur.execute(
            "UPDATE grants_raw SET raw_jsonb = %s::jsonb, source_file = %s, "
            "ingested_at = now() "
            "WHERE batch_id = %s AND raw_jsonb->'meta'->>'row_index' = %s",
            (payload, source_file, batch_id, row_index),
        )
        if cur.rowcount:
            updated += cur.rowcount
            continue
        cur.execute(
            "INSERT INTO grants_raw (source_file, batch_id, raw_jsonb) "
            "VALUES (%s, %s, %s::jsonb)",
            (source_file, batch_id, payload),
        )
        inserted += 1
    return inserted, updated


def fetch_stage(detail: Dict[str, Any]) -> Dict[str, Any]:
    """Read the dropped object, normalize it, land it in ``grants_raw``.

    ``detail`` is the EventBridge S3 ``Object Created`` detail (or any dict with
    ``bucket.name`` / ``object.key``). Returns the run manifest the state
    machine threads through the remaining states.
    """
    bucket = ((detail or {}).get("bucket") or {}).get("name") or os.environ.get("RAW_BUCKET")
    obj = (detail or {}).get("object") or {}
    key = obj.get("key") or ""
    size = obj.get("size")

    ok, reason = is_ingestible(key, size)
    if not bucket or not ok:
        return {
            "status": "skipped",
            "reason": reason if bucket else "no bucket in the event and RAW_BUCKET is unset",
            "source_file": f"landing://drops/{os.path.basename(key)}" if key else None,
        }

    text = read_object(bucket, key)
    source_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source_object_version = str(obj.get("version-id") or obj.get("versionId") or "") or None
    logical_source = f"landing://drops/{os.path.basename(key)}"
    envelope = normalize.parse_drop(text, key=key, source_file=logical_source)
    records = normalize.normalize_envelope(envelope)
    batch_id = envelope.batch_id
    run_id = run_id_for(batch_id)

    meta = {
        "batch_id": batch_id,
        "run_id": run_id,
        "source_file": logical_source,
        "schema_variant": envelope.schema_variant,
        "fetched_at": normalize.utc_now_iso(),
    }
    raw_envelopes = [r.to_jsonb(meta=meta) for r in records]
    normalized_ok = sum(1 for r in records if not r.issues)

    conn = db.get_conn()
    with db.set_org(conn, PIPELINE_ORG_UNIT) as c, c.cursor() as cur:
        inserted, updated = _upsert_raw_rows(cur, batch_id, logical_source, raw_envelopes)
        upsert_lineage_nodes(
            cur,
            run_id,
            [
                {
                    "node_id": "src-file",
                    "kind": "source",
                    "label": logical_source,
                    "meta": {
                        "schema_variant": envelope.schema_variant,
                        "record_count": len(records),
                        "parse_errors": envelope.parse_errors,
                        "source_sha256": source_sha256,
                        "source_object_version": source_object_version,
                    },
                },
                {
                    "node_id": "raw",
                    "kind": "table",
                    "label": "grants_raw",
                    "meta": {
                        "batch_id": batch_id,
                        "rows": len(raw_envelopes),
                        "inserted": inserted,
                        "updated": updated,
                        "rows_normalized_clean": normalized_ok,
                    },
                },
            ],
        )
        upsert_lineage_edges(cur, run_id, [("src-file", "raw")])
        audit.write_audit(
            c,
            actor=PIPELINE_ACTOR,
            action="ingest_fetch",
            resource=f"grants_raw:{batch_id}",
            detail={
                "source_file": logical_source,
                "run_id": run_id,
                "rows": len(raw_envelopes),
                "inserted": inserted,
                "updated": updated,
                "schema_variant": envelope.schema_variant,
            },
        )

    result = {
        "status": "ok",
        "action": "fetch",
        "batch_id": batch_id,
        "run_id": run_id,
        "source_file": logical_source,
        "schema_variant": envelope.schema_variant,
        "rows_raw": len(raw_envelopes),
        "rows_inserted": inserted,
        "rows_updated": updated,
        "rows_normalized_clean": normalized_ok,
        "parse_errors": envelope.parse_errors,
        "source_sha256": source_sha256,
        "source_object_version": source_object_version,
    }
    operational_evidence.record_stage(
        run_id=run_id,
        run_kind="structured-intake",
        sequence=1,
        stage_id="source-received",
        label="Versioned structured source received",
        status="completed",
        source=logical_source,
        source_sha256=source_sha256,
        actor=PIPELINE_ACTOR,
        detail={
            "record_count": len(records),
            "schema": envelope.schema_variant,
            "source_object_version": source_object_version,
        },
    )
    operational_evidence.record_stage(
        run_id=run_id,
        run_kind="structured-intake",
        sequence=2,
        stage_id="raw-normalized",
        label="Raw rows normalized and retained",
        status="completed",
        source=logical_source,
        destination="database://grants_raw",
        source_sha256=source_sha256,
        output_sha256=operational_evidence.canonical_digest(raw_envelopes),
        actor=PIPELINE_ACTOR,
        detail={
            "accepted_records": normalized_ok,
            "record_count": len(records),
            "rejected_records": len(records) - normalized_ok,
            "schema": envelope.schema_variant,
            "field_mapping": {
                "grant identifier": "grants_raw.normalized.grant_no",
                "title": "grants_raw.normalized.title",
                "amount": "grants_raw.normalized.amount_usd",
                "organization": "grants_raw.normalized.org_unit",
            },
        },
    )
    print(json.dumps({"event_type": "ingest_fetch_complete", **result}, default=str))
    return result


# --------------------------------------------------------------------------- #
# Persist stage
# --------------------------------------------------------------------------- #
def _embed_abstract(text: Optional[str]) -> Optional[str]:
    """Titan v2 embedding as a pgvector literal, or ``None`` if unavailable.

    Embedding failures never fail an ingest: the row is curated with a NULL
    ``abstract_embedding`` and the RAG route can backfill. Silently curating
    nothing would be worse than curating without a vector.
    """
    if not text or not text.strip():
        return None
    try:
        from compass_common import llm

        vector = llm.embed(text)
        return "[" + ",".join(f"{float(v):.6f}" for v in vector) + "]"
    except Exception as exc:  # noqa: BLE001 - logged, never fatal
        print(json.dumps({"event_type": "embed_failed", "error": str(exc)}))
        return None


def _passing_rows(cur, batch_id: str) -> List[Dict[str, Any]]:
    cur.execute(
        "SELECT id, raw_jsonb->'normalized' "
        "FROM grants_raw "
        "WHERE batch_id = %s AND raw_jsonb->'quality'->>'status' = 'passed' "
        "ORDER BY id",
        (batch_id,),
    )
    out = []
    for raw_id, normalized in cur.fetchall():
        if isinstance(normalized, str):
            normalized = json.loads(normalized)
        if normalized:
            out.append({"raw_id": raw_id, "normalized": normalized})
    return out


def persist_stage(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Insert the gate-approved rows of a batch into ``grants_curated``."""
    batch_id = payload.get("batch_id")
    if not batch_id:
        raise ValueError("persist requires a batch_id")
    run_id = payload.get("run_id") or run_id_for(batch_id)
    source_file = payload.get("source_file") or ""

    conn = db.get_conn()
    with conn.cursor() as cur:            # autocommit read; no RLS on grants_raw
        rows = _passing_rows(cur, batch_id)

    # Embeddings are network calls to Bedrock - done before the write
    # transaction opens, so a slow model never holds a DB transaction open.
    embed_enabled = os.environ.get("EMBED_ON_INGEST", "true").lower() != "false"
    embed_cap = int(os.environ.get("EMBED_MAX_ROWS", "200"))
    vectors: Dict[int, Optional[str]] = {}
    embedded = 0
    if embed_enabled:
        for row in rows[:embed_cap]:
            vec = _embed_abstract((row["normalized"] or {}).get("abstract"))
            vectors[row["raw_id"]] = vec
            embedded += 1 if vec else 0

    inserted = 0
    duplicates = 0
    org_units: Dict[str, int] = {}
    curated_links: List[Tuple[int, int]] = []

    with db.set_org(conn, PIPELINE_ORG_UNIT) as c, c.cursor() as cur:
        for row in rows:
            n = row["normalized"]
            cur.execute(
                "INSERT INTO grants_curated "
                "(grant_no, title, abstract, abstract_embedding, program_area, "
                " fiscal_year, amount_usd, awardee, org_unit, classification_band, "
                " batch_id, created_at) "
                "VALUES (%s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, "
                "        COALESCE(%s::timestamptz, now())) "
                "ON CONFLICT (grant_no) DO NOTHING "
                "RETURNING id",
                (
                    n.get("grant_no"),
                    n.get("title"),
                    n.get("abstract"),
                    vectors.get(row["raw_id"]),
                    n.get("program_area"),
                    n.get("fiscal_year"),
                    n.get("amount_usd"),
                    n.get("awardee"),
                    n.get("org_unit"),
                    n.get("classification_band") or normalize.DEFAULT_CLASSIFICATION_BAND,
                    batch_id,
                    n.get("created_at"),
                ),
            )
            got = cur.fetchone()
            if got:
                inserted += 1
                curated_links.append((got[0], row["raw_id"]))
                org_units[n.get("org_unit") or "unknown"] = (
                    org_units.get(n.get("org_unit") or "unknown", 0) + 1
                )
            else:
                duplicates += 1

        # Row-level lineage: point each raw row at the curated row it became.
        for curated_id, raw_id in curated_links:
            cur.execute(
                "UPDATE grants_raw "
                "SET raw_jsonb = jsonb_set(raw_jsonb, '{meta,curated_id}', "
                "                          to_jsonb(%s::bigint), true) "
                "WHERE id = %s",
                (curated_id, raw_id),
            )
        cur.execute(
            "UPDATE grants_raw SET raw_jsonb = raw_jsonb || %s::jsonb WHERE batch_id = %s",
            (json.dumps({"batch_status": "curated"}), batch_id),
        )

        upsert_lineage_nodes(
            cur,
            run_id,
            [
                {
                    "node_id": "curated",
                    "kind": "table",
                    "label": "grants_curated",
                    "meta": {
                        "batch_id": batch_id,
                        "rows": inserted,
                        "duplicates_skipped": duplicates,
                        "org_units": org_units,
                        "embedded_rows": embedded,
                        "rls": "FORCE ROW LEVEL SECURITY on org_unit",
                    },
                },
                {
                    "node_id": "exec-dashboard",
                    "kind": "dashboard",
                    "label": "Executive dashboard",
                    "meta": {"batch_id": batch_id},
                },
            ],
        )
        upsert_lineage_edges(
            cur, run_id, [("quality-gate", "curated"), ("curated", "exec-dashboard")]
        )
        audit.write_audit(
            c,
            actor=PIPELINE_ACTOR,
            action="ingest_persist",
            resource=f"grants_curated:{batch_id}",
            detail={
                "run_id": run_id,
                "source_file": source_file,
                "rows_curated": inserted,
                "duplicates_skipped": duplicates,
                "embedded_rows": embedded,
            },
        )

    result = {
        "status": "ok",
        "action": "persist",
        "batch_id": batch_id,
        "run_id": run_id,
        "source_file": source_file,
        "rows_eligible": len(rows),
        "rows_curated": inserted,
        "duplicates_skipped": duplicates,
        "embedded_rows": embedded,
    }
    source_sha256 = str(payload.get("source_sha256") or "") or None
    operational_evidence.record_stage(
        run_id=run_id,
        run_kind="structured-intake",
        sequence=4,
        stage_id="curated-published",
        label="Quality-approved records published",
        status="completed",
        source="database://grants_raw",
        destination="database://grants_curated",
        source_sha256=source_sha256,
        output_sha256=operational_evidence.canonical_digest(
            {
                "batch_id": batch_id,
                "rows_curated": inserted,
                "duplicates_skipped": duplicates,
                "embedded_rows": embedded,
            }
        ),
        actor=PIPELINE_ACTOR,
        detail={
            "accepted_records": inserted,
            "record_count": len(rows),
            "unchanged_records": duplicates,
            "consumer": "Governed catalog and decision workspace",
        },
    )
    operational_evidence.record_stage(
        run_id=run_id,
        run_kind="structured-intake",
        sequence=5,
        stage_id="consumer-ready",
        label="Decision workspace projection ready",
        status="completed",
        source="database://grants_curated",
        destination="application://decision-workspace",
        source_sha256=source_sha256,
        actor=PIPELINE_ACTOR,
        detail={
            "accepted_records": inserted,
            "consumer": "Authorized portfolio users",
        },
    )
    operational_evidence.record_signal(
        category="structured-intake",
        severity="info",
        title="Structured intake completed",
        message=(
            f"The governed intake published {inserted} records and retained "
            f"{duplicates} duplicate records without creating copies."
        ),
        run_id=run_id,
        evidence_uri="database://grants_curated",
        detail={
            "accepted_records": inserted,
            "record_count": len(rows),
            "unchanged_records": duplicates,
        },
    )
    print(json.dumps({"event_type": "ingest_persist_complete", **result}, default=str))
    return result

"""Ingest pipeline stages: S3 → ``grants_raw`` (Fetch) → ``grants_curated`` (Persist).

These are the two intake-owned states of ``statemachines/intake.asl.yaml``. The
quality gate sits between them and is a separate Lambda.

Data flow
---------
``Fetch`` reads the dropped object, parses and normalizes it
(``normalize.py``), and upserts one ``grants_raw`` row per source record. It
returns only a small manifest — batch id, run id, counts — never the records
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
*any* unit — a batch legitimately contains Code-30, Code-32 and Code-34 awards.
It is still the real policy doing the work: the connection is
``compass_app`` (``compass_common.db`` sets the role), the table is
``FORCE ROW LEVEL SECURITY``, and the GUC is set with ``SET LOCAL`` inside the
transaction so it cannot leak to the next invocation. The corporate context is
also what makes ``INSERT … RETURNING id`` legal here — under RLS, ``RETURNING``
reads the new row back through the SELECT policy, which a unit context would
refuse for another unit's award.

Idempotency
-----------
The batch id is deterministic (from the drop envelope, else derived from the
object key), and every write is an upsert keyed on ``(batch_id, row_index)``
for raw rows, ``grant_no`` for curated rows, and the primary keys for lineage.
Re-dropping the same file therefore re-runs the same batch instead of doubling
it — which matters, because a demo drops the same file more than once.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from compass_common import audit, config, db

import normalize

PIPELINE_ORG_UNIT = config.CORPORATE_ORG_UNIT     # "ONR-Corporate"
PIPELINE_ACTOR = "compass-intake-pipeline"

# EventBridge fires on EVERY object created in the raw bucket, and other parts
# of the stack write there too (exports, RMF artifacts). Those prefixes are not
# ingest drops and are skipped without an error.
DEFAULT_SKIP_PREFIXES = "exports/,rmf/,quarantine/,tmp/,athena-results/"
INGESTIBLE_SUFFIXES = (".json", ".jsonl", ".ndjson")
DEFAULT_MAX_OBJECT_BYTES = 8 * 1024 * 1024

_S3 = None


def run_id_for(batch_id: str) -> str:
    """``run-<batch_id>`` — the convention the catalog and lineage routes join on."""
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
    """Write ``lineage_nodes`` for this run (upsert — a re-run refreshes meta)."""
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
            "bucket": bucket,
            "key": key,
        }

    text = read_object(bucket, key)
    source_file = f"s3://{bucket}/{key}"
    envelope = normalize.parse_drop(text, key=key, source_file=source_file)
    records = normalize.normalize_envelope(envelope)
    batch_id = envelope.batch_id
    run_id = run_id_for(batch_id)

    meta = {
        "batch_id": batch_id,
        "run_id": run_id,
        "source_file": source_file,
        "schema_variant": envelope.schema_variant,
        "fetched_at": normalize.utc_now_iso(),
    }
    raw_envelopes = [r.to_jsonb(meta=meta) for r in records]
    normalized_ok = sum(1 for r in records if not r.issues)

    conn = db.get_conn()
    with db.set_org(conn, PIPELINE_ORG_UNIT) as c, c.cursor() as cur:
        inserted, updated = _upsert_raw_rows(cur, batch_id, source_file, raw_envelopes)
        upsert_lineage_nodes(
            cur,
            run_id,
            [
                {
                    "node_id": "src-file",
                    "kind": "source",
                    "label": source_file,
                    "meta": {
                        "bucket": bucket,
                        "key": key,
                        "schema_variant": envelope.schema_variant,
                        "record_count": len(records),
                        "parse_errors": envelope.parse_errors,
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
                "source_file": source_file,
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
        "bucket": bucket,
        "key": key,
        "source_file": source_file,
        "schema_variant": envelope.schema_variant,
        "rows_raw": len(raw_envelopes),
        "rows_inserted": inserted,
        "rows_updated": updated,
        "rows_normalized_clean": normalized_ok,
        "parse_errors": envelope.parse_errors,
    }
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
    except Exception as exc:  # noqa: BLE001 — logged, never fatal
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

    # Embeddings are network calls to Bedrock — done before the write
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
    print(json.dumps({"event_type": "ingest_persist_complete", **result}, default=str))
    return result

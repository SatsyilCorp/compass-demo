"""Compass intake Lambda — the ingest path's front door (element 3).

One function, four callers:

* **Step Functions** (``statemachines/intake.asl.yaml``) invokes it twice per
  run: ``{"action":"fetch"}`` to land a dropped file in ``grants_raw`` and
  ``{"action":"persist"}`` to curate the rows the quality gate approved. Both
  live in ``pipeline.py``.
* **EventBridge** can also invoke it directly with an S3 ``Object Created``
  event (the same fetch stage), which is what makes the pipeline testable
  without the state machine.
* **EventBridge Scheduler** invokes it once a minute with
  ``{"action":"stream_tick"}`` to publish genuinely-recent pipeline activity
  onto the Kinesis ticker stream.
* **API Gateway** routes three contract endpoints here:
  ``POST /ingest/simulate``, ``GET /ingest/status``, ``GET /stream/recent``.

Read-path visibility
--------------------
``grants_curated`` is RLS-protected, so ``GET /ingest/status`` and
``GET /stream/recent`` run their curated queries under the caller's own
``org_unit`` and the database does the filtering. ``grants_raw``,
``grant_quality`` and Kinesis have no row-level security of their own, so this
module applies the same visibility rule in application code: a unit viewer sees
a batch only if RLS let it see at least one curated row from that batch, and
only corporate sees batches that never made it out of the landing zone. Where
that application-layer filter is doing the work, the code says so.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from compass_common import config, db, http

import normalize
import pipeline

# --------------------------------------------------------------------------- #
# Identity. Mirrors src/functions/authorizer/app.py, which is the source of
# truth for the group→role→org_unit map. The duplication exists because the API
# is fronted by the *native* HttpApi JWT authorizer (see template.yaml), which
# forwards raw Cognito claims without deriving anything — so each handler must
# do the derivation itself. Promoting this into compass_common would remove the
# copy; that file belongs to the shared layer, not this module.
# --------------------------------------------------------------------------- #
GROUP_ROLE = {"compass-poweruser": "poweruser", "compass-viewer": "viewer"}
ROLE_ORG_UNIT = {"poweruser": "ONR-Corporate", "viewer": "Code-30"}
ROLE_PRECEDENCE = ("poweruser", "viewer")


class Identity:
    __slots__ = ("role", "org_unit", "actor", "groups")

    def __init__(self, role: str, org_unit: str, actor: str, groups: List[str]):
        self.role, self.org_unit, self.actor, self.groups = role, org_unit, actor, groups

    @property
    def is_corporate(self) -> bool:
        return self.org_unit == config.CORPORATE_ORG_UNIT


def resolve_identity(event: Dict[str, Any]) -> Optional[Identity]:
    """Caller identity from the authorizer context, or ``None`` (→ 401)."""
    claims = http.get_claims(event)
    role = claims.role
    if role not in ROLE_ORG_UNIT:
        roles = {GROUP_ROLE[g] for g in claims.groups if g in GROUP_ROLE}
        role = next((r for r in ROLE_PRECEDENCE if r in roles), None)
    if role not in ROLE_ORG_UNIT:
        return None
    org_unit = claims.org_unit or ROLE_ORG_UNIT[role]
    actor = claims.username or claims.email or claims.sub or role
    return Identity(role, org_unit, actor, claims.groups)


# --------------------------------------------------------------------------- #
# GET /ingest/status
# --------------------------------------------------------------------------- #
def _quality_by_run(cur, run_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not run_ids:
        return {}
    cur.execute(
        "SELECT run_id, rule, passed_rows, failed_rows, score, details_jsonb "
        "FROM grant_quality WHERE run_id = ANY(%s) ORDER BY run_id, rule",
        (run_ids,),
    )
    out: Dict[str, List[Dict[str, Any]]] = {}
    for run_id, rule, passed, failed, score, details in cur.fetchall():
        out.setdefault(run_id, []).append(
            {
                "rule": rule,
                "passed_rows": int(passed),
                "failed_rows": int(failed),
                "score": float(score),
                "details": details or {},
            }
        )
    return out


def _gate_nodes(cur, run_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """The ``quality-gate`` lineage node per run — where the gate verdict lives."""
    if not run_ids:
        return {}
    cur.execute(
        "SELECT run_id, meta_jsonb FROM lineage_nodes "
        "WHERE run_id = ANY(%s) AND node_id = 'quality-gate'",
        (run_ids,),
    )
    return {run_id: (meta or {}) for run_id, meta in cur.fetchall()}


def ingest_status(identity: Identity) -> Dict[str, Any]:
    """``GET /ingest/status`` → recent batches with their quality-gate results."""
    conn = db.get_conn()
    with db.set_org(conn, identity.org_unit) as c, c.cursor() as cur:
        # RLS decides which batches this caller can see any curated row from.
        cur.execute(
            "SELECT batch_id, count(*), min(created_at) FROM grants_curated "
            "WHERE batch_id IS NOT NULL GROUP BY batch_id"
        )
        curated = {b: (int(n), first) for b, n, first in cur.fetchall()}

        # grants_raw has no RLS of its own, so the landing-zone count is grouped
        # by the org each record claims and re-aggregated below for this caller.
        # Reporting a whole-batch raw count to a unit viewer would both leak the
        # size of other units' holdings and make the UI look like rows had gone
        # missing between raw (40) and curated (8).
        cur.execute(
            "SELECT batch_id, raw_jsonb->'normalized'->>'org_unit', count(*), "
            "       min(ingested_at), min(source_file) "
            "FROM grants_raw GROUP BY 1, 2"
        )
        raw: Dict[str, Dict[str, Any]] = {}
        for batch_id, row_org, n, at, sf in cur.fetchall():
            entry = raw.setdefault(
                batch_id, {"rows_raw": 0, "ingested_at": at, "source_file": sf}
            )
            if identity.is_corporate or row_org == identity.org_unit:
                entry["rows_raw"] += int(n)
            if at and (entry["ingested_at"] is None or at < entry["ingested_at"]):
                entry["ingested_at"] = at

        # Application-layer visibility for the non-RLS tables (see module docs):
        # a quarantined batch has no curated rows, so only corporate sees it.
        visible = set(curated)
        if identity.is_corporate:
            visible |= set(raw)

        run_ids = [pipeline.run_id_for(b) for b in visible]
        quality = _quality_by_run(cur, run_ids)
        gates = _gate_nodes(cur, run_ids)

    batches: List[Dict[str, Any]] = []
    for batch_id in visible:
        run_id = pipeline.run_id_for(batch_id)
        rules = quality.get(run_id, [])
        gate = gates.get(run_id, {})
        rows_curated = curated.get(batch_id, (0, None))[0]
        raw_info = raw.get(batch_id)

        if gate.get("overall_score") is not None:
            overall = float(gate["overall_score"])
        elif rules:
            overall = round(sum(r["score"] for r in rules) / len(rules), 2)
        else:
            overall = 100.0 if rows_curated else 0.0

        decision = gate.get("decision")
        if decision == "pass":
            status = "passed"
        elif decision in ("fail", "quarantine"):
            status = "failed"
        elif rules:
            status = "passed" if rows_curated else "failed"
        elif raw_info:
            status = "running"
        else:
            status = "passed"

        ingested_at = (
            raw_info["ingested_at"] if raw_info else curated.get(batch_id, (0, None))[1]
        )
        batches.append(
            {
                "batch_id": batch_id,
                "run_id": run_id,
                "source_file": (raw_info or {}).get("source_file")
                or f"(loaded directly into grants_curated) {batch_id}",
                "ingested_at": ingested_at,
                "status": status,
                "rows_raw": (raw_info or {}).get("rows_raw", 0),
                "rows_curated": rows_curated,
                "quality": rules,
                "overall_score": overall,
                # Batches with no landing-zone rows were loaded straight into the
                # curated table by the seed loader; reported, never invented.
                "origin": "pipeline" if raw_info else "seed-load",
            }
        )

    batches.sort(key=lambda b: (b["ingested_at"] is not None, b["ingested_at"]), reverse=True)
    return {"batches": batches}


# --------------------------------------------------------------------------- #
# GET /stream/recent  (+ the scheduled Kinesis producer)
# --------------------------------------------------------------------------- #
_KINESIS = None


def _kinesis():
    global _KINESIS
    if _KINESIS is None:
        import boto3

        _KINESIS = boto3.client("kinesis", region_name=config.aws_region())
    return _KINESIS


def _visible_to(identity: Identity, org_unit: Optional[str]) -> bool:
    return identity.is_corporate or not org_unit or org_unit == identity.org_unit


def _activity_from_db(identity: Identity, limit: int) -> List[Dict[str, Any]]:
    """Recent pipeline activity read straight from the tables that recorded it.

    Every entry is a real row: a curated grant, a quality-gate result, an
    anomaly, an audit entry. Nothing is synthesized to fill the ticker.
    """
    records: List[Dict[str, Any]] = []
    conn = db.get_conn()
    with db.set_org(conn, identity.org_unit) as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, grant_no, org_unit, batch_id, created_at FROM grants_curated "
            "ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        visible_batches = set()
        for gid, grant_no, org_unit, batch_id, created_at in cur.fetchall():
            visible_batches.add(batch_id)
            records.append(
                {
                    "id": f"grant:{gid}",
                    "at": created_at,
                    "kind": "ingest",
                    "message": f"Curated {grant_no} into grants_curated"
                    + (f" (batch {batch_id})" if batch_id else ""),
                    "grant_no": grant_no,
                    "org_unit": org_unit,
                }
            )

        cur.execute("SELECT DISTINCT batch_id FROM grants_curated WHERE batch_id IS NOT NULL")
        visible_batches |= {row[0] for row in cur.fetchall()}
        run_ids = [pipeline.run_id_for(b) for b in visible_batches]

        quality_rows: List[Any] = []
        if identity.is_corporate:
            cur.execute(
                "SELECT run_id, rule, score, batch_id, created_at FROM grant_quality "
                "ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            quality_rows = cur.fetchall()
        elif run_ids:
            cur.execute(
                "SELECT run_id, rule, score, batch_id, created_at FROM grant_quality "
                "WHERE run_id = ANY(%s) ORDER BY created_at DESC LIMIT %s",
                (run_ids, limit),
            )
            quality_rows = cur.fetchall()
        for run_id, rule, score, batch_id, created_at in quality_rows:
            records.append(
                {
                    "id": f"quality:{run_id}:{rule}",
                    "at": created_at,
                    "kind": "quality",
                    "message": f"Quality rule {rule} scored {float(score):.1f} on batch {batch_id}",
                    "org_unit": None,
                }
            )

        # anomalies / audit_log carry no org column, so they are corporate-only
        # rather than shown to a unit viewer who could not see the underlying row.
        if identity.is_corporate:
            cur.execute(
                "SELECT id, kind, severity, reason, created_at FROM anomalies "
                "WHERE status = 'open' ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            for aid, kind, severity, reason, created_at in cur.fetchall():
                records.append(
                    {
                        "id": f"anomaly:{aid}",
                        "at": created_at,
                        "kind": "anomaly",
                        "message": f"[{severity}] {kind}: {reason}",
                        "org_unit": None,
                    }
                )
            cur.execute(
                "SELECT id, actor, action, resource, at FROM audit_log "
                "ORDER BY at DESC LIMIT %s",
                (limit,),
            )
            kind_for = {
                "export": "export",
                "export_blocked": "export",
                "approval": "approval",
                "analytics_run": "analytics",
                "quality_gate": "quality",
                "quarantine_batch": "anomaly",
                "ingest_fetch": "ingest",
                "ingest_persist": "ingest",
            }
            for aid, actor, action, resource, at in cur.fetchall():
                records.append(
                    {
                        "id": f"audit:{aid}",
                        "at": at,
                        "kind": kind_for.get(action, "ingest"),
                        "message": f"{actor} · {action}" + (f" · {resource}" if resource else ""),
                        "org_unit": None,
                    }
                )

    records.sort(key=lambda r: str(r["at"]), reverse=True)
    return records[:limit]


def _activity_from_kinesis(identity: Identity, limit: int) -> List[Dict[str, Any]]:
    """Read the ticker stream. Returns ``[]`` if the stream is empty or absent."""
    stream = os.environ.get("STREAM_NAME")
    if not stream:
        return []
    client = _kinesis()
    seen: Dict[str, Dict[str, Any]] = {}
    try:
        shards = client.list_shards(StreamName=stream).get("Shards", [])
        for shard in shards[: int(os.environ.get("STREAM_MAX_SHARDS", "4"))]:
            it = client.get_shard_iterator(
                StreamName=stream,
                ShardId=shard["ShardId"],
                ShardIteratorType="TRIM_HORIZON",
            )["ShardIterator"]
            resp = client.get_records(ShardIterator=it, Limit=max(limit * 4, 50))
            for rec in resp.get("Records", []):
                try:
                    item = json.loads(rec["Data"].decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                # Kinesis has no row-level security; the org filter is enforced
                # here so a unit viewer never sees another unit's activity.
                if not _visible_to(identity, item.get("org_unit")):
                    continue
                if item.get("id"):
                    seen[item["id"]] = item
    except Exception as exc:  # noqa: BLE001 — the DB feed is the fallback
        print(json.dumps({"event_type": "stream_read_failed", "error": str(exc)}))
        return []
    out = sorted(seen.values(), key=lambda r: str(r.get("at", "")), reverse=True)
    return out[:limit]


def stream_recent(identity: Identity, limit: int = 25) -> Dict[str, Any]:
    """``GET /stream/recent`` → the activity ticker.

    Reads the Kinesis ticker first; when the stream has nothing for this caller
    (an idle demo, or the schedule switched off via ``StreamTickerState``) it
    falls back to the same activity read directly from the database. The
    response labels which one answered in ``source`` — the ticker never shows
    invented traffic.
    """
    records = _activity_from_kinesis(identity, limit)
    source = "kinesis"
    if not records:
        records = _activity_from_db(identity, limit)
        source = "database"
    return {"records": records, "source": source}


def stream_tick() -> Dict[str, Any]:
    """Scheduled producer: publish genuinely-recent activity onto Kinesis.

    Only rows written inside the tick window are published, so an idle system
    publishes nothing rather than manufacturing traffic. Ids are stable, so the
    slight window overlap is de-duplicated by the reader.
    """
    stream = os.environ.get("STREAM_NAME")
    if not stream:
        return {"status": "skipped", "reason": "STREAM_NAME is not set"}
    window = int(os.environ.get("TICK_WINDOW_SECONDS", "120"))
    limit = int(os.environ.get("TICK_MAX_RECORDS", "50"))

    items: List[Dict[str, Any]] = []
    conn = db.get_conn()
    with db.set_org(conn, pipeline.PIPELINE_ORG_UNIT) as c, c.cursor() as cur:
        cur.execute(
            "SELECT id, grant_no, org_unit, batch_id, created_at FROM grants_curated "
            "WHERE created_at > now() - make_interval(secs => %s) "
            "ORDER BY created_at DESC LIMIT %s",
            (window, limit),
        )
        for gid, grant_no, org_unit, batch_id, created_at in cur.fetchall():
            items.append(
                {
                    "id": f"grant:{gid}",
                    "at": created_at.isoformat(),
                    "kind": "ingest",
                    "message": f"Curated {grant_no} into grants_curated (batch {batch_id})",
                    "grant_no": grant_no,
                    "org_unit": org_unit,
                }
            )
        cur.execute(
            "SELECT run_id, rule, score, batch_id, created_at FROM grant_quality "
            "WHERE created_at > now() - make_interval(secs => %s) "
            "ORDER BY created_at DESC LIMIT %s",
            (window, limit),
        )
        for run_id, rule, score, batch_id, created_at in cur.fetchall():
            items.append(
                {
                    "id": f"quality:{run_id}:{rule}",
                    "at": created_at.isoformat(),
                    "kind": "quality",
                    "message": f"Quality rule {rule} scored {float(score):.1f} on batch {batch_id}",
                    "org_unit": None,
                }
            )
        cur.execute(
            "SELECT id, kind, severity, reason, created_at FROM anomalies "
            "WHERE created_at > now() - make_interval(secs => %s) "
            "ORDER BY created_at DESC LIMIT %s",
            (window, limit),
        )
        for aid, kind, severity, reason, created_at in cur.fetchall():
            items.append(
                {
                    "id": f"anomaly:{aid}",
                    "at": created_at.isoformat(),
                    "kind": "anomaly",
                    "message": f"[{severity}] {kind}: {reason}",
                    "org_unit": None,
                }
            )

    if not items:
        return {"status": "ok", "published": 0, "window_seconds": window}

    entries = [
        {
            "Data": json.dumps(item, default=str).encode("utf-8"),
            "PartitionKey": item.get("org_unit") or "compass",
        }
        for item in items[:limit]
    ]
    resp = _kinesis().put_records(StreamName=stream, Records=entries)
    failed = int(resp.get("FailedRecordCount", 0))
    out = {
        "status": "ok",
        "published": len(entries) - failed,
        "failed": failed,
        "window_seconds": window,
    }
    print(json.dumps({"event_type": "stream_tick_complete", **out}))
    return out


# --------------------------------------------------------------------------- #
# POST /ingest/simulate
# --------------------------------------------------------------------------- #
DEFAULT_SIMULATE_PREFIX = "drops/"


def _strip_s3_uri(value: str, bucket: str) -> str:
    if value.startswith("s3://"):
        rest = value[5:]
        head, _, tail = rest.partition("/")
        return tail if head == bucket else rest
    return value.lstrip("/")


def _start_execution(bucket: str, key: str, size: Optional[int]) -> Optional[str]:
    """Start the intake state machine for an object already in the bucket."""
    arn = os.environ.get("INTAKE_STATE_MACHINE_ARN")
    if not arn:
        return None
    import boto3

    sfn = boto3.client("stepfunctions", region_name=config.aws_region())
    payload = {
        "source": "compass.ingest.simulate",
        "detail-type": "Object Created",
        "detail": {"bucket": {"name": bucket}, "object": {"key": key, "size": size}},
    }
    return sfn.start_execution(stateMachineArn=arn, input=json.dumps(payload))[
        "executionArn"
    ]


def ingest_simulate(identity: Identity, body: Dict[str, Any]) -> Dict[str, Any]:
    """``POST /ingest/simulate`` — fire the real pipeline, three ways.

    * ``{"records": [...]}`` writes the batch to ``s3://<raw>/incoming/<batch>.json``
      and lets the bucket's EventBridge notification start the pipeline — the
      full production path, no shortcuts.
    * ``{"source_file": "drops/drop_good.json"}`` (a key or an ``s3://`` URI for
      an object already in the raw bucket) starts the state machine on it.
    * An empty body picks the most recently modified object under ``drops/``.

    Requires ``poweruser`` — triggering ingest is a write action.
    """
    bucket = os.environ.get("RAW_BUCKET")
    if not bucket:
        return http.server_error("RAW_BUCKET is not configured")

    records = body.get("records")
    now = normalize.utc_now_iso()

    if isinstance(records, list) and records:
        stamp = now[:19].replace("-", "").replace(":", "")
        batch_id = str(body.get("batch_id") or f"batch-sim-{stamp}")
        key = f"incoming/{batch_id}.json"
        envelope = {
            "source_file": body.get("source_file") or key,
            "batch_id": batch_id,
            "schema_variant": body.get("schema_variant")
            or normalize.infer_schema_variant(records),
            "dropped_at": now,
            "record_count": len(records),
            "records": records,
        }
        pipeline._s3().put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(envelope, default=str).encode("utf-8"),
            ContentType="application/json",
        )
        return http.json_response(
            202,
            {
                "batch_id": batch_id,
                "run_id": pipeline.run_id_for(batch_id),
                "source_file": f"s3://{bucket}/{key}",
                "status": "queued",
                "triggered_at": now,
                "trigger": "s3-object-created",
            },
        )

    source = body.get("source_file") or body.get("source_key")
    if source:
        key = _strip_s3_uri(str(source), bucket)
    else:
        prefix = body.get("prefix") or DEFAULT_SIMULATE_PREFIX
        listing = pipeline._s3().list_objects_v2(Bucket=bucket, Prefix=prefix)
        candidates = [
            o
            for o in listing.get("Contents", [])
            if pipeline.is_ingestible(o["Key"], o.get("Size"))[0]
        ]
        if not candidates:
            return http.bad_request(
                f"no ingestible object under s3://{bucket}/{prefix}. Upload a drop file "
                "there (seed/drops/*.json), pass {\"source_file\": \"<key>\"}, or post "
                "{\"records\": [...]} to synthesize a batch.",
                bucket=bucket,
                prefix=prefix,
            )
        key = max(candidates, key=lambda o: o["LastModified"])["Key"]

    try:
        head = pipeline._s3().head_object(Bucket=bucket, Key=key)
    except Exception:  # noqa: BLE001 — a bad key is a client error, not a 500
        return http.not_found(f"no such object: s3://{bucket}/{key}")
    size = head.get("ContentLength")

    ok, reason = pipeline.is_ingestible(key, size)
    if not ok:
        return http.bad_request(f"s3://{bucket}/{key} is not ingestible: {reason}")

    # Read the envelope so the reported batch_id is the one the run will really
    # use, rather than a guess from the filename.
    text = pipeline.read_object(bucket, key)
    envelope = normalize.parse_drop(text, key=key, source_file=f"s3://{bucket}/{key}")

    execution_arn = _start_execution(bucket, key, size)
    return http.json_response(
        202,
        {
            "batch_id": envelope.batch_id,
            "run_id": pipeline.run_id_for(envelope.batch_id),
            "source_file": f"s3://{bucket}/{key}",
            "status": "running" if execution_arn else "queued",
            "triggered_at": now,
            "trigger": "state-machine" if execution_arn else "none",
            "execution_arn": execution_arn,
            "record_count": len(envelope.records),
            "schema_variant": envelope.schema_variant,
        },
    )


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #
def _route_key(event: Dict[str, Any]) -> str:
    rk = event.get("routeKey")
    if isinstance(rk, str) and rk:
        return rk
    method = http.get_method(event) or ""
    path = http.get_path(event) or ""
    return f"{method} {path}".strip()


def _handle_api(event: Dict[str, Any]) -> Dict[str, Any]:
    identity = resolve_identity(event)
    if identity is None:
        return http.unauthorized(
            "no Compass role on the request context (expected group compass-poweruser "
            "or compass-viewer)"
        )
    route = _route_key(event)
    method = http.get_method(event) or ""

    if method == "GET" and route.endswith("/ingest/status"):
        return http.ok(ingest_status(identity))

    if method == "GET" and route.endswith("/stream/recent"):
        params = http.query_params(event)
        try:
            limit = max(1, min(200, int(params.get("limit", "25"))))
        except (TypeError, ValueError):
            limit = 25
        return http.ok(stream_recent(identity, limit))

    if method == "POST" and route.endswith("/ingest/simulate"):
        if identity.role != "poweruser":
            return http.forbidden("simulating an ingest requires the poweruser role")
        try:
            body = http.parse_body(event)
        except ValueError as exc:
            return http.bad_request(f"invalid JSON body: {exc}")
        return ingest_simulate(identity, body)

    return http.not_found(f"no intake route for {route!r}")


def handler(event, context=None):
    """Dispatch on event shape: state machine action, schedule, S3 event, or API."""
    event = event or {}
    action = event.get("action")

    if action == "fetch":
        return pipeline.fetch_stage(event.get("detail") or {})
    if action == "persist":
        return pipeline.persist_stage(event)
    if action == "stream_tick":
        return stream_tick()

    if (event.get("requestContext") or {}).get("http"):
        return _handle_api(event)

    detail = event.get("detail")
    if isinstance(detail, dict) and detail.get("bucket"):
        return pipeline.fetch_stage(detail)

    raise ValueError(
        "unrecognized intake event; expected {'action': 'fetch'|'persist'|'stream_tick'}, "
        "an S3 Object Created event, or an HTTP API request"
    )

"""Compass intake Lambda - the ingest path's front door (element 3).

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
* **API Gateway** routes ingest, ticker, and operator-controlled continuous
  synthetic stream controls here.

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

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from compass_common import audit, config, db, disclosure, http, operational_evidence

import normalize
import pipeline

# --------------------------------------------------------------------------- #
# Identity. Cognito group normalization and role mapping live in the shared
# HTTP module so every native JWT route applies the same deny-by-default rules.
# --------------------------------------------------------------------------- #
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
    role, org_unit = http.resolve_identity(claims)
    if role is None or org_unit is None:
        return None
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
    """The ``quality-gate`` lineage node per run - where the gate verdict lives."""
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
                "source_file": (
                    disclosure.logical_source_locator(raw_info.get("source_file"))
                    if raw_info
                    else disclosure.logical_curated_locator(batch_id)
                ),
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
_OPERATIONS_TABLE = None
_STEP_FUNCTIONS = None

DEMO_STREAM_PK = "DEMO_STREAM"
DEMO_STREAM_SK = "CURRENT"
DEMO_STREAM_DEFAULT_CADENCE_SECONDS = 2
DEMO_STREAM_DEFAULT_TOTAL_EVENTS = 15
DEMO_STREAM_MAX_TOTAL_EVENTS = 60
DEMO_STREAM_DEFAULT_MODE = "continuous"
DEMO_STREAM_EXECUTION_CHUNK_EVENTS = 250
DEMO_STREAM_RAW_RETENTION_DAYS = 7
DEMO_STREAM_PROGRAM_AREAS = (
    "Autonomy",
    "Biotech",
    "Cyber",
    "Ocean Engineering",
    "Quantum",
    "Undersea Systems",
)
DEMO_STREAM_ORG_UNITS = ("Code-30", "Code-31", "Code-32", "Code-34", "Code-35")


def _kinesis():
    global _KINESIS
    if _KINESIS is None:
        import boto3

        _KINESIS = boto3.client("kinesis", region_name=config.aws_region())
    return _KINESIS


def _operations_table():
    global _OPERATIONS_TABLE
    if _OPERATIONS_TABLE is None:
        import boto3

        table_name = os.environ.get("OPERATIONS_TABLE", "").strip()
        if not table_name:
            raise RuntimeError("OPERATIONS_TABLE is required")
        _OPERATIONS_TABLE = boto3.resource("dynamodb").Table(table_name)
    return _OPERATIONS_TABLE


def _step_functions():
    global _STEP_FUNCTIONS
    if _STEP_FUNCTIONS is None:
        import boto3

        _STEP_FUNCTIONS = boto3.client(
            "stepfunctions", region_name=config.aws_region()
        )
    return _STEP_FUNCTIONS


def _json_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {str(key): _json_scalar(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_scalar(item) for item in value]
    return value


def _demo_stream_item() -> Optional[Dict[str, Any]]:
    response = _operations_table().get_item(
        Key={"pk": DEMO_STREAM_PK, "sk": DEMO_STREAM_SK},
        ConsistentRead=True,
    )
    item = response.get("Item")
    return _json_scalar(item) if isinstance(item, dict) else None


def _put_demo_stream_item(item: Dict[str, Any]) -> None:
    _operations_table().put_item(Item=item)


def _conditional_error(exc: Exception) -> bool:
    code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
    return code == "ConditionalCheckFailedException" or "ConditionalCheckFailed" in type(exc).__name__


def _s3_precondition_error(exc: Exception) -> bool:
    code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
    return code in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"}


def _create_demo_stream_item(item: Dict[str, Any]) -> bool:
    try:
        _operations_table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(pk) OR #status <> :running",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":running": "running"},
        )
        return True
    except Exception as exc:  # noqa: BLE001 - botocore stays runtime-only
        if _conditional_error(exc):
            return False
        raise


def _bind_demo_stream_execution(
    session_id: str, execution_arn: str, chunk_number: int
) -> bool:
    try:
        _operations_table().update_item(
            Key={"pk": DEMO_STREAM_PK, "sk": DEMO_STREAM_SK},
            UpdateExpression=(
                "SET execution_arn = :execution_arn, "
                "execution_chunk_number = :chunk_number"
            ),
            ConditionExpression="session_id = :session_id AND #status = :running",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":execution_arn": execution_arn,
                ":chunk_number": chunk_number,
                ":session_id": session_id,
                ":running": "running",
            },
        )
        return True
    except Exception as exc:  # noqa: BLE001 - botocore stays runtime-only
        if _conditional_error(exc):
            return False
        raise


def _advance_demo_stream_item(
    *,
    session_id: str,
    sequence: int,
    batch_id: str,
    latest_event: Dict[str, Any],
    occurred_at: str,
    completed: bool,
) -> bool:
    values: Dict[str, Any] = {
        ":session_id": session_id,
        ":running": "running",
        ":status": "completed" if completed else "running",
        ":sequence": sequence,
        ":batch_id": batch_id,
        ":latest_event": latest_event,
        ":updated_at": occurred_at,
        ":completed_at": occurred_at if completed else None,
    }
    try:
        _operations_table().update_item(
            Key={"pk": DEMO_STREAM_PK, "sk": DEMO_STREAM_SK},
            UpdateExpression=(
                "SET emitted_events = :sequence, latest_batch_id = :batch_id, "
                "latest_event = :latest_event, updated_at = :updated_at, "
                "completed_at = :completed_at, #status = :status"
            ),
            ConditionExpression=(
                "session_id = :session_id AND #status = :running AND "
                "(attribute_not_exists(emitted_events) OR emitted_events < :sequence)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=values,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - botocore stays runtime-only
        if _conditional_error(exc):
            return False
        raise


def _mark_demo_stream_terminal(session_id: str, status: str, now: str) -> bool:
    try:
        _operations_table().update_item(
            Key={"pk": DEMO_STREAM_PK, "sk": DEMO_STREAM_SK},
            UpdateExpression=(
                "SET #status = :status, updated_at = :now, completed_at = :now"
            ),
            ConditionExpression="session_id = :session_id AND #status = :running",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":now": now,
                ":session_id": session_id,
                ":running": "running",
            },
        )
        return True
    except Exception as exc:  # noqa: BLE001 - botocore stays runtime-only
        if _conditional_error(exc):
            return False
        raise


def _public_demo_stream(item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not item:
        session = {
            "session_id": None,
            "status": "idle",
            "stream_mode": DEMO_STREAM_DEFAULT_MODE,
            "cadence_seconds": DEMO_STREAM_DEFAULT_CADENCE_SECONDS,
            "total_events": None,
            "emitted_events": 0,
            "started_at": None,
            "updated_at": None,
            "completed_at": None,
            "execution_chunk_number": 0,
        }
        latest_event = None
    else:
        stream_mode = str(item.get("stream_mode") or "").strip().lower()
        if stream_mode not in {"continuous", "bounded"}:
            stream_mode = "bounded" if item.get("total_events") is not None else "continuous"
        session = {
            key: item.get(key)
            for key in (
                "session_id",
                "status",
                "cadence_seconds",
                "total_events",
                "emitted_events",
                "started_at",
                "updated_at",
                "completed_at",
                "execution_chunk_number",
            )
        }
        session["stream_mode"] = stream_mode
        if stream_mode == "continuous":
            session["total_events"] = None
        latest_event = item.get("latest_event")
    cadence = int(session.get("cadence_seconds") or DEMO_STREAM_DEFAULT_CADENCE_SECONDS)
    return {
        "contract": "compass.demo-stream.v1",
        "mode": "live",
        "generated_at": normalize.utc_now_iso(),
        "stream_kind": "continuous-synthetic",
        "session": session,
        "latest_event": latest_event,
        "safeguards": {
            "operator_stop_required": True,
            "workflow_chunk_events": DEMO_STREAM_EXECUTION_CHUNK_EVENTS,
            "raw_retention_days": DEMO_STREAM_RAW_RETENTION_DAYS,
            "estimated_events_per_hour": 3600 // cadence,
        },
        "disclosure": (
            "This operator-controlled synthetic stream remains active until Stop. "
            "Each pulse uses the deployed ingestion path. Official USAspending "
            "acquisition keeps its independent source cadence."
        ),
    }


def demo_stream_status() -> Dict[str, Any]:
    return _public_demo_stream(_demo_stream_item())


def _valid_demo_stream_settings(
    body: Dict[str, Any],
) -> tuple[int, str, Optional[int]]:
    try:
        cadence = int(body.get("cadence_seconds", DEMO_STREAM_DEFAULT_CADENCE_SECONDS))
    except (TypeError, ValueError) as exc:
        raise ValueError("cadence_seconds must be an integer") from exc
    if cadence not in {1, 2}:
        raise ValueError("cadence_seconds must be 1 or 2")

    raw_mode = str(body.get("stream_mode") or "").strip().lower()
    if not raw_mode:
        raw_mode = "bounded" if body.get("total_events") is not None else DEMO_STREAM_DEFAULT_MODE
    if raw_mode not in {"continuous", "bounded"}:
        raise ValueError("stream_mode must be continuous or bounded")
    if raw_mode == "continuous":
        return cadence, raw_mode, None

    try:
        total = int(body.get("total_events", DEMO_STREAM_DEFAULT_TOTAL_EVENTS))
    except (TypeError, ValueError) as exc:
        raise ValueError("total_events must be an integer") from exc
    if total < 1 or total > DEMO_STREAM_MAX_TOTAL_EVENTS:
        raise ValueError(
            f"total_events must be between 1 and {DEMO_STREAM_MAX_TOTAL_EVENTS}"
        )
    return cadence, raw_mode, total


def _execution_arn_for_name(state_machine_arn: str, execution_name: str) -> str:
    prefix, state_machine_name = state_machine_arn.rsplit(":stateMachine:", 1)
    return f"{prefix}:execution:{state_machine_name}:{execution_name}"


def _demo_stream_workflow_arn() -> str:
    workflow_arn = os.environ.get("DEMO_STREAM_STATE_MACHINE_ARN", "").strip()
    if not workflow_arn:
        raise RuntimeError("DEMO_STREAM_STATE_MACHINE_ARN is required")
    return workflow_arn


def _demo_stream_execution_name(session_id: str, chunk_number: int) -> str:
    return f"{session_id}-{chunk_number:06d}"


def _start_demo_stream_execution(
    *,
    session_id: str,
    cadence: int,
    stream_mode: str,
    total_events: Optional[int],
    sequence: int,
    chunk_number: int,
) -> str:
    workflow_arn = _demo_stream_workflow_arn()
    execution_name = _demo_stream_execution_name(session_id, chunk_number)
    try:
        response = _step_functions().start_execution(
            stateMachineArn=workflow_arn,
            name=execution_name,
            input=json.dumps(
                {
                    "action": "demo_stream_tick",
                    "session_id": session_id,
                    "stream_mode": stream_mode,
                    "cadence_seconds": cadence,
                    "total_events": total_events,
                    "sequence": sequence,
                    "chunk_number": chunk_number,
                    "chunk_emitted": 0,
                }
            ),
        )
        execution_arn = str(response.get("executionArn") or "")
        if not execution_arn:
            raise RuntimeError("Step Functions returned no demo stream execution ARN")
        return execution_arn
    except Exception as exc:  # noqa: BLE001 - botocore stays runtime-only
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code == "ExecutionAlreadyExists":
            return _execution_arn_for_name(workflow_arn, execution_name)
        raise


def start_demo_stream(identity: Identity, body: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
    cadence, stream_mode, total = _valid_demo_stream_settings(body)
    current = _demo_stream_item()
    if current and current.get("status") == "running":
        return 200, _public_demo_stream(current)

    now = normalize.utc_now_iso()
    session_id = f"pulse-{uuid.uuid4().hex[:12]}"
    item = {
        "pk": DEMO_STREAM_PK,
        "sk": DEMO_STREAM_SK,
        "record_type": "control",
        "session_id": session_id,
        "status": "running",
        "stream_mode": stream_mode,
        "cadence_seconds": cadence,
        "total_events": total,
        "emitted_events": 0,
        "execution_chunk_number": 1,
        "started_at": now,
        "updated_at": now,
        "completed_at": None,
        "started_by": identity.actor[:160],
    }
    if not _create_demo_stream_item(item):
        return 200, demo_stream_status()
    try:
        execution_arn = _start_demo_stream_execution(
            session_id=session_id,
            cadence=cadence,
            stream_mode=stream_mode,
            total_events=total,
            sequence=1,
            chunk_number=1,
        )
    except Exception:
        _mark_demo_stream_terminal(session_id, "failed", normalize.utc_now_iso())
        raise
    if execution_arn:
        _bind_demo_stream_execution(session_id, execution_arn, 1)
    operational_evidence.record_signal(
        category="demo-stream",
        severity="info",
        title="Continuous synthetic ingestion started",
        message=(
            f"The operator started a synthetic ingestion pulse every {cadence} seconds. "
            "The session remains active until an operator stops it."
        ),
        run_id=session_id,
        evidence_uri=f"operations://demo-stream/{session_id}",
        event_id=f"sig-demo-stream-started-{session_id}",
        publish=False,
    )
    return 202, demo_stream_status()


def stop_demo_stream(session_id: str) -> Dict[str, Any]:
    current = _demo_stream_item()
    if not current or current.get("session_id") != session_id:
        raise LookupError("demo stream session not found")
    if current.get("status") != "running":
        return _public_demo_stream(current)
    now = normalize.utc_now_iso()
    if not _mark_demo_stream_terminal(session_id, "stopped", now):
        return demo_stream_status()
    execution_arn = str(current.get("execution_arn") or "")
    if execution_arn:
        try:
            _step_functions().stop_execution(
                executionArn=execution_arn,
                cause="Stopped from the Compass demo stream control",
            )
        except Exception as exc:  # noqa: BLE001 - stopped state remains authoritative
            print(
                json.dumps(
                    {
                        "event_type": "demo_stream_stop_execution_deferred",
                        "session_id": session_id,
                        "error_type": type(exc).__name__,
                    }
                )
            )
    operational_evidence.record_signal(
        category="demo-stream",
        severity="info",
        title="Continuous synthetic ingestion stopped",
        message=(
            f"The operator stopped the continuous session after "
            f"{int(current.get('emitted_events') or 0)} accepted pulses."
        ),
        run_id=session_id,
        evidence_uri=f"operations://demo-stream/{session_id}",
        event_id=f"sig-demo-stream-stopped-{session_id}",
        publish=False,
    )
    return demo_stream_status()


def _demo_stream_record(session_id: str, sequence: int, occurred_at: str) -> Dict[str, Any]:
    suffix = session_id.removeprefix("pulse-")[:8].upper()
    area = DEMO_STREAM_PROGRAM_AREAS[(sequence - 1) % len(DEMO_STREAM_PROGRAM_AREAS)]
    org_unit = DEMO_STREAM_ORG_UNITS[(sequence - 1) % len(DEMO_STREAM_ORG_UNITS)]
    return {
        "grant_no": f"ONR-LIVE-{suffix}-{sequence:08d}",
        "title": f"Live {area} evidence update {sequence}",
        "abstract": (
            f"Synthetic continuous demonstration record {sequence} for {area}. "
            "It exercises the same governed ingestion, quality, lineage, and decision path."
        ),
        "program_area": area,
        "fiscal_year": 2026,
        "amount_usd": 250000 + ((((sequence - 1) % 20) + 1) * 37500),
        "awardee": f"Synthetic Mission Partner {((sequence - 1) % 7) + 1}",
        "org_unit": org_unit,
        "classification_band": "Public-Mock",
        "created_at": occurred_at,
    }


def demo_stream_tick(event: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(event.get("session_id") or "")
    sequence = max(1, int(event.get("sequence") or 1))
    cadence = int(event.get("cadence_seconds") or DEMO_STREAM_DEFAULT_CADENCE_SECONDS)
    chunk_number = max(1, int(event.get("chunk_number") or 1))
    chunk_emitted = max(0, int(event.get("chunk_emitted") or 0))
    current = _demo_stream_item()
    current_mode = str((current or {}).get("stream_mode") or "").strip().lower()
    if current_mode not in {"continuous", "bounded"}:
        current_mode = "bounded" if (current or {}).get("total_events") is not None else "continuous"
    total_value = (current or {}).get("total_events")
    total = int(total_value) if current_mode == "bounded" and total_value is not None else None
    if (
        not current
        or current.get("session_id") != session_id
        or current.get("status") != "running"
        or int(current.get("execution_chunk_number") or 1) > chunk_number
    ):
        return {
            "session_id": session_id,
            "cadence_seconds": cadence,
            "total_events": total,
            "sequence": sequence,
            "continue": False,
            "status": (current or {}).get("status", "stopped"),
        }

    emitted_events = int(current.get("emitted_events") or 0)
    if emitted_events >= sequence:
        is_final_retry = current_mode == "bounded" and total is not None and emitted_events >= total
        return {
            "action": "demo_stream_tick",
            "session_id": session_id,
            "stream_mode": current_mode,
            "cadence_seconds": cadence,
            "total_events": total,
            "sequence": emitted_events + 1,
            "chunk_number": chunk_number,
            "chunk_emitted": chunk_emitted + 1,
            "emitted_events": emitted_events,
            "continue": not is_final_retry,
            "status": "completed" if is_final_retry else "running",
            "latest_event": current.get("latest_event"),
        }

    occurred_at = normalize.utc_now_iso()
    batch_id = f"live-{session_id.removeprefix('pulse-')}-{sequence:08d}"
    run_id = pipeline.run_id_for(batch_id)
    key = f"drops/live-stream/{session_id}/{sequence:08d}.json"
    record = _demo_stream_record(session_id, sequence, occurred_at)
    envelope = {
        "source_file": f"landing://drops/live-stream/{sequence:08d}.json",
        "batch_id": batch_id,
        "schema_variant": "canonical",
        "synthetic_only": True,
        "demo_stream_session": session_id,
        "dropped_at": occurred_at,
        "record_count": 1,
        "records": [record],
    }
    payload = json.dumps(envelope, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    bucket = os.environ.get("RAW_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("RAW_BUCKET is required")
    object_created = True
    try:
        pipeline._s3().put_object(
            Bucket=bucket,
            Key=key,
            Body=payload,
            ContentType="application/json",
            Metadata={
                "synthetic-only": "true",
                "demo-stream-session": session_id,
                "source-sha256": hashlib.sha256(payload).hexdigest(),
            },
            IfNoneMatch="*",
        )
    except Exception as exc:  # noqa: BLE001 - botocore stays runtime-only
        if not _s3_precondition_error(exc):
            raise
        object_created = False

    message = f"Synthetic live pulse {sequence} landed for {record['program_area']}"
    stream_name = os.environ.get("STREAM_NAME", "").strip()
    if stream_name and object_created:
        _kinesis().put_record(
            StreamName=stream_name,
            PartitionKey=str(record["org_unit"]),
            Data=json.dumps(
                {
                    "id": f"demo-stream:{session_id}:{sequence:08d}",
                    "at": occurred_at,
                    "kind": "ingest",
                    "message": message,
                    "grant_no": record["grant_no"],
                    "org_unit": record["org_unit"],
                }
            ).encode("utf-8"),
        )

    latest_event = {
        "sequence": sequence,
        "run_id": run_id,
        "event_id": f"demo-stream:{session_id}:{sequence:08d}",
        "occurred_at": occurred_at,
        "message": message,
    }
    is_final = current_mode == "bounded" and total is not None and sequence >= total
    next_chunk_emitted = chunk_emitted + 1
    should_rotate = (
        current_mode == "continuous"
        and next_chunk_emitted >= DEMO_STREAM_EXECUTION_CHUNK_EVENTS
    )
    advanced = _advance_demo_stream_item(
        session_id=session_id,
        sequence=sequence,
        batch_id=batch_id,
        latest_event=latest_event,
        occurred_at=occurred_at,
        completed=is_final,
    )

    rotated = False
    if advanced and should_rotate:
        next_chunk = chunk_number + 1
        workflow_arn = _demo_stream_workflow_arn()
        expected_execution_arn = _execution_arn_for_name(
            workflow_arn,
            _demo_stream_execution_name(session_id, next_chunk),
        )
        if _bind_demo_stream_execution(
            session_id, expected_execution_arn, next_chunk
        ):
            execution_arn = _start_demo_stream_execution(
                session_id=session_id,
                cadence=cadence,
                stream_mode=current_mode,
                total_events=None,
                sequence=sequence + 1,
                chunk_number=next_chunk,
            )
            if execution_arn == expected_execution_arn:
                rotated = True
            else:
                rotated = _bind_demo_stream_execution(
                    session_id, execution_arn, next_chunk
                )

    print(
        json.dumps(
            {
                "event_type": "demo_stream_tick_complete",
                "session_id": session_id,
                "sequence": sequence,
                "total_events": total,
                "stream_mode": current_mode,
                "execution_chunk_number": chunk_number,
                "rotated": rotated,
                "object_created": object_created,
                "batch_id": batch_id,
            }
        )
    )
    return {
        "action": "demo_stream_tick",
        "session_id": session_id,
        "stream_mode": current_mode,
        "cadence_seconds": cadence,
        "total_events": total,
        "sequence": sequence + 1,
        "chunk_number": chunk_number,
        "chunk_emitted": next_chunk_emitted,
        "emitted_events": sequence,
        "continue": advanced and not is_final and not should_rotate,
        "status": "completed" if is_final else "running",
        "rotated": rotated,
        "latest_event": latest_event,
    }


def fail_demo_stream(event: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(event.get("session_id") or "")
    current = _demo_stream_item()
    if current and current.get("session_id") == session_id:
        _mark_demo_stream_terminal(session_id, "failed", normalize.utc_now_iso())
        operational_evidence.record_signal(
            category="demo-stream",
            severity="high",
            title="Continuous synthetic stream failed",
            message="The continuous synthetic stream stopped after an AWS workflow failure.",
            run_id=session_id,
            evidence_uri=f"operations://demo-stream/{session_id}",
            event_id=f"sig-demo-stream-failed-{session_id}",
        )
    return {
        "session_id": session_id,
        "status": "failed",
        "continue": False,
    }


def _visible_to(identity: Identity, org_unit: Optional[str]) -> bool:
    return identity.is_corporate or bool(org_unit and org_unit == identity.org_unit)


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
        read_window = max(60, int(os.environ.get("STREAM_READ_WINDOW_SECONDS", "900")))
        start_at = datetime.now(timezone.utc) - timedelta(seconds=read_window)
        page_limit = min(10_000, max(limit * 20, 500))
        max_pages = max(1, min(8, int(os.environ.get("STREAM_READ_MAX_PAGES", "4"))))
        for shard in shards[: int(os.environ.get("STREAM_MAX_SHARDS", "4"))]:
            it = client.get_shard_iterator(
                StreamName=stream,
                ShardId=shard["ShardId"],
                ShardIteratorType="AT_TIMESTAMP",
                Timestamp=start_at,
            )["ShardIterator"]
            for _page in range(max_pages):
                if not it:
                    break
                resp = client.get_records(ShardIterator=it, Limit=page_limit)
                for rec in resp.get("Records", []):
                    try:
                        item = json.loads(rec["Data"].decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if not isinstance(item, dict):
                        continue
                    kind = str(item.get("kind") or "")
                    if kind not in {
                        "ingest",
                        "quality",
                        "anomaly",
                        "export",
                        "approval",
                        "analytics",
                        "public-feed",
                    }:
                        continue
                    item_id = str(item.get("id") or "")[:240]
                    message = " ".join(str(item.get("message") or "").split())[:500]
                    event_at = str(item.get("at") or "")[:40]
                    if not item_id or not message or not event_at:
                        continue
                    item = {
                        "id": item_id,
                        "at": event_at,
                        "kind": kind,
                        "message": message,
                        "grant_no": str(item.get("grant_no") or "")[:160] or None,
                        "org_unit": str(item.get("org_unit") or "")[:80] or None,
                    }
                    # Kinesis has no row-level security. A missing scope is
                    # corporate-only, never a wildcard for a unit viewer.
                    if not _visible_to(identity, item.get("org_unit")):
                        continue
                    seen[item["id"]] = item
                it = resp.get("NextShardIterator")
                if not resp.get("Records"):
                    break
    except Exception as exc:  # noqa: BLE001 - the DB feed is the fallback
        print(json.dumps({"event_type": "stream_read_failed", "error": str(exc)}))
        return []
    out = sorted(seen.values(), key=lambda r: str(r.get("at", "")), reverse=True)
    return out[:limit]


def stream_recent(identity: Identity, limit: int = 25) -> Dict[str, Any]:
    """``GET /stream/recent`` → the activity ticker.

    The ordered database projection is authoritative so the latest committed
    event cannot be hidden by an old stream page. Recent Kinesis transport
    receipts are merged by stable id when present. The response labels whether
    both sources contributed, and the ticker never invents traffic.
    """
    stream_records = _activity_from_kinesis(identity, limit)
    database_records = _activity_from_db(identity, limit)
    merged = {str(item["id"]): item for item in stream_records if item.get("id")}
    for item in database_records:
        if item.get("id"):
            merged[str(item["id"])] = item
    records = sorted(
        merged.values(),
        key=lambda record: str(record.get("at", "")),
        reverse=True,
    )[:limit]
    return {
        "records": records,
        "source": "database+kinesis" if stream_records else "database",
    }


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
            """
            WITH batch_scope AS (
              SELECT batch_id,
                     CASE WHEN COUNT(DISTINCT org_unit) = 1 THEN MIN(org_unit) END AS org_unit
              FROM (
                SELECT batch_id, org_unit
                  FROM grants_curated
                 WHERE batch_id IS NOT NULL
                UNION ALL
                SELECT batch_id, raw_jsonb ->> 'org_unit' AS org_unit
                  FROM grants_raw
                 WHERE NULLIF(raw_jsonb ->> 'org_unit', '') IS NOT NULL
              ) scoped
              GROUP BY batch_id
            )
            SELECT q.run_id, q.rule, q.score, q.batch_id, q.created_at, s.org_unit
              FROM grant_quality q
              LEFT JOIN batch_scope s ON s.batch_id = q.batch_id
             WHERE q.created_at > now() - make_interval(secs => %s)
             ORDER BY q.created_at DESC
             LIMIT %s
            """,
            (window, limit),
        )
        for run_id, rule, score, batch_id, created_at, org_unit in cur.fetchall():
            items.append(
                {
                    "id": f"quality:{run_id}:{rule}",
                    "at": created_at.isoformat(),
                    "kind": "quality",
                    "message": f"Quality rule {rule} scored {float(score):.1f} on batch {batch_id}",
                    "org_unit": org_unit,
                }
            )
        cur.execute(
            "SELECT a.id, a.kind, a.severity, a.reason, a.created_at, g.org_unit "
            "FROM anomalies a LEFT JOIN grants_curated g ON g.id = a.grant_id "
            "WHERE a.created_at > now() - make_interval(secs => %s) "
            "ORDER BY a.created_at DESC LIMIT %s",
            (window, limit),
        )
        for aid, kind, severity, reason, created_at, org_unit in cur.fetchall():
            items.append(
                {
                    "id": f"anomaly:{aid}",
                    "at": created_at.isoformat(),
                    "kind": "anomaly",
                    "message": f"[{severity}] {kind}: {reason}",
                    "org_unit": org_unit,
                }
            )

    if not items:
        return {"status": "ok", "published": 0, "window_seconds": window}

    entries = [
        {
            "Data": json.dumps(item, default=str).encode("utf-8"),
            "PartitionKey": item.get("org_unit") or "corporate-only",
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
FIXTURE_CONTRACT = "compass.synthetic.v1"
FIXTURE_RELEASES = {
    "good": {
        "staged_key": "demo-stage/drops/drop_good.fixture",
        "target_key": "drops/drop_good.json",
        "batch_id": "drop-good-2026-08",
        "schema_variant": "canonical",
        "record_count": 40,
        "hash_field": "drop_good_sha256",
    },
    "compatible": {
        "staged_key": "demo-stage/drops/drop_compatible_variant.fixture",
        "target_key": "drops/drop_compatible_variant.json",
        "batch_id": "drop-compat-2026-08",
        "schema_variant": "compatible-renamed",
        "record_count": 40,
        "hash_field": "drop_compatible_sha256",
    },
    "bad": {
        "staged_key": "demo-stage/drops/drop_incompatible_bad.fixture",
        "target_key": "drops/drop_incompatible_bad.json",
        "batch_id": "drop-bad-2026-08",
        "schema_variant": "incompatible-malformed",
        "record_count": 60,
        "hash_field": "drop_bad_sha256",
    },
}
MAX_STAGED_FIXTURE_BYTES = 8 * 1024 * 1024


def _release_prepared_fixture(identity: Identity, bucket: str, name: str, now: str):
    spec = FIXTURE_RELEASES.get(name)
    if spec is None:
        return http.bad_request(
            "fixture must be one of: good, compatible, bad",
            allowed_fixtures=sorted(FIXTURE_RELEASES),
        )

    try:
        staged = pipeline._s3().get_object(Bucket=bucket, Key=spec["staged_key"])
        body = staged["Body"].read(MAX_STAGED_FIXTURE_BYTES + 1)
    except Exception:  # noqa: BLE001 - return a logical operational error only
        return http.error_response(
            409,
            "the fixed synthetic fixture is not staged; run demo preparation first",
            fixture=name,
        )
    if len(body) > MAX_STAGED_FIXTURE_BYTES:
        return http.error_response(409, "the staged fixture exceeds the release limit")

    digest = hashlib.sha256(body).hexdigest()
    metadata = staged.get("Metadata") or {}
    try:
        envelope = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return http.error_response(409, "the staged fixture is not valid UTF-8 JSON")
    valid_contract = (
        isinstance(envelope, dict)
        and envelope.get("fixture_contract") == FIXTURE_CONTRACT
        and envelope.get("synthetic_only") is True
        and envelope.get("generator_seed") == 20260810
        and envelope.get("batch_id") == spec["batch_id"]
        and envelope.get("schema_variant") == spec["schema_variant"]
        and envelope.get("record_count") == spec["record_count"]
        and isinstance(envelope.get("records"), list)
        and len(envelope["records"]) == spec["record_count"]
        and metadata.get("fixture-sha256") == digest
        and metadata.get("synthetic-only") == "true"
    )
    if not valid_contract:
        return http.error_response(409, "the staged fixture failed its synthetic contract")

    conn = db.get_conn()
    with db.set_org(conn, identity.org_unit) as c, c.cursor() as cur:
        cur.execute(
            "SELECT detail_jsonb->>%s FROM audit_log "
            "WHERE actor = 'compass-demo-preparer' AND action = 'demo_reseed' "
            "ORDER BY at DESC LIMIT 1",
            (spec["hash_field"],),
        )
        row = cur.fetchone()
        approved_digest = row[0] if row else None
    if approved_digest != digest:
        return http.error_response(
            409,
            "the staged fixture does not match the latest preparation receipt",
            fixture=name,
        )

    try:
        pipeline._s3().put_object(
            Bucket=bucket,
            Key=spec["target_key"],
            Body=body,
            ContentType="application/json",
            Metadata={
                "fixture-sha256": digest,
                "synthetic-only": "true",
                "fixture-contract": FIXTURE_CONTRACT,
            },
            IfNoneMatch="*",
        )
    except Exception as exc:  # noqa: BLE001 - botocore is a runtime-only dependency
        error = getattr(exc, "response", {}).get("Error", {})
        if str(error.get("Code")) in {"409", "412", "ConditionalRequestConflict", "PreconditionFailed"}:
            return http.error_response(
                409,
                "this fixed fixture was already released; reset before releasing it again",
                fixture=name,
            )
        return http.server_error("the fixed fixture could not be released")

    try:
        with db.set_org(conn, identity.org_unit) as c:
            audit.write_audit(
                c,
                actor=identity.actor,
                action="fixture_released",
                resource=f"grants_raw:{spec['batch_id']}",
                detail={
                    "fixture": name,
                    "batch_id": spec["batch_id"],
                    "source_file": disclosure.logical_source_locator(spec["target_key"]),
                    "status": "queued",
                },
            )
    except Exception:  # noqa: BLE001 - intake itself writes the durable receipt next
        print(
            json.dumps(
                {
                    "event_type": "fixture_release_audit_deferred",
                    "fixture": name,
                    "batch_id": spec["batch_id"],
                }
            )
        )
    return http.json_response(
        202,
        {
            "batch_id": spec["batch_id"],
            "run_id": pipeline.run_id_for(spec["batch_id"]),
            "source_file": disclosure.logical_source_locator(spec["target_key"]),
            "status": "queued",
            "triggered_at": now,
            "trigger": "s3-object-created",
            "fixture": name,
        },
    )


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
    """``POST /ingest/simulate``: release or trigger the real pipeline.

    * ``{"fixture": "good|compatible|bad"}`` atomically copies one fixed,
      preparation-receipted synthetic fixture into the live drop prefix. The
      resulting object-created event is the sole workflow starter.
    * ``{"records": [...]}`` writes the batch under ``drops/simulated/``
      and lets the bucket's EventBridge notification start the pipeline. This
      is the full production path, with no shortcut.
    * ``{"source_file": "drops/drop_good.json"}`` (a key or an ``s3://`` URI for
      an object already in the raw bucket) starts the state machine on it.
    * An empty body picks the most recently modified object under ``drops/``.

    Requires ``poweruser`` because triggering ingest is a write action.
    """
    bucket = os.environ.get("RAW_BUCKET")
    if not bucket:
        return http.server_error("RAW_BUCKET is not configured")

    now = normalize.utc_now_iso()

    fixture = body.get("fixture")
    if fixture is not None:
        return _release_prepared_fixture(identity, bucket, str(fixture), now)

    records = body.get("records")

    if isinstance(records, list) and records:
        stamp = now[:19].replace("-", "").replace(":", "")
        batch_id = str(body.get("batch_id") or f"batch-sim-{stamp}")
        key = f"drops/simulated/{batch_id}.json"
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
                "source_file": disclosure.logical_source_locator(key),
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
            logical_prefix = disclosure.safe_label(prefix, fallback="drops")
            return http.bad_request(
                f"no ingestible object under landing://{logical_prefix}. Upload a drop file "
                "there (seed/drops/*.json), pass {\"source_file\": \"<key>\"}, or post "
                "{\"records\": [...]} to synthesize a batch.",
                source_scope=f"landing://{logical_prefix}",
            )
        key = max(candidates, key=lambda o: o["LastModified"])["Key"]

    try:
        head = pipeline._s3().head_object(Bucket=bucket, Key=key)
    except Exception:  # noqa: BLE001 - a bad key is a client error, not a 500
        return http.not_found(
            f"no such object: {disclosure.logical_source_locator(key)}"
        )
    size = head.get("ContentLength")

    ok, reason = pipeline.is_ingestible(key, size)
    if not ok:
        return http.bad_request(
            f"{disclosure.logical_source_locator(key)} is not ingestible: {reason}"
        )

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
            "source_file": disclosure.logical_source_locator(key),
            "status": "running" if execution_arn else "queued",
            "triggered_at": now,
            "trigger": "state-machine" if execution_arn else "none",
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

    if method == "GET" and route.endswith("/demo-stream"):
        return http.ok(demo_stream_status())

    if method == "POST" and route.endswith("/demo-stream/start"):
        if identity.role != "poweruser" or not identity.is_corporate:
            return http.forbidden("demo stream control requires the corporate poweruser role")
        try:
            body = http.parse_body(event)
            status_code, response = start_demo_stream(identity, body)
        except ValueError as exc:
            return http.bad_request(str(exc))
        return http.json_response(status_code, response)

    if method == "POST" and route.endswith("/demo-stream/stop"):
        if identity.role != "poweruser" or not identity.is_corporate:
            return http.forbidden("demo stream control requires the corporate poweruser role")
        try:
            body = http.parse_body(event)
        except ValueError as exc:
            return http.bad_request(str(exc))
        session_id = str(body.get("session_id") or "")
        if not session_id:
            return http.bad_request("session_id is required")
        try:
            return http.ok(stop_demo_stream(session_id))
        except LookupError:
            return http.not_found("demo stream session not found")

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
    if action == "demo_stream_tick":
        return demo_stream_tick(event)
    if action == "demo_stream_fail":
        return fail_demo_stream(event)

    if (event.get("requestContext") or {}).get("http"):
        return _handle_api(event)

    detail = event.get("detail")
    if isinstance(detail, dict) and detail.get("bucket"):
        return pipeline.fetch_stage(detail)

    raise ValueError(
        "unrecognized intake event; expected a supported action, "
        "an S3 Object Created event, or an HTTP API request"
    )

"""The served OpenAPI 3.1 contract for the Compass API — element 7.

``GET /openapi.json`` returns this document. It is built in code rather than
checked in as a static file for one reason: the ``servers`` block is filled
from the *actual* request context (domain + stage), so the contract a caller
downloads always points at the deployment they downloaded it from.

Every path here is a row of the API table in docs/CONTRACTS.md. Routes owned by
other functions in the stack are documented all the same — an interface
contract that only described one Lambda's routes would not be a contract.

Conventions:
* Schemas mirror the Postgres column names in db/migrations/001_schema.sql
  (snake_case), which is the shape ``frontend/lib/types.ts`` is written against.
* Money fields are ``["number", "null"]``: null is what a caller sees when
  column-level security masks ``amount_usd``, and that is part of the contract,
  not an error.
* Every operation carries ``security: [{cognitoJwt: []}]`` because the HttpApi
  applies a default JWT authorizer to every route (deny-by-default).
"""
from __future__ import annotations

from typing import Any, Dict

API_TITLE = "Compass — S&T Portfolio Intelligence API"
API_VERSION = "1.0.0"

# Strings reused across operations.
_ERR = {"$ref": "#/components/responses/Error"}


def _ref(name: str) -> Dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _json(schema: Dict[str, Any], description: str = "OK") -> Dict[str, Any]:
    return {"description": description, "content": {"application/json": {"schema": schema}}}


def _op(
    op_id: str,
    summary: str,
    element: str,
    response_schema: Dict[str, Any],
    *,
    description: str = "",
    parameters: Any = None,
    request_schema: Dict[str, Any] | None = None,
    extra_responses: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    op: Dict[str, Any] = {
        "operationId": op_id,
        "summary": summary,
        "description": description or summary,
        "tags": [element],
        "security": [{"cognitoJwt": []}],
        "responses": {
            "200": _json(response_schema),
            "401": _ERR,
            "403": _ERR,
            "500": _ERR,
        },
    }
    if parameters:
        op["parameters"] = parameters
    if request_schema is not None:
        op["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": request_schema}},
        }
    if extra_responses:
        op["responses"].update(extra_responses)
    return op


def _schemas() -> Dict[str, Any]:
    money = {"type": ["number", "null"], "description": "null when masked by column-level security"}
    return {
        "Error": {
            "type": "object",
            "required": ["error"],
            "properties": {"error": {"type": "string"}},
            "additionalProperties": True,
        },
        "QualityRuleResult": {
            "type": "object",
            "required": ["rule", "passed_rows", "failed_rows", "score"],
            "properties": {
                "rule": {"type": "string"},
                "passed_rows": {"type": "integer"},
                "failed_rows": {"type": "integer"},
                "score": {"type": ["number", "null"]},
                "details": {"type": ["object", "null"], "additionalProperties": True},
            },
        },
        "QualityFormula": {
            "type": "object",
            "description": "How quality_score was computed, with the inputs it used.",
            "properties": {
                "per_rule": {"type": "string", "examples": ["rule_score = 100 * passed_rows / (passed_rows + failed_rows)"]},
                "overall": {"type": "string"},
                "note": {"type": "string"},
                "source_table": {"type": "string"},
                "run_id": {"type": ["string", "null"]},
                "rule_count": {"type": "integer"},
                "inputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule": {"type": "string"},
                            "passed_rows": {"type": "integer"},
                            "failed_rows": {"type": "integer"},
                            "evaluated_rows": {"type": "integer"},
                            "rule_score": {"type": ["number", "null"]},
                            "weight": {"type": "number"},
                            "score_source": {"type": "string", "enum": ["stored", "recomputed"]},
                        },
                    },
                },
                "computed": {"type": "object", "additionalProperties": True},
            },
        },
        "Me": {
            "type": "object",
            "required": ["sub", "role", "org_unit"],
            "properties": {
                "sub": {"type": "string"},
                "email": {"type": ["string", "null"]},
                "display_name": {"type": ["string", "null"]},
                "role": {"type": "string", "enum": ["poweruser", "viewer"]},
                "org_unit": {"type": "string", "examples": ["ONR-Corporate", "Code-30"]},
                "groups": {"type": "array", "items": {"type": "string"}},
            },
        },
        "CatalogEntry": {
            "type": "object",
            "required": ["id", "batch_id", "run_id", "row_count", "quality_score"],
            "properties": {
                "id": {"type": "string", "description": "== batch_id; the {id} for /catalog/{id}/lineage"},
                "batch_id": {"type": "string"},
                "run_id": {"type": "string"},
                "dataset_name": {"type": "string"},
                "source_file": {"type": "string"},
                "program_area": {"type": "string"},
                "org_unit": {"type": "string"},
                "fiscal_year": {"type": "integer"},
                "fiscal_year_min": {"type": "integer"},
                "fiscal_year_max": {"type": "integer"},
                "row_count": {"type": "integer"},
                "amount_usd": money,
                "amount_masked": {"type": "boolean"},
                "masked_fields": {"type": "array", "items": {"type": "string"}},
                "mask_reason": {"type": ["string", "null"]},
                "quality_score": {"type": ["number", "null"]},
                "quality_rules": {"type": "array", "items": _ref("QualityRuleResult")},
                "quality_formula": _ref("QualityFormula"),
                "classification_band": {"type": "string"},
                "ingested_at": {"type": "string", "format": "date-time"},
                "owner": {"type": "string"},
            },
        },
        "CatalogResponse": {
            "type": "object",
            "required": ["datasets"],
            "properties": {
                "datasets": {"type": "array", "items": _ref("CatalogEntry")},
                "quality_formula": _ref("QualityFormula"),
                "row_filtering": {"type": "object", "additionalProperties": True},
            },
        },
        "LineageNode": {
            "type": "object",
            "required": ["run_id", "node_id", "kind", "label"],
            "properties": {
                "run_id": {"type": "string"},
                "node_id": {"type": "string"},
                "kind": {"type": "string", "enum": ["source", "stage", "table", "model", "dashboard"]},
                "label": {"type": "string"},
                "meta": {"type": ["object", "null"], "additionalProperties": True},
            },
        },
        "LineageEdge": {
            "type": "object",
            "required": ["run_id", "from_node", "to_node"],
            "properties": {
                "run_id": {"type": "string"},
                "from_node": {"type": "string"},
                "to_node": {"type": "string"},
            },
        },
        "LineageResponse": {
            "type": "object",
            "required": ["run_id", "nodes", "edges"],
            "properties": {
                "run_id": {"type": "string"},
                "batch_id": {"type": "string"},
                "nodes": {"type": "array", "items": _ref("LineageNode")},
                "edges": {"type": "array", "items": _ref("LineageEdge")},
                "note": {"type": "string"},
            },
        },
        "IngestSimulateRequest": {
            "type": "object",
            "properties": {"source_file": {"type": "string"}},
        },
        "IngestSimulateResponse": {
            "type": "object",
            "required": ["batch_id", "run_id", "status"],
            "properties": {
                "batch_id": {"type": "string"},
                "run_id": {"type": "string"},
                "source_file": {"type": "string"},
                "status": {"type": "string", "enum": ["queued", "running"]},
                "triggered_at": {"type": "string", "format": "date-time"},
            },
        },
        "IngestBatch": {
            "type": "object",
            "properties": {
                "batch_id": {"type": "string"},
                "run_id": {"type": "string"},
                "source_file": {"type": "string"},
                "ingested_at": {"type": "string", "format": "date-time"},
                "status": {"type": "string", "enum": ["queued", "running", "passed", "failed"]},
                "rows_raw": {"type": "integer"},
                "rows_curated": {"type": "integer"},
                "quality": {"type": "array", "items": _ref("QualityRuleResult")},
                "overall_score": {"type": ["number", "null"]},
            },
        },
        "IngestStatusResponse": {
            "type": "object",
            "required": ["batches"],
            "properties": {"batches": {"type": "array", "items": _ref("IngestBatch")}},
        },
        "StreamRecord": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "at": {"type": "string", "format": "date-time"},
                "kind": {
                    "type": "string",
                    "enum": ["ingest", "quality", "anomaly", "export", "approval", "analytics"],
                },
                "message": {"type": "string"},
                "grant_no": {"type": "string"},
                "org_unit": {"type": "string"},
            },
        },
        "StreamRecentResponse": {
            "type": "object",
            "required": ["records"],
            "properties": {"records": {"type": "array", "items": _ref("StreamRecord")}},
        },
        "AnalyticsRunRequest": {
            "type": "object",
            "properties": {
                "program_area": {"type": "string"},
                "fiscal_year": {"type": "integer"},
                "k": {"type": "integer", "description": "number of topics"},
            },
        },
        "AnalyticsRunResponse": {
            "type": "object",
            "required": ["run_id", "kind", "status"],
            "properties": {
                "run_id": {"type": "string"},
                "kind": {"type": "string", "enum": ["topic_model"]},
                "status": {"type": "string", "enum": ["queued", "running", "completed"]},
            },
        },
        "Topic": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "integer"},
                "label": {"type": "string"},
                "top_terms": {"type": "array", "items": {"type": "string"}},
                "trend": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"period": {"type": "string"}, "value": {"type": "number"}},
                    },
                },
                "grant_count": {"type": "integer"},
                "total_funding_usd": money,
            },
        },
        "AnalyticsRunDetail": {
            "type": "object",
            "required": ["run_id", "kind", "topics"],
            "properties": {
                "run_id": {"type": "string"},
                "kind": {"type": "string", "enum": ["topic_model"]},
                "status": {"type": "string"},
                "params": {"type": "object", "additionalProperties": True},
                "metrics": {"type": "object", "additionalProperties": True},
                "recommendation": {"type": "string"},
                "topics": {"type": "array", "items": _ref("Topic")},
                "created_at": {"type": "string", "format": "date-time"},
            },
        },
        "DashboardResponse": {
            "type": "object",
            "required": ["kpis"],
            "properties": {
                "kpis": {
                    "type": "object",
                    "properties": {
                        "total_grants": {"type": "integer"},
                        "total_funding_usd": money,
                        "active_program_areas": {"type": "integer"},
                        "avg_quality_score": {"type": ["number", "null"]},
                        "open_anomalies": {"type": "integer"},
                        "pending_approvals": {"type": "integer"},
                    },
                },
                "funding_by_program_area": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "program_area": {"type": "string"},
                            "amount_usd": money,
                            "grant_count": {"type": "integer"},
                        },
                    },
                },
                "funding_by_fiscal_year": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fiscal_year": {"type": "integer"},
                            "amount_usd": money,
                        },
                    },
                },
                "quality_trend": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "run_id": {"type": "string"},
                            "date": {"type": "string"},
                            "score": {"type": "number"},
                        },
                    },
                },
                "top_topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic_id": {"type": "integer"},
                            "label": {"type": "string"},
                            "weight": {"type": "number"},
                        },
                    },
                },
                "org_unit_breakdown": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "org_unit": {"type": "string"},
                            "grant_count": {"type": "integer"},
                            "amount_usd": money,
                        },
                    },
                },
            },
        },
        "ChatRequest": {
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": {"type": "string"},
                "history": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["user", "assistant"]},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
        },
        "ChatResponse": {
            "type": "object",
            "required": ["answer"],
            "properties": {
                "answer": {"type": "string"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "grant_no": {"type": "string"},
                            "title": {"type": "string"},
                            "snippet": {"type": "string"},
                        },
                    },
                },
                "model": {
                    "type": "string",
                    "description": "Bedrock model id — in-boundary only (amazon.nova-lite-v1:0)",
                },
            },
        },
        "Anomaly": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "grant_id": {"type": ["integer", "null"]},
                "grant_no": {"type": ["string", "null"]},
                "kind": {"type": "string"},
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "reason": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "acknowledged", "resolved"]},
                "created_at": {"type": "string", "format": "date-time"},
            },
        },
        "AnomaliesResponse": {
            "type": "object",
            "required": ["anomalies"],
            "properties": {
                "anomalies": {"type": "array", "items": _ref("Anomaly")},
                "summary": {"type": "object", "additionalProperties": True},
                "filters": {"type": "object", "additionalProperties": True},
            },
        },
        "ApprovalRequest": {
            "type": "object",
            "required": ["subject_type", "subject_id", "action"],
            "properties": {
                "subject_type": {"type": "string", "examples": ["export"]},
                "subject_id": {"type": "string"},
                "action": {"type": "string", "enum": ["request", "approve", "reject"]},
                "note": {"type": "string"},
            },
        },
        "Approval": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "subject_type": {"type": "string"},
                "subject_id": {"type": "string"},
                "state": {"type": "string", "enum": ["pending", "approved", "rejected"]},
                "requested_by": {"type": ["string", "null"]},
                "decided_by": {"type": ["string", "null"]},
                "decided_at": {"type": ["string", "null"], "format": "date-time"},
                "note": {"type": ["string", "null"]},
                "created_at": {"type": "string", "format": "date-time"},
            },
        },
        "ApprovalResponse": {
            "type": "object",
            "required": ["approval"],
            "properties": {
                "approval": _ref("Approval"),
                "approval_token": {
                    "type": ["string", "null"],
                    "description": "Issued only on an approved decision; POST /export accepts it.",
                },
                "four_eyes": {"type": "object", "additionalProperties": True},
            },
        },
        "License": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "vendor": {"type": "string"},
                "product": {"type": "string"},
                "datasets": {"type": "array", "items": {"type": "string"}},
                "entitlements": {"type": "string"},
                "seats_used": {"type": "integer"},
                "seats_total": {"type": "integer"},
                "renews_on": {"type": ["string", "null"], "format": "date"},
                "owner": {"type": "string"},
                "status": {"type": "string", "enum": ["active", "expiring", "expired", "suspended"]},
                "status_stored": {"type": "string"},
                "days_to_renewal": {"type": ["integer", "null"]},
                "renewal_alert": {"type": "object", "additionalProperties": True},
                "seat_alert": {"type": "object", "additionalProperties": True},
                "needs_action": {"type": "boolean"},
            },
        },
        "LicensesResponse": {
            "type": "object",
            "required": ["licenses"],
            "properties": {
                "licenses": {"type": "array", "items": _ref("License")},
                "alerts": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "summary": {"type": "object", "additionalProperties": True},
                "thresholds": {"type": "object", "additionalProperties": True},
            },
        },
        "ExportRequest": {
            "type": "object",
            "required": ["format"],
            "properties": {
                "format": {"type": "string", "enum": ["csv", "json", "parquet"]},
                "filters": {
                    "type": "object",
                    "description": "Whitelisted filters only; anything else is a 400.",
                    "properties": {
                        "program_area": {"type": "string"},
                        "org_unit": {"type": "string"},
                        "awardee": {"type": "string", "description": "substring match"},
                        "classification_band": {"type": "string"},
                        "batch_id": {"type": "string"},
                        "grant_no": {"type": "string"},
                        "fiscal_year": {"type": "integer"},
                        "fiscal_year_min": {"type": "integer"},
                        "fiscal_year_max": {"type": "integer"},
                        "min_amount_usd": {
                            "type": "number",
                            "description": "Rejected with 403 for callers whose amount_usd is masked.",
                        },
                        "max_amount_usd": {"type": "number"},
                        "q": {"type": "string", "description": "substring match on title/abstract"},
                        "limit": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Subset of the exportable column whitelist.",
                },
                "approval_token": {
                    "type": "string",
                    "description": "apr-<id> from POST /approvals; clears the aggregation guard.",
                },
            },
        },
        "ExportResponse": {
            "type": "object",
            "required": ["export_id", "row_count", "format", "download_url", "audited"],
            "properties": {
                "export_id": {"type": "string"},
                "row_count": {"type": "integer", "description": "rows actually written"},
                "matched_rows": {"type": "integer", "description": "rows the filter selected under RLS"},
                "format": {"type": "string", "enum": ["csv", "json", "parquet"]},
                "requested_format": {"type": "string", "enum": ["csv", "json", "parquet"]},
                "download_url": {"type": "string"},
                "delivery": {"type": "string", "enum": ["s3-presigned", "inline-data-uri"]},
                "bytes": {"type": "integer"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "masked_fields": {"type": "array", "items": {"type": "string"}},
                "filters_applied": {"type": "object", "additionalProperties": True},
                "audited": {"type": "boolean", "const": True},
                "audit_id": {"type": "integer"},
                "note": {"type": "string"},
            },
        },
        "ApprovalRequired": {
            "type": "object",
            "required": ["error", "row_count", "max_rows"],
            "properties": {
                "error": {"type": "string", "const": "approval_required"},
                "row_count": {"type": "integer"},
                "max_rows": {"type": "integer"},
                "subject_type": {"type": "string", "const": "export"},
                "subject_id": {"type": "string", "description": "POST this to /approvals to request clearance"},
                "how_to_clear": {"type": "string"},
            },
        },
    }


def build_openapi(server_url: str = "") -> Dict[str, Any]:
    """Return the OpenAPI 3.1 document, optionally bound to a concrete server."""
    servers = [{"url": server_url, "description": "This deployment"}] if server_url else []

    paths: Dict[str, Any] = {
        "/me": {
            "get": _op(
                "getMe",
                "Current identity, role and org_unit",
                "1 · identity",
                _ref("Me"),
                description="Echoes the authorizer's mapping of cognito:groups -> role "
                            "and the org_unit that will be bound to compass.org_unit for "
                            "row-level security on every subsequent call.",
            )
        },
        "/catalog": {
            "get": _op(
                "listCatalog",
                "Catalog of ingested datasets with quality scores",
                "4 · catalog",
                _ref("CatalogResponse"),
                description="One entry per ingest batch, each carrying its quality score "
                            "AND the formula plus per-rule inputs that produced it. "
                            "Batches with no rows visible under RLS do not appear.",
            )
        },
        "/catalog/{id}/lineage": {
            "get": _op(
                "getLineage",
                "Lineage graph for a dataset's latest run",
                "4 · catalog",
                _ref("LineageResponse"),
                description="Nodes and edges recorded by the pipeline for the most recent "
                            "run of this batch. Serving is gated on the caller being able "
                            "to see at least one curated row from the batch under RLS.",
                parameters=[
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "batch_id (or run_id) from GET /catalog",
                    }
                ],
                extra_responses={"404": _ERR},
            )
        },
        "/ingest/simulate": {
            "post": _op(
                "simulateIngest",
                "Trigger a demo file-drop into the landing zone",
                "3 · ingest",
                _ref("IngestSimulateResponse"),
                request_schema=_ref("IngestSimulateRequest"),
                description="Developer convenience: copies a seed drop into the raw bucket, "
                            "which fires the real S3 -> EventBridge -> Step Functions path.",
            )
        },
        "/ingest/status": {
            "get": _op(
                "getIngestStatus",
                "Recent batches and their quality-gate results",
                "3 · ingest",
                _ref("IngestStatusResponse"),
            )
        },
        "/stream/recent": {
            "get": _op(
                "getStreamRecent",
                "Recent streamed records for the live ticker",
                "3 · ingest",
                _ref("StreamRecentResponse"),
            )
        },
        "/analytics/run": {
            "post": _op(
                "runAnalytics",
                "Run the topic-model routine over curated abstracts",
                "5 · analytics",
                _ref("AnalyticsRunResponse"),
                request_schema=_ref("AnalyticsRunRequest"),
            )
        },
        "/analytics/{run_id}": {
            "get": _op(
                "getAnalyticsRun",
                "Topics, trends and the run's recommendation",
                "5 · analytics",
                _ref("AnalyticsRunDetail"),
                parameters=[
                    {"name": "run_id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                extra_responses={"404": _ERR},
            )
        },
        "/dashboard": {
            "get": _op(
                "getDashboard",
                "Executive dashboard: KPIs and every chart series in one round-trip",
                "6 · dashboard",
                _ref("DashboardResponse"),
            )
        },
        "/chat": {
            "post": _op(
                "postChat",
                "Natural-language Q&A over the curated portfolio (RAG)",
                "6 · dashboard",
                _ref("ChatResponse"),
                request_schema=_ref("ChatRequest"),
                description="Retrieval runs against pgvector embeddings of curated "
                            "abstracts under the caller's RLS context; generation uses "
                            "Bedrock in-boundary (amazon.nova-lite-v1:0).",
            )
        },
        "/anomalies": {
            "get": _op(
                "getAnomalies",
                "Open anomaly queue",
                "6 · dashboard",
                _ref("AnomaliesResponse"),
                parameters=[
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["open", "acknowledged", "resolved", "all"]},
                    },
                    {
                        "name": "severity",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    },
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "maximum": 500}},
                ],
            )
        },
        "/approvals": {
            "post": _op(
                "postApproval",
                "Create or advance an approval",
                "6 · dashboard",
                _ref("ApprovalResponse"),
                request_schema=_ref("ApprovalRequest"),
                description="request -> pending -> approve|reject. Only a poweruser may "
                            "decide. An approved decision returns the approval_token that "
                            "clears the POST /export aggregation guard.",
                extra_responses={"201": _json(_ref("ApprovalResponse"), "Approval requested"), "404": _ERR},
            )
        },
        "/licenses": {
            "get": _op(
                "getLicenses",
                "Data-license lifecycle table with renewal alerts",
                "6 · dashboard",
                _ref("LicensesResponse"),
            )
        },
        "/export": {
            "post": _op(
                "postExport",
                "Filtered export (csv | json | parquet)",
                "7 · export",
                _ref("ExportResponse"),
                request_schema=_ref("ExportRequest"),
                description=(
                    "Applies row-level security (org context), column-level security "
                    "(amount_usd masked for viewers), and the aggregation guard: if the "
                    "filter matches more than EXPORT_MAX_ROWS rows the request is refused "
                    "with 428 unless a valid approval_token is attached. Every outcome — "
                    "allowed, blocked, denied — writes compass.audit_log."
                ),
                extra_responses={
                    "400": _ERR,
                    "413": _ERR,
                    "428": _json(_ref("ApprovalRequired"), "Aggregation guard tripped — approval required"),
                },
            )
        },
        "/openapi.json": {
            "get": _op(
                "getOpenApi",
                "This document",
                "7 · export",
                {"type": "object", "additionalProperties": True},
            )
        },
    }

    return {
        "openapi": "3.1.0",
        "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "info": {
            "title": API_TITLE,
            "version": API_VERSION,
            "summary": "Portfolio intelligence over a synthetic ONR S&T grants portfolio.",
            "description": (
                "Every route is behind a Cognito JWT authorizer (deny-by-default). "
                "Data access is governed in PostgreSQL, not in application code: "
                "row-level security keys on `compass.org_unit`, set per transaction from "
                "the caller's claim, and column-level security revokes `amount_usd` from "
                "the runtime role. All data is synthetic — no real CUI or PII."
            ),
            "contact": {"name": "Compass demo"},
            "license": {"name": "Demonstration use only", "identifier": "LicenseRef-demo"},
        },
        "servers": servers,
        "tags": [
            {"name": "1 · identity", "description": "Who is calling, and with what entitlements"},
            {"name": "3 · ingest", "description": "File drop, quality gate, live ticker"},
            {"name": "4 · catalog", "description": "Datasets, quality scores, lineage"},
            {"name": "5 · analytics", "description": "Topic model over curated abstracts"},
            {"name": "6 · dashboard", "description": "KPIs, chat, anomalies, approvals, licenses"},
            {"name": "7 · export", "description": "Governed export and the served contract"},
        ],
        "security": [{"cognitoJwt": []}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                "cognitoJwt": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Cognito user-pool token. The API Gateway JWT authorizer "
                                   "validates it and the request context carries the "
                                   "role / org_unit used for RLS.",
                }
            },
            "responses": {
                "Error": _json(_ref("Error"), "Error"),
            },
            "schemas": _schemas(),
        },
    }

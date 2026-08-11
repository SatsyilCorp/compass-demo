"""The served OpenAPI 3.1 contract for the Compass API, element 7.

``GET /openapi.json`` returns this document. It is built in code rather than
checked in as a static file for one reason: the ``servers`` block is filled
from the *actual* request context (domain + stage), so the contract a caller
downloads always points at the deployment they downloaded it from.

Every path here is a row of the API table in docs/CONTRACTS.md. Routes owned by
other functions in the stack are documented all the same. An interface
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

from typing import Any

API_TITLE = "Compass | S&T Portfolio Intelligence API"
API_VERSION = "1.3.0"

# Strings reused across operations.
_ERR = {"$ref": "#/components/responses/Error"}


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _json(schema: dict[str, Any], description: str = "OK") -> dict[str, Any]:
    return {"description": description, "content": {"application/json": {"schema": schema}}}


def _op(
    op_id: str,
    summary: str,
    element: str,
    response_schema: dict[str, Any],
    *,
    description: str = "",
    parameters: Any = None,
    request_schema: dict[str, Any] | None = None,
    success_status: str = "200",
    success_description: str = "OK",
    extra_responses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    op: dict[str, Any] = {
        "operationId": op_id,
        "summary": summary,
        "description": description or summary,
        "tags": [element],
        "security": [{"cognitoJwt": []}],
        "responses": {
            success_status: _json(response_schema, success_description),
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


def _schemas() -> dict[str, Any]:
    money = {"type": ["number", "null"], "description": "null when masked by column-level security"}
    scale_cost_required = [
        "currency",
        "estimated_run_usd",
        "upper_bound_usd",
        "incremental_idle_monthly_usd",
        "pricing_as_of",
        "estimate_source",
        "disclaimer",
        "line_items",
    ]
    scale_cost_properties = {
        "currency": {"type": "string", "const": "USD"},
        "estimated_run_usd": {"type": "number", "minimum": 0},
        "upper_bound_usd": {"type": "number", "minimum": 0},
        "incremental_idle_monthly_usd": {"type": "number", "minimum": 0},
        "pricing_as_of": {"type": "string", "format": "date-time"},
        "estimate_source": {
            "type": "string",
            "enum": ["aws_price_model", "replay_model"],
            "description": "Live API responses use aws_price_model.",
        },
        "disclaimer": {"type": "string"},
        "line_items": {
            "type": "array",
            "items": _ref("ScaleCostLineItem"),
        },
    }
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
            "properties": {
                "fixture": {
                    "type": "string",
                    "enum": ["good", "compatible", "bad"],
                    "description": (
                        "Release one fixed, preparation-receipted synthetic fixture. "
                        "The object-created event owns workflow start and duplicate "
                        "release is blocked."
                    ),
                },
                "source_file": {"type": "string"},
            },
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
                "trigger": {"type": "string"},
                "fixture": {
                    "type": "string",
                    "enum": ["good", "compatible", "bad"],
                },
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
                "filters_applied": {
                    "type": "object",
                    "properties": {
                        "program_area": {"type": ["string", "null"]},
                        "fiscal_year": {"type": ["integer", "null"]},
                        "org_unit": {"type": ["string", "null"]},
                        "q": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                "filter_options": {
                    "type": "object",
                    "properties": {
                        "program_areas": {"type": "array", "items": {"type": "string"}},
                        "fiscal_years": {"type": "array", "items": {"type": "integer"}},
                        "org_units": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": False,
                },
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
                    "description": "Bedrock model id, in-boundary only (amazon.nova-lite-v1:0)",
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
                "expires_at": {"type": ["string", "null"], "format": "date-time"},
                "consumed_at": {"type": ["string", "null"], "format": "date-time"},
                "consumed_by": {"type": ["string", "null"]},
            },
        },
        "ApprovalResponse": {
            "type": "object",
            "required": ["approval"],
            "properties": {
                "approval": _ref("Approval"),
                "approval_token": {
                    "type": ["string", "null"],
                    "description": (
                        "Opaque, short-lived, single-use value issued only in a successful "
                        "approve response. The inbox never returns it and the service stores "
                        "only its SHA-256 digest."
                    ),
                },
                "four_eyes": {"type": "object", "additionalProperties": True},
            },
        },
        "ApprovalsListResponse": {
            "type": "object",
            "required": [
                "approvals",
                "actor",
                "scope",
                "can_decide",
                "four_eyes_enforced",
                "tokens_included",
                "generated_at",
            ],
            "properties": {
                "approvals": {
                    "type": "array",
                    "items": _ref("Approval"),
                    "description": "Pending approvals visible to the caller.",
                },
                "actor": {"type": "string"},
                "scope": {
                    "type": "string",
                    "enum": ["all_pending", "requested_by_actor"],
                },
                "can_decide": {"type": "boolean"},
                "four_eyes_enforced": {"type": "boolean"},
                "tokens_included": {
                    "type": "boolean",
                    "const": False,
                    "description": "The list route never returns capability tokens.",
                },
                "generated_at": {"type": "string", "format": "date-time"},
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
                    "description": (
                        "Opaque one-time token from the independent approve response. "
                        "It clears the guard only for the exact bound request."
                    ),
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
        "ScaleProfileId": {
            "type": "string",
            "enum": ["1k", "10k", "100k", "1m"],
            "description": "A server-approved workload profile. Arbitrary record counts are not accepted.",
        },
        "ScaleCapacityState": {
            "type": "string",
            "enum": ["ready", "locked"],
        },
        "ScaleStageId": {
            "type": "string",
            "enum": [
                "plan",
                "generate",
                "buffer",
                "ingest",
                "quality",
                "curate",
                "intelligence",
                "export",
                "evidence",
            ],
        },
        "ScaleRunStatus": {
            "type": "string",
            "enum": [
                "queued",
                "generating",
                "ingesting",
                "quality",
                "intelligence",
                "exporting",
                "cancelling",
                "cancelled",
                "completed",
                "failed",
            ],
        },
        "ScaleSyntheticDomain": {
            "type": "string",
            "enum": [
                "grants",
                "finance",
                "milestones",
                "documents",
                "licenses",
                "stream_events",
            ],
        },
        "ScaleProfile": {
            "type": "object",
            "required": [
                "id",
                "label",
                "short_label",
                "total_records",
                "description",
                "capacity_state",
                "capacity_note",
                "recommended",
            ],
            "properties": {
                "id": _ref("ScaleProfileId"),
                "label": {"type": "string"},
                "short_label": {"type": "string"},
                "total_records": {"type": "integer", "minimum": 1},
                "description": {"type": "string"},
                "capacity_state": _ref("ScaleCapacityState"),
                "capacity_note": {"type": "string"},
                "recommended": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "ScaleProfilesResponse": {
            "type": "object",
            "required": ["profiles", "generated_at"],
            "properties": {
                "profiles": {
                    "type": "array",
                    "items": _ref("ScaleProfile"),
                    "minItems": 4,
                    "maxItems": 4,
                },
                "generated_at": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": False,
        },
        "ScaleDatasetAllocation": {
            "type": "object",
            "required": ["domain", "label", "records", "percentage", "purpose"],
            "properties": {
                "domain": _ref("ScaleSyntheticDomain"),
                "label": {"type": "string"},
                "records": {"type": "integer", "minimum": 0},
                "percentage": {"type": "number", "minimum": 0, "maximum": 100},
                "purpose": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "ScaleCostLineItem": {
            "type": "object",
            "required": ["id", "label", "estimated_usd", "basis"],
            "properties": {
                "id": {"type": "string"},
                "label": {"type": "string"},
                "estimated_usd": {"type": "number", "minimum": 0},
                "basis": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "ScaleCostEstimate": {
            "type": "object",
            "required": scale_cost_required,
            "properties": scale_cost_properties,
            "additionalProperties": False,
        },
        "ScalePlanStage": {
            "type": "object",
            "required": ["id", "label", "detail", "resource"],
            "properties": {
                "id": _ref("ScaleStageId"),
                "label": {"type": "string"},
                "detail": {"type": "string"},
                "resource": {
                    "type": "string",
                    "description": "Logical service role, not a deployed resource identifier.",
                },
            },
            "additionalProperties": False,
        },
        "ScalePlan": {
            "type": "object",
            "required": [
                "plan_id",
                "profile_id",
                "seed",
                "generated_at",
                "capacity_state",
                "total_records",
                "estimated_raw_bytes",
                "target_duration_seconds",
                "concurrency_limit",
                "partition_count",
                "dataset_mix",
                "stages",
                "cost",
            ],
            "properties": {
                "plan_id": {"type": "string"},
                "profile_id": _ref("ScaleProfileId"),
                "seed": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 9999999999,
                },
                "generated_at": {"type": "string", "format": "date-time"},
                "capacity_state": _ref("ScaleCapacityState"),
                "total_records": {"type": "integer", "minimum": 1},
                "estimated_raw_bytes": {"type": "integer", "minimum": 0},
                "target_duration_seconds": {"type": "integer", "minimum": 1},
                "concurrency_limit": {"type": "integer", "minimum": 1},
                "partition_count": {"type": "integer", "minimum": 1},
                "dataset_mix": {
                    "type": "array",
                    "items": _ref("ScaleDatasetAllocation"),
                    "minItems": 6,
                    "maxItems": 6,
                },
                "stages": {
                    "type": "array",
                    "items": _ref("ScalePlanStage"),
                    "minItems": 9,
                    "maxItems": 9,
                },
                "cost": _ref("ScaleCostEstimate"),
            },
            "additionalProperties": False,
        },
        "ScalePlanRequest": {
            "type": "object",
            "required": ["profile_id", "seed"],
            "properties": {
                "profile_id": _ref("ScaleProfileId"),
                "seed": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 9999999999,
                },
            },
            "additionalProperties": False,
        },
        "ScaleLaunchRequest": {
            "type": "object",
            "required": ["plan_id", "idempotency_key"],
            "properties": {
                "plan_id": {"type": "string", "minLength": 1},
                "idempotency_key": {
                    "type": "string",
                    "minLength": 12,
                    "maxLength": 128,
                },
            },
            "additionalProperties": False,
        },
        "ScaleCancelRequest": {
            "type": "object",
            "required": ["reason"],
            "properties": {
                "reason": {"type": "string", "const": "operator_requested"},
            },
            "additionalProperties": False,
        },
        "ScaleExportRequest": {
            "type": "object",
            "required": ["dataset", "format", "idempotency_key"],
            "properties": {
                "dataset": {"type": "string", "const": "curated_portfolio"},
                "format": {"type": "string", "const": "parquet"},
                "idempotency_key": {
                    "type": "string",
                    "minLength": 12,
                    "maxLength": 128,
                },
            },
            "additionalProperties": False,
        },
        "ScaleRunProgress": {
            "type": "object",
            "required": [
                "stage",
                "percent",
                "records_generated",
                "records_ingested",
                "records_curated",
                "records_quarantined",
                "bytes_written",
                "partitions_completed",
                "partitions_total",
                "current_throughput_rps",
                "peak_throughput_rps",
                "elapsed_seconds",
                "eta_seconds",
            ],
            "properties": {
                "stage": _ref("ScaleStageId"),
                "percent": {"type": "number", "minimum": 0, "maximum": 100},
                "records_generated": {"type": "integer", "minimum": 0},
                "records_ingested": {"type": "integer", "minimum": 0},
                "records_curated": {"type": "integer", "minimum": 0},
                "records_quarantined": {"type": "integer", "minimum": 0},
                "bytes_written": {"type": "integer", "minimum": 0},
                "partitions_completed": {"type": "integer", "minimum": 0},
                "partitions_total": {"type": "integer", "minimum": 0},
                "current_throughput_rps": {"type": "number", "minimum": 0},
                "peak_throughput_rps": {"type": "number", "minimum": 0},
                "elapsed_seconds": {"type": "integer", "minimum": 0},
                "eta_seconds": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                },
            },
            "additionalProperties": False,
        },
        "ScaleQualityRule": {
            "type": "object",
            "required": [
                "id",
                "label",
                "score",
                "passed_records",
                "failed_records",
            ],
            "properties": {
                "id": {"type": "string"},
                "label": {"type": "string"},
                "score": {"type": "number", "minimum": 0, "maximum": 100},
                "passed_records": {"type": "integer", "minimum": 0},
                "failed_records": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "ScaleRunQuality": {
            "type": "object",
            "required": [
                "overall_score",
                "passed_records",
                "failed_records",
                "quarantined_records",
                "rules",
            ],
            "properties": {
                "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
                "passed_records": {"type": "integer", "minimum": 0},
                "failed_records": {"type": "integer", "minimum": 0},
                "quarantined_records": {"type": "integer", "minimum": 0},
                "rules": {
                    "type": "array",
                    "items": _ref("ScaleQualityRule"),
                },
            },
            "additionalProperties": False,
        },
        "ScaleTopic": {
            "type": "object",
            "required": ["label", "record_count", "confidence", "terms"],
            "properties": {
                "label": {"type": "string"},
                "record_count": {"type": "integer", "minimum": 0},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "terms": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "ScaleRunIntelligence": {
            "type": "object",
            "required": [
                "status",
                "model_run_id",
                "grants_analyzed",
                "topic_count",
                "anomalies_detected",
                "processing_seconds",
                "top_topics",
            ],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "completed", "cancelled"],
                },
                "model_run_id": {
                    "type": ["string", "null"],
                    "description": "Deterministic intelligence receipt identifier.",
                },
                "grants_analyzed": {"type": "integer", "minimum": 0},
                "topic_count": {"type": "integer", "minimum": 0},
                "anomalies_detected": {"type": "integer", "minimum": 0},
                "processing_seconds": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                },
                "top_topics": {
                    "type": "array",
                    "items": _ref("ScaleTopic"),
                },
            },
            "additionalProperties": False,
        },
        "ScaleExportReceipt": {
            "type": "object",
            "required": [
                "export_id",
                "status",
                "format",
                "row_count",
                "bytes",
                "object_uri",
                "download_url",
                "expires_at",
                "sha256",
            ],
            "properties": {
                "export_id": {"type": ["string", "null"]},
                "status": {
                    "type": "string",
                    "enum": ["pending", "building", "ready", "cancelled"],
                },
                "format": {"type": "string", "const": "parquet"},
                "row_count": {"type": "integer", "minimum": 0},
                "bytes": {"type": "integer", "minimum": 0},
                "object_uri": {
                    "type": ["string", "null"],
                    "description": "Opaque logical object locator without physical deployment details.",
                },
                "download_url": {
                    "type": ["string", "null"],
                    "description": "Short-lived download URL, present only while a ready export remains valid.",
                },
                "expires_at": {
                    "type": ["string", "null"],
                    "format": "date-time",
                },
                "sha256": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        },
        "ScaleEvidenceStage": {
            "type": "object",
            "required": ["id", "label", "status", "receipt", "recorded_at"],
            "properties": {
                "id": _ref("ScaleStageId"),
                "label": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": [
                        "pending",
                        "running",
                        "completed",
                        "cancelled",
                        "failed",
                    ],
                },
                "receipt": {
                    "type": ["string", "null"],
                    "description": "Logical evidence receipt identifier.",
                },
                "recorded_at": {
                    "type": ["string", "null"],
                    "format": "date-time",
                },
            },
            "additionalProperties": False,
        },
        "ScaleRunEvidence": {
            "type": "object",
            "required": [
                "correlation_id",
                "audit_receipt",
                "manifest_uri",
                "manifest_sha256",
                "metrics_recorded_at",
                "recovery_queue_depth",
                "duplicate_records_suppressed",
                "stages",
            ],
            "properties": {
                "correlation_id": {"type": "string"},
                "audit_receipt": {"type": "string"},
                "manifest_uri": {
                    "type": "string",
                    "description": "Logical manifest locator without physical deployment details.",
                },
                "manifest_sha256": {"type": "string"},
                "metrics_recorded_at": {"type": "string", "format": "date-time"},
                "recovery_queue_depth": {"type": "integer", "minimum": 0},
                "duplicate_records_suppressed": {"type": "integer", "minimum": 0},
                "stages": {
                    "type": "array",
                    "items": _ref("ScaleEvidenceStage"),
                    "minItems": 9,
                    "maxItems": 9,
                },
            },
            "additionalProperties": False,
        },
        "ScaleRunCost": {
            "type": "object",
            "required": [*scale_cost_required, "accrued_usd"],
            "properties": {
                **scale_cost_properties,
                "accrued_usd": {"type": "number", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "ScaleRunError": {
            "type": "object",
            "required": ["code", "message", "retryable"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "retryable": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "ScaleRun": {
            "type": "object",
            "required": [
                "run_id",
                "mode",
                "status",
                "created_at",
                "started_at",
                "updated_at",
                "completed_at",
                "cancelled_at",
                "plan",
                "progress",
                "quality",
                "costs",
                "intelligence",
                "export_receipt",
                "evidence",
                "error",
            ],
            "properties": {
                "run_id": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["live", "replay"],
                    "description": "Deployed API responses use live. Replay is a frontend-only adapter mode.",
                },
                "status": _ref("ScaleRunStatus"),
                "created_at": {"type": "string", "format": "date-time"},
                "started_at": {"type": ["string", "null"], "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
                "completed_at": {"type": ["string", "null"], "format": "date-time"},
                "cancelled_at": {"type": ["string", "null"], "format": "date-time"},
                "plan": _ref("ScalePlan"),
                "progress": _ref("ScaleRunProgress"),
                "quality": _ref("ScaleRunQuality"),
                "costs": _ref("ScaleRunCost"),
                "intelligence": _ref("ScaleRunIntelligence"),
                "export_receipt": _ref("ScaleExportReceipt"),
                "evidence": _ref("ScaleRunEvidence"),
                "error": {
                    "oneOf": [_ref("ScaleRunError"), {"type": "null"}],
                },
            },
            "additionalProperties": False,
        },
        "ScaleRunsResponse": {
            "type": "object",
            "required": ["runs", "generated_at"],
            "properties": {
                "runs": {
                    "type": "array",
                    "items": _ref("ScaleRun"),
                },
                "generated_at": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": False,
        },
        "SystemEvidence": {
            "type": "object",
            "required": [
                "mode",
                "evidence_class",
                "generated_at",
                "deploy_revision",
                "correlation_id",
                "request",
                "identity_decision",
                "health",
                "metrics",
                "services",
                "recent_runs",
                "recent_audit",
                "controls",
                "disclosure",
            ],
            "properties": {
                "mode": {"type": "string", "const": "live"},
                "evidence_class": {
                    "type": "string",
                    "const": "sanitized_application_projection",
                },
                "generated_at": {"type": "string", "format": "date-time"},
                "deploy_revision": {"type": "string"},
                "correlation_id": {"type": "string"},
                "request": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "const": "GET"},
                        "route": {"type": "string", "const": "/system/evidence"},
                        "status": {"type": "integer"},
                        "latency_ms": {"type": "integer"},
                    },
                },
                "identity_decision": {
                    "type": "object",
                    "description": "Resolved policy result only. Raw claims are never returned.",
                    "additionalProperties": {"type": ["string", "boolean"]},
                },
                "health": {"type": "object", "additionalProperties": {"type": "string"}},
                "metrics": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                },
                "services": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "recent_runs": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "recent_audit": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "description": "Allowlisted audit projection without actor identity or delivery location.",
                        "additionalProperties": True,
                    },
                },
                "latest_model_run": {
                    "type": ["object", "null"],
                    "additionalProperties": True,
                },
                "controls": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "disclosure": {"type": "string"},
            },
        },
    }


def build_openapi(server_url: str = "") -> dict[str, Any]:
    """Return the OpenAPI 3.1 document, optionally bound to a concrete server."""
    servers = [{"url": server_url, "description": "This deployment"}] if server_url else []

    paths: dict[str, Any] = {
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
                description=(
                    "Releases one fixed, preparation-receipted synthetic fixture "
                    "into the landing zone. Its S3 object-created event fires the "
                    "real EventBridge to Step Functions path exactly once."
                ),
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
                parameters=[
                    {"name": "program_area", "in": "query", "schema": {"type": "string"}},
                    {"name": "fiscal_year", "in": "query", "schema": {"type": "integer"}},
                    {"name": "org_unit", "in": "query", "schema": {"type": "string"}},
                    {
                        "name": "q",
                        "in": "query",
                        "description": "Case-insensitive title and abstract search.",
                        "schema": {"type": "string"},
                    },
                ],
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
            "get": _op(
                "listPendingApprovals",
                "List pending approvals visible to the caller",
                "6 · dashboard",
                _ref("ApprovalsListResponse"),
                description=(
                    "Powerusers receive the shared pending review queue. Viewers receive only "
                    "requests they created. Capability tokens are never returned by this read "
                    "path. A token is issued only in the successful POST approve response."
                ),
            ),
            "post": _op(
                "postApproval",
                "Create or advance an approval",
                "6 · dashboard",
                _ref("ApprovalResponse"),
                request_schema=_ref("ApprovalRequest"),
                description="request -> pending -> approve|reject. Only a separate poweruser may "
                            "decide. An approved decision returns a short-lived, single-use "
                            "approval_token for copy and paste into the exact POST /export retry.",
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
                    "with 428 unless a valid approval_token is attached. Every outcome, "
                    "whether allowed, blocked, or denied, writes compass.audit_log."
                ),
                extra_responses={
                    "400": _ERR,
                    "413": _ERR,
                    "428": _json(_ref("ApprovalRequired"), "Aggregation guard tripped: approval required"),
                },
            )
        },
        "/scale/profiles": {
            "get": _op(
                "getScaleProfiles",
                "List guarded synthetic workload profiles",
                "8 · scale lab",
                _ref("ScaleProfilesResponse"),
                description=(
                    "Poweruser-only capacity catalog for the four server-approved "
                    "synthetic workload sizes. Readiness and lock reasons are evaluated "
                    "by the live control plane; callers cannot submit arbitrary counts."
                ),
            )
        },
        "/scale/plans": {
            "post": _op(
                "createScalePlan",
                "Preview a deterministic, cost-gated Scale Run",
                "8 · scale lab",
                _ref("ScalePlan"),
                request_schema=_ref("ScalePlanRequest"),
                success_status="201",
                success_description="Scale Plan created",
                description=(
                    "Poweruser-only planning gate. Binds a fixed profile and seed to "
                    "dataset allocations, bounded concurrency, partition count, ordered "
                    "stages, and a pre-run cost envelope. Planning does not launch work."
                ),
                extra_responses={"400": _ERR},
            )
        },
        "/scale/runs": {
            "get": _op(
                "listScaleRuns",
                "List recent Scale Runs and evidence",
                "8 · scale lab",
                _ref("ScaleRunsResponse"),
                description=(
                    "Poweruser-only sanitized projections of recent synthetic runs. "
                    "Each entry includes progress, quality, metered cost, intelligence, "
                    "governed export state, and logical audit evidence."
                ),
            ),
            "post": _op(
                "createScaleRun",
                "Launch one approved Scale Plan",
                "8 · scale lab",
                _ref("ScaleRun"),
                request_schema=_ref("ScaleLaunchRequest"),
                success_status="201",
                success_description="Scale Run launched",
                description=(
                    "Poweruser-only idempotent launch. Consumes an unexpired cost-gated "
                    "plan and returns the live run projection. The control plane permits "
                    "only one protected active rehearsal at a time."
                ),
                extra_responses={"400": _ERR},
            ),
        },
        "/scale/runs/{run_id}": {
            "get": _op(
                "getScaleRun",
                "Get live Scale Run progress and evidence",
                "8 · scale lab",
                _ref("ScaleRun"),
                parameters=[
                    {
                        "name": "run_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Run identifier returned by POST /scale/runs.",
                    }
                ],
                description=(
                    "Poweruser-only live projection. Returns logical receipts and "
                    "sanitized operational evidence without deployed resource identifiers."
                ),
                extra_responses={"404": _ERR},
            )
        },
        "/scale/runs/{run_id}/cancel": {
            "post": _op(
                "cancelScaleRun",
                "Request cooperative Scale Run cancellation",
                "8 · scale lab",
                _ref("ScaleRun"),
                request_schema=_ref("ScaleCancelRequest"),
                parameters=[
                    {
                        "name": "run_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Run identifier returned by POST /scale/runs.",
                    }
                ],
                description=(
                    "Poweruser-only cooperative cancellation. The response is the latest "
                    "run projection; callers poll GET /scale/runs/{run_id} until the "
                    "status becomes cancelled or another terminal state."
                ),
                extra_responses={"404": _ERR},
            )
        },
        "/scale/runs/{run_id}/exports": {
            "post": _op(
                "createScaleRunExport",
                "Request a governed Parquet portfolio export",
                "8 · scale lab",
                _ref("ScaleExportReceipt"),
                request_schema=_ref("ScaleExportRequest"),
                success_status="201",
                success_description="Export job accepted",
                parameters=[
                    {
                        "name": "run_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Completed run identifier.",
                    }
                ],
                description=(
                    "Poweruser-only idempotent export request for the completed curated "
                    "portfolio. The asynchronous receipt exposes an opaque logical locator "
                    "and a short-lived download URL only after the manifest is ready."
                ),
                extra_responses={"400": _ERR, "404": _ERR},
            )
        },
        "/scale/runs/{run_id}/exports/{export_id}": {
            "get": _op(
                "getScaleRunExport",
                "Poll a governed Scale Run export receipt",
                "8 · scale lab",
                _ref("ScaleExportReceipt"),
                parameters=[
                    {
                        "name": "run_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Completed run identifier.",
                    },
                    {
                        "name": "export_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Export identifier returned by the export request.",
                    },
                ],
                description=(
                    "Poweruser-only asynchronous status projection. Ready receipts include "
                    "row and byte counts, checksum, expiration, logical object locator, "
                    "and a short-lived download URL."
                ),
                extra_responses={"404": _ERR},
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
        "/system/evidence": {
            "get": _op(
                "getSystemEvidence",
                "Sanitized live backend evidence for the protected System Inspector",
                "system evidence",
                _ref("SystemEvidence"),
                description=(
                    "Poweruser-only, read-only application projections. Returns policy "
                    "decisions, service health, recent workflow receipts, model-run metadata, "
                    "and allowlisted audit evidence. It excludes infrastructure identifiers, "
                    "credentials, tokens, personal data, source records, SQL, model inputs, "
                    "delivery locations, and exception details."
                ),
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
                "the runtime role. All data is synthetic. No real CUI or PII is used."
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
            {
                "name": "8 · scale lab",
                "description": "Cost-gated synthetic workload rehearsal and evidence",
            },
            {"name": "system evidence", "description": "Protected, sanitized runtime proof"},
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

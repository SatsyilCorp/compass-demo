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
API_VERSION = "1.7.0"

# Strings reused across operations.
_ERR = {"$ref": "#/components/responses/Error"}


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _json(schema: dict[str, Any], description: str = "OK") -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": schema}},
    }


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
    money = {
        "type": ["number", "null"],
        "description": "null when masked by column-level security",
    }
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
                "per_rule": {
                    "type": "string",
                    "examples": [
                        "rule_score = 100 * passed_rows / (passed_rows + failed_rows)"
                    ],
                },
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
                            "score_source": {
                                "type": "string",
                                "enum": ["stored", "recomputed"],
                            },
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
                "org_unit": {
                    "type": "string",
                    "examples": ["ONR-Corporate", "Code-30"],
                },
                "groups": {"type": "array", "items": {"type": "string"}},
            },
        },
        "CatalogEntry": {
            "type": "object",
            "required": ["id", "batch_id", "run_id", "row_count", "quality_score"],
            "properties": {
                "id": {
                    "type": "string",
                    "description": "== batch_id; the {id} for /catalog/{id}/lineage",
                },
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
                "kind": {
                    "type": "string",
                    "enum": ["source", "stage", "table", "model", "dashboard"],
                },
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
                "status": {
                    "type": "string",
                    "enum": ["queued", "running", "passed", "failed"],
                },
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
                    "enum": [
                        "ingest",
                        "quality",
                        "anomaly",
                        "export",
                        "approval",
                        "analytics",
                    ],
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
        "DemoStreamStartRequest": {
            "type": "object",
            "required": ["cadence_seconds", "stream_mode"],
            "properties": {
                "cadence_seconds": {"type": "integer", "enum": [1, 2]},
                "stream_mode": {"type": "string", "enum": ["continuous", "bounded"]},
                "total_events": {"type": "integer", "minimum": 1, "maximum": 60},
            },
        },
        "DemoStreamStopRequest": {
            "type": "object",
            "required": ["session_id"],
            "properties": {"session_id": {"type": "string"}},
        },
        "DemoStreamEvent": {
            "type": ["object", "null"],
            "properties": {
                "sequence": {"type": "integer"},
                "run_id": {"type": "string"},
                "event_id": {"type": "string"},
                "occurred_at": {"type": "string", "format": "date-time"},
                "message": {"type": "string"},
            },
        },
        "DemoStreamSession": {
            "type": "object",
            "required": ["status", "stream_mode", "cadence_seconds", "total_events", "emitted_events"],
            "properties": {
                "session_id": {"type": ["string", "null"]},
                "status": {
                    "type": "string",
                    "enum": ["idle", "running", "completed", "stopped", "failed"],
                },
                "stream_mode": {"type": "string", "enum": ["continuous", "bounded"]},
                "cadence_seconds": {"type": "integer", "enum": [1, 2]},
                "total_events": {"type": ["integer", "null"], "minimum": 0, "maximum": 60},
                "emitted_events": {"type": "integer", "minimum": 0},
                "started_at": {"type": ["string", "null"], "format": "date-time"},
                "updated_at": {"type": ["string", "null"], "format": "date-time"},
                "completed_at": {"type": ["string", "null"], "format": "date-time"},
                "execution_chunk_number": {"type": "integer", "minimum": 0},
            },
        },
        "DemoStreamSafeguards": {
            "type": "object",
            "required": [
                "operator_stop_required",
                "workflow_chunk_events",
                "raw_retention_days",
                "estimated_events_per_hour",
            ],
            "properties": {
                "operator_stop_required": {"type": "boolean"},
                "workflow_chunk_events": {"type": "integer", "minimum": 1},
                "raw_retention_days": {"type": "integer", "minimum": 1},
                "estimated_events_per_hour": {"type": "integer", "minimum": 0},
            },
        },
        "DemoStreamResponse": {
            "type": "object",
            "required": ["contract", "mode", "generated_at", "stream_kind", "session", "disclosure"],
            "properties": {
                "contract": {"type": "string", "const": "compass.demo-stream.v1"},
                "mode": {"type": "string", "const": "live"},
                "generated_at": {"type": "string", "format": "date-time"},
                "stream_kind": {"type": "string", "const": "continuous-synthetic"},
                "session": _ref("DemoStreamSession"),
                "latest_event": _ref("DemoStreamEvent"),
                "safeguards": _ref("DemoStreamSafeguards"),
                "disclosure": {"type": "string"},
            },
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
                "status": {
                    "type": "string",
                    "enum": ["queued", "running", "completed"],
                },
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
                        "properties": {
                            "period": {"type": "string"},
                            "value": {"type": "number"},
                        },
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
        "PublicEvidenceRecord": {
            "type": "object",
            "required": [
                "record_id",
                "source_id",
                "title",
                "summary",
                "source_url",
                "evidence_class",
                "model_run_id",
                "uncertainty",
                "snapshot_id",
                "record_sha256",
            ],
            "properties": {
                "record_id": {"type": "string"},
                "source_id": {"type": "string"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "source_url": {"type": "string", "format": "uri", "pattern": "^https://"},
                "evidence_class": {
                    "type": "string",
                    "enum": [
                        "observed",
                        "derived",
                        "predicted",
                        "public_observed",
                        "public_derived",
                        "public_predicted",
                    ],
                },
                "model_run_id": {"type": ["string", "null"]},
                "uncertainty": {
                    "type": ["object", "array", "string", "number", "null"],
                },
                "snapshot_id": {"type": "string"},
                "record_sha256": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
            },
            "additionalProperties": False,
        },
        "PublicIntelligenceSnapshot": {
            "type": "object",
            "required": [
                "contract",
                "snapshot_id",
                "snapshot_version",
                "generated_at",
                "as_of_at",
                "evidence_class",
                "provenance",
                "identity_scope",
                "snapshot",
                "sources",
                "models",
                "record_count",
                "records",
                "disclosure",
            ],
            "properties": {
                "contract": {
                    "type": "string",
                    "const": "compass.public-intelligence.snapshot-response.v1",
                },
                "snapshot_id": {"type": "string"},
                "snapshot_version": {"type": "integer", "const": 1},
                "generated_at": {"type": "string", "format": "date-time"},
                "as_of_at": {"type": "string", "format": "date-time"},
                "evidence_class": {"type": "string"},
                "provenance": {
                    "type": "object",
                    "required": [
                        "manifest_sha256",
                        "index_sha256",
                        "manifest_object_version",
                        "index_object_version",
                    ],
                    "properties": {
                        "manifest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "index_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "manifest_object_version": {"type": ["string", "null"]},
                        "index_object_version": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                "identity_scope": {"type": "object", "additionalProperties": {"type": "string"}},
                "snapshot": {"type": "object", "additionalProperties": True},
                "sources": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "models": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "record_count": {"type": "integer", "minimum": 0, "maximum": 5000},
                "records": {"type": "array", "items": _ref("PublicEvidenceRecord")},
                "disclosure": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "PublicExplainRequest": {
            "type": "object",
            "required": ["question"],
            "properties": {
                "question": {"type": "string", "minLength": 1, "maxLength": 1200},
                "record_ids": {
                    "type": "array",
                    "maxItems": 12,
                    "items": {"type": "string", "minLength": 1, "maxLength": 240},
                },
                "top_k": {"type": "integer", "minimum": 1, "maximum": 6, "default": 5},
            },
            "additionalProperties": False,
        },
        "PublicEvidenceCitation": {
            "type": "object",
            "required": [
                "record_id",
                "source_id",
                "title",
                "source_url",
                "evidence_class",
                "model_run_id",
                "uncertainty",
                "snapshot_id",
                "record_sha256",
                "citation_token",
            ],
            "properties": {
                "record_id": {"type": "string"},
                "source_id": {"type": "string"},
                "title": {"type": "string"},
                "source_url": {"type": "string", "format": "uri", "pattern": "^https://"},
                "evidence_class": {"type": "string"},
                "model_run_id": {"type": ["string", "null"]},
                "uncertainty": {
                    "type": ["object", "array", "string", "number", "null"],
                },
                "snapshot_id": {"type": "string"},
                "record_sha256": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "citation_token": {"type": "string", "pattern": "^\\[SRC:"},
            },
            "additionalProperties": False,
        },
        "PublicExplanation": {
            "type": "object",
            "required": [
                "contract",
                "answer",
                "grounded",
                "refused",
                "refusal_code",
                "citations",
                "evidence_class",
                "model_run_id",
                "model_run_ids",
                "explanation_run_id",
                "uncertainty",
                "generation",
                "snapshot_id",
                "identity_scope",
            ],
            "properties": {
                "contract": {
                    "type": "string",
                    "const": "compass.public-intelligence.explanation.v1",
                },
                "answer": {"type": "string"},
                "grounded": {"type": "boolean"},
                "refused": {"type": "boolean"},
                "refusal_code": {
                    "type": ["string", "null"],
                    "enum": ["INSUFFICIENT_CITABLE_EVIDENCE", None],
                },
                "citations": {"type": "array", "items": _ref("PublicEvidenceCitation")},
                "evidence_class": {"type": "string"},
                "model_run_id": {"type": ["string", "null"]},
                "model_run_ids": {"type": "array", "items": {"type": "string"}},
                "explanation_run_id": {"type": "string"},
                "uncertainty": {"type": "object", "additionalProperties": True},
                "generation": {
                    "type": "object",
                    "required": ["provider", "model_id", "usage"],
                    "properties": {
                        "provider": {
                            "type": "string",
                            "enum": ["amazon-bedrock", "deterministic", "none"],
                        },
                        "model_id": {"type": ["string", "null"]},
                        "usage": {"type": ["object", "null"], "additionalProperties": True},
                    },
                    "additionalProperties": False,
                },
                "snapshot_id": {"type": "string"},
                "identity_scope": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        "PublicModelExecutionRequest": {
            "type": "object",
            "properties": {
                "sampleSize": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "default": 8,
                }
            },
            "additionalProperties": False,
        },
        "PublicModelExecutionPrediction": {
            "type": "object",
            "required": [
                "recordId",
                "observedPublicTransitionProbability",
                "candidateLabel",
                "semantics",
                "humanReviewRequired",
            ],
            "properties": {
                "recordId": {"type": "string"},
                "observedPublicTransitionProbability": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
                "candidateLabel": {"type": "integer", "enum": [0, 1]},
                "semantics": {"type": "string"},
                "humanReviewRequired": {"type": "boolean", "const": True},
            },
            "additionalProperties": False,
        },
        "PublicModelExecutionReceipt": {
            "type": "object",
            "required": [
                "contract",
                "version",
                "executionId",
                "status",
                "createdAt",
                "updatedAt",
                "completedAt",
                "purpose",
                "executionMode",
                "model",
                "input",
                "execution",
                "output",
                "cost",
                "provenance",
                "humanReviewRequired",
                "disclosure",
            ],
            "properties": {
                "contract": {
                    "type": "string",
                    "const": "compass.public-intelligence.model-execution.v1",
                },
                "version": {"type": "integer", "const": 1},
                "executionId": {
                    "type": "string",
                    "pattern": "^sbir-batch-[0-9]{8}T[0-9]{6}-[a-f0-9]{8}$",
                },
                "status": {
                    "type": "string",
                    "enum": ["SUBMITTED", "IN_PROGRESS", "COMPLETED", "FAILED", "STOPPED"],
                },
                "createdAt": {"type": "string", "format": "date-time"},
                "updatedAt": {"type": "string", "format": "date-time"},
                "completedAt": {"type": ["string", "null"], "format": "date-time"},
                "purpose": {
                    "type": "string",
                    "enum": [
                        "current_public_cohort_scoring",
                        "training_cohort_smoke_scoring",
                        "bounded_public_validation",
                    ],
                    "description": (
                        "Current public post-cutoff cohort scoring. Earlier values are retained "
                        "only for compatibility with prior hash-bound execution receipts."
                    ),
                },
                "executionMode": {"type": "string", "const": "sagemaker_batch_transform"},
                "model": {
                    "type": "object",
                    "required": [
                        "name",
                        "packageArn",
                        "packageVersion",
                        "approvalStatus",
                        "candidateOnly",
                        "trainingJobArn",
                        "modelArtifactSha256",
                        "modelCardSha256",
                        "imageDigest",
                    ],
                    "properties": {
                        "name": {"type": "string"},
                        "packageArn": {"type": "string"},
                        "packageVersion": {"type": "integer", "minimum": 1},
                        "approvalStatus": {"type": "string", "const": "PendingManualApproval"},
                        "candidateOnly": {"type": "boolean", "const": True},
                        "trainingJobArn": {"type": "string"},
                        "modelArtifactSha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "modelBundleSha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "modelArtifactSourceVersionId": {"type": "string"},
                        "modelCardSha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "imageDigest": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"},
                    },
                    "additionalProperties": False,
                },
                "input": {
                    "type": "object",
                    "required": ["recordCount", "sha256", "records"],
                    "properties": {
                        "recordCount": {"type": "integer", "minimum": 1, "maximum": 25},
                        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "records": {
                            "type": "array",
                            "maxItems": 25,
                            "items": {
                                "type": "object",
                                "required": ["recordId", "eventTime", "sourceRecordIds"],
                                "properties": {
                                    "recordId": {"type": "string"},
                                    "eventTime": {"type": "string", "format": "date-time"},
                                    "sourceRecordIds": {
                                        "type": "array",
                                        "maxItems": 10,
                                        "items": {"type": "string"},
                                    },
                                },
                                "additionalProperties": False,
                            },
                        },
                    },
                    "additionalProperties": False,
                },
                "execution": {
                    "type": "object",
                    "required": [
                        "transformJobArn",
                        "transformJobName",
                        "instanceType",
                        "instanceCount",
                        "networkIsolation",
                        "maxRuntimeSeconds",
                        "temporaryModelName",
                        "temporaryModelCleanupStatus",
                    ],
                    "properties": {
                        "transformJobArn": {"type": ["string", "null"]},
                        "transformJobName": {"type": "string"},
                        "instanceType": {"type": "string", "const": "ml.m5.large"},
                        "instanceCount": {"type": "integer", "const": 1},
                        "networkIsolation": {"type": "boolean", "const": True},
                        "maxRuntimeSeconds": {"type": "integer", "maximum": 1800},
                        "temporaryModelName": {"type": "string"},
                        "temporaryModelCleanupStatus": {
                            "type": "string",
                            "enum": ["PENDING", "DELETED", "DELETE_PENDING", "REFUSED_INVALID_NAME"],
                        },
                        "reconciliationSchedule": {"type": ["string", "null"]},
                        "stopRequestedAt": {"type": "string", "format": "date-time"},
                        "stopReason": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "output": {
                    "oneOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "required": ["predictionCount", "sha256", "predictions"],
                            "properties": {
                                "predictionCount": {"type": "integer", "minimum": 1, "maximum": 25},
                                "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                                "predictions": {
                                    "type": "array",
                                    "maxItems": 25,
                                    "items": _ref("PublicModelExecutionPrediction"),
                                },
                            },
                            "additionalProperties": False,
                        },
                    ]
                },
                "cost": {
                    "oneOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "required": [
                                "observedDurationSeconds",
                                "estimatedComputeUsd",
                                "estimateOnly",
                                "basis",
                            ],
                            "properties": {
                                "observedDurationSeconds": {"type": ["integer", "null"], "minimum": 0},
                                "estimatedComputeUsd": {"type": ["number", "null"], "minimum": 0},
                                "estimateOnly": {"type": "boolean", "const": True},
                                "basis": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    ]
                },
                "provenance": {
                    "type": "object",
                    "required": [
                        "requestId",
                        "actorRole",
                        "candidatePoolSha256",
                        "candidatePoolVersionId",
                        "sourceDataset",
                        "inputVersionId",
                        "outputVersionId",
                        "receiptSha256",
                        "receiptVersionId",
                    ],
                    "properties": {
                        "requestId": {"type": "string"},
                        "actorRole": {"type": "string", "const": "poweruser"},
                        "candidatePoolSha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "candidatePoolVersionId": {"type": ["string", "null"]},
                        "sourceDataset": {"type": "object", "additionalProperties": True},
                        "inputVersionId": {"type": ["string", "null"]},
                        "executionModelVersionId": {"type": ["string", "null"]},
                        "outputVersionId": {"type": ["string", "null"]},
                        "receiptSha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "receiptVersionId": {"type": ["string", "null"]},
                    },
                    "additionalProperties": False,
                },
                "failure": {
                    "type": "object",
                    "required": ["code", "message"],
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "humanReviewRequired": {"type": "boolean", "const": True},
                "disclosure": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "PublicModelExecutionList": {
            "type": "object",
            "required": ["contract", "executions"],
            "properties": {
                "contract": {
                    "type": "string",
                    "const": "compass.public-intelligence.model-execution-list.v1",
                },
                "executions": {
                    "type": "array",
                    "maxItems": 10,
                    "items": _ref("PublicModelExecutionReceipt"),
                },
            },
            "additionalProperties": False,
        },
        "PublicAcquisition": {
            "type": "object",
            "required": ["contract", "run_id", "source_id", "status", "stage", "started_at", "updated_at"],
            "properties": {
                "contract": {"type": "string", "const": "compass.public-acquisition.v1"},
                "run_id": {"type": "string"},
                "source_id": {"type": "string", "const": "usaspending-onr-grants"},
                "status": {"type": "string", "enum": ["completed", "failed", "running"]},
                "stage": {"type": "string"},
                "started_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
                "watermark": {"type": ["string", "null"]},
                "snapshot_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "source_response_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "canonical_object_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "record_count": {"type": "integer", "minimum": 0},
                "added_records": {"type": "integer", "minimum": 0},
                "changed_records": {"type": "integer", "minimum": 0},
                "unchanged_records": {"type": "integer", "minimum": 0},
                "not_observed_records": {"type": "integer", "minimum": 0},
                "poll_mode": {"type": "string", "const": "scheduled-micro-batch"},
                "scope_disclosure": {"type": "string"},
                "failure_code": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "PublicAcquisitionList": {
            "type": "object",
            "required": ["contract", "mode", "generated_at", "schedule", "source_transport", "acquisitions"],
            "properties": {
                "contract": {"type": "string", "const": "compass.public-acquisition-list.v1"},
                "mode": {"type": "string", "const": "live"},
                "generated_at": {"type": "string", "format": "date-time"},
                "schedule": {"type": "string", "const": "rate(5 minutes)"},
                "source_transport": {"type": "string"},
                "acquisitions": {"type": "array", "maxItems": 50, "items": _ref("PublicAcquisition")},
            },
            "additionalProperties": False,
        },
        "OperationalSignal": {
            "type": "object",
            "required": ["contract", "event_id", "category", "severity", "title", "message", "status"],
            "properties": {
                "contract": {"type": "string", "const": "compass.operational-signal.v1"},
                "event_id": {"type": "string"},
                "category": {"type": "string"},
                "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
                "title": {"type": "string"},
                "message": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "acknowledged"]},
                "run_id": {"type": ["string", "null"]},
                "evidence_uri": {"type": ["string", "null"]},
                "receipt_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "delivery": {"type": "object", "additionalProperties": True},
            },
            "additionalProperties": True,
        },
        "OperationalSignals": {
            "type": "object",
            "required": ["contract", "mode", "generated_at", "signals", "unacknowledged"],
            "properties": {
                "contract": {"type": "string", "const": "compass.operational-signals.v1"},
                "mode": {"type": "string", "const": "live"},
                "generated_at": {"type": "string", "format": "date-time"},
                "signals": {"type": "array", "maxItems": 100, "items": _ref("OperationalSignal")},
                "unacknowledged": {"type": "integer", "minimum": 0},
                "delivery_disclosure": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "OperationalLineage": {
            "type": "object",
            "required": ["contract", "mode", "run_id", "run_kind", "status", "stages", "edges", "generated_at"],
            "properties": {
                "contract": {"type": "string", "const": "compass.operational-lineage.v1"},
                "mode": {"type": "string", "const": "live"},
                "run_id": {"type": "string"},
                "run_kind": {"type": "string"},
                "status": {"type": "string"},
                "source": {"type": ["string", "null"]},
                "source_sha256": {"type": ["string", "null"], "pattern": "^[a-f0-9]{64}$"},
                "model": {"type": ["string", "null"]},
                "consumer": {"type": ["string", "null"]},
                "stages": {"type": "array", "maxItems": 100, "items": {"type": "object", "additionalProperties": True}},
                "edges": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "generated_at": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": False,
        },
        "OperationalLineageList": {
            "type": "object",
            "required": ["contract", "mode", "generated_at", "runs"],
            "properties": {
                "contract": {"type": "string", "const": "compass.operational-lineage-list.v1"},
                "mode": {"type": "string", "const": "live"},
                "generated_at": {"type": "string", "format": "date-time"},
                "runs": {"type": "array", "maxItems": 100, "items": {"type": "object", "additionalProperties": True}},
            },
            "additionalProperties": False,
        },
        "OperationalSummary": {
            "type": "object",
            "required": ["contract", "mode", "generated_at", "counts", "runs", "proof", "disclosure"],
            "properties": {
                "contract": {"type": "string", "const": "compass.operational-summary.v1"},
                "mode": {"type": "string", "const": "live"},
                "generated_at": {"type": "string", "format": "date-time"},
                "counts": {"type": "object", "additionalProperties": {"type": "integer"}},
                "runs": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "latest_public_acquisition": {"oneOf": [_ref("PublicAcquisition"), {"type": "null"}]},
                "latest_public_acquisition_attempt": {"oneOf": [_ref("PublicAcquisition"), {"type": "null"}]},
                "proof": {"type": "object", "additionalProperties": {"type": "string"}},
                "disclosure": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "Anomaly": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "grant_id": {"type": ["integer", "null"]},
                "grant_no": {"type": ["string", "null"]},
                "kind": {"type": "string"},
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },
                "reason": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["open", "acknowledged", "resolved"],
                },
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
                "state": {
                    "type": "string",
                    "enum": ["pending", "approved", "rejected"],
                },
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
                "status": {
                    "type": "string",
                    "enum": ["active", "expiring", "expired", "suspended"],
                },
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
                "alerts": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
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
                        "q": {
                            "type": "string",
                            "description": "substring match on title/abstract",
                        },
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
                "row_count": {
                    "type": "integer",
                    "description": "rows actually written",
                },
                "matched_rows": {
                    "type": "integer",
                    "description": "rows the filter selected under RLS",
                },
                "format": {"type": "string", "enum": ["csv", "json", "parquet"]},
                "requested_format": {
                    "type": "string",
                    "enum": ["csv", "json", "parquet"],
                },
                "download_url": {"type": "string"},
                "delivery": {
                    "type": "string",
                    "enum": ["s3-presigned", "inline-data-uri"],
                },
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
                "subject_id": {
                    "type": "string",
                    "description": "POST this to /approvals to request clearance",
                },
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
        "DocumentTaxonomy": {
            "type": "string",
            "enum": [
                "grant_abstract",
                "technical_report",
                "publication_summary",
                "patent_summary",
                "investment_brief",
                "financial_execution",
            ],
        },
        "DocumentUploadRequest": {
            "type": "object",
            "required": [
                "filename",
                "content_type",
                "size_bytes",
                "source_sha256",
                "synthetic_only",
                "data_classification",
                "contains_cui",
                "pii_minimized",
            ],
            "properties": {
                "filename": {"type": "string", "minLength": 1, "maxLength": 120},
                "content_type": {"type": "string"},
                "size_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 15728640,
                },
                "source_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "synthetic_only": {"type": "boolean", "default": True},
                "data_classification": {
                    "type": "string",
                    "enum": ["synthetic-demo", "public"],
                },
                "contains_cui": {"type": "boolean", "const": False},
                "pii_minimized": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "DocumentUploadResponse": {
            "type": "object",
            "required": [
                "run_id",
                "status",
                "stage",
                "filename",
                "content_type",
                "expected_bytes",
                "source",
                "upload",
            ],
            "properties": {
                "run_id": {"type": "string"},
                "document_id": {"type": "string"},
                "status": {"type": "string", "const": "awaiting-upload"},
                "stage": {"type": "string", "const": "browser-upload"},
                "filename": {"type": "string"},
                "content_type": {"type": "string"},
                "expected_bytes": {"type": "integer"},
                "org_unit": {"type": "string"},
                "requested_by": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
                "source": {"type": "string", "pattern": "^document-lake://"},
                "synthetic_only": {"type": "boolean"},
                "data_boundary": {
                    "type": "object",
                    "required": ["classification", "contains_cui", "pii_minimized"],
                    "properties": {
                        "classification": {
                            "type": "string",
                            "enum": ["synthetic-demo", "public"],
                        },
                        "contains_cui": {"type": "boolean", "const": False},
                        "pii_minimized": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "upload": {
                    "type": "object",
                    "required": [
                        "method",
                        "url",
                        "fields",
                        "expires_in_seconds",
                        "maximum_bytes",
                    ],
                    "properties": {
                        "method": {"type": "string", "const": "POST"},
                        "url": {"type": "string", "format": "uri"},
                        "fields": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "expires_in_seconds": {"type": "integer", "const": 900},
                        "maximum_bytes": {"type": "integer", "const": 15728640},
                    },
                    "additionalProperties": False,
                },
                "next": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "DocumentRun": {
            "type": "object",
            "required": ["run_id", "status", "stage"],
            "properties": {
                "run_id": {"type": "string"},
                "document_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["awaiting-upload", "running", "completed", "quarantined"],
                },
                "stage": {"type": "string"},
                "filename": {"type": "string"},
                "content_type": {"type": "string"},
                "bytes": {"type": "integer"},
                "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "document_class": _ref("DocumentTaxonomy"),
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "review_required": {"type": "boolean"},
                "model_version": {"type": "string"},
                "quality": {"type": "object", "additionalProperties": True},
                "lineage": {"type": "array", "items": {"type": "string"}},
                "reason": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
                "completed_at": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": True,
        },
        "DocumentRunsResponse": {
            "type": "object",
            "required": ["runs"],
            "properties": {
                "runs": {"type": "array", "items": _ref("DocumentRun")},
            },
            "additionalProperties": False,
        },
        "DocumentTrainingRecord": {
            "type": "object",
            "required": ["text", "label"],
            "properties": {
                "sample_id": {"type": "string"},
                "text": {"type": "string", "minLength": 20},
                "label": _ref("DocumentTaxonomy"),
            },
            "additionalProperties": False,
        },
        "DocumentTrainingRequest": {
            "type": "object",
            "properties": {
                "training_records": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 500,
                    "items": _ref("DocumentTrainingRecord"),
                }
            },
            "additionalProperties": False,
        },
        "DocumentModel": {
            "type": "object",
            "required": ["model_version", "status", "algorithm", "labels", "metrics"],
            "properties": {
                "model_version": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": [
                        "registered",
                        "training",
                        "configuration-required",
                        "approved",
                        "deployed",
                    ],
                },
                "algorithm": {"type": "string"},
                "labels": {"type": "array", "items": _ref("DocumentTaxonomy")},
                "metrics": {"type": "object", "additionalProperties": True},
                "artifact_uri": {"type": "string", "pattern": "^document-lake://"},
                "training_data_uri": {
                    "type": "string",
                    "pattern": "^document-lake://",
                },
                "training_digest": {"type": "string"},
                "adapter": {"type": "object", "additionalProperties": True},
                "synthetic_only": {"type": "boolean"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": True,
        },
        "DocumentModelsResponse": {
            "type": "object",
            "required": ["models", "champion"],
            "properties": {
                "models": {"type": "array", "items": _ref("DocumentModel")},
                "champion": {"type": ["object", "null"], "additionalProperties": True},
            },
            "additionalProperties": False,
        },
        "DocumentDeployment": {
            "type": "object",
            "required": [
                "deployment_id",
                "model_version",
                "alias",
                "status",
                "target",
            ],
            "properties": {
                "deployment_id": {"type": "string"},
                "model_version": {"type": "string"},
                "alias": {"type": "string", "const": "champion"},
                "status": {"type": "string", "const": "active"},
                "target": {"type": "object", "additionalProperties": True},
                "deployed_by": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": False,
        },
        "DocumentDriftRequest": {
            "type": "object",
            "properties": {
                "documents": {
                    "type": "array",
                    "minItems": 5,
                    "maxItems": 200,
                    "items": {"type": "string", "minLength": 20},
                },
                "threshold": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "additionalProperties": False,
        },
        "DocumentDriftReceipt": {
            "type": "object",
            "required": [
                "drift_id",
                "model_version",
                "drift_detected",
                "drift_score",
                "receipt_uri",
            ],
            "properties": {
                "drift_id": {"type": "string"},
                "model_version": {"type": "string"},
                "threshold": {"type": "number"},
                "population_stability_index": {"type": "number"},
                "out_of_vocabulary_rate": {"type": "number"},
                "drift_score": {"type": "number"},
                "drift_detected": {"type": "boolean"},
                "recommended_action": {"type": "string"},
                "receipt_uri": {"type": "string", "pattern": "^document-lake://"},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": True,
        },
        "DocumentMlOpsEvidence": {
            "type": "object",
            "required": [
                "mode",
                "truthfulness",
                "champion",
                "models",
                "deployments",
                "drift_receipts",
                "architecture",
            ],
            "properties": {
                "mode": {"type": "string", "enum": ["demo", "sagemaker"]},
                "truthfulness": {"type": "string"},
                "champion": {"type": ["object", "null"], "additionalProperties": True},
                "models": {"type": "array", "items": _ref("DocumentModel")},
                "deployments": {
                    "type": "array",
                    "items": _ref("DocumentDeployment"),
                },
                "drift_receipts": {
                    "type": "array",
                    "items": _ref("DocumentDriftReceipt"),
                },
                "architecture": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
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
                "health": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "metrics": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                },
                "services": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
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
                    "items": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "disclosure": {"type": "string"},
            },
        },
    }


def build_openapi(server_url: str = "") -> dict[str, Any]:
    """Return the OpenAPI 3.1 document, optionally bound to a concrete server."""
    servers = (
        [{"url": server_url, "description": "This deployment"}] if server_url else []
    )

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
        "/demo-stream": {
            "get": _op(
                "getDemoStream",
                "Read the operator-controlled continuous stream session",
                "3 · ingest",
                _ref("DemoStreamResponse"),
                description=(
                    "Reads the current synthetic demo-stream receipt. The stream is "
                    "separate from official public-source acquisition cadence."
                ),
            )
        },
        "/demo-stream/start": {
            "post": _op(
                "startDemoStream",
                "Start an operator-controlled continuous synthetic stream",
                "3 · ingest",
                _ref("DemoStreamResponse"),
                request_schema=_ref("DemoStreamStartRequest"),
                success_status="202",
                success_description="Accepted",
                description=(
                    "Starts synthetic S3 drops at a one-second or two-second cadence and "
                    "continues until an operator calls Stop. Every drop follows the deployed "
                    "EventBridge and Step Functions intake path. Bounded mode remains available "
                    "for automated smoke tests."
                ),
            )
        },
        "/demo-stream/stop": {
            "post": _op(
                "stopDemoStream",
                "Stop the current continuous synthetic stream",
                "3 · ingest",
                _ref("DemoStreamResponse"),
                request_schema=_ref("DemoStreamStopRequest"),
                extra_responses={"404": _ERR},
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
                    {
                        "name": "runId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
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
                    {
                        "name": "program_area",
                        "in": "query",
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "fiscal_year",
                        "in": "query",
                        "schema": {"type": "integer"},
                    },
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
        "/public-intelligence/snapshot": {
            "get": _op(
                "getPublicIntelligenceSnapshot",
                "Verified public ONR-related evidence snapshot",
                "9 · public intelligence",
                _ref("PublicIntelligenceSnapshot"),
                description=(
                    "Reads a PII-minimized public-evidence index only after its versioned "
                    "S3 manifest, boundary declaration, source URLs, and SHA-256 digest "
                    "validate. It is isolated from the synthetic portfolio database."
                ),
                extra_responses={"503": _ERR},
            )
        },
        "/public-intelligence/explain": {
            "post": _op(
                "explainPublicIntelligence",
                "Cited explanation from verified public evidence",
                "9 · public intelligence",
                _ref("PublicExplanation"),
                request_schema=_ref("PublicExplainRequest"),
                description=(
                    "Runs bounded retrieval over the verified public index and makes at "
                    "most one 500-token Bedrock call. Every returned citation contains "
                    "a record identifier and HTTPS source URL. No supporting record "
                    "produces an explicit refusal without a model call."
                ),
                extra_responses={"400": _ERR, "503": _ERR},
            )
        },
        "/public-intelligence/model-executions": {
            "get": _op(
                "listPublicModelExecutions",
                "List recent durable public-model execution receipts",
                "9 · public intelligence",
                _ref("PublicModelExecutionList"),
                description=(
                    "Returns at most ten newest KMS-encrypted execution receipts. "
                    "The route can resume polling after a browser refresh without "
                    "starting compute."
                ),
                extra_responses={"503": _ERR},
            ),
            "post": _op(
                "startPublicModelExecution",
                "Start one bounded SageMaker public-model smoke run",
                "9 · public intelligence",
                _ref("PublicModelExecutionReceipt"),
                request_schema=_ref("PublicModelExecutionRequest"),
                success_status="202",
                success_description="Submitted",
                description=(
                    "Power-user-only submission of one ephemeral Batch Transform job "
                    "for 1 to 25 PII-minimized public Navy SBIR records. The model stays "
                    "PendingManualApproval, no endpoint is created, and receipts are "
                    "digest-bound."
                ),
                extra_responses={"400": _ERR, "409": _ERR, "503": _ERR},
            ),
        },
        "/public-intelligence/model-executions/{executionId}": {
            "get": _op(
                "getPublicModelExecution",
                "Read and reconcile one public-model execution receipt",
                "9 · public intelligence",
                _ref("PublicModelExecutionReceipt"),
                parameters=[
                    {
                        "name": "executionId",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "pattern": "^sbir-batch-[0-9]{8}T[0-9]{6}-[a-f0-9]{8}$",
                        },
                    }
                ],
                description=(
                    "Reads the durable receipt and reconciles it against the bounded "
                    "SageMaker Batch Transform job. Terminal reconciliation records "
                    "output digest, prediction count, observed duration, estimated cost, "
                    "and temporary-model cleanup."
                ),
                extra_responses={"404": _ERR, "503": _ERR},
            )
        },
        "/public-intelligence/acquisitions": {
            "get": _op(
                "listPublicAcquisitions",
                "List scheduled USAspending acquisition and change receipts",
                "9 · public intelligence",
                _ref("PublicAcquisitionList"),
                description=(
                    "Returns bounded public-source micro-batch receipts, accepted "
                    "watermarks, immutable snapshot digests, and hash-derived changes."
                ),
            )
        },
        "/public-intelligence/acquisitions/run": {
            "post": _op(
                "runPublicAcquisition",
                "Run one bounded USAspending public-source poll",
                "9 · public intelligence",
                _ref("PublicAcquisition"),
                request_schema={"type": "object", "maxProperties": 0},
                success_status="201",
                success_description="Accepted snapshot",
                description=(
                    "Corporate poweruser control for the same bounded acquisition used "
                    "by the five-minute schedule. A failure leaves the prior accepted "
                    "snapshot active."
                ),
                extra_responses={"502": _ERR},
            )
        },
        "/operations/signals": {
            "get": _op(
                "listOperationalSignals",
                "Read safe operational signals and delivery evidence",
                "10 · operations evidence",
                _ref("OperationalSignals"),
                description="Corporate poweruser-only in-app and encrypted SNS signal projection.",
            )
        },
        "/operations/signals/{eventId}/acknowledge": {
            "post": _op(
                "acknowledgeOperationalSignal",
                "Acknowledge one retained operational signal",
                "10 · operations evidence",
                _ref("OperationalSignal"),
                request_schema={"type": "object", "maxProperties": 0},
                parameters=[
                    {
                        "name": "eventId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "pattern": "^sig-[A-Za-z0-9._:-]+$"},
                    }
                ],
                description="Records actor and acknowledgement time without deleting the signal.",
                extra_responses={"404": _ERR},
            )
        },
        "/operations/lineage": {
            "get": _op(
                "listOperationalLineage",
                "List recent cross-workflow run projections",
                "10 · operations evidence",
                _ref("OperationalLineageList"),
            )
        },
        "/operations/lineage/{runId}": {
            "get": _op(
                "getOperationalLineage",
                "Read ordered stage receipts for one run",
                "10 · operations evidence",
                _ref("OperationalLineage"),
                parameters=[
                    {
                        "name": "runId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "maxLength": 180},
                    }
                ],
                description=(
                    "Returns logical locators, counts, hashes, model version, consumer, "
                    "actor, and receipt timestamps. Raw records and physical cloud "
                    "identifiers are excluded."
                ),
                extra_responses={"404": _ERR},
            )
        },
        "/operations/summary": {
            "get": _op(
                "getOperationalSummary",
                "Read the current cross-workflow operational scorecard",
                "10 · operations evidence",
                _ref("OperationalSummary"),
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
                        "schema": {
                            "type": "string",
                            "enum": ["open", "acknowledged", "resolved", "all"],
                        },
                    },
                    {
                        "name": "severity",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                        },
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "maximum": 500},
                    },
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
                extra_responses={
                    "201": _json(_ref("ApprovalResponse"), "Approval requested"),
                    "404": _ERR,
                },
            ),
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
                    "428": _json(
                        _ref("ApprovalRequired"),
                        "Aggregation guard tripped: approval required",
                    ),
                },
            )
        },
        "/documents/uploads": {
            "post": _op(
                "requestDocumentUpload",
                "Request a bounded browser upload for a document",
                "3 · document intake",
                _ref("DocumentUploadResponse"),
                request_schema=_ref("DocumentUploadRequest"),
                success_status="201",
                success_description="Upload slot created",
                description=(
                    "Corporate poweruser-only request for a 15-minute presigned PUT. "
                    "The accepted S3 object starts inspect, quality, quarantine or "
                    "curation through EventBridge and Step Functions."
                ),
                extra_responses={"400": _ERR},
            )
        },
        "/documents/runs": {
            "get": _op(
                "listDocumentRuns",
                "List document intake runs visible to the caller",
                "3 · document intake",
                _ref("DocumentRunsResponse"),
                description=(
                    "Returns the sanitized bronze, quality, silver, gold, or "
                    "quarantine status for recent browser document drops."
                ),
            )
        },
        "/documents/runs/{run_id}": {
            "get": _op(
                "getDocumentRun",
                "Get one document run and its lineage receipt",
                "3 · document intake",
                _ref("DocumentRun"),
                parameters=[
                    {
                        "name": "runId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                extra_responses={"404": _ERR},
            )
        },
        "/ml/train": {
            "post": _op(
                "trainDocumentClassifier",
                "Train and evaluate the shared document classifier",
                "5 · MLOps",
                _ref("DocumentModel"),
                request_schema=_ref("DocumentTrainingRequest"),
                success_status="201",
                success_description="Model trained and registered",
                description=(
                    "Corporate poweruser-only deterministic train and holdout evaluation. "
                    "SageMaker mode can return 202 after a bounded training job is "
                    "actually submitted; demo mode never claims that cloud job."
                ),
                extra_responses={
                    "202": _json(_ref("DocumentModel"), "SageMaker job submitted"),
                    "400": _ERR,
                },
            )
        },
        "/ml/models": {
            "get": _op(
                "listDocumentModels",
                "List classifier versions and the champion alias",
                "5 · MLOps",
                _ref("DocumentModelsResponse"),
            )
        },
        "/ml/models/{version}/deploy": {
            "post": _op(
                "deployDocumentModel",
                "Promote one model version to champion",
                "5 · MLOps",
                _ref("DocumentDeployment"),
                success_status="201",
                success_description="Champion promoted",
                parameters=[
                    {
                        "name": "version",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                description=(
                    "Corporate poweruser-only promotion with an immutable deployment "
                    "receipt. SageMaker mode requires an approved registered package."
                ),
                extra_responses={"404": _ERR, "409": _ERR},
            )
        },
        "/ml/drift/evaluate": {
            "post": _op(
                "evaluateDocumentModelDrift",
                "Evaluate champion label and vocabulary drift",
                "5 · MLOps",
                _ref("DocumentDriftReceipt"),
                request_schema=_ref("DocumentDriftRequest"),
                success_status="201",
                success_description="Drift receipt created",
                description=(
                    "Corporate poweruser-only population stability and vocabulary drift "
                    "check against supplied text or recent curated documents."
                ),
                extra_responses={"400": _ERR, "409": _ERR},
            )
        },
        "/ml/ops/evidence": {
            "get": _op(
                "getDocumentMlOpsEvidence",
                "Get model, deployment, and drift evidence",
                "5 · MLOps",
                _ref("DocumentMlOpsEvidence"),
                description=(
                    "Sanitized evidence separates locally completed deterministic work "
                    "from actual SageMaker submissions and deployment targets."
                ),
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
                        "name": "runId",
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
                        "name": "runId",
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
                        "name": "runId",
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
                        "name": "runId",
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
            "summary": "Governed portfolio intelligence over synthetic and public evidence planes.",
            "description": (
                "Every route is behind a Cognito JWT authorizer (deny-by-default). "
                "Data access is governed in PostgreSQL, not in application code: "
                "row-level security keys on `compass.org_unit`, set per transaction from "
                "the caller's claim, and column-level security revokes `amount_usd` from "
                "the runtime role. The core portfolio uses synthetic data. Separate public "
                "intelligence routes serve checksummed, PII-minimized public evidence only. "
                "No CUI is accepted by either plane."
            ),
            "contact": {"name": "Compass demo"},
            "license": {
                "name": "Demonstration use only",
                "identifier": "LicenseRef-demo",
            },
        },
        "servers": servers,
        "tags": [
            {
                "name": "1 · identity",
                "description": "Who is calling, and with what entitlements",
            },
            {
                "name": "3 · ingest",
                "description": "File drop, quality gate, live ticker",
            },
            {"name": "4 · catalog", "description": "Datasets, quality scores, lineage"},
            {
                "name": "5 · analytics",
                "description": "Topic model over curated abstracts",
            },
            {
                "name": "6 · dashboard",
                "description": "KPIs, chat, anomalies, approvals, licenses",
            },
            {
                "name": "7 · export",
                "description": "Governed export and the served contract",
            },
            {
                "name": "8 · scale lab",
                "description": "Cost-gated synthetic workload rehearsal and evidence",
            },
            {
                "name": "9 · public intelligence",
                "description": "Verified public evidence and cited explanations",
            },
            {
                "name": "system evidence",
                "description": "Protected, sanitized runtime proof",
            },
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

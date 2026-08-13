"""Keep the served API contract synchronized with the deployed HTTP routes."""

from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "functions" / "export"))

build_openapi = importlib.import_module("openapi").build_openapi


def template_routes() -> set[tuple[str, str]]:
    source = (ROOT / "template.yaml").read_text(encoding="utf-8")
    return {
        (method.lower(), path)
        for method, path in re.findall(
            r"Method:\s*(GET|POST)\s+Path:\s*([^\s#]+)",
            source,
        )
    }


def openapi_routes() -> set[tuple[str, str]]:
    paths = build_openapi()["paths"]
    return {
        (method.lower(), path)
        for path, operations in paths.items()
        for method in operations
        if method.lower() in {"get", "post"}
    }


def test_openapi_matches_every_deployed_application_route():
    deployed = template_routes()
    served = openapi_routes()
    assert len(deployed) == 48
    assert served == deployed


def test_every_operation_is_jwt_protected_in_the_served_contract():
    document = build_openapi()
    for path, operations in document["paths"].items():
        for method, operation in operations.items():
            if method.lower() not in {"get", "post"}:
                continue
            assert operation["security"] == [{"cognitoJwt": []}], (method, path)


def test_scale_lab_operations_publish_exact_success_and_request_schemas():
    document = build_openapi()
    expected = {
        ("get", "/scale/profiles"): ("200", "ScaleProfilesResponse", None),
        ("post", "/scale/plans"): ("201", "ScalePlan", "ScalePlanRequest"),
        ("get", "/scale/runs"): ("200", "ScaleRunsResponse", None),
        ("post", "/scale/runs"): ("201", "ScaleRun", "ScaleLaunchRequest"),
        ("get", "/scale/runs/{run_id}"): ("200", "ScaleRun", None),
        ("post", "/scale/runs/{run_id}/cancel"): (
            "200",
            "ScaleRun",
            "ScaleCancelRequest",
        ),
        ("post", "/scale/runs/{run_id}/exports"): (
            "201",
            "ScaleExportReceipt",
            "ScaleExportRequest",
        ),
        ("get", "/scale/runs/{run_id}/exports/{export_id}"): (
            "200",
            "ScaleExportReceipt",
            None,
        ),
    }

    for (method, path), (status, response_name, request_name) in expected.items():
        operation = document["paths"][path][method]
        success_codes = set(operation["responses"]) & {"200", "201"}
        assert success_codes == {status}, (method, path)
        response_schema = operation["responses"][status]["content"]["application/json"][
            "schema"
        ]
        assert response_schema == {"$ref": f"#/components/schemas/{response_name}"}
        if request_name is None:
            assert "requestBody" not in operation
        else:
            request_schema = operation["requestBody"]["content"]["application/json"][
                "schema"
            ]
            assert request_schema == {"$ref": f"#/components/schemas/{request_name}"}


def test_document_ml_operations_publish_success_and_request_schemas():
    document = build_openapi()
    expected = {
        ("post", "/documents/uploads"): (
            "201",
            "DocumentUploadResponse",
            "DocumentUploadRequest",
        ),
        ("get", "/documents/runs"): ("200", "DocumentRunsResponse", None),
        ("get", "/documents/runs/{run_id}"): ("200", "DocumentRun", None),
        ("post", "/ml/train"): (
            "201",
            "DocumentModel",
            "DocumentTrainingRequest",
        ),
        ("get", "/ml/models"): ("200", "DocumentModelsResponse", None),
        ("post", "/ml/models/{version}/deploy"): (
            "201",
            "DocumentDeployment",
            None,
        ),
        ("post", "/ml/drift/evaluate"): (
            "201",
            "DocumentDriftReceipt",
            "DocumentDriftRequest",
        ),
        ("get", "/ml/ops/evidence"): (
            "200",
            "DocumentMlOpsEvidence",
            None,
        ),
    }

    for (method, path), (status, response_name, request_name) in expected.items():
        operation = document["paths"][path][method]
        response_schema = operation["responses"][status]["content"]["application/json"][
            "schema"
        ]
        assert response_schema == {"$ref": f"#/components/schemas/{response_name}"}
        if request_name is None:
            assert "requestBody" not in operation
        else:
            request_schema = operation["requestBody"]["content"]["application/json"][
                "schema"
            ]
            assert request_schema == {"$ref": f"#/components/schemas/{request_name}"}

    assert "202" in document["paths"]["/ml/train"]["post"]["responses"]


def test_public_intelligence_operations_publish_bounded_grounded_contracts():
    document = build_openapi()
    snapshot = document["paths"]["/public-intelligence/snapshot"]["get"]
    explain = document["paths"]["/public-intelligence/explain"]["post"]

    assert snapshot["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PublicIntelligenceSnapshot"
    }
    assert explain["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PublicExplainRequest"
    }
    assert explain["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PublicExplanation"
    }
    request = document["components"]["schemas"]["PublicExplainRequest"]
    assert request["properties"]["question"]["maxLength"] == 1200
    assert request["properties"]["record_ids"]["maxItems"] == 12
    assert request["properties"]["top_k"]["maximum"] == 6
    citation = document["components"]["schemas"]["PublicEvidenceCitation"]
    assert "source_url" in citation["required"]
    assert "model_run_id" in citation["required"]
    assert "uncertainty" in citation["required"]


def test_public_model_execution_operations_publish_bounded_receipt_contracts():
    document = build_openapi()
    paths = document["paths"]
    collection = paths["/public-intelligence/model-executions"]
    item = paths["/public-intelligence/model-executions/{executionId}"]["get"]

    assert collection["post"]["responses"]["202"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/PublicModelExecutionReceipt"}
    assert collection["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/PublicModelExecutionRequest"}
    assert collection["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/PublicModelExecutionList"}
    assert item["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PublicModelExecutionReceipt"
    }
    schemas = document["components"]["schemas"]
    assert schemas["PublicModelExecutionRequest"]["properties"]["sampleSize"][
        "maximum"
    ] == 25
    receipt = schemas["PublicModelExecutionReceipt"]
    assert receipt["properties"]["model"]["properties"]["approvalStatus"][
        "const"
    ] == "PendingManualApproval"
    assert receipt["properties"]["execution"]["properties"]["instanceCount"][
        "const"
    ] == 1


def test_scale_lab_component_shapes_match_the_frontend_contract():
    document = build_openapi()
    schemas = document["components"]["schemas"]
    expected_fields = {
        "ScaleProfile": {
            "id",
            "label",
            "short_label",
            "total_records",
            "description",
            "capacity_state",
            "capacity_note",
            "recommended",
        },
        "ScalePlan": {
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
        },
        "ScaleRun": {
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
        },
        "ScaleExportReceipt": {
            "export_id",
            "status",
            "format",
            "row_count",
            "bytes",
            "object_uri",
            "download_url",
            "expires_at",
            "sha256",
        },
    }
    for name, fields in expected_fields.items():
        assert set(schemas[name]["required"]) == fields
        assert set(schemas[name]["properties"]) == fields
        assert schemas[name]["additionalProperties"] is False

    assert schemas["ScaleSyntheticDomain"]["enum"] == [
        "grants",
        "finance",
        "milestones",
        "documents",
        "licenses",
        "stream_events",
    ]
    assert schemas["ScalePlanRequest"]["required"] == ["profile_id", "seed"]
    assert schemas["ScaleLaunchRequest"]["required"] == [
        "plan_id",
        "idempotency_key",
    ]
    assert schemas["ScaleCancelRequest"]["properties"]["reason"]["const"] == (
        "operator_requested"
    )
    assert schemas["ScaleExportRequest"]["properties"]["dataset"]["const"] == (
        "curated_portfolio"
    )
    assert schemas["ScaleExportRequest"]["properties"]["format"]["const"] == ("parquet")


def test_scale_lab_openapi_exposes_no_physical_resource_identifiers():
    document = build_openapi()
    scale_contract = {
        "paths": {
            path: value
            for path, value in document["paths"].items()
            if path.startswith("/scale/")
        },
        "schemas": {
            name: value
            for name, value in document["components"]["schemas"].items()
            if name.startswith("Scale")
        },
    }
    encoded = json.dumps(scale_contract).lower()

    for forbidden in ("arn:", "s3://", "account_id", "bucket_name", "table_name"):
        assert forbidden not in encoded

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
FUNCTION_DIR = ROOT / "src" / "functions" / "public_intelligence"
COMMON_DIR = ROOT / "src" / "common" / "python"
for path in (str(COMMON_DIR), str(FUNCTION_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("PUBLIC_INTELLIGENCE_BUCKET", "private-evidence-bucket")
os.environ.setdefault("PUBLIC_INTELLIGENCE_PREFIX", "public-intelligence/")
os.environ.setdefault(
    "PUBLIC_INTELLIGENCE_MANIFEST_KEY",
    "public-intelligence/current/manifest.json",
)

SPEC = importlib.util.spec_from_file_location(
    "compass_public_intelligence_app", FUNCTION_DIR / "app.py"
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = app
SPEC.loader.exec_module(app)


class FakeS3:
    def __init__(self, objects):
        self.objects = dict(objects)
        self.calls = []

    def get_object(self, *, Bucket, Key):
        self.calls.append((Bucket, Key))
        raw = self.objects[Key]
        return {
            "Body": io.BytesIO(raw),
            "ContentLength": len(raw),
            "VersionId": "version-" + str(len(self.calls)),
        }


def json_bytes(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def evidence_fixture(*, index_patch=None, manifest_patch=None):
    snapshot_id = "onr-public-2026-08-11"
    index = {
        "contract": app.INDEX_CONTRACT,
        "version": 1,
        "snapshot_id": snapshot_id,
        "snapshot": {
            "corpus": {"awards": 2, "candidateAwardValueUsd": 141_000_000},
        },
        "records": [
            {
                "record_id": "N0001423C1022",
                "source_id": "usaspending",
                "title": "Future Advanced Strike research award",
                "summary": "The public award record reports work on ISR and precision strike capability.",
                "source_url": "https://www.usaspending.gov/award/example-one",
                "evidence_class": "observed",
                "record_sha256": "a" * 64,
            },
            {
                "record_id": "forecast-fy2027",
                "source_id": "usaspending-derived",
                "title": "Candidate-scope obligation forecast",
                "summary": "A bounded model estimates the next fiscal-year obligation range.",
                "source_url": "https://api.usaspending.gov/docs/endpoints",
                "evidence_class": "predicted",
                "model_run_id": "funding-forecast-20260811-a1",
                "uncertainty": {
                    "p10_usd": 900_000_000,
                    "p50_usd": 1_100_000_000,
                    "p90_usd": 1_400_000_000,
                },
                "record_sha256": "b" * 64,
            },
        ],
    }
    if index_patch:
        index.update(index_patch)
    index_raw = json_bytes(index)
    index_key = f"public-intelligence/snapshots/{snapshot_id}/evidence-index.json"
    manifest = {
        "contract": app.MANIFEST_CONTRACT,
        "version": 1,
        "snapshot_id": snapshot_id,
        "generated_at": "2026-08-11T22:00:00Z",
        "as_of_at": "2026-08-11T22:00:00Z",
        "evidence_class": "public_evidence",
        "data_boundary": {
            "classification": "public",
            "contains_cui": False,
            "pii_minimized": True,
        },
        "evidence_index": {
            "key": index_key,
            "sha256": hashlib.sha256(index_raw).hexdigest(),
        },
        "sources": [{"id": "usaspending", "record_count": 2}],
        "models": [{"id": "funding-forecast", "status": "candidate"}],
    }
    if manifest_patch:
        manifest.update(manifest_patch)
    manifest_raw = json_bytes(manifest)
    return FakeS3(
        {
            "public-intelligence/current/manifest.json": manifest_raw,
            index_key: index_raw,
        }
    )


def event(method, path, body=None, *, role="poweruser", authenticated=True):
    group = "compass-poweruser" if role == "poweruser" else "compass-viewer"
    authorizer = {}
    if authenticated:
        authorizer = {
            "lambda": {
                "sub": "test-subject",
                "role": role,
                "org_unit": "ONR-Corporate" if role == "poweruser" else "Code-30",
                "groups": json.dumps([group]),
            }
        }
    return {
        "requestContext": {
            "requestId": "request-123",
            "http": {"method": method, "path": path},
            "authorizer": authorizer,
        },
        "body": json.dumps(body) if body is not None else None,
    }


def response_body(response):
    return json.loads(response["body"])


def setup_function():
    app._S3_CLIENT = evidence_fixture()


def test_snapshot_verifies_manifest_and_returns_sanitized_public_index():
    response = app.handler(
        event("GET", "/public-intelligence/snapshot"),
        SimpleNamespace(aws_request_id="aws-123"),
    )
    body = response_body(response)

    assert response["statusCode"] == 200
    assert body["contract"] == app.SNAPSHOT_RESPONSE_CONTRACT
    assert body["snapshot_id"] == "onr-public-2026-08-11"
    assert body["record_count"] == 2
    assert body["identity_scope"] == {
        "role": "poweruser",
        "org_unit": "ONR-Corporate",
    }
    assert body["records"][0]["source_url"].startswith("https://")
    assert len(body["provenance"]["manifest_sha256"]) == 64
    rendered = json.dumps(body)
    assert "private-evidence-bucket" not in rendered
    assert "public-intelligence/snapshots/" not in rendered


def test_explain_uses_one_bounded_bedrock_call_and_returns_record_citations(monkeypatch):
    calls = []

    def fake_converse(**kwargs):
        calls.append(kwargs)
        return {
            "text": "The record describes ISR and precision strike research. [SRC:N0001423C1022]",
            "usage": {"inputTokens": 120, "outputTokens": 20},
            "model_id": "amazon.nova-lite-v1:0",
        }

    monkeypatch.setattr(app.llm, "converse", fake_converse)
    response = app.handler(
        event(
            "POST",
            "/public-intelligence/explain",
            {"question": "What precision strike work is represented?", "top_k": 3},
        ),
        SimpleNamespace(aws_request_id="aws-123"),
    )
    body = response_body(response)

    assert response["statusCode"] == 200
    assert body["grounded"] is True
    assert body["refused"] is False
    assert body["citations"][0]["record_id"] == "N0001423C1022"
    assert body["citations"][0]["source_url"].startswith("https://")
    assert body["generation"]["provider"] == "amazon-bedrock"
    assert body["explanation_run_id"].startswith("public-explain-")
    assert len(calls) == 1
    assert calls[0]["max_tokens"] == app.BEDROCK_MAX_TOKENS
    assert len(calls[0]["user"]) <= app.MAX_TOTAL_CONTEXT_CHARS + 2000


def test_predicted_explanation_returns_model_run_and_uncertainty(monkeypatch):
    monkeypatch.setattr(
        app.llm,
        "converse",
        lambda **_: {
            "text": "The forecast reports a bounded range. [SRC:forecast-fy2027]",
            "usage": None,
            "model_id": "amazon.nova-lite-v1:0",
        },
    )
    response = app.handler(
        event(
            "POST",
            "/public-intelligence/explain",
            {
                "question": "Explain the next fiscal-year obligation forecast",
                "record_ids": ["forecast-fy2027"],
            },
        ),
        SimpleNamespace(aws_request_id="aws-456"),
    )
    body = response_body(response)

    assert body["model_run_id"] == "funding-forecast-20260811-a1"
    assert body["evidence_class"] == "predicted"
    assert body["uncertainty"]["level"] == "model-reported"
    assert body["uncertainty"]["per_record"][0]["record_id"] == "forecast-fy2027"


def test_explain_refuses_without_relevant_citable_evidence(monkeypatch):
    called = False

    def forbidden_call(**_):
        nonlocal called
        called = True
        raise AssertionError("Bedrock must not be called without evidence")

    monkeypatch.setattr(app.llm, "converse", forbidden_call)
    response = app.handler(
        event(
            "POST",
            "/public-intelligence/explain",
            {"question": "What is the internal classified readiness assessment?"},
        ),
        SimpleNamespace(aws_request_id="aws-789"),
    )
    body = response_body(response)

    assert response["statusCode"] == 200
    assert body["grounded"] is False
    assert body["refused"] is True
    assert body["refusal_code"] == "INSUFFICIENT_CITABLE_EVIDENCE"
    assert body["citations"] == []
    assert called is False


def test_bedrock_failure_uses_deterministic_cited_fallback(monkeypatch):
    def fail(**_):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(app.llm, "converse", fail)
    response = app.handler(
        event(
            "POST",
            "/public-intelligence/explain",
            {"question": "Summarize precision strike research"},
        ),
        SimpleNamespace(aws_request_id="aws-fallback"),
    )
    body = response_body(response)

    assert response["statusCode"] == 200
    assert body["grounded"] is True
    assert body["generation"]["provider"] == "deterministic"
    assert "[SRC:N0001423C1022]" in body["answer"]


def test_invalid_index_digest_fails_closed():
    app._S3_CLIENT = evidence_fixture(
        manifest_patch={
            "evidence_index": {
                "key": "public-intelligence/snapshots/onr-public-2026-08-11/evidence-index.json",
                "sha256": "f" * 64,
            }
        }
    )
    response = app.handler(
        event("GET", "/public-intelligence/snapshot"),
        SimpleNamespace(aws_request_id="aws-invalid"),
    )
    body = response_body(response)

    assert response["statusCode"] == 503
    assert body["code"] == "PUBLIC_EVIDENCE_UNAVAILABLE"
    assert "digest" not in body["error"]


def test_non_public_boundary_fails_closed():
    app._S3_CLIENT = evidence_fixture(
        manifest_patch={
            "data_boundary": {
                "classification": "CUI",
                "contains_cui": True,
                "pii_minimized": False,
            }
        }
    )
    response = app.handler(
        event("GET", "/public-intelligence/snapshot"),
        SimpleNamespace(aws_request_id="aws-cui"),
    )
    assert response["statusCode"] == 503


def test_unauthenticated_and_unknown_roles_are_denied_before_s3_read():
    fake = evidence_fixture()
    app._S3_CLIENT = fake
    unauthenticated = app.handler(
        event("GET", "/public-intelligence/snapshot", authenticated=False),
        SimpleNamespace(aws_request_id="aws-auth"),
    )
    unknown = app.handler(
        {
            "requestContext": {
                "http": {"method": "GET", "path": "/public-intelligence/snapshot"},
                "authorizer": {
                    "lambda": {
                        "sub": "unknown",
                        "role": "administrator",
                        "org_unit": "ONR-Corporate",
                        "groups": "[]",
                    }
                },
            }
        },
        SimpleNamespace(aws_request_id="aws-role"),
    )

    assert unauthenticated["statusCode"] == 401
    assert unknown["statusCode"] == 401
    assert fake.calls == []


def test_configured_role_allowlist_is_enforced_before_s3_read(monkeypatch):
    fake = evidence_fixture()
    app._S3_CLIENT = fake
    monkeypatch.setenv("PUBLIC_INTELLIGENCE_READ_ROLES", "poweruser")
    response = app.handler(
        event("GET", "/public-intelligence/snapshot", role="viewer"),
        SimpleNamespace(aws_request_id="aws-viewer"),
    )

    assert response["statusCode"] == 403
    assert fake.calls == []


def test_explain_input_limits_are_enforced_before_s3_read():
    fake = evidence_fixture()
    app._S3_CLIENT = fake
    response = app.handler(
        event(
            "POST",
            "/public-intelligence/explain",
            {"question": "valid question", "top_k": app.MAX_TOP_K + 1},
        ),
        SimpleNamespace(aws_request_id="aws-limit"),
    )

    assert response["statusCode"] == 400
    assert fake.calls == []


def test_sam_resource_is_isolated_and_least_privilege():
    template = (ROOT / "template.yaml").read_text(encoding="utf-8")
    block = template.split("  PublicIntelligenceFunction:", 1)[1].split(
        "  ApprovalsFunction:", 1
    )[0]

    assert "VpcConfig:" not in block
    assert "Action: s3:GetObject" in block
    assert "GovernPublicSbirExecutionReceipts" in block
    assert 'Resource: !Sub "${RawBucket.Arn}/mlops/public-sbir-transition/executions/*"' in block
    assert "Action: s3:ListBucket" in block
    assert "s3:prefix: [mlops/public-sbir-transition/executions/history/*]" in block
    assert "bedrock:InvokeModelWithResponseStream" not in block
    assert "amazon.nova-lite-v1:0" in block
    assert '${RawBucket.Arn}/public-intelligence/*' in block
    assert '${ScaleDataLakeBucket.Arn}/public-intelligence/*' in block
    assert "Path: /public-intelligence/snapshot" in block
    assert "Path: /public-intelligence/explain" in block
    assert "Path: /public-intelligence/model-executions" in block
    assert "Path: /public-intelligence/model-executions/{executionId}" in block


def test_model_execution_routes_enforce_auth_and_role(monkeypatch):
    monkeypatch.setattr(
        app.model_execution,
        "start_execution",
        lambda **kwargs: {
            "contract": app.model_execution.CONTRACT,
            "executionId": "sbir-batch-20260812T120000-1234abcd",
            "status": "SUBMITTED",
        },
    )
    poweruser = app.handler(
        event(
            "POST",
            "/public-intelligence/model-executions",
            {"sampleSize": 8},
        ),
        SimpleNamespace(aws_request_id="aws-model"),
    )
    viewer = app.handler(
        event(
            "POST",
            "/public-intelligence/model-executions",
            {"sampleSize": 8},
            role="viewer",
        ),
        SimpleNamespace(aws_request_id="aws-model"),
    )

    assert poweruser["statusCode"] == 202
    assert response_body(poweruser)["status"] == "SUBMITTED"
    assert viewer["statusCode"] == 403


def test_model_execution_list_and_get_are_readable_by_viewer(monkeypatch):
    execution_id = "sbir-batch-20260812T120000-1234abcd"
    receipt = {
        "contract": app.model_execution.CONTRACT,
        "executionId": execution_id,
        "status": "COMPLETED",
    }
    monkeypatch.setattr(
        app.model_execution,
        "list_executions",
        lambda: {
            "contract": "compass.public-intelligence.model-execution-list.v1",
            "executions": [receipt],
        },
    )
    monkeypatch.setattr(app.model_execution, "get_execution", lambda _: receipt)

    listed = app.handler(
        event("GET", "/public-intelligence/model-executions", role="viewer"),
        SimpleNamespace(aws_request_id="aws-list"),
    )
    fetched = app.handler(
        event(
            "GET",
            f"/public-intelligence/model-executions/{execution_id}",
            role="viewer",
        ),
        SimpleNamespace(aws_request_id="aws-get"),
    )

    assert response_body(listed)["executions"][0]["executionId"] == execution_id
    assert response_body(fetched)["status"] == "COMPLETED"

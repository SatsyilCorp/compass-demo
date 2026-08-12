from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
FUNCTION_DIR = ROOT / "src" / "functions" / "document_ml"
COMMON_DIR = ROOT / "src" / "common" / "python"
for path in (str(COMMON_DIR), str(FUNCTION_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

SPEC = importlib.util.spec_from_file_location(
    "compass_document_ml_app", FUNCTION_DIR / "app.py"
)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


class FakeRepository:
    bucket = "physical-bucket-hidden"

    def __init__(self):
        self.objects = {}
        self.source_objects = {}
        self.records = {}
        self.aliases = {}

    def presign_upload(self, key, content_type, *, expires_in):
        assert key.startswith("documents/incoming/doc-")
        assert expires_in == 900
        return "https://upload.example.test/signed"

    def put_json(self, key, value, *, metadata=None):
        self.objects[key] = json.loads(json.dumps(value, default=str))
        return f"lake://{key}"

    def get_json(self, key):
        return self.objects[key]

    def get_bytes(self, bucket, key):
        payload, content_type = self.source_objects[(bucket, key)]
        return payload, {"Body": io.BytesIO(payload), "ContentType": content_type}

    def copy_object(self, source_bucket, source_key, destination_key):
        self.objects[destination_key] = {
            "copied_from": [source_bucket, source_key],
        }
        return f"lake://{destination_key}"

    def put_record(self, kind, record_id, value):
        self.records[(kind, record_id)] = json.loads(json.dumps(value, default=str))
        return dict(value)

    def get_record(self, kind, record_id):
        value = self.records.get((kind, record_id))
        return dict(value) if value else None

    def merge_record(self, kind, record_id, patch):
        value = {**self.records.get((kind, record_id), {}), **dict(patch)}
        self.records[(kind, record_id)] = value
        return dict(value)

    def list_records(self, kind, *, limit=25):
        values = [
            value for (item_kind, _), value in self.records.items() if item_kind == kind
        ]
        return list(reversed(values))[:limit]

    def put_alias(self, alias, model_version, value):
        self.aliases[alias] = {**dict(value), "model_version": model_version}

    def get_alias(self, alias="champion"):
        value = self.aliases.get(alias)
        return dict(value) if value else None


def api_event(method, path, body=None, *, role="poweruser", org_unit="ONR-Corporate"):
    group = "compass-poweruser" if role == "poweruser" else "compass-viewer"
    return {
        "requestContext": {
            "http": {"method": method, "path": path},
            "authorizer": {
                "lambda": {
                    "sub": "test-user",
                    "username": f"{role}@compass.demo",
                    "role": role,
                    "org_unit": org_unit,
                    "groups": json.dumps([group]),
                }
            },
        },
        "body": json.dumps(body or {}),
    }


def test_browser_upload_contract_and_poweruser_gate(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)

    response = app.handler(
        api_event(
            "POST",
            "/documents/uploads",
            {
                "filename": "research-summary.txt",
                "content_type": "text/plain",
                "size_bytes": 120,
            },
        )
    )
    payload = json.loads(response["body"])

    assert response["statusCode"] == 201
    assert payload["status"] == "awaiting-upload"
    assert payload["upload"]["method"] == "PUT"
    assert payload["upload"]["url"] == "https://upload.example.test/signed"
    assert "physical-bucket-hidden" not in response["body"]

    denied = app.handler(
        api_event(
            "POST",
            "/documents/uploads",
            {"filename": "x.txt", "content_type": "text/plain", "size_bytes": 50},
            role="viewer",
            org_unit="Code-30",
        )
    )
    assert denied["statusCode"] == 403


def test_browser_jsonl_media_type_is_accepted(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)

    response = app.handler(
        api_event(
            "POST",
            "/documents/uploads",
            {
                "filename": "research-records.jsonl",
                "content_type": "application/x-ndjson",
                "size_bytes": 120,
            },
        )
    )

    assert response["statusCode"] == 201
    assert json.loads(response["body"])["content_type"] == "application/x-ndjson"


def test_public_upload_requires_explicit_public_boundary(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)

    denied = app.handler(
        api_event(
            "POST",
            "/documents/uploads",
            {
                "filename": "public-opportunity.json",
                "content_type": "application/json",
                "size_bytes": 120,
                "synthetic_only": False,
                "data_classification": "public",
                "contains_cui": False,
            },
        )
    )
    assert denied["statusCode"] == 400

    accepted = app.handler(
        api_event(
            "POST",
            "/documents/uploads",
            {
                "filename": "public-opportunity.json",
                "content_type": "application/json",
                "size_bytes": 120,
                "synthetic_only": False,
                "data_classification": "public",
                "contains_cui": False,
                "pii_minimized": True,
            },
        )
    )
    payload = json.loads(accepted["body"])
    assert accepted["statusCode"] == 201
    assert payload["synthetic_only"] is False
    assert payload["data_boundary"] == {
        "classification": "public",
        "contains_cui": False,
        "pii_minimized": True,
    }


def test_drop_runs_bronze_quality_silver_gold_and_exposes_lineage(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)
    run_id = "doc-1234567890abcdef"
    source_key = f"documents/incoming/{run_id}/technical-report.txt"
    fake.source_objects[("input-bucket", source_key)] = (
        b"Technical report documents test objectives, laboratory configuration, measured performance, and findings.",
        "text/plain",
    )

    inspected = app.inspect_stage(
        {
            "detail": {
                "bucket": {"name": "input-bucket"},
                "object": {"key": source_key},
            }
        }
    )
    quality = app.quality_stage(inspected)
    curated = app.curate_stage(quality)

    assert inspected["gate"] == "continue"
    assert quality["gate"] == "pass"
    assert curated["status"] == "completed"
    assert curated["document_class"] == "technical_report"
    assert [part.split("/")[3] for part in curated["lineage"][1:]] == [
        "bronze",
        "quality",
        "silver",
        "gold",
    ]
    assert fake.records[("run", run_id)]["stage"] == "gold-published"


def test_training_registry_deployment_and_drift_are_real_state_changes(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)

    trained_response = app.handler(api_event("POST", "/ml/train"))
    trained = json.loads(trained_response["body"])
    assert trained_response["statusCode"] == 201
    assert trained["status"] == "registered"
    assert trained["metrics"]["accuracy"] >= 0.75

    version = trained["model_version"]
    deployed_response = app.handler(api_event("POST", f"/ml/models/{version}/deploy"))
    deployed = json.loads(deployed_response["body"])
    assert deployed_response["statusCode"] == 201
    assert deployed["target"]["kind"] == "deterministic-demo-adapter"
    assert deployed["target"]["online_endpoint"] is False

    drift_response = app.handler(
        api_event(
            "POST",
            "/ml/drift/evaluate",
            {
                "documents": [
                    "Cryptocurrency retail promotion unrelated galaxy football recipe."
                    for _ in range(6)
                ],
                "threshold": 0.20,
            },
        )
    )
    drift = json.loads(drift_response["body"])
    assert drift_response["statusCode"] == 201
    assert drift["drift_detected"] is True
    assert drift["receipt_uri"].startswith("document-lake://mlops/drift/")

    evidence_response = app.handler(api_event("GET", "/ml/ops/evidence"))
    evidence = json.loads(evidence_response["body"])
    assert evidence["champion"]["model_version"] == version
    assert evidence["models"][0]["status"] == "deployed"


def test_model_promotion_enforces_source_controlled_metric_gate(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)
    fake.put_record(
        "model",
        "weak-model",
        {
            "model_version": "weak-model",
            "status": "registered",
            "metrics": {"accuracy": 0.70, "macro_f1": 0.68},
        },
    )

    response = app.handler(api_event("POST", "/ml/models/weak-model/deploy"))

    assert response["statusCode"] == 409
    assert "promotion gate" in json.loads(response["body"])["error"]
    assert fake.get_alias("champion") is None

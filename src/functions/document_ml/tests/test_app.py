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
SOURCE_SHA256 = "a" * 64


class FakeRepository:
    bucket = "physical-bucket-hidden"

    def __init__(self):
        self.objects = {}
        self.source_objects = {}
        self.records = {}
        self.aliases = {}

    def presign_upload(self, key, content_type, *, maximum_bytes, expires_in):
        assert key.startswith("documents/incoming/doc-")
        assert expires_in == 900
        assert maximum_bytes == app.MAX_UPLOAD_BYTES
        return {
            "url": "https://upload.example.test/signed",
            "fields": {
                "Content-Type": content_type,
                "key": key,
                "policy": "bounded-test-policy",
            },
        }

    def put_json(self, key, value, *, metadata=None):
        self.objects[key] = json.loads(json.dumps(value, default=str))
        return f"lake://{key}"

    def get_json(self, key):
        return self.objects[key]

    def get_bytes(self, bucket, key, *, maximum_bytes):
        payload, content_type = self.source_objects[(bucket, key)]
        if len(payload) > maximum_bytes:
            raise ValueError("uploaded object exceeds the enforced size limit")
        return payload, {
            "Body": io.BytesIO(payload),
            "ContentType": content_type,
            "ContentLength": len(payload),
            "VersionId": "source-version-1",
        }

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


def run_public_document_pipeline(monkeypatch, *, project_state_machine_payloads=False):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)
    stages = {}
    signals = []

    def record_stage(**receipt):
        stages[(receipt["run_id"], receipt["sequence"], receipt["stage_id"])] = receipt
        return True

    def record_signal(**receipt):
        signals.append(receipt)
        return "signal-test"

    monkeypatch.setattr(app.operational_evidence, "record_stage", record_stage)
    monkeypatch.setattr(app.operational_evidence, "record_signal", record_signal)
    source = json.dumps(
        {
            "opportunity_number": "N00014-26-S-B001",
            "title": "Public ONR research opportunity",
            "summary": "Research grant objectives and expected outcomes.",
        }
    ).encode("utf-8")
    planned = json.loads(
        app.handler(
            api_event(
                "POST",
                "/documents/uploads",
                {
                    "filename": "onr-public-opportunity.json",
                    "content_type": "application/json",
                    "size_bytes": len(source),
                    "synthetic_only": False,
                    "data_classification": "public",
                    "contains_cui": False,
                    "pii_minimized": True,
                    "source_sha256": app.engine.sha256_bytes(source),
                },
            )
        )["body"]
    )
    source_key = planned["source"].removeprefix("document-lake://")
    fake.source_objects[("input-bucket", source_key)] = (source, "application/json")
    inspected = app.inspect_stage(
        {
            "detail": {
                "bucket": {"name": "input-bucket"},
                "object": {"key": source_key, "size": len(source)},
            }
        }
    )
    quality_input = inspected
    if project_state_machine_payloads:
        quality_input = {
            key: inspected[key]
            for key in (
                "run_id",
                "source_bucket",
                "source_key",
                "bronze_key",
                "org_unit",
            )
        }
    quality = app.quality_stage(quality_input)
    curate_input = quality
    if project_state_machine_payloads:
        curate_input = {
            key: quality[key]
            for key in (
                "run_id",
                "source_bucket",
                "source_key",
                "bronze_key",
                "quality_key",
                "org_unit",
            )
        }
    completed = app.curate_stage(curate_input)
    return planned, completed, stages, signals


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
                "source_sha256": SOURCE_SHA256,
            },
        )
    )
    payload = json.loads(response["body"])

    assert response["statusCode"] == 201
    assert payload["status"] == "awaiting-upload"
    assert payload["upload"]["method"] == "POST"
    assert payload["upload"]["url"] == "https://upload.example.test/signed"
    assert payload["upload"]["fields"]["Content-Type"] == "text/plain"
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
                "source_sha256": SOURCE_SHA256,
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
                "source_sha256": SOURCE_SHA256,
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
                "source_sha256": SOURCE_SHA256,
            },
        )
    )
    payload = json.loads(accepted["body"])
    assert accepted["statusCode"] == 201
    assert payload["contract"] == "compass.document-upload-plan.v1"
    assert payload["evidence_class"] == "public-operational"
    assert payload["synthetic_only"] is False
    assert payload["data_boundary"] == {
        "classification": "public",
        "contains_cui": False,
        "pii_minimized": True,
    }

    fake.put_record(
        "run",
        "public-ml-not-a-document",
        {"run_id": "public-ml-not-a-document", "status": "completed"},
    )
    listed = json.loads(app.handler(api_event("GET", "/documents/runs"))["body"])
    assert [item["run_id"] for item in listed["runs"]] == [payload["run_id"]]

    fetched = json.loads(
        app.handler(api_event("GET", f"/documents/runs/{payload['run_id']}"))["body"]
    )
    assert fetched["contract"] == "compass.document-intake-run.v1"
    assert fetched["source_sha256"] == SOURCE_SHA256


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


def test_completed_public_document_run_finalizes_upload_authorization(monkeypatch):
    planned, completed, stages, _signals = run_public_document_pipeline(monkeypatch)
    run_id = planned["run_id"]

    assert completed["status"] == "completed"
    assert stages[(run_id, 1, "upload-authorized")]["status"] == "completed"


def test_public_document_lineage_directly_labels_every_stage(monkeypatch):
    planned, _completed, stages, _signals = run_public_document_pipeline(monkeypatch)
    run_id = planned["run_id"]
    run_stages = [
        receipt
        for (receipt_run_id, _sequence, _stage_id), receipt in stages.items()
        if receipt_run_id == run_id
    ]

    assert sorted(receipt["sequence"] for receipt in run_stages) == list(range(1, 9))
    assert {
        receipt["evidence_class"] for receipt in run_stages
    } == {"public-operational"}


def test_public_document_completion_signal_carries_run_evidence_class(monkeypatch):
    planned, _completed, _stages, signals = run_public_document_pipeline(monkeypatch)
    completion = next(
        signal
        for signal in signals
        if signal["run_id"] == planned["run_id"]
        and signal["title"] == "Document pipeline completed"
    )

    assert completion["evidence_class"] == "public-operational"


def test_public_document_recovers_evidence_class_after_payload_projection(monkeypatch):
    planned, completed, stages, signals = run_public_document_pipeline(
        monkeypatch, project_state_machine_payloads=True
    )
    run_id = planned["run_id"]
    run_stages = [
        receipt
        for (receipt_run_id, _sequence, _stage_id), receipt in stages.items()
        if receipt_run_id == run_id
    ]
    completion = next(
        signal
        for signal in signals
        if signal["run_id"] == run_id
        and signal["title"] == "Document pipeline completed"
    )

    assert completed["evidence_class"] == "public-operational"
    assert {receipt["evidence_class"] for receipt in run_stages} == {
        "public-operational"
    }
    assert completion["evidence_class"] == "public-operational"


def test_public_award_narratives_use_governed_champion_and_publish_evidence(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)
    train, _test = app.engine.split_samples(app.engine.default_training_samples())
    model = app.engine.train_classifier(train)
    fake.put_json("mlops/models/champion.json", model)
    fake.put_record(
        "model",
        model["model_version"],
        {
            "model_version": model["model_version"],
            "artifact_key": "mlops/models/champion.json",
            "status": "deployed",
            "updated_at": "2026-08-13T12:00:00+00:00",
        },
    )
    fake.put_alias("champion", model["model_version"], {"status": "active"})

    receipt = app.classify_public_records(
        {
            "acquisition_run_id": "acq-public-test",
            "canonical_uri": "public-evidence://canonical-records.json",
            "canonical_sha256": "b" * 64,
            "records": [
                {
                    "source_record_id": "N00014-26-1-0001",
                    "recipient_name": "Example Research University",
                    "award_amount_usd": 500000,
                    "award_type": "PROJECT GRANT",
                    "awarding_subagency": "Department of the Navy",
                    "description": "Technical research objectives, measured performance, laboratory findings, and test results.",
                    "source_url": "https://www.usaspending.gov/award/example",
                }
            ],
        }
    )

    assert receipt["status"] == "completed"
    assert receipt["model_registered"] is True
    assert receipt["model_version"] == model["model_version"]
    assert receipt["record_count"] == 1
    assert receipt["artifact_uri"].startswith("lake://documents/gold/public-acquisitions/")
    assert fake.records[("run", receipt["run_id"])]["source_kind"] == "public-source-narratives"
    assert receipt["preview"][0]["source_record_id"] == "N00014-26-1-0001"


def test_public_upload_with_detected_sensitive_patterns_is_quarantined(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)
    run_id = "doc-sensitive-public"
    source_key = f"documents/incoming/{run_id}/public-note.txt"
    payload = b"Public note. Contact analyst@example.test for details."
    fake.source_objects[("input-bucket", source_key)] = (payload, "text/plain")
    fake.put_record(
        "run",
        run_id,
        {
            "run_id": run_id,
            "source_sha256": app.engine.sha256_bytes(payload),
            "expected_bytes": len(payload),
            "data_boundary": {"classification": "public", "pii_minimized": True},
        },
    )

    inspected = app.inspect_stage(
        {
            "detail": {
                "bucket": {"name": "input-bucket"},
                "object": {"key": source_key, "size": len(payload)},
            }
        }
    )

    assert inspected["status"] == "quarantined"
    assert inspected["gate"] == "quarantine"
    assert "sensitive patterns" in inspected["reason"]
    assert not any(key.startswith("documents/bronze/") for key in fake.objects)


def test_declared_upload_size_mismatch_is_quarantined(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)
    run_id = "doc-size-mismatch"
    source_key = f"documents/incoming/{run_id}/report.txt"
    payload = b"A compact technical report with measured results."
    fake.source_objects[("input-bucket", source_key)] = (payload, "text/plain")
    fake.put_record(
        "run",
        run_id,
        {
            "run_id": run_id,
            "source_sha256": app.engine.sha256_bytes(payload),
            "expected_bytes": len(payload) + 1,
            "data_boundary": {"classification": "synthetic-demo"},
        },
    )

    inspected = app.inspect_stage(
        {
            "detail": {
                "bucket": {"name": "input-bucket"},
                "object": {"key": source_key, "size": len(payload)},
            }
        }
    )

    assert inspected["status"] == "quarantined"
    assert "declared upload size" in inspected["reason"]


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
    assert drift["contract"] == "compass.model-drift-receipt.v1"
    assert drift["evidence_class"] == "public-operational"
    assert drift["model_version"] == version
    assert drift["documents_observed"] == 6
    assert drift["drift_detected"] is True
    assert len(drift["baseline_sha256"]) == 64
    assert len(drift["evaluation_window_sha256"]) == 64
    assert drift["recommended_action"] == "retrain-and-review"
    assert drift["created_at"].endswith("+00:00")
    assert drift["receipt_uri"].startswith("document-lake://mlops/drift/")

    evidence_response = app.handler(api_event("GET", "/ml/ops/evidence"))
    evidence = json.loads(evidence_response["body"])
    assert evidence["champion"]["model_version"] == version
    assert evidence["models"][0]["status"] == "deployed"


def test_live_drift_requires_an_explicit_monitoring_window(monkeypatch):
    fake = FakeRepository()
    monkeypatch.setattr(app, "_REPOSITORY", fake)
    trained = json.loads(app.handler(api_event("POST", "/ml/train"))["body"])
    app.handler(api_event("POST", f"/ml/models/{trained['model_version']}/deploy"))

    response = app.handler(api_event("POST", "/ml/drift/evaluate", {}))

    assert response["statusCode"] == 400
    assert "explicit public monitoring window" in json.loads(response["body"])["error"]


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

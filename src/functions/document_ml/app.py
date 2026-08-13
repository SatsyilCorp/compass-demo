"""AWS-native document pipeline and classical MLOps control API.

HTTP routes provide direct browser upload, run evidence, model training,
registry promotion, and drift evaluation. Step Functions invokes the same
Lambda for inspect, quality, curate, and quarantine stages after S3 reports a
new object under ``documents/incoming/``.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
import zipfile
from pathlib import PurePosixPath
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import unquote_plus

from compass_common import http, operational_evidence

import engine
import repository
import sagemaker_adapter


logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
UPLOAD_PREFIX = "documents/incoming/"
MAX_UPLOAD_BYTES = engine.MAX_DOCUMENT_BYTES
MLOPS_MODE = os.environ.get("MLOPS_MODE", "demo").strip().lower()
MIN_DRIFT_DOCUMENTS = 5
ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/x-ndjson",
    "application/xml",
    "text/csv",
    "text/markdown",
    "text/plain",
    "text/xml",
}
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_REPOSITORY = None


def _stage(
    run_id: str,
    sequence: int,
    stage_id: str,
    label: str,
    status: str,
    **kwargs: Any,
) -> None:
    run_kind = (
        "model-training"
        if run_id.startswith("train-")
        else "model-deployment"
        if run_id.startswith("deploy-")
        else "model-monitoring"
        if run_id.startswith("drift-")
        else "document-intake"
    )
    operational_evidence.record_stage(
        run_id=run_id,
        run_kind=run_kind,
        sequence=sequence,
        stage_id=stage_id,
        label=label,
        status=status,
        **kwargs,
    )


def _repo():
    global _REPOSITORY
    if _REPOSITORY is None:
        _REPOSITORY = repository.AwsRepository()
    return _REPOSITORY


def _poweruser(claims: http.Claims) -> bool:
    return claims.role == "poweruser" and claims.is_corporate


def _actor(claims: http.Claims) -> str:
    return claims.username or claims.email or claims.sub or "unknown"


def _safe_filename(filename: str) -> str:
    base = PurePosixPath(filename or "").name
    safe = SAFE_NAME_RE.sub("-", base).strip(".-")[:120]
    if not safe or PurePosixPath(safe.lower()).suffix not in engine.SUPPORTED_SUFFIXES:
        raise ValueError(
            "filename must use one of: " + ", ".join(engine.SUPPORTED_SUFFIXES)
        )
    return safe


def _logical_uri(key: str) -> str:
    return f"document-lake://{key}"


def _public_record(item: Mapping[str, Any]) -> Dict[str, Any]:
    hidden = {"pk", "sk", "gsi1pk", "gsi1sk"}
    return {key: value for key, value in item.items() if key not in hidden}


def request_upload(claims: http.Claims, body: Mapping[str, Any]) -> Dict[str, Any]:
    filename = _safe_filename(str(body.get("filename") or ""))
    content_type = str(body.get("content_type") or "application/octet-stream").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("unsupported content_type")
    try:
        size_bytes = int(body.get("size_bytes") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("size_bytes must be an integer") from exc
    if not 0 < size_bytes <= MAX_UPLOAD_BYTES:
        raise ValueError(f"size_bytes must be between 1 and {MAX_UPLOAD_BYTES}")

    synthetic_only = bool(body.get("synthetic_only", True))
    data_classification = str(
        body.get("data_classification")
        or ("synthetic-demo" if synthetic_only else "public")
    ).strip().lower()
    if data_classification not in {"synthetic-demo", "public"}:
        raise ValueError("data_classification must be synthetic-demo or public")
    if data_classification == "public":
        if body.get("contains_cui") is not False:
            raise ValueError("public uploads must explicitly declare contains_cui=false")
        if body.get("pii_minimized") is not True:
            raise ValueError("public uploads must explicitly declare pii_minimized=true")
        synthetic_only = False
    elif not synthetic_only:
        raise ValueError("synthetic-demo uploads must declare synthetic_only=true")

    source_sha256 = str(body.get("source_sha256") or "").strip().lower()
    if not SHA256_RE.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be the browser-computed SHA-256 digest")

    upload_id = uuid.uuid4().hex
    run_id = f"doc-{upload_id}"
    key = f"{UPLOAD_PREFIX}{run_id}/{filename}"
    now = engine.utc_now()
    record = {
        "run_id": run_id,
        "document_id": upload_id,
        "status": "awaiting-upload",
        "stage": "browser-upload",
        "filename": filename,
        "content_type": content_type,
        "expected_bytes": size_bytes,
        "org_unit": claims.org_unit,
        "requested_by": _actor(claims),
        "created_at": now,
        "updated_at": now,
        "source": _logical_uri(key),
        "source_sha256": source_sha256,
        "synthetic_only": synthetic_only,
        "data_boundary": {
            "classification": data_classification,
            "contains_cui": False,
            "pii_minimized": data_classification == "public",
        },
    }
    _repo().put_record("run", run_id, record)
    _stage(
        run_id,
        1,
        "upload-authorized",
        "Upload authorized and source hash declared",
        "running",
        source=_logical_uri(key),
        source_sha256=source_sha256,
        actor=_actor(claims),
        detail={
            "evidence_class": data_classification,
            "record_count": 1,
            "schema": PurePosixPath(filename).suffix.lower(),
        },
    )
    upload_plan = _repo().presign_upload(
        key,
        content_type,
        maximum_bytes=MAX_UPLOAD_BYTES,
        expires_in=900,
    )
    return {
        **record,
        "upload": {
            "method": "POST",
            "url": upload_plan["url"],
            "fields": upload_plan["fields"],
            "expires_in_seconds": 900,
            "maximum_bytes": MAX_UPLOAD_BYTES,
        },
        "next": "POST the signed form fields and file to upload.url; S3 starts the pipeline automatically.",
    }


def _event_object(event: Mapping[str, Any]) -> tuple[str, str, Optional[int]]:
    detail = event.get("detail") if isinstance(event.get("detail"), Mapping) else event
    bucket = (
        (detail.get("bucket") or {}).get("name")
        if isinstance(detail, Mapping)
        else None
    )
    object_detail = detail.get("object") or {} if isinstance(detail, Mapping) else {}
    key = unquote_plus(str(object_detail.get("key") or ""))
    size = object_detail.get("size")
    if not bucket or not key:
        raise ValueError("document event requires bucket.name and object.key")
    return str(bucket), key, int(size) if size is not None else None


def _run_id_from_key(key: str) -> str:
    parts = key.split("/")
    if (
        len(parts) >= 4
        and parts[0:2] == ["documents", "incoming"]
        and parts[2].startswith("doc-")
    ):
        return parts[2]
    digest = engine.sha256_bytes(key.encode("utf-8"))[:24]
    return f"doc-{digest}"


def inspect_stage(event: Mapping[str, Any]) -> Dict[str, Any]:
    bucket, key, event_size = _event_object(event)
    run_id = _run_id_from_key(key)
    filename = PurePosixPath(key).name
    now = engine.utc_now()
    current_before = _repo().get_record("run", run_id) or {}
    _stage(
        run_id,
        2,
        "object-event",
        "Object-created event correlated",
        "completed",
        source=_logical_uri(key),
        source_sha256=str(current_before.get("source_sha256") or "") or None,
        detail={"record_count": 1},
    )
    try:
        if event_size is not None and event_size > MAX_UPLOAD_BYTES:
            raise ValueError("uploaded object exceeds the enforced size limit")
        payload, response = _repo().get_bytes(
            bucket, key, maximum_bytes=MAX_UPLOAD_BYTES
        )
        content_type = str(response.get("ContentType") or "application/octet-stream")
        if event_size is not None and event_size != len(payload):
            raise ValueError("event size does not match the retrieved object")
        expected_bytes = current_before.get("expected_bytes")
        if expected_bytes is not None and int(expected_bytes) != len(payload):
            raise ValueError("declared upload size does not match the retrieved object")
        extracted = engine.extract_document(filename, content_type, payload)
        declared_sha256 = str(current_before.get("source_sha256") or "")
        if declared_sha256 and extracted["sha256"] != declared_sha256:
            raise ValueError("browser and server source SHA-256 digests do not match")
        boundary = current_before.get("data_boundary")
        classification = (
            str(boundary.get("classification") or "")
            if isinstance(boundary, Mapping)
            else ""
        )
        sensitive_counts = extracted.get("sensitive_pattern_counts") or {}
        if classification == "public" and any(
            int(count or 0) > 0 for count in sensitive_counts.values()
        ):
            raise ValueError(
                "public upload contains sensitive patterns and must be quarantined"
            )
    except (UnicodeDecodeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        failure = {
            "run_id": run_id,
            "status": "quarantined",
            "stage": "inspect",
            "gate": "quarantine",
            "reason": str(exc),
            "source": _logical_uri(key),
            "updated_at": now,
        }
        _repo().merge_record("run", run_id, failure)
        _stage(
            run_id,
            3,
            "source-verification",
            "Source verification failed",
            "quarantined",
            source=_logical_uri(key),
            source_sha256=str(current_before.get("source_sha256") or "") or None,
            detail={"rejected_records": 1},
        )
        operational_evidence.record_signal(
            category="document-intake",
            severity="high",
            title="Document source quarantined",
            message="The uploaded source failed inspection or digest verification and was not published.",
            run_id=run_id,
            evidence_uri=_logical_uri(key),
            detail={"rejected_records": 1},
        )
        return {**failure, "source_bucket": bucket, "source_key": key}

    bronze_key = f"documents/bronze/{run_id}/document.json"
    bronze = {
        **extracted,
        "run_id": run_id,
        "source": _logical_uri(key),
        "inspected_at": now,
    }
    _repo().put_json(
        bronze_key,
        bronze,
        metadata={"run-id": run_id, "stage": "bronze", "sha256": extracted["sha256"]},
    )
    update = {
        "run_id": run_id,
        "document_id": run_id.removeprefix("doc-"),
        "status": "running",
        "stage": "bronze-inspected",
        "filename": filename,
        "content_type": content_type,
        "bytes": extracted["bytes"],
        "sha256": extracted["sha256"],
        "schema": extracted["schema"],
        "classification_marking": extracted["classification_marking"],
        "sensitive_pattern_counts": extracted["sensitive_pattern_counts"],
        "bronze_uri": _logical_uri(bronze_key),
        "bronze_key": bronze_key,
        "source": _logical_uri(key),
        "source_object_version": str(response.get("VersionId") or "") or None,
        "updated_at": now,
    }
    current = _repo().merge_record("run", run_id, update)
    _stage(
        run_id,
        3,
        "source-verified",
        "Source bytes verified",
        "completed",
        source=_logical_uri(key),
        destination=_logical_uri(bronze_key),
        source_sha256=extracted["sha256"],
        output_sha256=operational_evidence.canonical_digest(bronze),
        detail={
            "record_count": int((extracted.get("schema") or {}).get("record_count") or 1),
            "schema": str((extracted.get("schema") or {}).get("shape") or "document"),
        },
    )
    _stage(
        run_id,
        4,
        "bronze-extracted",
        "Bronze retained and schema inferred",
        "completed",
        source=_logical_uri(key),
        destination=_logical_uri(bronze_key),
        source_sha256=extracted["sha256"],
        output_sha256=operational_evidence.canonical_digest(bronze),
        detail={
            "accepted_records": int((extracted.get("schema") or {}).get("record_count") or 1),
            "schema": str((extracted.get("schema") or {}).get("shape") or "document"),
        },
    )
    return {
        "run_id": run_id,
        "status": "ok",
        "gate": "continue",
        "source_bucket": bucket,
        "source_key": key,
        "bronze_key": bronze_key,
        "org_unit": current.get("org_unit", "ONR-Corporate"),
    }


def quality_stage(event: Mapping[str, Any]) -> Dict[str, Any]:
    run_id = str(event["run_id"])
    bronze_key = str(event["bronze_key"])
    extracted = _repo().get_json(bronze_key)
    receipt = engine.quality_receipt(extracted)
    receipt.update({"run_id": run_id, "evaluated_at": engine.utc_now()})
    receipt_key = f"documents/quality/{run_id}.json"
    _repo().put_json(
        receipt_key, receipt, metadata={"run-id": run_id, "stage": "quality"}
    )
    update = {
        "status": "running" if receipt["gate"] == "pass" else "quarantined",
        "stage": "quality-gate",
        "quality": receipt,
        "quality_receipt_uri": _logical_uri(receipt_key),
        "updated_at": engine.utc_now(),
    }
    _repo().merge_record("run", run_id, update)
    _stage(
        run_id,
        5,
        "quality-gate",
        "Blocking and advisory quality rules evaluated",
        "completed" if receipt["gate"] == "pass" else "quarantined",
        source=_logical_uri(bronze_key),
        destination=_logical_uri(receipt_key),
        input_sha256=str(extracted.get("sha256") or "") or None,
        output_sha256=operational_evidence.canonical_digest(receipt),
        detail={
            "quality_score": receipt["score"],
            "failed_records": len(receipt["blocking_failures"]),
            "accepted_records": 1 if receipt["gate"] == "pass" else 0,
            "rejected_records": 0 if receipt["gate"] == "pass" else 1,
        },
    )
    reason = (
        "blocking quality rules failed: " + ", ".join(receipt["blocking_failures"])
        if receipt["blocking_failures"]
        else ""
    )
    return {
        **dict(event),
        "gate": receipt["gate"],
        "quality_key": receipt_key,
        "reason": reason,
    }


def _load_model(model_version: str) -> Dict[str, Any]:
    record = _repo().get_record("model", model_version)
    if not record or not record.get("artifact_key"):
        raise ValueError(f"model version {model_version!r} is not registered")
    return _repo().get_json(str(record["artifact_key"]))


def _champion_or_baseline() -> tuple[Dict[str, Any], Dict[str, Any]]:
    alias = _repo().get_alias("champion")
    if alias and alias.get("model_version"):
        model = _load_model(str(alias["model_version"]))
        return model, {"registered": True, "alias": "champion"}
    train, _test = engine.split_samples(engine.default_training_samples())
    model = engine.train_classifier(train)
    return model, {
        "registered": False,
        "alias": None,
        "disclosure": "No champion was deployed; deterministic source baseline was used.",
    }


def curate_stage(event: Mapping[str, Any]) -> Dict[str, Any]:
    run_id = str(event["run_id"])
    bronze = _repo().get_json(str(event["bronze_key"]))
    model, model_state = _champion_or_baseline()
    prediction = engine.predict(model, str(bronze.get("extracted_text") or ""))
    now = engine.utc_now()
    silver_key = f"documents/silver/{run_id}/normalized.json"
    gold_key = f"documents/gold/{run_id}/decision-record.json"
    silver = {
        "contract": "compass.document-silver.v1",
        "run_id": run_id,
        "source_sha256": bronze["sha256"],
        "filename": bronze["filename"],
        "schema": bronze["schema"],
        "classification_marking": bronze["classification_marking"],
        "sensitive_pattern_counts": bronze["sensitive_pattern_counts"],
        "normalized_text": bronze["extracted_text"],
        "curated_at": now,
    }
    gold = {
        "contract": "compass.document-gold.v1",
        "run_id": run_id,
        "document_class": prediction["label"],
        "confidence": prediction["confidence"],
        "review_required": prediction["review_required"],
        "class_probabilities": prediction["probabilities"],
        "model_version": model["model_version"],
        "model_state": model_state,
        "quality_receipt": _logical_uri(str(event["quality_key"])),
        "decision_use": "portfolio discovery and routing",
        "generated_at": now,
    }
    _repo().put_json(silver_key, silver, metadata={"run-id": run_id, "stage": "silver"})
    _repo().put_json(gold_key, gold, metadata={"run-id": run_id, "stage": "gold"})
    _stage(
        run_id,
        6,
        "model-inference",
        "Champion classifier scored the document",
        "completed",
        source=_logical_uri(str(event["bronze_key"])),
        destination=_logical_uri(gold_key),
        source_sha256=str(bronze.get("sha256") or "") or None,
        input_sha256=operational_evidence.canonical_digest(silver),
        output_sha256=operational_evidence.canonical_digest(prediction),
        detail={
            "model_version": model["model_version"],
            "confidence": prediction["confidence"],
            "consumer": "Document review queue",
        },
    )
    _stage(
        run_id,
        7,
        "silver-published",
        "Normalized Silver document published",
        "completed",
        source=_logical_uri(str(event["bronze_key"])),
        destination=_logical_uri(silver_key),
        source_sha256=str(bronze.get("sha256") or "") or None,
        output_sha256=operational_evidence.canonical_digest(silver),
        detail={"accepted_records": 1, "schema": str(bronze.get("schema", {}).get("shape") or "document")},
    )
    complete = {
        "run_id": run_id,
        "status": "completed",
        "stage": "gold-published",
        "document_class": prediction["label"],
        "confidence": prediction["confidence"],
        "review_required": prediction["review_required"],
        "class_probabilities": prediction["probabilities"],
        "model_version": model["model_version"],
        "model_state": model_state,
        "silver_uri": _logical_uri(silver_key),
        "silver_key": silver_key,
        "gold_uri": _logical_uri(gold_key),
        "gold_key": gold_key,
        "lineage": [
            _logical_uri(str(event["source_key"])),
            _logical_uri(str(event["bronze_key"])),
            _logical_uri(str(event["quality_key"])),
            _logical_uri(silver_key),
            _logical_uri(gold_key),
        ],
        "completed_at": now,
        "updated_at": now,
    }
    complete["lineage_receipt_sha256"] = operational_evidence.canonical_digest(complete)
    _repo().merge_record("run", run_id, complete)
    _stage(
        run_id,
        8,
        "gold-published",
        "Governed Gold decision record published",
        "completed",
        source=_logical_uri(silver_key),
        destination=_logical_uri(gold_key),
        source_sha256=str(bronze.get("sha256") or "") or None,
        input_sha256=operational_evidence.canonical_digest(silver),
        output_sha256=operational_evidence.canonical_digest(gold),
        detail={
            "accepted_records": 1,
            "model_version": model["model_version"],
            "confidence": prediction["confidence"],
            "consumer": "Governed catalog and decision workspace",
        },
    )
    operational_evidence.record_signal(
        category="document-intake",
        severity="info" if not prediction["review_required"] else "medium",
        title="Document pipeline completed",
        message=(
            f"The source passed quality and was classified as {prediction['label']} "
            f"with {prediction['confidence']:.0%} confidence."
        ),
        run_id=run_id,
        evidence_uri=_logical_uri(gold_key),
        detail={
            "accepted_records": 1,
            "model_version": model["model_version"],
            "confidence": prediction["confidence"],
        },
    )
    return complete


def quarantine_stage(event: Mapping[str, Any]) -> Dict[str, Any]:
    run_id = str(event["run_id"])
    source_bucket = str(event["source_bucket"])
    source_key = str(event["source_key"])
    quarantine_key = f"documents/quarantine/{run_id}/{PurePosixPath(source_key).name}"
    uri = _repo().copy_object(source_bucket, source_key, quarantine_key)
    update = {
        "run_id": run_id,
        "status": "quarantined",
        "stage": "quarantine",
        "quarantine_uri": uri,
        "reason": event.get("reason")
        or "document failed one or more blocking quality rules",
        "updated_at": engine.utc_now(),
    }
    _repo().merge_record("run", run_id, update)
    _stage(
        run_id,
        8,
        "quarantine",
        "Source retained in quarantine",
        "quarantined",
        source=_logical_uri(source_key),
        destination=uri,
        detail={"rejected_records": 1, "consumer": "Human quality review"},
    )
    operational_evidence.record_signal(
        category="document-quality",
        severity="high",
        title="Document quality gate quarantined source",
        message="Blocking validation or quality rules prevented Silver and Gold publication.",
        run_id=run_id,
        evidence_uri=uri,
        detail={"rejected_records": 1},
    )
    return update


def workflow_failure_stage(event: Mapping[str, Any]) -> Dict[str, Any]:
    failure = event.get("failure") if isinstance(event.get("failure"), Mapping) else {}
    run_id = str(failure.get("run_id") or "")
    source_key = str(failure.get("source_key") or "")
    if not run_id and source_key:
        run_id = _run_id_from_key(source_key)
    if not run_id:
        execution_id = SAFE_NAME_RE.sub(
            "-", str(event.get("execution_id") or uuid.uuid4().hex[:16])
        )[:100]
        run_id = f"doc-failure-{execution_id}"
    error = failure.get("error") if isinstance(failure.get("error"), Mapping) else {}
    failure_code = str(error.get("Error") or "WorkflowStageFailed")[:120]
    source = _logical_uri(source_key) if source_key else "document-lake://unknown"
    now = engine.utc_now()
    if _repo().get_record("run", run_id):
        _repo().merge_record(
            "run",
            run_id,
            {
                "status": "failed",
                "stage": "workflow-failed",
                "failure_code": failure_code,
                "updated_at": now,
            },
        )
    _stage(
        run_id,
        99,
        "workflow-failed",
        "Document pipeline failed after bounded retries",
        "failed",
        source=source,
        actor="compass-document-workflow",
        detail={"failed_records": 1, "failure_code": failure_code},
    )
    operational_evidence.record_signal(
        category="document-intake",
        severity="critical",
        title="Document workflow failed",
        message="A document stage exhausted its bounded retries. No unverified Gold record was published.",
        run_id=run_id,
        evidence_uri=source,
        detail={"failed_records": 1, "failure_code": failure_code},
    )
    return {"run_id": run_id, "status": "failed", "failure_code": failure_code}


def _training_samples(body: Mapping[str, Any]) -> List[engine.TrainingSample]:
    requested = body.get("training_records")
    if requested is None:
        return engine.default_training_samples()
    if not isinstance(requested, list) or not 4 <= len(requested) <= 500:
        raise ValueError("training_records must contain between 4 and 500 records")
    samples = []
    for index, item in enumerate(requested):
        if not isinstance(item, Mapping):
            raise ValueError(f"training_records[{index}] must be an object")
        text = str(item.get("text") or "").strip()
        label = str(item.get("label") or "").strip().lower()
        if len(text) < 20 or label not in engine.DOCUMENT_TAXONOMY:
            raise ValueError(f"training_records[{index}] has invalid text or label")
        samples.append(
            engine.TrainingSample(
                text=text,
                label=label,
                sample_id=str(item.get("sample_id") or f"record-{index + 1}"),
            )
        )
    labels = {sample.label for sample in samples}
    expected = set(engine.DOCUMENT_TAXONOMY)
    if labels != expected:
        raise ValueError(
            "training_records must cover the shared taxonomy exactly: "
            + ", ".join(engine.DOCUMENT_TAXONOMY)
        )
    return samples


def train_model(claims: http.Claims, body: Mapping[str, Any]) -> Dict[str, Any]:
    samples = _training_samples(body)
    model, metrics = engine.train_and_evaluate(samples)
    model_version = model["model_version"]
    now = engine.utc_now()
    training_key = f"mlops/training/{model_version}/training.json"
    artifact_key = f"mlops/models/{model_version}/model.json"
    _repo().put_json(
        training_key,
        [
            {"sample_id": item.sample_id, "label": item.label, "text": item.text}
            for item in samples
        ],
        metadata={"model-version": model_version, "synthetic-only": "true"},
    )
    _repo().put_json(
        artifact_key,
        model,
        metadata={
            "model-version": model_version,
            "training-digest": model["training_digest"],
        },
    )

    adapter_evidence: Dict[str, Any]
    if MLOPS_MODE == "sagemaker":
        adapter_evidence = sagemaker_adapter.SageMakerTrainingAdapter().submit(
            model_version=model_version,
            training_data_uri=f"s3://{_repo().bucket}/{training_key}",
            output_uri=f"s3://{_repo().bucket}/mlops/sagemaker-output/",
        )
        status = (
            "training"
            if adapter_evidence["status"] == "submitted"
            else "configuration-required"
        )
    else:
        adapter_evidence = {
            "adapter": "deterministic-demo",
            "status": "completed",
            "configured": True,
            "disclosure": "Training and evaluation ran in-process using the source classical model.",
        }
        status = "registered"

    record = {
        "model_version": model_version,
        "status": status,
        "algorithm": model["algorithm"],
        "labels": model["labels"],
        "metrics": metrics,
        "artifact_uri": _logical_uri(artifact_key),
        "artifact_key": artifact_key,
        "training_data_uri": _logical_uri(training_key),
        "training_digest": model["training_digest"],
        "adapter": adapter_evidence,
        "registered_by": _actor(claims),
        "created_at": now,
        "updated_at": now,
        "synthetic_only": True,
    }
    _repo().put_record("model", model_version, record)
    training_run_id = f"train-{model_version}"
    _stage(
        training_run_id,
        1,
        "training-snapshot",
        "Immutable training snapshot retained",
        "completed",
        source=_logical_uri(training_key),
        source_sha256=model["training_digest"],
        actor=_actor(claims),
        detail={"record_count": len(samples), "model_version": model_version},
    )
    _stage(
        training_run_id,
        2,
        "model-trained",
        "Classical classifier trained",
        "completed" if status == "registered" else "running",
        source=_logical_uri(training_key),
        destination=_logical_uri(artifact_key),
        input_sha256=model["training_digest"],
        output_sha256=operational_evidence.canonical_digest(model),
        actor=_actor(claims),
        detail={"model_version": model_version, "record_count": len(samples)},
    )
    _stage(
        training_run_id,
        3,
        "evaluation-gate",
        "Evaluation metrics and promotion gates recorded",
        "completed",
        source=_logical_uri(artifact_key),
        output_sha256=operational_evidence.canonical_digest(metrics),
        actor=_actor(claims),
        detail={"model_version": model_version, "schema": "document-taxonomy-v1"},
    )
    _stage(
        training_run_id,
        4,
        "candidate-registered",
        "Candidate registry receipt recorded",
        "completed" if status == "registered" else "running",
        source=_logical_uri(artifact_key),
        destination="model-registry://document-classifier/candidate",
        actor=_actor(claims),
        detail={"model_version": model_version, "consumer": "Human promotion review"},
    )
    operational_evidence.record_signal(
        category="model-training",
        severity="info" if status == "registered" else "medium",
        title="Document model training receipt recorded",
        message=(
            "A classical model candidate completed local AWS evaluation and registry recording."
            if status == "registered"
            else "A governed SageMaker training request was submitted or requires environment configuration."
        ),
        run_id=training_run_id,
        evidence_uri=_logical_uri(artifact_key),
        detail={"model_version": model_version, "record_count": len(samples)},
    )
    return record


def deploy_model(claims: http.Claims, model_version: str) -> Dict[str, Any]:
    record = _repo().get_record("model", model_version)
    if not record:
        raise KeyError("model version not found")
    metrics = record.get("metrics") or {}
    if (
        float(metrics.get("accuracy") or 0) < engine.PROMOTION_MIN_ACCURACY
        or float(metrics.get("macro_f1") or 0) < engine.PROMOTION_MIN_MACRO_F1
    ):
        raise RuntimeError(
            "model metrics do not satisfy the source-controlled promotion gate"
        )
    if MLOPS_MODE == "sagemaker" and record.get("status") != "approved":
        raise RuntimeError(
            "SageMaker models can be promoted only after the registered package is approved"
        )
    now = engine.utc_now()
    target = sagemaker_adapter.deployment_target(MLOPS_MODE)
    deployment_id = f"deploy-{uuid.uuid4().hex[:12]}"
    deployment = {
        "deployment_id": deployment_id,
        "model_version": model_version,
        "alias": "champion",
        "status": "active",
        "target": target,
        "deployed_by": _actor(claims),
        "created_at": now,
        "updated_at": now,
    }
    _repo().put_record("deployment", deployment_id, deployment)
    _repo().put_alias("champion", model_version, deployment)
    _repo().merge_record(
        "model", model_version, {"status": "deployed", "updated_at": now}
    )
    _stage(
        deployment_id,
        1,
        "champion-promoted",
        "Human-approved Champion alias updated",
        "completed",
        source=f"model-registry://document-classifier/{model_version}",
        destination="model-alias://document-classifier/champion",
        actor=_actor(claims),
        detail={"model_version": model_version, "consumer": "Document intake inference"},
    )
    operational_evidence.record_signal(
        category="model-deployment",
        severity="medium",
        title="Document Champion alias changed",
        message=f"Model {model_version} was promoted through the explicit human control.",
        run_id=deployment_id,
        evidence_uri="model-alias://document-classifier/champion",
        detail={"model_version": model_version},
    )
    return deployment


def _documents_for_drift(body: Mapping[str, Any]) -> List[str]:
    requested = body.get("documents")
    if requested is not None:
        if not isinstance(requested, list) or not MIN_DRIFT_DOCUMENTS <= len(requested) <= 200:
            raise ValueError(
                f"documents must contain between {MIN_DRIFT_DOCUMENTS} and 200 text values"
            )
        documents = [str(value).strip() for value in requested]
        if any(len(value) < 20 for value in documents):
            raise ValueError("every drift document must contain at least 20 characters")
        return documents
    documents = []
    for run in _repo().list_records("run", limit=25):
        silver_key = run.get("silver_key")
        if silver_key:
            value = str(_repo().get_json(str(silver_key)).get("normalized_text") or "").strip()
            if len(value) >= 20:
                documents.append(value)
    _train, evaluation = engine.split_samples(engine.default_training_samples())
    for sample in evaluation:
        if len(documents) >= MIN_DRIFT_DOCUMENTS:
            break
        if sample.text not in documents:
            documents.append(sample.text)
    if len(documents) < MIN_DRIFT_DOCUMENTS:
        raise RuntimeError("at least five valid monitoring documents are required")
    return documents


def evaluate_drift(claims: http.Claims, body: Mapping[str, Any]) -> Dict[str, Any]:
    alias = _repo().get_alias("champion")
    if not alias or not alias.get("model_version"):
        raise RuntimeError("train and deploy a model before evaluating drift")
    model = _load_model(str(alias["model_version"]))
    try:
        threshold = float(body.get("threshold", 0.25))
    except (TypeError, ValueError) as exc:
        raise ValueError("threshold must be numeric") from exc
    documents = _documents_for_drift(body)
    receipt = engine.drift_receipt(model, documents, threshold=threshold)
    now = engine.utc_now()
    drift_id = f"drift-{uuid.uuid4().hex[:12]}"
    receipt.update(
        {
            "drift_id": drift_id,
            "evaluated_by": _actor(claims),
            "created_at": now,
            "updated_at": now,
        }
    )
    receipt["evaluation_window_sha256"] = operational_evidence.canonical_digest(documents)
    receipt["baseline_sha256"] = operational_evidence.canonical_digest(
        {
            "model_version": model["model_version"],
            "class_document_counts": model["class_document_counts"],
            "vocabulary": model["vocabulary"],
        }
    )
    receipt_key = f"mlops/drift/{drift_id}.json"
    _repo().put_json(
        receipt_key, receipt, metadata={"model-version": model["model_version"]}
    )
    receipt["receipt_uri"] = _logical_uri(receipt_key)
    _repo().put_record("drift", drift_id, receipt)
    _stage(
        drift_id,
        1,
        "monitoring-window",
        "Inference monitoring window sealed",
        "completed",
        source="model-alias://document-classifier/champion",
        input_sha256=receipt["baseline_sha256"],
        output_sha256=receipt["evaluation_window_sha256"],
        actor=_actor(claims),
        detail={
            "model_version": model["model_version"],
            "record_count": len(documents),
            "threshold": threshold,
        },
    )
    _stage(
        drift_id,
        2,
        "drift-evaluated",
        "Population and vocabulary drift evaluated",
        "completed",
        source="model-alias://document-classifier/champion",
        destination=_logical_uri(receipt_key),
        input_sha256=receipt["evaluation_window_sha256"],
        output_sha256=operational_evidence.canonical_digest(receipt),
        actor=_actor(claims),
        detail={
            "model_version": model["model_version"],
            "record_count": len(documents),
            "threshold": threshold,
            "consumer": "Model review queue",
        },
    )
    operational_evidence.record_signal(
        category="model-drift",
        severity="high" if receipt["drift_detected"] else "info",
        title="Model drift threshold crossed" if receipt["drift_detected"] else "Model drift check passed",
        message=(
            "The monitored window crossed the configured drift threshold. Retraining requires human review."
            if receipt["drift_detected"]
            else "The monitored window remained within the configured drift threshold."
        ),
        run_id=drift_id,
        evidence_uri=_logical_uri(receipt_key),
        detail={
            "model_version": model["model_version"],
            "record_count": len(documents),
            "threshold": threshold,
        },
    )
    return receipt


def mlops_evidence() -> Dict[str, Any]:
    alias = _repo().get_alias("champion")
    return {
        "mode": MLOPS_MODE,
        "truthfulness": (
            "Demo adapter evidence is labeled separately from submitted SageMaker jobs and endpoints."
        ),
        "champion": _public_record(alias) if alias else None,
        "models": [
            _public_record(item) for item in _repo().list_records("model", limit=20)
        ],
        "deployments": [
            _public_record(item)
            for item in _repo().list_records("deployment", limit=10)
        ],
        "drift_receipts": [
            _public_record(item) for item in _repo().list_records("drift", limit=10)
        ],
        "architecture": {
            "training": "SageMaker training job when configured; deterministic Lambda adapter otherwise",
            "registry": "SageMaker Model Registry integration seam plus durable Compass registry receipt",
            "deployment": "explicit champion promotion with immutable model artifact",
            "monitoring": "population stability and out-of-vocabulary drift receipts",
        },
    }


def _run_visible(claims: http.Claims, run: Mapping[str, Any]) -> bool:
    return claims.is_corporate or run.get("org_unit") == claims.org_unit


def _handle_api(event: Mapping[str, Any]) -> Dict[str, Any]:
    claims = http.get_claims(dict(event))
    if not claims.is_authenticated:
        return http.unauthorized()
    method = http.get_method(dict(event)) or ""
    path = http.get_path(dict(event)) or ""

    if method == "POST" and path.endswith("/documents/uploads"):
        if not _poweruser(claims):
            return http.forbidden(
                "document upload requires the corporate poweruser role"
            )
        return http.created(request_upload(claims, http.parse_body(dict(event))))

    if method == "GET" and path.endswith("/documents/runs"):
        runs = [
            _public_record(item)
            for item in _repo().list_records("run", limit=50)
            if _run_visible(claims, item)
        ]
        return http.ok({"runs": runs})

    run_match = re.search(r"/documents/runs/([^/]+)$", path)
    if method == "GET" and run_match:
        run = _repo().get_record("run", run_match.group(1))
        if not run or not _run_visible(claims, run):
            return http.not_found("document run not found")
        return http.ok(_public_record(run))

    if method == "POST" and path.endswith("/ml/train"):
        if not _poweruser(claims):
            return http.forbidden(
                "model training requires the corporate poweruser role"
            )
        result = train_model(claims, http.parse_body(dict(event)))
        return http.json_response(
            202 if result["status"] == "training" else 201, result
        )

    if method == "GET" and path.endswith("/ml/models"):
        models = [
            _public_record(item) for item in _repo().list_records("model", limit=50)
        ]
        return http.ok({"models": models, "champion": _repo().get_alias("champion")})

    deploy_match = re.search(r"/ml/models/([^/]+)/deploy$", path)
    if method == "POST" and deploy_match:
        if not _poweruser(claims):
            return http.forbidden(
                "model deployment requires the corporate poweruser role"
            )
        try:
            return http.created(deploy_model(claims, deploy_match.group(1)))
        except KeyError:
            return http.not_found("model version not found")
        except RuntimeError as exc:
            return http.error_response(409, str(exc))

    if method == "POST" and path.endswith("/ml/drift/evaluate"):
        if not _poweruser(claims):
            return http.forbidden(
                "drift evaluation requires the corporate poweruser role"
            )
        try:
            return http.created(evaluate_drift(claims, http.parse_body(dict(event))))
        except RuntimeError as exc:
            return http.error_response(409, str(exc))

    if method == "GET" and path.endswith("/ml/ops/evidence"):
        return http.ok(mlops_evidence())

    return http.not_found("unknown document or MLOps route")


def handler(event, context=None):
    event = event or {}
    try:
        action = event.get("action")
        if action == "inspect":
            return inspect_stage(event.get("event") or event)
        if action == "quality":
            return quality_stage(event)
        if action == "curate":
            return curate_stage(event)
        if action == "quarantine":
            return quarantine_stage(event)
        if action == "workflow_failure":
            return workflow_failure_stage(event)
        if (event.get("requestContext") or {}).get("http"):
            return _handle_api(event)
        if isinstance(event.get("detail"), Mapping):
            return inspect_stage(event)
        raise ValueError("unrecognized document ML event")
    except ValueError as exc:
        if (event.get("requestContext") or {}).get("http"):
            return http.bad_request(str(exc))
        raise
    except Exception:
        logger.exception("document ML handler failed")
        if (event.get("requestContext") or {}).get("http"):
            return http.server_error()
        raise

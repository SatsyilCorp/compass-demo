"""Deterministic document extraction, quality, classification, and drift logic.

This module is intentionally free of AWS calls. The Lambda handler uses it in
the AWS-native pipeline, and the local rehearsal script uses the exact same
implementation. That seam lets a presenter prove the business behavior even
when a SageMaker execution role or training image has not been configured.

The classifier is a classical multinomial Naive Bayes model implemented with
the Python standard library. It is small enough to inspect during a demo, has
no generative behavior, and serializes to a portable JSON artifact.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from defusedxml import ElementTree


MODEL_CONTRACT = "compass.document-classifier.v1"
PIPELINE_CONTRACT = "compass.document-pipeline.v1"
DOCUMENT_TAXONOMY = (
    "grant_abstract",
    "technical_report",
    "publication_summary",
    "patent_summary",
    "investment_brief",
    "financial_execution",
)
TRAINING_SPLIT_SEED = 20260811
REVIEW_THRESHOLD = 0.62
PROMOTION_MIN_ACCURACY = 0.90
PROMOTION_MIN_MACRO_F1 = 0.88
SUPPORTED_SUFFIXES = (
    ".csv",
    ".docx",
    ".json",
    ".jsonl",
    ".md",
    ".pdf",
    ".txt",
    ".xlsx",
    ".xml",
)
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
MIN_EXTRACTED_CHARACTERS = 30
TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]{2,}", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")


@dataclass(frozen=True)
class TrainingSample:
    text: str
    label: str
    sample_id: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def tokenize(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _flatten_strings(
    value: Any, *, path: str = "", rows: List[Dict[str, Any]] | None = None
) -> List[str]:
    strings: List[str] = []
    if isinstance(value, Mapping):
        if rows is not None:
            rows.append(
                {"path": path or "$", "fields": sorted(str(key) for key in value)}
            )
        for key in sorted(value, key=str):
            child = f"{path}.{key}" if path else str(key)
            strings.extend(_flatten_strings(value[key], path=child, rows=rows))
    elif isinstance(value, list):
        for index, child_value in enumerate(value):
            strings.extend(
                _flatten_strings(child_value, path=f"{path}[{index}]", rows=rows)
            )
    elif value not in (None, ""):
        strings.append(str(value))
    return strings


def _extract_json(payload: bytes, *, lines: bool) -> Tuple[str, Dict[str, Any]]:
    text = payload.decode("utf-8")
    values: List[Any]
    if lines:
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
        parsed: Any = values
    else:
        parsed = json.loads(text)
        values = parsed if isinstance(parsed, list) else [parsed]
    schemas: List[Dict[str, Any]] = []
    strings = _flatten_strings(parsed, rows=schemas)
    top_fields = sorted(
        {str(key) for value in values if isinstance(value, Mapping) for key in value}
    )
    return "\n".join(strings), {
        "shape": "records" if isinstance(parsed, list) else "object",
        "record_count": len(values),
        "fields": top_fields,
        "schema_samples": schemas[:10],
    }


def _extract_csv(payload: bytes) -> Tuple[str, Dict[str, Any]]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    fields = [str(field) for field in (reader.fieldnames or [])]
    values = [
        str(value) for row in rows for value in row.values() if value not in (None, "")
    ]
    searchable = fields + values
    return "\n".join(searchable), {
        "shape": "tabular",
        "record_count": len(rows),
        "fields": fields,
    }


def _extract_xml(payload: bytes) -> Tuple[str, Dict[str, Any]]:
    root = ElementTree.fromstring(payload)
    tags = sorted({element.tag.rsplit("}", 1)[-1] for element in root.iter()})
    values = [part.strip() for part in root.itertext() if part and part.strip()]
    return "\n".join(values), {
        "shape": "xml",
        "record_count": max(1, len(list(root))),
        "fields": tags,
    }


def _extract_docx(payload: bytes) -> Tuple[str, Dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    text = " ".join(part.strip() for part in root.itertext() if part and part.strip())
    return text, {"shape": "unstructured", "record_count": 1, "fields": []}


def _extract_xlsx(payload: bytes) -> Tuple[str, Dict[str, Any]]:
    try:
        import openpyxl
    except ImportError as exc:
        raise ValueError(
            "XLSX extraction requires the packaged openpyxl dependency"
        ) from exc
    workbook = openpyxl.load_workbook(
        io.BytesIO(payload), read_only=True, data_only=True
    )
    values: List[str] = []
    sheets: Dict[str, Dict[str, Any]] = {}
    for sheet in workbook.worksheets:
        rows = 0
        width = 0
        headers: List[str] = []
        for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
            present = [value for value in row if value not in (None, "")]
            if not present:
                continue
            rows += 1
            width = max(width, len(row))
            if row_index == 0:
                headers = [str(value) for value in row if value not in (None, "")]
            values.extend(str(value) for value in present)
        sheets[sheet.title] = {"rows": rows, "columns": width, "headers": headers}
    return "\n".join(values), {
        "shape": "workbook",
        "record_count": sum(item["rows"] for item in sheets.values()),
        "fields": sorted(
            {header for item in sheets.values() for header in item["headers"]}
        ),
        "sheets": sheets,
    }


def _extract_pdf(payload: bytes) -> Tuple[str, Dict[str, Any]]:
    if not payload.startswith(b"%PDF"):
        raise ValueError("file extension says PDF but the PDF signature is absent")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError(
            "PDF extraction requires the packaged pypdf dependency"
        ) from exc
    reader = PdfReader(io.BytesIO(payload))
    if reader.is_encrypted:
        raise ValueError("encrypted PDFs require a controlled decryption workflow")
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n".join(page for page in pages if page), {
        "shape": "unstructured",
        "record_count": len(reader.pages),
        "fields": [],
        "pages": len(reader.pages),
    }


def extract_document(
    filename: str, content_type: str, payload: bytes
) -> Dict[str, Any]:
    """Inspect a document and return portable extracted metadata and text."""
    suffix = PurePosixPath(filename.lower()).suffix
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported document extension {suffix or '<none>'}")
    if not payload:
        raise ValueError("document is empty")
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"document exceeds the {MAX_DOCUMENT_BYTES}-byte limit")

    if suffix in (".txt", ".md"):
        text = payload.decode("utf-8")
        schema = {"shape": "unstructured", "record_count": 1, "fields": []}
    elif suffix in (".json", ".jsonl"):
        text, schema = _extract_json(payload, lines=suffix == ".jsonl")
    elif suffix == ".csv":
        text, schema = _extract_csv(payload)
    elif suffix == ".xml":
        text, schema = _extract_xml(payload)
    elif suffix == ".docx":
        text, schema = _extract_docx(payload)
    elif suffix == ".xlsx":
        text, schema = _extract_xlsx(payload)
    else:
        text, schema = _extract_pdf(payload)

    normalized_text = "\n".join(
        line.strip() for line in text.splitlines() if line.strip()
    )
    pii = {
        "email": len(EMAIL_RE.findall(normalized_text)),
        "ssn_pattern": len(SSN_RE.findall(normalized_text)),
        "phone": len(PHONE_RE.findall(normalized_text)),
    }
    return {
        "contract": PIPELINE_CONTRACT,
        "filename": PurePosixPath(filename).name,
        "suffix": suffix,
        "declared_content_type": content_type or "application/octet-stream",
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "schema": schema,
        "extracted_text": normalized_text,
        "extracted_characters": len(normalized_text),
        "token_count": len(tokenize(normalized_text)),
        "sensitive_pattern_counts": pii,
        "classification_marking": "CUI-Mock" if any(pii.values()) else "Public-Mock",
    }


def quality_receipt(extracted: Mapping[str, Any]) -> Dict[str, Any]:
    rules = [
        {
            "id": "supported-format",
            "passed": extracted.get("suffix") in SUPPORTED_SUFFIXES,
            "blocking": True,
        },
        {
            "id": "object-size",
            "passed": 0 < int(extracted.get("bytes") or 0) <= MAX_DOCUMENT_BYTES,
            "blocking": True,
        },
        {
            "id": "extractable-content",
            "passed": int(extracted.get("extracted_characters") or 0)
            >= MIN_EXTRACTED_CHARACTERS,
            "blocking": True,
        },
        {
            "id": "schema-or-text-detected",
            "passed": bool((extracted.get("schema") or {}).get("shape")),
            "blocking": True,
        },
        {
            "id": "sensitive-pattern-tagging",
            "passed": isinstance(extracted.get("sensitive_pattern_counts"), Mapping),
            "blocking": False,
        },
    ]
    passed = sum(1 for rule in rules if rule["passed"])
    blocking_failures = [
        rule["id"] for rule in rules if rule["blocking"] and not rule["passed"]
    ]
    return {
        "contract": "compass.document-quality-receipt.v1",
        "gate": "quarantine" if blocking_failures else "pass",
        "score": round(100.0 * passed / len(rules), 2),
        "rules": rules,
        "blocking_failures": blocking_failures,
    }


def default_training_samples() -> List[TrainingSample]:
    """Small domain-relevant corpus used by the deterministic demo adapter."""
    rows = {
        "grant_abstract": [
            "Grant abstract investigates autonomous maritime navigation and resilient sensing.",
            "University grant award funds basic research in undersea acoustic communications.",
            "Principal investigator proposes a science study of advanced battery materials.",
            "Research grant describes hypothesis, milestones, academic performer, and funding period.",
            "Basic research award supports quantum sensing experiments and investigator outcomes.",
            "Cooperative grant evaluates bio-inspired coatings for naval platforms.",
        ],
        "technical_report": [
            "Technical report documents test objectives, laboratory configuration, measured performance, and findings.",
            "Engineering evaluation report records prototype requirements, verification results, and limitations.",
            "Operational assessment describes test events, system performance, defects, and corrective actions.",
            "Technical report summarizes simulation configuration, benchmark measurements, and recommendations.",
            "Verification report compares threshold requirements with observed platform performance.",
            "Laboratory technical report presents test procedures, measurements, results, and lessons learned.",
        ],
        "publication_summary": [
            "Publication summary covers a peer reviewed paper with methods, citations, and conclusions.",
            "Journal article summary explains scientific methodology, experimental results, and references.",
            "Conference manuscript summary presents an algorithm, related work, and future research.",
            "Literature review summary synthesizes scientific findings and cites prior publications.",
            "Research article abstract describes authors, methods, findings, and journal references.",
            "Publication summary highlights peer review, citations, scientific contribution, and conclusions.",
        ],
        "patent_summary": [
            "Patent summary describes claims, inventors, assignee, filing date, and prior art.",
            "Invention disclosure summarizes patent claims for a novel sensor and prosecution status.",
            "Patent application profile records inventor, assignee, classification code, and cited art.",
            "Intellectual property summary explains independent claims and technology ownership.",
            "Patent landscape entry tracks application number, filing family, claims, and assignee.",
            "Invention patent summary covers novelty, claims, inventors, and prior art references.",
        ],
        "investment_brief": [
            "Investment brief tracks startup financing round, valuation, investors, and market sector.",
            "Venture funding brief lists company stage, capital raised, and commercial technology.",
            "Portfolio investment memo assesses growth, market traction, risk, and exit potential.",
            "Startup brief records seed investment, lead investor, and company valuation.",
            "Commercial investment analysis compares capital, revenue growth, and technology readiness.",
            "Investment brief describes funding round, ownership, and dual-use market opportunity.",
        ],
        "financial_execution": [
            "Financial execution record compares budget authority, obligations, expenditures, and remaining balance.",
            "Program funding report tracks planned amount, obligated funds, disbursements, and variance.",
            "Fiscal execution summary records appropriation, commitment, obligation, expenditure, and burn rate.",
            "Budget execution table compares monthly plan, actual spending, variance, and forecast.",
            "Financial status report lists fiscal year funding, obligations, outlays, and available balance.",
            "Execution brief analyzes budget, obligated amount, expenditure rate, and funding variance.",
        ],
    }
    return [
        TrainingSample(text=text, label=label, sample_id=f"{label}-{index + 1}")
        for label, texts in rows.items()
        for index, text in enumerate(texts)
    ]


def split_samples(
    samples: Sequence[TrainingSample],
    *,
    seed: int = TRAINING_SPLIT_SEED,
) -> Tuple[List[TrainingSample], List[TrainingSample]]:
    grouped: Dict[str, List[TrainingSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.label].append(sample)
    train: List[TrainingSample] = []
    test: List[TrainingSample] = []
    for label in sorted(grouped):
        ordered = sorted(
            grouped[label],
            key=lambda item: hashlib.sha256(
                f"{seed}:{item.sample_id}:{item.text}".encode("utf-8")
            ).hexdigest(),
        )
        if len(ordered) < 2:
            raise ValueError(f"label {label!r} requires at least two samples")
        test.append(ordered[-1])
        train.extend(ordered[:-1])
    return train, test


def train_classifier(
    samples: Sequence[TrainingSample], *, alpha: float = 1.0
) -> Dict[str, Any]:
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    observed_labels = {sample.label for sample in samples}
    unknown_labels = observed_labels.difference(DOCUMENT_TAXONOMY)
    if unknown_labels:
        raise ValueError(
            "training contains unsupported labels: " + ", ".join(sorted(unknown_labels))
        )
    labels = [label for label in DOCUMENT_TAXONOMY if label in observed_labels]
    if len(labels) < 2:
        raise ValueError("training requires at least two labels")
    class_docs: Counter[str] = Counter()
    token_counts: Dict[str, Counter[str]] = {label: Counter() for label in labels}
    vocabulary: set[str] = set()
    digest_rows = []
    for sample in sorted(
        samples, key=lambda item: (item.label, item.sample_id, item.text)
    ):
        tokens = tokenize(sample.text)
        if not tokens:
            raise ValueError(
                f"training sample {sample.sample_id or '<unnamed>'} has no tokens"
            )
        class_docs[sample.label] += 1
        token_counts[sample.label].update(tokens)
        vocabulary.update(tokens)
        digest_rows.append(
            {"id": sample.sample_id, "label": sample.label, "text": sample.text}
        )
    digest = hashlib.sha256(stable_json(digest_rows).encode("utf-8")).hexdigest()
    return {
        "contract": MODEL_CONTRACT,
        "model_version": f"doc-nb-{digest[:12]}",
        "algorithm": "multinomial-naive-bayes",
        "taxonomy": list(DOCUMENT_TAXONOMY),
        "training_split_seed": TRAINING_SPLIT_SEED,
        "alpha": float(alpha),
        "labels": labels,
        "vocabulary": sorted(vocabulary),
        "class_document_counts": dict(class_docs),
        "token_counts": {label: dict(token_counts[label]) for label in labels},
        "token_totals": {label: sum(token_counts[label].values()) for label in labels},
        "training_document_count": len(samples),
        "training_digest": digest,
    }


def predict(model: Mapping[str, Any], text: str) -> Dict[str, Any]:
    tokens = tokenize(text)
    labels = list(model["labels"])
    total_docs = sum(int(value) for value in model["class_document_counts"].values())
    vocabulary_size = max(1, len(model["vocabulary"]))
    alpha = float(model.get("alpha", 1.0))
    scores: Dict[str, float] = {}
    for label in labels:
        class_docs = int(model["class_document_counts"][label])
        score = math.log(class_docs / total_docs)
        counts = model["token_counts"][label]
        denominator = float(model["token_totals"][label]) + alpha * vocabulary_size
        for token, count in Counter(tokens).items():
            likelihood = (float(counts.get(token, 0)) + alpha) / denominator
            score += count * math.log(likelihood)
        scores[label] = score
    best = max(scores, key=scores.get)
    peak = max(scores.values())
    exp_scores = {label: math.exp(value - peak) for label, value in scores.items()}
    normalizer = sum(exp_scores.values()) or 1.0
    probabilities = {label: exp_scores[label] / normalizer for label in labels}
    return {
        "label": best,
        "confidence": round(probabilities[best], 6),
        "review_required": probabilities[best] < REVIEW_THRESHOLD,
        "probabilities": {label: round(probabilities[label], 6) for label in labels},
        "token_count": len(tokens),
    }


def evaluate_classifier(
    model: Mapping[str, Any], samples: Sequence[TrainingSample]
) -> Dict[str, Any]:
    labels = list(model["labels"])
    matrix = {actual: {predicted: 0 for predicted in labels} for actual in labels}
    predictions = []
    for sample in samples:
        result = predict(model, sample.text)
        matrix[sample.label][result["label"]] += 1
        predictions.append(
            {
                "sample_id": sample.sample_id,
                "actual": sample.label,
                "predicted": result["label"],
                "confidence": result["confidence"],
            }
        )
    per_class: Dict[str, Dict[str, float | int]] = {}
    for label in labels:
        true_positive = matrix[label][label]
        false_positive = sum(
            matrix[actual][label] for actual in labels if actual != label
        )
        false_negative = sum(
            matrix[label][predicted] for predicted in labels if predicted != label
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        per_class[label] = {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "support": sum(matrix[label].values()),
        }
    correct = sum(matrix[label][label] for label in labels)
    total = len(samples)
    return {
        "evaluation_document_count": total,
        "accuracy": round(correct / total, 6) if total else 0.0,
        "macro_f1": round(
            sum(float(per_class[label]["f1"]) for label in labels) / len(labels), 6
        ),
        "confusion_matrix": matrix,
        "per_class": per_class,
        "predictions": predictions,
    }


def train_and_evaluate(
    samples: Sequence[TrainingSample],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    train, test = split_samples(samples)
    model = train_classifier(train)
    metrics = evaluate_classifier(model, test)
    metrics["training_document_count"] = len(train)
    metrics["training_split_seed"] = TRAINING_SPLIT_SEED
    metrics["evaluation_strategy"] = "one deterministic holdout per class"
    metrics["dataset_digest"] = hashlib.sha256(
        stable_json(
            [
                {"id": sample.sample_id, "label": sample.label, "text": sample.text}
                for sample in sorted(
                    samples, key=lambda item: (item.label, item.sample_id, item.text)
                )
            ]
        ).encode("utf-8")
    ).hexdigest()
    return model, metrics


def _distribution(labels: Iterable[str], allowed: Sequence[str]) -> Dict[str, float]:
    counts = Counter(labels)
    total = sum(counts.values())
    if not total:
        return {label: 0.0 for label in allowed}
    return {label: counts[label] / total for label in allowed}


def _psi(reference: Mapping[str, float], current: Mapping[str, float]) -> float:
    epsilon = 1e-6
    return sum(
        (max(current.get(key, 0.0), epsilon) - max(reference.get(key, 0.0), epsilon))
        * math.log(
            max(current.get(key, 0.0), epsilon) / max(reference.get(key, 0.0), epsilon)
        )
        for key in reference
    )


def drift_receipt(
    model: Mapping[str, Any],
    documents: Sequence[str],
    *,
    threshold: float = 0.25,
) -> Dict[str, Any]:
    if not 0 < threshold <= 1:
        raise ValueError("drift threshold must be in (0, 1]")
    labels = list(model["labels"])
    predictions = [predict(model, text) for text in documents]
    reference = _distribution(
        [
            label
            for label, count in model["class_document_counts"].items()
            for _ in range(int(count))
        ],
        labels,
    )
    current = _distribution([item["label"] for item in predictions], labels)
    vocabulary = set(model["vocabulary"])
    tokens = [token for text in documents for token in tokenize(text)]
    oov = sum(1 for token in tokens if token not in vocabulary)
    oov_rate = oov / len(tokens) if tokens else 1.0
    population_stability_index = _psi(reference, current)
    score = min(1.0, 0.7 * min(population_stability_index, 1.0) + 0.3 * oov_rate)
    return {
        "contract": "compass.model-drift-receipt.v1",
        "model_version": model["model_version"],
        "documents_observed": len(documents),
        "tokens_observed": len(tokens),
        "reference_label_distribution": {
            key: round(value, 6) for key, value in reference.items()
        },
        "observed_label_distribution": {
            key: round(value, 6) for key, value in current.items()
        },
        "population_stability_index": round(population_stability_index, 6),
        "out_of_vocabulary_rate": round(oov_rate, 6),
        "drift_score": round(score, 6),
        "threshold": threshold,
        "drift_detected": score >= threshold,
        "recommended_action": "retrain-and-review"
        if score >= threshold
        else "continue-monitoring",
    }

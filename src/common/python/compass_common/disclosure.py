"""Safe product projections for infrastructure-backed evidence."""

from __future__ import annotations

from pathlib import PurePosixPath
import re
from typing import Any, Dict
from urllib.parse import unquote, urlsplit


_SAFE_LABEL = re.compile(r"[^A-Za-z0-9._-]+")
_LINEAGE_META_ALLOWLIST = frozenset(
    {
        "anomalies_flagged",
        "batch_id",
        "decision",
        "duplicates_skipped",
        "embedded_rows",
        "flagged",
        "grant_topic_rows",
        "inserted",
        "k",
        "n_docs",
        "org_units",
        "overall_score",
        "record_count",
        "reconstruction_error",
        "retention",
        "rls",
        "rows",
        "rows_checked",
        "rows_failed",
        "rows_held",
        "rows_normalized_clean",
        "rows_passed",
        "rule_evaluation_score",
        "rules",
        "schema_variant",
        "score_formula",
        "threshold",
        "updated",
    }
)
_AUDIT_NUMBER_FIELDS = frozenset(
    {"approval_id", "bytes", "limit", "matched_rows", "max_rows", "requested_rows", "row_count"}
)
_AUDIT_BOOLEAN_FIELDS = frozenset(
    {"approval_used", "four_eyes_enforced", "guard_tripped", "self_approved", "token_issued"}
)
_AUDIT_TEXT_FIELDS = frozenset(
    {"code", "decision", "effective_format", "format", "query_fingerprint", "status", "subject_id"}
)


def safe_label(value: Any, fallback: str = "source", max_length: int = 120) -> str:
    """Return a bounded display label without paths or control characters."""
    cleaned = _SAFE_LABEL.sub("-", str(value or "").strip()).strip("-.")
    return (cleaned or fallback)[:max_length]


def logical_source_locator(source: Any) -> str:
    """Project a physical object locator to a stable logical landing label."""
    text = str(source or "").strip()
    parsed = urlsplit(text)
    path = parsed.path if parsed.scheme else text
    filename = PurePosixPath(unquote(path)).name
    return f"landing://drops/{safe_label(filename)}"


def logical_curated_locator(batch_id: Any) -> str:
    """Describe seed-loaded data without inventing a physical bucket."""
    return f"curated://seed/{safe_label(batch_id, fallback='batch')}"


def _safe_meta_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if "s3://" in lowered or "arn:" in lowered:
            return "[restricted locator]"
        return value[:240]
    if isinstance(value, (list, tuple)):
        return [_safe_meta_value(item) for item in value[:20]]
    return str(value)[:240]


def safe_lineage_meta(meta: Any) -> Dict[str, Any]:
    """Allowlist evidence fields and discard storage or raw-record metadata."""
    if not isinstance(meta, dict):
        return {}
    return {
        key: _safe_meta_value(value)
        for key, value in meta.items()
        if key in _LINEAGE_META_ALLOWLIST
    }


def safe_lineage_node(
    *,
    run_id: Any,
    node_id: Any,
    kind: Any,
    label: Any,
    meta: Any,
) -> Dict[str, Any]:
    """Shape one node for the product without physical infrastructure data."""
    node_kind = str(kind or "stage")
    node_label = (
        logical_source_locator(label)
        if node_kind == "source"
        else str(label or node_id or "Workflow stage")[:240]
    )
    return {
        "run_id": str(run_id),
        "node_id": str(node_id),
        "kind": node_kind,
        "label": node_label,
        "meta": safe_lineage_meta(meta),
    }


def safe_audit_detail(value: Any) -> Dict[str, Any]:
    """Project producer receipts to nonsecret evidence fields."""
    if not isinstance(value, dict):
        return {}
    result: Dict[str, Any] = {}
    for key in _AUDIT_NUMBER_FIELDS:
        item = value.get(key)
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            result[key] = item
    for key in _AUDIT_BOOLEAN_FIELDS:
        item = value.get(key)
        if isinstance(item, bool):
            result[key] = item
    for key in _AUDIT_TEXT_FIELDS:
        item = value.get(key)
        if not isinstance(item, str):
            continue
        if key == "subject_id":
            if re.fullmatch(r"exp-[0-9a-fA-F]{16}", item):
                result[key] = item.lower()
        elif key == "query_fingerprint":
            result[key] = item[:16]
        else:
            result[key] = item[:48]
    return result

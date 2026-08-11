"""Parse a dropped grants file and normalize it to the curated schema.

Pure functions only - no AWS, no database, no imports beyond the stdlib - so
this module is directly runnable (``python3 normalize.py`` runs its self-test)
and the ingest Lambda's most fiddly logic is testable offline.

What it handles
---------------
**Envelope shapes.** A drop is either the envelope
``{"source_file","batch_id","schema_variant","records":[...]}`` that
``scripts/seed_data.py`` writes, a bare JSON array of records, or JSON Lines
(one record per line - the ``.jsonl`` form the catalog's ``source_file`` values
advertise).

**Field aliases.** Real exporters rename columns. Every canonical field has an
alias list; the first entry is the canonical name (see ``FIELD_ALIASES``). The
compatible variant fixture exercises all of them
(``award_id`` → ``grant_no``, ``portfolio_area`` → ``program_area``, …), and
fields with no canonical counterpart (``source_system``) are dropped from the
normalized record while remaining in ``grants_raw`` verbatim.

**Strict canonical, lenient aliases.** This is the deliberate rule that makes
the demo's quality story honest: a value under a *canonical* name must already
be the canonical type, while a value under an *alias* gets the documented
adapter transform. So ``fy: "FY2026"`` normalizes to ``2026`` (the legacy
exporter's known format) but ``fiscal_year: "FY2026"`` is a type violation the
quality gate must catch - which is exactly how ``seed/SYNTHETIC-DATA-MANIFEST.md``
labels those two rows. Same for money: ``obligated_amount_usd: "$6,429,000.00"``
parses; ``amount_usd: "TBD"`` does not.

**Issue codes, not silent repair.** Normalization never invents a value. A
field that is absent/null/blank yields ``missing``; a field that is present but
uncoercible yields ``invalid_type`` and keeps the offending raw value. The
quality gate (``quality_gate/rules.py``) consumes those codes so each failure is
attributed to the right rule with a precise reason.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Canonical field first, then accepted aliases.
FIELD_ALIASES: Dict[str, Tuple[str, ...]] = {
    "grant_no": ("grant_no", "award_id", "award_number", "grant_number", "award_no"),
    "title": ("title", "project_title", "award_title"),
    "abstract": ("abstract", "summary", "description", "project_abstract"),
    "program_area": ("program_area", "portfolio_area", "program", "research_area"),
    "fiscal_year": ("fiscal_year", "fy", "award_fy"),
    "amount_usd": ("amount_usd", "obligated_amount_usd", "amount", "award_amount"),
    "awardee": ("awardee", "performer_org", "recipient", "performer"),
    "org_unit": ("org_unit", "command_code", "code", "owning_unit"),
    "classification_band": ("classification_band", "marking", "classification"),
    "created_at": ("created_at", "award_date", "start_date"),
}

CANONICAL_FIELDS: Tuple[str, ...] = tuple(FIELD_ALIASES)

# Fields ``grants_curated`` declares NOT NULL (plus awardee, which the portfolio
# treats as mandatory provenance). ``abstract`` and ``created_at`` are optional.
REQUIRED_FIELDS: Tuple[str, ...] = (
    "grant_no",
    "title",
    "program_area",
    "fiscal_year",
    "amount_usd",
    "awardee",
    "org_unit",
)

TEXT_FIELDS = ("grant_no", "title", "abstract", "program_area", "awardee", "org_unit",
               "classification_band")

# Conservative default: an unmarked record is treated as controlled, not open.
DEFAULT_CLASSIFICATION_BAND = "CUI-Mock"

_FY_RE = re.compile(r"^\s*(?:fy)?\s*(\d{4})\s*$", re.IGNORECASE)
_MONEY_STRIP = str.maketrans({"$": None, ",": None, " ": None, " ": None})


# --------------------------------------------------------------------------- #
# Field issues
# --------------------------------------------------------------------------- #
@dataclass
class FieldIssue:
    """Why a field did not normalize. ``code`` is ``missing`` or ``invalid_type``."""

    field: str
    code: str
    detail: str
    raw: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "code": self.code,
            "detail": self.detail,
            "raw": _jsonable(self.raw),
        }


def _jsonable(value: Any) -> Any:
    """Shrink an arbitrary raw value to something safe to store in jsonb."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:200]
    try:
        return json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return str(value)[:200]


# --------------------------------------------------------------------------- #
# Coercion
# --------------------------------------------------------------------------- #
def coerce_year(value: Any, *, lenient: bool) -> Tuple[Optional[int], Optional[str]]:
    """Coerce a fiscal year. ``lenient`` (alias source) also accepts ``"FY2026"``."""
    if isinstance(value, bool):
        return None, "expected an integer year, got a boolean"
    if isinstance(value, int):
        return value, None
    if isinstance(value, float):
        if float(value).is_integer():
            return int(value), None
        return None, f"expected an integer year, got {value!r}"
    if isinstance(value, str):
        if not lenient:
            return None, f"expected an integer year, got the string {value!r}"
        m = _FY_RE.match(value)
        if m:
            return int(m.group(1)), None
        return None, f"cannot parse a fiscal year from {value!r}"
    return None, f"expected an integer year, got {type(value).__name__}"


def coerce_amount(value: Any, *, lenient: bool) -> Tuple[Optional[float], Optional[str]]:
    """Coerce a USD amount. ``lenient`` (alias source) also accepts ``"$1,234.00"``."""
    if isinstance(value, bool):
        return None, "expected a number, got a boolean"
    if isinstance(value, (int, float)):
        return float(value), None
    if isinstance(value, str):
        if not lenient:
            return None, f"expected a number, got the string {value!r}"
        cleaned = value.translate(_MONEY_STRIP)
        try:
            return float(cleaned), None
        except ValueError:
            return None, f"cannot parse a dollar amount from {value!r}"
    return None, f"expected a number, got {type(value).__name__}"


def coerce_text(value: Any) -> Tuple[Optional[str], Optional[str]]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped, None) if stripped else (None, "empty string")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value), None
    return None, f"expected a string, got {type(value).__name__}"


def coerce_timestamp(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """Keep an ISO-8601 timestamp as text; Postgres casts it on insert."""
    if not isinstance(value, str) or not value.strip():
        return None, None if value in (None, "") else "expected an ISO-8601 string"
    text = value.strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, f"not an ISO-8601 timestamp: {text!r}"
    return text, None


# --------------------------------------------------------------------------- #
# Record normalization
# --------------------------------------------------------------------------- #
@dataclass
class NormalizedRecord:
    row_index: int
    record: Dict[str, Any]                       # verbatim source record
    normalized: Dict[str, Any] = field(default_factory=dict)
    issues: List[FieldIssue] = field(default_factory=list)
    matched_keys: Dict[str, str] = field(default_factory=dict)  # canonical -> source key

    def issue_codes(self) -> Dict[str, str]:
        return {i.field: i.code for i in self.issues}

    def to_jsonb(self, *, meta: Dict[str, Any]) -> Dict[str, Any]:
        """The ``grants_raw.raw_jsonb`` envelope.

        ``record`` is the source row untouched (the landing zone stays a true
        landing zone); ``normalized`` and ``meta`` sit beside it so the quality
        gate and persist stages never have to re-parse the source. The quality
        gate later adds a ``quality`` key to this same object.
        """
        return {
            "record": self.record,
            "normalized": self.normalized,
            "meta": {
                **meta,
                "row_index": self.row_index,
                "matched_keys": self.matched_keys,
                "issues": [i.to_dict() for i in self.issues],
            },
        }


def _lookup(record: Dict[str, Any], canonical: str) -> Tuple[Optional[str], Any]:
    """Find the first alias present on the record. Returns (source_key, value)."""
    for key in FIELD_ALIASES[canonical]:
        if key in record:
            return key, record[key]
    # Case-insensitive second pass - exporters love SHOUTING columns.
    lowered = {str(k).lower(): k for k in record}
    for key in FIELD_ALIASES[canonical]:
        actual = lowered.get(key)
        if actual is not None:
            return actual, record[actual]
    return None, None


def normalize_record(record: Any, row_index: int = 0) -> NormalizedRecord:
    """Map one source record onto the curated schema, recording every issue."""
    if not isinstance(record, dict):
        out = NormalizedRecord(row_index=row_index, record={"_unparseable": _jsonable(record)})
        out.issues.append(
            FieldIssue("record", "invalid_type", f"expected a JSON object, got {type(record).__name__}", record)
        )
        return out

    out = NormalizedRecord(row_index=row_index, record=record)
    for canonical in CANONICAL_FIELDS:
        source_key, value = _lookup(record, canonical)
        if source_key is None or value is None:
            if canonical == "classification_band":
                out.normalized[canonical] = DEFAULT_CLASSIFICATION_BAND
                continue
            if canonical in REQUIRED_FIELDS:
                out.issues.append(
                    FieldIssue(
                        canonical,
                        "missing",
                        "field absent" if source_key is None else f"field {source_key!r} is null",
                        None,
                    )
                )
            out.normalized[canonical] = None
            continue

        out.matched_keys[canonical] = source_key
        lenient = source_key != FIELD_ALIASES[canonical][0]

        if canonical == "fiscal_year":
            coerced, err = coerce_year(value, lenient=lenient)
        elif canonical == "amount_usd":
            coerced, err = coerce_amount(value, lenient=lenient)
        elif canonical == "created_at":
            coerced, err = coerce_timestamp(value)
        else:
            coerced, err = coerce_text(value)

        out.normalized[canonical] = coerced
        if err:
            code = "missing" if err == "empty string" else "invalid_type"
            out.issues.append(FieldIssue(canonical, code, err, value))

    if not out.normalized.get("classification_band"):
        out.normalized["classification_band"] = DEFAULT_CLASSIFICATION_BAND
    return out


# --------------------------------------------------------------------------- #
# Envelope parsing
# --------------------------------------------------------------------------- #
@dataclass
class Envelope:
    batch_id: str
    source_file: str
    schema_variant: str
    records: List[Any]
    parse_errors: List[str] = field(default_factory=list)
    envelope_keys: Dict[str, Any] = field(default_factory=dict)


def infer_schema_variant(records: List[Any]) -> str:
    """Name the incoming shape from the keys actually present."""
    for rec in records:
        if isinstance(rec, dict):
            if "grant_no" in rec:
                return "canonical"
            if any(k in rec for k in ("award_id", "project_title", "portfolio_area")):
                return "compatible-renamed"
            return "unknown"
    return "empty"


def derive_batch_id(key: str) -> str:
    """Deterministic batch id from an object key, so re-dropping a file re-runs
    the *same* batch instead of forking a duplicate one."""
    stem = key.rsplit("/", 1)[-1]
    for suffix in (".jsonl", ".ndjson", ".json"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower() or "drop"
    return f"batch-{slug}"


def parse_drop(text: str, *, key: str = "", source_file: str = "") -> Envelope:
    """Parse a dropped file (envelope JSON, JSON array, or JSON Lines)."""
    parse_errors: List[str] = []
    records: List[Any] = []
    envelope_keys: Dict[str, Any] = {}
    is_lines = key.lower().endswith((".jsonl", ".ndjson"))

    parsed: Any = None
    if not is_lines:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            parse_errors.append(f"not valid JSON ({exc}); retrying as JSON Lines")
            is_lines = True

    if is_lines:
        for lineno, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                parse_errors.append(f"line {lineno}: {exc}")
    elif isinstance(parsed, dict):
        for container in ("records", "grants", "items", "data"):
            if isinstance(parsed.get(container), list):
                records = parsed[container]
                break
        else:
            # A single record dropped on its own.
            records = [parsed]
        envelope_keys = {k: v for k, v in parsed.items() if not isinstance(v, (list, dict))}
    elif isinstance(parsed, list):
        records = parsed
    else:
        parse_errors.append(f"unsupported top-level JSON type {type(parsed).__name__}")

    batch_id = str(envelope_keys.get("batch_id") or "").strip()
    if not batch_id:
        for rec in records:
            if isinstance(rec, dict) and rec.get("batch_id"):
                batch_id = str(rec["batch_id"]).strip()
                break
    if not batch_id:
        batch_id = derive_batch_id(key)

    variant = str(envelope_keys.get("schema_variant") or "").strip() or infer_schema_variant(records)
    resolved_source = (
        source_file or str(envelope_keys.get("source_file") or "").strip() or key
    )
    return Envelope(
        batch_id=batch_id,
        source_file=resolved_source,
        schema_variant=variant,
        records=records,
        parse_errors=parse_errors,
        envelope_keys=envelope_keys,
    )


def normalize_envelope(envelope: Envelope) -> List[NormalizedRecord]:
    return [normalize_record(r, i) for i, r in enumerate(envelope.records)]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Self-test - `python3 normalize.py`
# --------------------------------------------------------------------------- #
def _selftest() -> None:
    canonical = {
        "grant_no": "ONRD-2026-BIOT-D1-00401",
        "title": "Adaptive Hull Coatings",
        "abstract": "…",
        "program_area": "Biotech",
        "fiscal_year": 2026,
        "amount_usd": 927000,
        "awardee": "Cascade Advanced Systems Group",
        "org_unit": "Code-30",
        "classification_band": "Public-Mock",
    }
    n = normalize_record(canonical)
    assert not n.issues, n.issues
    assert n.normalized["fiscal_year"] == 2026
    assert n.normalized["amount_usd"] == 927000.0

    variant = {
        "award_id": "ONRD-2026-AUTO-D2-00442",
        "project_title": "Behavior-tree mission planning",
        "summary": "…",
        "portfolio_area": "Autonomy",
        "fy": "FY2026",
        "obligated_amount_usd": "$6,429,000.00",
        "performer_org": "Summit Systems, Inc.",
        "command_code": "Code-30",
        "marking": "CUI-Mock",
        "source_system": "Legacy-GMS-Export",
    }
    v = normalize_record(variant)
    assert not v.issues, v.issues
    assert v.normalized["fiscal_year"] == 2026
    assert v.normalized["amount_usd"] == 6429000.0
    assert v.normalized["grant_no"] == "ONRD-2026-AUTO-D2-00442"
    assert "source_system" not in v.normalized  # extra field dropped …
    assert v.record["source_system"] == "Legacy-GMS-Export"  # … but preserved raw

    # Strict canonical: the same string that is valid under `fy` is a defect
    # under `fiscal_year` (seed/SYNTHETIC-DATA-MANIFEST.md defect ledger).
    strict = dict(canonical, fiscal_year="FY2026")
    s = normalize_record(strict)
    assert s.issue_codes()["fiscal_year"] == "invalid_type", s.issues
    tbd = dict(canonical, amount_usd="TBD")
    assert normalize_record(tbd).issue_codes()["amount_usd"] == "invalid_type"
    obj = dict(canonical, amount_usd={"value": 1})
    assert normalize_record(obj).issue_codes()["amount_usd"] == "invalid_type"

    missing = {k: v for k, v in canonical.items() if k != "org_unit"}
    assert normalize_record(missing).issue_codes()["org_unit"] == "missing"
    blank = dict(canonical, title="")
    assert normalize_record(blank).issue_codes()["title"] == "missing"
    nulled = dict(canonical, awardee=None)
    assert normalize_record(nulled).issue_codes()["awardee"] == "missing"

    unmarked = {k: v for k, v in canonical.items() if k != "classification_band"}
    assert normalize_record(unmarked).normalized["classification_band"] == "CUI-Mock"

    env = parse_drop(
        json.dumps({"batch_id": "drop-good-2026-08", "schema_variant": "canonical",
                    "records": [canonical]}),
        key="drops/drop_good.json",
    )
    assert env.batch_id == "drop-good-2026-08" and len(env.records) == 1

    lines = parse_drop(json.dumps(canonical) + "\n" + json.dumps(variant),
                       key="incoming/onr_grants_export.jsonl")
    assert len(lines.records) == 2 and lines.batch_id == "batch-onr-grants-export"

    arr = parse_drop(json.dumps([variant]), key="incoming/x.json")
    assert arr.schema_variant == "compatible-renamed"

    bad = parse_drop("{not json", key="incoming/x.json")
    assert bad.parse_errors and not bad.records

    print("normalize.py self-test OK")


if __name__ == "__main__":  # pragma: no cover
    _selftest()

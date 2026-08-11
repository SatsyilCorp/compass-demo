"""The Compass data-quality rule engine.

Pure functions - no AWS, no database, stdlib only - so the rules can be read,
reasoned about and run offline (``python3 rules.py`` executes the self-test).
The Lambda around it (``app.py``) does the I/O: read the batch out of
``grants_raw``, run :func:`evaluate_batch`, write ``grant_quality``, mark the
rows, raise anomalies, emit lineage.

The five rules
--------------
``not_null_required_fields``   every NOT NULL curated column has a value
``valid_fiscal_year_range``    fiscal_year is an integer inside the window
``amount_usd_within_bounds``   amount_usd is numeric, positive, below the cap
``org_unit_recognized``        org_unit is a known ONR unit (RLS key must be real)
``grant_no_unique``            grant_no is unique in-batch and not already curated

(The names match ``frontend/lib/mock/quality.ts`` so the mock and live modes
render the same rule list.)

The score
---------
One formula, applied at two grains::

    score = 100 * passed / (passed + failed)

*Per rule* (what lands in ``grant_quality.score``) the units are the rows that
rule evaluated. *Per batch* (``overall_score``, the number the gate decides on)
the units are whole rows: a row passes only if it fails no rule. The batch
number is deliberately row-grained - "45 of 60 rows are clean" is the fact an
evaluator cares about, and averaging across rules would dilute 15 bad rows into
a reassuring 95%. The rule-evaluation aggregate is still reported, as
``rule_evaluation_score``, so both views are on the record. Every
``grant_quality`` row carries the formula string in its ``details_jsonb`` so a
score is never shown without the rule and the arithmetic that produced it.

**Not-applicable rows.** Rules are independent and each failure is attributed
once. If ``fiscal_year`` is absent, that is a ``not_null_required_fields``
failure; ``valid_fiscal_year_range`` has nothing to range-check, so the row is
*not applicable* to it and is not counted in either column for that rule. The
count is reported as ``not_applicable_rows`` in the rule's details, so the
denominator is always auditable. A field that is *present but the wrong type*
(``fiscal_year: "FY2026"``, ``amount_usd: "TBD"``) is a real failure of the
typed rule, not a missing value - see ``intake/normalize.py`` for why that
distinction is drawn at normalization time.

A row is **quarantined** when it fails one or more rules; only rows that fail
none are eligible to be curated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

SCORE_FORMULA = "score = 100 * passed_rows / (passed_rows + failed_rows)"

RULE_NAMES = (
    "not_null_required_fields",
    "valid_fiscal_year_range",
    "amount_usd_within_bounds",
    "org_unit_recognized",
    "grant_no_unique",
)

# The org units that exist in this portfolio. ``org_unit`` is the RLS key, so an
# unrecognized value would create a row nobody can ever see - a silent data
# black hole. That is why it is a hard rule, not a warning.
KNOWN_ORG_UNITS: Set[str] = {
    "ONR-Corporate",
    "Code-30",
    "Code-31",
    "Code-32",
    "Code-34",
    "Code-35",
}

# Required curated columns, mirrored from intake/normalize.REQUIRED_FIELDS.
REQUIRED_FIELDS = (
    "grant_no",
    "title",
    "program_area",
    "fiscal_year",
    "amount_usd",
    "awardee",
    "org_unit",
)

DEFAULT_FY_MIN = 2015
DEFAULT_FY_MAX = 2035
DEFAULT_AMOUNT_MAX = 100_000_000.0
DEFAULT_PASS_THRESHOLD = 90.0


def score_of(passed: int, failed: int) -> float:
    """The documented score formula. An unevaluated rule scores 100."""
    total = passed + failed
    if total <= 0:
        return 100.0
    return round(100.0 * passed / total, 2)


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
@dataclass
class RuleResult:
    rule: str
    passed_rows: int = 0
    failed_rows: int = 0
    not_applicable_rows: int = 0
    failures: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def score(self) -> float:
        return score_of(self.passed_rows, self.failed_rows)

    def details(self, *, sample: int = 10) -> Dict[str, Any]:
        return {
            "formula": SCORE_FORMULA,
            "passed_rows": self.passed_rows,
            "failed_rows": self.failed_rows,
            "not_applicable_rows": self.not_applicable_rows,
            "evaluated_rows": self.passed_rows + self.failed_rows,
            "failure_sample": self.failures[:sample],
            "failure_count": len(self.failures),
        }


@dataclass
class RowResult:
    row_index: int
    raw_id: Optional[int]
    grant_no: Optional[str]
    violations: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations

    @property
    def reason(self) -> str:
        if not self.violations:
            return ""
        return "; ".join(f"{v['rule']}: {v['detail']}" for v in self.violations)

    @property
    def severity(self) -> str:
        """High when the row can never be curated (identity/required/duplicate)."""
        hard = {"not_null_required_fields", "grant_no_unique", "org_unit_recognized"}
        return "high" if any(v["rule"] in hard for v in self.violations) else "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_index": self.row_index,
            "raw_id": self.raw_id,
            "grant_no": self.grant_no,
            "status": "passed" if self.passed else "quarantined",
            "violations": self.violations,
        }


@dataclass
class BatchQualityResult:
    rules: List[RuleResult]
    rows: List[RowResult]
    threshold: float = DEFAULT_PASS_THRESHOLD

    @property
    def rows_checked(self) -> int:
        return len(self.rows)

    @property
    def rows_passed(self) -> int:
        return sum(1 for r in self.rows if r.passed)

    @property
    def rows_failed(self) -> int:
        return self.rows_checked - self.rows_passed

    @property
    def overall_score(self) -> float:
        """Row-level pass rate - the number the gate decides on."""
        return score_of(self.rows_passed, self.rows_failed)

    @property
    def rule_evaluation_score(self) -> float:
        """The same formula aggregated over every rule evaluation (reported,
        not decided on - see the module docstring)."""
        return score_of(
            sum(r.passed_rows for r in self.rules),
            sum(r.failed_rows for r in self.rules),
        )

    @property
    def gate(self) -> str:
        """``pass`` routes the batch to Persist, ``fail`` routes it to Quarantine."""
        return "pass" if self.overall_score >= self.threshold else "fail"

    def summary(self) -> Dict[str, Any]:
        return {
            "rows_checked": self.rows_checked,
            "rows_passed": self.rows_passed,
            "rows_failed": self.rows_failed,
            "overall_score": self.overall_score,
            "rule_evaluation_score": self.rule_evaluation_score,
            "score_formula": SCORE_FORMULA,
            "score_grain": "rows (a row passes only if it fails no rule)",
            "threshold": self.threshold,
            "gate": self.gate,
            "rules": [
                {
                    "rule": r.rule,
                    "passed_rows": r.passed_rows,
                    "failed_rows": r.failed_rows,
                    "score": r.score,
                    "details": r.details(),
                }
                for r in self.rules
            ],
        }


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def _issue_code(issues: Sequence[Dict[str, Any]], field_name: str) -> Optional[str]:
    for issue in issues or ():
        if issue.get("field") == field_name:
            return issue.get("code")
    return None


def _issue_detail(issues: Sequence[Dict[str, Any]], field_name: str) -> str:
    for issue in issues or ():
        if issue.get("field") == field_name:
            return str(issue.get("detail") or issue.get("code") or "invalid")
    return "invalid"


def evaluate_batch(
    rows: Iterable[Dict[str, Any]],
    *,
    existing_grant_nos: Optional[Set[str]] = None,
    fy_min: int = DEFAULT_FY_MIN,
    fy_max: int = DEFAULT_FY_MAX,
    amount_max: float = DEFAULT_AMOUNT_MAX,
    known_org_units: Optional[Set[str]] = None,
    threshold: float = DEFAULT_PASS_THRESHOLD,
) -> BatchQualityResult:
    """Run every rule over every row of a batch.

    Args:
        rows: dicts shaped like the ``grants_raw.raw_jsonb`` envelope written by
            the intake stage - ``{"raw_id", "record", "normalized", "meta":
            {"row_index", "issues": [...]}}``.
        existing_grant_nos: grant numbers already in ``grants_curated`` (read
            under the pipeline's corporate RLS context, so the uniqueness check
            sees the whole portfolio and not one org's slice).
        fy_min/fy_max: inclusive fiscal-year window.
        amount_max: upper sanity bound on a single award.
        known_org_units: the recognized RLS keys.
        threshold: batch score at or above which the gate passes.
    """
    known = known_org_units or KNOWN_ORG_UNITS
    existing = set(existing_grant_nos or ())
    results = {name: RuleResult(rule=name) for name in RULE_NAMES}
    row_results: List[RowResult] = []
    seen_in_batch: Dict[str, int] = {}

    for row in rows:
        meta = row.get("meta") or {}
        issues = meta.get("issues") or []
        norm = row.get("normalized") or {}
        row_index = int(meta.get("row_index", len(row_results)))
        grant_no = norm.get("grant_no")
        rr = RowResult(row_index=row_index, raw_id=row.get("raw_id"), grant_no=grant_no)

        def fail(rule: str, detail: str, **extra: Any) -> None:
            results[rule].failed_rows += 1
            results[rule].failures.append(
                {"row_index": row_index, "grant_no": grant_no, "detail": detail, **extra}
            )
            rr.violations.append({"rule": rule, "detail": detail, **extra})

        # 1) required fields present ---------------------------------------
        missing = [
            f for f in REQUIRED_FIELDS
            if norm.get(f) is None and _issue_code(issues, f) != "invalid_type"
        ]
        if missing:
            fail("not_null_required_fields", "missing required field(s): " + ", ".join(missing),
                 fields=missing)
        else:
            results["not_null_required_fields"].passed_rows += 1

        # 2) fiscal year ----------------------------------------------------
        fy = norm.get("fiscal_year")
        fy_issue = _issue_code(issues, "fiscal_year")
        if fy_issue == "invalid_type":
            fail("valid_fiscal_year_range", _issue_detail(issues, "fiscal_year"))
        elif fy is None:
            results["valid_fiscal_year_range"].not_applicable_rows += 1
        elif not (fy_min <= int(fy) <= fy_max):
            fail("valid_fiscal_year_range",
                 f"fiscal_year {fy} outside the {fy_min}-{fy_max} window", value=fy)
        else:
            results["valid_fiscal_year_range"].passed_rows += 1

        # 3) amount ---------------------------------------------------------
        amount = norm.get("amount_usd")
        amount_issue = _issue_code(issues, "amount_usd")
        if amount_issue == "invalid_type":
            fail("amount_usd_within_bounds", _issue_detail(issues, "amount_usd"))
        elif amount is None:
            results["amount_usd_within_bounds"].not_applicable_rows += 1
        elif float(amount) <= 0:
            fail("amount_usd_within_bounds", f"amount_usd {amount} is not positive",
                 value=float(amount))
        elif float(amount) > amount_max:
            fail("amount_usd_within_bounds",
                 f"amount_usd {amount} exceeds the {amount_max:,.0f} cap", value=float(amount))
        else:
            results["amount_usd_within_bounds"].passed_rows += 1

        # 4) org unit -------------------------------------------------------
        org = norm.get("org_unit")
        if org is None:
            results["org_unit_recognized"].not_applicable_rows += 1
        elif org not in known:
            fail("org_unit_recognized",
                 f"org_unit {org!r} is not a recognized ONR unit", value=org)
        else:
            results["org_unit_recognized"].passed_rows += 1

        # 5) grant number uniqueness ---------------------------------------
        if not grant_no:
            results["grant_no_unique"].not_applicable_rows += 1
        elif grant_no in existing:
            fail("grant_no_unique",
                 f"grant_no {grant_no!r} already exists in grants_curated")
        elif grant_no in seen_in_batch:
            fail("grant_no_unique",
                 f"grant_no {grant_no!r} duplicates row {seen_in_batch[grant_no]} of this batch")
        else:
            seen_in_batch[grant_no] = row_index
            results["grant_no_unique"].passed_rows += 1

        row_results.append(rr)

    return BatchQualityResult(
        rules=[results[name] for name in RULE_NAMES],
        rows=row_results,
        threshold=threshold,
    )


# --------------------------------------------------------------------------- #
# Self-test - `python3 rules.py`
# --------------------------------------------------------------------------- #
def _row(row_index: int, normalized: Dict[str, Any], issues=None) -> Dict[str, Any]:
    return {
        "raw_id": 1000 + row_index,
        "normalized": normalized,
        "meta": {"row_index": row_index, "issues": issues or []},
    }


def _selftest() -> None:
    good = {
        "grant_no": "ONRD-2026-AIML-D1-00001",
        "title": "T",
        "program_area": "AI/ML",
        "fiscal_year": 2026,
        "amount_usd": 500000.0,
        "awardee": "Cascade Advanced Systems Group",
        "org_unit": "Code-30",
        "classification_band": "CUI-Mock",
    }
    clean = evaluate_batch([_row(0, dict(good)), _row(1, dict(good, grant_no="X-2"))])
    assert clean.rows_passed == 2 and clean.overall_score == 100.0, clean.summary()
    assert clean.gate == "pass"

    rows = [
        _row(0, dict(good)),
        _row(1, dict(good, grant_no="X-1", org_unit=None),
             [{"field": "org_unit", "code": "missing", "detail": "field absent"}]),
        _row(2, dict(good, grant_no="X-2", amount_usd=-152000.0)),
        _row(3, dict(good, grant_no="X-3", org_unit="Code-99")),
        _row(4, dict(good, grant_no="ONRD-2026-AIML-D1-00001")),  # dup in-batch
        _row(5, dict(good, grant_no="X-5", fiscal_year=1998)),
        _row(6, dict(good, grant_no="X-6", amount_usd=None),
             [{"field": "amount_usd", "code": "invalid_type",
               "detail": "expected a number, got the string 'TBD'"}]),
    ]
    res = evaluate_batch(rows, existing_grant_nos={"ALREADY-CURATED"})
    by_rule = {r.rule: r for r in res.rules}

    assert by_rule["not_null_required_fields"].failed_rows == 1        # row 1
    assert by_rule["org_unit_recognized"].failed_rows == 1             # row 3
    assert by_rule["org_unit_recognized"].not_applicable_rows == 1     # row 1
    assert by_rule["amount_usd_within_bounds"].failed_rows == 2        # rows 2, 6
    assert by_rule["valid_fiscal_year_range"].failed_rows == 1         # row 5
    assert by_rule["grant_no_unique"].failed_rows == 1                 # row 4
    assert res.rows_passed == 1 and res.rows_failed == 6, res.summary()

    # A row that duplicates something already curated fails too.
    dup = evaluate_batch([_row(0, dict(good))], existing_grant_nos={good["grant_no"]})
    assert dup.rows_failed == 1

    # The gate score is row-grained: 1 of 7 rows is clean.
    assert res.overall_score == score_of(1, 6), res.overall_score
    assert res.gate == "fail", res.overall_score
    # …while the rule-evaluation aggregate is the (higher) diluted view.
    total_pass = sum(r.passed_rows for r in res.rules)
    total_fail = sum(r.failed_rows for r in res.rules)
    assert res.rule_evaluation_score == score_of(total_pass, total_fail)
    assert res.rule_evaluation_score > res.overall_score

    assert score_of(0, 0) == 100.0 and score_of(3, 1) == 75.0
    print("rules.py self-test OK")


if __name__ == "__main__":  # pragma: no cover
    _selftest()

"""Conservative PII removal for public-source ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
# Public award identifiers such as N252-114 and N68335-26-C-0082 are not
# telephone numbers. Require separators used by conventional phone formats.
PHONE_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:\+?1[ .-]?)?(?:\(\d{3}\)[ .-]?|\d{3}[ .-])\d{3}[ .-]\d{4}(?![A-Z0-9])",
    re.IGNORECASE,
)
SSN_PATTERN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")


SENSITIVE_EXACT_KEYS = {
    "contact",
    "contactname",
    "contactfirstname",
    "contactlastname",
    "contactemail",
    "contactphone",
    "contactfax",
    "email",
    "emailaddress",
    "fax",
    "faxnumber",
    "phone",
    "phonenumber",
    "piname",
    "piemail",
    "piphone",
    "pifax",
    "pocname",
    "pocemail",
    "pocphone",
    "pocfax",
    "principalinvestigator",
    "principalinvestigatorname",
    "principalinvestigatoremail",
    "principalinvestigatorphone",
    "projectmanager",
    "projectmanagername",
    "streetaddress",
    "address1",
    "address2",
    "addressline1",
    "addressline2",
    "address",
    "companyaddress",
    "mailingaddress",
    "contactperson",
    "businessofficialname",
    "businessofficialemail",
    "businessofficialphone",
    "ceoname",
    "ownername",
    "presidentname",
    "ssn",
}

SENSITIVE_KEY_TOKENS = (
    "contactemail",
    "contactphone",
    "contactfax",
    "contactname",
    "businesscontact",
    "businessofficial",
    "companycontact",
    "firmcontact",
    "contactperson",
    "principalinvestigator",
    "projectmanager",
    "piemail",
    "piphone",
    "pifax",
    "piname",
    "pocemail",
    "pocphone",
    "pocfax",
    "pocname",
    "ripoc",
)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def is_sensitive_key(key: str) -> bool:
    normalized = normalize_key(key)
    return normalized in SENSITIVE_EXACT_KEYS or any(token in normalized for token in SENSITIVE_KEY_TOKENS)


@dataclass(frozen=True)
class PiiReport:
    dropped_fields: int = 0
    redacted_values: int = 0

    def add(self, other: "PiiReport") -> "PiiReport":
        return PiiReport(
            dropped_fields=self.dropped_fields + other.dropped_fields,
            redacted_values=self.redacted_values + other.redacted_values,
        )


def redact_text(value: str) -> tuple[str, int]:
    redactions = 0

    def replace(pattern: re.Pattern[str], text: str, marker: str) -> str:
        nonlocal redactions
        text, count = pattern.subn(marker, text)
        redactions += count
        return text

    result = replace(EMAIL_PATTERN, value, "[REDACTED_EMAIL]")
    result = replace(PHONE_PATTERN, result, "[REDACTED_PHONE]")
    result = replace(SSN_PATTERN, result, "[REDACTED_SSN]")
    return result, redactions


def sanitize_mapping(value: Mapping[str, Any]) -> tuple[dict[str, Any], PiiReport]:
    """Drop direct-PII fields and redact direct-PII patterns recursively."""

    output: dict[str, Any] = {}
    report = PiiReport()
    for key, item in value.items():
        key_text = str(key)
        if is_sensitive_key(key_text):
            report = report.add(PiiReport(dropped_fields=1))
            continue
        if isinstance(item, Mapping):
            sanitized, nested_report = sanitize_mapping(item)
            output[key_text] = sanitized
            report = report.add(nested_report)
        elif isinstance(item, list):
            sanitized_items: list[Any] = []
            for nested in item:
                if isinstance(nested, Mapping):
                    sanitized, nested_report = sanitize_mapping(nested)
                    sanitized_items.append(sanitized)
                    report = report.add(nested_report)
                elif isinstance(nested, str):
                    sanitized, count = redact_text(nested)
                    sanitized_items.append(sanitized)
                    report = report.add(PiiReport(redacted_values=count))
                else:
                    sanitized_items.append(nested)
            output[key_text] = sanitized_items
        elif isinstance(item, str):
            sanitized, count = redact_text(item)
            output[key_text] = sanitized
            report = report.add(PiiReport(redacted_values=count))
        else:
            output[key_text] = item
    return output, report

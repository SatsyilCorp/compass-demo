#!/usr/bin/env python3
"""Verify the deployed HTTP API browser preflight contract.

This check intentionally exercises several routes used by different screens.
API Gateway owns HTTP API preflight responses, so one missing global CORS
configuration otherwise presents as a generic ``Failed to fetch`` everywhere.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Probe:
    path: str
    method: str


PROBES = (
    Probe("/me", "GET"),
    Probe("/catalog", "GET"),
    Probe("/catalog/cors-contract-dataset/lineage", "GET"),
    Probe("/ingest/status", "GET"),
    Probe("/stream/recent", "GET"),
    Probe("/ingest/simulate", "POST"),
    Probe("/analytics/cors-contract-run", "GET"),
    Probe("/dashboard", "GET"),
    Probe("/analytics/run", "POST"),
    Probe("/chat", "POST"),
    Probe("/anomalies", "GET"),
    Probe("/approvals", "GET"),
    Probe("/approvals", "POST"),
    Probe("/licenses", "GET"),
    Probe("/export", "POST"),
    Probe("/openapi.json", "GET"),
    Probe("/system/evidence", "GET"),
    Probe("/scale/profiles", "GET"),
    Probe("/scale/plans", "POST"),
    Probe("/scale/runs", "GET"),
    Probe("/scale/runs", "POST"),
    Probe("/scale/runs/cors-contract-run", "GET"),
    Probe("/scale/runs/cors-contract-run/cancel", "POST"),
    Probe("/scale/runs/cors-contract-run/exports", "POST"),
    Probe(
        "/scale/runs/cors-contract-run/exports/cors-contract-export",
        "GET",
    ),
)


def _tokens(value: str | None) -> set[str]:
    return {token.strip().lower() for token in (value or "").split(",") if token.strip()}


def validated_api_base_url(value: str) -> str:
    """Return a canonical HTTPS API URL or reject the probe target."""
    candidate = value.rstrip("/")
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("api-base-url must be an absolute https URL without credentials, query, or fragment")
    return candidate


def _open_https(request: Request):
    """Open only a request whose URL has already passed the HTTPS boundary."""
    if urlsplit(request.full_url).scheme != "https":
        raise ValueError("CORS probes may only open https URLs")
    return urlopen(request, timeout=15)  # nosec B310


def check_preflight(api_base_url: str, origin: str, probe: Probe) -> list[str]:
    request = Request(
        f"{api_base_url.rstrip('/')}{probe.path}",
        method="OPTIONS",
        headers={
            "Origin": origin.rstrip("/"),
            "Access-Control-Request-Method": probe.method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    try:
        with _open_https(request) as response:
            status = response.status
            headers = response.headers
    except HTTPError as error:
        status = error.code
        headers = error.headers
    except URLError as error:
        return [f"{probe.method} {probe.path}: network error: {error.reason}"]

    problems: list[str] = []
    expected_origin = origin.rstrip("/")
    actual_origin = headers.get("Access-Control-Allow-Origin")
    allowed_methods = _tokens(headers.get("Access-Control-Allow-Methods"))
    allowed_headers = _tokens(headers.get("Access-Control-Allow-Headers"))

    if status != 204:
        problems.append(f"{probe.method} {probe.path}: expected 204, received {status}")
    if actual_origin != expected_origin:
        problems.append(
            f"{probe.method} {probe.path}: expected exact allow-origin {expected_origin!r}, "
            f"received {actual_origin!r}"
        )
    if probe.method.lower() not in allowed_methods:
        problems.append(
            f"{probe.method} {probe.path}: method missing from allow-methods "
            f"{sorted(allowed_methods)!r}"
        )
    for required_header in ("authorization", "content-type"):
        if required_header not in allowed_headers:
            problems.append(
                f"{probe.method} {probe.path}: {required_header} missing from "
                f"allow-headers {sorted(allowed_headers)!r}"
            )
    return problems


def check_denied_response(api_base_url: str, origin: str, probe: Probe) -> list[str]:
    """Ensure authorizer failures remain readable by the browser."""
    request = Request(
        f"{api_base_url.rstrip('/')}{probe.path}",
        data=b"{}" if probe.method in {"POST", "PUT"} else None,
        method=probe.method,
        headers={
            "Origin": origin.rstrip("/"),
            "Authorization": "Bearer invalid",
            "Content-Type": "application/json",
        },
    )

    try:
        with _open_https(request) as response:
            status = response.status
            headers = response.headers
    except HTTPError as error:
        status = error.code
        headers = error.headers
    except URLError as error:
        return [f"{probe.method} {probe.path}: network error: {error.reason}"]

    problems: list[str] = []
    expected_origin = origin.rstrip("/")
    actual_origin = headers.get("Access-Control-Allow-Origin")
    if status != 401:
        problems.append(f"{probe.method} {probe.path}: expected denied 401, received {status}")
    if actual_origin != expected_origin:
        problems.append(
            f"{probe.method} {probe.path}: denied response expected exact allow-origin "
            f"{expected_origin!r}, received {actual_origin!r}"
        )
    return problems


def check_unapproved_origin(api_base_url: str) -> list[str]:
    """Ensure the API does not reflect an arbitrary browser origin."""
    attacker_origin = "https://attacker.invalid"
    request = Request(
        f"{api_base_url.rstrip('/')}/catalog",
        method="OPTIONS",
        headers={
            "Origin": attacker_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    try:
        with _open_https(request) as response:
            actual_origin = response.headers.get("Access-Control-Allow-Origin")
    except HTTPError as error:
        actual_origin = error.headers.get("Access-Control-Allow-Origin")
    except URLError as error:
        return [f"unapproved origin probe: network error: {error.reason}"]

    if actual_origin is not None:
        return [f"unapproved origin received allow-origin {actual_origin!r}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    api_base_url = validated_api_base_url(args.api_base_url)

    failures = [
        problem
        for probe in PROBES
        for problem in (
            check_preflight(api_base_url, args.origin, probe)
            + check_denied_response(api_base_url, args.origin, probe)
        )
    ]
    failures.extend(check_unapproved_origin(api_base_url))
    if failures:
        print("CORS contract failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        "OK CORS preflight and denied-response contract passed for "
        f"{len(PROBES)} protected operations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

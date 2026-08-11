"""API Gateway (HTTP API / payload format 2.0) request + response helpers.

Every Compass route sits behind a JWT/Lambda authorizer that maps
``cognito:groups`` → ``role`` and injects ``org_unit`` into the request context
(deny-by-default). Handlers read that context with :func:`get_claims` and shape
their replies with :func:`json_response` and the typed error helpers, so the
response envelope (status, CORS, JSON body) is identical across every Lambda.

No AWS SDK, no network - pure dict shaping, safe to import anywhere.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# API Gateway owns preflight handling in the deployed stack. Lambda responses
# therefore start with no access-control origin at all. Direct Lambda/local
# callers can opt into an origin only when it appears in CORS_ALLOW_ORIGINS.
# This avoids the previous fail-open wildcard and keeps the policy in one place.
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Headers": "authorization,content-type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def cors_allow_origins() -> tuple[str, ...]:
    """Return the configured exact-match browser origin allowlist.

    ``CORS_ALLOW_ORIGINS`` is a comma-separated list. Local development origins
    are the safe default. An empty configured value means no direct Lambda
    origin is allowed; deployed API Gateway CORS still applies independently.
    """
    configured = os.environ.get("CORS_ALLOW_ORIGINS")
    if configured is None:
        return DEFAULT_CORS_ALLOW_ORIGINS
    return tuple(
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    )


def cors_headers(origin: Optional[str] = None) -> Dict[str, str]:
    """Build response headers and reflect only an explicitly allowed origin."""
    headers = dict(CORS_HEADERS)
    normalized = (origin or "").strip().rstrip("/")
    if normalized and normalized in cors_allow_origins():
        headers["Access-Control-Allow-Origin"] = normalized
        headers["Vary"] = "Origin"
    return headers


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
def json_response(
    status: int,
    body: Any,
    headers: Optional[Dict[str, str]] = None,
    *,
    origin: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an HTTP API response with centralized, allowlisted CORS headers."""
    merged = cors_headers(origin)
    if headers:
        merged.update(headers)
    # A caller cannot weaken the shared policy with a wildcard or arbitrary
    # origin override.
    response_origin = merged.get("Access-Control-Allow-Origin", "").rstrip("/")
    if response_origin and response_origin not in cors_allow_origins():
        merged.pop("Access-Control-Allow-Origin")
        merged.pop("Vary", None)
    elif response_origin:
        merged["Access-Control-Allow-Origin"] = response_origin
        merged["Vary"] = "Origin"
    return {
        "statusCode": status,
        "headers": merged,
        "body": json.dumps(body, default=str),
    }


def error_response(status: int, message: str, **extra: Any) -> Dict[str, Any]:
    """Standard error envelope: ``{"error": <message>, ...extra}``."""
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return json_response(status, payload)


# Convenience shortcuts used across handlers.
def ok(body: Any) -> Dict[str, Any]:
    return json_response(200, body)


def created(body: Any) -> Dict[str, Any]:
    return json_response(201, body)


def bad_request(message: str = "bad request", **extra: Any) -> Dict[str, Any]:
    return error_response(400, message, **extra)


def unauthorized(message: str = "unauthorized") -> Dict[str, Any]:
    return error_response(401, message)


def forbidden(message: str = "forbidden") -> Dict[str, Any]:
    return error_response(403, message)


def not_found(message: str = "not found") -> Dict[str, Any]:
    return error_response(404, message)


def approval_required(
    message: str = "approval required", **extra: Any
) -> Dict[str, Any]:
    """HTTP 428 - the /export aggregation guard's 'row count exceeds cap' reply."""
    return error_response(428, message, **extra)


def server_error(message: str = "internal error") -> Dict[str, Any]:
    return error_response(500, message)


# --------------------------------------------------------------------------- #
# Identity / claims
# --------------------------------------------------------------------------- #
GROUP_TO_ROLE: Dict[str, str] = {
    "compass-poweruser": "poweruser",
    "compass-viewer": "viewer",
}
ROLE_TO_ORG_UNIT: Dict[str, str] = {
    "poweruser": "ONR-Corporate",
    "viewer": "Code-30",
}
ROLE_PRECEDENCE = ("poweruser", "viewer")


@dataclass
class Claims:
    """The caller identity the authorizer injected into the request context.

    ``role`` and ``org_unit`` are the load-bearing fields: the personas are
    ``poweruser`` (org_unit ``ONR-Corporate``, sees all) and ``viewer``
    (org_unit ``Code-30``, sees only its own rows).
    """

    sub: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    org_unit: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.role and self.org_unit)

    @property
    def is_corporate(self) -> bool:
        return self.org_unit == "ONR-Corporate"


def _authorizer_context(event: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the authorizer-supplied context out of an HTTP API v2 event.

    Supports both a REQUEST/Lambda authorizer (``authorizer.lambda.*`` - the
    Compass authorizer that derives role from groups and injects org_unit) and a
    native JWT authorizer (``authorizer.jwt.claims.*``).
    """
    rc = (event or {}).get("requestContext") or {}
    authz = rc.get("authorizer") or {}
    if isinstance(authz.get("lambda"), dict):
        return dict(authz["lambda"])
    jwt = authz.get("jwt")
    if isinstance(jwt, dict) and isinstance(jwt.get("claims"), dict):
        return dict(jwt["claims"])
    # Fallback: some setups place context keys directly on `authorizer`.
    return {k: v for k, v in authz.items() if k not in ("lambda", "jwt")}


def _split_groups(value: Any) -> List[str]:
    """Normalize a groups claim to a list. Lambda context values are strings;
    Cognito's ``cognito:groups`` may arrive as a list or a bracketed string."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(g).strip() for g in value if str(g).strip()]
    s = str(value).strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = json.loads(s)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return _split_groups(parsed)
        s = s[1:-1]
    return [
        group.strip().strip("'\"")
        for group in s.replace(",", " ").split()
        if group.strip().strip("'\"")
    ]


def role_from_groups(groups: List[str]) -> Optional[str]:
    """Resolve recognized Cognito groups using deterministic precedence."""
    roles = {
        GROUP_TO_ROLE.get(str(group).strip().lower())
        for group in groups
    }
    for role in ROLE_PRECEDENCE:
        if role in roles:
            return role
    return None


def org_unit_for_role(role: Optional[str]) -> Optional[str]:
    """Return the only RLS organization permitted for a Compass role."""
    return ROLE_TO_ORG_UNIT.get((role or "").strip().lower())


def resolve_identity_values(
    role: Any,
    org_unit: Any,
    groups: Any,
) -> tuple[Optional[str], Optional[str], List[str]]:
    """Normalize and validate a role, organization, and Cognito group set.

    Recognized Cognito groups are authoritative when present. A trusted Lambda
    authorizer context without group names may still supply a known role. An
    explicit organization that conflicts with the role mapping fails closed.
    """
    normalized_groups = _split_groups(groups)
    group_role = role_from_groups(normalized_groups)
    explicit_role = str(role or "").strip().lower() or None
    resolved_role = group_role or (
        explicit_role if explicit_role in ROLE_TO_ORG_UNIT else None
    )
    if resolved_role is None:
        return None, None, normalized_groups

    expected_org = org_unit_for_role(resolved_role)
    explicit_org = str(org_unit or "").strip() or None
    if explicit_org is not None and explicit_org != expected_org:
        return None, None, normalized_groups
    return resolved_role, expected_org, normalized_groups


def resolve_identity(claims: Claims) -> tuple[Optional[str], Optional[str]]:
    """Return a validated ``(role, org_unit)`` pair or a deny pair."""
    role, org_unit, _ = resolve_identity_values(
        claims.role,
        claims.org_unit,
        claims.groups,
    )
    return role, org_unit


def get_claims(event: Dict[str, Any]) -> Claims:
    """Read the caller's identity/role/org_unit from the authorizer context.

    Never raises - returns a :class:`Claims` with whatever the authorizer
    provided. Handlers enforce deny-by-default by checking
    ``claims.is_authenticated`` (or the specific role/org they require) and
    replying with :func:`unauthorized` / :func:`forbidden` when it fails.
    """
    ctx = _authorizer_context(event)

    def pick(*names: str) -> Optional[str]:
        for n in names:
            v = ctx.get(n)
            if v not in (None, ""):
                return str(v)
        return None

    groups = _split_groups(ctx.get("groups") or ctx.get("cognito:groups"))
    role, org_unit, groups = resolve_identity_values(
        pick("role"),
        pick("org_unit", "orgUnit"),
        groups,
    )

    return Claims(
        sub=pick("sub", "principalId"),
        username=pick("username", "cognito:username", "preferred_username"),
        email=pick("email"),
        role=role,
        org_unit=org_unit,
        groups=groups,
        raw=ctx,
    )


# --------------------------------------------------------------------------- #
# Request accessors
# --------------------------------------------------------------------------- #
def get_method(event: Dict[str, Any]) -> Optional[str]:
    return ((event.get("requestContext") or {}).get("http") or {}).get("method")


def get_path(event: Dict[str, Any]) -> Optional[str]:
    request_context = event.get("requestContext") or {}
    path = (request_context.get("http") or {}).get("path")
    if not isinstance(path, str):
        return None
    stage = request_context.get("stage")
    if isinstance(stage, str) and stage and stage != "$default":
        prefix = f"/{stage}"
        if path == prefix:
            return "/"
        if path.startswith(f"{prefix}/"):
            return path[len(prefix) :]
    return path


def path_param(event: Dict[str, Any], name: str) -> Optional[str]:
    return (event.get("pathParameters") or {}).get(name)


def query_params(event: Dict[str, Any]) -> Dict[str, str]:
    return dict(event.get("queryStringParameters") or {})


def parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Decode the JSON request body (handling base64-encoded bodies).

    Returns ``{}`` for an empty body. Raises ``ValueError`` on malformed JSON so
    the handler can return a 400.
    """
    raw = event.get("body")
    if raw is None or raw == "":
        return {}
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("request body must be a JSON object")
    return parsed

"""API Gateway (HTTP API / payload format 2.0) request + response helpers.

Every Compass route sits behind a JWT/Lambda authorizer that maps
``cognito:groups`` → ``role`` and injects ``org_unit`` into the request context
(deny-by-default). Handlers read that context with :func:`get_claims` and shape
their replies with :func:`json_response` and the typed error helpers, so the
response envelope (status, CORS, JSON body) is identical across every Lambda.

No AWS SDK, no network — pure dict shaping, safe to import anywhere.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Demo CORS: the SPA is served from CloudFront; the browser calls the HTTP API
# cross-origin. Tighten `Access-Control-Allow-Origin` to the CloudFront domain
# for a hardened deploy.
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization,content-type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
def json_response(
    status: int, body: Any, headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Build an HTTP API proxy response with a JSON body and CORS headers."""
    merged = dict(CORS_HEADERS)
    if headers:
        merged.update(headers)
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
    """HTTP 428 — the /export aggregation guard's 'row count exceeds cap' reply."""
    return error_response(428, message, **extra)


def server_error(message: str = "internal error") -> Dict[str, Any]:
    return error_response(500, message)


# --------------------------------------------------------------------------- #
# Identity / claims
# --------------------------------------------------------------------------- #
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

    Supports both a REQUEST/Lambda authorizer (``authorizer.lambda.*`` — the
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
    if isinstance(value, list):
        return [str(g) for g in value if str(g).strip()]
    s = str(value).strip().strip("[]")
    if not s:
        return []
    return [g.strip() for g in s.replace(",", " ").split() if g.strip()]


def get_claims(event: Dict[str, Any]) -> Claims:
    """Read the caller's identity/role/org_unit from the authorizer context.

    Never raises — returns a :class:`Claims` with whatever the authorizer
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

    return Claims(
        sub=pick("sub", "principalId"),
        username=pick("username", "cognito:username", "preferred_username"),
        email=pick("email"),
        role=pick("role"),
        org_unit=pick("org_unit", "orgUnit"),
        groups=_split_groups(ctx.get("groups") or ctx.get("cognito:groups")),
        raw=ctx,
    )


# --------------------------------------------------------------------------- #
# Request accessors
# --------------------------------------------------------------------------- #
def get_method(event: Dict[str, Any]) -> Optional[str]:
    return ((event.get("requestContext") or {}).get("http") or {}).get("method")


def get_path(event: Dict[str, Any]) -> Optional[str]:
    return ((event.get("requestContext") or {}).get("http") or {}).get("path")


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

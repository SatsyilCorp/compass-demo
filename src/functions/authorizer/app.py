"""Compass identity: the Cognito JWT context authorizer + ``GET /me``.

One Lambda, two jobs (both driven by the same claims → role → org_unit map):

1. **Lambda REQUEST authorizer** (registered in template.yaml as
   ``CompassContextAuthorizer``, payload format 2.0, simple responses). It
   validates the Cognito JWT *itself* — signature against the user pool's
   JWKS, issuer, expiry, and audience — then derives the caller's ``role``
   from ``cognito:groups`` and the ``org_unit`` that Postgres row-level
   security keys on, and injects both into the request context. Anything it
   cannot fully verify is denied: ``{"isAuthorized": false}``. Deny-by-default,
   no exceptions.

2. **``GET /me``** (element 1). That route sits behind the API's *default*
   authorizer (the native HttpApi JWT authorizer), so the token is already
   verified by API Gateway and the raw Cognito claims arrive on
   ``requestContext.authorizer.jwt.claims``. The handler applies the same
   group→role→org_unit mapping and returns the identity the SPA renders.

The mapping (docs/CONTRACTS.md "RLS", and the two ``AWS::Cognito::UserPoolGroup``
resources in template.yaml)::

    cognito group        role         org_unit         sees
    -------------------  -----------  ---------------  ---------------------------
    compass-poweruser    poweruser    ONR-Corporate    every row (corporate branch)
    compass-viewer       viewer       Code-30          only Code-30 rows

``org_unit`` is what the request-scoped ``SET LOCAL compass.org_unit`` in
``compass_common.db.set_org`` binds, which is what the ``grants_curated``
policies read. So this file is where "which JWT group you are in" becomes
"which rows the database will hand you" — it is the front door of the whole
access-control story.

Environment
-----------
USER_POOL_ID   Cognito user pool id (required).
WEB_CLIENT_ID  App client id; checked against ``aud`` (ID tokens) or
               ``client_id`` (access tokens).
AWS_REGION     Supplied by the Lambda runtime; used to build the issuer URL.
JWKS_CACHE_SECONDS  Signing-key cache lifetime.            default 3600

Dependencies: PyJWT + cryptography, from this function's own
``requirements.txt`` (deliberately not in the shared CommonLayer — only this
function verifies tokens). This function has **no VpcConfig** in the template,
so it can reach the public Cognito JWKS endpoint.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from compass_common import http

# --------------------------------------------------------------------------- #
# The contract's identity map. Single source of truth; the API handlers that
# need the same derivation (intake) mirror these two dicts and say so.
# --------------------------------------------------------------------------- #
GROUP_ROLE: Dict[str, str] = {
    "compass-poweruser": "poweruser",
    "compass-viewer": "viewer",
}
ROLE_ORG_UNIT: Dict[str, str] = {
    "poweruser": "ONR-Corporate",
    "viewer": "Code-30",
}
# Most-privileged first: a user in both groups resolves to poweruser (this
# mirrors the Cognito group Precedence 10 / 20 set in template.yaml).
ROLE_PRECEDENCE: Tuple[str, ...] = ("poweruser", "viewer")

_JWK_CLIENT = None


class AuthError(Exception):
    """Token could not be verified — always answered with a deny."""


# --------------------------------------------------------------------------- #
# Claims → role → org_unit
# --------------------------------------------------------------------------- #
def role_from_groups(groups: List[str]) -> Optional[str]:
    """Highest-precedence Compass role in ``groups``; ``None`` if none apply."""
    roles = {GROUP_ROLE[g] for g in groups if g in GROUP_ROLE}
    for role in ROLE_PRECEDENCE:
        if role in roles:
            return role
    return None


def org_unit_for_role(role: Optional[str]) -> Optional[str]:
    return ROLE_ORG_UNIT.get(role or "")


# --------------------------------------------------------------------------- #
# Token verification
# --------------------------------------------------------------------------- #
def _region() -> str:
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def issuer() -> str:
    pool = os.environ.get("USER_POOL_ID")
    if not pool:
        raise AuthError("USER_POOL_ID is not configured")
    return f"https://cognito-idp.{_region()}.amazonaws.com/{pool}"


def jwks_url() -> str:
    return f"{issuer()}/.well-known/jwks.json"


def _jwk_client():
    """Module-level cached ``PyJWKClient`` (keys cached across warm invokes)."""
    global _JWK_CLIENT
    if _JWK_CLIENT is None:
        from jwt import PyJWKClient

        _JWK_CLIENT = PyJWKClient(
            jwks_url(),
            cache_keys=True,
            lifespan=int(os.environ.get("JWKS_CACHE_SECONDS", "3600")),
        )
    return _JWK_CLIENT


def bearer_token(event: Dict[str, Any]) -> Optional[str]:
    """Pull the raw JWT out of an authorizer or HTTP API event."""
    candidates: List[str] = []
    ident = event.get("identitySource")
    if isinstance(ident, list):
        candidates.extend(str(v) for v in ident if v)
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    for name in ("authorization", "x-amz-security-token"):
        if headers.get(name):
            candidates.append(str(headers[name]))
    for raw in candidates:
        token = raw.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if token:
            return token
    return None


def verify_token(token: str, *, jwk_client=None) -> Dict[str, Any]:
    """Verify a Cognito JWT and return its claims, or raise :class:`AuthError`.

    Checks signature (RS256, against the pool's JWKS), issuer, ``exp``/``nbf``
    (60s leeway for clock skew), and the audience — Cognito puts the app client
    id in ``aud`` on ID tokens and in ``client_id`` on access tokens, so the
    check follows ``token_use``. Both token types are accepted: the SPA sends
    ID tokens, and machine callers/curl typically send access tokens.

    ``jwk_client`` is injectable so this can be exercised offline against a
    fake key provider.
    """
    import jwt  # PyJWT — from this function's requirements.txt

    if not token:
        raise AuthError("missing bearer token")
    client = jwk_client or _jwk_client()
    try:
        signing_key = client.get_signing_key_from_jwt(token)
    except Exception as exc:  # unknown kid, unreachable/invalid JWKS, malformed
        raise AuthError(f"cannot resolve signing key: {exc}") from exc

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer(),
            leeway=60,
            # Audience lives in different claims per token_use; checked below.
            options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
        )
    except Exception as exc:
        raise AuthError(f"token rejected: {exc}") from exc

    expected_client = os.environ.get("WEB_CLIENT_ID")
    token_use = claims.get("token_use")
    if expected_client:
        if token_use == "id":
            aud = claims.get("aud")
            aud_list = aud if isinstance(aud, list) else [aud]
            if expected_client not in aud_list:
                raise AuthError("id token audience does not match the app client")
        elif token_use == "access":
            if claims.get("client_id") != expected_client:
                raise AuthError("access token client_id does not match the app client")
        else:
            raise AuthError(f"unsupported token_use {token_use!r}")
    return claims


def _groups(claims: Dict[str, Any]) -> List[str]:
    raw = claims.get("cognito:groups")
    if isinstance(raw, list):
        return [str(g) for g in raw if str(g).strip()]
    return http._split_groups(raw)  # tolerant of "[a b]" / "a,b" string forms


# --------------------------------------------------------------------------- #
# 1) Lambda REQUEST authorizer (simple response format)
# --------------------------------------------------------------------------- #
def _deny(reason: str) -> Dict[str, Any]:
    print(f'{{"event_type":"authz_deny","reason":"{reason}"}}')
    return {"isAuthorized": False, "context": {"reason": reason}}


def authorize(event: Dict[str, Any]) -> Dict[str, Any]:
    """Verify the token and return the authz context (or a deny).

    On allow, ``context`` carries the values every downstream handler reads via
    ``compass_common.http.get_claims``: ``sub``, ``username``, ``email``,
    ``role``, ``org_unit``, ``groups``. API Gateway stringifies context values,
    so ``groups`` is emitted comma-joined (``get_claims`` splits it back).
    """
    try:
        claims = verify_token(bearer_token(event) or "")
    except AuthError as exc:
        return _deny(str(exc))

    groups = _groups(claims)
    role = role_from_groups(groups)
    if role is None:
        return _deny("no Compass group on the token (expected compass-poweruser or compass-viewer)")
    org_unit = org_unit_for_role(role)
    if not org_unit:
        return _deny(f"no org_unit mapped for role {role!r}")

    return {
        "isAuthorized": True,
        "context": {
            "sub": str(claims.get("sub", "")),
            "username": str(
                claims.get("cognito:username") or claims.get("username") or ""
            ),
            "email": str(claims.get("email", "")),
            "role": role,
            "org_unit": org_unit,
            "groups": ",".join(groups),
        },
    }


# --------------------------------------------------------------------------- #
# 2) GET /me
# --------------------------------------------------------------------------- #
def _display_name(raw: Dict[str, Any], email: Optional[str], role: str) -> str:
    for key in ("name", "given_name", "preferred_username", "cognito:username"):
        val = raw.get(key)
        if val:
            return str(val)
    if email:
        return str(email).split("@")[0]
    return "Power User" if role == "poweruser" else "Viewer"


def get_me(event: Dict[str, Any]) -> Dict[str, Any]:
    """``GET /me`` → the caller's identity, role and RLS org_unit.

    Works behind either authorizer: ``get_claims`` reads the Lambda
    authorizer's injected context when present, and the native JWT
    authorizer's raw Cognito claims otherwise (in which case role/org_unit are
    derived here from ``cognito:groups``).
    """
    claims = http.get_claims(event)
    role = claims.role or role_from_groups(claims.groups)
    if role not in ROLE_ORG_UNIT:
        return http.forbidden(
            "caller is not in a Compass group (compass-poweruser or compass-viewer)"
        )
    org_unit = claims.org_unit or org_unit_for_role(role)
    return http.ok(
        {
            "sub": claims.sub or "",
            "email": claims.email or "",
            "display_name": _display_name(claims.raw, claims.email, role),
            "role": role,
            "org_unit": org_unit,
            "groups": claims.groups,
        }
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def handler(event, context=None):
    """Route by event shape: authorizer invocation vs. HTTP API request."""
    event = event or {}
    if event.get("type") == "REQUEST" or "routeArn" in event:
        return authorize(event)
    if (event.get("requestContext") or {}).get("http"):
        return get_me(event)
    return http.bad_request("unrecognized event shape for the authorizer function")

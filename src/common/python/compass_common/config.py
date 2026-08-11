"""Compass runtime configuration - one place that reads the environment.

Every Lambda in the layer resolves its settings here so the env-var contract
lives in exactly one file. Values are read from ``os.environ`` at call time
(not import time) so tests can set/patch env vars after import, and so a warm
Lambda picks up nothing stale.

Environment variables (contract - see docs/CONTRACTS.md)
------------------------------------------------------
DB_HOST             Aurora/RDS cluster endpoint (required at runtime).
DB_NAME             Database name (required at runtime).
DB_SECRET_ARN       Secrets Manager ARN holding {"username","password"} for the
                    DB *login* role (which is a member of ``compass_app``).
DB_SCHEMA           Postgres schema for search_path.        default "compass"
BEDROCK_CHAT_MODEL  Bedrock chat/summary model id.          default "amazon.nova-lite-v1:0"
BEDROCK_EMBED_MODEL Bedrock embedding model id.             default "amazon.titan-embed-text-v2:0"
EXPORT_MAX_ROWS     Aggregation-guard threshold for /export. default 5000
AWS_REGION          Region for AWS clients.                 default "us-east-1"

The DB access-control invariants live here too as named constants so db.py,
audit.py and the RLS migration all speak the same vocabulary:

APP_ROLE            Least-privilege runtime role we ``SET ROLE`` to.  "compass_app"
ORG_SETTING         The per-transaction GUC RLS reads.               "compass.org_unit"
CORPORATE_ORG_UNIT  The org_unit that sees every row.                "ONR-Corporate"
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# --- Defaults (the contract's canonical values) --------------------------- #
DB_SCHEMA_DEFAULT = "compass"
BEDROCK_CHAT_MODEL_DEFAULT = "amazon.nova-lite-v1:0"
BEDROCK_EMBED_MODEL_DEFAULT = "amazon.titan-embed-text-v2:0"
EXPORT_MAX_ROWS_DEFAULT = 5000
AWS_REGION_DEFAULT = "us-east-1"
EMBED_DIMENSIONS_DEFAULT = 1024  # matches grants_curated.abstract_embedding vector(1024)

# --- Fixed access-control vocabulary (not env-tunable) -------------------- #
APP_ROLE = "compass_app"
ORG_SETTING = "compass.org_unit"
CORPORATE_ORG_UNIT = "ONR-Corporate"


def _get(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is not None and val != "":
        return val
    return default


# --- Per-setting accessors (read env at call time) ------------------------ #
def db_host() -> str:
    return os.environ["DB_HOST"]


def db_name() -> str:
    return os.environ["DB_NAME"]


def db_secret_arn() -> str:
    return os.environ["DB_SECRET_ARN"]


def db_schema() -> str:
    return _get("DB_SCHEMA", DB_SCHEMA_DEFAULT)


def bedrock_chat_model() -> str:
    return _get("BEDROCK_CHAT_MODEL", BEDROCK_CHAT_MODEL_DEFAULT)


def bedrock_embed_model() -> str:
    return _get("BEDROCK_EMBED_MODEL", BEDROCK_EMBED_MODEL_DEFAULT)


def export_max_rows() -> int:
    raw = _get("EXPORT_MAX_ROWS", str(EXPORT_MAX_ROWS_DEFAULT))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return EXPORT_MAX_ROWS_DEFAULT


def aws_region() -> str:
    return _get("AWS_REGION") or _get("AWS_DEFAULT_REGION") or AWS_REGION_DEFAULT


@dataclass(frozen=True)
class Config:
    """An immutable snapshot of the runtime configuration.

    ``db_host`` / ``db_name`` / ``db_secret_arn`` are optional on the snapshot
    so config can be inspected in environments where the DB is not wired
    (e.g. an offline import smoke test); the DB helpers still fail loudly at
    connect time if they are actually needed and missing.
    """

    db_host: str | None
    db_name: str | None
    db_secret_arn: str | None
    db_schema: str
    bedrock_chat_model: str
    bedrock_embed_model: str
    export_max_rows: int
    aws_region: str
    embed_dimensions: int = EMBED_DIMENSIONS_DEFAULT
    app_role: str = APP_ROLE
    org_setting: str = ORG_SETTING
    corporate_org_unit: str = CORPORATE_ORG_UNIT


def load_config() -> Config:
    """Snapshot the current environment into an immutable ``Config``."""
    return Config(
        db_host=os.environ.get("DB_HOST"),
        db_name=os.environ.get("DB_NAME"),
        db_secret_arn=os.environ.get("DB_SECRET_ARN"),
        db_schema=db_schema(),
        bedrock_chat_model=bedrock_chat_model(),
        bedrock_embed_model=bedrock_embed_model(),
        export_max_rows=export_max_rows(),
        aws_region=aws_region(),
    )

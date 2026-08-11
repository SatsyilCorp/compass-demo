"""compass_common - the shared Python layer for every Compass Lambda.

Five domain-free modules that carry the platform's cross-cutting concerns:

    config   env-var contract in one place (DB, Bedrock models, export cap).
    db       cached psycopg2 conn run as `compass_app` + `set_org()` RLS context.
    llm      Bedrock-only gateway (nova-lite converse, titan-v2 embeddings).
    http     HTTP API proxy responses + JWT/authorizer `get_claims()`.
    audit    append-only writer for `compass.audit_log`.

Typical handler::

    from compass_common import db, http, audit

    def handler(event, context):
        claims = http.get_claims(event)
        if not claims.is_authenticated:
            return http.unauthorized()
        conn = db.get_conn()
        with db.set_org(conn, claims.org_unit) as c, c.cursor() as cur:
            cur.execute("SELECT grant_no, title FROM grants_curated LIMIT 50")
            rows = cur.fetchall()
        return http.ok({"grants": rows})
"""
from . import audit, config, db, disclosure, http, llm

__all__ = ["config", "db", "disclosure", "llm", "http", "audit"]

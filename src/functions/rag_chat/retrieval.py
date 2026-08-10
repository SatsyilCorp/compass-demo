"""pgvector retrieval over ``grants_curated.abstract_embedding``.

Adapted from the ``satsyil_search.pgvector`` building block
(the satsyil-blocks library, satsyil_search) — same shape: a pure SQL
builder that unit-tests with no database, plus a thin executor that takes a
live connection. Specialized here for the Compass grants table:

* cosine distance (``<=>``) over the Titan-v2 1024-dim ``abstract_embedding``;
* returns ``similarity = 1 - cosine_distance`` so the UI can show relevance;
* ``amount_usd`` is DELIBERATELY not selected — it is column-revoked from
  ``compass_app`` (002_rls.sql CLS), and chat answers must not leak dollars;
* rows with no embedding yet (mid-ingest) are excluded.

RLS: the caller must run :func:`search_grants` inside
``compass_common.db.set_org(conn, claims.org_unit)`` — the SELECT then only
sees rows the caller's org is allowed to see, so retrieval (and therefore the
answer) respects row-level security by construction.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

GRANT_COLUMNS = (
    "id",
    "grant_no",
    "title",
    "abstract",
    "program_area",
    "fiscal_year",
    "awardee",
    "org_unit",
)


def embedding_to_vector_literal(embedding: Sequence[float]) -> str:
    """Render an embedding as a pgvector literal: ``[0.1,0.2,...]``."""
    return "[" + ",".join(str(float(v)) for v in embedding) + "]"


def build_grant_search_sql() -> str:
    """Parameterized cosine-ranked search over curated grants.

    Params (positional): ``(vector_literal, vector_literal, top_k)`` — the
    vector appears twice (similarity expression + ORDER BY).
    """
    cols = ", ".join(GRANT_COLUMNS)
    return (
        f"SELECT {cols}, "
        "1 - (abstract_embedding <=> %s::vector) AS similarity "
        "FROM grants_curated "
        "WHERE abstract_embedding IS NOT NULL "
        "ORDER BY abstract_embedding <=> %s::vector "
        "LIMIT %s"
    )


def search_grants(
    conn: Any, query_embedding: Sequence[float], top_k: int = 6
) -> List[Dict[str, Any]]:
    """Run the ranked search; returns dict rows including ``similarity``.

    ``conn`` must already carry the request's RLS org context (see module
    docstring).
    """
    vec = embedding_to_vector_literal(query_embedding)
    sql = build_grant_search_sql()
    with conn.cursor() as cur:
        cur.execute(sql, (vec, vec, top_k))
        rows = cur.fetchall()
    cols = list(GRANT_COLUMNS) + ["similarity"]
    return [dict(zip(cols, r)) for r in rows]

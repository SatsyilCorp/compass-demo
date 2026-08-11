"""Server-backed executive dashboard projection.

GET /dashboard returns the portfolio metrics used by the decision workspace.
The endpoint accepts four optional filters: program_area, fiscal_year,
org_unit, and q. Request values are never interpolated into SQL. PostgreSQL
row-level security remains the source of truth for row scope and column-level
security remains the source of truth for funding visibility.

Filter options are calculated before request filters are applied, but inside
the caller's RLS transaction. A viewer therefore never receives an option for
an organization they cannot read. Corporate callers use the GUC-gated
grants_curated_corp view for funding values. Every other caller reads only the
masked base table.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from compass_common import db, http


CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 60

_BASE_TABLE = "grants_curated"
_CORP_VIEW = "grants_curated_corp"
_ALLOWED_QUERY_KEYS = frozenset({"program_area", "fiscal_year", "org_unit", "q"})
_SAFE_YEAR = re.compile(r"^[0-9]{4}$")
_MAX_FILTER_LENGTH = 120
_MAX_SEARCH_LENGTH = 160


@dataclass(frozen=True)
class DashboardFilters:
    program_area: Optional[str] = None
    fiscal_year: Optional[int] = None
    org_unit: Optional[str] = None
    q: Optional[str] = None

    @property
    def has_portfolio_filter(self) -> bool:
        return any(
            value is not None
            for value in (self.program_area, self.fiscal_year, self.org_unit, self.q)
        )

    def as_response(self) -> Dict[str, Any]:
        return {
            "program_area": self.program_area,
            "fiscal_year": self.fiscal_year,
            "org_unit": self.org_unit,
            "q": self.q,
        }


def _clean_text(value: Any, *, field: str, max_length: int) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    if any(ord(char) < 32 for char in cleaned):
        raise ValueError(f"{field} contains unsupported control characters")
    return cleaned


def _parse_filters(params: Dict[str, Any]) -> DashboardFilters:
    unknown = sorted(set(params) - _ALLOWED_QUERY_KEYS)
    if unknown:
        raise ValueError(f"unsupported dashboard filter: {unknown[0]}")

    year_raw = _clean_text(
        params.get("fiscal_year"),
        field="fiscal_year",
        max_length=4,
    )
    fiscal_year: Optional[int] = None
    if year_raw is not None:
        if not _SAFE_YEAR.fullmatch(year_raw):
            raise ValueError("fiscal_year must be a four-digit year")
        fiscal_year = int(year_raw)
        if fiscal_year < 1900 or fiscal_year > 2200:
            raise ValueError("fiscal_year is outside the supported range")

    return DashboardFilters(
        program_area=_clean_text(
            params.get("program_area"),
            field="program_area",
            max_length=_MAX_FILTER_LENGTH,
        ),
        fiscal_year=fiscal_year,
        org_unit=_clean_text(
            params.get("org_unit"),
            field="org_unit",
            max_length=_MAX_FILTER_LENGTH,
        ),
        q=_clean_text(
            params.get("q"),
            field="q",
            max_length=_MAX_SEARCH_LENGTH,
        ),
    )


def _escape_like(value: str) -> str:
    """Treat percent, underscore, and backslash as search text, not patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _grant_predicates(
    filters: DashboardFilters,
    *,
    alias: str = "g",
) -> Tuple[List[str], List[Any]]:
    """Build fixed SQL predicates and a separate ordered parameter list."""
    if alias != "g":
        raise ValueError("unsupported grant alias")

    predicates: List[str] = []
    params: List[Any] = []
    if filters.program_area is not None:
        predicates.append(f"{alias}.program_area = %s")
        params.append(filters.program_area)
    if filters.fiscal_year is not None:
        predicates.append(f"{alias}.fiscal_year = %s")
        params.append(filters.fiscal_year)
    if filters.org_unit is not None:
        predicates.append(f"{alias}.org_unit = %s")
        params.append(filters.org_unit)
    if filters.q is not None:
        pattern = f"%{_escape_like(filters.q)}%"
        predicates.append(
            "(g.grant_no ILIKE %s ESCAPE '\\' "
            "OR g.title ILIKE %s ESCAPE '\\' "
            "OR COALESCE(g.abstract, '') ILIKE %s ESCAPE '\\' "
            "OR COALESCE(g.awardee, '') ILIKE %s ESCAPE '\\')"
        )
        params.extend([pattern, pattern, pattern, pattern])
    return predicates, params


def _grant_where(filters: DashboardFilters) -> Tuple[str, Tuple[Any, ...]]:
    predicates, params = _grant_predicates(filters)
    clause = f" WHERE {' AND '.join(predicates)}" if predicates else ""
    return clause, tuple(params)


def _relation(is_corporate: bool) -> str:
    return _CORP_VIEW if is_corporate else _BASE_TABLE


def _filter_options(cur) -> Dict[str, List[Any]]:
    """Return unfiltered choices inside the caller's RLS scope."""
    cur.execute(
        "SELECT DISTINCT program_area FROM grants_curated "
        "ORDER BY program_area ASC"
    )
    program_areas = [row[0] for row in cur.fetchall()]

    cur.execute(
        "SELECT DISTINCT fiscal_year FROM grants_curated "
        "ORDER BY fiscal_year DESC"
    )
    fiscal_years = [int(row[0]) for row in cur.fetchall()]

    cur.execute(
        "SELECT DISTINCT org_unit FROM grants_curated "
        "ORDER BY org_unit ASC"
    )
    org_units = [row[0] for row in cur.fetchall()]
    return {
        "program_areas": program_areas,
        "fiscal_years": fiscal_years,
        "org_units": org_units,
    }


def _funding_by_program_area(
    cur,
    is_corporate: bool,
    filters: DashboardFilters,
) -> List[Dict[str, Any]]:
    where, params = _grant_where(filters)
    relation = _relation(is_corporate)
    if is_corporate:
        query = (
            f"SELECT g.program_area, count(*), COALESCE(sum(g.amount_usd), 0) "
            f"FROM {relation} AS g{where} GROUP BY g.program_area "
            "ORDER BY count(*) DESC, g.program_area ASC"
        )
        cur.execute(query, params)
        return [
            {"program_area": row[0], "grant_count": int(row[1]), "amount_usd": float(row[2])}
            for row in cur.fetchall()
        ]

    query = (
        f"SELECT g.program_area, count(*) FROM {relation} AS g{where} "
        "GROUP BY g.program_area ORDER BY count(*) DESC, g.program_area ASC"
    )
    cur.execute(query, params)
    return [
        {"program_area": row[0], "grant_count": int(row[1]), "amount_usd": None}
        for row in cur.fetchall()
    ]


def _funding_by_fiscal_year(
    cur,
    is_corporate: bool,
    filters: DashboardFilters,
) -> List[Dict[str, Any]]:
    where, params = _grant_where(filters)
    relation = _relation(is_corporate)
    if is_corporate:
        query = (
            f"SELECT g.fiscal_year, COALESCE(sum(g.amount_usd), 0) "
            f"FROM {relation} AS g{where} GROUP BY g.fiscal_year "
            "ORDER BY g.fiscal_year ASC"
        )
        cur.execute(query, params)
        return [
            {"fiscal_year": int(row[0]), "amount_usd": float(row[1])}
            for row in cur.fetchall()
        ]

    query = (
        f"SELECT DISTINCT g.fiscal_year FROM {relation} AS g{where} "
        "ORDER BY g.fiscal_year ASC"
    )
    cur.execute(query, params)
    return [
        {"fiscal_year": int(row[0]), "amount_usd": None}
        for row in cur.fetchall()
    ]


def _quality_trend(cur, filters: DashboardFilters) -> List[Dict[str, Any]]:
    return _quality_trend_for_scope(cur, filters, is_corporate=False)


def _raw_grant_predicates(filters: DashboardFilters) -> Tuple[List[str], List[Any]]:
    """Build bound predicates against normalized grants_raw documents."""
    normalized = "r.raw_jsonb -> 'normalized'"
    predicates: List[str] = []
    params: List[Any] = []
    if filters.program_area is not None:
        predicates.append(f"{normalized} ->> 'program_area' = %s")
        params.append(filters.program_area)
    if filters.fiscal_year is not None:
        predicates.append(f"{normalized} ->> 'fiscal_year' = %s")
        params.append(str(filters.fiscal_year))
    if filters.org_unit is not None:
        predicates.append(f"{normalized} ->> 'org_unit' = %s")
        params.append(filters.org_unit)
    if filters.q is not None:
        pattern = f"%{_escape_like(filters.q)}%"
        predicates.append(
            f"({normalized} ->> 'grant_no' ILIKE %s ESCAPE '\\' "
            f"OR {normalized} ->> 'title' ILIKE %s ESCAPE '\\' "
            f"OR COALESCE({normalized} ->> 'abstract', '') ILIKE %s ESCAPE '\\' "
            f"OR COALESCE({normalized} ->> 'awardee', '') ILIKE %s ESCAPE '\\')"
        )
        params.extend([pattern, pattern, pattern, pattern])
    return predicates, params


def _quality_trend_for_scope(
    cur,
    filters: DashboardFilters,
    *,
    is_corporate: bool,
) -> List[Dict[str, Any]]:
    predicates, params = _grant_predicates(filters)
    predicate_sql = f" AND {' AND '.join(predicates)}" if predicates else ""
    curated_scope = (
        "EXISTS (SELECT 1 FROM grants_curated AS g "
        f"WHERE g.batch_id = q.batch_id{predicate_sql})"
    )
    scope_sql = f" WHERE {curated_scope}"
    query_params: List[Any] = list(params)
    if is_corporate:
        raw_predicates, raw_params = _raw_grant_predicates(filters)
        raw_filter_sql = (
            f" AND {' AND '.join(raw_predicates)}" if raw_predicates else ""
        )
        quarantined_scope = (
            "(EXISTS (SELECT 1 FROM lineage_nodes AS terminal "
            "WHERE terminal.run_id = q.run_id AND terminal.node_id = 'quarantine') "
            "AND EXISTS (SELECT 1 FROM grants_raw AS r "
            f"WHERE r.batch_id = q.batch_id{raw_filter_sql}))"
        )
        scope_sql = f" WHERE ({curated_scope} OR {quarantined_scope})"
        query_params.extend(raw_params)
    query = (
        f"SELECT q.run_id, MIN(q.created_at) AS run_started, "
        f"AVG(q.score) AS avg_score FROM grant_quality AS q{scope_sql} "
        "GROUP BY q.run_id ORDER BY run_started ASC"
    )
    cur.execute(query, tuple(query_params))
    return [
        {
            "run_id": run_id,
            "date": run_started.isoformat() if run_started else None,
            "score": round(float(avg_score), 1) if avg_score is not None else 0.0,
        }
        for run_id, run_started, avg_score in cur.fetchall()
    ]


def _top_topics(cur, filters: DashboardFilters) -> List[Dict[str, Any]]:
    predicates, params = _grant_predicates(filters)
    filter_sql = f" AND {' AND '.join(predicates)}" if predicates else ""
    latest_query = (
        f"SELECT mr.run_id FROM model_runs AS mr WHERE mr.kind = %s "
        "AND EXISTS (SELECT 1 FROM grant_topics AS visible_gt "
        "JOIN grants_curated AS g ON g.id = visible_gt.grant_id "
        f"WHERE visible_gt.run_id = mr.run_id{filter_sql}) "
        "ORDER BY mr.created_at DESC LIMIT 1"
    )
    cur.execute(latest_query, ("topic_model", *params))
    latest = cur.fetchone()
    if not latest:
        return []
    run_id = latest[0]

    topics_query = (
        f"SELECT t.topic_id, t.label, count(gt.grant_id) AS grant_count "
        "FROM topics AS t JOIN grant_topics AS gt "
        "ON gt.run_id = t.run_id AND gt.topic_id = t.topic_id "
        "JOIN grants_curated AS g ON g.id = gt.grant_id "
        f"WHERE t.run_id = %s{filter_sql} GROUP BY t.topic_id, t.label"
    )
    cur.execute(topics_query, (run_id, *params))
    rows = cur.fetchall()
    if not rows:
        return []
    total = sum(int(row[2]) for row in rows) or 1
    ranked = sorted(rows, key=lambda row: row[2], reverse=True)[:5]
    return [
        {
            "topic_id": int(row[0]),
            "label": row[1],
            "weight": round(int(row[2]) / total, 3),
        }
        for row in ranked
    ]


def _org_unit_breakdown(
    cur,
    is_corporate: bool,
    filters: DashboardFilters,
) -> List[Dict[str, Any]]:
    where, params = _grant_where(filters)
    relation = _relation(is_corporate)
    if is_corporate:
        query = (
            f"SELECT g.org_unit, count(*), COALESCE(sum(g.amount_usd), 0) "
            f"FROM {relation} AS g{where} GROUP BY g.org_unit "
            "ORDER BY count(*) DESC, g.org_unit ASC"
        )
        cur.execute(query, params)
        return [
            {"org_unit": row[0], "grant_count": int(row[1]), "amount_usd": float(row[2])}
            for row in cur.fetchall()
        ]

    query = (
        f"SELECT g.org_unit, count(*) FROM {relation} AS g{where} "
        "GROUP BY g.org_unit ORDER BY count(*) DESC, g.org_unit ASC"
    )
    cur.execute(query, params)
    return [
        {"org_unit": row[0], "grant_count": int(row[1]), "amount_usd": None}
        for row in cur.fetchall()
    ]


def _open_anomalies_count(
    cur,
    filters: DashboardFilters,
    *,
    is_corporate: bool,
) -> int:
    predicates, params = _grant_predicates(filters)
    grant_conditions = " AND ".join(["g.id = a.grant_id", *predicates])
    bound_scope = (
        "EXISTS (SELECT 1 FROM grants_curated AS g WHERE "
        f"{grant_conditions})"
    )
    include_unbound = is_corporate and not filters.has_portfolio_filter
    scope_sql = f"(a.grant_id IS NULL OR {bound_scope})" if include_unbound else bound_scope
    query = (
        f"SELECT count(*) FROM anomalies AS a "
        f"WHERE a.status = %s AND {scope_sql}"
    )
    cur.execute(query, ("open", *params))
    return int(cur.fetchone()[0])


def _pending_approvals_count(cur, *, is_corporate: bool, actor: str) -> int:
    actor_scope = "" if is_corporate else " AND requested_by = %s"
    params: Tuple[Any, ...] = ("pending",) if is_corporate else ("pending", actor)
    query = f"SELECT count(*) FROM approvals WHERE state = %s{actor_scope}"
    cur.execute(query, params)
    return int(cur.fetchone()[0])


def _compute_dashboard(
    cur,
    is_corporate: bool,
    filters: DashboardFilters,
    *,
    actor: str,
) -> Dict[str, Any]:
    filter_options = _filter_options(cur)
    program_area_rows = _funding_by_program_area(cur, is_corporate, filters)
    fiscal_year_rows = _funding_by_fiscal_year(cur, is_corporate, filters)
    quality_rows = _quality_trend_for_scope(
        cur,
        filters,
        is_corporate=is_corporate,
    )
    topic_rows = _top_topics(cur, filters)
    org_unit_rows = _org_unit_breakdown(cur, is_corporate, filters)

    total_grants = sum(row["grant_count"] for row in program_area_rows)
    total_funding_usd: Optional[float] = (
        round(sum(row["amount_usd"] for row in program_area_rows), 2)
        if is_corporate
        else None
    )
    avg_quality_score = (
        round(sum(row["score"] for row in quality_rows) / len(quality_rows), 1)
        if quality_rows
        else None
    )

    return {
        "filters_applied": filters.as_response(),
        "filter_options": filter_options,
        "kpis": {
            "total_grants": total_grants,
            "total_funding_usd": total_funding_usd,
            "active_program_areas": len(program_area_rows),
            "avg_quality_score": avg_quality_score,
            "open_anomalies": _open_anomalies_count(
                cur,
                filters,
                is_corporate=is_corporate,
            ),
            "pending_approvals": _pending_approvals_count(
                cur,
                is_corporate=is_corporate,
                actor=actor,
            ),
        },
        "funding_by_program_area": program_area_rows,
        "funding_by_fiscal_year": fiscal_year_rows,
        "quality_trend": quality_rows,
        "top_topics": topic_rows,
        "org_unit_breakdown": org_unit_rows,
    }


def _cache_key(
    org_unit: str,
    is_corporate: bool,
    filters: DashboardFilters,
    actor: str,
) -> str:
    raw = json.dumps(
        {
            "org_unit": org_unit,
            "is_corporate": is_corporate,
            "actor": actor,
            "filters": filters.as_response(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _log(**fields: Any) -> None:
    print(json.dumps(fields, default=str))


def _viewer_scope_violation(claims: http.Claims, filters: DashboardFilters) -> bool:
    return bool(
        not claims.is_corporate
        and filters.org_unit is not None
        and filters.org_unit != claims.org_unit
    )


def _actor_of(claims: http.Claims) -> str:
    return claims.username or claims.email or claims.sub or "unknown"


def handler(event, context):
    method = http.get_method(event) or "GET"
    if method == "OPTIONS":
        return http.json_response(200, {})

    claims = http.get_claims(event)
    if not claims.is_authenticated:
        return http.unauthorized()

    try:
        filters = _parse_filters(http.query_params(event))
    except ValueError as exc:
        return http.bad_request(str(exc))

    if _viewer_scope_violation(claims, filters):
        return http.forbidden("organization filter exceeds the caller's portfolio scope")

    actor = _actor_of(claims)
    key = _cache_key(
        claims.org_unit or "",
        claims.is_corporate,
        filters,
        actor,
    )
    now = time.time()
    cached = CACHE.get(key)
    if cached is not None and cached["expires"] > now:
        _log(
            fn=getattr(context, "function_name", "dashboard"),
            request_id=getattr(context, "aws_request_id", None),
            route="GET /dashboard",
            org_unit=claims.org_unit,
            cache="hit",
            filtered=filters.has_portfolio_filter,
        )
        return http.ok(cached["value"])

    try:
        conn = db.get_conn()
        with db.set_org(conn, claims.org_unit) as scoped_conn:
            with scoped_conn.cursor() as cur:
                body = _compute_dashboard(
                    cur,
                    claims.is_corporate,
                    filters,
                    actor=actor,
                )
    except Exception as exc:  # noqa: BLE001
        _log(
            fn=getattr(context, "function_name", "dashboard"),
            request_id=getattr(context, "aws_request_id", None),
            route="GET /dashboard",
            org_unit=claims.org_unit,
            error=str(exc),
        )
        return http.server_error("failed to compute dashboard")

    CACHE[key] = {"value": body, "expires": now + CACHE_TTL_SECONDS}
    _log(
        fn=getattr(context, "function_name", "dashboard"),
        request_id=getattr(context, "aws_request_id", None),
        route="GET /dashboard",
        org_unit=claims.org_unit,
        is_corporate=claims.is_corporate,
        cache="miss",
        filtered=filters.has_portfolio_filter,
        total_grants=body["kpis"]["total_grants"],
    )
    return http.ok(body)

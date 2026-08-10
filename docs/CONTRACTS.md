# Compass — Interface Contracts (locked before parallel build)

Every subsystem builds against these. Do not invent alternative shapes.

## Domain

Compass is an S&T (Science & Technology) Portfolio Intelligence platform. Core entity: a **research grant** in a Navy/ONR S&T portfolio. Everything flows: raw grant file → ingest → quality gate → curated table → catalog/lineage → analytics (topic model) → executive dashboard → export.

All data is **synthetic** (mock ONR S&T portfolio). No real CUI/PII anywhere.

## Database (PostgreSQL, schema `compass`)

Tables (see db/migrations for DDL):
- `grants_raw(id, source_file, ingested_at, raw_jsonb, batch_id)` — landing zone
- `grants_curated(id, grant_no, title, abstract, program_area, fiscal_year, amount_usd, awardee, org_unit, classification_band, created_at, batch_id)` — RLS-protected on `org_unit`
- `grant_quality(batch_id, rule, passed_rows, failed_rows, score, details_jsonb, run_id, created_at)`
- `lineage_nodes(run_id, node_id, kind, label, meta_jsonb)` and `lineage_edges(run_id, from_node, to_node)`
- `topics(run_id, topic_id, label, top_terms, trend_jsonb, created_at)` and `grant_topics(grant_id, topic_id, weight)`
- `anomalies(id, grant_id, kind, severity, reason, status, created_at)`
- `approvals(id, subject_type, subject_id, state, requested_by, decided_by, decided_at, note)`
- `licenses(id, vendor, product, datasets, entitlements, seats_used, seats_total, renews_on, owner, status)`
- `model_runs(run_id, kind, params_jsonb, metrics_jsonb, recommendation, created_at)`
- `audit_log(id, actor, action, resource, detail_jsonb, at)` — immutable, for export/aggregation guard
- `_schema_migrations(name, applied_at)`

### RLS (row-level security) — REQUIRED to be real
- `grants_curated` has RLS ENABLED and **FORCE ROW LEVEL SECURITY**.
- Policy keys on `org_unit = current_setting('compass.org_unit', true)`.
- Runtime role `compass_app` is NOT the table owner (owners bypass RLS unless FORCE). Migrator owns; app connects as `compass_app`.
- Request context set per-transaction: `SET LOCAL compass.org_unit = '<from JWT claim>'`.
- Two demo personas: `poweruser` → org_unit `ONR-Corporate` (sees all via a corporate policy branch); `viewer` → org_unit `Code-30` (sees only Code-30 rows).

## API (HttpApi, JWT authorizer on EVERY route, deny-by-default)

Base: `/{stage}`. All routes require a valid Cognito access token; the authorizer maps `cognito:groups` → role and injects `org_unit`.

| Method | Route | Purpose | Element |
|---|---|---|---|
| GET | /me | current identity/role/org_unit | 1 |
| GET | /catalog | list datasets + quality score + metadata | 4 |
| GET | /catalog/{id}/lineage | lineage nodes+edges for a run | 4 |
| POST | /ingest/simulate | trigger a demo file-drop (dev convenience) | 3 |
| GET | /ingest/status | recent batches + quality gate results | 3 |
| GET | /stream/recent | recent streamed records (ticker) | 3 |
| POST | /analytics/run | run the topic-model routine → run_id | 5 |
| GET | /analytics/{run_id} | topics, trend, recommendation | 5 |
| GET | /dashboard | one round-trip: KPIs + all chart series | 6 |
| POST | /chat | NL Q&A (RAG over curated grants, Bedrock) | 6 |
| GET | /anomalies | open anomalies | 6 |
| POST | /approvals | create/advance an approval | 6 |
| GET | /licenses | license lifecycle table | 6 |
| POST | /export | filtered export (csv|json|parquet); enforces RLS/CLS + aggregation guard + audit | 7 |
| GET | /openapi.json | served OpenAPI 3.1 contract | 7 |

Aggregation guard: `/export` blocks (HTTP 428, "approval required") if requested row count > `EXPORT_MAX_ROWS` (default 5000) unless an approval token is attached. Every export writes `audit_log`.

## LLM (in-boundary only)
- Transport: **Bedrock**. `amazon.nova-lite-v1:0` for chat/summary, `amazon.titan-embed-text-v2:0` for embeddings. No public Anthropic API in any narrated/recorded path (IL5 boundary story).
- Gateway: reuse `satsyil_llm` `bedrock_transport`.

## Frontend (Next.js 15 App Router, static export → S3/CloudFront)
- Env: `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_COGNITO_*`, `NEXT_PUBLIC_AUTH_DISABLED`, `NEXT_PUBLIC_USE_MOCK`.
- Pages map 1:1 to elements: `/login`, `/catalog`, `/catalog/[id]` (lineage), `/ingest`, `/analytics`, `/dashboard`, `/export`, `/licenses`, `/admin/pipeline`.
- Mock mode (`USE_MOCK=true`) renders every page on fixture data with auth disabled — the zero-AWS demo/dev path.

## Naming
- Stack: `compass-demo`. Resource prefix: `compass`. DB schema: `compass`. Region: us-east-1.

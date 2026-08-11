-- 001_schema.sql - Compass core schema (idempotent)
-- Applied via the migrator Lambda in-VPC. All objects live in schema `compass`.

CREATE SCHEMA IF NOT EXISTS compass;
SET search_path TO compass, public;

CREATE TABLE IF NOT EXISTS _schema_migrations (
  name TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- pgvector for RAG retrieval over abstracts
CREATE EXTENSION IF NOT EXISTS vector;

-- Landing zone: raw ingested payloads, one row per source record
CREATE TABLE IF NOT EXISTS grants_raw (
  id            BIGSERIAL PRIMARY KEY,
  source_file   TEXT NOT NULL,
  batch_id      TEXT NOT NULL,
  ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  raw_jsonb     JSONB NOT NULL
);

-- Curated, RLS-protected grants (the portfolio)
CREATE TABLE IF NOT EXISTS grants_curated (
  id                 BIGSERIAL PRIMARY KEY,
  grant_no           TEXT UNIQUE NOT NULL,
  title              TEXT NOT NULL,
  abstract           TEXT,
  abstract_embedding vector(1024),
  program_area       TEXT NOT NULL,
  fiscal_year        INT NOT NULL,
  amount_usd         NUMERIC(14,2) NOT NULL,
  awardee            TEXT,
  org_unit           TEXT NOT NULL,              -- RLS key
  classification_band TEXT NOT NULL DEFAULT 'CUI-Mock',
  batch_id           TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_grants_org ON grants_curated(org_unit);
CREATE INDEX IF NOT EXISTS ix_grants_fy  ON grants_curated(fiscal_year);
CREATE INDEX IF NOT EXISTS ix_grants_prog ON grants_curated(program_area);

-- Data quality results per batch/run (score is shown WITH its formula in the UI)
CREATE TABLE IF NOT EXISTS grant_quality (
  batch_id     TEXT NOT NULL,
  run_id       TEXT NOT NULL,
  rule         TEXT NOT NULL,
  passed_rows  INT NOT NULL,
  failed_rows  INT NOT NULL,
  score        NUMERIC(5,2) NOT NULL,
  details_jsonb JSONB,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, rule)
);

-- Lineage graph emitted by the actual ingest/analysis run
CREATE TABLE IF NOT EXISTS lineage_nodes (
  run_id   TEXT NOT NULL,
  node_id  TEXT NOT NULL,
  kind     TEXT NOT NULL,           -- source|stage|table|model|dashboard
  label    TEXT NOT NULL,
  meta_jsonb JSONB,
  PRIMARY KEY (run_id, node_id)
);
CREATE TABLE IF NOT EXISTS lineage_edges (
  run_id    TEXT NOT NULL,
  from_node TEXT NOT NULL,
  to_node   TEXT NOT NULL,
  PRIMARY KEY (run_id, from_node, to_node)
);

-- Topic model outputs
CREATE TABLE IF NOT EXISTS topics (
  run_id    TEXT NOT NULL,
  topic_id  INT NOT NULL,
  label     TEXT NOT NULL,
  top_terms TEXT[],
  trend_jsonb JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, topic_id)
);
CREATE TABLE IF NOT EXISTS grant_topics (
  grant_id BIGINT NOT NULL,
  run_id   TEXT NOT NULL,
  topic_id INT NOT NULL,
  weight   NUMERIC(6,4) NOT NULL,
  PRIMARY KEY (grant_id, run_id, topic_id)
);

CREATE TABLE IF NOT EXISTS model_runs (
  run_id   TEXT PRIMARY KEY,
  kind     TEXT NOT NULL,
  params_jsonb JSONB,
  metrics_jsonb JSONB,
  recommendation TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS anomalies (
  id         BIGSERIAL PRIMARY KEY,
  grant_id   BIGINT,
  kind       TEXT NOT NULL,
  severity   TEXT NOT NULL,
  reason     TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approvals (
  id           BIGSERIAL PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id   TEXT NOT NULL,
  state        TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
  requested_by TEXT,
  decided_by   TEXT,
  decided_at   TIMESTAMPTZ,
  note         TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS licenses (
  id           BIGSERIAL PRIMARY KEY,
  vendor       TEXT NOT NULL,
  product      TEXT NOT NULL,
  datasets     TEXT[],
  entitlements TEXT,
  seats_used   INT,
  seats_total  INT,
  renews_on    DATE,
  owner        TEXT,
  status       TEXT NOT NULL DEFAULT 'active'
);

-- Immutable audit trail (export + aggregation guard write here)
CREATE TABLE IF NOT EXISTS audit_log (
  id       BIGSERIAL PRIMARY KEY,
  actor    TEXT NOT NULL,
  action   TEXT NOT NULL,
  resource TEXT,
  detail_jsonb JSONB,
  at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO _schema_migrations(name) VALUES ('001_schema')
  ON CONFLICT (name) DO NOTHING;

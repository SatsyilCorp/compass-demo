-- 003_security_hardening.sql
-- Close broad runtime grants, enforce append-only audit, bind corporate
-- funding access to the corporate RLS context, and add single-use approvals.

SET search_path TO compass, public;

-- Export approvals are short-lived capabilities. Consumption is recorded in
-- the same transaction as the authorized export.
ALTER TABLE approvals
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS consumed_by TEXT;

UPDATE approvals
   SET expires_at = COALESCE(decided_at, created_at) + interval '1 hour'
 WHERE state = 'approved'
   AND expires_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_approvals_subject_state_created
  ON approvals (subject_type, subject_id, state, created_at DESC);

-- Remove inherited table-wide access from 002. Every current and future table
-- must receive an explicit read or write grant.
REVOKE SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON ALL TABLES IN SCHEMA compass FROM compass_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA compass
  REVOKE SELECT, INSERT, UPDATE ON TABLES FROM compass_app;

GRANT SELECT ON grants_raw, grant_quality, lineage_nodes, lineage_edges,
  topics, grant_topics, model_runs, anomalies, approvals, licenses
  TO compass_app;

GRANT INSERT ON grants_raw, grants_curated, grant_quality,
  lineage_nodes, lineage_edges, topics, grant_topics, model_runs,
  anomalies, approvals, audit_log
  TO compass_app;

GRANT UPDATE (source_file, ingested_at, raw_jsonb)
  ON grants_raw TO compass_app;
GRANT UPDATE (batch_id, passed_rows, failed_rows, score, details_jsonb, created_at)
  ON grant_quality TO compass_app;
GRANT UPDATE (kind, label, meta_jsonb)
  ON lineage_nodes TO compass_app;
GRANT UPDATE (state, decided_by, decided_at, note,
              expires_at, consumed_at, consumed_by)
  ON approvals TO compass_app;

-- A table-level SELECT grant overrides a column revoke in PostgreSQL. Remove
-- the table grant first, then grant only the non-funding columns required by
-- the application. abstract_embedding remains readable for governed RAG.
REVOKE SELECT ON grants_curated FROM compass_app;
GRANT SELECT (
  id, grant_no, title, abstract, abstract_embedding, program_area,
  fiscal_year, awardee, org_unit, classification_band, batch_id, created_at
) ON grants_curated TO compass_app;

-- The shared runtime role serves both personas, so the corporate view must
-- enforce its own GUC gate. A non-corporate context receives no rows and the
-- base table cannot expose amount_usd at all.
CREATE OR REPLACE VIEW grants_curated_corp
  WITH (security_barrier = true)
AS
  SELECT *
    FROM grants_curated
   WHERE current_setting('compass.org_unit', true) = 'ONR-Corporate';

REVOKE ALL ON grants_curated_corp FROM compass_app;
GRANT SELECT ON grants_curated_corp TO compass_app;

-- Runtime audit access is read plus append only. The trigger also protects
-- against accidental mutation by elevated operational sessions.
REVOKE ALL ON audit_log FROM compass_app;
GRANT SELECT, INSERT ON audit_log TO compass_app;

CREATE OR REPLACE FUNCTION reject_audit_log_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'compass.audit_log is append-only';
END;
$$;

DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log;
CREATE TRIGGER audit_log_append_only
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();

INSERT INTO _schema_migrations(name) VALUES ('003_security_hardening')
  ON CONFLICT (name) DO NOTHING;

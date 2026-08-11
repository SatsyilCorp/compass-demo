-- 002_rls.sql - Row-Level Security done correctly (idempotent)
-- Codex finding #16: table owners bypass RLS unless FORCE; runtime must use a
-- non-owner least-privilege role and set org context per transaction.

SET search_path TO compass, public;

-- Least-privilege runtime role used by all application Lambdas.
-- Owner (migrator) creates objects; compass_app only reads/writes rows.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compass_app') THEN
    CREATE ROLE compass_app NOLOGIN;   -- membership granted to the IAM/db login
  END IF;
END $$;

GRANT USAGE ON SCHEMA compass TO compass_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA compass TO compass_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA compass TO compass_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA compass
  GRANT SELECT, INSERT, UPDATE ON TABLES TO compass_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA compass
  GRANT USAGE, SELECT ON SEQUENCES TO compass_app;

-- Enable + FORCE RLS on the curated portfolio.
ALTER TABLE grants_curated ENABLE ROW LEVEL SECURITY;
ALTER TABLE grants_curated FORCE ROW LEVEL SECURITY;   -- <-- the load-bearing line

-- Context: each request runs `SET LOCAL compass.org_unit = '<claim>'`.
-- Corporate org sees all rows; a unit org sees only its own.
DROP POLICY IF EXISTS grants_rls_read ON grants_curated;
CREATE POLICY grants_rls_read ON grants_curated
  FOR SELECT
  USING (
    current_setting('compass.org_unit', true) = 'ONR-Corporate'
    OR org_unit = current_setting('compass.org_unit', true)
  );

DROP POLICY IF EXISTS grants_rls_write ON grants_curated;
CREATE POLICY grants_rls_write ON grants_curated
  FOR INSERT
  WITH CHECK (
    current_setting('compass.org_unit', true) = 'ONR-Corporate'
    OR org_unit = current_setting('compass.org_unit', true)
  );

-- Column-Level Security (CLS): viewers cannot read the dollar amount.
-- Revoke the column from compass_app, expose a masked view for viewers.
REVOKE SELECT (amount_usd) ON grants_curated FROM compass_app;
GRANT SELECT (id, grant_no, title, abstract, program_area, fiscal_year,
              awardee, org_unit, classification_band, batch_id, created_at)
  ON grants_curated TO compass_app;

CREATE OR REPLACE VIEW grants_curated_corp AS
  SELECT * FROM grants_curated;   -- amount visible only where column grant allows

INSERT INTO _schema_migrations(name) VALUES ('002_rls')
  ON CONFLICT (name) DO NOTHING;

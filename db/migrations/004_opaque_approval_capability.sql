-- 004_opaque_approval_capability.sql
-- Add the verifier required by opaque, one-time approval capabilities.

SET search_path TO compass, public;

-- The plaintext capability is returned once and never stored. Application
-- code stores only the lowercase SHA-256 digest in this verifier column.
ALTER TABLE approvals
  ADD COLUMN IF NOT EXISTS capability_hash TEXT;

-- Migration 003 removed table-wide UPDATE. Grant only the new verifier column
-- required by the approval decision transaction.
GRANT UPDATE (capability_hash)
  ON approvals TO compass_app;

INSERT INTO _schema_migrations(name)
VALUES ('004_opaque_approval_capability')
ON CONFLICT (name) DO NOTHING;

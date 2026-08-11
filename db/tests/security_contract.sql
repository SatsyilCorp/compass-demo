\set ON_ERROR_STOP on

SET search_path TO compass, public;
GRANT compass_app TO CURRENT_USER;

INSERT INTO grants_curated
  (grant_no, title, program_area, fiscal_year, amount_usd, org_unit)
VALUES
  ('C-1', 'Corporate sample', 'AI', 2026, 100.00, 'Code-20'),
  ('V-1', 'Viewer sample', 'Ocean', 2026, 50.00, 'Code-30');

SET ROLE compass_app;
SET compass.org_unit = 'Code-30';

DO $check$
DECLARE visible_rows integer;
BEGIN
  SELECT count(*) INTO visible_rows FROM grants_curated;
  IF visible_rows <> 1 THEN
    RAISE EXCEPTION 'viewer expected one RLS row, got %', visible_rows;
  END IF;
END
$check$;

DO $check$
DECLARE blocked boolean := false;
BEGIN
  BEGIN
    PERFORM amount_usd FROM grants_curated;
  EXCEPTION WHEN insufficient_privilege THEN
    blocked := true;
  END;
  IF NOT blocked THEN
    RAISE EXCEPTION 'viewer read amount_usd unexpectedly succeeded';
  END IF;
END
$check$;

DO $check$
DECLARE visible_rows integer;
BEGIN
  SELECT count(*) INTO visible_rows FROM grants_curated_corp;
  IF visible_rows <> 0 THEN
    RAISE EXCEPTION 'viewer corporate view leaked % row(s)', visible_rows;
  END IF;
END
$check$;

DO $check$
DECLARE blocked boolean := false;
BEGIN
  BEGIN
    UPDATE grants_curated SET title = 'forbidden' WHERE grant_no = 'V-1';
  EXCEPTION WHEN insufficient_privilege THEN
    blocked := true;
  END;
  IF NOT blocked THEN
    RAISE EXCEPTION 'broad curated update unexpectedly succeeded';
  END IF;
END
$check$;

INSERT INTO grants_raw (source_file, batch_id, raw_jsonb)
VALUES ('safe.csv', 'batch-safe', '{}'::jsonb);
UPDATE grants_raw
   SET raw_jsonb = '{"status":"checked"}'::jsonb
 WHERE batch_id = 'batch-safe';

INSERT INTO grant_quality
  (batch_id, run_id, rule, passed_rows, failed_rows, score, details_jsonb)
VALUES
  ('batch-safe', 'run-safe', 'required_fields', 1, 0, 100, '{}'::jsonb);
UPDATE grant_quality
   SET passed_rows = 1,
       failed_rows = 0,
       score = 100,
       details_jsonb = '{"verified":true}'::jsonb,
       created_at = now()
 WHERE run_id = 'run-safe' AND rule = 'required_fields';

INSERT INTO lineage_nodes (run_id, node_id, kind, label, meta_jsonb)
VALUES ('run-safe', 'quality-gate', 'stage', 'Quality gate', '{}'::jsonb)
ON CONFLICT (run_id, node_id) DO UPDATE
SET kind = EXCLUDED.kind,
    label = EXCLUDED.label,
    meta_jsonb = EXCLUDED.meta_jsonb;

INSERT INTO approvals
  (subject_type, subject_id, state, requested_by, decided_by, decided_at,
   expires_at)
VALUES
  ('export', 'exp-contract', 'approved', 'requester', 'reviewer', now(),
   now() + interval '1 hour');
UPDATE approvals
   SET capability_hash = repeat('a', 64),
       consumed_at = now(),
       consumed_by = 'contract-test'
 WHERE subject_id = 'exp-contract';

DO $check$
DECLARE verifier text;
BEGIN
  SELECT capability_hash INTO verifier
    FROM approvals
   WHERE subject_id = 'exp-contract';
  IF verifier <> repeat('a', 64) THEN
    RAISE EXCEPTION 'capability verifier update did not persist';
  END IF;
END
$check$;

DO $check$
DECLARE blocked boolean := false;
BEGIN
  BEGIN
    UPDATE approvals
       SET requested_by = 'tampered'
     WHERE subject_id = 'exp-contract';
  EXCEPTION WHEN insufficient_privilege THEN
    blocked := true;
  END;
  IF NOT blocked THEN
    RAISE EXCEPTION 'unrelated approval column update unexpectedly succeeded';
  END IF;
END
$check$;

INSERT INTO audit_log (actor, action, resource)
VALUES ('test', 'security_check', 'audit_log');

DO $check$
DECLARE blocked boolean := false;
BEGIN
  BEGIN
    UPDATE audit_log SET action = 'tampered' WHERE actor = 'test';
  EXCEPTION WHEN insufficient_privilege THEN
    blocked := true;
  END;
  IF NOT blocked THEN
    RAISE EXCEPTION 'runtime audit update unexpectedly succeeded';
  END IF;
END
$check$;

SET compass.org_unit = 'ONR-Corporate';
DO $check$
DECLARE total numeric;
BEGIN
  SELECT sum(amount_usd) INTO total FROM grants_curated_corp;
  IF total <> 150.00 THEN
    RAISE EXCEPTION 'corporate view expected 150, got %', total;
  END IF;
END
$check$;

RESET ROLE;

DO $check$
DECLARE blocked boolean := false;
DECLARE failure_message text;
BEGIN
  BEGIN
    UPDATE audit_log SET action = 'owner-tampered' WHERE actor = 'test';
  EXCEPTION WHEN raise_exception THEN
    GET STACKED DIAGNOSTICS failure_message = MESSAGE_TEXT;
    IF failure_message = 'compass.audit_log is append-only' THEN
      blocked := true;
    ELSE
      RAISE;
    END IF;
  END;
  IF NOT blocked THEN
    RAISE EXCEPTION 'audit append-only trigger did not block owner update';
  END IF;
END
$check$;

SELECT 'OK database security contract passed' AS result;
